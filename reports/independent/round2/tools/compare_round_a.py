"""Compare the round A runs with the draft renderer's readings of each pass kit.

Run with draft-check's venv python:  python compare_round_a.py <scratchpad> <run dirs...>
Writes <scratchpad>/round-a/compare/{report.md, strips/*.png, readings/*.png}.
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image, ImageDraw

from cartosym_draft.doc_examples import to_json
from cartosym_draft.passes import CASES, DRAFT, VIEW
from cartosym_draft.render import render

S = Path(sys.argv[1])
runs = [Path(p) for p in sys.argv[2:]]
mapping = json.loads((S / "private" / "round-a-mapping.json").read_text())
out = S / "round-a" / "compare"
(out / "strips").mkdir(parents=True, exist_ok=True)
(out / "readings").mkdir(parents=True, exist_ok=True)
by_key = {f"passes-{c.name}": c for c in CASES}
THRESH = 48  # a channel differing by more than this counts as a clear difference


def png(svg: str) -> Image.Image:
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert("RGB")


def diff(a: Image.Image, b: Image.Image) -> float | None:
    if a.size != b.size:
        return None
    d = np.abs(np.asarray(a, dtype=int) - np.asarray(b, dtype=int)).max(axis=2)
    return 100.0 * (d > THRESH).mean()


def fmt(x):
    return "size?" if x is None else f"{x:.1f}"


lines = ["# Round A: rendering passes", "",
         f"Share of pixels (%) that differ clearly (a channel by more than {THRESH}). "
         "Rows: our readings of the kit (the draft's, then the variants in `passes.py`). Columns: the runs.", ""]
for case, m in mapping.items():
    kit, style = m["kit"], m["style"]
    imgs = {}
    for r in runs:
        p = r / "out" / f"{case}-1.png"
        imgs[r.name] = Image.open(p).convert("RGB") if p.exists() else None
    readings = {}
    c = by_key.get(kit)
    if c is not None:
        suffix = style[len("style-"):] if style.startswith("style-") else ""
        st, _ = to_json(c.css_of(suffix))
        readings["draft"] = png(render(st, c.layers, VIEW, DRAFT))
        if not suffix:
            for v in c.variants:
                readings[v.label] = png(render(st, c.layers, VIEW, v.options))
    title = f"## {case}: {kit}" + ("" if style == "style" else f" ({style})")
    lines += [title, ""]
    names = [n for n, im in imgs.items() if im is not None]
    missing = [n for n, im in imgs.items() if im is None]
    if missing:
        lines += [f"No image from: {', '.join(missing)}", ""]
    if readings and names:
        lines += ["| reading | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for label, im in readings.items():
            lines.append(f"| {label} | " + " | ".join(fmt(diff(im, imgs[n])) for n in names) + " |")
        lines.append("")
    if len(names) > 1:
        pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
        lines += ["Between runs: " + ", ".join(f"{a}–{b} {fmt(diff(imgs[a], imgs[b]))}" for a, b in pairs), ""]
    # Strip: readings, then runs, labelled, at 2x.
    tiles = list(readings.items()) + [(n, imgs[n]) for n in names]
    if tiles:
        w, h = 600, 400
        strip = Image.new("RGB", (len(tiles) * (w + 8), h + 24), "white")
        dr = ImageDraw.Draw(strip)
        for i, (label, im) in enumerate(tiles):
            strip.paste(im.resize((w, h), Image.NEAREST), (i * (w + 8), 24))
            dr.text((i * (w + 8) + 4, 4), label[:80], fill="black")
        strip.save(out / "strips" / f"{case}.png")
    for label, im in readings.items():
        im.save(out / "readings" / f"{case}-{label.replace(' ', '_').replace('/', '_')[:40]}.png")
(out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {out / 'report.md'}")
