import uuid

import pytest
from sqlalchemy import text

from app.db import CamareroSessionLocal, NegocioSessionLocal
from app.models import EmailOutbox, Invitacion


@pytest.fixture(scope="module")
def db_ready():
    with CamareroSessionLocal() as session:
        session.execute(text("SELECT 1"))
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _camarero(camarero_client, prefix: str = "dir-cam") -> tuple[str, str, str]:
    email = _email(prefix)
    registered = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Directorio",
            "apellidos": "Camarero",
            "email": email,
            "password": "pass-12345678",
            "nick": prefix,
        },
    )
    assert registered.status_code == 201
    login = camarero_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    return registered.json()["id"], email, login.json()["token"]


def _negocio(negocio_client, prefix: str = "dir-biz", camarero_vinculado_id=None) -> str:
    email = _email(prefix)
    body = {
        "nombre_mostrar": "Bar Directorio",
        "email": email,
        "password": "negocio-12345678",
    }
    if camarero_vinculado_id:
        body["camarero_vinculado_id"] = camarero_vinculado_id
    registered = negocio_client.post("/v1/auth/negocio/registro", json=body)
    assert registered.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return login.json()["token"]


def _establecimiento(negocio_client, token: str, nombre: str = "Bar Directorio") -> str:
    response = negocio_client.post(
        "/v1/establecimientos",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": nombre},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _set_visible(camarero_client, token: str, visible: str) -> dict:
    resp = camarero_client.put(
        "/v1/camareros/me/visibilidad-establecimientos",
        headers={"Authorization": f"Bearer {token}"},
        json={"visible": visible},
    )
    assert resp.status_code == 200
    return resp.json()


def _directorio(negocio_client, establecimiento_id: str, token: str, **params) -> list[dict]:
    resp = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/camareros/directorio",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    assert resp.status_code == 200
    return resp.json()


def test_visibilidad_establecimientos_endpoint(db_ready, camarero_client):
    _, _, token = _camarero(camarero_client)
    headers = {"Authorization": f"Bearer {token}"}
    perfil = camarero_client.get("/v1/camareros/me", headers=headers)
    assert perfil.status_code == 200
    assert perfil.json()["visible_otros_establecimientos"] == "nunca"

    body = _set_visible(camarero_client, token, "solo_libre")
    assert body["visible_otros_establecimientos"] == "solo_libre"

    sin_token = camarero_client.put(
        "/v1/camareros/me/visibilidad-establecimientos",
        json={"visible": "nunca"},
    )
    assert sin_token.status_code == 401

    invalido = camarero_client.put(
        "/v1/camareros/me/visibilidad-establecimientos",
        headers=headers,
        json={"visible": "a_veces"},
    )
    assert invalido.status_code == 422


def test_directorio_default_nunca_no_aparece(db_ready, camarero_client, negocio_client):
    camarero_id, _, _ = _camarero(camarero_client)
    token = _negocio(negocio_client)
    est = _establecimiento(negocio_client, token)
    items = _directorio(negocio_client, est, token)
    assert all(item["id"] != camarero_id for item in items)


def test_directorio_siempre_aparece_y_sin_email(db_ready, camarero_client, negocio_client):
    camarero_id, _, camarero_token = _camarero(camarero_client)
    _set_visible(camarero_client, camarero_token, "siempre")
    token = _negocio(negocio_client)
    est = _establecimiento(negocio_client, token)
    items = _directorio(negocio_client, est, token)
    entry = next(item for item in items if item["id"] == camarero_id)
    assert entry["nombre"] == "Directorio"
    assert "email" not in entry
    assert entry["libre"] is True
    assert entry["visibilidad"] == "siempre"


def test_directorio_solo_libre_filtra_ocupados(db_ready, camarero_client, negocio_client):
    libre_id, _, libre_token = _camarero(camarero_client, "dir-libre")
    ocupado_id, _, ocupado_token = _camarero(camarero_client, "dir-ocupado")
    _set_visible(camarero_client, libre_token, "solo_libre")
    _set_visible(camarero_client, ocupado_token, "solo_libre")

    token_a = _negocio(negocio_client, "dir-biz-a")
    est_a = _establecimiento(negocio_client, token_a, "Bar A")

    # Ocupamos al camarero en otro establecimiento (B)
    token_b = _negocio(negocio_client, "dir-biz-b")
    est_b = _establecimiento(negocio_client, token_b, "Bar B")
    added = negocio_client.post(
        f"/v1/establecimientos/{est_b}/miembros",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"camarero_id": ocupado_id, "rol": "staff"},
    )
    assert added.status_code == 201

    ids = {item["id"] for item in _directorio(negocio_client, est_a, token_a)}
    assert libre_id in ids
    assert ocupado_id not in ids


def test_directorio_dueno_nunca_aparece(db_ready, camarero_client, negocio_client):
    dueno_id, _, dueno_token = _camarero(camarero_client, "dir-dueno")
    _set_visible(camarero_client, dueno_token, "siempre")
    token = _negocio(negocio_client, "dir-biz-dueno", camarero_vinculado_id=dueno_id)
    est = _establecimiento(negocio_client, token)
    items = _directorio(negocio_client, est, token)
    assert all(item["id"] != dueno_id for item in items)


def test_directorio_excluye_miembros_propios(db_ready, camarero_client, negocio_client):
    miembro_id, _, miembro_token = _camarero(camarero_client, "dir-miembro")
    _set_visible(camarero_client, miembro_token, "siempre")
    token = _negocio(negocio_client)
    est = _establecimiento(negocio_client, token)
    added = negocio_client.post(
        f"/v1/establecimientos/{est}/miembros",
        headers={"Authorization": f"Bearer {token}"},
        json={"camarero_id": miembro_id, "rol": "staff"},
    )
    assert added.status_code == 201
    items = _directorio(negocio_client, est, token)
    assert all(item["id"] != miembro_id for item in items)


def test_directorio_q_filtra(db_ready, camarero_client, negocio_client):
    _, _, token1 = _camarero(camarero_client, "dir-ana")
    _set_visible(camarero_client, token1, "siempre")
    _, _, token2 = _camarero(camarero_client, "dir-beto")
    _set_visible(camarero_client, token2, "siempre")
    token = _negocio(negocio_client)
    est = _establecimiento(negocio_client, token)
    items = _directorio(negocio_client, est, token, q="dir-ana")
    assert items
    assert all("dir-ana" in item["nick"] for item in items)


def test_directorio_requiere_auth(db_ready, camarero_client, negocio_client):
    token = _negocio(negocio_client)
    est = _establecimiento(negocio_client, token)
    resp = negocio_client.get(f"/v1/establecimientos/{est}/camareros/directorio")
    assert resp.status_code == 401


def test_invitacion_por_id(db_ready, camarero_client, negocio_client):
    camarero_id, email, camarero_token = _camarero(camarero_client, "dir-inv")
    _set_visible(camarero_client, camarero_token, "siempre")
    token = _negocio(negocio_client)
    est = _establecimiento(negocio_client, token)
    invitation = negocio_client.post(
        f"/v1/establecimientos/{est}/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
        json={"camarero_id": camarero_id, "rol": "staff"},
    )
    assert invitation.status_code == 201
    with NegocioSessionLocal() as session:
        row = session.get(Invitacion, uuid.UUID(invitation.json()["id"]))
        assert row.email_objetivo == email
        outbox = session.query(EmailOutbox).filter_by(invitacion_id=row.id).one()
        assert outbox.destinatario == email


def test_invitacion_requiere_email_o_id(db_ready, camarero_client, negocio_client):
    token = _negocio(negocio_client)
    est = _establecimiento(negocio_client, token)
    resp = negocio_client.post(
        f"/v1/establecimientos/{est}/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
        json={"rol": "staff"},
    )
    assert resp.status_code == 422


def test_foto_publica_por_id_y_foto_url_directorio(db_ready, camarero_client, negocio_client):
    from io import BytesIO

    from PIL import Image

    camarero_id, _, token = _camarero(camarero_client, "dir-foto")
    headers = {"Authorization": f"Bearer {token}"}
    img = Image.new("RGB", (300, 200), (20, 120, 240))
    buf = BytesIO()
    img.save(buf, format="PNG")
    subida = camarero_client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("foto.png", buf.getvalue(), "image/png")},
    )
    assert subida.status_code == 200
    vis = camarero_client.put("/v1/camareros/me/visibilidad", headers=headers, json={"foto": True})
    assert vis.status_code == 200
    _set_visible(camarero_client, token, "siempre")

    foto = camarero_client.get(f"/v1/camareros/ficha/foto/{camarero_id}")
    assert foto.status_code == 200
    assert foto.headers["content-type"] == "image/webp"

    # Sin opt-in de foto → 404 aunque el camarero exista.
    camarero_id2, _, _ = _camarero(camarero_client, "dir-foto2")
    assert camarero_client.get(f"/v1/camareros/ficha/foto/{camarero_id2}").status_code == 404

    # El directorio expone foto_url solo cuando la foto es pública.
    biz = _negocio(negocio_client, "dir-biz-foto")
    est = _establecimiento(negocio_client, biz)
    entry = next(
        item for item in _directorio(negocio_client, est, biz) if item["id"] == camarero_id
    )
    assert entry["foto_url"] == f"/v1/camareros/ficha/foto/{camarero_id}"
