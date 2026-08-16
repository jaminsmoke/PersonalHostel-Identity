#!/usr/bin/env python3
"""Crea las cuentas de prueba canónicas (camarero test + negocio test).

Uso:
    python services/identity/scripts/seed_test_accounts.py

Da de alta, con `data_origin=real` (obligatorio en staging), a:
  - Camarero:  `camarero.test@example.com`  (nick `camarero_test`)
  - Negocio:   `negocio.test@example.com`   (`Negocio Test`, tipo `bar`)

Configuración (por variable de entorno o `.env` en la raíz del repo):
  - CAMAREROS_API_URL      (default http://localhost:8080)
  - NEGOCIO_API_URL        (default http://localhost:8082)
  - TEST_CAMARERO_EMAIL    (default camarero.test@example.com)
  - TEST_CAMARERO_PASSWORD (obligatoria)
  - TEST_NEGOCIO_EMAIL     (default negocio.test@example.com)
  - TEST_NEGOCIO_PASSWORD  (obligatoria)

Idempotente: si el email ya existe (409) se omite y el proceso termina 0.
Solo usa la stdlib (`urllib`); no añade dependencias.
"""

import json
import os
import sys
import urllib.error
import urllib.request

ENV_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
)

DEFAULTS = {
    "CAMAREROS_API_URL": "http://localhost:8080",
    "NEGOCIO_API_URL": "http://localhost:8082",
    "TEST_CAMARERO_EMAIL": "camarero.test@example.com",
    "TEST_NEGOCIO_EMAIL": "negocio.test@example.com",
}


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


def config(key: str) -> str:
    """Variable de entorno > `.env` > default."""
    return os.environ.get(key) or env_value(key) or DEFAULTS.get(key, "")


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return exc.code, parsed


def seed(label: str, url: str, payload: dict) -> int:
    status, body = post_json(url, payload)
    if status in (200, 201):
        print(f"[{label}] creada: id={body.get('id')}")
        return 0
    if status == 409:
        print(f"[{label}] ya existe (409), se omite")
        return 0
    print(f"[{label}] error {status}: {body.get('detail', body)}", file=sys.stderr)
    return 1


def main() -> int:
    camarero_url = f"{config('CAMAREROS_API_URL').rstrip('/')}/v1/camareros/registro"
    negocio_url = f"{config('NEGOCIO_API_URL').rstrip('/')}/v1/auth/negocio/registro"

    camarero_password = config("TEST_CAMARERO_PASSWORD")
    negocio_password = config("TEST_NEGOCIO_PASSWORD")
    if not camarero_password or not negocio_password:
        print(
            f"Faltan TEST_CAMARERO_PASSWORD/TEST_NEGOCIO_PASSWORD en {ENV_FILE} o en el entorno.",
            file=sys.stderr,
        )
        return 1

    camarero = {
        "nombre": "Camarero",
        "apellidos": "Test",
        "nick": "camarero_test",
        "email": config("TEST_CAMARERO_EMAIL"),
        "password": camarero_password,
        "data_origin": "real",
    }
    negocio = {
        "nombre_mostrar": "Negocio Test",
        "email": config("TEST_NEGOCIO_EMAIL"),
        "password": negocio_password,
        "tipo_establecimiento": "bar",
        "data_origin": "real",
    }

    errors = seed("camarero", camarero_url, camarero)
    errors += seed("negocio", negocio_url, negocio)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
