"""Build gallery/requirements.html: every requirement in PR #133 and how it is checked."""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from pathlib import Path

from .gallery import COPY_SCRIPT, CSS, PR_FILES, REQUIREMENTS, _check_styles, _inline_code, decisions, style_pane
from .kit import export
from .nav import NAV_CSS, NAV_SCRIPT, permalink, toc, topbar
from .render import render
from .samples import annotate, samples

RESULTS = Path(__file__).resolve().parents[2] / "reports" / "results.json"

# Requirements checked without rendering or expression tests.
ENCODING = {
    "/req/json/schema": "every gallery and sample style is validated against the PR's JSON schema on each build",
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
    "/req/json/dot-size-color": "enforced by the PR's JSON schema (`not` on Dot), which every style is validated against",
}
NOT_IMPLEMENTED = {
    "/req/core/time": "not implemented: the draft renderer has no visualization time",
    "/req/core/expressions-system-identifiers": "partly: viz.sd and dataLayer identifiers work; `capabilities` identifiers "
                                                "are not implemented",
    "/req/labels/placement": "partly: priority and minSpacing are rendered; maxSpacing is not implemented",
    "/per/vector/image-alpha-test": "not implemented: a permission; the draft renderer has no picking and no alpha test",
}


def _results() -> dict[str, list[dict]]:
    by_req: dict[str, list[dict]] = defaultdict(list)
    if RESULTS.exists():
        for case in json.loads(RESULTS.read_text(encoding="utf-8")).values():
            by_req[case["requirement"]].append(case)
    return by_req


def _tests(cases: list[dict]) -> str:
    def tally(impl: str) -> str:
        rs = [c["results"][impl]["verdict"] for c in cases if impl in c["results"]]
        return f"{rs.count('pass')}/{len(rs)}" if rs else "–"
    return (f'<a href="../reports/report.md">{len(cases)} test case{"s" if len(cases) != 1 else ""}</a>: '
            f"draft renderer {tally('draft renderer')}, libCartoSym {tally('libCartoSym')}")


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
                evidence.append(f'card: <a href="index.html#{d.key}">{html.escape(d.title)}</a>')
            if cards_by_req.get(rid):
                status.append("card")
            for s in samples_by_req.get(rid, []):
                evidence.append(f'sample: <a href="#s-{s.key}">{html.escape(s.title)}</a>')
                if s not in class_samples:
                    class_samples.append(s)
            if samples_by_req.get(rid):
                status.append("sample")
            if tests_by_req.get(rid):
                evidence.append(_tests(tests_by_req[rid]))
                status.append("tested")
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
                f'<td>{" ".join(f"<span class=chip>{html.escape(s)}</span>" for s in status)}</td>'
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
    summary = (f"{counts['requirements']} requirements: {counts['card']} with a gallery card, {counts['sample']} with a sample "
               f"render, {counts['tested']} with test cases, {counts['encoding']} checked as encodings, "
               f"{counts['partly']} partly and {counts['not implemented']} not implemented"
               + (f", {counts['none']} with no check" if counts.get("none") else "") + ". A requirement can be checked in more than one way.")
    labels = [("", "All"), ("card", "Gallery card"), ("sample", "Sample"), ("tested", "Tested"), ("encoding", "Encoding"),
              ("partly", "Partly"), ("not implemented", "Not implemented")]
    filters = "".join(
        f'<button type="button" data-status="{st}" aria-pressed="{"true" if not st else "false"}">{lab}'
        + (f" ({counts[st]})" if st else "") + "</button>" for st, lab in labels)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Draft Requirements</title>
<style>{CSS}
.chip {{ display:inline-block; font-size: 11.5px; padding: 1px 7px; border-radius: 99px; background: var(--bg); border: 1px solid var(--line); margin: 1px 2px; white-space: nowrap; }}
.gap {{ color: #b03a2e; }} .reqtable td {{ font-size: 13.5px; vertical-align: top; }} .reqtable details {{ font-size: 13px; }}
.sample h3 {{ margin: 0 0 4px; font-size: 16px; }}
.filters {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin: 14px 0 4px; }}
.filters button {{ font: inherit; font-size: 13px; padding: 3px 10px; border-radius: 99px; border: 1px solid var(--line);
  background: var(--card); color: var(--fg); cursor: pointer; }}
.filters button[aria-pressed="true"] {{ background: var(--accent-bg); color: var(--accent); border-color: var(--accent); font-weight: 600; }}
#shown {{ font-size: 13px; color: var(--muted); }}
{NAV_CSS}</style></head><body class="has-toc">
{topbar("requirements.html", [(a, label) for a, label, _ in contents if a])}
<div class="layout has-toc">{toc(contents)}<main>
<h1>CartoSym 2.0 draft: every requirement in PR #133</h1>
<p class="lead">Each requirement with its text, how it is checked, and links to the evidence: a gallery card for judgement calls,
a sample render (below each class) for straightforward visual requirements, test cases for expressions, or a note for
encodings. Samples show what the draft renderer draws; "Check" says what to look for. {summary}</p>
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


__all__ = ["build"]
