"""Build the home page, index.html at the repository root: what the site is and where to go."""

from __future__ import annotations

import html
from pathlib import Path

from .nav import HOME, NAV_CSS, RECORDS, REPO, topbar

SPEC = "https://github.com/opengeospatial/cartographic-symbology"

HOME_CSS = """
main { max-width: 1100px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin: 22px 0; }
.tile { display: block; background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px;
  color: var(--fg); text-decoration: none; }
a.tile:hover { border-color: var(--accent); }
.tile h2 { margin: 0 0 6px; font-size: 18px; }
a.tile h2 { color: var(--accent); }
.tile p { margin: 0 0 8px; font-size: 14px; color: var(--muted); }
.tile ul { margin: 6px 0 0; padding-left: 18px; font-size: 14px; }
.tile li { margin: 3px 0; }
.standing { font-size: 14.5px; }
footer.site { margin: 40px 0 24px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 13px; color: var(--muted); }
"""


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build(css: str) -> str:
    from .gallery import REQUIREMENTS, decisions
    from .requirements_page import IMPLEMENTATIONS, agrees, load_results, provenance

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
        f'<li><a href="{html.escape(href if href.startswith("https://") else "gallery/" + href)}">{html.escape(label)}</a>: '
        f"{html.escape(desc)}</li>" for href, label, desc in RECORDS)
    n_req = len(REQUIREMENTS["requirements"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Draft Check</title>
<meta name="description" content="Checks of the requirement text of OGC Cartographic Symbology 2.0 Part 1: renders, judgement calls and test cases.">
<style>{css}{NAV_CSS}{HOME_CSS}</style></head><body>
{topbar(HOME, base="gallery/")}
<div class="layout"><main>
<h1>Checking the CartoSym 2.0 requirements</h1>
<p class="lead">A renderer, an expression evaluator and test cases that follow the requirement text of
<a href="{SPEC}">OGC Cartographic Symbology 2.0</a> Part 1 (and the Part 2 gradient fills), used to check the text while
it is being written: where it leaves a choice open, where readers draw different maps from it, and where implementations
differ from it. What they show are proposals for the Cartographic Symbology SWG, not decisions.</p>

<div class="tiles">
<a class="tile" href="gallery/requirements.html"><h2>Requirements</h2>
<p>All {n_req} requirements, recommendations and permissions, each with its text and how it is checked: a render, test
cases run through three implementations, or a note.</p></a>
<a class="tile" href="gallery/index.html"><h2>Judgement calls</h2>
<p>{len(cards)} places where the text leaves (or left) a choice, each drawn every way, with a decision matrix of
proposed resolutions and where each stands on GitHub. In {open_cards} the text still makes no choice.</p></a>
<a class="tile" href="gallery/passes.html"><h2>Rendering passes</h2>
<p>Test cases for how passes, <code>zOrder</code>, casings and nested rules decide what is drawn on top, each with a
render kit for other software.</p></a>
<a class="tile" href="gallery/playground.html"><h2>Playground</h2>
<p>Edit the style of any card or sample and see the draft renderer draw it again, in your browser.</p></a>
</div>

<section class="card standing"><h2>Where things stand</h2>
<p>The requirement text is from <code>{html.escape(REQUIREMENTS["branch"])}</code> at
<code>{html.escape(REQUIREMENTS["commit"])}</code>. {cases_line} The draft renderer implements the text itself, so its
results show that it matches the text, not that the text is right; the independent renders in the records are there
for that.</p></section>

<section class="card"><h2>Records</h2>
<p>The walkthroughs of earlier pull requests, kept as they were presented, and the full records behind the pages:</p><ul>{records}</ul></section>

<footer class="site">Made by Henrik Gulliksen Schüller, Part 1 editor, with Claude (Anthropic) as a coding assistant.
Code under the MIT licence: <a href="{REPO}">{REPO.removeprefix("https://")}</a>. Map and elevation data © Kartverket,
CC BY 4.0; contains modified Copernicus Sentinel data 2024.</footer>
</main></div></body></html>"""


def write(root: Path, css: str) -> Path:
    out = root / "index.html"
    out.write_text(build(css), encoding="utf-8")
    return out


__all__ = ["build", "write"]
