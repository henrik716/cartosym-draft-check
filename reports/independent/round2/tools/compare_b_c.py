"""Compare rounds B and C.  uv run --no-project --with numpy --with pillow python compare_b_c.py <scratchpad>"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

S = Path(sys.argv[1])
THRESH = 48


def diff(a, b):
    if a.size != b.size:
        return None
    d = np.abs(np.asarray(a, dtype=int) - np.asarray(b, dtype=int)).max(axis=2)
    return 100.0 * (d > THRESH).mean()


# Round B
runs = [S / f"indep-b{i}" for i in (1, 2, 3)]
mapping = json.loads((S / "private" / "round-b-mapping.json").read_text(encoding="utf-8"))
out = S / "round-b" / "compare"
(out / "strips").mkdir(parents=True, exist_ok=True)
lines = ["# Round B: the text of our open PRs", "",
         f"Share of pixels (%) that differ clearly (a channel by more than {THRESH}); ours = the draft renderer "
         "on white, without the context layers.", "",
         "| case | example | panel | ours–b1 | ours–b2 | ours–b3 | b1–b2 | b1–b3 | b2–b3 |", "|---|---|---|---|---|---|---|---|---|"]
for case, m in mapping.items():
    ours = Image.open(S / "round-b" / "ours" / f"{case}.png").convert("RGB")
    ims = []
    for r in runs:
        p = r / "out" / f"{case}-1.png"
        ims.append(Image.open(p).convert("RGB") if p.exists() else None)
    f = lambda a, b: "—" if a is None or b is None else ("size?" if diff(a, b) is None else f"{diff(a, b):.1f}")
    lines.append(f"| {case} | {m['example']} | {m['label']} | " + " | ".join(
        [f(ours, im) for im in ims] + [f(ims[0], ims[1]), f(ims[0], ims[2]), f(ims[1], ims[2])]) + " |")
    tiles = [("ours", ours)] + [(r.name, im) for r, im in zip(runs, ims) if im is not None]
    w, h = ours.size
    strip = Image.new("RGB", (len(tiles) * (w + 8), h + 20), "white")
    dr = ImageDraw.Draw(strip)
    for i, (lab, im) in enumerate(tiles):
        strip.paste(im.resize((w, h)), (i * (w + 8), 20))
        dr.text((i * (w + 8) + 4, 4), lab, fill="black")
    strip.save(out / "strips" / f"{case}.png")
(out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Round C
exp = json.loads((S / "private" / "round-c-expected.json").read_text(encoding="utf-8"))
res = {}
for i in (1, 2, 3):
    p = S / f"indep-c{i}" / "results.json"
    res[f"c{i}"] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def norm(v):
    """Comparable form: numbers rounded, errors as 'error', 'null' strings as None."""
    if isinstance(v, dict) and "error" in v and len(v) == 1:
        return "error"
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 9)
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        if set(v) == {"x", "y"}:
            return {"x": norm(v["x"]), "y": norm(v["y"])}
        return {k: norm(x) for k, x in v.items()}
    return v


def expected(e):
    """The harness writes most expectations as text: 'null', 'true', '{x: 10, y: -4}', ..."""
    v = e["expect"]
    if isinstance(v, str):
        t = v.strip()
        if t in ("null", "true", "false"):
            return {"null": None, "true": True, "false": False}[t]
        if t.startswith("{") and ":" in t:
            import re
            try:
                return json.loads(re.sub(r"([A-Za-z_]\w*)\s*:", r'"\1":', t))
            except ValueError:
                return v
        if t.startswith("error"):
            return "error"
    return v


lines = ["# Round C: expressions", "",
         "Cases where a run's result differs from the harness's expected value, or the runs differ among "
         "themselves (probes have no expected value).", "",
         "| id | expected | c1 | c2 | c3 |", "|---|---|---|---|---|"]
agree = 0
for cid, e in exp.items():
    want = None if e["expect"] is None else norm(expected(e))
    got = [norm(res[k].get(cid, "MISSING")) for k in ("c1", "c2", "c3")]
    same_runs = got[0] == got[1] == got[2]
    if (e["expect"] is not None and all(g == want for g in got)) or (e["expect"] is None and same_runs and False):
        agree += 1
        continue
    if e["expect"] is None or any(g != want for g in got):
        cell = lambda g: json.dumps(g, ensure_ascii=False)[:60]
        lines.append(f"| {cid} | {'(probe)' if e['expect'] is None else cell(want)} | " + " | ".join(cell(g) for g in got) + " |")
lines.insert(3, f"All three runs give the expected value in {agree} of {sum(1 for e in exp.values() if e['expect'] is not None)} cases.\n")
(S / "round-c" / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("ok")
