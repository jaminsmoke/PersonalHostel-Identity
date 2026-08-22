"""IP de cuota detrás de proxy de confianza."""

from starlette.requests import Request

from app.client_ip import client_ip


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 12345),
        "server": ("test", 80),
    }
    return Request(scope)


def test_xff_se_honra_desde_bridge_docker():
    req = _request("172.17.0.1", "203.0.113.9, 172.17.0.1")
    assert client_ip(req) == "203.0.113.9"


def test_xff_se_ignora_si_el_peer_no_es_de_confianza():
    req = _request("8.8.8.8", "203.0.113.9")
    assert client_ip(req) == "8.8.8.8"


def test_peer_no_ip_sin_xff():
    req = _request("testclient")
    assert client_ip(req) == "testclient"


def test_xff_basura_no_sustituye_al_peer_de_confianza():
    req = _request("127.0.0.1", "no-es-una-ip")
    assert client_ip(req) == "127.0.0.1"
