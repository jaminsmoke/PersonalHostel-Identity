import uuid
from datetime import UTC, datetime

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


def _crear_negocio_establecimiento(negocio_client, nombre="Local Web") -> tuple[dict, str]:
    email = _email("web-negocio")
    reg = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Negocio Web",
            "email": email,
            "password": "negocio-12345678",
            "tipo_establecimiento": "restaurante",
        },
    )
    assert reg.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login", json={"email": email, "password": "negocio-12345678"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    est = negocio_client.post("/v1/establecimientos", headers=headers, json={"nombre": nombre})
    assert est.status_code == 201
    return headers, est.json()["id"]


def _crear_enlace(negocio_client, headers, est_id, tipo, slug) -> dict:
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": tipo, "slug": slug},
    )
    assert resp.status_code == 201
    return resp.json()


def _crear_producto(
    negocio_client, est_id, headers, nombre, categoria, precio, destino="barra", descripcion=None
):
    payload = {
        "nombre": nombre,
        "categoria": categoria,
        "destino": destino,
        "precio_centimos": precio,
        "moneda": "EUR",
        "disponible": True,
    }
    if descripcion is not None:
        payload["descripcion"] = descripcion
    body = {
        "operation_id": str(uuid.uuid4()),
        "device_id": "web-test-01",
        "aggregate_type": "producto",
        "aggregate_id": str(uuid.uuid4()),
        "action": "crear",
        "base_revision": 0,
        "base_snapshot": None,
        "client_created_at": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/sync/operaciones",
        headers=headers,
        json=body,
    )
    assert resp.status_code == 200, resp.text


def test_web_negocio_resuelve_slug_de_ficha_y_devuelve_ficha_mas_carta(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-ficha-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)
    _crear_producto(negocio_client, est_id, headers, "Café solo", "Cafés", 150)
    _crear_producto(negocio_client, est_id, headers, "Tortilla", "Cocina", 450)

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 200
    body = resp.json()
    assert body["establecimiento_id"] == est_id
    assert body["nombre"] == "Local Web"
    assert body["tipo_establecimiento"] == "restaurante"
    assert body["logo_url"] is None
    assert body["organizacion_nombre"] == "Negocio Web"
    assert body["categorias"] == [
        {
            "nombre": "Cafés",
            "productos": [
                {
                    "nombre": "Café solo",
                    "precio_centimos": 150,
                    "moneda": "EUR",
                    "destino": "barra",
                }
            ],
        },
        {
            "nombre": "Cocina",
            "productos": [
                {
                    "nombre": "Tortilla",
                    "precio_centimos": 450,
                    "moneda": "EUR",
                    "destino": "barra",
                }
            ],
        },
    ]
    assert "email" not in body
    assert body["horario"] is None
    assert resp.headers["cache-control"] == "public, max-age=300"


def test_web_negocio_incluye_horario_configurado(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-horario-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)

    patch = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario",
        headers=headers,
        json={
            "dias": [
                {"dia_semana": 0, "turnos": [{"abre": "10:00", "cierra": "16:00"}]},
                {"dia_semana": 6, "cerrado": True, "turnos": []},
            ]
        },
    )
    assert patch.status_code == 200, patch.text

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 200
    assert resp.json()["horario"] == [
        {
            "dia_semana": 0,
            "cerrado": False,
            "turnos": [{"abre": "10:00", "cierra": "16:00"}],
        },
        {"dia_semana": 6, "cerrado": True, "turnos": []},
    ]


def test_web_negocio_resuelve_tambien_slug_de_carta(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-carta-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "carta", slug)

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 200
    assert resp.json()["establecimiento_id"] == est_id
    assert resp.json()["categorias"] == []


def test_web_negocio_logo_url_y_servido_por_cualquier_slug(db_ready, negocio_client):
    from io import BytesIO

    from PIL import Image

    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug_ficha = f"web-logo-f-{uuid.uuid4().hex[:8]}"
    slug_carta = f"web-logo-c-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug_ficha)
    _crear_enlace(negocio_client, headers, est_id, "carta", slug_carta)

    img = Image.new("RGB", (300, 200), (200, 80, 40))
    buf = BytesIO()
    img.save(buf, format="PNG")
    upload = negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("logo.png", buf.getvalue(), "image/png")},
    )
    assert upload.status_code == 200

    body = negocio_client.get("/v1/negocio/web", params={"slug": slug_ficha}).json()
    assert body["logo_url"] == f"/v1/negocio/web/logo?slug={slug_ficha}"

    for slug in (slug_ficha, slug_carta):
        logo = negocio_client.get("/v1/negocio/web/logo", params={"slug": slug})
        assert logo.status_code == 200
        assert logo.headers["content-type"] == "image/webp"
        assert logo.headers["cache-control"] == "public, max-age=86400"
        assert Image.open(BytesIO(logo.content)).format == "WEBP"


def test_web_negocio_slug_inexistente_404(db_ready, negocio_client):
    resp = negocio_client.get("/v1/negocio/web", params={"slug": "no-existe"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.enlace_no_encontrado"


def test_web_negocio_revocada_410(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-revocada-{uuid.uuid4().hex[:8]}"
    enlace = _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)

    revoke = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces/{enlace['id']}/revocar",
        headers=headers,
    )
    assert revoke.status_code == 200

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 410
    assert resp.json()["code"] == "identity.enlace_revocado"


def test_web_negocio_incluye_perfil_contacto_y_rebranding(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-perfil-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)

    patch = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/perfil-web",
        headers=headers,
        json={
            "eslogan": "Cocina de mercado",
            "descripcion": "Restaurante de barrio.",
            "direccion": "Calle Mayor 3",
            "ciudad": "Madrid",
            "telefono": "+34910000000",
            "email_contacto": "cocina@local.example",
            "web": "https://local.example",
            "redes": {"tiktok": "https://tiktok.com/@local"},
            "color_primario": "#2A6B4F",
        },
    )
    assert patch.status_code == 200, patch.text

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plantilla"] == "estate_hospitality"
    assert body["color_primario"] == "#2A6B4F"
    assert body["perfil"] == {
        "eslogan": "Cocina de mercado",
        "descripcion": "Restaurante de barrio.",
        "direccion": "Calle Mayor 3",
        "ciudad": "Madrid",
    }
    assert body["contacto"] == {
        "telefono": "+34910000000",
        "email_contacto": "cocina@local.example",
        "web": "https://local.example",
        "redes": {"tiktok": "https://tiktok.com/@local"},
    }
    assert "email" not in body
    assert body["equipo"] == []


def test_web_negocio_hero_y_galeria_publicos(db_ready, negocio_client):
    from io import BytesIO

    from PIL import Image

    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-imagenes-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)

    def png(color, size=(1200, 800)):
        image = Image.new("RGB", size, color)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    hero = negocio_client.post(
        f"/v1/establecimientos/{est_id}/hero",
        headers=headers,
        files={"hero": ("hero.png", png((30, 100, 200)), "image/png")},
    )
    assert hero.status_code == 200
    galeria = negocio_client.post(
        f"/v1/establecimientos/{est_id}/galeria",
        headers=headers,
        files={"imagen": ("g1.png", png((200, 100, 30)), "image/png")},
    )
    assert galeria.status_code == 200

    body = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()
    assert body["hero"] == {"url": f"/v1/negocio/web/hero?slug={slug}"}
    assert body["galeria"] == [
        {
            "id": galeria.json()["id"],
            "url": f"/v1/negocio/web/galeria/{galeria.json()['id']}?slug={slug}",
        }
    ]

    hero_img = negocio_client.get("/v1/negocio/web/hero", params={"slug": slug})
    assert hero_img.status_code == 200
    assert hero_img.headers["content-type"] == "image/webp"
    assert Image.open(BytesIO(hero_img.content)).format == "WEBP"

    galeria_img = negocio_client.get(
        "/v1/negocio/web/galeria/" + galeria.json()["id"], params={"slug": slug}
    )
    assert galeria_img.status_code == 200
    assert galeria_img.headers["content-type"] == "image/webp"


def test_web_negocio_privada_410_no_store_y_logo_sigue_publico(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-privada-{uuid.uuid4().hex[:8]}"
    slug_carta = f"web-privada-carta-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)
    _crear_enlace(negocio_client, headers, est_id, "carta", slug_carta)

    off = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/perfil-web",
        headers=headers,
        json={"web_publica": False},
    )
    assert off.status_code == 200

    web = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert web.status_code == 410
    assert web.json()["code"] == "identity.web_privada"
    assert web.headers["cache-control"] == "no-store"

    web_carta = negocio_client.get("/v1/negocio/web", params={"slug": slug_carta})
    assert web_carta.status_code == 410
    assert web_carta.json()["code"] == "identity.web_privada"
    assert web_carta.headers["cache-control"] == "no-store"

    hero = negocio_client.get("/v1/negocio/web/hero", params={"slug": slug})
    assert hero.status_code == 410
    assert hero.headers["cache-control"] == "no-store"

    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (100, 100), (90, 160, 220))
    buf = BytesIO()
    img.save(buf, format="PNG")
    negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("logo.png", buf.getvalue(), "image/png")},
    )

    logo = negocio_client.get("/v1/negocio/web/logo", params={"slug": slug})
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/webp"


def test_web_negocio_abierto_ahora_con_horario(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-abierto-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)

    patch = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario",
        headers=headers,
        json={
            "dias": [
                {"dia_semana": 0, "turnos": [{"abre": "00:00", "cierra": "23:59"}]},
                {"dia_semana": 1, "turnos": [{"abre": "00:00", "cierra": "23:59"}]},
                {"dia_semana": 2, "turnos": [{"abre": "00:00", "cierra": "23:59"}]},
                {"dia_semana": 3, "turnos": [{"abre": "00:00", "cierra": "23:59"}]},
                {"dia_semana": 4, "turnos": [{"abre": "00:00", "cierra": "23:59"}]},
                {"dia_semana": 5, "turnos": [{"abre": "00:00", "cierra": "23:59"}]},
                {"dia_semana": 6, "turnos": [{"abre": "00:00", "cierra": "23:59"}]},
            ]
        },
    )
    assert patch.status_code == 200, patch.text

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 200
    abierto = resp.json()["abierto_ahora"]
    assert abierto["abierto"] is True
    assert abierto["proximo_cambio"] is not None


def test_web_negocio_equipo_matriz_and(db_ready, camarero_client, negocio_client):
    from app.models import Membresia, MembresiaEstado, MembresiaRol

    email = _email("equipo")
    camarero = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Luis",
            "apellidos": "Pérez",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert camarero.status_code == 201
    camarero_id = camarero.json()["id"]
    login = camarero_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200

    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-equipo-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)

    with NegocioSessionLocal() as session:
        session.add(
            Membresia(
                establecimiento_id=uuid.UUID(est_id),
                camarero_id=uuid.UUID(camarero_id),
                rol=MembresiaRol.staff,
                estado=MembresiaEstado.activa,
            )
        )
        session.commit()

    patch = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/perfil-web",
        headers=headers,
        json={"mostrar_equipo": True},
    )
    assert patch.status_code == 200

    # El camarero no ha hecho opt-in: no aparece.
    body = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()
    assert body["equipo"] == []

    # Opt-in del camarero → aparece (matriz AND completa).
    opt_in = camarero_client.put(
        "/v1/camareros/me/pagina-publica",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
        json={"aparecer_web_negocio": True},
    )
    assert opt_in.status_code == 200

    body = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()
    assert body["equipo"] == [
        {
            "camarero_id": camarero_id,
            "nombre": "Luis",
            "apellidos": "Pérez",
            "nick": None,
            "foto_url": None,
            "rol": "staff",
        }
    ]

    # Si el local apaga mostrar_equipo, desaparece aunque el camarero haya optado.
    off = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/perfil-web",
        headers=headers,
        json={"mostrar_equipo": False},
    )
    assert off.status_code == 200
    body = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()
    assert body["equipo"] == []


def test_web_negocio_expone_destino_y_descripcion(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-carta-destino-{uuid.uuid4().hex[:8]}"
    created = _crear_enlace(negocio_client, headers, est_id, "web", slug)
    assert created["tipo"] == "web"
    _crear_producto(
        negocio_client,
        est_id,
        headers,
        "Negroni",
        "Cócteles",
        900,
        destino="barra",
        descripcion="Gin, vermut y Campari",
    )
    _crear_producto(negocio_client, est_id, headers, "Bravas", "Entrantes", 700, destino="cocina")

    body = negocio_client.get("/v1/negocio/web", params={"slug": slug}).json()
    por_nombre = {p["nombre"]: p for c in body["categorias"] for p in c["productos"]}
    assert por_nombre["Negroni"]["destino"] == "barra"
    assert por_nombre["Negroni"]["descripcion"] == "Gin, vermut y Campari"
    assert por_nombre["Bravas"]["destino"] == "cocina"
    assert "descripcion" not in por_nombre["Bravas"]
