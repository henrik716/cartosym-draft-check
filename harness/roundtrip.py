"""Round trips through CQL2-JSON and CartoSym-JSON with cs-canif and pycartosym; writes reports/roundtrip.md.

Usage: uv run python harness/roundtrip.py [path to a cartographic-symbology checkout]  (default ../cartographic-symbology)

Expressions (the expression cases in cases/, as run.py runs them):
  1. CQL2-Text -> CQL2-JSON; compared with the case's own CQL2-JSON where it has one
  2. that CQL2-JSON -> CQL2-Text, written with non-ASCII characters as they are; for a case with any, also
     with them as \\u escapes, which should give the same CQL2-Text
  3. that CQL2-Text -> CQL2-JSON again; the round trip is stable if this is the CQL2-JSON of step 1
Styles (each 1-core/examples/<name>.cscss with its <name>.cs.json in the checkout):
  1. CartoSym-CSS -> CartoSym-JSON; compared with the example's CartoSym-JSON
  2. that CartoSym-JSON -> CartoSym-CSS -> CartoSym-JSON; stable if it is the CartoSym-JSON of step 1
  3. the example's CartoSym-JSON -> CartoSym-CSS -> CartoSym-JSON; compared with the example's CartoSym-JSON

JSON is compared as data (member order and the spelling of numbers do not matter; true is not 1), and
`$comment` members (CSS comments kept in the JSON) are left out; a difference is reported as the path of
the first one. roundtrip.json also keeps each conversion's output, to see a difference in full. libCartoSym is cs-canif from the pip package, or the
build given by CS_CANIF (see adapters.py); REPORT_DIR chooses where the report goes, as for run.py.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import yaml

import adapters

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / os.environ.get("REPORT_DIR", "reports")
LIBCARTOSYM = os.environ.get("LIBCARTOSYM_LABEL") or (
    f"cs-canif from `cartosym` {version('cartosym')}, `ecrt` {version('ecrt')}")
WORK = adapters.WORK / "roundtrip"
LOCAL_WORK = str(WORK) + os.sep


# ------------------------------------------------------------------ converters
# Each takes the source text and returns an Outcome whose value is the converted text.

def _canif_convert(src: str, src_ext: str, dst_ext: str) -> adapters.Outcome:
    WORK.mkdir(parents=True, exist_ok=True)
    inp, out = WORK / f"in.{src_ext}", WORK / f"out.{dst_ext}"
    inp.write_text(src, encoding="utf-8")
    out.unlink(missing_ok=True)
    result = adapters._canif("convert", str(inp), str(out))
    if result.status != "ok":
        return result
    if not out.exists():
        return adapters.Outcome("error", detail=result.value or "no output file")
    return adapters.Outcome("ok", value=out.read_text(encoding="utf-8"), detail=result.value or "")


def _py_expr(src: str, src_ext: str, dst_ext: str) -> adapters.Outcome:
    from pycartosym import cql2
    try:
        if src_ext == "cql2":
            return adapters.Outcome("ok", value=json.dumps(cql2.to_cql2_json(cql2.parse_text(src))))
        return adapters.Outcome("ok", value=cql2.to_cql2_text(json.loads(src)))
    except Exception as exc:  # noqa: BLE001 - any failure is a result
        return adapters.Outcome("error", detail=f"{type(exc).__name__}: {exc}")


def _py_style(src: str, src_ext: str, dst_ext: str) -> adapters.Outcome:
    WORK.mkdir(parents=True, exist_ok=True)
    ext = {"cscss": "cscss", "csjson": "cs.json"}
    inp, out = WORK / f"in.{ext[src_ext]}", WORK / f"out.{ext[dst_ext]}"
    inp.write_text(src, encoding="utf-8")
    out.unlink(missing_ok=True)
    proc = adapters._cartosym_cli(str(inp), "-q", "--force", "-o", str(out))
    msg = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0 or not out.exists():
        return adapters.Outcome("error", detail=msg or f"exit code {proc.returncode}")
    return adapters.Outcome("ok", value=out.read_text(encoding="utf-8"), detail=msg)


EXPR = {"libCartoSym": _canif_convert, "pycartosym": _py_expr}
STYLE = {"libCartoSym": _canif_convert, "pycartosym": _py_style}


# ------------------------------------------------------------------ comparing

def diff(a, b, path: str = "") -> str | None:
    """The path of the first difference between two JSON values, or None if they are the same data."""
    def show(v):
        s = json.dumps(v, ensure_ascii=False)
        return s if len(s) <= 50 else s[:47] + "..."
    num = (int, float)
    if isinstance(a, bool) or isinstance(b, bool) or not (isinstance(a, num) and isinstance(b, num)):
        if type(a) is not type(b):
            return f"{path or '/'}: `{show(a)}` vs `{show(b)}`"
    if isinstance(a, dict):
        for k in sorted((set(a) | set(b)) - {"$comment"}):
            if k not in b:
                return f"{path}/{k}: missing"
            if k not in a:
                return f"{path}/{k}: added (`{show(b[k])}`)"
            d = diff(a[k], b[k], f"{path}/{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path or '/'}: {len(a)} items vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = diff(x, y, f"{path}/{i}")
            if d:
                return d
        return None
    return None if a == b else f"{path or '/'}: `{show(a)}` vs `{show(b)}`"


def _load(text: str):
    try:
        return json.loads(text), None
    except ValueError as exc:
        return None, f"not JSON ({exc})"


def _fail(outcome: adapters.Outcome) -> str:
    first = (outcome.detail or outcome.status).strip().splitlines()[0] if (outcome.detail or outcome.status) else ""
    return f"{outcome.status}: {first.replace(LOCAL_WORK, '')}"


# ------------------------------------------------------------------ the checks

NO_JSON = object()  # a case without its own CQL2-JSON (a case's JSON can be null)


def expression_trip(convert, text: str, case_json=NO_JSON) -> dict:
    """CQL2-Text -> CQL2-JSON -> CQL2-Text -> CQL2-JSON."""
    r = {"to_json": None, "vs_case": "-", "text": None, "stable": None, "escaped": "-"}
    o = convert(text, "cql2", "cql2json")
    if o.status != "ok":
        r["to_json"] = _fail(o)
        return r
    j1, err = _load(o.value)
    if err:
        r["to_json"] = err
        return r
    r["to_json"], r["json"] = "ok", j1
    if case_json is not NO_JSON:
        r["vs_case"] = diff(case_json, j1) or "same"
    # Non-ASCII characters as they are, as cs-canif writes them (RFC 8259 allows both forms).
    plain = json.dumps(j1, ensure_ascii=False)
    o = convert(plain, "cql2json", "cql2")
    if o.status != "ok":
        r["text"], r["stable"] = _fail(o), "-"
        return r
    r["text"] = o.value.strip()
    # The same CQL2-JSON with non-ASCII characters as \u escapes (json.dumps's default), which a reader
    # must also accept: it should give the same CQL2-Text.
    escaped = json.dumps(j1)
    if escaped != plain:
        e = convert(escaped, "cql2json", "cql2")
        if e.status != "ok":
            r["escaped"] = _fail(e)
        else:
            r["escaped"] = "same" if e.value.strip() == r["text"] else f"`{e.value.strip()}`"
    o = convert(r["text"], "cql2", "cql2json")
    if o.status != "ok":
        r["stable"] = "text does not parse: " + _fail(o)
        return r
    j2, err = _load(o.value)
    r["stable"] = err or diff(j1, j2) or "yes"
    return r


def style_trip(convert, css: str, spec_json) -> dict:
    r = {"css_to_json": None, "vs_spec": "-", "stable": "-", "json_trip": None}
    o = convert(css, "cscss", "csjson")
    if o.status != "ok":
        r["css_to_json"] = _fail(o)
    else:
        j1, err = _load(o.value)
        r["css_to_json"] = err or "ok"
        r["json"] = j1 if not err else o.value
        if not err:
            r["vs_spec"] = diff(spec_json, j1) or "same"
            r["stable"] = _json_css_json(convert, j1, j1)
    r["json_trip"] = _json_css_json(convert, spec_json, spec_json)
    return r


def _json_css_json(convert, start, expected) -> str:
    o = convert(json.dumps(start, ensure_ascii=False), "csjson", "cscss")
    if o.status != "ok":
        return "to CartoSym-CSS: " + _fail(o)
    o = convert(o.value, "cscss", "csjson")
    if o.status != "ok":
        return "back to CartoSym-JSON: " + _fail(o)
    j, err = _load(o.value)
    return err or diff(expected, j) or "yes"


# ------------------------------------------------------------------ report

def _cell(v) -> str:
    return "-" if v is None else str(v).replace("|", "\\|").replace("\n", " ")


def main(spec: Path) -> int:
    cases = [c for f in sorted((ROOT / "cases").glob("*.yaml")) for c in yaml.safe_load(f.read_text(encoding="utf-8"))
             if c["kind"] == "expression" and not c.get("draft_only")]
    examples = sorted((spec / "1-core" / "examples").glob("*.cscss"),
                      key=lambda p: (int(p.name.split("-")[0]), p.name))
    examples = [p for p in examples if p.with_suffix(".cs.json").exists()]
    spec_rev = subprocess.run(["git", "-C", str(spec), "log", "-1", "--format=%h"], capture_output=True,
                              text=True).stdout.strip()
    spec_branch = subprocess.run(["git", "-C", str(spec), "branch", "--show-current"], capture_output=True,
                                 text=True).stdout.strip()

    expr = {impl: {c["id"]: expression_trip(fn, c["input"], c.get("json", NO_JSON)) for c in cases} for impl, fn in EXPR.items()}
    style = {}
    for impl, fn in STYLE.items():
        style[impl] = {}
        for p in examples:
            spec_json = json.loads(p.with_suffix(".cs.json").read_text(encoding="utf-8"))
            style[impl][p.stem] = style_trip(fn, p.read_text(encoding="utf-8"), spec_json)
            print(f"{impl:12} {p.stem:32} {style[impl][p.stem]}")

    n_json = sum(1 for c in cases if "json" in c)
    lines = [
        "# Round trips through CQL2-JSON and CartoSym-JSON",
        "",
        f"Generated {datetime.date.today()} by [`harness/roundtrip.py`](../harness/roundtrip.py) with libCartoSym "
        f"({LIBCARTOSYM}) and pycartosym {version('pycartosym')}; the style examples are those of "
        f"opengeospatial/cartographic-symbology at `{spec_rev}`" + (f" (branch `{spec_branch}`)" if spec_branch else "")
        + ".",
        "",
        "This checks conversion only: whether each implementation writes the same JSON as the case or the example, "
        "and whether converting back and forth gives the same JSON again. It does not evaluate anything; "
        "[`report.md`](report.md) has the evaluation results. A difference from a case or an example may be in the "
        "case, the example or the implementation.",
        "",
        "## Summary",
        "",
        "| | " + " | ".join(EXPR) + " |",
        "|---|" + "---|" * len(EXPR),
    ]

    def count(rows, key, ok):
        return sum(1 for r in rows if r[key] == ok)

    for label, key, ok, total in [
        (f"Expressions converted to CQL2-JSON (of {len(cases)})", "to_json", "ok", None),
        (f"Same CQL2-JSON as the case (of the {n_json} cases that give one)", "vs_case", "same", None),
        (f"Text → JSON → text → JSON gives the same JSON (of {len(cases)})", "stable", "yes", None),
    ]:
        lines.append(f"| {label} | " + " | ".join(str(count(expr[i].values(), key, ok)) for i in EXPR) + " |")
    n_escaped = max(sum(1 for r in expr[i].values() if r["escaped"] != "-") for i in EXPR)
    lines.append(f"| CQL2-JSON with `\\u` escapes gives the same CQL2-Text (of the {n_escaped} cases with non-ASCII "
                 "text) | " + " | ".join(str(count(expr[i].values(), "escaped", "same")) for i in EXPR) + " |")
    for label, key, ok in [
        (f"Examples converted from CartoSym-CSS to CartoSym-JSON (of {len(examples)})", "css_to_json", "ok"),
        (f"Same CartoSym-JSON as the example (of {len(examples)})", "vs_spec", "same"),
        (f"CSS → JSON → CSS → JSON gives the same JSON (of {len(examples)})", "stable", "yes"),
        (f"The example's JSON → CSS → JSON gives it back (of {len(examples)})", "json_trip", "yes"),
    ]:
        lines.append(f"| {label} | " + " | ".join(str(count(style[i].values(), key, ok)) for i in STYLE) + " |")

    lines += ["", "## How they are run", "",
              "- **libCartoSym:** `cs-canif convert in.<ext> out.<ext>`, with `.cql2` (CQL2-Text), `.cql2json`, "
              "`.cscss` and `.csjson` (`.cs.json` is read by cs-canif as a Mapbox GL style).",
              "- **pycartosym:** expressions with `cql2.to_cql2_json(cql2.parse_text(text))` and "
              "`cql2.to_cql2_text(json)`; styles with `cartosym in.cscss -o out.cs.json` and back.",
              "- JSON is compared as data: member order and the spelling of numbers (`2` and `2.0`) do not matter, "
              "but `true` is not `1`. `$comment` members, which keep CSS comments in the JSON, are left out. "
              "CQL2-JSON is converted back to CQL2-Text with non-ASCII characters as they are, and, for the cases "
              "that have any, also with them as `\\u` escapes (both are JSON, RFC 8259), which should give the same "
              "CQL2-Text. "
              "[`roundtrip.json`](roundtrip.json) has each conversion's output. A difference is shown as the path of the first one, with the expected value "
              "(the case's or the example's, or the first conversion's for the round trip) first.",
              ""]

    lines += ["## Expressions", ""]
    for impl in EXPR:
        lines += [f"### {impl}", "", "| Case | Input | To CQL2-JSON | Same as the case | Back to CQL2-Text | "
                  "From `\\u` escapes | Stable |", "|---|---|---|---|---|---|---|"]
        for c in cases:
            r = expr[impl][c["id"]]
            inp = c["input"].strip().replace("|", "\\|")
            text = r["text"]  # the CQL2-Text written, or why none was
            text_cell = "-" if text is None else _cell(f"`{text}`" if r["stable"] != "-" else text)
            lines.append(f"| {c['id']} | `{inp}` | {_cell(r['to_json'])} | {_cell(r['vs_case'])} | {text_cell} | "
                         f"{_cell(r['escaped'])} | {_cell(r['stable'])} |")
        lines.append("")

    lines += ["## Styles", ""]
    for impl in STYLE:
        lines += [f"### {impl}", "", "| Example | CSS to JSON | Same as the example's JSON | CSS → JSON → CSS → JSON "
                  "stable | Example's JSON → CSS → JSON |", "|---|---|---|---|---|"]
        for name, r in style[impl].items():
            lines.append(f"| {name} | {_cell(r['css_to_json'])} | {_cell(r['vs_spec'])} | {_cell(r['stable'])} | "
                         f"{_cell(r['json_trip'])} |")
        lines.append("")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "roundtrip.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    (REPORTS / "roundtrip.json").write_text(json.dumps({"expressions": expr, "styles": style}, indent=1,
                                                       ensure_ascii=False), encoding="utf-8")
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "cartographic-symbology").resolve()))
