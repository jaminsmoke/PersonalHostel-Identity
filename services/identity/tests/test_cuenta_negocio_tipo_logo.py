import uuid
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import text

from app.db import NegocioSessionLocal
from app.storage import get_foto_storage


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _crear_negocio(negocio_client, tipo: str | None = None) -> tuple[str, str, str]:
    email = _email("negtipo")
    payload = {
        "nombre_mostrar": "Negocio Tipo",
        "email": email,
        "password": "negocio-12345678",
    }
    if tipo is not None:
        payload["tipo_establecimiento"] = tipo
    response = negocio_client.post("/v1/auth/negocio/registro", json=payload)
    assert response.status_code == 201
    data = response.json()
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return data["id"], email, login.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _png_bytes(color=(200, 30, 30)) -> bytes:
    img = Image.new("RGB", (300, 200), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _reg_chip() -> bytes:
    img = Image.new("RGB", (64, 64), (10, 80, 200))
    buf = BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def test_registro_con_tipo_nulo_y_login_incluye_tipo(db_ready, negocio_client):
    _, email, token = _crear_negocio(negocio_client)
    login_resp = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login_resp.status_code == 200
    cuenta = login_resp.json()["cuenta"]
    assert cuenta["tipo_establecimiento"] is None
    assert cuenta["logo_url"] is None
    assert _auth(token)


def test_registro_tipo_valido_en_login(db_ready, negocio_client):
    _, email, _ = _crear_negocio(negocio_client, "restaurante")
    login_resp = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["cuenta"]["tipo_establecimiento"] == "restaurante"


def test_registro_tipo_invalido_422(db_ready, negocio_client):
    response = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Invalido",
            "email": _email("neg-inv"),
            "password": "negocio-12345678",
            "tipo_establecimiento": "discoteca",
        },
    )
    assert response.status_code == 422


def test_registro_todos_los_tipos_validos(db_ready, negocio_client):
    for tipo in ("bar", "restaurante", "cafeteria", "pub", "copas"):
        response = negocio_client.post(
            "/v1/auth/negocio/registro",
            json={
                "nombre_mostrar": f"Tipo {tipo}",
                "email": _email(f"neg-{tipo}"),
                "password": "negocio-12345678",
                "tipo_establecimiento": tipo,
            },
        )
        assert response.status_code == 201, tipo


def test_logo_ciclo_completo(db_ready, negocio_client):
    _, email, token = _crear_negocio(negocio_client)
    headers = _auth(token)

    resp = negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("logo.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["logo_url"] == "/v1/auth/negocio/me/logo"

    logo = negocio_client.get("/v1/auth/negocio/me/logo", headers=headers)
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/webp"
    assert logo.headers["etag"]
    img = Image.open(BytesIO(logo.content))
    assert img.format == "WEBP"
    assert img.size == (256, 256)

    login_resp = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["cuenta"]["logo_url"] == "/v1/auth/negocio/me/logo"


def test_logo_reemplazo_borra_anterior(db_ready, negocio_client):
    _, email, token = _crear_negocio(negocio_client)
    headers = _auth(token)

    negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("a.png", _png_bytes((255, 0, 0)), "image/png")},
    )
    with NegocioSessionLocal() as session:
        from app.models import CuentaNegocio

        cuenta = session.query(CuentaNegocio).filter_by(email=email).one()
        old_clave = cuenta.logo_clave
    assert old_clave is not None

    negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("b.webp", _reg_chip(), "image/webp")},
    )
    with NegocioSessionLocal() as session:
        from app.models import CuentaNegocio

        cuenta = session.query(CuentaNegocio).filter_by(email=email).one()
        assert cuenta.logo_clave != old_clave

    assert get_foto_storage().leer(old_clave) is None


def test_logo_borrar_y_404(db_ready, negocio_client):
    _, _, token = _crear_negocio(negocio_client)
    headers = _auth(token)

    negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("a.webp", _reg_chip(), "image/webp")},
    )
    resp = negocio_client.delete("/v1/auth/negocio/me/logo", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["logo_url"] is None

    assert negocio_client.get("/v1/auth/negocio/me/logo", headers=headers).status_code == 404


def test_logo_invalido_422(db_ready, negocio_client):
    _, _, token = _crear_negocio(negocio_client)
    headers = _auth(token)

    resp = negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("no-imagen.txt", b"esto no es una imagen", "text/plain")},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "identity.foto_invalida"


def test_logo_requiere_token_negocio(db_ready, negocio_client):
    resp = negocio_client.post(
        "/v1/auth/negocio/me/logo",
        files={"logo": ("a.webp", _reg_chip(), "image/webp")},
    )
    assert resp.status_code in (401, 403)
    assert negocio_client.get("/v1/auth/negocio/me/logo").status_code in (401, 403)


def test_supresion_borra_fichero_logo(db_ready, negocio_client):
    _, email, token = _crear_negocio(negocio_client)
    headers = _auth(token)
    negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("a.webp", _reg_chip(), "image/webp")},
    )
    with NegocioSessionLocal() as session:
        from app.models import CuentaNegocio

        clave = session.query(CuentaNegocio).filter_by(email=email).one().logo_clave
    assert get_foto_storage().leer(clave) is not None

    resp = negocio_client.request(
        "DELETE",
        "/v1/auth/negocio/me",
        headers=headers,
        json={"password": "negocio-12345678"},
    )
    assert resp.status_code == 200
    assert get_foto_storage().leer(clave) is None
