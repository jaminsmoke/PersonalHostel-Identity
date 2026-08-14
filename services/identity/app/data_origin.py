"""Política de admisión para procedencias no reales."""

import os

from fastapi import status

from app.errors import NON_REAL_DATA_FORBIDDEN, ApiError
from app.models import DataOrigin


_TRUE_VALUES = {"1", "true", "yes", "on", "si", "sí"}


def non_real_data_allowed() -> bool:
    """Devuelve True solo cuando el entorno lo habilita explícitamente."""

    return os.environ.get("ALLOW_NON_REAL_DATA", "false").strip().lower() in _TRUE_VALUES


def ensure_data_origin_allowed(origin: DataOrigin) -> None:
    """Rechaza test/demo con un default seguro para producción."""

    if origin is not DataOrigin.real and not non_real_data_allowed():
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=NON_REAL_DATA_FORBIDDEN,
            detail="La procedencia test o demo no está permitida en este entorno",
        )
