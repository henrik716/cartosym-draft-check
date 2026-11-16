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
from functools import lru_cache
from pathlib import Path

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


_DATA = Path(__file__).resolve().parent / "data" / "rondane"


def _read_50m(name: str, cols: int = 900, rows: int = 600) -> list[list[int]]:
    raw = zlib.decompress((_DATA / name).read_bytes())
    v = struct.unpack(f"<{cols * rows}h", raw)
    return [list(v[r * cols:(r + 1) * cols]) for r in range(rows)]


@lru_cache(maxsize=1)
def rondane_50m() -> Grid:
    """The same Rondane elevation at 50 m cells (tools/fetch_hires.py), for the document's figures."""
    rows = [[v / 10 for v in row] for row in _read_50m("elevation-50m.i16.zz")]
    return Grid((0.0, 0.0, 45000.0, 30000.0), 900, 600, {"elevation": rows}, name="rondane_50m",
                origin=rondane_data.ORIGIN, attribution="Elevation data © Kartverket, CC BY 4.0")


@lru_cache(maxsize=1)
def sentinel2_50m() -> Grid:
    """A cloud-free Sentinel-2 scene (1 September 2024) at 50 m cells (tools/fetch_hires.py), for the document's figures."""
    bands = {b: _read_50m(f"sentinel2-50m-{b}.i16.zz") for b in ("B02", "B03", "B04", "B08", "SCL")}
    return Grid((0.0, 0.0, 45000.0, 30000.0), 900, 600, bands, name="sentinel2_50m",
                origin=sentinel2_data.ORIGIN, attribution="Contains modified Copernicus Sentinel data 2024")


def detail_elevation(box: tuple[float, float, float, float], cell: float) -> Grid | None:
    """Elevation of *box* at *cell* metres (tools/fetch_hires.py detail), or None when it was not fetched."""
    key = f"{box[0]:.0f}_{box[1]:.0f}_{box[2]:.0f}_{box[3]:.0f}_{cell:g}m"
    path = _DATA / "detail" / f"{key}.i16.zz"
    if not path.exists():
        return None
    cols, rows = round((box[2] - box[0]) / cell), round((box[3] - box[1]) / cell)
    delta = struct.unpack(f"<{cols * rows}h", zlib.decompress(path.read_bytes()))
    out, prev = [], [0] * cols
    for r in range(rows):  # each row is stored as its difference from the row above
        prev = [a + b for a, b in zip(prev, delta[r * cols:(r + 1) * cols])]
        out.append([v / 10 for v in prev])
    return Grid(box, cols, rows, {"elevation": out}, name=f"rondane_{cell:g}m", origin=rondane_data.ORIGIN,
                attribution="Elevation data © Kartverket, CC BY 4.0")


def crop(grid: Grid, bbox: tuple[float, float, float, float], margin: int = 2) -> Grid:
    """The cells of *grid* that cover *bbox*, plus *margin* cells on each side (for hill-shading neighbours)."""
    cs = grid.cell_size
    c0 = max(0, int((bbox[0] - grid.bbox[0]) // cs) - margin)
    c1 = min(grid.cols, int(-(-(bbox[2] - grid.bbox[0]) // cs)) + margin)
    r0 = max(0, int((grid.bbox[3] - bbox[3]) // cs) - margin)
    r1 = min(grid.rows, int(-(-(grid.bbox[3] - bbox[1]) // cs)) + margin)
    if c0 >= c1 or r0 >= r1:
        return grid
    bands = {k: [row[c0:c1] for row in v[r0:r1]] for k, v in grid.bands.items()}
    box = (grid.bbox[0] + c0 * cs, grid.bbox[3] - r1 * cs, grid.bbox[0] + c1 * cs, grid.bbox[3] - r0 * cs)
    return Grid(box, c1 - c0, r1 - r0, bands, name=grid.name, origin=grid.origin, attribution=grid.attribution)


__all__ = ["BBOX", "crop", "detail_elevation", "pyramids", "rondane", "rondane_50m", "sentinel2", "sentinel2_50m"]
