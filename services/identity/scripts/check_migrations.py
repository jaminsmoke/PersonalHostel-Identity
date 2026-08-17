#!/usr/bin/env python3
"""Valida la reversibilidad de ambas cadenas Alembic de Identity.

Para cada cadena (camareros y negocio) ejecuta el ciclo
``upgrade head -> downgrade base -> upgrade head`` contra Postgres y sale
con 1 si cualquier paso falla, para que CI lo use como gate.

Uso:
    python scripts/check_migrations.py
    python scripts/check_migrations.py --config alembic.ini --config alembic_negocio.ini
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = ["alembic.ini", "alembic_negocio.ini"]


def run_alembic(config: str, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["alembic", "-c", config, command, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def check_chain(config: str) -> list[str]:
    errores: list[str] = []
    for step, cmd, *rest in (
        ("upgrade head", "upgrade", "head"),
        ("downgrade base", "downgrade", "base"),
        ("upgrade head (final)", "upgrade", "head"),
    ):
        proc = run_alembic(config, cmd, *rest)
        if proc.returncode != 0:
            errores.append(f"[{config}] {step} falló:\n{proc.stderr.strip()}")
    return errores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        action="append",
        default=DEFAULTS,
        help="Fichero .ini de Alembic a validar (repetible).",
    )
    args = parser.parse_args()

    fallos: list[str] = []
    for config in args.config:
        fallos.extend(check_chain(config))

    if fallos:
        for f in fallos:
            print(f"::error::{f}", file=sys.stderr)
        return 1
    print("Migraciones OK: ambas cadenas son reversibles (upgrade→downgrade→upgrade).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
