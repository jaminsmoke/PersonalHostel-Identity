#!/usr/bin/env python3
"""Comprueba que los clientes de la familia no piden rutas que Identity ya no expone
y deja un informe de aprovechamiento (summary de Actions / stdout).

Es el espejo de ``PersonalComander/scripts/check_family_contracts.py``: cada
miembro de PersonalHostel cuida sus propias integraciones con el resto.

Uso:
    python scripts/check_family_contracts.py \\
        --camareros-openapi docs/openapi-camareros.json \\
        --negocio-openapi docs/openapi-negocio.json \\
        --bar-src path/IdentityNegocioClient.kt \\
        --commander-src path/IdentityCliente.kt \\
        --web-src services/web-camareros/static/app.js

    python scripts/check_family_contracts.py --selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Captura rutas de Identity en literales de string: /v1/..., /internal/... y /health.
RUTA_RE = re.compile(r'"((?:/v1/|/internal/|/health)[^"]*)"')

PARAM_RE = re.compile(r"\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*")
QUERY_SUFFIX_VAR_RE = re.compile(r"(?<!/)\$[A-Za-z_][A-Za-z0-9_]*$")


def openapi_paths(path: Path) -> set[str]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise ValueError(f"{path} no tiene objeto paths")
    return {normalize(p) for p in paths}


def client_paths(fuentes: list[str]) -> set[str]:
    rutas: set[str] = set()
    for fuente in fuentes:
        rutas.update(normalize(m) for m in RUTA_RE.findall(fuente))
    return rutas


def fusionar_concatenadas(src: str) -> str:
    """Une literales de ruta partidos por concatenación JS: `"/v1/x/" + tok + "/y"`
    -> `"/v1/x/*/y"`, para que la ruta completa sea comparable."""

    def _repl(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        inner = a[1:-1] + "*" + b[1:-1]
        return '"' + inner + '"'

    return re.sub(
        r'("(?:/v1/|/internal/|/health)[^"]*")\s*\+\s*[^\"+\n]+\s*\+\s*("[^"]*")',
        _repl,
        src,
    )


def normalize(ruta: str) -> str:
    """Deja la ruta comparable: sin query, sin parámetros con nombre, sin slash final."""
    base = ruta.split("?", 1)[0].strip().rstrip("/")
    # Kotlin puede anexar una variable que contiene el query opcional:
    # ``/invitaciones$q``. No es otro segmento de ruta y no debe convertirse en ``*``.
    base = QUERY_SUFFIX_VAR_RE.sub("", base)
    return PARAM_RE.sub("*", base)


def es_interna(ruta: str) -> bool:
    return normalize(ruta).startswith("/internal")


def bullets(rutas: list[str], vacio: str = "_Ninguna._") -> str:
    if not rutas:
        return vacio
    return "\n".join(f"- `{r}`" for r in rutas)


@dataclass
class Informe:
    markdown: str
    fallos: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def comprobar(
    camareros_openapi: Path,
    negocio_openapi: Path,
    bar_srcs: list[str],
    commander_srcs: list[str],
    web_srcs: list[str],
) -> Informe:
    camareros = openapi_paths(camareros_openapi)
    negocio = openapi_paths(negocio_openapi)
    spec = camareros | negocio

    bar = client_paths(bar_srcs)
    commander = client_paths(commander_srcs)
    web = client_paths([fusionar_concatenadas(src) for src in web_srcs])

    fallos: list[str] = []
    warnings: list[str] = []

    # Rutas que piden los clientes y que Identity ya no expone -> ROJO.
    for cliente, rutas in (
        ("Bar", bar),
        ("Commander", commander),
        ("Webs (web-camareros)", web),
    ):
        for ruta in sorted(rutas):
            if ruta not in spec:
                fallos.append(f"{cliente} pide {ruta} que Identity ya no expone")

    # Clasificación de cada ruta del spec.
    usadas_bar = sorted(r for r in spec if r in bar)
    usadas_commander = sorted(r for r in spec if r in commander)
    usadas_web = sorted(r for r in spec if r in web)
    internas = sorted(r for r in spec if es_interna(r))
    usadas_por_cliente = bar | commander | web
    nadie = sorted(r for r in spec if r not in usadas_por_cliente and not es_interna(r))

    for ruta in nadie:
        warnings.append(f"Ruta pública sin consumidor de familia: {ruta}")

    markdown = f"""# Family contracts — informe (Identity)

Rojo solo si un cliente pide una ruta que Identity ya no expone.
Lo no usado no falla el job: es señal para decidir ítem o deuda.

## Rutas usadas por Bar

{bullets(usadas_bar)}

## Rutas usadas por Commander

{bullets(usadas_commander)}

## Rutas usadas por las webs (web-camareros)

{bullets(usadas_web)}

## Rutas internas (auto-llamadas entre servicios)

{bullets(internas)}

## Rutas públicas sin consumidor de familia (aviso)

{bullets(nadie)}

## Error

{bullets(fallos, "_Ninguno._")}
"""
    return Informe(markdown=markdown.strip() + "\n", fallos=fallos, warnings=warnings)


def escribir_informe(informe: Informe) -> None:
    sys.stdout.write(informe.markdown)
    if not informe.markdown.endswith("\n"):
        sys.stdout.write("\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(informe.markdown)
            if not informe.markdown.endswith("\n"):
                fh.write("\n")
    for msg in informe.warnings:
        print(f"::warning::{msg}")


def _fixtures_ok() -> tuple[dict, dict, str, str, str]:
    camareros = {
        "paths": {
            "/v1/auth/login": {},
            "/v1/camareros/me": {},
            "/v1/camareros/me/qr": {},
            "/v1/camareros/me/renovar": {},
            "/v1/camareros/me/revocar": {},
            "/v1/camareros/me/foto": {},
            "/v1/camareros/me/establecimientos": {},
            "/v1/camareros/me/visibilidad": {},
            "/v1/camareros/registro": {},
            "/v1/camareros/ficha": {},
            "/v1/keys/qr": {},
            "/v1/meta": {},
            "/health": {},
            "/internal/camareros/buscar": {},
        }
    }
    negocio = {
        "paths": {
            "/v1/auth/negocio/login": {},
            "/v1/auth/negocio/registro": {},
            "/v1/auth/negocio/me/logo": {},
            "/v1/establecimientos": {},
            "/v1/establecimientos/mios": {},
            "/v1/establecimientos/{establecimiento_id}/camareros/buscar": {},
            "/v1/establecimientos/{establecimiento_id}/miembros": {},
            "/v1/establecimientos/{establecimiento_id}/miembros/qr": {},
            "/v1/establecimientos/{establecimiento_id}/miembros/{camarero_id}": {},
            "/v1/establecimientos/{establecimiento_id}/invitaciones": {},
            "/v1/establecimientos/{establecimiento_id}/invitaciones/{invitacion_id}/revocar": {},
            "/v1/establecimientos/{establecimiento_id}/layout": {},
            "/v1/negocio/carta": {},
            "/v1/negocio/ficha": {},
            "/v1/invitaciones/{token}/aceptar": {},
            "/v1/invitaciones/{token}/rechazar": {},
        }
    }
    bar = """
        IdentityHttp.request(baseUrl, "POST", "/v1/auth/negocio/registro", ...)
        IdentityHttp.request(baseUrl, "POST", "/v1/auth/negocio/login", ...)
        IdentityHttp.request(baseUrl, "POST", "/v1/auth/negocio/me/logo", ...)
        IdentityHttp.request(baseUrl, "GET", "/v1/establecimientos/mios", ...)
        IdentityHttp.request(baseUrl, "POST", "/v1/establecimientos", ...)
        IdentityHttp.request(baseUrl, "POST", "/v1/establecimientos/$id/miembros/qr", ...)
        IdentityHttp.request(baseUrl, "GET", "/v1/establecimientos/$id/camareros/buscar?email=$q", ...)
        val q = estado?.let { "?estado=$it" } ?: ""
        IdentityHttp.request(baseUrl, "GET", "/v1/establecimientos/$id/invitaciones$q", ...)
        IdentityHttp.request(baseUrl, "POST", "/v1/establecimientos/$id/invitaciones", ...)
        IdentityHttp.request(baseUrl, "POST", "/v1/establecimientos/$id/invitaciones/$invitacionId/revocar", ...)
        IdentityHttp.request(baseUrl, "GET", "/v1/establecimientos/$id/miembros", ...)
        IdentityHttp.request(baseUrl, "DELETE", "/v1/establecimientos/$id/miembros/$camareroId", ...)
        IdentityHttp.request(baseUrl, "PUT", "/v1/establecimientos/$id/layout", ...)
    """
    commander = """
        const val REGISTRO = "/v1/camareros/registro"
        const val LOGIN = "/v1/auth/login"
        const val ME = "/v1/camareros/me"
        const val ME_QR = "/v1/camareros/me/qr"
        const val ME_RENOVAR = "/v1/camareros/me/renovar"
        const val ME_REVOCAR = "/v1/camareros/me/revocar"
        const val ME_FOTO = "/v1/camareros/me/foto"
        const val ME_ESTABLECIMIENTOS = "/v1/camareros/me/establecimientos"
        const val ME_VISIBILIDAD = "/v1/camareros/me/visibilidad"
    """
    web = """
        fetch(camarerosApiBase + "/v1/camareros/ficha?qr=" + ...)
        fetch(negocioApiBase + "/v1/negocio/ficha?slug=" + ...)
        fetch(negocioApiBase + "/v1/negocio/carta?slug=" + ...)
        fetch(negocioApiBase + "/v1/invitaciones/" + token + "/aceptar", ...)
        fetch(negocioApiBase + "/v1/invitaciones/" + token + "/rechazar", ...)
    """
    return camareros, negocio, bar, commander, web


def selftest() -> int:
    camareros, negocio, bar, commander, web = _fixtures_ok()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cam = tmp_path / "camareros.json"
        neg = tmp_path / "negocio.json"
        cam.write_text(json.dumps(camareros), encoding="utf-8")
        neg.write_text(json.dumps(negocio), encoding="utf-8")

        informe = comprobar(cam, neg, [bar], [commander], [web])
        if informe.fallos:
            print("SELFTEST FAIL: fixtures completas deberían pasar", file=sys.stderr)
            return 1
        md = informe.markdown
        if "/v1/meta" not in md or "/v1/keys/qr" not in md:
            print("SELFTEST FAIL: el informe debía listar públicas no usadas", file=sys.stderr)
            return 1
        if "/internal/camareros/buscar" not in md:
            print("SELFTEST FAIL: el informe debía listar internas", file=sys.stderr)
            return 1
        # Normalización de parámetros: $id -> {establecimiento_id}.
        if not any("/v1/establecimientos/*/miembros/qr" in line for line in md.splitlines()):
            print("SELFTEST FAIL: debía normalizar $id en /miembros/qr", file=sys.stderr)
            return 1
        if not any("/v1/establecimientos/*/camareros/buscar" in line for line in md.splitlines()):
            print("SELFTEST FAIL: debía normalizar query ?email= y $id", file=sys.stderr)
            return 1
        if not any(
            w.startswith("Ruta pública sin consumidor") and "/v1/meta" in w
            for w in informe.warnings
        ):
            print("SELFTEST FAIL: debía avisar de /v1/meta sin consumidor", file=sys.stderr)
            return 1
        if any(es_interna(w.split(": ", 1)[-1]) for w in informe.warnings):
            print("SELFTEST FAIL: no debe avisar de rutas internas", file=sys.stderr)
            return 1

        # Ruta que un cliente pide pero el spec ya no tiene -> ROJO.
        broken = dict(camareros)
        broken["paths"] = dict(camareros["paths"])
        del broken["paths"]["/v1/auth/login"]
        cam.write_text(json.dumps(broken), encoding="utf-8")
        fallos = comprobar(cam, neg, [bar], [commander], [web]).fallos
        if not any("Commander" in f and "login" in f for f in fallos):
            print("SELFTEST FAIL: debía detectar /v1/auth/login ausente", file=sys.stderr)
            return 1

        # Ruta de Bar que ya no existe -> ROJO.
        broken2 = dict(negocio)
        broken2["paths"] = dict(negocio["paths"])
        del broken2["paths"]["/v1/establecimientos/{establecimiento_id}/layout"]
        neg.write_text(json.dumps(broken2), encoding="utf-8")
        fallos2 = comprobar(cam, neg, [bar], [commander], [web]).fallos
        if not any("Bar" in f and "layout" in f for f in fallos2):
            print("SELFTEST FAIL: debía detectar layout ausente para Bar", file=sys.stderr)
            return 1

        print("SELFTEST OK")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camareros-openapi", type=Path)
    parser.add_argument("--negocio-openapi", type=Path)
    parser.add_argument("--bar-src", action="append", default=[])
    parser.add_argument("--commander-src", action="append", default=[])
    parser.add_argument("--web-src", action="append", default=[])
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not all(
        (
            args.camareros_openapi,
            args.negocio_openapi,
            args.bar_src,
            args.commander_src,
            args.web_src,
        )
    ):
        parser.error(
            "Se requieren --camareros-openapi, --negocio-openapi, --bar-src (1+), --commander-src (1+) y --web-src (1+)"
        )

    bar_srcs = [Path(p).read_text(encoding="utf-8") for p in args.bar_src]
    commander_srcs = [Path(p).read_text(encoding="utf-8") for p in args.commander_src]
    web_srcs = [Path(p).read_text(encoding="utf-8") for p in args.web_src]

    informe = comprobar(
        args.camareros_openapi,
        args.negocio_openapi,
        bar_srcs,
        commander_srcs,
        web_srcs,
    )
    escribir_informe(informe)
    if informe.fallos:
        for f in informe.fallos:
            print(f"::error::{f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
