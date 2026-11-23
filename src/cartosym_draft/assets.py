"""Images as files next to the pages instead of inside them, so that a page loads before its pictures.

- `raster_figure`: a figure SVG that only wraps coverage rasters becomes a lossless WebP at the rasters' own
  resolution, shown scaled up with `image-rendering: pixelated`, as the inline SVG was. Vector figures stay inline.
- `externalize_data_images`: the `data:` images of a page (the walkthroughs) become files, byte for byte.
- `prune`: removes the files of a folder that the pages no longer use.

File names are a hash of the content, so a rebuild that draws the same picture writes the same file.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import re
from pathlib import Path

import resvg_py
from PIL import Image

_IMAGE = re.compile(r'<image href="data:image/png;base64,([A-Za-z0-9+/=]+)"([^>]*)/?>')
_SIZE = re.compile(r'<svg\b[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"')
_DATA_IMG = re.compile(r'(<img\b[^>]*?\bsrc=")data:image/(png|jpeg|jpg|gif|webp|svg\+xml);base64,([A-Za-z0-9+/=]+)("[^>]*>)')
EXT = {"png": "png", "jpeg": "jpg", "jpg": "jpg", "gif": "gif", "webp": "webp", "svg+xml": "svg"}


def _name(data: bytes, ext: str) -> str:
    return hashlib.sha256(data).hexdigest()[:16] + "." + ext


def _write(out_dir: Path, data: bytes, ext: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _name(data, ext)
    path = out_dir / name
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    return name


def is_raster(svg: str) -> bool:
    """A figure whose content is coverage rasters only (a background rect and <image> elements)."""
    rest = _IMAGE.sub("", svg)
    return "data:image/png" in svg and not re.search(r"<(path|text|circle|line|polyline|polygon|use|g)\b", rest)


def webp(png: bytes, lossless: bool = True, quality: int = 82) -> bytes:
    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).save(buf, "WEBP", lossless=lossless, quality=100 if lossless else quality, method=6)
    return buf.getvalue()


def raster_figure(svg: str, out_dir: Path, rel: str, alt: str = "") -> str:
    """An <img> for a raster-only figure SVG, written to *out_dir* (referenced as *rel*/<file>); other SVGs unchanged."""
    if not is_raster(svg):
        return svg
    w, h = (float(v) for v in _SIZE.search(svg).groups())
    sizes = {Image.open(io.BytesIO(base64.b64decode(b))).size for b, _ in _IMAGE.findall(svg)}
    # Render at the rasters' own grid when they all share it, so no pixel is resampled; otherwise at the figure's size.
    zoom = 1.0
    if len(sizes) == 1:
        (nw, nh), = sizes
        if abs(nw / w - nh / h) < 1e-9:
            zoom = nw / w
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=zoom))
    name = _write(out_dir, webp(png), "webp")
    return (f'<img class="raster" src="{rel}/{name}" width="{w:g}" height="{h:g}" loading="lazy" decoding="async" '
            f'alt="{html.escape(alt)}">')


def svg_thumbnail(svg: str, out_dir: Path, rel: str, width: int = 480) -> str:
    """A lossy WebP of any figure SVG, *width* pixels wide, for a preview (the home page's tiles). Returns its path."""
    w = float(_SIZE.search(svg).group(1))
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=width / w))
    return f"{rel}/{_write(out_dir, webp(png, lossless=False), 'webp')}"


def externalize_data_images(page: str, out_dir: Path, rel: str) -> str:
    """Move each <img src="data:..."> of *page* into a file in *out_dir*, unchanged, and load it lazily."""
    def repl(m: re.Match) -> str:
        data = base64.b64decode(m.group(3))
        name = _write(out_dir, data, EXT[m.group(2)])
        tail = m.group(4)
        if "loading=" not in m.group(1) + tail:
            tail = tail.replace(">", ' loading="lazy" decoding="async">', 1) if not tail.endswith("/>") else \
                tail[:-2] + ' loading="lazy" decoding="async"/>'
        return f"{m.group(1)}{rel}/{name}{tail}"
    return _DATA_IMG.sub(repl, page)


def prune(out_dir: Path, pages: list[str]) -> list[str]:
    """Delete the files of *out_dir* that none of *pages* (their HTML) mention. Returns the names deleted."""
    if not out_dir.exists():
        return []
    text = "".join(pages)
    gone = [p.name for p in out_dir.iterdir() if p.is_file() and p.name not in text]
    for name in gone:
        (out_dir / name).unlink()
    return gone


__all__ = ["externalize_data_images", "is_raster", "prune", "raster_figure", "svg_thumbnail", "webp"]
