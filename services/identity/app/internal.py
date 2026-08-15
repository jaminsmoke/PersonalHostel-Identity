"""Cliente interno entre los dos servicios (profesionales ↔ negocio).

Cada servicio tiene su propia BD y no puede leer la del otro. Para las pocas
consultas que cruzan la frontera (buscar/verificar camarero, listar
establecimientos de un camarero) se usa este cliente, con dos transportes:

- ``direct`` (default, tests y ejecución en un solo proceso): consulta la BD del
  otro servicio directamente, sin red.
- ``http`` (Docker Compose / VPS): llama a las rutas ``/internal/*`` del otro
  servicio mediante httpx.

El transporte se elige con la variable ``INTERNAL_TRANSPORT`` (``direct`` por
defecto). En ``http`` se requieren ``CAMAREROS_INTERNAL_URL`` y
``NEGOCIO_INTERNAL_URL``.
"""

import os
import uuid
from typing import Protocol

import httpx
from fastapi import status

from app.db import CamareroSessionLocal, NegocioSessionLocal
from app.errors import (
    CAMARERO_NOT_FOUND,
    CREDENTIAL_INACTIVE,
    QR_INVALIDO,
    ApiError,
)
from app.models import (
    Camarero,
    Credencial,
    CredencialEstado,
    Establecimiento,
    Membresia,
    MembresiaEstado,
)
from app.security import get_verify_key, parse_and_verify_qr_payload

TRANSPORT_ENV = "INTERNAL_TRANSPORT"
CAMAREROS_URL_ENV = "CAMAREROS_INTERNAL_URL"
NEGOCIO_URL_ENV = "NEGOCIO_INTERNAL_URL"

TIMEOUT = 5.0


def _perfil_dict(c: Camarero) -> dict:
    return {
        "id": str(c.id),
        "nombre": c.nombre,
        "apellidos": c.apellidos,
        "email": c.email,
        "nick": c.nick,
        "data_origin": c.data_origin.value,
    }


class CamarerosInternal(Protocol):
    def buscar_por_email(self, email: str) -> dict | None:
        """Perfil del camarero por email, o ``None`` si no existe."""

    def perfil(self, camarero_id: uuid.UUID) -> dict | None:
        """Perfil del camarero por id, o ``None`` si no existe."""

    def verificar_qr(self, qr: str) -> uuid.UUID:
        """Devuelve ``camarero_id`` si el QR es válido y su credencial activa.

        Lanza 422 ``qr_invalido`` o 409 ``credencial_inactiva``.
        """


class NegocioInternal(Protocol):
    def establecimientos_de(self, camarero_id: uuid.UUID) -> list[dict]:
        """Establecimientos activos del camarero con su rol."""


class DirectCamarerosInternal:
    def buscar_por_email(self, email: str) -> dict | None:
        with CamareroSessionLocal() as db:
            c = db.query(Camarero).filter_by(email=email.lower()).one_or_none()
        return _perfil_dict(c) if c else None

    def perfil(self, camarero_id: uuid.UUID) -> dict | None:
        with CamareroSessionLocal() as db:
            c = db.get(Camarero, camarero_id)
        return _perfil_dict(c) if c else None

    def verificar_qr(self, qr: str) -> uuid.UUID:
        with CamareroSessionLocal() as db:
            parsed = parse_and_verify_qr_payload(qr, get_verify_key(db))
            if parsed is None:
                raise ApiError(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    code=QR_INVALIDO,
                    detail="El QR no es válido",
                )
            camarero_id, credencial_id = parsed
            credencial = db.get(Credencial, credencial_id)
            if (
                credencial is None
                or credencial.camarero_id != camarero_id
                or credencial.estado != CredencialEstado.activa
            ):
                raise ApiError(
                    status_code=status.HTTP_409_CONFLICT,
                    code=CREDENTIAL_INACTIVE,
                    detail="La credencial del QR no está activa",
                )
            return camarero_id


class DirectNegocioInternal:
    def establecimientos_de(self, camarero_id: uuid.UUID) -> list[dict]:
        with NegocioSessionLocal() as db:
            rows = (
                db.query(Establecimiento, Membresia.rol)
                .join(Membresia, Membresia.establecimiento_id == Establecimiento.id)
                .filter(
                    Membresia.camarero_id == camarero_id,
                    Membresia.estado == MembresiaEstado.activa,
                )
                .all()
            )
        return [
            {
                "id": str(e.id),
                "nombre": e.nombre,
                "cuenta_negocio_id": str(e.cuenta_negocio_id),
                "data_origin": e.data_origin.value,
                "rol": rol.value,
            }
            for e, rol in rows
        ]


def _raise_from_response(response: httpx.Response, fallback_code: str) -> None:
    try:
        body = response.json()
    except ValueError:
        body = {}
    raise ApiError(
        status_code=response.status_code,
        code=body.get("code", fallback_code),
        detail=body.get("detail", "Error interno entre servicios"),
    )


class HttpCamarerosInternal:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return httpx.request(method, f"{self.base_url}{path}", timeout=TIMEOUT, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="identity.internal_unavailable",
                detail="Servicio de profesionales no disponible",
            ) from exc

    def buscar_por_email(self, email: str) -> dict | None:
        response = self._request("GET", "/internal/camareros/buscar", params={"email": email})
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if response.status_code != 200:
            _raise_from_response(response, CAMARERO_NOT_FOUND)
        return response.json()

    def perfil(self, camarero_id: uuid.UUID) -> dict | None:
        response = self._request("GET", f"/internal/camareros/{camarero_id}")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if response.status_code != 200:
            _raise_from_response(response, CAMARERO_NOT_FOUND)
        return response.json()

    def verificar_qr(self, qr: str) -> uuid.UUID:
        response = self._request("POST", "/internal/camareros/qr/verify", json={"qr": qr})
        if response.status_code != 200:
            _raise_from_response(response, QR_INVALIDO)
        return uuid.UUID(response.json()["camarero_id"])


class HttpNegocioInternal:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def establecimientos_de(self, camarero_id: uuid.UUID) -> list[dict]:
        try:
            response = httpx.get(
                f"{self.base_url}/internal/camareros/{camarero_id}/establecimientos",
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise ApiError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="identity.internal_unavailable",
                detail="Servicio de negocio no disponible",
            ) from exc
        if response.status_code != 200:
            _raise_from_response(response, "identity.internal_error")
        return response.json()


def _transport() -> str:
    return os.environ.get(TRANSPORT_ENV, "direct").lower()


def get_camareros_internal() -> CamarerosInternal:
    if _transport() == "http":
        return HttpCamarerosInternal(os.environ[CAMAREROS_URL_ENV])
    return DirectCamarerosInternal()


def get_negocio_internal() -> NegocioInternal:
    if _transport() == "http":
        return HttpNegocioInternal(os.environ[NEGOCIO_URL_ENV])
    return DirectNegocioInternal()
