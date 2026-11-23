"""Build the walkthrough of the renders PR: the examples, how the wording was checked, and each change.

Usage: python tools/build_renders_walkthrough.py [--spec ../cartographic-symbology] [--artifact PATH]

Writes gallery/pr192-renders-walkthrough.html (a full HTML document, for GitHub Pages; the old name
gallery/renders-walkthrough.html redirects to it) and, with --artifact,
the same page without the document wrapper, for publishing as an Artifact. Images are embedded as JPEG.
The record behind it is reports/wording-decisions.md and reports/independent/.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "independent"
REPO = "https://github.com/henrik716/cartosym-draft-check/blob/main"

BEFORE = ["1 Opus", "2 Opus", "3 Sonnet", "4 Opus", "5 Sonnet", "6 Haiku"]
AFTER = ["v1 Opus", "v2 Sonnet", "v3 Haiku"]

# status: "proposal" (the SWG confirms), "fix" (a contradiction fixed, no decision), "ours" (our own tools)
DECISIONS = [
    dict(id="W1", group="Graphics", title="Which way +y in a Graphic position points", req="/req/vector/graphics",
         status="proposal",
         before="a uom-qualified 2D real position offsetting the graphic from its original position",
         after="a positive x of the position as an offset to the right and a positive y as an offset upwards on the "
               "map, as for Displacement in SE 1.1",
         readers=["up", "up", "down", "up", "down", "up"], agree="up", verify=["up", "up", "up"],
         evidence="SE 1.1 Displacement, which Annex B now maps a position to, displaces above and to the right. "
                  "The document's own examples were written with y up. Both Sonnet runs read y as down until the "
                  "sentence was added.",
         ask="Confirm y up, as in SE.", panels=["vector-text-1"]),
    dict(id="W2", group="Graphics", title="Image hotSpot: origin, axes and a number without a unit",
         req="/req/vector/image", status="proposal",
         before="an optional uom-qualified hotSpot position within the image (default { 0.5, 0.5 }); clause 17: "
                "a number without a unit is in pixels for screen-space objects",
         after="in the coordinates of the image, from its top left corner with x to the right and y downwards, where "
               "a number without a unit is a fraction of the image's width or height, a value in pc is a percentage",
         readers=["pixels", "fraction", "fraction", "fraction", "fraction", "fraction"], agree="fraction",
         verify=["fraction", "fraction", "fraction"],
         evidence="The default { 0.5, 0.5 } is a fraction, as is SE AnchorPoint. Every reader assumed image "
                  "coordinates (top left, y down); SE measures AnchorPointY from the bottom, so a NOTE gives the "
                  "mapping.",
         ask="Confirm image coordinates, or measure from the lower left as SE does.", panels=["vector-image-1"]),
    dict(id="W3", group="Graphics", title="What text alignment means, and its default", req="/req/vector/text",
         status="proposal", before="the alignment values are listed, not what they mean or the default",
         after="left puts the start of the text at the position, right its end, top the top of the font's ascent, "
               "bottom the bottom of its descent, middle halfway; the default is center middle",
         readers=["as proposed"] * 6, agree="as proposed", verify=["as proposed"] * 3,
         evidence="All readers already chose this; written down so the next one does too.", ask=None,
         panels=["vector-text-1"]),
    dict(id="W4", group="Graphics", title="A Dot with a size of 0 or less", req="/req/vector/dot", status="proposal",
         before="not stated (the core-parameters case computes negative sizes)", after="nothing is drawn",
         readers=["nothing"] * 6, agree="nothing", verify=["nothing"] * 3,
         evidence="Unanimous.", ask=None, panels=["core-parameters-1"]),
    dict(id="W5", group="Strokes", title="dashOffset", req="/req/dashes/dash-offset", status="proposal",
         before="dashing vector geometry based on a dashOffset property; the figure caption: a dash pattern preceded "
                "by an offset",
         after="the distance into the dash pattern at which dashing starts at the beginning of each line (as "
               "stroke-dashoffset in SVG and SE 1.1), with a worked example: [8, 4] and 4 start with a 4 px dash",
         readers=["into", "leading gap", "into", "into", "into", "into"], agree="into",
         verify=["into", "into", "into"],
         evidence="SE 1.1 and SVG stroke-dashoffset. The figure starts with a gap, which both readings can draw.",
         ask="Confirm the SE/SVG meaning.", panels=["dashes-1"]),
    dict(id="W6", group="Strokes", title="Centre lines after all main strokes", req="/req/casing/center",
         status="proposal", before="on top of the main stroke",
         after="the center lines of all features with the same zOrder on top of the main strokes of all those features",
         readers=["per feature", "after all", "per feature", "after all", "after all", "after all"],
         agree="after all", verify=["after all"] * 3,
         evidence="Drawn per feature, a later road's main stroke cuts an earlier road's centre line at a junction; "
                  "casings are already drawn together for the same reason.", ask="Confirm.", panels=["casing-1"]),
    dict(id="W7", group="Labels", title="Label repetitions, and labels at the map edge",
         req="/req/labels/placement, /rec/labels/overlap", status="proposal",
         before="the distance between repetitions of that label is at least minSpacing; nothing about the edge",
         after="repetitions are all labels with the same content from the same data layer, measured between their "
               "positions on the map; a Renderer SHOULD omit labels that would extend beyond the edges of the map, "
               "except for maps drawn in tiles",
         readers=["same text, kept", "same text, dropped", "same text, kept", "same text, kept",
                  "per feature, kept", "per feature, kept"], agree="same text, dropped",
         verify=["same text, dropped"] * 3,
         evidence="A road is split into many features; per-feature spacing repeats its number at every split. On the "
                  "edge, five of six readers clipped labels: we propose omitting them (a cut name cannot be read), "
                  "as a SHOULD with an exception for tiles.",
         ask="Confirm omitting labels at the edge, which goes against most readers' first choice.",
         panels=["labels-spacing-1", "labels-priority-1"]),
    dict(id="W11", group="Labels", title="Font outline size in pixels", req="/req/font-outlines/size",
         status="proposal", before="by the thickness specified by the size property (no unit)",
         after="by the thickness specified by the size property, in pixels",
         readers=["pixels", "pixels", "pixels", "pixels", "pixels", "points"], agree="pixels",
         verify=["pixels"] * 3, evidence="Haiku read points, the unit of the font size.", ask=None,
         panels=["font-outlines-1"]),
    dict(id="W8", group="Fills", title="Hatches: colour, angle, distance and phase", req="/req/hatches/*",
         status="proposal",
         before="no colour in the Hatch class; angle: Hatches orientation clockwise degree (with a TODO saying it "
                "should probably be counter-clockwise, #146); no phase",
         after="lines in the Fill's color and opacity, nothing between them; 0 gives horizontal lines and angles "
               "turn counter-clockwise as seen on the map; distance between the centres of the lines; one pattern "
               "for the map with a line through its top left corner",
         readers=["clockwise"] * 6, agree="counter-clockwise", verify=["counter-clockwise"] * 3,
         evidence="All six readers followed the table's clockwise; they had no figures. The document's figure of "
                  "the default 45 degree hatch rises to the right, which is counter-clockwise, as for gradients.",
         ask="Confirm counter-clockwise, following the figure (#146).", panels=["hatches-1"]),
    dict(id="W9", group="Fills", title="Dot pattern dots", req="/req/dot-patterns/dotpattern", status="proposal",
         before="size and colour of the points not given (#84)",
         after="filled circles 2 pixels across in the Fill's color and opacity, on one grid aligned with the map, "
               "the first point half a step from its top left corner",
         readers=["2 px", "2 px", "2 px", "2 px", "2 px, at corner", "2 px, at corner"], agree="2 px",
         verify=["2 px"] * 3, evidence="Every reader chose 2 px; two put the first point at the corner.",
         ask="Confirm the 2 px (#84).", panels=["stipples-dot-patterns-1"]),
    dict(id="W10", group="Fills", title="Stipples", req="/req/stipples/ratio", status="proposal",
         before="Ratio of stippling dots according to area filled (#84)",
         after="dots in the Fill's color and opacity, placed at random so that they cover the ratio fraction of the "
               "area; a NOTE leaves dot size and placement to the Renderer",
         readers=["random", "random", "grid", "random", "grid", "grid"], agree="random",
         verify=["random"] * 3,
         evidence="The document's figure shows random dots, with the ratio as the share of the area covered. Two "
                  "Renderers will never draw the same random dots, so the NOTE says only the share is defined.",
         ask="Confirm, and decide the dot size (#84).", panels=["stipples-dot-patterns-1"]),
    dict(id="W12", group="Coverage", title="Coverage cells and map pixels", req="/req/coverage/single-channel",
         status="proposal", before="portraying each coverage cell",
         after="each cell over its whole area: a pixel whose center lies in a cell takes that cell's color and opacity",
         readers=["bilinear", "bilinear", "nearest", "nearest", "nearest", "nearest"], agree="nearest",
         verify=["nearest"] * 3, evidence="Smoothing between cells is a common display choice, but not what "
                                          "\"portraying each cell\" says.",
         ask="Is a permission to interpolate between cells wanted?", panels=["coverage-opacity-map-1"]),
    dict(id="W13", group="Coverage", title="Which samples hill shading differentiates",
         req="/req/hill-shading/hill-shading", status="proposal",
         before="differences in elevation between neighbouring samples of the elevation coverage at the resolution "
                "being rendered",
         after="the cells where a map pixel covers no more ground than a cell, the coverage resampled to the map's "
               "pixels where it covers more; central differences, repeating the edge sample",
         readers=["pixels", "pixels", "cells", "pixels", "pixels", "cells"], agree="cells",
         verify=["cells", "cells", "misread"],
         evidence="Differencing interpolated values at pixels finer than the cells gives faceted relief, which four "
                  "readers noted themselves. A first rewording (\"where the map's resolution is coarser\") was "
                  "misread by Haiku, so it now compares ground sizes.",
         ask="Jérôme: is this what \"at the resolution being rendered\" meant? It is our reading.",
         panels=["hill-shading-sun-1", "font-outlines-1"]),
    dict(id="W16", group="Coverage", title="North for the sun's azimuth", req="/req/hill-shading/sun",
         status="proposal", before="in degrees clockwise from North, as a compass bearing",
         after="where North is up on the map, the grid north of its coordinate reference system",
         readers=["grid"] * 6, agree="grid", verify=["grid"] * 3,
         evidence="Found by a verification run: grid and true north differ by about 4.5 degrees at Rondane in UTM "
                  "zone 33, enough to change the shading.", ask=None, panels=["hill-shading-sun-1"]),
    dict(id="W14", group="Core", title="Opacity applied together, per feature", req="/rec/core/opacity-together",
         status="proposal", before="to the fill, the stroke and the graphics of markers together",
         after="... of each feature together, so that they do not show through each other; different features still "
               "show through each other",
         readers=["per feature"] * 6, agree="per feature", verify=["per feature"] * 3, evidence="Unanimous.",
         ask=None, panels=["core-opacity-1"]),
    dict(id="W15", group="Core", title="Features that no rule selects", req="/req/core/symbolizer", status="proposal",
         before="only a NOTE: so that every feature is visible by default",
         after="a requirement part: features and coverage cells that no StylingRule selects are portrayed with the "
               "default values, so a style hides data only by setting visibility to false",
         readers=["drawn", "drawn", "drawn", "drawn", "drawn", "not drawn"], agree="drawn", verify=["drawn"] * 3,
         evidence="Example 11 starts with { visibility: false; }, which is only needed if unselected features are "
                  "drawn. Note that the default Marker, a white Dot without an outline, cannot be seen on white "
                  "(run 4).",
         ask="Confirm, and look at whether the default Dot should be visible on white.", panels=["core-opacity-1"]),
    dict(id="W17", group="Annex B", title="Marker position maps to Displacement", req="Annex B",
         status="fix", before="Marker position: <AnchorPoint> inside <PointSymbolizer> (the same as the hotSpot row)",
         after="Marker position: <Displacement> inside <Graphic> (SE 1.1), or inside <PointPlacement> for labels "
               "(SE 1.1 and SLD 1.0)",
         readers=None, verify=None,
         evidence="Found by a verification run: the old row contradicted W1 and the annex's own SE example, which "
                  "uses Displacement.", ask="Maxime: please check the row.", panels=[]),
    dict(id="X1", group="Expressions", title="max with three arguments: the harness was wrong",
         req="/req/math/max, /req/functions/call-expressions", status="ours",
         before="harness case max(1, 5, 3) expected 5", after="max takes two arguments, so three give NULL; the "
                                                              "harness and the draft renderer were changed, not the text",
         readers=["NULL", "NULL", "NULL"], agree="NULL", verify=None, reader_labels=["e1 Opus", "e2 Sonnet", "e3 Haiku"],
         evidence="All three independent evaluators followed the text.", ask=None, panels=[]),
    dict(id="X2", group="Expressions", title="like and an escape character", req="/req/text-relation/like",
         status="proposal", before="% and _ are defined, no escape character",
         after="a backslash in the pattern makes the character after it match only itself",
         readers=["no escape", "no escape", "no escape"], agree="escape", verify=None,
         reader_labels=["e1 Opus", "e2 Sonnet", "e3 Haiku"],
         evidence="All three evaluators read the backslash as an ordinary character; libCartoSym escapes with it. "
                  "CQL2 Requirement 5, part K, makes the backslash the escape character, as the new text does; "
                  "this is #181.",
         ask="Confirm, closing #181: the backslash is written once in a CartoSym-CSS string, so '50\\%' "
             "matches the text 50%.", panels=[]),
]

STATUS = {"proposal": "Proposal for the SWG", "fix": "Fix, to check", "ours": "Our tools, no text change"}

# Jérôme's replies on #192 (16 and 17 November 2026), and on #100, #193, #194 and #195 where they bear on a change.
# kind: "agrees" (the change stands), "differs" (his answer differs from the change), "open" (neither, yet).
# These are one member's answers, not SWG decisions.
ANSWERS_ON = "16–17 November 2026"
ANSWERS = {
    "W1": ("differs", ("In screen space, a positive y was intended to point down.")),
    "W2": ("differs", ("Origin top left, as proposed, but a number without a unit is in pixels, as for everything "
                      "else: 50 pc 50 pc is the centre and 0 0 the top left corner. The pixels are those of the "
                      "image file (#100).")),
    "W3": ("differs", ("The meaning is right (top is the top of the font's ascent), but the default was meant to be "
                      "top left; a baseline alignment may be added (#195).")),
    "W4": ("agrees", ("A Dot of size 0 draws nothing.")),
    "W5": ("agrees", ("Yes, restarting at each line; [5, 2] is a 5 pixel dash and a 2 pixel gap from the start of "
                     "the line.")),
    "W6": ("agrees", ("Centre lines after all main strokes of the same zOrder: correct.")),
    "W7": ("differs", ("Whether labels that cross the edge of the map are placed should be a Renderer option, not "
                      "required either way (static maps, dynamic maps, tiles), perhaps with a NOTE saying so.")),
    "W8": ("agrees", ("Counter-clockwise sounds right.")),
    "W9": ("open", ("Not settled: he would expect dot patterns to be perhaps more random, and asks whether both "
                   "stipples and dot patterns are needed (#84).")),
    "W10": ("open", ("Not settled: he would expect a stipple to be a regular bitmap pattern, for example 8 × 8 (#84).")),
    "W11": ("agrees", ("Pixels unless another unit is given. Still to decide: whether a font size without a unit is "
                      "in points or pixels.")),
    "W12": ("differs", ("Do not prescribe one mechanism (coverages may be draped on 3D terrain, or drawn from several "
                       "levels of detail). Interpolation is allowed, but only for continuous variables, as the "
                       "logical schema says; where nothing says, CartoSym need not require a behaviour.")),
    "W13": ("agrees", ("Essentially yes, but the wording should leave room.")),
    "W14": ("open", ("Per-feature group opacity may be very costly for many features; the recommendation might be "
                    "left open, or noted as still under consideration.")),
    "W15": ("agrees", ("Correct. He suggests a permission in Part 1 to draw a hairline outline, so that the white "
                      "default Dot shows on white.")),
    "W16": ("open", ("It needs room for global data and globes; \"north as shown on the map at the shaded point\" "
                    "might work. Defaults suggested on #194: azimuth 315, elevation 45.")),
    "X1": ("differs", ("min and max should take any number of arguments (added to libCartoSym); even one may make "
                      "sense.")),
    "X2": ("agrees", "Yes, '50\\%' matches the text 50% (also on #181)."),
}
ANSWER_LABEL = {"agrees": "Agrees", "differs": "Differs", "open": "Open"}


def jpeg(path: Path, width: int) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def esc(s) -> str:
    return html.escape(str(s))


SPEC_REPO = "https://github.com/opengeospatial/cartographic-symbology"
SPEC_PRS = {188, 192, 196}
PYCS = "https://github.com/maxcollombin/pycartosym/issues"
ISSUE_REF = re.compile(r"(?<![\w&/])#(\d{2,3})\b")


def link_issues(body: str) -> str:
    """Link each bare #NNN in the page text to the spec repo; tags and text already inside <a> are left alone."""
    out, in_a = [], 0
    for part in re.split(r"(<[^>]*>)", body):
        if part.startswith("<"):
            if re.match(r"<a[\s>]", part):
                in_a += 1
            elif re.match(r"</a\s*>", part):
                in_a -= 1
            out.append(part)
        elif in_a:
            out.append(part)
        else:
            out.append(ISSUE_REF.sub(
                lambda m: f'<a href="{SPEC_REPO}/{"pull" if int(m[1]) in SPEC_PRS else "issues"}/{m[1]}">#{m[1]}</a>',
                part))
    return "".join(out)


def chips(labels, values, agree) -> str:
    out = []
    for lab, val in zip(labels, values):
        cls = "chip ok" if val == agree else "chip off"
        out.append(f'<span class="{cls}"><b>{esc(lab)}</b> {esc(val)}</span>')
    return "".join(out)


def card(d: dict) -> str:
    rows = []
    if d.get("readers"):
        labels = d.get("reader_labels") or BEFORE
        rows.append(f'<div class="readers"><span class="rl">Old text</span>{chips(labels, d["readers"], d["agree"])}</div>')
    if d.get("verify"):
        rows.append(f'<div class="readers"><span class="rl">New text</span>{chips(AFTER, d["verify"], d["agree"])}</div>')
    figs = []
    for p in d["panels"]:
        b, a = REPORTS / "strips" / f"{p}.png", REPORTS / "verify-strips" / f"{p}.png"
        figs.append(f'<figure><figcaption>{esc(p)}: the six runs on the old text</figcaption>'
                    f'<div class="strip"><img loading="lazy" alt="{esc(p)} rendered by six runs on the old text" '
                    f'src="{jpeg(b, 1824)}"></div></figure>')
        figs.append(f'<figure><figcaption>{esc(p)}: the draft renderer and three runs on the new text</figcaption>'
                    f'<div class="strip"><img loading="lazy" alt="{esc(p)} rendered on the new text" '
                    f'src="{jpeg(a, 1216)}"></div></figure>')
    ask = f'<p class="ask"><b>Asked:</b> {esc(d["ask"])}</p>' if d.get("ask") else ""
    if d["id"] in ANSWERS:
        kind, text = ANSWERS[d["id"]]
        ask += (f'<p class="answer {kind}"><b>Jérôme on #192, {ANSWERS_ON}</b> '
                f'<span class="akind">{ANSWER_LABEL[kind]}</span> {esc(text)}</p>')
    return f"""<article class="card {d['status']}" id="{d['id']}">
<header><span class="cid">{d['id']}</span><h3>{esc(d['title'])}</h3><span class="status">{STATUS[d['status']]}</span></header>
<p class="req">{esc(d['req'])}</p>
<div class="ba"><div><span class="lbl">Before</span><q>{esc(d['before'])}</q></div>
<div><span class="lbl">After</span><q>{esc(d['after'])}</q></div></div>
{''.join(rows)}
<p class="ev">{esc(d['evidence'])}</p>{ask}
{''.join(figs)}
</article>"""


def examples_grid(spec: Path) -> str:
    fig = spec / "1-core" / "figures" / "examples"
    items = []
    for p in sorted(fig.glob("*.jpg"), key=lambda p: (len(p.stem.split("-")[0]), p.stem)):
        items.append(f'<figure class="thumb"><img loading="lazy" alt="example {esc(p.stem)}" src="{jpeg(p, 520)}">'
                     f'<figcaption>{esc(p.stem)}</figcaption></figure>')
    # The requirement figures are vignettes (a row of small panels): one per row, at full width.
    req = []
    for p in sorted((fig / "requirements").glob("*.jpg")):
        req.append(f'<figure class="thumb"><img loading="lazy" alt="requirement figure {esc(p.stem)}" '
                   f'src="{jpeg(p, 1040)}"><figcaption>{esc(p.stem)}</figcaption></figure>')
    gallery = []
    for p in sorted((ROOT / "gallery" / "maps").glob("*.jpg")):
        gallery.append(f'<figure class="thumb"><img loading="lazy" alt="gallery map {esc(p.stem)}" '
                       f'src="{jpeg(p, 520)}"><figcaption>{esc(p.stem)}</figcaption></figure>')
    return (f'<h3>The {len(items)} examples of clause 17 and Annex C</h3><div class="grid">' + "".join(items) + "</div>"
            f'<h3>The {len(req)} figures under the requirements</h3>'
            '<p>Each is a row of small panels of one place that differ in one value; the bold label marks the panel '
            'whose style is printed under the figure. Pale lakes are the only context.</p>'
            '<div class="rows">' + "".join(req) + "</div>"
            f'<h3>The {len(gallery)} gallery maps (not in the document)</h3>'
            '<p>The earlier requirement figures, with land cover, relief and rivers as context. They are not part of '
            '#192: their styles and renders are in <a href="maps/">gallery/maps</a> of cartosym-draft-check, for a later '
            'gallery or use case annex, as Jérôme suggested on #185.</p>'
            '<div class="grid">' + "".join(gallery) + "</div>")


CSS = """
:root {
  --paper:#f5f8fa; --panel:#ffffff; --ink:#15232e; --muted:#536473; --rule:#d3dde4; --accent:#0a5d88;
  --proposal:#9a5800; --fix:#0a5d88; --ours:#14745a; --ok:#e3f1ea; --ok-ink:#14745a; --off:#fbe7e4; --off-ink:#b02a1f;
  --display:"IBM Plex Sans Condensed","Arial Narrow",Arial,sans-serif;
  --body:"IBM Plex Sans","Segoe UI",Arial,sans-serif;
  --mono:"IBM Plex Mono",Consolas,monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper:#0f171d; --panel:#16212a; --ink:#e3eaef; --muted:#9bacb9; --rule:#2c3b47; --accent:#74bce2;
  --proposal:#e8ad5c; --fix:#74bce2; --ours:#5cc6a2; --ok:#173a2e; --ok-ink:#7fd9b5; --off:#3d1f1c; --off-ink:#f2a097;
  color-scheme:dark; } }
:root[data-theme="dark"] {
  --paper:#0f171d; --panel:#16212a; --ink:#e3eaef; --muted:#9bacb9; --rule:#2c3b47; --accent:#74bce2;
  --proposal:#e8ad5c; --fix:#74bce2; --ours:#5cc6a2; --ok:#173a2e; --ok-ink:#7fd9b5; --off:#3d1f1c; --off-ink:#f2a097;
  color-scheme:dark; }
body { background:var(--paper); color:var(--ink); font:15px/1.55 var(--body); }
.wrap { max-width:1080px; margin:0 auto; padding-block:28px 64px;
  padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); }
h1,h2,h3 { font-family:var(--display); text-wrap:balance; line-height:1.15; }
h1 { font-size:2.1rem; margin:0 0 6px; } h2 { font-size:1.45rem; margin:44px 0 12px; padding-top:10px; border-top:1px solid var(--rule); }
h3 { font-size:1.12rem; margin:22px 0 10px; }
p, li { max-width:72ch; } a { color:var(--accent); } code, q { font-family:var(--mono); font-size:.86em; }
.lede { color:var(--muted); font-size:1.05rem; }
nav.toc { display:flex; flex-wrap:wrap; gap:6px 14px; font-size:.9rem; margin:14px 0 0; }
.facts { display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:10px; margin:18px 0; }
.fact { background:var(--panel); border:1px solid var(--rule); padding:10px 12px; }
.fact b { display:block; font:600 1.5rem var(--display); font-variant-numeric:tabular-nums; }
.fact span { color:var(--muted); font-size:.86rem; }
.tablewrap { overflow-x:auto; } table { border-collapse:collapse; font-size:.9rem; min-width:560px; }
th, td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--rule); vertical-align:top; }
th { font-family:var(--display); font-weight:600; } td.n { font-variant-numeric:tabular-nums; }
.card { background:var(--panel); border:1px solid var(--rule); border-left:5px solid var(--proposal); padding:14px 16px 10px; margin:14px 0; min-width:0; }
.card.fix { border-left-color:var(--fix); } .card.ours { border-left-color:var(--ours); }
.card header { display:flex; flex-wrap:wrap; align-items:baseline; gap:6px 12px; }
.card h3 { margin:0; flex:1 1 300px; }
.cid { font:600 .95rem var(--mono); color:var(--muted); }
.status { font:600 .72rem var(--body); text-transform:uppercase; letter-spacing:.06em; color:var(--proposal); }
.card.fix .status { color:var(--fix); } .card.ours .status { color:var(--ours); }
.req { font:.84rem var(--mono); color:var(--muted); margin:4px 0 10px; }
.ba { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
@media (max-width:700px) { .ba { grid-template-columns:1fr; } }
.ba > div { min-width:0; } .lbl { display:block; font:600 .72rem var(--body); text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
.ba q { quotes:none; display:block; font-family:var(--body); font-size:.92rem; }
.readers { display:flex; flex-wrap:wrap; align-items:center; gap:5px; margin:10px 0 0; }
.rl { font:600 .72rem var(--body); text-transform:uppercase; letter-spacing:.06em; color:var(--muted); width:70px; }
.chip { font-size:.8rem; padding:2px 7px; border-radius:3px; white-space:nowrap; }
.chip b { font-weight:600; } .chip.ok { background:var(--ok); color:var(--ok-ink); } .chip.off { background:var(--off); color:var(--off-ink); }
.ev { margin:12px 0 4px; } .ask { margin:4px 0 8px; }
.answer { margin:6px 0 10px; padding:8px 12px; border-left:3px solid var(--rule); background:var(--paper); }
.answer .akind { font:600 .72rem var(--body); text-transform:uppercase; letter-spacing:.06em; margin:0 6px; }
.answer.agrees { border-left-color:var(--ok-ink); } .answer.agrees .akind { color:var(--ok-ink); }
.answer.differs { border-left-color:var(--off-ink); } .answer.differs .akind { color:var(--off-ink); }
.answer.open .akind { color:var(--muted); }
figure { margin:12px 0 0; } figcaption { font-size:.8rem; color:var(--muted); margin-bottom:4px; }
.strip { overflow-x:auto; border:1px solid var(--rule); } .strip img { max-width:none; width:auto; display:block; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(230px, 1fr)); gap:12px; }
.rows { display:grid; gap:12px; }
.thumb { margin:0; background:var(--panel); border:1px solid var(--rule); padding:6px; }
.thumb img { width:100%; display:block; } .thumb figcaption { font-family:var(--mono); margin:4px 0 0; }
ul.plain { padding-left:18px; } ul.plain li { margin:3px 0; }
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
"""


def page(spec: Path) -> tuple[str, str]:
    groups: dict[str, list[dict]] = {}
    for d in DECISIONS:
        groups.setdefault(d["group"], []).append(d)
    cards = "".join(f"<h3>{esc(g)}</h3>" + "".join(card(d) for d in ds) for g, ds in groups.items())
    asks = "".join(f'<li><a href="#{d["id"]}">{d["id"]}</a> {esc(d["ask"])}</li>' for d in DECISIONS if d.get("ask"))
    table_rows = [
        ("W1 y of a position", "4 up, 2 down", "3 up"), ("W2 bare hotSpot number", "5 fraction, 1 pixels", "3 fraction"),
        ("W5 dashOffset", "5 into the pattern, 1 leading gap", "3 into the pattern"),
        ("W6 centre lines", "2 per feature, 4 after all", "3 after all"),
        ("W7 repetitions", "4 same text in the layer, 2 per feature", "3 same text in the layer"),
        ("W7 labels at the edge", "1 dropped, 5 kept (clipped)", "3 dropped"),
        ("W8 hatch angle", "6 clockwise", "3 counter-clockwise"),
        ("W10 stipples", "3 random, 3 regular grid", "3 random"),
        ("W11 font outline unit", "5 pixels, 1 points", "3 pixels"),
        ("W12 cells and pixels", "4 nearest, 2 bilinear", "3 nearest"),
        ("W13 hill-shading samples", "2 cells, 4 bilinear at pixels", "2 cells, 1 misread (reworded)"),
        ("W15 unselected features", "5 drawn, 1 not drawn", "3 drawn"),
    ]
    trows = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in table_rows)
    body = f"""<div class="wrap">
<h1>Walkthrough of PR #192: renders in the Part 1 document</h1>
<p class="lede">Part 1 of OGC Cartographic Symbology 2.0 gets rendered examples on Norwegian data, with CartoSym-CSS and CartoSym-JSON next to each render, and the requirements that independent readers rendered differently get tighter wording. Pull request <a href="https://github.com/opengeospatial/cartographic-symbology/pull/192">#192</a> (branch <code>example-renders</code>); nothing here is an SWG decision until the group makes it.
Jérôme's replies on #192 ({ANSWERS_ON}) are shown under each change: he agrees with {sum(k == "agrees" for k, _ in ANSWERS.values())},
answered {sum(k == "differs" for k, _ in ANSWERS.values())} differently, and left {sum(k == "open" for k, _ in ANSWERS.values())} open.
Since 17 November the branch follows these answers; the changes, and the choices made where an answer left one open, are in the decision log under &ldquo;Changes after the replies&rdquo;.</p>
<nav class="toc"><a href="#examples">1. The examples</a><a href="#method">2. How the wording was checked</a><a href="#changes">3. The changes</a><a href="#asks">4. Asked of the SWG</a><a href="#open">5. Left for issues</a><a href="#links">6. Records</a></nav>
<div class="facts">
<div class="fact"><b>31</b><span>examples: 11 whole styles, 20 under requirements</span></div>
<div class="fact"><b>138</b><span>requirements, each with a test, render or encoding check</span></div>
<div class="fact"><b>12</b><span>independent runs: 6 + 3 renderers, 3 evaluators</span></div>
<div class="fact"><b>0.0 %</b><span>pixels apart, two runs on the new text, all maps but stipples</span></div>
</div>

<h2 id="examples">1. The examples</h2>
<p>All examples use one area, Rondane in Norway: Kartverket N50 Kartdata (land cover, rivers, roads, cabins, protected areas, place names), the national terrain model and a Sentinel-2 scene, all CC BY 4.0 or Copernicus. In the document each figure sits above a two-column table with the style in CartoSym-CSS and CartoSym-JSON. The JSON is converted from the CSS with pycartosym and validated against the schema of <code>main</code> and of #188; pycartosym 0.6.5 needs one fix-up, renaming <code>centerLine</code> to <code>center</code> (until #188). The elevation model is fetched for each panel at about one cell per screen pixel (2 m at 1:4 000, 50 m for the whole area), and the Sentinel-2 scene of 1 September 2024 is cloud-free. The numbered vector examples are drawn over a pale map (forest, farmland, water, rivers and the grey shadows of the relief, leaving out any layer the example styles itself), with a scale bar and a credit; the caption says these are context, not part of the style. Coverage examples 5 and 7, which are 80 % opaque, show the relief shadows through them. The 21 figures under the requirements are vignettes: rows of small panels of one place that each change one value, with pale lakes as the only context (Jérôme on #185 and #192); the earlier requirement maps are kept as a gallery outside the document. Examples 1 to 4, 10 and 11 were rewritten for Rondane; 2, 3 and 4 also differ from the SWG's originals beyond the data: colours and stroke widths from the shared palette, road classes in 3, a Dot at every scale in 4 (the default white Dot disappeared on the map), and SVG icons in 2 (the draft renderer draws every Image 24 px wide, so 24 px PNGs were blurred in the 2&times; figures). The structure of each style, and what it shows, is the SWG's. In the N50 data, coordinates are kept to 0.1 m, and road and river pieces that meet end to end with the same properties are joined into one line.</p>
{examples_grid(spec)}

<h2 id="method">2. How the wording was checked</h2>
<p>The question: does an implementation written only from the requirement text draw the same maps as another one? Six fresh Claude sessions (three Opus, two Sonnet, one Haiku) each got the requirement text of <code>main</code> without figures and the render kits of the 20 requirement examples, and wrote a renderer from the text alone, listing every choice the text left open. They could not see the draft renderer, pycartosym, libCartoSym, the web or each other. Where they split, one reading was written into the requirement, preferring in order: what the document shows (its figures and examples), consistency with the rest of the document, the SE 1.1 mapping in Annex B, and what most readers chose. Three fresh runs on the tightened text then checked the result. Three more sessions wrote expression evaluators from the text for the 123 cases of the test harness.</p>
<div class="tablewrap"><table><thead><tr><th>Point</th><th>Six runs, old text</th><th>Three runs, new text</th></tr></thead><tbody>{trows}</tbody></table></div>
<p>On the expressions, all three evaluators agreed with each other on all 123 cases and with the harness on 121: one harness case was wrong (X1) and one gap in the text was found (X2).</p>

<h2 id="changes">3. The changes</h2>
<p>Each card quotes the text before and after, shows what each reader chose (green where it matches the proposal) and, where there is a map, the six old-text runs above the draft renderer and the three new-text runs. Scroll the strips sideways. The strips were drawn from the render kits the readers got (the 150 m elevation and the first versions of the styles), before the figures in section 1 got their finer data and palette: they compare the readers, not the final figures.</p>
{cards}
<h3>Contradictions fixed without a decision</h3>
<ul class="plain"><li>Clause 7: <code>visualization.timeInterval</code> described as the time of day; TimeOfDay <code>minutes</code> typed Month; <code>zOrder</code> float in one table and int in the requirement.</li><li>Clause 9: the ValueOpacity table listed <code>color</code> instead of <code>opacity</code>.</li><li>The hatch angle table (W8) and the stale dot pattern TODO.</li></ul>

<h2 id="asks">4. Asked of the SWG</h2>
<ul class="plain">{asks}<li>Example 8's <code>factor: 56</code> rendered the Rondane relief almost black with factor as vertical exaggeration. Answered by Jérôme (56 was an extreme value): examples 8 and 9 now use <code>factor: 3</code>, and the requirement figures are to show several values.</li><li>Part 1 fixed butt caps and miter joins, and N50 starts a new feature wherever an attribute changes, so the figures showed a notch where two pieces of a road meet at a bend (#193). Answered by Jérôme: round caps and round joins by default. Clause 8 and <code>/req/vector/stroke</code> now say so, and the figures are drawn with them.</li></ul>

<h2 id="open">5. Left for issues</h2>
<ul class="plain">
<li>Schema and text names, all in existing issues: <code>center</code>/<code>centerLine</code> and <code>dashOffset</code> (#120, fixed in #188); <code>dataLayer.identifier</code>/<code>dataLayer.id</code> and <code>visualization.*</code>/<code>viz.*</code> (#168); <code>url</code>/<code>uri</code>, the alignment members and the unit lists (#169); colour ranges 0 to 1 and 0 to 255 (#150).</li>
<li>Rendering points no reader could settle from the text (#194). Answered by Jérôme and now in the branch: no miter limit (round joins), nothing for a stroke of width 0, an Image at its own size in pixels, linear light allowed for colour maps and tints, overviews allowed for maps coarser than the coverage, casing and centre line width 0 by default, and hill shading off by default. Still open: how a number is written as text, defaults for fonts and outlines, the unit of a font <code>size</code> without one, and an Image <code>size</code> (#100).</li>
<li>Expressions: precedence and associativity exist only in the order of the grammar's alternatives (<code>-2 ^ 2</code> is 4, <code>2 ^ 3 ^ 2</code> is 64): #118, #178, #180. NULL: #155, where a comment points out that the Logical Operators table is still two-valued. Added to #173: <code>random()</code> parses as an empty instance, not as a function call, as <code>arguments</code> needs at least one expression (fixed by #196); <code>true</code>, <code>false</code> and <code>null</code> are not tokens of the lexer and parse as identifiers, which Jérôme answered is intended.</li>
<li>pycartosym: 0.6.4 dropped <code>marker: null</code>, <code>dashOffset</code> and dash lengths with units, turned a bare identifier in label placement into a string, and kept a hex colour of a Dot as a string (maxcollombin/pycartosym <a href="{PYCS}/174">#174</a>, <a href="{PYCS}/182">#182</a> to <a href="{PYCS}/185">#185</a>). 0.6.5 fixes all of these, and converts every example without fix-ups except casing, where it writes <code>centerLine</code>, the name in <code>main</code>&rsquo;s schema until #188.</li>
</ul>

<h2 id="links">6. Records</h2>
<ul class="plain">
<li><a href="https://github.com/opengeospatial/cartographic-symbology/pull/192">#192</a>: the pull request; <a href="https://github.com/opengeospatial/cartographic-symbology/issues/193">#193</a> (caps and joins) and <a href="https://github.com/opengeospatial/cartographic-symbology/issues/194">#194</a> (rendering details the text leaves open) came from it.</li>
<li><a href="{REPO}/reports/wording-decisions.md">wording-decisions.md</a>: the log behind this page, with the alternatives not taken.</li>
<li><a href="{REPO}/reports/independent/README.md">reports/independent/</a>: the notes, code, results and maps of all twelve runs.</li>
<li><a href="{REPO}/tools/fetch_n50.py">tools/fetch_n50.py</a> and <a href="{REPO}/src/cartosym_draft/doc_examples.py">doc_examples.py</a>: the data and the build of the examples.</li>
</ul>
</div>"""
    head = ('<title>PR #192 renders walkthrough</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+'
            'Condensed:wght@600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">\n'
            f"<style>{CSS}</style>\n")
    return head, link_issues(body)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, default=ROOT.parent / "cartographic-symbology")
    ap.add_argument("--artifact", type=Path, help="also write the page without the document wrapper here")
    args = ap.parse_args(argv)
    head, body = page(args.spec)
    full = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"{head}</head>\n<body>\n{body}\n</body>\n</html>\n")
    from cartosym_draft.assets import externalize_data_images
    from cartosym_draft.gallery import RECORD_IMAGES, RECORD_PAGES
    from cartosym_draft.nav import insert_topbar

    out = ROOT / "gallery" / "pr192-renders-walkthrough.html"
    full = insert_topbar(full, out.name, **RECORD_PAGES[out.name])  # the site's bar; the --artifact copy goes without
    # The images as files next to the page (the --artifact copy keeps them inside, as claude.ai needs)
    full = externalize_data_images(full, out.parent / RECORD_IMAGES[out.name], RECORD_IMAGES[out.name])
    out.write_text(full, encoding="utf-8")
    print(out, len(full) // 1024, "KiB")
    if args.artifact:
        args.artifact.write_text(head + body + "\n", encoding="utf-8")
        print(args.artifact)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
