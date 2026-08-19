import uuid
from datetime import UTC, datetime


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
        "client_created_at": datetime.now(UTC).isoformat(),
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
    collision = _post_operation(negocio_client, establishment_id, headers, changed_intention)
    assert collision.status_code == 409
    assert collision.json()["code"] == "identity.operation_id_en_uso"


def test_descripcion_opcional_en_sync_y_snapshot(negocio_client):
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    create = _operation(product_id)
    assert _post_operation(negocio_client, establishment_id, headers, create).status_code == 200
    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    )
    assert catalog.json()["productos"][0]["descripcion"] is None

    update = _operation(product_id, action="actualizar", base_revision=1)
    update["payload"]["descripcion"] = "  Espresso de finca  "
    updated = _post_operation(negocio_client, establishment_id, headers, update)
    assert updated.status_code == 200
    assert updated.json()["result_snapshot"]["descripcion"] == "Espresso de finca"

    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())
    assert (
        _post_operation(
            negocio_client, establishment_id, headers, _operation(product_id)
        ).status_code
        == 200
    )

    update = _operation(product_id, action="actualizar", base_revision=1, name="Café doble")
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
    assert (
        _post_operation(
            negocio_client, establishment_id, headers, _operation(product_id)
        ).status_code
        == 200
    )

    stale = _operation(product_id, action="actualizar", base_revision=0, name="Café offline")
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
    assert (
        _post_operation(
            negocio_client, establishment_id, headers, _operation(product_id)
        ).status_code
        == 200
    )

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
    assert (
        _post_operation(
            negocio_client, establishment_id, owner_headers, _operation(product_id)
        ).status_code
        == 200
    )

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
    login = camarero_client.post("/v1/auth/login", json={"email": email, "password": password})
    member_headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert (
        negocio_client.get(
            f"/v1/establecimientos/{establishment_id}/catalogo", headers=member_headers
        ).status_code
        == 200
    )
    assert (
        negocio_client.get(
            f"/v1/establecimientos/{establishment_id}/sync/cambios", headers=member_headers
        ).status_code
        == 200
    )
    member_write = _post_operation(
        negocio_client,
        establishment_id,
        member_headers,
        _operation(product_id, action="actualizar", base_revision=1),
    )
    assert member_write.status_code == 401

    other_headers, _ = _create_business_and_establishment(negocio_client)
    assert (
        negocio_client.get(
            f"/v1/establecimientos/{establishment_id}/catalogo", headers=other_headers
        ).status_code
        == 403
    )
    assert (
        _post_operation(
            negocio_client,
            establishment_id,
            other_headers,
            _operation(product_id, action="actualizar", base_revision=1),
        ).status_code
        == 403
    )


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


def test_orden_invertido_crea_conflicto_y_no_pisa(negocio_client):
    """La actualización llega antes que el alta: entra en conflicto (no se aplica en
    silencio), el alta posterior aplica, y la resolución obsoleta se rechaza con 409
    sin pisar el canónico ni perder la operación pendiente."""
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())

    # La actualización (base 1) llega primero: sin producto aún -> conflicto, no aplica.
    update = _operation(product_id, action="actualizar", base_revision=1, name="Nombre invertido")
    conflicted = _post_operation(negocio_client, establishment_id, headers, update)
    assert conflicted.status_code == 200
    assert conflicted.json()["estado"] == "conflicto"
    conflict_id = conflicted.json()["conflict_id"]

    # El alta (base 0) llega después y se aplica.
    created = _post_operation(negocio_client, establishment_id, headers, _operation(product_id))
    assert created.status_code == 200
    assert created.json()["estado"] == "aplicada"

    # Resolver con la revisión actual (1): el canónico del conflicto era 0, así que
    # la resolución es obsoleta y se rechaza. La operación pendiente no se pierde.
    stale = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos/{conflict_id}/resolver",
        headers=headers,
        json={"decision": "aceptar", "expected_revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "identity.resolucion_sync_obsoleta"

    # El catálogo refleja solo el alta; la actualización sigue pendiente de decisión.
    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    ).json()
    assert catalog["revision"] == 1
    assert catalog["productos"][0]["nombre"] == "Café solo"
    conflicts = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos?estado=todos",
        headers=headers,
    )
    assert [c["id"] for c in conflicts.json()] == [conflict_id]


def test_duplicado_con_reloj_atrasado_es_idempotente(negocio_client):
    """Reenviar la misma operación con un client_created_at menor (reloj atrasado)
    no la reaplica ni la pisa: devuelve el mismo resultado y no crea conflicto nuevo."""
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())

    first = _post_operation(negocio_client, establishment_id, headers, _operation(product_id))
    assert first.status_code == 200
    assert first.json()["estado"] == "aplicada"

    replay = _operation(product_id, operation_id=first.json()["operation_id"])
    replay["client_created_at"] = "2025-01-01T00:00:00+00:00"  # reloj atrasado
    repeated = _post_operation(negocio_client, establishment_id, headers, replay)
    assert repeated.status_code == 200
    assert repeated.json() == first.json()

    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    ).json()
    assert catalog["revision"] == 1
    assert len(catalog["productos"]) == 1
    conflicts = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos?estado=todos",
        headers=headers,
    )
    assert conflicts.status_code == 200
    assert conflicts.json() == []


def test_modificacion_vs_borrado_en_mismo_lote(negocio_client):
    """Un alta y un borrado del mismo producto llegan seguidos: el borrado sobre
    base obsoleta entra en conflicto y, al aceptarse, aplica el tombstone."""
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())

    created = _post_operation(negocio_client, establishment_id, headers, _operation(product_id))
    assert created.status_code == 200

    # El borrado se basa en la revisión 1 (correcta) y se aplica.
    archived = _post_operation(
        negocio_client,
        establishment_id,
        headers,
        _operation(product_id, action="archivar", base_revision=1),
    )
    assert archived.status_code == 200
    assert archived.json()["estado"] == "aplicada"

    # Una modificación con base obsoleta (revisión 1 tras el borrado) -> conflicto.
    stale_update = _post_operation(
        negocio_client,
        establishment_id,
        headers,
        _operation(product_id, action="actualizar", base_revision=1, name="Revive"),
    )
    assert stale_update.status_code == 200
    assert stale_update.json()["estado"] == "conflicto"

    # Rechazar la modificación: el tombstone del borrado se mantiene.
    rejected = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos/{stale_update.json()['conflict_id']}/resolver",
        headers=headers,
        json={"decision": "rechazar", "expected_revision": 2},
    )
    assert rejected.status_code == 200, rejected.text
    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    ).json()
    assert catalog["revision"] == 2
    assert catalog["productos"] == []  # sigue archivado


def test_decision_repetida_tras_resolver_es_idempotente(negocio_client):
    """Resolver dos veces el mismo conflicto: la segunda devuelve 409 sin volver a
    aplicar la operación ni cambiar la revisión."""
    headers, establishment_id = _create_business_and_establishment(negocio_client)
    product_id = str(uuid.uuid4())

    assert (
        _post_operation(
            negocio_client, establishment_id, headers, _operation(product_id)
        ).status_code
        == 200
    )
    conflicted = _post_operation(
        negocio_client,
        establishment_id,
        headers,
        _operation(product_id, action="actualizar", base_revision=0, name="Segunda"),
    ).json()
    conflict_id = conflicted["conflict_id"]

    first = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos/{conflict_id}/resolver",
        headers=headers,
        json={"decision": "aceptar", "expected_revision": 1},
    )
    assert first.status_code == 200
    assert first.json()["estado"] == "aceptado"

    repeat = negocio_client.post(
        f"/v1/establecimientos/{establishment_id}/sync/conflictos/{conflict_id}/resolver",
        headers=headers,
        json={"decision": "aceptar", "expected_revision": 2},
    )
    assert repeat.status_code == 409
    assert repeat.json()["code"] == "identity.conflicto_sync_ya_resuelto"

    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment_id}/catalogo", headers=headers
    ).json()
    assert catalog["revision"] == 2
    assert catalog["productos"][0]["nombre"] == "Segunda"
