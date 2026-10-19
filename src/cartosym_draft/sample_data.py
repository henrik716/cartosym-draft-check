"""Coverages for the gallery, shaped like the spec examples' data.

- :func:`rondane`: real elevation of Rondane, Norway (about 1020 to 2170 m),
  from Kartverket's national terrain model averaged to 100 m cells, for the
  elevation cards. Elevation data © Kartverket, CC BY 4.0.
- :func:`pyramids`: three synthetic pyramids, for the direction of the light.
- :func:`sentinel2`: synthetic integer ``B02``, ``B03``, ``B04`` (blue, green, red) and
  ``B08`` (near infrared) bands in Sentinel-2 L2A digital numbers (reflectance
  x 10 000), and an ``SCL`` scene classification with a cloud (8 = medium,
  9 = high probability), as examples 6 and 7 expect.
"""

from __future__ import annotations

import base64
import math
import struct
import zlib

from . import rondane_data
from .coverage import Grid

BBOX = (0.0, 0.0, 15000.0, 10000.0)  # 15 x 10 km, so 1:178 571 at 300 px wide
COLS, ROWS = 150, 100  # 100 m cells


def _cells():
    cell = (BBOX[2] - BBOX[0]) / COLS
    for r in range(ROWS):
        y = BBOX[3] - (r + 0.5) * cell
        yield r, [(BBOX[0] + (c + 0.5) * cell, y) for c in range(COLS)]


def rondane() -> Grid:
    """Rondane, Norway: Rondeslottet, Storronden and Smiubelgen around Rondvatnet, at 100 m cells."""
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


# NDVI of 2 km parcels, read row by row from the north-west corner.
_PARCELS = [0.82, 0.35, 0.65, 0.12, 0.74, 0.55, 0.88, 0.25,
            0.48, 0.91, 0.18, 0.70, 0.40, 0.86, 0.60, 0.30,
            0.66, 0.22, 0.79, 0.52, 0.08, 0.68, 0.45, 0.84,
            0.33, 0.58, 0.87, 0.15, 0.62, 0.38, 0.76, 0.50,
            0.72, 0.42, 0.28, 0.81, 0.57, 0.90, 0.20, 0.64]


def sentinel2() -> Grid:
    b02, b03, b04, b08, scl = [], [], [], [], []
    for _, cells in _cells():
        r02, r03, r04, r08, rscl = [], [], [], [], []
        for x, y in cells:
            i = int(x // 2000) + 8 * int((BBOX[3] - y) // 2000)
            ndvi = _PARCELS[i % len(_PARCELS)] + 0.06 * math.sin(x / 300) * math.cos(y / 260)
            total = 4200
            water = math.hypot(x - 4200, y - 3300) < 1500 or abs(y - 7600 - 600 * math.sin(x / 1800)) < 140
            if water:
                ndvi, total = -0.45, 1300
            red, nir = total * (1 - ndvi) / 2, total * (1 + ndvi) / 2
            green, blue = (650, 900) if water else (red * (0.75 + 0.9 * ndvi), red * (0.7 + 0.2 * ndvi))
            cloud = math.hypot(x - 11200, (y - 3200) * 1.4)
            if cloud < 1900:  # bright, flat spectrum
                k = 1 - cloud / 1900
                red, green, blue, nir = (v + (7500 - v) * min(1.0, 1.6 * k) for v in (red, green, blue, nir))
            r02.append(round(blue))
            r03.append(round(green))
            r04.append(round(red))
            r08.append(round(nir))
            rscl.append(9 if cloud < 1100 else 8 if cloud < 1900 else 4)
        b02.append(r02)
        b03.append(r03)
        b04.append(r04)
        b08.append(r08)
        scl.append(rscl)
    return Grid(BBOX, COLS, ROWS, {"B02": b02, "B03": b03, "B04": b04, "B08": b08, "SCL": scl},
                name="sentinel2")


__all__ = ["BBOX", "pyramids", "rondane", "sentinel2"]
