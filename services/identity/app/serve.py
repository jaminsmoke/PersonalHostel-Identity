"""Sirve la app pública (:8080) y la interna (:8081) en el mismo proceso."""

from __future__ import annotations

import asyncio
import os
import signal

import uvicorn

PUBLIC_PORT = 8080
INTERNAL_PORT = 8081


def _config(app, port: int) -> uvicorn.Config:
    return uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        access_log=False,
        lifespan="on",
    )


def _stop(*servers: uvicorn.Server) -> None:
    for server in servers:
        server.should_exit = True


async def serve(public_app, internal_app) -> None:
    public = uvicorn.Server(_config(public_app, PUBLIC_PORT))
    internal = uvicorn.Server(_config(internal_app, INTERNAL_PORT))
    public.install_signal_handlers = False
    internal.install_signal_handlers = False
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _stop, public, internal)
    except NotImplementedError:
        pass
    await asyncio.gather(public.serve(), internal.serve())


def main() -> None:
    service = os.environ.get("SERVICE", "camareros")
    if service == "negocio":
        from app.main_negocio import app as public_app
        from app.main_negocio_internal import app as internal_app
    else:
        from app.main import app as public_app
        from app.main_internal import app as internal_app
    asyncio.run(serve(public_app, internal_app))


if __name__ == "__main__":
    main()
