"""Exporta los OpenAPI de los dos servicios a ``docs/``.

Uso:
    python services/identity/scripts/export_openapi.py            # escribe los specs
    python services/identity/scripts/export_openapi.py --check    # falla si difieren

El directorio de salida se puede sobreescribir con la variable ``OPENAPI_DOCS_DIR``
(útil para generar dentro de un contenedor y copiar los ficheros al host).

No requiere conexión a Postgres: ``app.openapi()`` construye el esquema sin
tocar la base de datos (el engine de SQLAlchemy es lazy).
"""

import argparse
import json
import os
import sys
from pathlib import Path

IDENTITY_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS = Path(os.environ.get("OPENAPI_DOCS_DIR", REPO_ROOT / "docs"))

sys.path.insert(0, str(IDENTITY_DIR))

from app.main import app as camareros_app  # noqa: E402
from app.main_negocio import app as negocio_app  # noqa: E402

SPECS = {
    "openapi-camareros.json": camareros_app,
    "openapi-negocio.json": negocio_app,
}


def generate(app) -> str:
    """Devuelve el spec OpenAPI serializado de forma determinista."""
    spec = app.openapi()
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Sale con código distinto de 0 si algún spec commiteado difiere.",
    )
    args = parser.parse_args()

    ok = True
    for name, app in SPECS.items():
        generated = generate(app)
        target = DOCS / name
        if args.check:
            current = target.read_text(encoding="utf-8")
            if current != generated:
                print(
                    f"docs/{name} difiere del spec generado. Regenera con:\n"
                    "  python services/identity/scripts/export_openapi.py",
                    file=sys.stderr,
                )
                ok = False
            else:
                print(f"docs/{name} en sincronía con el spec generado.")
        else:
            DOCS.mkdir(parents=True, exist_ok=True)
            target.write_text(generated, encoding="utf-8", newline="\n")
            print(f"Escrito {name}.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
