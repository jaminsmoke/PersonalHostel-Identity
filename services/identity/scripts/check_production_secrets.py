#!/usr/bin/env python3
"""Valida secretos de producción sin imprimir nunca sus valores."""

from __future__ import annotations

import argparse
import base64
import binascii
import sys
from collections.abc import Mapping
from pathlib import Path

KNOWN_DEFAULTS = {
    "POSTGRES_PASSWORD": {"devlocal"},
    "SESSION_SECRET": {"BdZh-Awc4rEhsHCtzyUoufxqf7mT97y68QhilC9fxVnszS4CFmICrNRncw7vVeN2"},
    "QR_SIGNING_KEY": {"osYIdBW7fkucKVqY9St5yQKpLpDuAzJ4PeRaFMXbtDI="},
    "GRAFANA_ADMIN_PASSWORD": {"admin"},
}
REQUIRED_SECRETS = {
    "POSTGRES_PASSWORD": 16,
    "SESSION_SECRET": 48,
    "QR_SIGNING_KEY": 44,
    "EMAIL_PASSWORD": 8,
    "GRAFANA_ADMIN_PASSWORD": 12,
}


def parse_env(text: str) -> tuple[dict[str, str], set[str]]:
    """Parsea el subconjunto KEY=VALUE y devuelve también claves duplicadas."""
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in values:
            duplicates.add(key)
        values[key] = value.strip()
    return values, duplicates


def _valid_qr_key(value: str) -> bool:
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (binascii.Error, ValueError):
        return False


def validate_production_secrets(
    values: Mapping[str, str], duplicates: set[str] | None = None
) -> list[str]:
    """Devuelve errores sanitizados; nunca incorpora valores a los mensajes."""
    errors: list[str] = []
    duplicates = duplicates or set()
    for key, minimum in REQUIRED_SECRETS.items():
        value = values.get(key, "")
        if key in duplicates:
            errors.append(f"{key}: definición duplicada")
        if not value:
            errors.append(f"{key}: ausente o vacío")
            continue
        if value in KNOWN_DEFAULTS.get(key, set()):
            errors.append(f"{key}: coincide con un default conocido")
        if len(value) < minimum:
            errors.append(f"{key}: longitud insuficiente")
    qr_key = values.get("QR_SIGNING_KEY", "")
    if qr_key and not _valid_qr_key(qr_key):
        errors.append("QR_SIGNING_KEY: debe ser base64 de 32 bytes")
    if values.get("ALLOW_NON_REAL_DATA", "").lower() != "false":
        errors.append("ALLOW_NON_REAL_DATA: debe ser false en producción")
    return errors


def validate_env_text(text: str) -> list[str]:
    values, duplicates = parse_env(text)
    return validate_production_secrets(values, duplicates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        errors = validate_env_text(args.env_file.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"No se pudo leer el fichero de entorno: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Secretos de producción: configuración válida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
