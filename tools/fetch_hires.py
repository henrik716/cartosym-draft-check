"""Fetch the Rondane elevation and Sentinel-2 scene at 50 m cells, for the document's figures.

Usage: uv run --no-project --with rasterio --with tifffile --with numpy python tools/fetch_hires.py

The same 45 x 30 km box, sources and processing as tools/fetch_rondane.py and tools/fetch_sentinel2.py,
at 50 m cells instead of 150 m (900 x 600 cells). The 150 m grids stay in the package as Python modules
for the browser playground; these finer grids are only used by cartosym_draft.doc_examples, so they are
written as plain files to src/cartosym_draft/data/rondane/:

- elevation-50m.i16.zz: elevation in decimetres;
- sentinel2-50m-<band>.i16.zz for B02, B03, B04, B08 (reflectance x 10 000) and SCL (scene classification);

each little-endian int16, row 0 at the north edge, zlib-compressed.

Elevation data © Kartverket, CC BY 4.0. Contains modified Copernicus Sentinel data 2024.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
import zlib
from pathlib import Path

import numpy as np
import tifffile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "cartosym_draft" / "data" / "rondane"
X0, Y0 = 205000.0, 6860500.0
COLS, ROWS, CELL = 900, 600, 50.0
WCS = "https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm-nhm-25833"
COVERAGE = "nhm_dtm_topo_25833"
FINE = 2  # 25 m cells fetched, averaged 2 x 2
# 1 September 2024: 0.03 % cloud, no snow, no no-data cells over the box. The 150 m playground grid keeps
# tools/fetch_sentinel2.py's 2 August scene, which has compact clouds over the massif.
S2_ITEM = "S2B_T32VNP_20240901T104944_L2A"


def _write(name: str, a: np.ndarray) -> None:
    path = OUT / name
    path.write_bytes(zlib.compress(a.astype("<i2").tobytes(), 9))
    print(f"{name}: {path.stat().st_size // 1024} KiB, {a.min():.0f} to {a.max():.0f}")


def elevation() -> int:
    x1, y1 = X0 + COLS * CELL, Y0 + ROWS * CELL
    url = (f"{WCS}?service=WCS&version=1.0.0&request=GetCoverage&coverage={COVERAGE}&crs=EPSG:25833"
           f"&bbox={X0:.0f},{Y0:.0f},{x1:.0f},{y1:.0f}&width={COLS * FINE}&height={ROWS * FINE}&format=GeoTIFF")
    with urllib.request.urlopen(url, timeout=600) as r:
        if r.headers.get_content_type() != "image/tiff":
            print(r.read(500).decode("utf-8", "replace"), file=sys.stderr)
            return 1
        fine = tifffile.imread(io.BytesIO(r.read())).astype(np.float64)
    if fine.shape != (ROWS * FINE, COLS * FINE) or (fine < -1000).any():
        print(f"unexpected grid {fine.shape} or no-data cells", file=sys.stderr)
        return 1
    grid = fine.reshape(ROWS, FINE, COLS, FINE).mean(axis=(1, 3))
    _write("elevation-50m.i16.zz", np.round(grid * 10))
    return 0


def sentinel2() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    import fetch_sentinel2 as s2  # the 150 m tool: same bands and offset handling
    from rasterio.enums import Resampling
    s2.COLS, s2.ROWS, s2.CELL = COLS, ROWS, CELL
    item = json.load(urllib.request.urlopen(s2.STAC + S2_ITEM, timeout=60))
    for band, key in s2.BANDS.items():
        rb = item["assets"][key]["raster:bands"][0]
        if (rb.get("scale"), rb.get("offset")) != (0.0001, -0.1):
            print(f"{band}: unexpected scale/offset {rb}", file=sys.stderr)
            return 1
        dn = s2._read(item["assets"][key]["href"], Resampling.average)
        if (dn == 0).any():
            print(f"{band}: no-data cells", file=sys.stderr)
            return 1
        _write(f"sentinel2-50m-{band}.i16.zz", np.clip(np.round(dn - 1000), 0, 32767))
    scl = s2._read(item["assets"]["scl"]["href"], Resampling.mode)
    _write("sentinel2-50m-SCL.i16.zz", scl)
    return 0


def _detail_key(bbox: tuple[float, float, float, float], cell: float) -> str:
    return f"{bbox[0]:.0f}_{bbox[1]:.0f}_{bbox[2]:.0f}_{bbox[3]:.0f}_{cell:g}m"


def detail() -> int:
    """Elevation at about one cell per screen pixel for each panel of the document's figures.

    The 50 m grid is two to twenty screen pixels per cell in the panels at 1:4 000 to 1:30 000, which makes
    the relief blurred. Each panel's box (plus two cells) is fetched from the 1 m DTM at half the cell size and
    averaged 2 x 2; written to data/rondane/detail/<x0>_<y0>_<x1>_<y1>_<cell>m.i16.zz in local metres, as
    decimetres, each row delta-coded from the previous one (it compresses three times better).
    """
    sys.path.insert(0, str(ROOT / "src"))
    from cartosym_draft import doc_examples as d
    out = OUT / "detail"
    out.mkdir(exist_ok=True)
    wanted = {}
    for ex in d.EXAMPLES + d.REQUIREMENT_EXAMPLES:
        for p in ex.panels:
            box, cell = d.detail_box(p)
            if cell is not None:
                wanted[_detail_key(box, cell)] = (box, cell)
    for stale in out.glob("*.i16.zz"):  # panels that moved
        if stale.name[:-len(".i16.zz")] not in wanted:
            stale.unlink()
            print(f"removed detail/{stale.name}")
    for key, (box, cell) in sorted(wanted.items()):
        path = out / f"{key}.i16.zz"
        if path.exists():
            continue
        cols, rows = round((box[2] - box[0]) / cell), round((box[3] - box[1]) / cell)
        x0, y0, x1, y1 = box[0] + X0, box[1] + Y0, box[2] + X0, box[3] + Y0
        url = (f"{WCS}?service=WCS&version=1.0.0&request=GetCoverage&coverage={COVERAGE}&crs=EPSG:25833"
               f"&bbox={x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}&width={cols * 2}&height={rows * 2}&format=GeoTIFF")
        with urllib.request.urlopen(url, timeout=600) as r:
            if r.headers.get_content_type() != "image/tiff":
                print(r.read(500).decode("utf-8", "replace"), file=sys.stderr)
                return 1
            fine = tifffile.imread(io.BytesIO(r.read())).astype(np.float64)
        if fine.shape != (rows * 2, cols * 2) or (fine < -1000).any():
            print(f"{key}: unexpected grid {fine.shape} or no-data cells", file=sys.stderr)
            return 1
        dm = np.round(fine.reshape(rows, 2, cols, 2).mean(axis=(1, 3)) * 10).astype(np.int32)
        delta = np.vstack([dm[:1], np.diff(dm, axis=0)])
        if np.abs(delta).max() > 32767:
            print(f"{key}: delta out of range", file=sys.stderr)
            return 1
        path.write_bytes(zlib.compress(delta.astype("<i2").tobytes(), 9))
        print(f"detail/{key}: {cols} x {rows}, {path.stat().st_size // 1024} KiB")
    return 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    steps = {"elevation": elevation, "sentinel2": sentinel2, "detail": detail}
    for name in sys.argv[1:] or list(steps):
        if steps[name]():
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
