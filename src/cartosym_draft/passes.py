"""Render kits for the rendering-pass cases of opengeospatial/cartographic-symbology#212.

Usage: python -m cartosym_draft.passes [gallery]

Each case is a CartoSym-CSS file in passes/, drawn on one small scene of crossing roads, a railway and a
zone. Cases 01 to 08 are maxcollombin/pycartosym `examples/passes` (MIT License, (c) Maxime Collombin) with
`marker: null;` added to each top-level rule, so that no default Dot is drawn (/req/core/default-values).
Cases 09 to 13 are the ones listed on #197 and #212 that pycartosym's set doesn't have; where the text is
open, the draft renderer draws each reading (the Options of casing_layers, label_viz_pass,
opacity_passes, label_pass and opacity). For each case this writes gallery/kit/passes-<case>/ (both style encodings, one GeoJSON file per data layer,
view.json, the draft renderer's image and a README with what should be drawn) and gallery/passes.html.
"""

from __future__ import annotations

import html
import io
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .kit import export, zip_all
from .options import Options
from .render import Layer, View, render

CASES_DIR = Path(__file__).parent / "passes"
# A mid-tone background, so that white strokes show (01, 02) as well as black ones.
VIEW = View(bbox=(0, 0, 300, 200), width=300, height=200, background="#bcc6b4")
DRAFT = Options()  # the draft's readings, the default Marker included: the styles set `marker: null`
ZOOM = 2  # the PNGs are drawn at twice the size of view.json
DETAIL = "84 77 75 50"  # viewBox around the crossing of roads 1 and 2 and the T-junction (4 × enlarged)
PYCARTOSYM_PASSES = "https://github.com/maxcollombin/pycartosym/tree/main/examples/passes"
ISSUE = "https://github.com/opengeospatial/cartographic-symbology/issues/"
ANNEX_C_PR = "https://github.com/opengeospatial/cartographic-symbology/pull/233"


def _line(coords, **props) -> dict:
    return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}}


# One scene for all cases, in metres (1 m = 1 px at 1:3 571): two roads crossing, a third ending on the first
# (a T-junction), a railway across them and a zone beneath. Feature order is data order: road 2 comes after road 1.
ROADS = Layer("Roads", [
    _line([[10, 60], [150, 110], [290, 150]], kind="road", name="Road 1"),
    _line([[40, 190], [140, 100], [250, 10]], kind="road", name="Road 2"),
    _line([[90, 10], [100, 92]], kind="road", name="Road 3"),
])
RAILS = Layer("Rails", [_line([[10, 150], [150, 40], [290, 80]], kind="rail", name="Railway")])
# The same railway in three pieces for 11: a bridge (z_order 2) where it crosses road 2, at (193, 52).
RAILS_BRIDGE = Layer("Rails", [
    _line([[10, 150], [150, 40], [175, 47.14]], kind="rail", name="Railway", bridge=False, z_order=1),
    _line([[175, 47.14], [211, 57.43]], kind="rail", name="Railway bridge", bridge=True, z_order=2),
    _line([[211, 57.43], [290, 80]], kind="rail", name="Railway", bridge=False, z_order=1),
])
ZONES = Layer("Zones", [{"type": "Feature", "properties": {"kind": "zone", "name": "Zone"},
                         "geometry": {"type": "Polygon",
                                      "coordinates": [[[60, 30], [240, 30], [240, 170], [60, 170], [60, 30]]]}}])


@dataclass
class Variant:
    label: str
    options: Options
    note: str = ""


@dataclass
class Case:
    name: str  # the file name in passes/, also the kit's name after "passes-"
    title: str
    layers: list[Layer]
    expected: str  # what should be drawn, in drawing order (Markdown)
    source: str = "pycartosym"
    variants: list[Variant] = field(default_factory=list)  # other readings, where the text is open
    # Other styles for the same case, as passes/<name>-<suffix>.cscss: (suffix, label).
    extra_styles: list[tuple[str, str]] = field(default_factory=list)
    # Symbolizer properties the case tests: removing them from the style must change the image.
    tests: tuple[str, ...] = ()
    # Suffixes of extra_styles that must draw the same image as the case's style.
    same_as: tuple[str, ...] = ()
    # The enlarged detail: SVG viewBox and what it shows.
    detail: tuple[str, str] = (DETAIL, "the crossing and the T-junction")
    question: str = ""  # where the text is open: the question the readings answer (Markdown)
    draft_label: str = "Draft renderer"  # the caption of the draft's reading

    @property
    def key(self) -> str:
        return f"passes-{self.name}"

    @property
    def css(self) -> str:
        return self.css_of("")

    def css_of(self, suffix: str) -> str:
        return (CASES_DIR / f"{self.name}{'-' + suffix if suffix else ''}.cscss").read_text(encoding="utf-8")


CASES = [
    Case("01-nested-override", "Nested rules without a selector override each other", [ROADS],
         "Each road is drawn once, with the white 3 px stroke. The two nested rules have no selector, so they merge "
         "into their parent and the second `stroke` replaces the first ([#197](" + ISSUE + "197), "
         "[#200](" + ISSUE + "200)). No black shows."),
    Case("02-toplevel-override", "Top-level rules with the same selector override each other", [ROADS],
         "The same as 01: both rules select every road, and the second rule's `stroke` replaces the first's. "
         "Each road has only the white 3 px stroke."),
    Case("03-feature-pass", "`feature.pass`: one feature at a time", [ROADS],
         "Each road is drawn with its black 5 px stroke and then its white 3 px stroke, before the next road. "
         "Roads are drawn in data order (road 1, 2, 3), so at the crossing road 2's black edges cut across road 1's "
         "white line, and at the T-junction road 3's black end cuts into road 1's white line. The edges are 1 px "
         "wide, so the difference from 04 is small; `style-wide.cscss` is the same style with 12 px and 8 px "
         "strokes, where it shows clearly.",
         extra_styles=[("wide", "The same with wider strokes (12 px and 8 px)")]),
    Case("04-viz-pass", "`viz.pass`: all features per pass", [ROADS],
         "Pass 0 draws the black 5 px strokes of all roads, pass 1 their white 3 px strokes. The white lines join "
         "at the crossing and at the T-junction, with no black across them. `style-wide.cscss` is the same style "
         "with 12 px and 8 px strokes, to compare with 03's.",
         extra_styles=[("wide", "The same with wider strokes (12 px and 8 px)")]),
    Case("05-casing", "Built-in casing", [ROADS],
         "Each road has a white 3 px stroke with a black casing 1 px beyond each side (5 px in all, "
         "[#147](" + ISSUE + "147)). The roads have the same `zOrder`, so the casings of all roads are drawn before "
         "their main strokes: the crossing and the T-junction merge, and the map looks the same as 04."),
    Case("06-rule-without-pass", "A rule without `viz.pass` next to rules with one", [ZONES, ROADS],
         "Pass 0: the light gray fill of the zone, with the default black 1 px stroke (the rule sets no stroke), "
         "and the black 5 px strokes of the roads. Pass 1: the white 3 px strokes of the roads. The Zones rule "
         "doesn't test `viz.pass`, so it is drawn in pass 0 only: a rule that doesn't test `viz.pass` is evaluated "
         "in every pass, but only a rule that tests it is drawn in a pass other than 0 (Jérôme on "
         "[#207](" + ISSUE + "207) and [#211](" + ISSUE + "211); [#198](" + ISSUE + "198))."),
    Case("07-feature-and-viz-pass", "`feature.pass` inside a `viz.pass`", [ROADS],
         "Pass 0, one road at a time: its black 7 px stroke, then its white 5 px stroke (feature passes 0 and 1), "
         "so at the crossing road 2's black edges cut across road 1's white line, as in 03. Pass 1: the red 1 px "
         "line of every road, above all of pass 0 and unbroken at the crossing."),
    Case("08-zorder", "`zOrder` across data layers", [RAILS, ROADS],
         "The railway (`zOrder: 1`) is drawn above the roads (`zOrder: 0`): the black 2 px line is unbroken where "
         "it crosses the gray 4 px roads (`/req/core/z-order`). `view.json` lists Rails before Roads, so without "
         "`zOrder` the roads would be drawn over the railway: only `zOrder` puts it on top. The roads join at the "
         "crossing and the T-junction, as they are all drawn before the railway.",
         tests=("zOrder",)),
    Case("09-center-line", "Built-in casing and center line", [ROADS],
         "Each road has a yellow 10 px stroke, a brown casing 1.5 px beyond each side and a brown 1 px center line. "
         "The casings of all roads are drawn first, then the main strokes, then the center lines: at the crossing "
         "and the T-junction the yellow strokes join with no casing across them, and the center lines run through "
         "(road 2's over road 1's). `style-passes.cscss` writes the same order with three visualization passes "
         "and draws the same image (the build checks this).",
         source="ours", extra_styles=[("passes", "The same with three visualization passes")], same_as=("passes",)),
    Case("10-labels-pass", "Labels and visualization passes", [ROADS],
         "Pass 0: the black 12 px strokes of the roads; pass 1: their white 8 px strokes; then the labels, black on "
         "the white roads, on top of everything. Each label is drawn once, although its rule applies in both "
         "passes. Road 2's label would overlap Road 1's, so only Road 1's is drawn (`/rec/labels/overlap`; "
         "both have the same priority, and Road 1 comes first).",
         source="ours", draft_label="Labels after the last pass (draft renderer)",
         question="Labels are drawn \"as a separate pass on top of all styled vector features and coverages\" "
                  "(`/req/labels/label`). With visualization passes, is that after the last pass, or at the end "
                  "of the pass that draws the label? The label is set in a rule that doesn't test `viz.pass`, so it "
                  "applies in both passes: is it drawn once?",
         variants=[Variant("Labels at the end of their pass", DRAFT.with_(label_viz_pass="own-pass"),
                           "The labels come with pass 0, so the white strokes of pass 1 cover them.")]),
    Case("11-feature-pass-minus-one", "A bridge in feature pass -1", [ROADS, RAILS_BRIDGE],
         "The roads and the two ground pieces of the railway (`z_order` 1) are at `zOrder` 1: the roads' casings "
         "first, then the main strokes in data layer order, so the railway crosses road 1 on the level, over it. "
         "The bridge piece has `z_order` 2, so it comes after everything at `zOrder` 1: first its feature pass "
         "-1, a white 9 px line with a dark casing 1 px beyond each side, covering road 2 beneath, then its pass "
         "0, the black 3 px railway on top. At the bridge's ends, the round caps of the white line and its casing "
         "(`/req/vector/stroke`) show as half circles around the railway.",
         source="ours", detail=("158 125 75 50", "the bridge")),
    Case("12-shared-zorder", "Two data layers sharing a `zOrder`", [ROADS, RAILS],
         "Roads and the railway have the same `zOrder` (the default). Reading \"all features\" across data layers: "
         "the casings of the roads and the railway are drawn first, then the main strokes in data layer order, "
         "roads then railway. Where the railway crosses a road, its white dashes lie on the yellow road with no "
         "dark casing across it, and no road casing cuts the railway.",
         source="ours", draft_label="Casings of all data layers first (draft renderer)",
         question="`/req/casing/casing` draws \"the casings of all features with the same `zOrder`\" beneath \"the "
                  "main strokes of all those features\". Does that include the features of other data layers? The "
                  "painter's algorithm in clause 7 says so, but it is commented out of the published text; QGIS "
                  "orders only within one map layer (kraftto on #212).",
         variants=[Variant("Each data layer complete before the next", DRAFT.with_(casing_layers="per-layer"),
                           "As separate QGIS or MapLibre layers draw: the railway's dark casing cuts across the "
                           "roads.")]),
    Case("13-translucent-passes", "A translucent layer with visualization passes", [ZONES, ROADS],
         "Pass 0: the green zone (with the default black 1 px stroke), then the roads' black 12 px strokes at 50 % "
         "as one group, so they don't show through each other at the crossing. Pass 1: the roads' white 8 px "
         "strokes at 50 %, as a second group over the first, so the black shows through the white: light gray roads "
         "with dark edges, through which the zone shows.",
         source="ours", draft_label="A group per pass (draft renderer)",
         question="`/rec/core/opacity-together` applies the Symbolizer `opacity` to the parts of a feature "
                  "together, \"either for each feature or for all features of a data layer with the same `zOrder` "
                  "drawn at once\". With visualization passes, is that one group per pass, or one group for all of "
                  "the layer's passes?",
         variants=[Variant("One group for all passes", DRAFT.with_(opacity_passes="all-passes"),
                           "The white covers the black inside the group: a 50 % white line with 50 % black edges."),
                   Variant("Each stroke on its own", DRAFT.with_(opacity="per-element"),
                           "Meets /req/core/opacity but not the recommendation: the strokes show through each "
                           "other at the crossing.")]),
]


def _png(svg: str) -> bytes:
    import resvg_py
    from PIL import Image

    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=ZOOM))
    out = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def _without(style, prop: str):
    """A copy of *style* with *prop* removed from every Symbolizer."""
    if isinstance(style, dict):
        return {k: _without(v, prop) for k, v in style.items()
                if not (k == prop and "selector" not in style and "stylingRules" not in style)}
    if isinstance(style, list):
        return [_without(v, prop) for v in style]
    return style


def _same(svg_a: str, svg_b: str) -> bool:
    """Whether two renders are the same apart from their generated ids."""
    norm = lambda s: re.sub(r'id="[^"]*"|url\(#[^)]*\)', "", s)  # noqa: E731
    return norm(svg_a) == norm(svg_b)


def _same_pixels(png_a: bytes, png_b: bytes) -> bool:
    from PIL import Image, ImageChops

    a, b = (Image.open(io.BytesIO(p)).convert("RGB") for p in (png_a, png_b))
    return a.size == b.size and ImageChops.difference(a, b).getbbox() is None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _readme(case: Case, fixups: list[str], images: list[tuple[str, str]]) -> str:
    if case.source == "pycartosym":
        origin = (f"From maxcollombin/pycartosym [`examples/passes/{case.name}`]({PYCARTOSYM_PASSES}) "
                  "(MIT License, © Maxime Collombin), with `marker: null;` added to each top-level rule so that no "
                  "default Dot is drawn.")
    else:
        origin = "Added for #212 from the list on [#197](" + ISSUE + "197) (cartosym-draft-check)."
    question = ""
    if case.question:
        readings = [case.draft_label] + [f"{v.label}. {v.note}" for v in case.variants]
        question = ("\n## Open question\n\n" + case.question + "\n\nThe draft renderer draws each reading:\n\n"
                    + "\n".join(f"- {r}" for r in readings) + "\n")
    layers = "\n".join(f"- `{layer.id}.geojson`: the data layer `{layer.id}` ({len(layer.features)} "
                       f"feature{'s' * (len(layer.features) != 1)}, EPSG:25833)" for layer in case.layers)
    import pycartosym

    conv = f"converted from `style.cscss` with pycartosym {pycartosym.__version__}"
    if fixups:
        conv += f" (corrected by cartosym-draft-check: {'; '.join(fixups)})"
    pics = "\n".join(f"- `{name}`: {label}" for name, label in images)
    extra_css = "".join(f"\n\n{label}, `style-{suffix}.cscss`:\n\n```css\n{case.css_of(suffix).rstrip()}\n```"
                        for suffix, label in case.extra_styles)
    extra_files = "".join(f"\n- `style-{suffix}.cscss`, `style-{suffix}.cs.json`: {label[0].lower()}{label[1:]}"
                          for suffix, label in case.extra_styles)
    return f"""# {case.name}: {case.title.replace('`', '')}

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212]({ISSUE}212). {origin}

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233]({ANNEX_C_PR}).

## Style

```css
{case.css.rstrip()}
```{extra_css}

## What should be drawn

{case.expected}
{question}
## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, {conv}{extra_files}
{layers}
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
{pics}

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.
"""


# The README ends with this; what contributors add after it (a line per renderer) is kept on a rebuild.
OTHER_RENDERERS_END = "other software (e.g. `qgis-render.png`), with a line here on what it can't express.\n"


def _contributed(readme: Path) -> str:
    """What follows the "Other renderers" paragraph in *readme*, if it exists."""
    if not readme.exists():
        return ""
    text = readme.read_text(encoding="utf-8")
    i = text.find(OTHER_RENDERERS_END)
    return text[i + len(OTHER_RENDERERS_END):] if i >= 0 else ""


def build(out_dir: Path) -> list[str]:
    """Write the kits and passes.html into *out_dir* (the gallery folder); return the problems found."""
    from .doc_examples import to_json
    from .gallery import _check_styles

    problems: list[str] = []
    rendered = []
    for case in CASES:
        styles, fixed = {}, set()
        for suffix, _ in [("", ""), *case.extra_styles]:
            style, fixups = to_json(case.css_of(suffix))
            problems += [f"{case.name} {suffix}: {f}" for f in fixups if f.startswith("pycartosym warning")]
            fixed |= {f for f in fixups if not f.startswith("pycartosym warning")}
            styles[suffix] = style
        files = {f"style{'-' + s if s else ''}.cs.json": st for s, st in styles.items()}
        problems += _check_styles(files, case.key)
        for prop in case.tests:
            if _same(render(styles[""], case.layers, VIEW, DRAFT),
                     render(_without(styles[""], prop), case.layers, VIEW, DRAFT)):
                problems.append(f"{case.name}: the image is the same without `{prop}`, so the case doesn't test it")
        export(case.key, case.title.replace("`", ""), files, case.layers, VIEW, out_dir)
        d = out_dir / "kit" / case.key
        for s in styles:
            (d / f"style{'-' + s if s else ''}.cscss").write_text(case.css_of(s), encoding="utf-8")
        # (label, style, options, file stem, note): the draft's readings of each style, then the other readings.
        readings = [(case.draft_label, styles[""], DRAFT, "draft-render", "")]
        readings += [(label, styles[s], DRAFT, f"draft-render-{s}", "") for s, label in case.extra_styles]
        readings += [(v.label, styles[""], v.options, f"draft-render-{_slug(v.label)}", v.note) for v in case.variants]
        svgs, images = [], []
        view_box, shows = case.detail
        pngs = {}
        for label, style, opts, stem, note in readings:
            svg = render(style, case.layers, VIEW, opts)
            # Rendered again so that the ids of the two SVGs inlined in the page differ.
            # The background is 100 % of the viewport, which the crop would move off the detail: give it the map's size.
            detail = render(style, case.layers, VIEW, opts).replace(
                f'viewBox="0 0 {VIEW.width} {VIEW.height}"', f'viewBox="{view_box}"', 1).replace(
                '<rect width="100%" height="100%"', f'<rect width="{VIEW.width}" height="{VIEW.height}"', 1)
            pngs[stem] = _png(svg)
            (d / f"{stem}.png").write_bytes(pngs[stem])
            (d / f"{stem}-detail.png").write_bytes(_png(detail))
            what = "the draft renderer" + ("" if opts == DRAFT else f", reading: {label}")
            if style is not styles[""]:
                what += f", style `{stem.replace('draft-render', 'style')}.cscss`"
            images.append((f"{stem}.png", f"{what}, at {ZOOM} × the size of `view.json`"))
            images.append((f"{stem}-detail.png", f"the same, {shows} enlarged 4 ×"))
            svgs.append((label, svg, note))
            svgs.append((f"{label}: {shows}, enlarged 4 ×", detail, ""))
        for s in case.same_as:
            if not _same_pixels(pngs["draft-render"], pngs[f"draft-render-{s}"]):
                problems.append(f"{case.name}: style-{s} doesn't draw the same image as style")
        for v in case.variants:
            if _same_pixels(pngs["draft-render"], pngs[f"draft-render-{_slug(v.label)}"]):
                problems.append(f"{case.name}: the reading \"{v.label}\" draws the same image as the draft's")
        readme = _readme(case, sorted(fixed), images)
        assert readme.endswith(OTHER_RENDERERS_END)
        (d / "README.md").write_text(readme + _contributed(d / "README.md"), encoding="utf-8")
        rendered.append((case, styles, svgs))
    (out_dir / "passes.html").write_text(_page(rendered, out_dir), encoding="utf-8")
    return problems


def _md_inline(text: str) -> str:
    """The Markdown of the expected text as HTML: code spans and links only."""
    out = html.escape(text)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", out)


def _md_block(text: str, kit_dir: Path) -> str:
    """Markdown from a kit's README as HTML: headings, bullets, tables and paragraphs. Links relative to the README
    are made relative to passes.html, and file names of the kit in code spans link to the file."""
    kit = kit_dir.name

    def inline(t: str) -> str:
        out = _md_inline(t.replace("](../../../", "](../"))
        out = re.sub(r'<a href="(?!https?:|\.\./|#)([^"]+)"', rf'<a href="kit/{kit}/\1"', out)
        out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
        return re.sub(r"<code>([\w.-]+)</code>",
                      lambda m: f'<a href="kit/{kit}/{m.group(1)}"><code>{m.group(1)}</code></a>'
                      if (kit_dir / m.group(1)).is_file() else m.group(0), out)

    parts = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if lines[0].startswith("#"):
            level = min(len(lines[0]) - len(lines[0].lstrip("#")) + 1, 4)
            parts.append(f"<h{level}>{inline(lines[0].lstrip('#').strip())}</h{level}>")
            lines = lines[1:]
            if not lines:
                continue
        if lines[0].startswith("|"):
            rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines
                    if not re.fullmatch(r"\|[\s|:-]+\|", ln)]
            head, body = rows[0], rows[1:]
            parts.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
                         + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                         + "</table>")
        elif lines[0].startswith("- "):
            items: list[str] = []
            for ln in lines:
                if ln.startswith("- "):
                    items.append(ln[2:])
                else:
                    items[-1] += " " + ln
            parts.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
        else:
            parts.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(parts)


def _other_software(case: Case, kit_dir: Path) -> str:
    """The renders from other software and the SLD/MapLibre files contributed to a kit, with their notes."""
    notes = _contributed(kit_dir / "README.md")
    version = (re.search(r"QGIS [\d.]+", notes) or re.search("QGIS", "QGIS")).group(0)
    readings = {_slug(v.label): v.label for v in case.variants}
    styles = dict(case.extra_styles)
    figs = []
    for png in sorted(kit_dir.glob("qgis-render*.png"), key=lambda p: (p.stem != "qgis-render", p.stem)):
        s = png.stem[len("qgis-render"):].lstrip("-")
        label = (version if not s else f"{version}, `style-{s}.cscss`" if s in styles
                 else f"{version}, reading: {readings[s]}" if s in readings else f"{version}, {s.replace('-', ' ')}")
        figs.append(f'<figure><img class="other" src="kit/{kit_dir.name}/{png.name}" width="300" height="200" '
                    f'loading="lazy" alt="{html.escape(label.replace("`", ""))}"><figcaption>{_md_inline(label)}'
                    "</figcaption></figure>")
    if not figs and not notes.strip():
        return ""
    return (f'<div class="others"><h3>Other software</h3>'
            + (f'<div class="variants">{"".join(figs)}</div>' if figs else "")
            + _md_block(notes, kit_dir) + "</div>")


def _contributed_kits(out_dir: Path) -> list[Path]:
    """Pass kits added by contributors rather than built from CASES (such as 14, from XPlanung)."""
    built = {case.key for case in CASES}
    return sorted(d for d in (out_dir / "kit").glob("passes-*") if d.is_dir() and d.name not in built)


def _contributed_card(kit_dir: Path) -> tuple[str, str, str]:
    """(anchor, title, card HTML) for a contributed kit: its README's opening and expected drawing, its renders
    from other software and links to its files. The draft renderer doesn't draw these kits (yet)."""
    from .nav import permalink

    text = (kit_dir / "README.md").read_text(encoding="utf-8")
    heading, _, rest = text.partition("\n")
    name, _, title = heading.lstrip("# ").partition(": ")
    sections = {s.partition("\n")[0].lstrip("# ").strip(): s.partition("\n")[2]
                for s in re.split(r"\n(?=## )", "\n" + rest) if s.startswith("## ")}
    intro = re.split(r"\n(?=## )", rest)[0]
    expected = sections.get("What should be drawn", "")
    # The renders' notes: the bullets of "Other renderers", without the paragraph asking for pull requests.
    notes = "\n".join(ln for ln in sections.get("Other renderers", "").splitlines() if ln.startswith("- "))
    version = (re.search(r"QGIS [\d.]+", notes) or re.search("QGIS", "QGIS")).group(0)
    figs = "".join(
        f'<figure><img class="other" src="kit/{kit_dir.name}/{png.name}" width="300" height="200" loading="lazy" '
        f'alt="{version} render"><figcaption>{version}</figcaption></figure>'
        for png in sorted(kit_dir.glob("qgis-render*.png")))
    first = ["README.md", "style.cs.json", "view.json"]
    files = [n for n in first if (kit_dir / n).is_file()] + sorted(
        p.name for p in kit_dir.iterdir() if p.is_file() and p.name not in first and not p.name.endswith(".png")) \
        + sorted(f"{p.name}/" for p in kit_dir.iterdir() if p.is_dir())
    links = " · ".join(f'<a href="kit/{kit_dir.name}/{n}">{n}</a>' for n in files)
    card = (f'<section class="card" id="{kit_dir.name}"><h2>{html.escape(name)}: {_md_inline(title)}'
            f'{permalink(kit_dir.name)}</h2>{_md_block(intro, kit_dir)}'
            f'<p class="note">Contributed kit. No draft render yet: the draft renderer doesn\'t draw Part 2\'s '
            f'pattern strokes and graphic patterns, which this style uses. How the style was made is in the '
            f'<a href="kit/{kit_dir.name}/README.md">README</a>.</p>'
            f'<div class="others"><div class="variants">{figs}</div>{_md_block(notes, kit_dir)}</div>'
            f'<div class="question"><strong>What should be drawn.</strong>{_md_block(expected, kit_dir)}</div>'
            + (f'<h3>Data</h3>{_md_block(sections["Data"], kit_dir)}' if "Data" in sections else "")
            + f'<p class="kit">Render it yourself: {links}</p></section>')
    return kit_dir.name, title.replace("`", ""), card


def _page(rendered, out_dir: Path) -> str:
    from .gallery import CSS
    from .highlight import CSS as HIGHLIGHT_CSS, cscss
    from .nav import NAV_CSS, NAV_SCRIPT, permalink, toc, topbar

    extra = [_contributed_card(d) for d in _contributed_kits(out_dir)]
    contents = [(case.key, case.title.replace("`", ""), bool(case.question)) for case, _, _ in rendered]
    contents += [(anchor, title, False) for anchor, title, _ in extra]
    cards = []
    open_tag = ' <span class="badge open">open in the text</span>'
    for case, _, svgs in rendered:
        figs = "".join(f"<figure>{svg}<figcaption>{html.escape(label)}"
                       + (f'<span class="vnote">{html.escape(note)}</span>' if note else "") + "</figcaption></figure>"
                       for label, svg, note in svgs)
        kit_dir = out_dir / "kit" / case.key
        converted = sorted(p.name for p in kit_dir.glob("style*.*")
                           if p.name.endswith((".sld", ".maplibre.json")))  # written by pycartosym (draft-check #5)
        links = " · ".join(f'<a href="kit/{case.key}/{n}">{n}</a>'
                           for n in ["README.md", "style.cscss", "style.cs.json",
                                     *(f"style-{s}.{ext}" for s, _ in case.extra_styles for ext in ("cscss", "cs.json")),
                                     *converted,
                                     *(f"{layer.id}.geojson" for layer in case.layers), "view.json"])
        cards.append(
            f'<section class="card" id="{case.key}"><h2>{case.name}: {_md_inline(case.title)}{open_tag if case.question else ""}{permalink(case.key)}</h2>'
            + (f'<p class="question"><strong>Open question.</strong> {_md_inline(case.question)}</p>' if case.question else "")
            + f'<div class="card-body"><div class="variants">{figs}</div>'
            f'<pre class="css cscss">{cscss(case.css.rstrip())}</pre></div>'
            f'<p class="question"><strong>What should be drawn.</strong> {_md_inline(case.expected)}</p>'
            + _other_software(case, kit_dir)
            + f'<p class="kit">Render it yourself: {links}</p></section>')
    cards += [card for _, _, card in extra]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Rendering Passes</title>
<style>{CSS}{NAV_CSS}{HIGHLIGHT_CSS} pre.css {{ white-space: pre-wrap; font-size: 12px; margin: 0; flex: 1 1 320px; }}
.others {{ margin-top: 14px; border-top: 1px solid var(--line); padding-top: 10px; }}
.others .variants {{ grid-template-columns: repeat(auto-fill, minmax(260px, 380px)); }}
.others h3 {{ font-size: 15px; margin: 0 0 10px; }} .others h4 {{ font-size: 14px; margin: 12px 0 6px; }}
figure img.other {{ width: 100%; height: auto; border-radius: 6px; border: 1px solid var(--line); display: block; }}
.card table {{ border-collapse: collapse; margin: 8px 0; }} .card td, .card th {{ border: 1px solid var(--line); padding: 3px 8px; text-align: left; }}</style></head>
<body class="has-toc">
{topbar("passes.html", [(a, label) for a, label, _ in contents])}
<div class="layout has-toc">{toc(contents)}<main>
<h1>Rendering passes, zOrder and casing: test cases</h1>
<p class="lead">Cases for <a href="{ISSUE}212">#212</a>: how <code>viz.pass</code>, <code>feature.pass</code>,
<code>zOrder</code>, casings, labels and nested rules decide what is drawn on top. Cases 01 to 08 are Maxime
Collombin's (<a href="{PYCARTOSYM_PASSES}">pycartosym <code>examples/passes</code></a>), with <code>marker: null;</code>
added to each top-level rule so that no default Dot is drawn; 09 to 13 are the others listed on <a href="{ISSUE}197">#197</a>.
Where the text is open, marked <span class="badge open">open in the text</span>, the draft renderer draws each reading. All are drawn on the same roads, railway and zone, kept small so
that other software can redraw them exactly; Annex C examples 12 and 13 in <a href="{ANNEX_C_PR}">#233</a> show the
same mechanisms on a real map (roads and the railway at Otta). Each card links
a render kit: the style in both encodings, one GeoJSON file per data layer, the view, the draft renderer's image and a
README with what should be drawn (all in <a href="kit.zip">kit.zip</a>). The draft renderer implements the text, so
its image shows what the text says, not that the text is right. Under "Other software", each case shows its renders in
QGIS (set up by <a href="https://github.com/kraftto">kraftto</a> with <a href="../qgis/render_kits.py"><code>qgis/render_kits.py</code></a>) with a note on
what QGIS can't express, and the SLD/SE and MapLibre files that pycartosym writes from the style (added by Maxime
Collombin), or why it refuses. Case 14 is kraftto's: a section of an XPlanung plan, with its QGIS render. Renders
from other software are welcome as pull requests.</p>
{''.join(cards)}
</main></div>{NAV_SCRIPT}</body></html>"""


def main(argv: list[str]) -> int:
    out = Path(argv[0] if argv else "gallery")
    problems = build(out)
    zip_all(out)
    for p in problems:
        print("PROBLEM:", p)
    print(f"Wrote {len(CASES)} kits in {(out / 'kit').resolve()} and {(out / 'passes.html').resolve()}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
