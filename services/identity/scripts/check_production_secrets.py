#!/usr/bin/env python3
"""Valida secretos de producción sin imprimir nunca sus valores."""

from __future__ import annotations

import argparse
import base64
import binascii
import sys
from collections.abc import Mapping
from enum import StrEnum
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


class SecretError(StrEnum):
    POSTGRES_MISSING = "POSTGRES_PASSWORD: ausente o vacío"
    POSTGRES_DUPLICATE = "POSTGRES_PASSWORD: definición duplicada"
    POSTGRES_DEFAULT = "POSTGRES_PASSWORD: coincide con un default conocido"
    POSTGRES_SHORT = "POSTGRES_PASSWORD: longitud insuficiente"
    SESSION_MISSING = "SESSION_SECRET: ausente o vacío"
    SESSION_DUPLICATE = "SESSION_SECRET: definición duplicada"
    SESSION_DEFAULT = "SESSION_SECRET: coincide con un default conocido"
    SESSION_SHORT = "SESSION_SECRET: longitud insuficiente"
    QR_MISSING = "QR_SIGNING_KEY: ausente o vacío"
    QR_DUPLICATE = "QR_SIGNING_KEY: definición duplicada"
    QR_DEFAULT = "QR_SIGNING_KEY: coincide con un default conocido"
    QR_SHORT = "QR_SIGNING_KEY: longitud insuficiente"
    QR_FORMAT = "QR_SIGNING_KEY: debe ser base64 de 32 bytes"
    EMAIL_MISSING = "EMAIL_PASSWORD: ausente o vacío"
    EMAIL_DUPLICATE = "EMAIL_PASSWORD: definición duplicada"
    EMAIL_SHORT = "EMAIL_PASSWORD: longitud insuficiente"
    GRAFANA_MISSING = "GRAFANA_ADMIN_PASSWORD: ausente o vacío"
    GRAFANA_DUPLICATE = "GRAFANA_ADMIN_PASSWORD: definición duplicada"
    GRAFANA_DEFAULT = "GRAFANA_ADMIN_PASSWORD: coincide con un default conocido"
    GRAFANA_SHORT = "GRAFANA_ADMIN_PASSWORD: longitud insuficiente"
    NON_REAL_DATA = "ALLOW_NON_REAL_DATA: debe ser false en producción"
    R2_ACCOUNT_MISSING = "R2_ACCOUNT_ID: requerido cuando el backup externo está activo"
    R2_BUCKET_MISSING = "R2_BUCKET: requerido cuando el backup externo está activo"
    R2_ACCESS_MISSING = "R2_ACCESS_KEY_ID: requerido cuando el backup externo está activo"
    R2_SECRET_MISSING = "R2_SECRET_ACCESS_KEY: requerido cuando el backup externo está activo"
    RESTIC_PASSWORD_FILE_MISSING = (
        "RESTIC_PASSWORD_FILE: requerido cuando el backup externo está activo"
    )


MISSING_ERRORS = {
    "POSTGRES_PASSWORD": SecretError.POSTGRES_MISSING,
    "SESSION_SECRET": SecretError.SESSION_MISSING,
    "QR_SIGNING_KEY": SecretError.QR_MISSING,
    "EMAIL_PASSWORD": SecretError.EMAIL_MISSING,
    "GRAFANA_ADMIN_PASSWORD": SecretError.GRAFANA_MISSING,
}
DUPLICATE_ERRORS = {
    "POSTGRES_PASSWORD": SecretError.POSTGRES_DUPLICATE,
    "SESSION_SECRET": SecretError.SESSION_DUPLICATE,
    "QR_SIGNING_KEY": SecretError.QR_DUPLICATE,
    "EMAIL_PASSWORD": SecretError.EMAIL_DUPLICATE,
    "GRAFANA_ADMIN_PASSWORD": SecretError.GRAFANA_DUPLICATE,
}
DEFAULT_ERRORS = {
    "POSTGRES_PASSWORD": SecretError.POSTGRES_DEFAULT,
    "SESSION_SECRET": SecretError.SESSION_DEFAULT,
    "QR_SIGNING_KEY": SecretError.QR_DEFAULT,
    "GRAFANA_ADMIN_PASSWORD": SecretError.GRAFANA_DEFAULT,
}
SHORT_ERRORS = {
    "POSTGRES_PASSWORD": SecretError.POSTGRES_SHORT,
    "SESSION_SECRET": SecretError.SESSION_SHORT,
    "QR_SIGNING_KEY": SecretError.QR_SHORT,
    "EMAIL_PASSWORD": SecretError.EMAIL_SHORT,
    "GRAFANA_ADMIN_PASSWORD": SecretError.GRAFANA_SHORT,
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
    except binascii.Error, ValueError:
        return False


def validate_production_secrets(
    values: Mapping[str, str], duplicates: set[str] | None = None
) -> list[SecretError]:
    """Devuelve errores sanitizados; nunca incorpora valores a los mensajes."""
    errors: list[SecretError] = []
    duplicates = duplicates or set()
    for key, minimum in REQUIRED_SECRETS.items():
        value = values.get(key, "")
        if key in duplicates:
            errors.append(DUPLICATE_ERRORS[key])
        if not value:
            errors.append(MISSING_ERRORS[key])
            continue
        if value in KNOWN_DEFAULTS.get(key, set()):
            errors.append(DEFAULT_ERRORS[key])
        if len(value) < minimum:
            errors.append(SHORT_ERRORS[key])
    qr_key = values.get("QR_SIGNING_KEY", "")
    if qr_key and not _valid_qr_key(qr_key):
        errors.append(SecretError.QR_FORMAT)
    if values.get("ALLOW_NON_REAL_DATA", "").lower() != "false":
        errors.append(SecretError.NON_REAL_DATA)
    if values.get("OFFSITE_BACKUP_ENABLED", "").lower() == "true":
        offsite_required = {
            "R2_ACCOUNT_ID": SecretError.R2_ACCOUNT_MISSING,
            "R2_BUCKET": SecretError.R2_BUCKET_MISSING,
            "R2_ACCESS_KEY_ID": SecretError.R2_ACCESS_MISSING,
            "R2_SECRET_ACCESS_KEY": SecretError.R2_SECRET_MISSING,
            "RESTIC_PASSWORD_FILE": SecretError.RESTIC_PASSWORD_FILE_MISSING,
        }
        for key, error in offsite_required.items():
            if not values.get(key):
                errors.append(error)
    return errors


def validate_env_text(text: str) -> list[SecretError]:
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
            print("ERROR: " + error.value, file=sys.stderr)
        return 1
    print("Secretos de producción: configuración válida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
