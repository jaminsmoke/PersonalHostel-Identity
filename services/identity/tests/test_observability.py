import logging

from app.main import app as camareros_app
from app.main_negocio import app as negocio_app
from app.observability import access_logger


def test_metrics_camareros_expone_formato_prometheus(camarero_client):
    resp = camarero_client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_metrics_negocio_expone_formato_prometheus(negocio_client):
    resp = negocio_client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


def test_metrics_no_aparece_en_openapi():
    assert "/metrics" not in camareros_app.openapi()["paths"]
    assert "/metrics" not in negocio_app.openapi()["paths"]


def test_access_log_emite_json(camarero_client):
    registros = []

    class _Capture(logging.Handler):
        def emit(self, record):
            registros.append(record.getMessage())

    handler = _Capture()
    access_logger.addHandler(handler)
    try:
        camarero_client.get("/health")
    finally:
        access_logger.removeHandler(handler)

    assert registros, "el access log JSON no emitió ninguna línea"
    assert '"status"' in registros[-1]
    assert '"path"' in registros[-1]
