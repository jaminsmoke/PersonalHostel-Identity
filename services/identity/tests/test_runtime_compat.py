"""Regresión de compatibilidad del runtime 3.14 y de las dependencias #30.

Garantiza que los hashes Argon2 persistidos por versión anterior siguen
verificándose (el hash es autodescriptivo y no debe depender de los defaults
del hasher actual) y que email-validator 2.3 mantiene el contrato observable
de registro (aceptación y 422).
"""

import uuid

from argon2 import PasswordHasher

from app.auth import hash_password, verify_password

LEGACY_PARAMS = {"time_cost": 3, "memory_cost": 32768, "parallelism": 1}


def test_argon2_verify_hash_con_parametros_heredados():
    hasher = PasswordHasher(**LEGACY_PARAMS)
    stored = hasher.hash("password-heredado-1")
    assert stored.startswith("$argon2id$")
    assert verify_password("password-heredado-1", stored) is True
    assert verify_password("password-otra", stored) is False


def test_argon2_round_trip_defaults():
    stored = hash_password("password-nueva-1")
    assert verify_password("password-nueva-1", stored) is True
    assert verify_password("incorrecta", stored) is False


def test_email_validator_acepta_correo_valido(camarero_client):
    resp = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": f"compat-valido-{uuid.uuid4()}@example.com",
            "password": "password-larga-1",
        },
    )
    assert resp.status_code == 201


def test_email_validator_rechaza_formato_invalido_422(camarero_client):
    resp = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": "no-es-un-email",
            "password": "password-larga-1",
        },
    )
    assert resp.status_code == 422
    assert "detail" in resp.json()
