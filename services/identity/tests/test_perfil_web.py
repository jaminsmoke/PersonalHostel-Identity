import uuid
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import text

from app.db import NegocioSessionLocal


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _cuenta(negocio_client, nombre="Organización Perfil") -> tuple[str, str]:
    email = _email("perfil-web")
    registro = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": nombre,
            "email": email,
            "password": "negocio-12345678",
            "tipo_establecimiento": "bar",
        },
    )
    assert registro.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return email, login.json()["token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _establecimiento(negocio_client, token: str, nombre: str = "Local Perfil") -> dict:
    response = negocio_client.post(
        "/v1/establecimientos", headers=_headers(token), json={"nombre": nombre}
    )
    assert response.status_code == 201
    return response.json()


def _png(color: tuple[int, int, int], size: tuple[int, int] = (1200, 800)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_perfil_web_defaults(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    est = _establecimiento(negocio_client, token)

    resp = negocio_client.get(
        f"/v1/establecimientos/{est['id']}/perfil-web",
        headers=_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["establecimiento_id"] == est["id"]
    assert body["plantilla"] == "estate_hospitality"
    assert body["tz"] == "Europe/Madrid"
    assert body["web_publica"] is True
    assert body["mostrar_equipo"] is False
    assert body["hero_url"] is None
    assert body["eslogan"] is None


def test_perfil_web_patch_parcial_y_redes(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    est = _establecimiento(negocio_client, token)

    patch = negocio_client.patch(
        f"/v1/establecimientos/{est['id']}/perfil-web",
        headers=_headers(token),
        json={
            "eslogan": "Tapas y sonrisas",
            "descripcion": "Bar de barrio con cocina de mercado.",
            "direccion": "Calle Mayor 7",
            "ciudad": "Toledo",
            "telefono": "+34925555123",
            "email_contacto": "hola@local.example",
            "web": "https://local.example",
            "redes": {"instagram": "https://instagram.com/local"},
            "color_primario": "#8B5A2B",
            "plantilla": "estate_hospitality",
        },
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["eslogan"] == "Tapas y sonrisas"
    assert body["redes"]["instagram"].endswith("/local")

    get = negocio_client.get(
        f"/v1/establecimientos/{est['id']}/perfil-web",
        headers=_headers(token),
    )
    assert get.status_code == 200
    assert get.json()["email_contacto"] == "hola@local.example"
    assert get.json()["color_primario"] == "#8B5A2B"

    assert (
        negocio_client.patch(
            f"/v1/establecimientos/{est['id']}/perfil-web",
            headers=_headers(token),
            json={},
        ).status_code
        == 422
    )


def test_perfil_web_toggles(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    est = _establecimiento(negocio_client, token)

    off = negocio_client.patch(
        f"/v1/establecimientos/{est['id']}/perfil-web",
        headers=_headers(token),
        json={"web_publica": False},
    )
    assert off.status_code == 200
    assert off.json()["web_publica"] is False

    on = negocio_client.patch(
        f"/v1/establecimientos/{est['id']}/perfil-web",
        headers=_headers(token),
        json={"mostrar_equipo": True},
    )
    assert on.status_code == 200
    assert on.json()["mostrar_equipo"] is True


def test_hero_subir_servir_y_borrar(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    est = _establecimiento(negocio_client, token)
    path = f"/v1/establecimientos/{est['id']}/hero"

    sin_hero = negocio_client.get(path, headers=_headers(token))
    assert sin_hero.status_code == 404

    upload = negocio_client.post(
        path,
        headers=_headers(token),
        files={"hero": ("portada.png", _png((40, 120, 200)), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["hero_url"] == path

    hero = negocio_client.get(path, headers=_headers(token))
    assert hero.status_code == 200
    assert hero.headers["content-type"] == "image/webp"
    assert Image.open(BytesIO(hero.content)).format == "WEBP"

    deleted = negocio_client.delete(path, headers=_headers(token))
    assert deleted.status_code == 200
    assert deleted.json()["hero_url"] is None

    assert negocio_client.get(path, headers=_headers(token)).status_code == 404


def test_galeria_crud_y_orden(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    est = _establecimiento(negocio_client, token)
    galeria = f"/v1/establecimientos/{est['id']}/galeria"

    assert negocio_client.get(galeria, headers=_headers(token)).json() == []

    primera = negocio_client.post(
        galeria,
        headers=_headers(token),
        files={"imagen": ("uno.png", _png((10, 200, 40)), "image/png")},
    )
    assert primera.status_code == 200, primera.text
    segunda = negocio_client.post(
        galeria,
        headers=_headers(token),
        files={"imagen": ("dos.png", _png((200, 40, 10)), "image/png")},
    )
    assert segunda.status_code == 200

    lista = negocio_client.get(galeria, headers=_headers(token)).json()
    assert [img["id"] for img in lista] == [primera.json()["id"], segunda.json()["id"]]

    img = negocio_client.get(primera.json()["url"], headers=_headers(token))
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/webp"

    deleted = negocio_client.delete(primera.json()["url"], headers=_headers(token))
    assert deleted.status_code == 200
    assert [i["id"] for i in negocio_client.get(galeria, headers=_headers(token)).json()] == [
        segunda.json()["id"]
    ]

    assert negocio_client.get(primera.json()["url"], headers=_headers(token)).status_code == 404


def test_perfil_web_ajena_403(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    est = _establecimiento(negocio_client, token)
    _, otro_token = _cuenta(negocio_client, nombre="Otra Organización")

    resp = negocio_client.get(
        f"/v1/establecimientos/{est['id']}/perfil-web",
        headers=_headers(otro_token),
    )
    assert resp.status_code == 403
