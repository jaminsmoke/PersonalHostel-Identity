#!/usr/bin/env python3
"""Smoke E2E destructivo y autolimpiable del perfil de establecimiento en staging."""

import argparse
import io
import uuid

import httpx2 as httpx
from PIL import Image


def _expect(response: httpx.Response, status_code: int, step: str) -> dict:
    if response.status_code != status_code:
        raise RuntimeError(f"{step}: HTTP {response.status_code}: {response.text[:500]}")
    if not response.content:
        return {}
    return response.json()


def _logo(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (80, 60), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def run(base_url: str) -> None:
    base_url = base_url.rstrip("/")
    email = f"smoke-perfil-{uuid.uuid4()}@example.com"
    password = f"Smoke-{uuid.uuid4()}-Aa1!"
    token: str | None = None
    last_slug: str | None = None

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        try:
            _expect(
                client.post(
                    f"{base_url}/v1/auth/negocio/registro",
                    json={
                        "nombre_mostrar": "Organización Smoke",
                        "email": email,
                        "password": password,
                        "tipo_establecimiento": "bar",
                    },
                ),
                201,
                "registro",
            )
            login = _expect(
                client.post(
                    f"{base_url}/v1/auth/negocio/login",
                    json={"email": email, "password": password},
                ),
                200,
                "login",
            )
            token = login["token"]
            headers = {"Authorization": f"Bearer {token}"}

            cuenta = _expect(
                client.patch(
                    f"{base_url}/v1/auth/negocio/me",
                    headers=headers,
                    json={"nombre_mostrar": "Grupo Smoke"},
                ),
                200,
                "actualizar organización",
            )
            assert cuenta["nombre_mostrar"] == "Grupo Smoke"

            primero = _expect(
                client.post(
                    f"{base_url}/v1/establecimientos",
                    headers=headers,
                    json={"nombre": "Café Smoke", "tipo_establecimiento": "cafeteria"},
                ),
                201,
                "crear primer establecimiento",
            )
            segundo = _expect(
                client.post(
                    f"{base_url}/v1/establecimientos",
                    headers=headers,
                    json={"nombre": "Pub Smoke", "tipo_establecimiento": "pub"},
                ),
                201,
                "crear segundo establecimiento",
            )
            first_id = primero["id"]
            second_id = segundo["id"]

            actualizado = _expect(
                client.patch(
                    f"{base_url}/v1/establecimientos/{first_id}",
                    headers=headers,
                    json={"nombre": "Restaurante Smoke", "tipo_establecimiento": "restaurante"},
                ),
                200,
                "actualizar establecimiento",
            )
            assert actualizado["tipo_establecimiento"] == "restaurante"

            _expect(
                client.post(
                    f"{base_url}/v1/establecimientos/{first_id}/logo",
                    headers=headers,
                    files={"logo": ("smoke.png", _logo((20, 80, 200)), "image/png")},
                ),
                200,
                "subir logo local",
            )

            link_path = f"{base_url}/v1/establecimientos/{first_id}/enlaces"
            enlace = _expect(
                client.post(link_path, headers=headers, json={"tipo": "ficha_negocio"}),
                201,
                "crear enlace ficha",
            )
            repetido = _expect(
                client.post(link_path, headers=headers, json={"tipo": "ficha_negocio"}),
                200,
                "repetir enlace ficha",
            )
            assert repetido["id"] == enlace["id"]
            assert enlace["url_publica"].startswith("https://ficha.siberia.solutions/negocio?slug=")

            ficha = _expect(
                client.get(f"{base_url}/v1/negocio/ficha", params={"slug": enlace["slug"]}),
                200,
                "leer ficha pública",
            )
            assert ficha["establecimiento_id"] == first_id
            assert ficha["nombre"] == "Restaurante Smoke"
            assert ficha["tipo_establecimiento"] == "restaurante"
            assert "establecimientos" not in ficha
            assert ficha["logo_url"]
            logo = client.get(f"{base_url}{ficha['logo_url']}")
            if logo.status_code != 200 or logo.headers.get("content-type") != "image/webp":
                raise RuntimeError("servir logo público: respuesta inesperada")

            rotado = _expect(
                client.post(
                    f"{link_path}/{enlace['id']}/rotar",
                    headers=headers,
                    json={},
                ),
                201,
                "rotar enlace ficha",
            )
            last_slug = rotado["slug"]
            _expect(
                client.get(f"{base_url}/v1/negocio/ficha", params={"slug": enlace["slug"]}),
                410,
                "rechazar enlace anterior",
            )
            _expect(
                client.get(f"{base_url}/v1/negocio/ficha", params={"slug": last_slug}),
                200,
                "aceptar enlace rotado",
            )

            carta = _expect(
                client.post(
                    f"{base_url}/v1/establecimientos/{second_id}/enlaces",
                    headers=headers,
                    json={"tipo": "carta"},
                ),
                201,
                "crear enlace carta",
            )
            assert carta["url_publica"].startswith("https://carta.siberia.solutions/carta?slug=")
            _expect(
                client.get(f"{base_url}/v1/negocio/carta", params={"slug": carta["slug"]}),
                200,
                "leer carta pública",
            )
            if client.get(rotado["url_publica"]).status_code != 200:
                raise RuntimeError("render web de ficha: respuesta inesperada")
            if client.get(carta["url_publica"]).status_code != 200:
                raise RuntimeError("render web de carta: respuesta inesperada")
        finally:
            if token is not None:
                cleanup = client.request(
                    "DELETE",
                    f"{base_url}/v1/auth/negocio/me",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"password": password},
                )
                if cleanup.status_code != 200:
                    raise RuntimeError(
                        f"limpieza: HTTP {cleanup.status_code}: {cleanup.text[:500]}"
                    )

        denied = client.post(
            f"{base_url}/v1/auth/negocio/login",
            json={"email": email, "password": password},
        )
        if denied.status_code != 401:
            raise RuntimeError("limpieza: la cuenta sintética aún permite login")
        if last_slug is not None:
            removed = client.get(f"{base_url}/v1/negocio/ficha", params={"slug": last_slug})
            if removed.status_code != 404:
                raise RuntimeError("limpieza: el enlace sintético aún existe")

    print("Smoke staging OK: perfil, aislamiento, logo, enlaces, rotación, web y limpieza.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://negocio.siberia.solutions")
    args = parser.parse_args()
    run(args.base_url)


if __name__ == "__main__":
    main()
