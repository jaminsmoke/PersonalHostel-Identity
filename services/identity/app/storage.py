"""Almacenamiento de fotos de perfil con abstracción portable.

La interfaz `FotoStorage` permite cambiar la implementación local (volumen
Docker) por object storage en el VPS sin tocar las rutas HTTP.
"""

import contextlib
import os
import uuid
from pathlib import Path
from typing import Protocol

FOTOS_DIR_ENV = "FOTOS_DIR"
DEFAULT_FOTOS_DIR = "/app/data/fotos"


class FotoStorage(Protocol):
    def guardar(self, camarero_id: uuid.UUID, data: bytes, extension: str) -> str:
        """Guarda ``data`` y devuelve la clave de almacenamiento."""

    def leer(self, clave: str) -> bytes | None:
        """Devuelve los bytes de ``clave``, o ``None`` si no existe."""

    def borrar(self, clave: str) -> None:
        """Elimina ``clave``; no falla si no existe."""


class LocalFotoStorage:
    """Implementación sobre un directorio local (volumen Docker)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def guardar(self, camarero_id: uuid.UUID, data: bytes, extension: str) -> str:
        carpeta = self.root / str(camarero_id)
        carpeta.mkdir(parents=True, exist_ok=True)
        clave = f"{camarero_id}/{uuid.uuid4()}.{extension}"
        (self.root / clave).write_bytes(data)
        return clave

    def leer(self, clave: str) -> bytes | None:
        path = self.root / clave
        if not path.is_file():
            return None
        return path.read_bytes()

    def borrar(self, clave: str) -> None:
        path = self.root / clave
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)


_storage: FotoStorage | None = None


def get_foto_storage() -> FotoStorage:
    """Devuelve el almacenamiento de fotos (singleton local por defecto)."""
    global _storage
    if _storage is None:
        root = Path(os.environ.get(FOTOS_DIR_ENV, DEFAULT_FOTOS_DIR))
        _storage = LocalFotoStorage(root)
    return _storage
