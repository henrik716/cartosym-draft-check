"""Portray coverages following the draft requirements.

- /req/coverage/*: colorChannels, alphaChannel, singleChannel, colorMap,
  opacityMap and gamma, resolved per cell (rules may select on cell values).
- /req/hill-shading/*: shade from slope and aspect relative to the sun,
  scaled by factor, optionally mapped through its own colorMap / opacityMap.

The result is an SVG <image> holding a PNG with one pixel per cell.
"""

from __future__ import annotations

import base64
import math
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any

from .colors import NAMED_COLORS
from .cascade import resolve
from .evaluate import Context
from .options import Options

_NAMED = {k.lower(): v for k, v in NAMED_COLORS.items()}

RGB = tuple[float, float, float]

# What a colorChannels value of 1 means, by Options.color_channels_scale.
_CHANNEL_SCALE = {"as-given": 1.0, "reflectance": 10000.0, "display": 3000.0}


@dataclass
class Grid:
    """A coverage: named bands of cell values, row 0 at the north edge."""

    bbox: tuple[float, float, float, float]  # minx, miny, maxx, maxy in metres
    cols: int
    rows: int
    bands: dict[str, list[list[Any]]] = field(default_factory=dict)
    name: str = ""  # which sample_data function made it, for the playground

    @property
    def cell_size(self) -> float:
        return (self.bbox[2] - self.bbox[0]) / self.cols


def parse_color(c: Any, scale: float = 255) -> RGB | None:
    """A color as 0..1 components: a name, #hex, [r, g, b] or {r, g, b} in 0..*scale*."""
    if c is None:
        return None
    if isinstance(c, str):
        h = _NAMED.get(c.lower(), c)
        if h.startswith("#") and len(h) == 7:
            return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]
        return None
    if isinstance(c, (list, tuple)) and len(c) == 3:
        return tuple(float(v) / scale for v in c)  # type: ignore[return-value]
    if isinstance(c, dict) and {"r", "g", "b"} <= set(c):
        return (float(c["r"]) / scale, float(c["g"]) / scale, float(c["b"]) / scale)
    return None


def map_value(entries: list, value: float, opts: Options, convert) -> Any:
    """Look *value* up in a colorMap / opacityMap ([[value, output, name?], ...]).

    Returns None for a value outside the map when values outside are transparent.
    """
    pts = sorted(((float(e[0]), convert(e[1])) for e in entries), key=lambda p: p[0])
    if value < pts[0][0] or value > pts[-1][0]:
        if opts.map_outside == "transparent":
            return None
        return pts[0][1] if value < pts[0][0] else pts[-1][1]
    for (v0, o0), (v1, o1) in zip(pts, pts[1:]):
        if v0 <= value <= v1:
            if opts.map_mode == "step" or v1 == v0:
                return o1 if value == v1 else o0
            t = (value - v0) / (v1 - v0)
            if isinstance(o0, tuple):
                return tuple(a + (b - a) * t for a, b in zip(o0, o1))
            return o0 + (o1 - o0) * t
    return pts[-1][1]


def _shade(elev: list[list[float | None]], r: int, c: int, cell: float, hs: dict, opts: Options) -> float:
    """Shade 0..1 of one cell: 1 = no darkening."""
    rows, cols = len(elev), len(elev[0])

    def z(rr, cc):
        v = elev[min(max(rr, 0), rows - 1)][min(max(cc, 0), cols - 1)]
        return elev[r][c] if v is None else v

    factor = float(hs.get("factor", 1) or 1)
    k = factor if opts.hillshade_factor == "exaggeration" else 1.0
    dzdx = (z(r, c + 1) - z(r, c - 1)) / (2 * cell)  # east
    dzdy = (z(r - 1, c) - z(r + 1, c)) / (2 * cell)  # north (row 0 is north)
    nx, ny, nz = -k * dzdx, -k * dzdy, 1.0
    n = math.sqrt(nx * nx + ny * ny + nz * nz)
    sun = hs.get("sun") or {}
    az = math.radians(float(sun.get("azimuth", 315)))
    el = math.radians(float(sun.get("elevation", 45)))
    if opts.hillshade_azimuth == "clockwise-from-north":
        hx, hy = math.sin(az), math.cos(az)
    else:
        hx, hy = math.cos(az), math.sin(az)
    lit = max(0.0, (nx * hx * math.cos(el) + ny * hy * math.cos(el) + nz * math.sin(el)) / n)
    if opts.hillshade_factor == "intensity":
        return min(1.0, max(0.0, 1 - factor * (1 - lit)))
    if opts.hillshade_factor == "percent":
        return min(1.0, max(0.0, 1 - factor / 100 * (1 - lit)))
    return lit


def _png(width: int, height: int, rgba: bytearray) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    raw = b"".join(b"\x00" + bytes(rgba[y * width * 4:(y + 1) * width * 4]) for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def portray(style: dict, grid: Grid, system: dict, opts: Options) -> tuple[float, str] | None:
    """Return (zOrder, PNG data URI) for *grid*, or None if no cell is visible."""
    syms: list[list[dict]] = []
    single: list[list[float | None]] = []
    for r in range(grid.rows):
        srow, vrow = [], []
        for c in range(grid.cols):
            props = {name: band[r][c] for name, band in grid.bands.items()}
            sym = resolve(style, Context(properties=props, system=system, options=opts))
            srow.append(sym)
            vrow.append(_num(sym.get("singleChannel")))
        syms.append(srow)
        single.append(vrow)

    rgba = bytearray(grid.cols * grid.rows * 4)
    z_order, any_visible = 1.0, False
    for r in range(grid.rows):
        for c in range(grid.cols):
            sym, v = syms[r][c], single[r][c]
            if sym.get("visibility") is False:
                continue
            any_visible = True
            z_order = float(sym.get("zOrder", 1))
            color: RGB | None = None
            alpha = _num(sym.get("alphaChannel"))
            alpha = 1.0 if alpha is None else alpha
            if sym.get("colorChannels") is not None:
                color = parse_color(sym["colorChannels"], scale=_CHANNEL_SCALE[opts.color_channels_scale])
            elif sym.get("colorMap") and v is not None:
                color = map_value(sym["colorMap"], v, opts, parse_color)
                if color is None:
                    alpha = 0.0
            if sym.get("opacityMap") and v is not None:
                o = map_value(sym["opacityMap"], v, opts, float)
                alpha *= 0.0 if o is None else o
            hs = sym.get("hillShading")
            if isinstance(hs, dict) and v is not None:
                s = _shade(single, r, c, grid.cell_size, hs, opts)
                if hs.get("colorMap"):
                    color = map_value(hs["colorMap"], s, opts, parse_color)
                elif color is not None:
                    color = tuple(x * s for x in color)  # type: ignore[assignment]
                if hs.get("opacityMap"):
                    o = map_value(hs["opacityMap"], s, opts, float)
                    alpha *= 0.0 if o is None else o
            if color is None:
                continue
            g = _num(sym.get("gamma"))
            if g:
                e = g if opts.gamma == "exponent" else 1 / g
                color = tuple(max(0.0, min(1.0, x)) ** e for x in color)  # type: ignore[assignment]
            alpha *= float(sym.get("opacity", 1))
            i = (r * grid.cols + c) * 4
            rgba[i:i + 4] = bytes(round(max(0.0, min(1.0, x)) * 255) for x in (*color, alpha))
    if not any_visible:
        return None
    uri = "data:image/png;base64," + base64.b64encode(_png(grid.cols, grid.rows, rgba)).decode()
    return z_order, uri


__all__ = ["Grid", "map_value", "parse_color", "portray"]
