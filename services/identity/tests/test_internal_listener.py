"""El listener público no sirve interno ni métricas; el interno sí."""


def test_publico_no_sirve_metrics_ni_internal(camarero_client, negocio_client):
    assert camarero_client.get("/metrics").status_code == 404
    assert camarero_client.get("/internal/camareros/directorio").status_code == 404
    assert negocio_client.get("/metrics").status_code == 404
    assert (
        negocio_client.get(
            "/internal/camareros/00000000-0000-0000-0000-000000000001/establecimientos"
        ).status_code
        == 404
    )


def test_interno_sirve_health_metrics_y_directorio(camarero_internal_client):
    assert camarero_internal_client.get("/health").json() == {"ok": True}
    metrics = camarero_internal_client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text
    directorio = camarero_internal_client.get("/internal/camareros/directorio")
    assert directorio.status_code == 200
    assert isinstance(directorio.json(), list)


def test_openapi_publico_no_declara_internal(camarero_client, negocio_client):
    cam = camarero_client.get("/openapi.json").json()["paths"]
    neg = negocio_client.get("/openapi.json").json()["paths"]
    assert "/metrics" not in cam
    assert "/metrics" not in neg
    assert not any(path.startswith("/internal") for path in cam)
    assert not any(path.startswith("/internal") for path in neg)
