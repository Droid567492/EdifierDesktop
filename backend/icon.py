"""Shared speaker icon renderer for system tray, web favicon/manifest, and Win32 taskbar."""

from __future__ import annotations

from functools import lru_cache
import io
from pathlib import Path

from PIL import Image, ImageDraw

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def create_app_icon_image(size: int = 256) -> Image.Image:
    """Render the minimalist Edifier M60 / M90 speaker cabinet icon at the requested square size."""
    base = 256
    img = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark studio badge for crisp contrast on both light and dark Windows taskbars.
    draw.rounded_rectangle([12, 12, 244, 244], radius=48, fill=(16, 18, 24, 255))

    # Minimalist speaker cabinet + copper tweeter & cyan woofer rings (4x scale of 64px tray icon).
    draw.rounded_rectangle(
        [48, 32, 208, 224],
        radius=32,
        fill=(28, 32, 42, 255),
        outline=(245, 158, 11, 255),
        width=12,
    )
    draw.ellipse([104, 60, 152, 108], fill=(245, 158, 11, 255))
    draw.ellipse([80, 124, 176, 204], outline=(56, 189, 248, 255), width=12)
    draw.ellipse([116, 152, 140, 176], fill=(245, 158, 11, 255))

    if size != base:
        return img.resize((size, size), Image.Resampling.LANCZOS)
    return img


@lru_cache(maxsize=4)
def get_icon_png_bytes(size: int = 256) -> bytes:
    buf = io.BytesIO()
    create_app_icon_image(size).save(buf, format="PNG")
    return buf.getvalue()


@lru_cache(maxsize=1)
def get_icon_ico_bytes() -> bytes:
    buf = io.BytesIO()
    master = create_app_icon_image(256)
    master.save(buf, format="ICO", sizes=ICO_SIZES)
    return buf.getvalue()


def ensure_ico_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ico_bytes = get_icon_ico_bytes()
    try:
        if path.exists() and path.read_bytes() == ico_bytes:
            return path
    except OSError:
        pass
    path.write_bytes(ico_bytes)
    return path
