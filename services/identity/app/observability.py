"""Observabilidad mínima de las APIs: métricas Prometheus y access log JSON.

- ``/metrics`` (formato Prometheus) lo expone ``prometheus-fastapi-instrumentator``.
  No se sirve por Caddy; Prometheus lo raspa por la red interna de Docker.
- El access log JSON emite una línea por request para que Alloy/Loki la
  parsee (método, ruta, status y latencia). Sustituye el access log plano de
  uvicorn (que se desactiva con ``--no-access-log`` en entrypoint).
  El path ``/v1/cfc/mesa/{token}`` (y subrutas) se registra como
  ``/v1/cfc/mesa/*`` o ``/v1/cfc/mesa/*/carta``.
"""

import json
import logging
import os
import time

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

access_logger = logging.getLogger("app.access")

_CFC_MESA_PREFIX = "/v1/cfc/mesa/"


def redact_access_path(path: str) -> str:
    """Sustituye el token opaco de mesa por ``*`` para no filtrarlo a Loki."""
    if not path.startswith(_CFC_MESA_PREFIX) or path == _CFC_MESA_PREFIX:
        return path
    resto = path[len(_CFC_MESA_PREFIX) :]
    segmento, *cola = resto.split("/", 1)
    if not segmento:
        return path
    sufijo = f"/{cola[0]}" if cola else ""
    return f"{_CFC_MESA_PREFIX}*{sufijo}"


def mount_metrics(app: FastAPI) -> None:
    """Instrumenta la app y expone ``/metrics`` en formato Prometheus."""
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, include_in_schema=False)


def mount_access_log(app: FastAPI) -> None:
    """Añade un access log JSON (una línea por request)."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    access_logger.handlers = [handler]
    access_logger.propagate = False
    access_logger.setLevel(logging.INFO)

    @app.middleware("http")
    async def json_access_log(request: Request, call_next):
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            access_logger.info(
                json.dumps(
                    {
                        "service": os.environ.get("SERVICE", "camareros"),
                        "method": request.method,
                        "path": redact_access_path(request.url.path),
                        "status": status_code,
                        "duration_ms": duration_ms,
                    }
                )
            )
