"""IP del cliente detrás de Caddy / Docker.

Las APIs publican en 127.0.0.1 (prod) o en la red Compose. El peer TCP es el
proxy, no el usuario. Solo se honra ``X-Forwarded-For`` si el peer está en
``TRUSTED_PROXY_CIDRS``.
"""

from __future__ import annotations

import ipaddress
import os

from fastapi import Request

_DEFAULT_TRUSTED = "127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw = os.environ.get("TRUSTED_PROXY_CIDRS", _DEFAULT_TRUSTED)
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        networks.append(ipaddress.ip_network(item, strict=False))
    return networks


def _is_trusted(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in network for network in _trusted_networks())


def client_ip(request: Request) -> str:
    """Devuelve la IP de cuota: primer hop de XFF si el peer es de confianza."""
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted(peer):
        return peer
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer
    first = forwarded.split(",", 1)[0].strip()
    try:
        ipaddress.ip_address(first)
    except ValueError:
        return peer
    return first
