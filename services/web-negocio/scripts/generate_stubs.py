"""Genera WebP atmosféricos originales para el shell Estate Hospitality.

No copia fotos de Stitch ni de CDNs. Son fondos abstractos (luz cálida sobre
carbón) para que la plantilla no colapse a un gradiente vacío.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1] / "public" / "stubs"


def _noise(size: tuple[int, int], rng: random.Random, amp: int = 18) -> Image.Image:
    w, h = size
    px = bytearray(w * h)
    for i in range(w * h):
        px[i] = rng.randint(0, amp)
    return Image.frombytes("L", size, bytes(px))


def _radial(size: tuple[int, int], cx: float, cy: float, radius: float, color: tuple[int, int, int]) -> Image.Image:
    w, h = size
    layer = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(layer)
    steps = 28
    for i in range(steps, 0, -1):
        t = i / steps
        r = radius * t
        fade = int(255 * (1 - t) ** 2)
        col = tuple(min(255, int(c * fade / 255)) for c in color)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    return layer.filter(ImageFilter.GaussianBlur(radius=max(8, radius / 8)))


def _screen(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.screen(a, b)


def _vignette(img: Image.Image, strength: float = 0.72) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((-w * 0.1, -h * 0.15, w * 1.1, h * 1.15), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=min(w, h) / 3))
    dark = Image.new("RGB", (w, h), (8, 9, 9))
    return Image.composite(img, Image.blend(img, dark, strength), mask)


def atmosphere(size: tuple[int, int], seed: int, portrait: bool = False, luminoso: bool = False) -> Image.Image:
    rng = random.Random(seed)
    w, h = size
    base = (32, 28, 24) if luminoso else (12, 14, 14)
    img = Image.new("RGB", size, base)

    lamps = [
        ((0.22, 0.38), 0.42, (255, 176, 72)),
        ((0.68, 0.28), 0.35, (255, 196, 110)),
        ((0.48, 0.72), 0.50, (180, 110, 40)),
        ((0.85, 0.62), 0.28, (255, 210, 140)),
        ((0.12, 0.78), 0.22, (120, 80, 36)),
    ]
    if luminoso:
        lamps = [
            ((0.30, 0.42), 0.55, (255, 198, 120)),
            ((0.62, 0.32), 0.48, (255, 220, 170)),
            ((0.50, 0.68), 0.58, (210, 140, 70)),
            ((0.78, 0.58), 0.36, (255, 230, 190)),
            ((0.18, 0.70), 0.32, (180, 110, 50)),
        ]
    if portrait:
        lamps = [
            ((0.55, 0.32), 0.48, (255, 186, 90)),
            ((0.30, 0.58), 0.40, (160, 96, 32)),
            ((0.72, 0.78), 0.30, (255, 214, 150)),
        ]
    for (nx, ny), rel, color in lamps:
        glow = _radial(size, nx * w, ny * h, rel * max(w, h), color)
        img = _screen(img, glow)

    # Barra / pasaplatos: trazo horizontal cálido.
    bar = Image.new("RGB", size, (0, 0, 0))
    bd = ImageDraw.Draw(bar)
    y = int(h * (0.62 if not portrait else 0.70))
    bd.rectangle((int(w * 0.08), y, int(w * 0.92), y + int(h * 0.035)), fill=(90, 58, 18))
    bar = bar.filter(ImageFilter.GaussianBlur(radius=18))
    img = _screen(img, bar)

    img = img.filter(ImageFilter.GaussianBlur(radius=4 if luminoso else 6))
    grain = _noise(size, rng, amp=22)
    img = _screen(img, Image.merge("RGB", (grain, grain, grain)))
    img = ImageEnhance.Color(img).enhance(0.95 if luminoso else 0.85)
    img = ImageEnhance.Contrast(img).enhance(1.2 if luminoso else 1.15)
    if luminoso:
        img = ImageEnhance.Brightness(img).enhance(1.25)
    return _vignette(img, 0.38 if luminoso else 0.68)


def mapa_oscuro(size: tuple[int, int], seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    w, h = size
    img = Image.new("RGB", size, (18, 20, 21))
    draw = ImageDraw.Draw(img)
    gold = (140, 110, 55)
    dim = (70, 64, 48)

    for i in range(8):
        y = int(h * (0.10 + i * 0.11))
        jitter = rng.randint(-18, 18)
        draw.line((0, y + jitter, w, y + jitter + rng.randint(-10, 10)), fill=dim, width=4)
    for i in range(10):
        x = int(w * (0.06 + i * 0.10))
        draw.line((x, 0, x + rng.randint(-40, 40), h), fill=dim, width=3)

    cx, cy = w // 2, int(h * 0.52)
    draw.rounded_rectangle((cx - 110, cy - 70, cx + 110, cy + 70), radius=8, outline=gold, width=3)
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=gold)
    pin = _radial(size, cx, cy - 70, 90, (255, 191, 0))
    img = _screen(img, pin)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    return _vignette(ImageEnhance.Contrast(img).enhance(1.1), 0.45)


def guardar(img: Image.Image, name: str, quality: int = 78) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    dest = ROOT / name
    img.save(dest, "WEBP", quality=quality, method=6)
    print(f"{dest} {dest.stat().st_size} bytes")


def main() -> None:
    guardar(atmosphere((1600, 1000), seed=11, luminoso=True), "hero.webp")
    guardar(atmosphere((1200, 1500), seed=23, portrait=True), "nosotros.webp")
    blurred = atmosphere((1600, 1000), seed=11, luminoso=True).filter(ImageFilter.GaussianBlur(radius=10))
    guardar(blurred, "interior.webp", quality=72)
    guardar(mapa_oscuro((1400, 900)), "mapa.webp", quality=74)


if __name__ == "__main__":
    main()
