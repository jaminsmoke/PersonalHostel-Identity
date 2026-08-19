#!/usr/bin/env python3
"""Abre un túnel SSH al stack de observabilidad del VPS y las UIs en local.

Reenvía al host local los puertos internos del VPS que solo escuchan en
127.0.0.1 (Prometheus :9090, Alertmanager :9093, Grafana :3001) y abre el
navegador por defecto. No expone ningún puerto nuevo en el VPS: solo tu
máquina alcanza las UIs mientras el túnel está activo.

Uso:
    python services/identity/scripts/obs_tunnel.py            # túnel + navegador
    python services/identity/scripts/obs_tunnel.py --no-browser
    python services/identity/scripts/obs_tunnel.py --ports 9090 3001

Lee de `.env` (nunca en git): VPS_HOST, VPS_USER, VPS_PASSWORD (fallback),
VPS_HOST_KEY (clave de host ed25519 pinned anti-MITM) y VPS_SSH_KEY_PATH
(opcional; por defecto ~/.ssh/identity_vps).

Detente con Ctrl+C. Si un puerto local ya está ocupado, se omite ese túnel.
"""

import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import paramiko

try:
    from scripts.deploy_staging import PinnedHostKey, env_value, ssh_key_path
except ModuleNotFoundError:  # ejecución directa desde la raíz del repositorio
    from deploy_staging import PinnedHostKey, env_value, ssh_key_path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TUNNELS = {
    "9090": "Prometheus",
    "9093": "Alertmanager",
    "3001": "Grafana",
}


def connect_vps():
    """Conecta con paramiko usando la clave pinned del .env (como deploy)."""
    host = env_value("VPS_HOST")
    user = env_value("VPS_USER") or "root"
    password = env_value("VPS_PASSWORD")
    expected_host_key = env_value("VPS_HOST_KEY")
    if not host or not expected_host_key:
        print("Falta VPS_HOST o VPS_HOST_KEY en el .env de la raíz.")
        return None

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(PinnedHostKey(expected_host_key))
    key = ssh_key_path()
    kwargs = {"timeout": 30, "look_for_keys": False, "allow_agent": False}
    if os.path.exists(key):
        kwargs["key_filename"] = key
        if password:
            kwargs["password"] = password
        print(f"Conectando con clave SSH ({key})...")
    elif password:
        kwargs["password"] = password
        print("AVISO: sin clave SSH; usando password del .env.")
    else:
        print(f"Sin clave SSH ({key}) ni VPS_PASSWORD en el .env.")
        return None
    try:
        client.connect(host, username=user, **kwargs)
    except paramiko.SSHException as exc:
        print(f"Error SSH: {exc}")
        return None
    return client


def _forward(chan, sock):
    """Pasa datos bidireccionalmente entre el canal SSH y el socket local."""
    try:
        while True:
            data = chan.recv(32768)
            if not data:
                break
            sock.sendall(data)
    except (OSError, EOFError):
        pass
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass
    try:
        chan.close()
    except Exception:
        pass


def forward_port(client, remote_port: str) -> bool:
    """Abre un listener local en remote_port y lo conecta al puerto del VPS."""
    if not remote_port.isdigit():
        print(f"Puerto inválido: {remote_port}")
        return False
    local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    local.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        local.bind(("127.0.0.1", int(remote_port)))
    except OSError:
        print(f"Puerto local {remote_port} ya en uso; se omite {remote_port}.")
        return False
    local.listen(10)
    transport = client.get_transport()

    def accept_loop():
        while True:
            try:
                conn, _addr = local.accept()
            except OSError:
                return
            try:
                chan = transport.open_channel(
                    "direct-tcpip", ("127.0.0.1", int(remote_port)), conn.getpeername()
                )
            except Exception as exc:
                print(f"No se pudo abrir túnel a :{remote_port}: {exc}")
                conn.close()
                continue
            t1 = threading.Thread(target=_forward, args=(chan, conn), daemon=True)
            t2 = threading.Thread(target=_forward, args=(conn, chan), daemon=True)
            t1.start()
            t2.start()

    threading.Thread(target=accept_loop, daemon=True).start()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-browser", action="store_true", help="No abrir el navegador."
    )
    parser.add_argument(
        "--ports", nargs="*", default=["9090", "9093", "3001"],
        help="Puertos a reenviar (default: 9090 9093 3001).",
    )
    args = parser.parse_args()

    client = connect_vps()
    if client is None:
        return 1

    opened = []
    for port in args.ports:
        if forward_port(client, port):
            opened.append(port)

    if not opened:
        print("No se pudo abrir ningún túnel (¿puertos locales ocupados?).")
        client.close()
        return 1

    print("\nTúneles activos (Ctrl+C para cerrar):")
    for port in opened:
        name = TUNNELS.get(port, "?")
        url = f"http://localhost:{port}"
        print(f"  {name:12s} -> {url}")
    if not args.no_browser:
        for port in opened:
            webbrowser.open(f"http://localhost:{port}")

    print("\nEsperando... pulsa Ctrl+C para cortar.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nCerrando túneles...")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
