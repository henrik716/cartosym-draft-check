"""Build the home page, index.html at the repository root: the overview map, what the site is and where to go."""

from __future__ import annotations

import html
from pathlib import Path

from .nav import HOME, NAV_CSS, RECORDS, REPO, topbar

SPEC = "https://github.com/opengeospatial/cartographic-symbology"
G = "gallery/"  # the pages, from the root
PASS_PREVIEW = "kit/passes-12-shared-zorder/draft-render.png"
CARD_PREVIEW = "casing-crossing"  # the judgement call whose first variant the tile shows
VIGNETTE_PREVIEW = "req-hatches-angle"

HOME_CSS = """
.hero { max-width: 1320px; margin: 0 auto; padding: 28px 16px 8px; display: grid; gap: 22px 32px;
  grid-template-columns: minmax(0, 1fr); align-items: center; }
@media (min-width: 980px) { .hero { grid-template-columns: minmax(0, 3fr) minmax(300px, 2fr); padding-top: 36px; } }
.hero figure { margin: 0; }
.hero figure a { display: block; border-radius: 14px; overflow: hidden; border: 1px solid var(--line);
  box-shadow: 0 18px 50px -24px rgba(0,0,0,.45); background: #e9e6df; }
.hero img { width: 100%; height: auto; display: block; }
.hero figcaption { font-size: 12.5px; color: var(--muted); margin-top: 8px; }
.kicker { font-size: 13px; letter-spacing: .06em; text-transform: uppercase; color: var(--accent); font-weight: 600; margin: 0 0 8px; }
.hero h1 { font-size: clamp(28px, 3.4vw, 42px); line-height: 1.12; margin: 0 0 14px; letter-spacing: -.01em; }
.hero p.lead { font-size: 16.5px; max-width: 560px; margin: 0 0 18px; }
.cta { display: flex; gap: 10px; flex-wrap: wrap; }
.btn { display: inline-block; padding: 9px 16px; border-radius: 8px; background: var(--accent); color: #fff; font-weight: 600;
  text-decoration: none; font-size: 15px; }
.btn:hover { filter: brightness(1.08); }
.btn.ghost { background: transparent; color: var(--fg); border: 1px solid var(--line); }
.btn.ghost:hover { border-color: var(--accent); }
:root[data-theme="dark"] .btn:not(.ghost) { color: #1c1408; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .btn:not(.ghost) { color: #1c1408; } }
main.home { max-width: 1320px; padding-top: 12px; }
.home h2.section { font-size: 20px; margin: 34px 0 4px; }
.home p.sub { color: var(--muted); margin: 0 0 12px; font-size: 14.5px; }
.strip { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
.strip a { display: block; border-radius: 10px; overflow: hidden; border: 1px solid var(--line); background: var(--card);
  color: var(--fg); text-decoration: none; }
.strip a:hover { border-color: var(--accent); }
.strip img { width: 100%; height: auto; aspect-ratio: 3 / 2; object-fit: cover; object-position: left center;
  display: block; background: #e9e6df; }  /* left: the first panel of a figure with several */
.strip span { display: block; padding: 7px 10px 9px; font-size: 13px; line-height: 1.35; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin: 14px 0 0; }
.tile { display: flex; flex-direction: column; background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  overflow: hidden; color: var(--fg); text-decoration: none; }
a.tile:hover { border-color: var(--accent); }
.tile .pic { height: 150px; background: #e9e6df; overflow: hidden; }
.tile .pic img { width: 100%; height: 100%; object-fit: cover; object-position: left center; display: block; }
.tile pre.pic { margin: 0; padding: 14px 16px; font-size: 12.5px; line-height: 1.5; color: var(--fg); background: var(--bg);
  border-bottom: 1px solid var(--line); overflow: hidden; }
.tile .txt { padding: 14px 18px 16px; }
.tile h3 { margin: 0 0 6px; font-size: 18px; color: var(--accent); }
.tile p { margin: 0; font-size: 14px; color: var(--muted); }
.two { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0 22px; }
@media (min-width: 980px) { .two { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }
.two .card { font-size: 14.5px; }
.two ul { padding-left: 18px; margin: 6px 0 0; } .two li { margin: 4px 0; }
footer.site { margin: 34px 0 24px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 13px; color: var(--muted); }
"""

PLAYGROUND_SNIPPET = """[dataLayer.id = 'Roads'] {
  stroke: {
    color: #c0392b;
    width: 3 px;
    casing: { color: white; width: 1 px; };
  };
}"""


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _card_preview(gallery_dir: Path) -> str | None:
    """A small picture of a judgement call's first variant, written to gallery/img."""
    from .assets import svg_thumbnail
    from .gallery import IMG_DIR, decisions
    from .render import render

    d = next((d for d in decisions() if d.key == CARD_PREVIEW), None)
    if d is None:
        return None
    v = d.variants[0]
    svg = render(v.style or d.style, d.layers, d.view, v.options, anchors=d.anchors)
    return svg_thumbnail(svg, gallery_dir / IMG_DIR, IMG_DIR, width=560)


def build(css: str, gallery_dir: Path, found: dict | None) -> str:
    from .gallery import REQUIREMENTS, decisions
    from .requirements_page import IMPLEMENTATIONS, agrees, load_results, provenance
    from .showcase import HERO, HOME_STRIP, img_tag

    cards = decisions()
    open_cards = sum(1 for d in cards if not any(v.is_draft for v in d.variants))
    results = load_results()
    prov = provenance()
    differ = {impl: sum(1 for c in results.values() if impl in c["results"] and not agrees(c["results"][impl]))
              for impl in IMPLEMENTATIONS}
    ran = {impl: sum(1 for c in results.values() if impl in c["results"]) for impl in IMPLEMENTATIONS}
    if not any(differ.values()):
        cases_line = (f"On the {len(results)} expression test cases, the draft renderer ({ran['draft renderer']} cases), "
                      f"libCartoSym {html.escape(prov['libcartosym'])} ({ran['libCartoSym']}) and pycartosym "
                      f"{html.escape(prov['pycartosym'])} ({ran['pycartosym']}, converting rather than evaluating) all give "
                      f"what the text says (run on {prov['date']}).")
    else:
        cases_line = (f"On the {len(results)} expression test cases (run on {prov['date']}), "
                      + _join([f"{impl} gives something else on {k}" for impl, k in differ.items() if k])
                      + "; the requirements page shows which.")
    records = "".join(
        f'<li><a href="{html.escape(href if href.startswith("https://") else G + href)}">{html.escape(label)}</a>: '
        f"{html.escape(desc)}</li>" for href, label, desc in RECORDS)
    n_req = len(REQUIREMENTS["requirements"])

    examples = {ex.name: (ex, shown) for ex, shown, _, _ in (found or {}).get("examples", [])}
    if HERO in examples:
        ex, shown = examples[HERO]
        hero_fig = (f'<figure><a href="{G}examples.html#{HERO}">'
                    f'{img_tag(shown, ex.title, base=G, lazy=False, sizes="(min-width: 980px) 760px, 100vw")}</a>'
                    f"<figcaption>Example 11 of the Part 1 document: an overview of Rondane from N50 layers and the "
                    f"elevation model, drawn by the draft renderer from its CartoSym-CSS.</figcaption></figure>")
    else:
        hero_fig = ""
    strip = "".join(
        f'<a href="{G}examples.html#{name}"><img src="{G}{examples[name][1].small}" alt="{html.escape(examples[name][0].title)}" '
        f'loading="lazy" decoding="async" width="640" height="427"><span>{html.escape(examples[name][0].title)}</span></a>'
        for name in HOME_STRIP if name in examples)
    vignette = next((s for ex, s in (found or {}).get("vignettes", []) if s.small.endswith(f"{VIGNETTE_PREVIEW}-640.jpg")), None)
    card_pic = _card_preview(gallery_dir)
    pass_pic = (gallery_dir / PASS_PREVIEW).exists()

    def pic(src: str | None, alt: str) -> str:
        return (f'<div class="pic"><img src="{G}{src}" alt="{html.escape(alt)}" loading="lazy" decoding="async"></div>'
                if src else "")

    strip_section = (f'<h2 class="section">Examples in the standard</h2><p class="sub">Every example map in Part 1 is '
                     f'drawn by this renderer on Norwegian data. <a href="{G}examples.html">All examples →</a></p>'
                     f'<div class="strip">{strip}</div>') if strip else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Draft Check</title>
<meta name="description" content="Checks of the requirement text of OGC Cartographic Symbology 2.0 Part 1: the example maps, judgement calls and test cases.">
<style>{css}{NAV_CSS}{HOME_CSS}</style></head><body>
{topbar(HOME, base=G)}
<section class="hero">
{hero_fig}
<div>
<p class="kicker">OGC Cartographic Symbology 2.0 · Part 1</p>
<h1>Checking the CartoSym requirements by drawing them</h1>
<p class="lead">A renderer, an expression evaluator and test cases that follow the requirement text of
<a href="{SPEC}">CartoSym 2.0</a>, used to check the text while it is being written: where it leaves a choice open,
where readers draw different maps from it, and where implementations differ from it. What they show are proposals
for the SWG, not decisions.</p>
<p class="cta"><a class="btn" href="{G}examples.html">See the examples</a>
<a class="btn ghost" href="{G}requirements.html">Every requirement</a></p>
</div>
</section>
<div class="layout"><main class="home">
{strip_section}

<h2 class="section">Explore</h2>
<div class="tiles">
<a class="tile" href="{G}requirements.html">{pic(vignette.small if vignette else None, "Hatch angles, one of the requirement figures")}
<div class="txt"><h3>Requirements</h3><p>All {n_req} requirements, recommendations and permissions, each with its text
and how it is checked: a render, test cases run through three implementations, or a note.</p></div></a>
<a class="tile" href="{G}index.html">{pic(card_pic, "Casings at a road crossing, one of the judgement calls")}
<div class="txt"><h3>Judgement calls</h3><p>{len(cards)} places where the text leaves (or left) a choice, each drawn
every way, with a decision matrix of proposed resolutions. In {open_cards} the text still makes no choice.</p></div></a>
<a class="tile" href="{G}passes.html">{pic(PASS_PREVIEW if pass_pic else None, "Roads and a railway drawn in rendering passes")}
<div class="txt"><h3>Rendering passes</h3><p>Test cases for how passes, <code>zOrder</code>, casings and nested rules
decide what is drawn on top, each with a render kit for other software.</p></div></a>
<a class="tile" href="{G}playground.html"><pre class="pic">{html.escape(PLAYGROUND_SNIPPET)}</pre>
<div class="txt"><h3>Playground</h3><p>Edit the style of any card or sample and see the draft renderer draw it again,
in your browser.</p></div></a>
</div>

<div class="two">
<section class="card"><h2>Where things stand</h2>
<p>The requirement text is from <code>{html.escape(REQUIREMENTS["branch"])}</code> at
<code>{html.escape(REQUIREMENTS["commit"])}</code>. {cases_line} The draft renderer implements the text itself, so
its results show that it matches the text, not that the text is right; the independent renders in the records are
there for that.</p></section>
<section class="card"><h2>Records</h2>
<p>The walkthroughs of earlier pull requests, kept as they were presented, and the full records behind the pages:</p>
<ul>{records}</ul></section>
</div>

<footer class="site">Made by Henrik Gulliksen Schüller, Part 1 editor, with Claude (Anthropic) as a coding assistant.
Code under the MIT licence: <a href="{REPO}">{REPO.removeprefix("https://")}</a>. Map and elevation data © Kartverket,
CC BY 4.0; contains modified Copernicus Sentinel data 2024.</footer>
</main></div></body></html>"""


def write(root: Path, css: str, found: dict | None = None) -> Path:
    out = root / "index.html"
    out.write_text(build(css, root / "gallery", found), encoding="utf-8")
    return out


__all__ = ["build", "write"]
