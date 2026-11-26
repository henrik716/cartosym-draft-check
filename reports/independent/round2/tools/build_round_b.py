"""Build the round B cases (the text of our open PRs): one case per panel of each example.

Run with draft-check's environment:  uv run python build_round_b.py <scratchpad> <name>...
Reads the merged spec from <scratchpad>/spec-b, writes <scratchpad>/round-b/sealed/cases,
<scratchpad>/private/round-b-mapping.json and our readings in <scratchpad>/round-b/ours/.
"""
import io
import json
import re
import shutil
import sys
from pathlib import Path

import resvg_py
from PIL import Image

import cartosym_draft.doc_examples as dx
from cartosym_draft import n50
from cartosym_draft.kit import CRS, PRJ, _ascii_grid, _geojson
from cartosym_draft.render import View, render

S = Path(sys.argv[1])
names = sys.argv[2:]
core = S / "spec-b" / "1-core"
cases_dir = S / "round-b" / "sealed" / "cases"
ours = S / "round-b" / "ours"
for d in (cases_dir, ours):
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
DRAFT = dx.DRAFT.with_(label_lines="curved")


def strip_json(v):
    if isinstance(v, dict):
        return {k: strip_json(x) for k, x in v.items() if k != "$comment"}
    if isinstance(v, list):
        return [strip_json(x) for x in v]
    return v


def strip_css(text: str) -> str:
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1]); i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i); i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2); i = n if j < 0 else j + 2
        else:
            out.append(c); i += 1
    kept = [l.rstrip() for l, o in zip("".join(out).splitlines(), text.splitlines()) if l.strip() or not o.strip()]
    return "\n".join(kept).strip("\n") + "\n"


def jsonable(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


by_name = {(e.subdir, e.name): e for e in dx.EXAMPLES + dx.REQUIREMENT_EXAMPLES}
mapping, n = {}, 0
ox, oy = n50.ORIGIN
for name in names:
    sub, _, stem = name.rpartition("/")
    ex = by_name[(sub, stem)]
    ex_dir = core / "examples" / sub if sub else core / "examples"
    css = (ex_dir / f"{stem}.cscss").read_text(encoding="utf-8")
    panels_css = ex.styles_css(css)
    views = ex.views()
    variants = ex.variants or [dx.Variant("")]
    for i, (panel_css, (p, interval), v) in enumerate(zip(panels_css, views, variants), start=1):
        n += 1
        case = f"case-{n:02d}"
        d = cases_dir / case
        d.mkdir()
        style, _ = dx.to_json(panel_css)
        (d / "style.cs.json").write_text(json.dumps(strip_json(style), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (d / "style.cscss").write_text(strip_css(panel_css), encoding="utf-8")
        layers = dx._layers(ex.layers, p)
        for layer in layers:
            if layer.grid is not None:
                for band in layer.grid.bands:
                    (d / f"{layer.id}.{band}.asc").write_text(_ascii_grid(layer, band, n50.ORIGIN), encoding="utf-8")
                    (d / f"{layer.id}.{band}.prj").write_text(PRJ, encoding="utf-8")
            else:
                fc = _geojson(layer, n50.ORIGIN)
                for f in fc["features"]:
                    f["properties"] = jsonable(f["properties"])
                (d / f"{layer.id}.geojson").write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
        for icons in (ex_dir / "icons", ex_dir.parent / "icons"):
            if icons.exists() and "icons/" in panel_css:
                shutil.copytree(icons, d / "icons")
                break
        b = p.bbox
        system = {"viz.date": dx.VIEW_DATE, "viz.timeInterval.start.date": interval[0],
                  "viz.timeInterval.end.date": interval[1], **v.system}
        view = {"crs": CRS, "bbox": [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], "width": p.width,
                "height": p.height, "scaleDenominator": round(p.scale, 1), "pixelSize_mm": dx.MM_PER_PX,
                "layers": ex.layers, "background": "white",
                "visualization": {"date": dx.VIEW_DATE.isoformat(),
                                  "timeInterval": {"start": interval[0].isoformat(), "end": interval[1].isoformat()}}}
        if v.system:
            view["systemIdentifiers"] = jsonable(v.system)
        if v.variables:
            view["variables"] = jsonable(v.variables)
        (d / "view-1.json").write_text(json.dumps(view, indent=2) + "\n", encoding="utf-8")
        # Our reading, at 1x, on white (no context layers).
        local = dx._local_images(style, ex_dir)
        svg = render(local, layers, View(b, p.width, p.height, background="#ffffff", system=system,
                                         variables=v.variables), DRAFT)
        Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert("RGB").save(ours / f"{case}.png")
        mapping[case] = {"example": name, "panel": i, "label": v.label}
        print(case, name, i, v.label)

(S / "private").mkdir(exist_ok=True)
(S / "private" / "round-b-mapping.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{n} cases")
