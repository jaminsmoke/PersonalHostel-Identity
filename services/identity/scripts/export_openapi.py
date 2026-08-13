"""Exporta el OpenAPI generado por FastAPI a ``docs/openapi.json``.

Uso:
    python services/identity/scripts/export_openapi.py            # escribe el spec
    python services/identity/scripts/export_openapi.py --check    # falla si difiere

No requiere conexión a Postgres: ``app.openapi()`` construye el esquema sin
tocar la base de datos (el engine de SQLAlchemy es lazy).
"""

import argparse
import json
import sys
from pathlib import Path

IDENTITY_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = REPO_ROOT / "docs" / "openapi.json"

sys.path.insert(0, str(IDENTITY_DIR))

from app.main import app  # noqa: E402


def generate() -> str:
    """Devuelve el spec OpenAPI serializado de forma determinista."""
    spec = app.openapi()
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Sale con código distinto de 0 si el spec commiteado difiere.",
    )
    args = parser.parse_args()

    generated = generate()

    if args.check:
        current = OUT.read_text(encoding="utf-8")
        if current != generated:
            print(
                "docs/openapi.json difiere del spec generado. Regenera con:\n"
                "  python services/identity/scripts/export_openapi.py",
                file=sys.stderr,
            )
            return 1
        print("OpenAPI spec en sincronía con docs/openapi.json.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(generated, encoding="utf-8", newline="\n")
    print(f"Escrito {OUT.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
