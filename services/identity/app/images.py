"""Procesado de la foto de perfil con Pillow.

Normaliza cualquier imagen aceptada (JPEG/PNG/WebP) a un único avatar
cuadrado 256×256 en WebP, minimizando el almacenamiento y la PII retenida.
"""

import io

from PIL import Image, UnidentifiedImageError

AVATAR_SIZE = 256
AVATAR_MIMETYPE = "image/webp"
AVATAR_EXTENSION = "webp"
MAX_INPUT_BYTES = 2 * 1024 * 1024  # 2 MB


class FotoInvalida(Exception):
    """La imagen no es válida (formato no soportado, demasiado grande o ilegible)."""


def normalizar_foto(data: bytes) -> tuple[bytes, str, int]:
    """Normaliza a un avatar 256×256 WebP.

    Devuelve ``(bytes, mimetype, size)``. Lanza :class:`FotoInvalida` si no es válida.
    """
    if len(data) > MAX_INPUT_BYTES:
        raise FotoInvalida("La foto supera el tamaño máximo de 2 MB")

    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ("JPEG", "PNG", "WEBP"):
                raise FotoInvalida("Formato no soportado. Usa JPEG, PNG o WebP")
            img = img.convert("RGB")
            img = _recortar_cuadrado(img)
            img = img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=85)
            buf.seek(0)
            payload = buf.read()
    except (UnidentifiedImageError, OSError) as exc:
        raise FotoInvalida("La imagen no se pudo leer") from exc

    return payload, AVATAR_MIMETYPE, len(payload)


def _recortar_cuadrado(img: Image.Image) -> Image.Image:
    ancho, alto = img.size
    lado = min(ancho, alto)
    izq = (ancho - lado) // 2
    sup = (alto - lado) // 2
    return img.crop((izq, sup, izq + lado, sup + lado))
