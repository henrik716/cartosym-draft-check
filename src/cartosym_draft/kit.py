"""Export each gallery card as a render kit: style, data and view.

So that another renderer can draw exactly what a card shows. Data is placed in
ETRS89 / UTM zone 33N (EPSG:25833) by offsetting the gallery's local metre
coordinates; vector layers become GeoJSON, coverage bands ESRI ASCII grids
(readable by GDAL). Each data file is named after its layer, which is what
the styles' `dataLayer.id` selectors match.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .render import Layer, View

ORIGIN = (597000.0, 6643000.0)  # local (0, 0) in EPSG:25833, near Oslo
CRS = "EPSG:25833"
PRJ = ('PROJCS["ETRS89 / UTM zone 33N",GEOGCS["ETRS89",DATUM["European_Terrestrial_Reference_System_1989",'
       'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
       'PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",15],'
       'PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],'
       'UNIT["metre",1],AUTHORITY["EPSG","25833"]]')


def _shift(coords):
    if isinstance(coords[0], (int, float)):
        return [coords[0] + ORIGIN[0], coords[1] + ORIGIN[1], *coords[2:]]
    return [_shift(c) for c in coords]


def _geojson(layer: Layer) -> dict:
    feats = []
    for f in layer.features:
        g = dict(f["geometry"])
        g["coordinates"] = _shift(g["coordinates"])
        feats.append({**f, "geometry": g})
    return {"type": "FeatureCollection", "name": layer.id,
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25833"}}, "features": feats}


def _ascii_grid(layer: Layer, band: str) -> str:
    g = layer.grid
    assert g is not None
    head = (f"ncols {g.cols}\nnrows {g.rows}\nxllcorner {g.bbox[0] + ORIGIN[0]}\nyllcorner {g.bbox[1] + ORIGIN[1]}\n"
            f"cellsize {g.cell_size}\nNODATA_value -9999\n")
    return head + "\n".join(" ".join(str(v) for v in row) for row in g.bands[band]) + "\n"


def export(key: str, title: str, styles: dict[str, dict], layers: list[Layer], view: View,
           out_dir: Path) -> list[tuple[str, str]]:
    """Write one card's kit to out_dir/key/ and return (label, relative path) links."""
    d = out_dir / "kit" / key
    d.mkdir(parents=True, exist_ok=True)
    links = []
    for name, style in styles.items():
        (d / name).write_text(json.dumps(style, indent=2, ensure_ascii=False), encoding="utf-8")
        links.append((name, f"kit/{key}/{name}"))
    for layer in layers:
        if layer.type == "coverage" and layer.grid is not None:
            for band in layer.grid.bands:
                (d / f"{layer.id}.{band}.asc").write_text(_ascii_grid(layer, band), encoding="utf-8")
                (d / f"{layer.id}.{band}.prj").write_text(PRJ, encoding="utf-8")
                links.append((f"{layer.id}.{band}.asc", f"kit/{key}/{layer.id}.{band}.asc"))
        else:
            (d / f"{layer.id}.geojson").write_text(json.dumps(_geojson(layer), ensure_ascii=False), encoding="utf-8")
            links.append((f"{layer.id}.geojson", f"kit/{key}/{layer.id}.geojson"))
    b = view.bbox
    view_info = {
        "card": title, "crs": CRS,
        "bbox": [b[0] + ORIGIN[0], b[1] + ORIGIN[1], b[2] + ORIGIN[0], b[3] + ORIGIN[1]],
        "width": view.width, "height": view.height,
        "scaleDenominator": round(view.scale_denominator, 1),
        "pixelSize_mm": 0.28,
        "layers": [{"id": layer.id, "type": layer.type} for layer in layers],
        "note": "Render each layer with the style, at this extent and size. Coverage bands share one grid; "
                "a cell's properties are the band names (e.g. elevation, B04).",
    }
    (d / "view.json").write_text(json.dumps(view_info, indent=2, ensure_ascii=False), encoding="utf-8")
    links.append(("view.json", f"kit/{key}/view.json"))
    return links


def zip_all(out_dir: Path) -> Path:
    z = out_dir / "kit.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted((out_dir / "kit").rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(out_dir).as_posix())
    return z


__all__ = ["CRS", "ORIGIN", "export", "zip_all"]
