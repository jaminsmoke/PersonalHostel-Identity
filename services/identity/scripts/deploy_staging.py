#!/usr/bin/env python3
"""Despliega Identity en el VPS de staging (igual que dev: git pull + compose up).

Uso:
    python services/identity/scripts/deploy_staging.py

Lee las credenciales SSH de `.env` (VPS_HOST, VPS_USER, VPS_PASSWORD) y ejecuta
en el VPS (ruta por defecto /opt/identity):
  1. `git clone` (solo la primera vez) y `git fetch + reset --hard origin/main`
  2. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

El `.env` de producción vive en /opt/identity/.env (gitignored) y se crea la
primera vez a mano (bootstrap). Este script aborta si falta.

Requiere: paramiko (pip install paramiko).
"""
import os
import sys

import paramiko

REPO = "https://github.com/jaminsmoke/PersonalHostel-Identity.git"
REMOTE_DIR = "/opt/identity"
ENV_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
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


def main() -> int:
    host = env_value("VPS_HOST")
    user = env_value("VPS_USER") or "root"
    password = env_value("VPS_PASSWORD")
    if not host or not password:
        print(f"Faltan VPS_HOST/VPS_PASSWORD en {ENV_FILE}")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host, username=user, password=password, timeout=30,
        look_for_keys=False, allow_agent=False,
    )

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

    try:
        run(f"test -d {REMOTE_DIR} || git clone {REPO} {REMOTE_DIR}")

        has_env = run(
            f"test -f {REMOTE_DIR}/.env && echo yes || echo no", check=False
        ).strip().splitlines()[-1].strip()
        if has_env != "yes":
            print(
                f"Falta {REMOTE_DIR}/.env en el VPS. "
                "Crea el .env de producción (bootstrap) antes de desplegar."
            )
            client.close()
            return 1

        run(f"cd {REMOTE_DIR} && git fetch origin && git reset --hard origin/main")
        run(
            f"cd {REMOTE_DIR} && "
            "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
            "up -d --build"
        )
    finally:
        client.close()

    print("Despliegue OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
