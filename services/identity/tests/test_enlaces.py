import uuid

import pytest
from sqlalchemy import text

from app.db import NegocioSessionLocal


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _crear_negocio(negocio_client) -> tuple[str, str]:
    email = _email("enlace-negocio")
    resp = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Negocio Enlaces",
            "email": email,
            "password": "negocio-12345678",
        },
    )
    assert resp.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return resp.json()["id"], login.json()["token"]


def _crear_establecimiento(negocio_client, token: str, nombre: str = "Casa Enlaces") -> str:
    resp = negocio_client.post(
        "/v1/establecimientos",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": nombre},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_crear_enlace_con_slug_derivado(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token, "El Bar de Ana")

    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "carta"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "el-bar-de-ana-carta"
    assert body["tipo"] == "carta"
    assert body["estado"] == "activo"


def test_crear_enlace_con_slug_explicito(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)

    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "ficha_negocio", "slug": "mi-ficha"},
    )
    assert resp.status_code == 201
    assert resp.json()["slug"] == "mi-ficha"


def test_crear_enlace_slug_duplicado_409(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)

    first = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "carta", "slug": "duplicado"},
    )
    assert first.status_code == 201

    second = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "ficha_negocio", "slug": "duplicado"},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "identity.enlace_duplicado"


def test_crear_enlace_tipo_invalido_422(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)

    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "promo"},
    )
    assert resp.status_code == 422


def test_listar_enlaces(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)

    negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "ficha_negocio"},
    )
    negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "carta"},
    )
    resp = negocio_client.get(f"/v1/establecimientos/{est_id}/enlaces", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_resolver_enlace_publico_sin_token(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)

    created = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "carta", "slug": "publica"},
    ).json()

    resp = negocio_client.get(f"/v1/enlaces/{created['slug']}")
    assert resp.status_code == 200
    assert resp.json() == {"tipo": "carta", "establecimiento_id": est_id}
    assert resp.headers["cache-control"] == "public, max-age=300"


def test_resolver_enlace_revocado_410(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)

    created = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "carta", "slug": "revocable"},
    ).json()

    revoke = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces/{created['id']}/revocar",
        headers=headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["estado"] == "revocado"

    resp = negocio_client.get(f"/v1/enlaces/{created['slug']}")
    assert resp.status_code == 410
    assert resp.json()["code"] == "identity.enlace_revocado"


def test_resolver_enlace_inexistente_404(db_ready, negocio_client):
    resp = negocio_client.get("/v1/enlaces/no-existe")
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.enlace_no_encontrado"


def test_crear_enlace_requiere_cuenta_titular(db_ready, negocio_client):
    _, token_a = _crear_negocio(negocio_client)
    _, token_b = _crear_negocio(negocio_client)
    est_id = _crear_establecimiento(negocio_client, token_a)

    # Otra cuenta no puede crear enlaces en el establecimiento de A.
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"tipo": "carta"},
    )
    assert resp.status_code == 403

    # Sin token, la gestión exige sesión (la resolución pública sí es libre).
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        json={"tipo": "carta"},
    )
    assert resp.status_code == 401


def test_crear_enlace_es_idempotente_y_devuelve_url_publica(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token, "Idempotente")

    first = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "ficha_negocio"},
    )
    second = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "ficha_negocio"},
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["url_publica"] == (
        f"http://web.test/negocio?slug={first.json()['slug']}"
    )

    conflict = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "ficha_negocio", "slug": f"otro-{uuid.uuid4().hex[:8]}"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "identity.enlace_activo_existente"


def test_rotar_enlace_revoca_anterior_y_crea_sustituto(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token, "Rotación")
    original = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "carta"},
    ).json()

    rotated = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces/{original['id']}/rotar",
        headers=headers,
        json={},
    )
    assert rotated.status_code == 201
    assert rotated.json()["id"] != original["id"]
    assert rotated.json()["slug"] != original["slug"]
    assert rotated.json()["url_publica"].startswith("http://web.test/carta?slug=")
    assert negocio_client.get(f"/v1/enlaces/{original['slug']}").status_code == 410
    assert negocio_client.get(f"/v1/enlaces/{rotated.json()['slug']}").status_code == 200

    enlaces = negocio_client.get(
        f"/v1/establecimientos/{est_id}/enlaces", headers=headers
    ).json()
    assert sum(link["estado"] == "activo" for link in enlaces) == 1
