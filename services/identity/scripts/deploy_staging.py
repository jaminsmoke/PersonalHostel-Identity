#!/usr/bin/env python3
"""Despliega Identity en el VPS de staging (igual que dev: git pull + compose up).

Uso:
    python services/identity/scripts/deploy_staging.py

Lee de `.env` (nunca en git):
  - VPS_HOST, VPS_USER, VPS_PASSWORD (password solo como fallback)
  - VPS_HOST_KEY (clave de host ed25519 del VPS, pinned anti-MITM)
  - VPS_SSH_KEY_PATH (opcional; por defecto ~/.ssh/identity_vps)

En el VPS (ruta por defecto /opt/identity):
  1. `git clone` (solo la primera vez) y `git fetch + reset --hard origin/main`
  2. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

El `.env` de producción vive en /opt/identity/.env (gitignored) y se crea la
primera vez a mano (bootstrap). Este script aborta si falta.

Requiere: paramiko (pip install paramiko).
"""

import os
import shlex
import sys

import paramiko

REPO = "https://github.com/jaminsmoke/PersonalHostel-Identity.git"
REMOTE_DIR = "/opt/identity"
ENV_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
)
DEFAULT_SSH_KEY = "~/.ssh/identity_vps"


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


def main() -> int:
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

        run(f"cd {remote} && git fetch origin && git reset --hard origin/main")
        run(
            f"cd {remote} && "
            "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
            "up -d --build"
        )
    finally:
        client.close()

    print("Despliegue OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
