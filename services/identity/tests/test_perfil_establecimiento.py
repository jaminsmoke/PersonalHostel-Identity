import uuid
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import text

from app.db import NegocioSessionLocal
from app.models import Establecimiento
from app.storage import get_foto_storage


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _cuenta(negocio_client, nombre="Organización Norte", tipo="bar") -> tuple[str, str]:
    email = _email("perfil-negocio")
    registro = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": nombre,
            "email": email,
            "password": "negocio-12345678",
            "tipo_establecimiento": tipo,
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


def _establecimiento(negocio_client, token: str, nombre: str, tipo=None) -> dict:
    payload = {"nombre": nombre}
    if tipo is not None:
        payload["tipo_establecimiento"] = tipo
    response = negocio_client.post("/v1/establecimientos", headers=_headers(token), json=payload)
    assert response.status_code == 201
    return response.json()


def _png(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (80, 60), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_get_y_patch_cuenta_organizacion(db_ready, negocio_client):
    email, token = _cuenta(negocio_client)
    response = negocio_client.get("/v1/auth/negocio/me", headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["nombre_mostrar"] == "Organización Norte"

    updated = negocio_client.patch(
        "/v1/auth/negocio/me",
        headers=_headers(token),
        json={"nombre_mostrar": "Grupo Norte"},
    )
    assert updated.status_code == 200
    assert updated.json()["nombre_mostrar"] == "Grupo Norte"

    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.json()["cuenta"]["nombre_mostrar"] == "Grupo Norte"
    assert (
        negocio_client.patch("/v1/auth/negocio/me", headers=_headers(token), json={}).status_code
        == 422
    )


def test_establecimientos_tienen_perfiles_independientes(db_ready, negocio_client):
    _, token = _cuenta(negocio_client, tipo="bar")
    cafeteria = _establecimiento(negocio_client, token, "Café Centro", "cafeteria")
    pub = _establecimiento(negocio_client, token, "Pub Norte", "pub")
    heredado = _establecimiento(negocio_client, token, "Bar Heredado")

    assert cafeteria["tipo_establecimiento"] == "cafeteria"
    assert pub["tipo_establecimiento"] == "pub"
    assert heredado["tipo_establecimiento"] == "bar"

    updated = negocio_client.patch(
        f"/v1/establecimientos/{cafeteria['id']}",
        headers=_headers(token),
        json={"nombre": "Café Plaza", "tipo_establecimiento": "restaurante"},
    )
    assert updated.status_code == 200
    assert updated.json()["nombre"] == "Café Plaza"
    assert updated.json()["tipo_establecimiento"] == "restaurante"

    _, otro_token = _cuenta(negocio_client)
    forbidden = negocio_client.patch(
        f"/v1/establecimientos/{pub['id']}",
        headers=_headers(otro_token),
        json={"nombre": "No permitido"},
    )
    assert forbidden.status_code == 403


def test_logo_local_sobrescribe_y_al_borrar_hereda(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    headers = _headers(token)
    establecimiento = _establecimiento(negocio_client, token, "Local Logo", "bar")
    path = f"/v1/establecimientos/{establecimiento['id']}/logo"

    corporativo = negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("corporativo.png", _png((220, 20, 20)), "image/png")},
    )
    assert corporativo.status_code == 200
    heredado = negocio_client.get(path, headers=headers)
    assert heredado.status_code == 200

    propio = negocio_client.post(
        path,
        headers=headers,
        files={"logo": ("local.png", _png((20, 20, 220)), "image/png")},
    )
    assert propio.status_code == 200
    assert propio.json()["logo_url"] == path
    local = negocio_client.get(path, headers=headers)
    assert local.status_code == 200
    assert local.content != heredado.content

    with NegocioSessionLocal() as session:
        clave_local = session.get(Establecimiento, uuid.UUID(establecimiento["id"])).logo_clave
    assert clave_local and get_foto_storage().leer(clave_local) is not None

    borrado = negocio_client.delete(path, headers=headers)
    assert borrado.status_code == 200
    assert borrado.json()["logo_url"] == path
    assert get_foto_storage().leer(clave_local) is None
    assert negocio_client.get(path, headers=headers).content == heredado.content


def test_supresion_borra_logo_propio_del_establecimiento(db_ready, negocio_client):
    _, token = _cuenta(negocio_client)
    headers = _headers(token)
    establecimiento = _establecimiento(negocio_client, token, "Local Borrable", "pub")
    negocio_client.post(
        f"/v1/establecimientos/{establecimiento['id']}/logo",
        headers=headers,
        files={"logo": ("local.png", _png((10, 100, 40)), "image/png")},
    )
    with NegocioSessionLocal() as session:
        clave = session.get(Establecimiento, uuid.UUID(establecimiento["id"])).logo_clave
    assert clave and get_foto_storage().leer(clave) is not None

    deleted = negocio_client.request(
        "DELETE",
        "/v1/auth/negocio/me",
        headers=headers,
        json={"password": "negocio-12345678"},
    )
    assert deleted.status_code == 200
    assert get_foto_storage().leer(clave) is None
