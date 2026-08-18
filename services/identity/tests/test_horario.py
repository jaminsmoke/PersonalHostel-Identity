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


def _crear_cuenta(negocio_client, nombre_mostrar: str) -> dict:
    email = _email("horario")
    reg = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": nombre_mostrar,
            "email": email,
            "password": "negocio-12345678",
            "tipo_establecimiento": "bar",
        },
    )
    assert reg.status_code == 201, reg.text
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _crear_establecimiento(negocio_client, headers: dict, nombre="Local") -> str:
    resp = negocio_client.post("/v1/establecimientos", headers=headers, json={"nombre": nombre})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


HORARIO_VALIDO = {
    "dias": [
        {"dia_semana": 0, "cerrado": False, "turnos": [{"abre": "10:00", "cierra": "16:00"}]},
        {"dia_semana": 1, "cerrado": False, "turnos": [{"abre": "10:00", "cierra": "16:00"}]},
        {"dia_semana": 2, "cerrado": False, "turnos": [{"abre": "10:00", "cierra": "16:00"}]},
        {"dia_semana": 3, "cerrado": False, "turnos": [{"abre": "10:00", "cierra": "16:00"}]},
        {"dia_semana": 4, "cerrado": False, "turnos": [{"abre": "10:00", "cierra": "16:00"}]},
        {"dia_semana": 5, "cerrado": False, "turnos": [{"abre": "10:00", "cierra": "16:00"}]},
        {"dia_semana": 6, "cerrado": True, "turnos": []},
    ]
}


def test_get_horario_vacio(db_ready, negocio_client):
    headers = _crear_cuenta(negocio_client, "Horario Vacío")
    est_id = _crear_establecimiento(negocio_client, headers)

    resp = negocio_client.get(f"/v1/establecimientos/{est_id}/horario", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["establecimiento_id"] == est_id
    assert body["dias"] == []
    assert body["updated_at"] is None


def test_patch_horario_valido_y_persistido(db_ready, negocio_client):
    headers = _crear_cuenta(negocio_client, "Horario Válido")
    est_id = _crear_establecimiento(negocio_client, headers)

    resp = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario", headers=headers, json=HORARIO_VALIDO
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["establecimiento_id"] == est_id
    assert body["dias"][0] == {
        "dia_semana": 0,
        "cerrado": False,
        "turnos": [{"abre": "10:00", "cierra": "16:00"}],
    }
    assert body["dias"][6]["cerrado"] is True
    assert body["updated_at"] is not None

    get = negocio_client.get(f"/v1/establecimientos/{est_id}/horario", headers=headers)
    assert get.status_code == 200
    assert get.json()["dias"] == body["dias"]


@pytest.mark.parametrize(
    ("payload", "motivo"),
    [
        (
            {"dias": [{"dia_semana": 0, "turnos": [{"abre": "16:00", "cierra": "10:00"}]}]},
            "turno que cierra antes de abrir",
        ),
        (
            {
                "dias": [
                    {
                        "dia_semana": 0,
                        "turnos": [
                            {"abre": "10:00", "cierra": "14:00"},
                            {"abre": "13:00", "cierra": "18:00"},
                        ],
                    }
                ]
            },
            "turnos solapados",
        ),
        (
            {
                "dias": [
                    {"dia_semana": 0, "turnos": [{"abre": "10:00", "cierra": "14:00"}]},
                    {"dia_semana": 0, "turnos": [{"abre": "18:00", "cierra": "23:00"}]},
                ]
            },
            "día repetido",
        ),
        (
            {
                "dias": [
                    {
                        "dia_semana": 0,
                        "cerrado": True,
                        "turnos": [{"abre": "10:00", "cierra": "14:00"}],
                    }
                ]
            },
            "día cerrado con turnos",
        ),
        (
            {"dias": [{"dia_semana": 0, "turnos": []}]},
            "día abierto sin turnos",
        ),
        (
            {"dias": [{"dia_semana": 7, "turnos": [{"abre": "10:00", "cierra": "14:00"}]}]},
            "día fuera de rango",
        ),
        (
            {"dias": [{"dia_semana": 0, "turnos": [{"abre": "25:00", "cierra": "14:00"}]}]},
            "hora con formato inválido",
        ),
    ],
)
def test_patch_rechaza_horarios_invalidos(db_ready, negocio_client, payload, motivo):
    headers = _crear_cuenta(negocio_client, "Horario Inválido")
    est_id = _crear_establecimiento(negocio_client, headers)

    resp = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario", headers=headers, json=payload
    )
    assert resp.status_code == 422, f"{motivo}: {resp.text}"
    assert resp.json()["code"] == "identity.validation_error"
    assert isinstance(resp.json()["detail"], list)


def test_horario_requiere_token(db_ready, negocio_client):
    est_id = str(uuid.uuid4())
    assert negocio_client.get(f"/v1/establecimientos/{est_id}/horario").status_code == 401
    assert (
        negocio_client.patch(
            f"/v1/establecimientos/{est_id}/horario", json=HORARIO_VALIDO
        ).status_code
        == 401
    )


def test_horario_otra_cuenta_403(db_ready, negocio_client):
    dueno = _crear_cuenta(negocio_client, "Dueño")
    est_id = _crear_establecimiento(negocio_client, dueno)
    intruso = _crear_cuenta(negocio_client, "Intruso")

    resp = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario", headers=intruso, json=HORARIO_VALIDO
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "identity.membresia_prohibida"


def test_horario_establecimiento_inexistente_404(db_ready, negocio_client):
    headers = _crear_cuenta(negocio_client, "Sin Establecimiento")
    resp = negocio_client.patch(
        f"/v1/establecimientos/{uuid.uuid4()}/horario", headers=headers, json=HORARIO_VALIDO
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.establecimiento_no_encontrado"


def test_patch_vacio_limpia_horario(db_ready, negocio_client):
    headers = _crear_cuenta(negocio_client, "Limpiar Horario")
    est_id = _crear_establecimiento(negocio_client, headers)

    primero = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario", headers=headers, json=HORARIO_VALIDO
    )
    assert primero.status_code == 200

    limpio = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario", headers=headers, json={"dias": []}
    )
    assert limpio.status_code == 200
    assert limpio.json()["dias"] == []

    get = negocio_client.get(f"/v1/establecimientos/{est_id}/horario", headers=headers)
    assert get.json()["dias"] == []


def test_patch_reemplaza_horario_anterior(db_ready, negocio_client):
    headers = _crear_cuenta(negocio_client, "Reemplazo")
    est_id = _crear_establecimiento(negocio_client, headers)

    primero = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario", headers=headers, json=HORARIO_VALIDO
    )
    assert primero.status_code == 200

    segundo = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario",
        headers=headers,
        json={"dias": [{"dia_semana": 2, "turnos": [{"abre": "09:00", "cierra": "13:00"}]}]},
    )
    assert segundo.status_code == 200
    dias = segundo.json()["dias"]
    assert len(dias) == 1
    assert dias[0]["dia_semana"] == 2
    assert dias[0]["turnos"] == [{"abre": "09:00", "cierra": "13:00"}]
