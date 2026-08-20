import os
import uuid
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import text

from app.db import NegocioSessionLocal
from app.fondos import CATALOGO, DEFAULTS, SECCIONES, url_catalogo


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _cuenta_y_local(negocio_client) -> tuple[dict, str]:
    email = _email("fondos")
    registro = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Org Fondos",
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
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    est = negocio_client.post(
        "/v1/establecimientos", headers=headers, json={"nombre": "Local Fondos"}
    )
    assert est.status_code == 201
    return headers, est.json()["id"]


def _enlace(negocio_client, headers, est_id: str) -> str:
    slug = f"fondos-{uuid.uuid4().hex[:8]}"
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "web", "slug": slug},
    )
    assert resp.status_code == 201
    return slug


def _slot(payload: dict, slot: str) -> dict:
    return {k: v for k, v in payload[slot].items() if v is not None}


def _png(color: tuple[int, int, int] = (40, 80, 120)) -> bytes:
    image = Image.new("RGB", (1200, 800), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_catalogo_fondos_tiene_dos_por_seccion(db_ready, negocio_client):
    headers, est_id = _cuenta_y_local(negocio_client)
    resp = negocio_client.get(
        f"/v1/establecimientos/{est_id}/fondos/catalogo",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {item["id"] for item in body} == {item.id for item in CATALOGO}
    assert len(body) == 10
    for item in body:
        assert item["url"] == url_catalogo(item["id"])
        assert item["url"].startswith(os.environ["WEB_NEGOCIO_URL_BASE"])


def test_fondos_default_y_put_catalogo_publico(db_ready, negocio_client):
    headers, est_id = _cuenta_y_local(negocio_client)
    slug = _enlace(negocio_client, headers, est_id)

    gestion = negocio_client.get(f"/v1/establecimientos/{est_id}/fondos", headers=headers)
    assert gestion.status_code == 200
    for slot in SECCIONES:
        assert gestion.json()[slot]["fuente"] == "catalogo"
        assert gestion.json()[slot]["id"] == DEFAULTS[slot]

    publico = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert publico.status_code == 200
    fondos = publico.json()["fondos"]
    assert set(fondos) == set(SECCIONES)
    assert _slot(fondos, "horario") == {
        "fuente": "catalogo",
        "id": "estate-horario-1",
        "url": url_catalogo("estate-horario-1"),
    }

    put = negocio_client.put(
        f"/v1/establecimientos/{est_id}/fondos",
        headers=headers,
        json={"horario": {"fuente": "catalogo", "id": "estate-horario-2"}},
    )
    assert put.status_code == 200
    assert put.json()["horario"]["id"] == "estate-horario-2"
    assert put.json()["carta"]["id"] == "estate-carta-1"

    fondos = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()["fondos"]
    assert fondos["horario"]["id"] == "estate-horario-2"
    assert fondos["horario"]["url"] == url_catalogo("estate-horario-2")


def test_put_catalogo_de_otra_seccion_422(db_ready, negocio_client):
    headers, est_id = _cuenta_y_local(negocio_client)
    resp = negocio_client.put(
        f"/v1/establecimientos/{est_id}/fondos",
        headers=headers,
        json={"carta": {"fuente": "catalogo", "id": "estate-horario-1"}},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "identity.fondo_invalido"


def test_hero_es_fallback_de_inicio_hasta_asignar_slot(db_ready, negocio_client):
    headers, est_id = _cuenta_y_local(negocio_client)
    slug = _enlace(negocio_client, headers, est_id)
    hero = negocio_client.post(
        f"/v1/establecimientos/{est_id}/hero",
        headers=headers,
        files={"hero": ("hero.png", _png((20, 40, 80)), "image/png")},
    )
    assert hero.status_code == 200

    fondos = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()["fondos"]
    assert _slot(fondos, "inicio") == {
        "fuente": "hero",
        "url": f"/v1/negocio/web/hero?slug={slug}",
    }

    put = negocio_client.put(
        f"/v1/establecimientos/{est_id}/fondos",
        headers=headers,
        json={"inicio": {"fuente": "catalogo", "id": "estate-inicio-2"}},
    )
    assert put.status_code == 200
    fondos = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()["fondos"]
    assert fondos["inicio"]["fuente"] == "catalogo"
    assert fondos["inicio"]["id"] == "estate-inicio-2"
    assert negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()["hero"] == {
        "url": f"/v1/negocio/web/hero?slug={slug}"
    }


def test_upload_no_sale_en_galeria_y_se_sirve_publico(db_ready, negocio_client):
    headers, est_id = _cuenta_y_local(negocio_client)
    slug = _enlace(negocio_client, headers, est_id)

    galeria = negocio_client.post(
        f"/v1/establecimientos/{est_id}/galeria",
        headers=headers,
        files={"imagen": ("g.png", _png((200, 100, 30)), "image/png")},
    )
    assert galeria.status_code == 200

    upload = negocio_client.post(
        f"/v1/establecimientos/{est_id}/fondos/carta",
        headers=headers,
        files={"imagen": ("fondo.png", _png((10, 80, 40)), "image/png")},
    )
    assert upload.status_code == 200
    assert upload.json()["carta"]["fuente"] == "upload"
    assert upload.json()["carta"]["url"] == f"/v1/establecimientos/{est_id}/fondos/carta"

    lista = negocio_client.get(f"/v1/establecimientos/{est_id}/galeria", headers=headers)
    assert lista.status_code == 200
    assert [img["id"] for img in lista.json()] == [galeria.json()["id"]]

    publico = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()
    assert publico["galeria"] == [
        {
            "id": galeria.json()["id"],
            "url": f"/v1/negocio/web/galeria/{galeria.json()['id']}?slug={slug}",
        }
    ]
    assert _slot(publico["fondos"], "carta") == {
        "fuente": "upload",
        "url": f"/v1/negocio/web/fondo/carta?slug={slug}",
    }

    img = negocio_client.get("/v1/negocio/web/fondo/carta", params={"slug": slug})
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/webp"
    assert Image.open(BytesIO(img.content)).format == "WEBP"

    privada = negocio_client.get(f"/v1/establecimientos/{est_id}/fondos/carta", headers=headers)
    assert privada.status_code == 200
    assert privada.headers["content-type"] == "image/webp"

    borrar = negocio_client.delete(f"/v1/establecimientos/{est_id}/fondos/carta", headers=headers)
    assert borrar.status_code == 200
    assert borrar.json()["carta"]["id"] == "estate-carta-1"
    ausente = negocio_client.get("/v1/negocio/web/fondo/carta", params={"slug": slug})
    assert ausente.status_code == 404


def test_put_null_limpia_upload(db_ready, negocio_client):
    headers, est_id = _cuenta_y_local(negocio_client)
    upload = negocio_client.post(
        f"/v1/establecimientos/{est_id}/fondos/equipo",
        headers=headers,
        files={"imagen": ("fondo.png", _png((90, 20, 20)), "image/png")},
    )
    assert upload.status_code == 200
    limpiar = negocio_client.put(
        f"/v1/establecimientos/{est_id}/fondos",
        headers=headers,
        json={"equipo": None},
    )
    assert limpiar.status_code == 200
    assert limpiar.json()["equipo"]["id"] == "estate-equipo-1"


def test_slot_desconocido_422(db_ready, negocio_client):
    headers, est_id = _cuenta_y_local(negocio_client)
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/fondos/galeria",
        headers=headers,
        files={"imagen": ("fondo.png", _png(), "image/png")},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "identity.fondo_invalido"
