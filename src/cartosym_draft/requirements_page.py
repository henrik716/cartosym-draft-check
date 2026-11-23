"""Build gallery/requirements.html: every requirement in the snapshot (requirements.json) and how it is checked."""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from pathlib import Path

from .gallery import COPY_SCRIPT, CSS, PR_FILES, REQUIREMENTS, _check_styles, _inline_code, decisions, style_pane
from .doc_examples import REQUIREMENT_EXAMPLES
from .kit import export
from .nav import NAV_CSS, NAV_SCRIPT, permalink, toc, topbar
from .render import render
from .samples import annotate, samples

# Requirements checked without rendering or expression tests.
ENCODING = {
    "/req/json/schema": "every gallery and sample style is validated against the snapshot's JSON schema on each build",
    "/req/json/expressions": "every style in the gallery uses CQL2-JSON expressions",
    "/req/json/include": "read by the draft renderer (`$include`, included rules first)",
    "/req/cscss/grammar": "the spec's examples 5 to 9 converted with pycartosym and parsed by libCartoSym",
    "/req/cscss/rules": "as for the grammar",
    "/req/cscss/selectors": "as for the grammar",
    "/req/cscss/expressions": "as for the grammar",
    "/req/cscss/comments": "the spec's examples contain comments; they convert",
    "/req/cscss/include": "pycartosym converts `.include` to `$include`, keeping the file's own rules and variables",
    "/req/cscss/variables": "pycartosym converts `@variables` to `$variables` and `$ref`, including variables defined by "
                            "expressions; the draft renderer resolves them",
    "/req/json/variables": "tested (variables cases) and used by the draft renderer",
    "/req/json/dot-size-color": "enforced by the snapshot's JSON schema (`not` on Dot), which every style is validated against",
}
NOT_IMPLEMENTED: dict[str, str] = {}
CHIPS = {"card": "judgement call"}  # how a status is shown, where it differs from its key
# Implemented in the draft renderer, checked by a direct call rather than a render or a harness case.
RENDERER_NOTES = {
    "/req/core/time": "the visualization date and time interval are system identifiers of the view; see the "
                      "core-time document example",
    "/req/core/expressions-system-identifiers": "`capabilities.*` are true for the classes the draft renderer "
                                                "implements (`render.CAPABILITIES`)",
    "/per/vector/image-alpha-test": "a permission, used: pixels of an Image whose alpha is below `alphaThreshold` are "
                                    "not drawn",
    "/rec/parameter-values/report-null": "each render lists the properties whose expression evaluated to NULL in an "
                                         "SVG comment and in `render.LAST_NULL_REPORTS`",
    "/per/functions/type-casts": "a permission, not used: the text leaves the conversion unspecified, so the draft "
                                 "renderer gives NULL for a wrong-type argument, as the harness cases on calls check",
    "/per/coverage/interpolation": "a permission, not used: the draft renderer draws every cell over its area from the "
                                   "full grid (`image-rendering: pixelated`), without interpolating or overviews",
    "/per/coverage/linear-light": "a permission, not used: `colorMap` colors are interpolated in sRGB",
    "/per/vector/dot-outline": "a permission, not used: Dots are drawn without an outline",
    "/per/vector/image-linear-light": "a permission, not used: the recoloring filter works in sRGB "
                                      "(`color-interpolation-filters=\"sRGB\"`)",
}

REPORTS = Path(__file__).resolve().parents[2] / "reports" / "libcartosym-main"
RESULTS = REPORTS / "results.json"  # written by CI with the latest libCartoSym, pycartosym and the draft renderer
REPORT_URL = "https://github.com/henrik716/cartosym-draft-check/blob/main/reports/libcartosym-main/report.md"
IMPLEMENTATIONS = ["draft renderer", "libCartoSym", "pycartosym"]


def load_results() -> dict[str, dict]:
    """The test cases with each implementation's result, by case name (CI's run against libCartoSym main)."""
    return json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}


def provenance() -> dict[str, str]:
    """Date, libCartoSym commit and pycartosym version of CI's report."""
    report = REPORTS / "report.md"
    text = report.read_text(encoding="utf-8") if report.exists() else ""
    m = re.search(r"^Generated (\S+) with libCartoSym \((.*?)\) and pycartosym (\S+?)\.?$", text, re.M)
    if not m:
        return {"date": "?", "libcartosym": "?", "pycartosym": "?"}
    commit = re.search(r"libCartoSym main @ (\w+)", m.group(2))
    return {"date": m.group(1), "libcartosym": f"main at {commit.group(1)}" if commit else m.group(2),
            "pycartosym": m.group(3)}


def agrees(result: dict) -> bool:
    return result["verdict"] == "pass"


def _results() -> dict[str, list[tuple[str, dict]]]:
    by_req: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for name, case in load_results().items():
        by_req[case["requirement"]].append((name, case))
    return by_req


def _anchor(rid: str) -> str:
    """GitHub's anchor for the report's heading of a requirement (### `/req/...`)."""
    return re.sub(r"[^a-z0-9 _-]", "", rid.lower()).replace(" ", "-")


def _value(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _cell(result: dict | None) -> str:
    if result is None:
        return '<td class="na" title="not run on this case">–</td>'
    detail = html.escape(_value(result.get("detail", "")))
    short = detail if len(detail) <= 90 else detail[:87] + "…"
    if agrees(result):
        return f'<td class="same" title="{detail}">same</td>'
    word = {"unsupported": "not supported", "error": "error", "CRASH": "crashed"}.get(result["verdict"], "differs")
    return f'<td class="differs" title="{detail}">{word}: {short}</td>'


def _tests(rid: str, cases: list[tuple[str, dict]]) -> str:
    """The cases of a requirement, folded, with what each implementation gave."""
    differ = {impl: sum(1 for _, c in cases if impl in c["results"] and not agrees(c["results"][impl]))
              for impl in IMPLEMENTATIONS}
    ran = [impl for impl in IMPLEMENTATIONS if any(impl in c["results"] for _, c in cases)]
    n = len(cases)
    if not any(differ.values()):
        who = (", ".join(ran[:-1]) + " and " + ran[-1]) if len(ran) > 1 else ran[0]
        verdict = f"{'all three give' if len(ran) == 3 else who + (' give' if len(ran) > 1 else ' gives')} what the text says"
    else:
        verdict = "; ".join(f"{impl} differs on {k}" for impl, k in differ.items() if k)
    rows = []
    for name, c in cases:
        given = {k: c[k] for k in ("properties", "system", "variables", "definitions") if k in c}
        with_ = ("<br><span class=with>with " + html.escape(
            ", ".join(f"{k} = {_value(v)}" for d in given.values() for k, v in d.items())) + "</span>") if given else ""
        rows.append(f'<tr><td title="{html.escape(name)}"><code>{html.escape(c["input"].strip())}</code>{with_}</td>'
                    f'<td><code>{html.escape(_value(c["expect"]))}</code></td>'
                    + "".join(_cell(c["results"].get(impl)) for impl in IMPLEMENTATIONS) + "</tr>")
    return (f'<details class="tests"><summary>{n} test case{"s" if n != 1 else ""} · {html.escape(verdict)}</summary>'
            f'<div class="table-wrap"><table><thead><tr><th>Input</th><th>The text gives</th>'
            + "".join(f"<th>{impl}</th>" for impl in IMPLEMENTATIONS)
            + f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<a class="full" href="{REPORT_URL}#{_anchor(rid)}">Full output of each implementation</a></details>')


def build(out_dir: Path) -> str:
    cards_by_req: dict[str, list] = defaultdict(list)
    for d in decisions():
        for r in d.requirements:
            cards_by_req[r].append(d)
    sample_list = samples()
    samples_by_req: dict[str, list] = defaultdict(list)
    for s in sample_list:
        for r in s.requirements:
            samples_by_req[r].append(s)
    tests_by_req = _results()
    doc_by_req: dict[str, list] = defaultdict(list)
    for ex in REQUIREMENT_EXAMPLES:
        for r in ex.requirements:
            doc_by_req[r].append(ex)

    groups: dict[str, list[str]] = defaultdict(list)
    for rid, r in REQUIREMENTS["requirements"].items():
        groups[r["file"]].append(rid)

    invalid: list[str] = []
    shown: set[str] = set()  # each sample once, under the first class that uses it
    counts: dict[str, int] = defaultdict(int)
    sections = []
    contents: list[tuple[str | None, str, bool]] = [(None, "Requirements classes", False)]
    # Core (clause 7) first, then the other classes in file order.
    for file, rids in sorted(groups.items(), key=lambda kv: (0 if "clause_7" in kv[0] else 1, kv[0])):
        rows = []
        class_samples: list = []
        for rid in rids:
            r = REQUIREMENTS["requirements"][rid]
            evidence, status = [], []
            for d in cards_by_req.get(rid, []):
                evidence.append(f'judgement call: <a href="index.html#{d.key}">{html.escape(d.title)}</a>')
            if cards_by_req.get(rid):
                status.append("card")
            for s in samples_by_req.get(rid, []):
                evidence.append(f'sample: <a href="#s-{s.key}">{html.escape(s.title)}</a>')
                if s not in class_samples:
                    class_samples.append(s)
            if samples_by_req.get(rid):
                status.append("sample")
            if tests_by_req.get(rid):
                evidence.append(_tests(rid, tests_by_req[rid]))
                status.append("tested")
            for ex in doc_by_req.get(rid, []):
                evidence.append(_inline_code(f"document example: `{ex.name}`"))
            if doc_by_req.get(rid):
                status.append("document example")
            if rid in RENDERER_NOTES:
                evidence.append(_inline_code(RENDERER_NOTES[rid]))
                status.append("implemented")
            if rid in ENCODING:
                evidence.append(_inline_code(ENCODING[rid]))
                status.append("encoding")
            if rid in NOT_IMPLEMENTED:
                evidence.append(f'<span class="gap">{_inline_code(NOT_IMPLEMENTED[rid])}</span>')
                status.append("partly" if NOT_IMPLEMENTED[rid].startswith("partly") else "not implemented")
            if not status:
                status.append("none")
                evidence.append('<span class="gap">no check yet</span>')
            for st in status:
                counts[st] += 1
            counts["requirements"] += 1
            parts = "".join(f"<li>{_inline_code(p)}</li>" for p in r["parts"])
            rows.append(
                f'<tr id="r{rid.replace("/", "-")}" data-status="{" ".join(status)}"><td><a href="{PR_FILES}{r["file"]}#L{r["line"]}"><code>{html.escape(rid)}</code></a>'
                f'<details><summary>text</summary><ul>{parts}</ul></details></td>'
                f'<td>{" ".join(f"<span class=chip>{html.escape(CHIPS.get(s, s))}</span>" for s in status)}</td>'
                f'<td>{"<br>".join(evidence)}</td></tr>')
        figs = []
        for s in class_samples:
            if s.key in shown:
                continue  # its requirement rows link to it above
            shown.add(s.key)
            panels = []
            for i, p in enumerate(s.panels):
                invalid += _check_styles({f"panel-{i + 1}": p.style}, f"sample-{s.key}")
                svg = annotate(render(p.style, p.layers, p.view, p.options, anchors=p.anchors), p)
                links = export(f"sample-{s.key}-{i + 1}", s.title, {"style.cs.json": p.style}, p.layers, p.view, out_dir)
                kit = " · ".join(f'<a href="{html.escape(u)}">{html.escape(n)}</a>' for n, u in links)
                cap = f"<figcaption>{html.escape(p.caption)}<span class='vnote'>{kit}</span></figcaption>"
                panels.append(f"<figure>{svg}{cap}</figure>")
            panes = "".join(
                style_pane(f"json-{s.key}-{i + 1}", p.style,
                           f"sample-{s.key}" + (f"-{i + 1}" if len(s.panels) > 1 else ""),
                           "Style (CartoSym-JSON)" + (f": {p.caption}" if p.caption and len(s.panels) > 1 else ""))
                for i, p in enumerate(s.panels))
            reqs = " ".join(f"<code>{html.escape(r)}</code>" for r in s.requirements)
            figs.append(f'<section class="card sample" id="s-{s.key}"><h3>{html.escape(s.title)}</h3>'
                        f'<div class="reqs">{reqs}</div><p class="question"><strong>Check:</strong> {_inline_code(s.check)}</p>'
                        f'<div class="card-body"><div class="variants">{"".join(panels)}</div><div>{panes}</div></div></section>')
        title = file.split("/")[-1].replace(".adoc", "")
        if title == "clause_7_core":
            title = "core (clause 7)"
        class_id = "c-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        contents.append((class_id, f"{title} ({len(rids)})", False))
        sections.append(
            f'<div class="req-class" id="{class_id}"><section class="card"><h2>{html.escape(title)}{permalink(class_id)}</h2>'
            f'<p class="note">{html.escape(file)}</p>'
            f'<div class="table-wrap"><table class="reqtable"><thead><tr><th>Requirement</th><th>Checked by</th>'
            f'<th>Evidence</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>{"".join(figs)}</div>')
    if invalid:
        raise SystemExit("Sample styles that do not validate against the CartoSym-JSON schema:\n  " + "\n  ".join(invalid))
    summary = (f"{counts['requirements']} requirements: {counts['card']} with a judgement call, {counts['sample']} with a sample "
               f"render, {counts['tested']} with test cases, {counts['encoding']} checked as encodings, "
               f"{counts['partly']} partly and {counts['not implemented']} not implemented"
               + (f", {counts['none']} with no check" if counts.get("none") else "") + ". A requirement can be checked in more than one way.")
    labels = [("", "All"), ("card", "Judgement call"), ("sample", "Sample"), ("tested", "Tested"), ("encoding", "Encoding"),
              ("partly", "Partly"), ("not implemented", "Not implemented")]
    prov = provenance()
    filters = "".join(
        f'<button type="button" data-status="{st}" aria-pressed="{"true" if not st else "false"}">{lab}'
        + (f" ({counts[st]})" if st else "") + "</button>" for st, lab in labels)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Requirements</title>
<style>{CSS}
.chip {{ display:inline-block; font-size: 11.5px; padding: 1px 7px; border-radius: 99px; background: var(--bg); border: 1px solid var(--line); margin: 1px 2px; white-space: nowrap; }}
.gap {{ color: #b03a2e; }} .reqtable td {{ font-size: 13.5px; vertical-align: top; }} .reqtable details {{ font-size: 13px; }}
.sample h3 {{ margin: 0 0 4px; font-size: 16px; }}
.filters {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin: 14px 0 4px; }}
.filters button {{ font: inherit; font-size: 13px; padding: 3px 10px; border-radius: 99px; border: 1px solid var(--line);
  background: var(--card); color: var(--fg); cursor: pointer; }}
.filters button[aria-pressed="true"] {{ background: var(--accent-bg); color: var(--accent); border-color: var(--accent); font-weight: 600; }}
#shown {{ font-size: 13px; color: var(--muted); }}
details.tests {{ margin-top: 2px; }}
details.tests > summary {{ cursor: pointer; }}
details.tests table {{ font-size: 12.5px; margin: 6px 0 4px; }}
details.tests td, details.tests th {{ padding: 3px 8px; vertical-align: top; }}
details.tests td.same {{ color: var(--muted); }}
details.tests td.differs {{ color: #b03a2e; }}
details.tests td.na {{ color: var(--muted); text-align: center; }}
details.tests .with {{ color: var(--muted); font-size: 12px; }}
details.tests a.full {{ font-size: 12.5px; }}
.provenance {{ font-size: 13px; color: var(--muted); }}
{NAV_CSS}</style></head><body class="has-toc">
{topbar("requirements.html", [(a, label) for a, label, _ in contents if a])}
<div class="layout has-toc">{toc(contents)}<main>
<h1>CartoSym 2.0 Part 1: every requirement and how it is checked</h1>
<p class="lead">Each requirement with its text, how it is checked, and links to the evidence: a judgement call where the
text leaves a choice, a sample render (below each class) for straightforward visual requirements, test cases for
expressions, or a note for encodings. Samples show what the draft renderer draws; "Check" says what to look for. {summary}</p>
<p class="provenance">Requirement text from <code>{html.escape(REQUIREMENTS["branch"])}</code> at
<code>{html.escape(REQUIREMENTS["commit"])}</code>. Test cases as run on {prov["date"]} with libCartoSym {html.escape(prov["libcartosym"])},
pycartosym {html.escape(prov["pycartosym"])} and the draft renderer. pycartosym does not evaluate expressions: "same" there
means it converts the input to the case's CQL2-JSON, or parses it. Where an implementation gives something else, the
text or the implementation may be the one to change.</p>
<div class="filters" role="group" aria-label="Show requirements checked by">{filters}<span id="shown"></span></div>
{"".join(sections)}
</main></div>{COPY_SCRIPT}{NAV_SCRIPT}
<script>
(() => {{
  const buttons = [...document.querySelectorAll(".filters button")];
  const shown = document.getElementById("shown");
  function apply(status) {{
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.status === status)));
    let n = 0;
    for (const cls of document.querySelectorAll(".req-class")) {{
      let visible = 0;
      for (const row of cls.querySelectorAll("tr[data-status]")) {{
        const on = !status || row.dataset.status.split(" ").includes(status) || row.dataset.status.includes(status);
        row.hidden = !on; if (on) visible++;
      }}
      cls.hidden = visible === 0;
      cls.querySelectorAll(".sample").forEach((s) => (s.hidden = !!status && status !== "sample"));
      n += visible;
    }}
    shown.textContent = status ? `${{n}} requirement${{n === 1 ? "" : "s"}} shown` : "";
  }}
  buttons.forEach((b) => b.addEventListener("click", () => apply(b.getAttribute("aria-pressed") === "true" ? "" : b.dataset.status)));
}})();
</script>
</body></html>"""


__all__ = ["agrees", "build", "load_results", "provenance"]
