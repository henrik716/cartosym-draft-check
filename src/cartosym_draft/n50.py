"""Vector layers for Rondane from Kartverket N50, written by tools/fetch_n50.py.

The GeoJSON files in data/rondane/ are in EPSG:25833. :func:`layer` shifts them to
the local metres that :func:`sample_data.rondane` and :func:`sample_data.sentinel2`
use (origin at the south-west corner of the 45 x 30 km box), so vector and
coverage layers line up. Map data and place names © Kartverket, CC BY 4.0.
"""

from __future__ import annotations

import datetime
import json
from functools import lru_cache
from pathlib import Path

from . import rondane_data
from .render import Layer

DATA = Path(__file__).resolve().parent / "data" / "rondane"
ORIGIN = rondane_data.ORIGIN
ATTRIBUTION = "Map data © Kartverket, CC BY 4.0"
LAYERS = ("Landcover", "Rivers", "Roads", "Railways", "Huts", "Buildings", "Contours", "SpotHeights", "ProtectedAreas",
          "Municipalities", "Places")


def _shift(coords, dx: float, dy: float):
    if isinstance(coords[0], (int, float)):
        return [coords[0] - dx, coords[1] - dy]
    return [_shift(c, dx, dy) for c in coords]


@lru_cache(maxsize=None)
def _features(name: str) -> tuple[dict, ...]:
    fc = json.loads((DATA / f"{name}.geojson").read_text(encoding="utf-8"))
    out = []
    for f in fc["features"]:
        g = f["geometry"]
        props = dict(f["properties"])
        if "validDate" in props:  # GeoJSON has no date type: the layer's description says it is a date
            props["validDate"] = datetime.date.fromisoformat(props["validDate"])
        out.append({"type": "Feature", "properties": props,
                    "geometry": {"type": g["type"], "coordinates": _shift(g["coordinates"], *ORIGIN)}})
    return tuple(out)


def _inside(geom: dict, bbox) -> bool:
    def walk(c):
        if isinstance(c[0], (int, float)):
            yield c
        else:
            for x in c:
                yield from walk(x)
    xs, ys = zip(*walk(geom["coordinates"]))
    return not (max(xs) < bbox[0] or min(xs) > bbox[2] or max(ys) < bbox[1] or min(ys) > bbox[3])


def layer(name: str, bbox: tuple[float, float, float, float] | None = None, layer_id: str | None = None,
          where=None) -> Layer:
    """One N50 layer in local metres, optionally only the features touching bbox and passing where(properties)."""
    feats = [f for f in _features(name)
             if (bbox is None or _inside(f["geometry"], bbox)) and (where is None or where(f["properties"]))]
    return Layer(layer_id or name, list(feats))


__all__ = ["ATTRIBUTION", "LAYERS", "ORIGIN", "layer"]
