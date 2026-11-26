"""Build the sealed folder for round A (rendering passes) of the second independent reading.

Usage: python build_round_a.py <spec repo> <draft-check repo> <out dir> <spec commit>

Writes <out>/sealed/ (what a run sees) and <out>/mapping.json (case -> kit, kept outside).
"""
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

spec_repo, dc_repo, out, commit = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
sealed = out / "sealed"
if sealed.exists():
    shutil.rmtree(sealed)
sealed.mkdir(parents=True)

# 1. The spec text of Part 1 at <commit>, without figures or any image.
tar = subprocess.run(["git", "-C", str(spec_repo), "archive", commit, "1-core"], capture_output=True, check=True).stdout
with tarfile.open(fileobj=io.BytesIO(tar)) as t:
    members = [m for m in t.getmembers()
               if not m.name.startswith("1-core/figures")
               and not re.search(r"\.(png|jpe?g|gif|svg|tiff?|webp|pdf)$", m.name, re.I)]
    t.extractall(sealed / "spec", members=members, filter="data")

# 2. The kits, under neutral names, with the comments that state the expected result removed.
KITS = [f"passes-{n}" for n in (
    "01-nested-override", "02-toplevel-override", "03-feature-pass", "04-viz-pass", "05-casing",
    "06-rule-without-pass", "07-feature-and-viz-pass", "08-zorder", "09-center-line", "10-labels-pass",
    "11-feature-pass-minus-one", "12-shared-zorder", "13-translucent-passes", "14-xplanung")] + ["label-pass"]


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
    lines = [l.rstrip() for l in "".join(out).splitlines()]
    orig = text.splitlines()
    # Drop lines that held only a comment; keep blank lines that were blank.
    kept = [l for l, o in zip(lines, orig) if l.strip() or not o.strip()]
    return "\n".join(kept).strip("\n") + "\n"


mapping, n = {}, 0
for kit in KITS:
    src = dc_repo / "gallery" / "kit" / kit
    styles = sorted(p.name[:-len(".cs.json")] for p in src.glob("style*.cs.json"))
    styles.sort(key=lambda s: s != "style")
    for style in styles:
        n += 1
        case = f"case-{n:02d}"
        d = sealed / "cases" / case
        d.mkdir(parents=True)
        mapping[case] = {"kit": kit, "style": style}
        j = json.loads((src / f"{style}.cs.json").read_text(encoding="utf-8"))
        (d / "style.cs.json").write_text(json.dumps(strip_json(j), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if (src / f"{style}.cscss").exists():
            (d / "style.cscss").write_text(strip_css((src / f"{style}.cscss").read_text(encoding="utf-8")), encoding="utf-8")
        view = json.loads((src / "view.json").read_text(encoding="utf-8"))
        view.pop("card", None)
        (d / "view-1.json").write_text(json.dumps(view, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for g in src.glob("*.geojson"):
            shutil.copy(g, d / g.name)
        for g in src.glob("*.asc"):
            shutil.copy(g, d / g.name)
        if (src / "svg").is_dir():
            shutil.copytree(src / "svg", d / "svg")

(out / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")

# 3. Leak check: nothing in the cases should name a kit, an issue, a renderer or an expected result.
bad = re.compile(r"pycartosym|libcartosym|draft.check|draft renderer|qgis|should be drawn|#\d{3}|override|"
                 r"nested-override|feature-pass|viz-pass", re.I)
for p in (sealed / "cases").rglob("*"):
    if p.is_file() and p.suffix in (".json", ".cscss", ".geojson"):
        for m in bad.finditer(p.read_text(encoding="utf-8")):
            print(f"LEAK? {p.relative_to(sealed)}: {m.group(0)!r}")
print(f"{n} cases; spec at {commit}")
