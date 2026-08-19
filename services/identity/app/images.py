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

IMAGEN_WEB_MIMETYPE = "image/webp"
IMAGEN_WEB_EXTENSION = "webp"
IMAGEN_WEB_MAX_INPUT_BYTES = 4 * 1024 * 1024  # 4 MB
IMAGEN_WEB_MAX_LADO = 2560  # px en el lado largo (hero/galería)


class FotoInvalida(Exception):
    """La imagen no es válida (formato no soportado, demasiado grande o ilegible)."""


def _normalizar_imagen(data: bytes, max_input: int, max_lado: int) -> tuple[bytes, str, int]:
    """Normaliza a WebP sin recorte, limitando el lado largo."""
    if len(data) > max_input:
        raise FotoInvalida(f"La imagen supera el tamaño máximo de {max_input // (1024 * 1024)} MB")

    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ("JPEG", "PNG", "WEBP"):
                raise FotoInvalida("Formato no soportado. Usa JPEG, PNG o WebP")
            img = img.convert("RGB")
            ancho, alto = img.size
            lado_largo = max(ancho, alto)
            if lado_largo > max_lado:
                escala = max_lado / lado_largo
                img = img.resize(
                    (int(ancho * escala), int(alto * escala)), Image.Resampling.LANCZOS
                )
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=82)
            buf.seek(0)
            payload = buf.read()
    except (UnidentifiedImageError, OSError) as exc:
        raise FotoInvalida("La imagen no se pudo leer") from exc

    return payload, IMAGEN_WEB_MIMETYPE, len(payload)


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


def normalizar_imagen_web(data: bytes) -> tuple[bytes, str, int]:
    """Normaliza una imagen de la web del negocio (hero/galería) a WebP.

    Sin recorte (respeta la proporción), con límite de tamaño de entrada (4 MB)
    y de lado largo (2560 px). Devuelve ``(bytes, mimetype, size)`` o lanza
    :class:`FotoInvalida`.
    """
    return _normalizar_imagen(data, IMAGEN_WEB_MAX_INPUT_BYTES, IMAGEN_WEB_MAX_LADO)
