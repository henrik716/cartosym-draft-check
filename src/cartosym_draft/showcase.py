"""Build gallery/examples.html: the renders this tool made for the Part 1 document, and the gallery maps.

The examples and requirement figures are read from the spec repository at a git ref (`origin/main` by default),
with `git show`, so the page does not depend on which branch the spec checkout has checked out. Web-sized copies
go to gallery/showcase/; the originals stay in the spec repository, which the page links at that commit.
Examples that are not at the ref yet (such as 12 and 13 while #233 is open) are left out.
"""

from __future__ import annotations

import html
import io
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .doc_examples import EXAMPLES, GALLERY_EXAMPLES, REQUIREMENT_EXAMPLES, DocExample
from .nav import NAV_CSS, NAV_SCRIPT, permalink, toc, topbar

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT.parent / "cartographic-symbology"
REF = "origin/main"
SHOW_DIR = "showcase"  # in gallery/
SPEC_REPO = "https://github.com/opengeospatial/cartographic-symbology"
# Requirement figures shown on the page (the document has one under each requirement a map can show).
VIGNETTES = ["hatches-angle", "hill-shading-sun", "casing-center", "dashes-dash-pattern", "font-outlines-size",
             "coverage-color-channels", "stipples-ratio", "labels-placement-priority"]
# Shown on the home page under the overview.
HOME_STRIP = ["3-vector-line", "6-coverage-sentinel2", "7-coverage-ndvi", "8-coverage-hillshading", "10-protected-areas",
              "5-coverage-dem"]
HERO = "11-rondane-overview"

EXTRA_CSS = """
.example { background: var(--card); border: 1px solid var(--line); border-radius: 12px; margin: 26px 0; overflow: hidden;
  display: grid; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 1100px) {
  .example { grid-template-columns: minmax(0, 1.75fr) minmax(320px, 1fr); }
  .example pre { max-height: 440px; }
}
.example > a.fig { display: block; background: #e9e6df; align-self: start; }
.example img { width: 100%; height: auto; display: block; }
.example .body { padding: 16px 20px 18px; }
.example h2 { font-size: 20px; margin: 0 0 4px; }
.example .num { color: var(--accent); font-weight: 600; margin-right: 6px; }
.meta { font-size: 13px; color: var(--muted); margin: 6px 0 0; }
.meta a { color: inherit; }
.example details { margin-top: 10px; }
.example details summary { cursor: pointer; font-size: 14px; }
.example pre { font-size: 12px; max-height: 360px; overflow-y: auto; background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px;
  overflow-x: auto; margin: 8px 0 0; }
.thumbs { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin: 14px 0 8px; }
.thumbs a { display: block; background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden;
  color: var(--fg); text-decoration: none; }
.thumbs a:hover { border-color: var(--accent); }
.thumbs img { width: 100%; height: auto; display: block; background: #e9e6df; }
.thumbs span { display: block; padding: 8px 12px 10px; font-size: 13.5px; line-height: 1.4; }
.thumbs small { display: block; color: var(--muted); font-size: 12px; margin-top: 2px; }
.section-head { margin-top: 40px; }
"""


@dataclass
class Shown:
    """An image on the page: its web copies (paths relative to gallery/) and its size."""
    large: str
    small: str
    width: int
    height: int


def _git(spec: Path, *args: str, binary: bool = False):
    r = subprocess.run(["git", "-C", str(spec), *args], capture_output=True, check=False)
    if r.returncode:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8")


def _save(im: Image.Image, path: Path, width: int) -> tuple[int, int]:
    """A progressive JPEG of *im*, at most *width* wide; written only when its bytes change."""
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    data = buf.getvalue()
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    return im.size


def web_copies(data: bytes, stem: str, out_dir: Path, large: int = 1600, small: int = 640) -> Shown:
    show = out_dir / SHOW_DIR
    show.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(data))
    w, h = _save(im, show / f"{stem}-{large}.jpg", large)
    _save(im, show / f"{stem}-{small}.jpg", small)
    return Shown(f"{SHOW_DIR}/{stem}-{large}.jpg", f"{SHOW_DIR}/{stem}-{small}.jpg", w, h)


def img_tag(s: Shown, alt: str, base: str = "", lazy: bool = True, sizes: str = "(min-width: 1100px) 1000px, 100vw") -> str:
    lazy_attr = ' loading="lazy"' if lazy else ' fetchpriority="high"'
    return (f'<img src="{base}{s.large}" srcset="{base}{s.small} 640w, {base}{s.large} {s.width}w" sizes="{sizes}" '
            f'width="{s.width}" height="{s.height}" alt="{html.escape(alt)}"{lazy_attr} decoding="async">')


def _number(ex: DocExample) -> str:
    m = re.match(r"(\d+)-", ex.name)
    return m.group(1) if m else ""


def collect(out_dir: Path, spec: Path = SPEC, ref: str = REF) -> dict | None:
    """Read the examples at *ref* and write their web copies. None if the spec repository or the ref is missing."""
    commit = _git(spec, "rev-parse", "--short", ref)
    if not commit:
        return None
    commit = commit.strip()
    examples = []
    for ex in EXAMPLES:
        jpg = _git(spec, "show", f"{ref}:1-core/figures/examples/{ex.name}.jpg", binary=True)
        css = _git(spec, "show", f"{ref}:1-core/examples/{ex.name}.cscss")
        if jpg is None or css is None:
            continue
        has_json = _git(spec, "cat-file", "-e", f"{ref}:1-core/examples/{ex.name}.cs.json") is not None
        examples.append((ex, web_copies(jpg, ex.name, out_dir), css, has_json))
    vignettes = []
    by_name = {ex.name: ex for ex in REQUIREMENT_EXAMPLES}
    for name in VIGNETTES:
        jpg = _git(spec, "show", f"{ref}:1-core/figures/examples/requirements/{name}.jpg", binary=True)
        if jpg is not None and name in by_name:
            vignettes.append((by_name[name], web_copies(jpg, f"req-{name}", out_dir, large=1200)))
    maps = []
    for ex in GALLERY_EXAMPLES:
        jpg = out_dir / "maps" / f"{ex.name}.jpg"
        if jpg.exists():
            maps.append((ex, web_copies(jpg.read_bytes(), f"map-{ex.name}", out_dir, large=640)))
    return {"commit": commit, "ref": ref, "examples": examples, "vignettes": vignettes, "maps": maps}


def build(found: dict) -> str:
    blob = f"{SPEC_REPO}/blob/{found['commit']}/1-core"
    contents: list[tuple[str | None, str, bool]] = [(None, "In the standard", False)]
    sections = []
    for i, (ex, shown, css, has_json) in enumerate(found["examples"]):
        n = _number(ex)
        contents.append((ex.name, f"{n}. {ex.title}" if n else ex.title, False))
        links = [f'<a href="{blob}/examples/{ex.name}.cscss">{ex.name}.cscss</a>']
        if has_json:
            links.append(f'<a href="{blob}/examples/{ex.name}.cs.json">{ex.name}.cs.json</a>')
        links.append(f'<a href="{blob}/figures/examples/{ex.name}.jpg">full-size figure</a>')
        notes = "".join(f'<p class="meta">{html.escape(note)}</p>' for note in ex.notes)
        sections.append(
            f'<section class="example" id="{ex.name}"><a class="fig" href="{blob}/figures/examples/{ex.name}.jpg">'
            f'{img_tag(shown, ex.title, lazy=i > 0, sizes="(min-width: 1100px) 800px, 100vw")}</a><div class="body">'
            f'<h2>{f"<span class=num>Example {n}</span>" if n else ""}{html.escape(ex.title)}{permalink(ex.name)}</h2>'
            f'{notes}<p class="meta">{" · ".join(links)}</p>'
            f'<details open><summary>The style, in CartoSym-CSS</summary><pre>{html.escape(css.rstrip())}</pre></details>'
            f"</div></section>")
    vig = "".join(
        f'<a href="requirements.html#r{ex.requirements[0].replace("/", "-")}">'
        f'{img_tag(s, ex.title, sizes="(min-width: 800px) 33vw, 100vw")}'
        f'<span>{html.escape(ex.title)}<small>{html.escape(", ".join(ex.requirements))} · panels vary '
        f'{html.escape(ex.varies.replace("`", ""))}</small></span></a>'
        for ex, s in found["vignettes"])
    maps = "".join(
        f'<a href="maps/index.html#{ex.name}"><img src="{s.small}" width="{s.width}" height="{s.height}" '
        f'alt="{html.escape(ex.title)}" loading="lazy" decoding="async"><span>{html.escape(ex.title)}</span></a>'
        for ex, s in found["maps"])
    contents += [("vignettes", "Requirement figures", False), ("gallery-maps", "Gallery maps", False)]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Examples</title>
<meta name="description" content="The example maps of OGC CartoSym 2.0 Part 1, drawn on Norwegian data by the draft renderer.">
<style>{_css()}{NAV_CSS}{EXTRA_CSS}</style></head><body class="has-toc">
{topbar("examples.html", [(a, label) for a, label, _ in contents if a])}
<div class="layout has-toc">{toc(contents)}<main>
<h1>Examples</h1>
<p class="lead">The example maps of OGC Cartographic Symbology 2.0 Part 1, as they are in the document: each drawn by
the draft renderer from the CartoSym-CSS below it, on real data of Rondane, Norway (Kartverket N50 Kartdata and the
national elevation model, and Copernicus Sentinel-2). Land cover, relief and rivers drawn as context are not part of the
style; the figure captions in the document say where. From the spec at <code>{html.escape(found["ref"])}</code>
<a href="{SPEC_REPO}/tree/{found["commit"]}"><code>{found["commit"]}</code></a>.</p>
{"".join(sections)}
<h2 class="section-head" id="vignettes">Requirement figures{permalink("vignettes")}</h2>
<p class="lead">Under each requirement a map can show, the document has a row of small panels that change one value of the
style. A few of them; each links to its requirement.</p>
<div class="thumbs">{vig}</div>
<h2 class="section-head" id="gallery-maps">Gallery maps{permalink("gallery-maps")}</h2>
<p class="lead">Fuller maps that combine a requirement with land cover, relief and rivers. They were the requirement
figures of #192 until the panels above replaced them, and are kept here, not in the document.</p>
<div class="thumbs">{maps}</div>
<p class="meta">Map data © Kartverket, CC BY 4.0; contains modified Copernicus Sentinel data 2024.</p>
</main></div>{NAV_SCRIPT}</body></html>"""


def _css() -> str:
    from .gallery import CSS
    return CSS


def write(out_dir: Path, spec: Path = SPEC, ref: str = REF) -> dict | None:
    """Write gallery/examples.html and the web copies; returns what was found (the home page uses it), or None."""
    found = collect(out_dir, spec, ref)
    if found is None:
        print(f"Examples page skipped: no {ref} in {spec}")
        return None
    (out_dir / "examples.html").write_text(build(found), encoding="utf-8")
    return found


__all__ = ["HERO", "HOME_STRIP", "img_tag", "write"]
