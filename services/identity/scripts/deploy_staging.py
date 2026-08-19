#!/usr/bin/env python3
"""Valida o despliega una referencia de Identity en el VPS de staging.

Uso:
    python services/identity/scripts/deploy_staging.py
    python services/identity/scripts/deploy_staging.py --ref feature/x --validate-only

Lee de `.env` (nunca en git):
  - VPS_HOST, VPS_USER, VPS_PASSWORD (password solo como fallback)
  - VPS_HOST_KEY (clave de host ed25519 del VPS, pinned anti-MITM)
  - VPS_SSH_KEY_PATH (opcional; por defecto ~/.ssh/identity_vps)

En el VPS (ruta por defecto /opt/identity):
  1. `git clone` (solo la primera vez) y `git fetch + reset --hard origin/<ref>`
  2. valida con el runner aislado y bases `_test`, o despliega con Compose de
     producción. La validación oficial no usa Docker local.

El `.env` de producción vive en /opt/identity/.env (gitignored) y se crea la
primera vez a mano (bootstrap). Este script aborta si falta.

Requiere: ``pip install -r services/identity/requirements-deploy.txt``.
"""

import argparse
import os
import re
import shlex
import sys

import paramiko

try:
    from scripts.check_production_secrets import validate_env_text
except ModuleNotFoundError:  # ejecución directa desde la raíz del repositorio
    from check_production_secrets import validate_env_text

# En consolas Windows (cp1252) el output de `docker compose` trae caracteres
# Unicode (barras de progreso, flechas) que rompen print(); forzamos UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = "https://github.com/jaminsmoke/PersonalHostel-Server.git"
REMOTE_DIR = "/opt/identity"
ENV_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
)
LOCAL_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(ENV_FILE)))
DEFAULT_SSH_KEY = "~/.ssh/identity_vps"
SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
STAGING_PUBLIC_URLS = {
    "WEB_NEGOCIO_URL_BASE": "https://web.negocio.siberia.solutions",
    "FICHA_URL_BASE": "https://web.camareros.siberia.solutions",
}


class PinnedHostKey(paramiko.MissingHostKeyPolicy):
    """Acepta solo la clave de host esperada; rechaza cualquier otra (anti-MITM)."""

    def __init__(self, expected: str):
        self.expected = expected

    def missing_host_key(self, client, hostname, key):
        presented = f"{key.get_name()} {key.get_base64()}"
        if presented != self.expected:
            raise paramiko.SSHException(
                f"Clave de host inesperada para {hostname}: {presented}. "
                "Posible MITM o VPS reinstalado; actualiza VPS_HOST_KEY en .env "
                "con `ssh-keyscan -t ed25519 <host>`."
            )


def env_value(key: str) -> str:
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def ssh_key_path() -> str:
    configured = env_value("VPS_SSH_KEY_PATH")
    return os.path.expanduser(configured or DEFAULT_SSH_KEY)


def ensure_staging_public_urls(client: paramiko.SSHClient) -> bool:
    """Actualiza atómicamente las URLs públicas no secretas del `.env` remoto."""
    path = f"{REMOTE_DIR}/.env"
    temp_path = f"{path}.deploy-tmp"
    sftp = client.open_sftp()
    try:
        sftp.stat(path)
        with sftp.open(path, "r") as source:
            raw = source.read()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        lines = text.splitlines()
        found: set[str] = set()
        changed = False
        for index, line in enumerate(lines):
            for key, value in STAGING_PUBLIC_URLS.items():
                if line.startswith(f"{key}="):
                    found.add(key)
                    replacement = f"{key}={value}"
                    if line != replacement:
                        lines[index] = replacement
                        changed = True
                    break
        for key, value in STAGING_PUBLIC_URLS.items():
            if key not in found:
                lines.append(f"{key}={value}")
                changed = True
        if not changed:
            return False
        payload = ("\n".join(lines).rstrip("\n") + "\n").encode()
        with sftp.open(temp_path, "wb") as target:
            target.write(payload)
        sftp.chmod(temp_path, 0o600)
        sftp.posix_rename(temp_path, path)
        return True
    finally:
        sftp.close()


def read_remote_env(client: paramiko.SSHClient) -> str:
    """Lee el `.env` remoto para validarlo sin registrarlo ni devolverlo al output."""
    sftp = client.open_sftp()
    try:
        with sftp.open(f"{REMOTE_DIR}/.env", "r") as source:
            raw = source.read()
        return raw.decode("utf-8") if isinstance(raw, bytes) else raw
    finally:
        sftp.close()


def validate_remote_env(client: paramiko.SSHClient) -> None:
    errors = validate_env_text(read_remote_env(client))
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise RuntimeError(f"Configuración de producción inválida:\n{details}")


def harden_remote_env_permissions(client: paramiko.SSHClient) -> None:
    """Impone mínimo privilegio al `.env` activo y sus copias históricas."""
    sftp = client.open_sftp()
    try:
        sftp.chmod(f"{REMOTE_DIR}/.env", 0o600)
        for entry in sftp.listdir_attr(REMOTE_DIR):
            if entry.filename.startswith(".env.") and entry.filename != ".env.example":
                sftp.chmod(f"{REMOTE_DIR}/{entry.filename}", 0o600)
    finally:
        sftp.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref",
        default="main",
        help="Rama remota a validar/desplegar (default: main).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Ejecuta calidad, tests y migraciones aisladas sin recrear las APIs activas.",
    )
    parser.add_argument(
        "--sync-openapi",
        action="store_true",
        help="Genera OpenAPI dentro del Docker del VPS y descarga docs al checkout local.",
    )
    parser.add_argument(
        "--smoke-profile",
        action="store_true",
        help="Ejecuta en Docker del VPS el E2E público autolimpiable del perfil de local.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Valida el .env remoto sin fetch, build, cambios de permisos ni despliegue.",
    )
    parser.add_argument(
        "--backup-restore-drill",
        action="store_true",
        help="Verifica y restaura el último backup solo en bases *_restore_test.",
    )
    parser.add_argument(
        "--quarantine-orphan-photos",
        action="store_true",
        help="Archiva fotos huérfanas verificadas antes de retirarlas del volumen activo.",
    )
    args = parser.parse_args()
    if not SAFE_REF.fullmatch(args.ref) or ".." in args.ref or args.ref.endswith("/"):
        print(f"Referencia no válida: {args.ref}")
        return 2

    host = env_value("VPS_HOST")
    user = env_value("VPS_USER") or "root"
    password = env_value("VPS_PASSWORD")
    expected_host_key = env_value("VPS_HOST_KEY")
    if not host:
        print(f"Falta VPS_HOST en {ENV_FILE}")
        return 1
    if not expected_host_key:
        print(
            f"Falta VPS_HOST_KEY en {ENV_FILE} "
            "(clave de host ed25519 del VPS; obtenerla con "
            "`ssh-keyscan -t ed25519 <host>`)."
        )
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(PinnedHostKey(expected_host_key))

    key = ssh_key_path()
    connect_kwargs = {
        "timeout": 30,
        "look_for_keys": False,
        "allow_agent": False,
    }
    if os.path.exists(key):
        connect_kwargs["key_filename"] = key
        if password:
            connect_kwargs["password"] = password  # fallback si la clave falla
        print(f"Conectando con clave SSH ({key})...")
    elif password:
        connect_kwargs["password"] = password
        print(f"AVISO: sin clave SSH en {key}; usando password (genera la clave deploy).")
    else:
        print(f"Sin clave SSH ({key}) ni VPS_PASSWORD en {ENV_FILE}")
        return 1

    client.connect(host, username=user, **connect_kwargs)

    def run(cmd: str, check: bool = True) -> str:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=900)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print("[stderr]", err.rstrip())
        if check and code != 0:
            raise RuntimeError(f"Comando falló ({code}): {cmd}")
        return out

    # shlex.quote: defensa en profundidad aunque REPO/REMOTE_DIR son constantes.
    remote = shlex.quote(REMOTE_DIR)
    repo = shlex.quote(REPO)
    try:
        run(f"test -d {remote} || git clone {repo} {remote}")

        has_env = (
            run(f"test -f {remote}/.env && echo yes || echo no", check=False)
            .strip()
            .splitlines()[-1]
            .strip()
        )
        if has_env != "yes":
            print(
                f"Falta {REMOTE_DIR}/.env en el VPS. "
                "Crea el .env de producción (bootstrap) antes de desplegar."
            )
            client.close()
            return 1

        validate_remote_env(client)
        if args.preflight_only:
            print("Preflight remoto OK: secretos válidos; no se modificó el VPS")
            return 0

        remote_ref = shlex.quote(f"origin/{args.ref}")
        run(f"cd {remote} && git fetch origin && git reset --hard {remote_ref}")
        compose = "docker compose -f docker-compose.yml -f docker-compose.prod.yml"
        if args.quarantine_orphan_photos:
            run(
                f"cd {remote} && PYTHONDONTWRITEBYTECODE=1 "
                "python3 services/identity/scripts/backup_restore.py "
                "quarantine-orphan-photos"
            )
        elif args.backup_restore_drill:
            run(
                f"cd {remote} && PYTHONDONTWRITEBYTECODE=1 "
                "python3 services/identity/scripts/backup_restore.py restore-drill"
            )
        elif args.sync_openapi:
            run(f"cd {remote} && {compose} build identity-tests")
            run(
                f"cd {remote} && {compose} run --rm "
                "--user 0:0 "
                f"-v {remote}/docs:/generated-docs "
                "-e OPENAPI_DOCS_DIR=/generated-docs identity-tests "
                "python scripts/export_openapi.py"
            )
            sftp = client.open_sftp()
            try:
                for name in ("openapi-camareros.json", "openapi-negocio.json"):
                    sftp.get(
                        f"{REMOTE_DIR}/docs/{name}",
                        os.path.join(LOCAL_REPO_ROOT, "docs", name),
                    )
            finally:
                sftp.close()
        elif args.validate_only:
            run(f"cd {remote} && {compose} up -d db")
            run(f"cd {remote} && {compose} build identity-tests")
            run(f"cd {remote} && {compose} run --rm identity-tests ruff check app tests scripts")
            run(
                f"cd {remote} && {compose} run --rm identity-tests "
                "ruff format --check app tests scripts"
            )
            run(
                f"cd {remote} && {compose} run --rm identity-tests "
                "python scripts/export_openapi.py --check"
            )
            run(
                f"cd {remote} && {compose} run --rm identity-tests "
                "python scripts/check_family_contracts.py --selftest"
            )
            run(f"cd {remote} && {compose} run --rm identity-tests")
            run(
                f"cd {remote} && {compose} exec -T db sh -c "
                '\'dropdb -U "$POSTGRES_USER" --if-exists identity_camareros_test && '
                'dropdb -U "$POSTGRES_USER" --if-exists identity_negocio_test && '
                'createdb -U "$POSTGRES_USER" identity_camareros_test && '
                'createdb -U "$POSTGRES_USER" identity_negocio_test\''
            )
            run(
                f"cd {remote} && set -a && . ./.env && set +a && "
                'export CAMAREROS_DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:'
                '${POSTGRES_PASSWORD}@db:5432/identity_camareros_test" && '
                'export NEGOCIO_DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:'
                '${POSTGRES_PASSWORD}@db:5432/identity_negocio_test" && '
                f"{compose} run --rm "
                "-e CAMAREROS_DATABASE_URL -e NEGOCIO_DATABASE_URL "
                "--entrypoint python identity-tests scripts/check_migrations.py"
            )
        elif args.smoke_profile:
            run(f"cd {remote} && {compose} build identity-tests")
            run(
                f"cd {remote} && {compose} run --rm identity-tests "
                "python scripts/smoke_staging_profile.py"
            )
        else:
            harden_remote_env_permissions(client)
            changed = ensure_staging_public_urls(client)
            print(
                "URLs públicas de staging actualizadas en el .env remoto."
                if changed
                else "URLs públicas de staging ya estaban configuradas."
            )
            run(f"cd {remote} && bash services/identity/scripts/backup_staging.sh")
            run(f"cd {remote} && {compose} up -d --build")
            # Observabilidad es prod-only y vive en un 3.er compose. Sin este
            # paso, un compose de solo 2 ficheros marca la pila como orphan y
            # un down/prune la borra (ítem #115). validate-only no la toca.
            run(f"cd {remote} && bash services/identity/scripts/obs_up.sh up")
            run(
                "curl --fail --silent --show-error http://127.0.0.1:8080/health && "
                "curl --fail --silent --show-error http://127.0.0.1:8080/v1/meta && "
                "curl --fail --silent --show-error http://127.0.0.1:8082/health && "
                "curl --fail --silent --show-error http://127.0.0.1:8082/v1/meta"
            )
    finally:
        client.close()

    if args.quarantine_orphan_photos:
        print("Cuarentena reversible de fotos completada")
    elif args.backup_restore_drill:
        print("Restore drill aislado OK")
    elif args.sync_openapi:
        print("OpenAPI generado en el VPS y sincronizado al checkout local")
    elif args.smoke_profile:
        print("Smoke público ejecutado dentro del Docker del VPS")
    else:
        print("Validación remota OK" if args.validate_only else "Despliegue OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
