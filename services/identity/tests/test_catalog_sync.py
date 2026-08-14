import uuid
from datetime import datetime, timezone


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _create_business_and_establishment(negocio_client) -> tuple[dict, str]:
    email = _email("catalogo-negocio")
    password = "negocio-12345678"
    registration = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={"nombre_mostrar": "Negocio Catálogo", "email": email, "password": password},
    )
    assert registration.status_code == 201, registration.text
    login = negocio_client.post(
        "/v1/auth/negocio/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    created = negocio_client.post(
        "/v1/establecimientos", headers=headers, json={"nombre": "Bar Sync"}
    )
    assert created.status_code == 201, created.text
    return headers, created.json()["id"]


def _operation(
    product_id: str,
    *,
    operation_id: str | None = None,
    action: str = "crear",
    base_revision: int = 0,
    name: str = "Café solo",
    device_id: str = "bar-tablet-01",
) -> dict:
    body = {
        "operation_id": operation_id or str(uuid.uuid4()),
        "device_id": device_id,
        "aggregate_type": "producto",
        "aggregate_id": product_id,
        "action": action,
        "base_revision": base_revision,
        "base_snapshot": None,
        "client_created_at": datetime.now(timezone.utc).isoformat(),
    }
    if action != "archivar":
        body["payload"] = {
            "nombre": name,
            "categoria": "Cafés",
            "destino": "barra",
            "precio_centimos": 150,
            "moneda": "EUR",
            "disponible": True,
        }
    return body


def _post_operation(negocio_client, establishment_id: str, headers: dict, body: dict):
    return negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/operaciones",
        headers=headers,
        json=body,
    )


def test_catalogo_aplica_operaciones_idempotentes_y_expone_deltas(negocio_client):
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    create = _operation(product_id)

    first = _post_operation(negocio_client, establishment_id, headers, create)
    assert first.status_code == 200, first.text
    assert first.json()["estado"] == "aplicada"
    assert first.json()["global_revision"] == 1
    assert first.json()["result_snapshot"]["revision"] == 1

    repeated = _post_operation(negocio_client, establishment_id, headers, create)
    assert repeated.status_code == 200
    assert repeated.json() == first.json()

    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    )
    assert catalog.status_code == 200
    assert catalog.json()["revision"] == 1
    assert [p["id"] for p in catalog.json()["productos"]] == [product_id]
    assert catalog.json()["productos"][0]["precio_centimos"] == 150

    changes = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/sync/cambios?desde=0",
        headers=headers,
    )
    assert changes.status_code == 200
    assert changes.json()["revision_actual"] == 1
    assert [change["revision"] for change in changes.json()["cambios"]] == [1]

    changed_intention = {**create, "payload": {**create["payload"], "nombre": "Otro"}}
    collision = _post_operation(
        negocio_client, establishment_id, headers, changed_intention
    )
    assert collision.status_code == 409
    assert collision.json()["code"] == "identity.operation_id_en_uso"


def test_actualizar_y_archivar_generan_revisiones_y_tombstone(negocio_client):
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    assert _post_operation(
        negocio_client, establishment_id, headers, _operation(product_id)
    ).status_code == 200

    update = _operation(
        product_id, action="actualizar", base_revision=1, name="Café doble"
    )
    updated = _post_operation(negocio_client, establishment_id, headers, update)
    assert updated.status_code == 200
    assert updated.json()["global_revision"] == 2
    assert updated.json()["result_snapshot"]["revision"] == 2
    assert updated.json()["result_snapshot"]["nombre"] == "Café doble"

    archive = _operation(product_id, action="archivar", base_revision=2)
    archived = _post_operation(negocio_client, establishment_id, headers, archive)
    assert archived.status_code == 200
    assert archived.json()["global_revision"] == 3
    assert archived.json()["result_snapshot"]["archived_at"] is not None

    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    )
    assert catalog.json()["revision"] == 3
    assert catalog.json()["productos"] == []
    changes = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/sync/cambios?desde=1",
        headers=headers,
    )
    assert [change["action"] for change in changes.json()["cambios"]] == [
        "actualizar",
        "archivar",
    ]


def test_conflicto_crea_aviso_y_puede_aceptarse(negocio_client):
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    assert _post_operation(
        negocio_client, establishment_id, headers, _operation(product_id)
    ).status_code == 200

    stale = _operation(
        product_id, action="actualizar", base_revision=0, name="Café offline"
    )
    conflicted = _post_operation(negocio_client, establishment_id, headers, stale)
    assert conflicted.status_code == 200
    conflict_id = conflicted.json()["conflict_id"]
    assert conflicted.json()["estado"] == "conflicto"
    assert conflicted.json()["global_revision"] is None

    conflicts = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos", headers=headers
    )
    assert conflicts.status_code == 200
    assert conflicts.json()[0]["canonical_revision"] == 1
    assert conflicts.json()[0]["canonical_snapshot"]["nombre"] == "Café solo"
    assert conflicts.json()[0]["proposed_snapshot"]["nombre"] == "Café offline"

    notifications = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/notificaciones?solo_no_leidas=true",
        headers=headers,
    )
    assert notifications.status_code == 200
    assert len(notifications.json()) == 1
    notification_id = notifications.json()[0]["id"]
    assert notifications.json()[0]["conflicto_id"] == conflict_id
    assert "deep_link" in notifications.json()[0]["payload"]

    read = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/notificaciones/{notification_id}/leer",
        headers=headers,
    )
    assert read.status_code == 200
    assert read.json()["read_at"] is not None

    accepted = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos/{conflict_id}/resolver",
        headers=headers,
        json={"decision": "aceptar", "expected_revision": 1},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["estado"] == "aceptado"

    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    ).json()
    assert catalog["revision"] == 2
    assert catalog["productos"][0]["nombre"] == "Café offline"
    assert catalog["productos"][0]["revision"] == 2


def test_conflicto_se_rechaza_y_resolucion_obsoleta_no_pisa(negocio_client):
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    assert _post_operation(
        negocio_client, establishment_id, headers, _operation(product_id)
    ).status_code == 200

    stale = _post_operation(
        negocio_client,
        establishment_id,
        headers,
        _operation(product_id, action="actualizar", base_revision=0, name="Offline A"),
    ).json()
    fresh = _post_operation(
        negocio_client,
        establishment_id,
        headers,
        _operation(product_id, action="actualizar", base_revision=1, name="Online B"),
    )
    assert fresh.status_code == 200

    obsolete = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos/{stale['conflict_id']}/resolver",
        headers=headers,
        json={"decision": "aceptar", "expected_revision": 1},
    )
    assert obsolete.status_code == 409
    assert obsolete.json()["code"] == "identity.resolucion_sync_obsoleta"

    rejectable = _post_operation(
        negocio_client,
        establishment_id,
        headers,
        _operation(product_id, action="actualizar", base_revision=0, name="Offline C"),
    ).json()
    rejected = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos/{rejectable['conflict_id']}/resolver",
        headers=headers,
        json={"decision": "rechazar", "expected_revision": 2},
    )
    assert rejected.status_code == 200
    assert rejected.json()["estado"] == "rechazado"
    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    ).json()
    assert catalog["revision"] == 2
    assert catalog["productos"][0]["nombre"] == "Online B"


def test_miembro_activo_lee_pero_no_escribe_y_hay_aislamiento(camarero_client, negocio_client):
    owner_headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    assert _post_operation(
        negocio_client, establishment_id, owner_headers, _operation(product_id)
    ).status_code == 200

    email = _email("catalogo-miembro")
    password = "camarero-12345678"
    registration = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "Miembro",
            "email": email,
            "password": password,
        },
    )
    assert registration.status_code == 201
    add = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/miembros",
        headers=owner_headers,
        json={"camarero_id": registration.json()["id"], "rol": "staff"},
    )
    assert add.status_code == 201, add.text
    login = camarero_client.post(
        "/v1/auth/login", json={"email": email, "password": password}
    )
    member_headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=member_headers
    ).status_code == 200
    assert negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/sync/cambios", headers=member_headers
    ).status_code == 200
    member_write = _post_operation(
        negocio_client,
        establishment_id,
        member_headers,
        _operation(product_id, action="actualizar", base_revision=1),
    )
    assert member_write.status_code == 401

    other_headers, _ = _create_business_and_establishment(negocio_client)
    assert negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=other_headers
    ).status_code == 403
    assert _post_operation(
        negocio_client,
        establishment_id,
        other_headers,
        _operation(product_id, action="actualizar", base_revision=1),
    ).status_code == 403


def test_operacion_valida_tipo_tamano_y_timestamp(negocio_client):
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    unsupported = _operation(product_id)
    unsupported["aggregate_type"] = "sala"
    response = _post_operation(negocio_client, establishment_id, headers, unsupported)
    assert response.status_code == 422
    assert response.json()["code"] == "identity.operacion_sync_no_soportada"

    naive_time = _operation(product_id)
    naive_time["client_created_at"] = "2026-08-14T12:00:00"
    response = _post_operation(negocio_client, establishment_id, headers, naive_time)
    assert response.status_code == 422
    assert response.json()["code"] == "identity.validation_error"
