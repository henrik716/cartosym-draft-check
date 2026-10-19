"""Coverages for the gallery, shaped like the spec examples' data.

- :func:`rondane`: real elevation of Rondane, Norway, 45 x 30 km (about 290 to
  2160 m), from Kartverket's national terrain model averaged to 150 m cells, for the
  elevation cards. Elevation data © Kartverket, CC BY 4.0.
- :func:`pyramids`: three synthetic pyramids, for the direction of the light.
- :func:`sentinel2`: a real Sentinel-2 L2A scene over the same area (2 August
  2024), with integer ``B02``, ``B03``, ``B04`` and ``B08`` bands as reflectance
  x 10 000 and an ``SCL`` scene classification with a few clouds (8 = medium,
  9 = high probability), as examples 6 and 7 expect. Contains modified
  Copernicus Sentinel data 2024.
"""

from __future__ import annotations

import base64
import struct
import zlib

from . import rondane_data, sentinel2_data
from .coverage import Grid

BBOX = (0.0, 0.0, 15000.0, 10000.0)  # 15 x 10 km, so 1:178 571 at 300 px wide
COLS, ROWS = 150, 100  # 100 m cells


def _cells():
    cell = (BBOX[2] - BBOX[0]) / COLS
    for r in range(ROWS):
        y = BBOX[3] - (r + 0.5) * cell
        yield r, [(BBOX[0] + (c + 0.5) * cell, y) for c in range(COLS)]


def rondane() -> Grid:
    """Rondane, Norway: the massif and the valleys around it, 45 x 30 km at 150 m cells."""
    d = rondane_data
    raw = zlib.decompress(base64.b64decode("".join(d.DATA)))
    dm = struct.unpack(f"<{d.COLS * d.ROWS}h", raw)
    rows = [[dm[r * d.COLS + c] / 10 for c in range(d.COLS)] for r in range(d.ROWS)]
    return Grid((0.0, 0.0, d.COLS * d.CELL, d.ROWS * d.CELL), d.COLS, d.ROWS, {"elevation": rows}, name="rondane",
                origin=d.ORIGIN, attribution="Elevation data © Kartverket, CC BY 4.0")


def pyramids() -> Grid:
    """Three square pyramids: flat faces make the direction of the light easy to see."""
    peaks = [(3500, 5500, 1500), (8500, 4500, 2200), (12500, 6200, 1200)]
    rows = []
    for _, cells in _cells():
        rows.append([round(max([200.0] + [200 + h - 0.9 * (abs(x - px) + abs(y - py)) for px, py, h in peaks]), 1)
                     for x, y in cells])
    return Grid(BBOX, COLS, ROWS, {"elevation": rows}, name="pyramids")


def sentinel2() -> Grid:
    """Sentinel-2 L2A over Rondane (2 August 2024), the same 45 x 30 km as :func:`rondane`, at 150 m cells."""
    d = sentinel2_data
    n = d.COLS * d.ROWS
    bands = {}
    for name, chunks in d.BANDS.items():
        v = struct.unpack(f"<{n}h", zlib.decompress(base64.b64decode("".join(chunks))))
        bands[name] = [list(v[r * d.COLS:(r + 1) * d.COLS]) for r in range(d.ROWS)]
    return Grid((0.0, 0.0, d.COLS * d.CELL, d.ROWS * d.CELL), d.COLS, d.ROWS, bands, name="sentinel2",
                origin=d.ORIGIN, attribution="Contains modified Copernicus Sentinel data 2024")


__all__ = ["BBOX", "pyramids", "rondane", "sentinel2"]
