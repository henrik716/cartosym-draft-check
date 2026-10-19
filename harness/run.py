"""Run all test cases and write reports/report.md.

Usage: uv run python harness/run.py [cases/<file>.yaml ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path

import yaml

import adapters

ROOT = Path(__file__).resolve().parent.parent
# Where the report goes, and how libCartoSym is described in it: the pip
# package by default, or a build from source (see CS_CANIF in adapters.py).
REPORTS = ROOT / os.environ.get("REPORT_DIR", "reports")
LIBCARTOSYM = os.environ.get("LIBCARTOSYM_LABEL") or (
    f"cs-canif from `cartosym` {version('cartosym')}, `ecrt` {version('ecrt')}")

PASS, FAIL, UNSUPPORTED, CRASH, ERROR = "pass", "FAIL", "unsupported", "CRASH", "error"
LOCAL_WORK = str(ROOT / "work") + os.sep  # replaced by "work/" in the reports


def _same(actual: str, expected) -> bool:
    # Ignore quoting: libCartoSym prints strings as 'abc', the draft renderer as abc.
    expected = str(expected).strip().strip("'").lower()
    actual = actual.strip().strip("'").lower()
    try:
        return abs(float(actual) - float(expected)) < 1e-9
    except ValueError:
        return actual == expected


def _verdict(outcome: adapters.Outcome, expected) -> tuple[str, str]:
    if outcome.status == "crash":
        return CRASH, outcome.detail
    if outcome.status == "unsupported":
        return UNSUPPORTED, outcome.detail.splitlines()[0] if outcome.detail else ""
    if outcome.status != "ok":
        return ERROR, outcome.detail.splitlines()[0] if outcome.detail else ""
    if _same(outcome.value, expected):
        return PASS, outcome.value
    if outcome.value.strip() == "null" and str(expected).strip().lower() != "null":
        return UNSUPPORTED, "returned `null` (function or operator not recognised)"
    return FAIL, f"got `{outcome.value}`, draft expects `{expected}`"


def _expr_text(value) -> str:
    """A short CQL2-Text form of a value in a case's definitions (numbers, @references, binary operations)."""
    if isinstance(value, dict) and "$ref" in value:
        return "@" + value["$ref"].rsplit("/", 1)[-1]
    if isinstance(value, dict) and "property" in value:
        return value["property"]
    if isinstance(value, dict) and len(value.get("args", [])) == 2:
        a, b = value["args"]
        return f"{_expr_text(a)} {value['op']} {_expr_text(b)}"
    return json.dumps(value) if isinstance(value, (dict, list, str)) else adapters._format(value)


def _values(case: dict) -> list[str]:
    """The values a case is evaluated with, as short `name = value` texts."""
    out = [f"{k} = {_expr_text(v)}" for k, v in case.get("properties", {}).items()]
    out += [f"{k} = {_expr_text(v)}" for k, v in case.get("system", {}).items()]
    out += [f"@{k} = {_expr_text(v)}" for k, v in case.get("definitions", {}).items()]
    out += [f"@{k} = {_expr_text(v)} (set by the application)" for k, v in case.get("variables", {}).items()]
    return out


def _pycartosym_verdict(case: dict) -> tuple[str, str]:
    """pycartosym does not evaluate expressions: compare its CQL2-JSON with the case's, or check that it parses."""
    if "json" not in case:
        parsed = adapters.pycartosym_parse_expression(case["input"])
        return (PASS, "parses") if parsed.status == "ok" else (UNSUPPORTED, "does not parse as CQL2")
    converted = adapters.pycartosym_to_json(case["input"])
    if converted.status != "ok":
        return UNSUPPORTED, "does not parse as CQL2"
    if converted.value == case["json"]:
        return PASS, "converts to the case's CQL2-JSON"
    return FAIL, f"converts to `{json.dumps(converted.value)}`, case has `{json.dumps(case['json'])}`"


def run_case(case: dict) -> dict[str, tuple[str, str]]:
    kind, expected = case["kind"], case["expect"]
    results = {}
    if kind == "expression":
        if not case.get("draft_only"):
            results["libCartoSym"] = _verdict(adapters.libcartosym_eval(case["input"]), expected)
            results["pycartosym"] = _pycartosym_verdict(case)
        results["draft renderer"] = _verdict(adapters.draft_eval(
            case["input"], case.get("json"), case.get("properties"), case.get("variables"), case.get("definitions"),
            case.get("system")),
            expected)
    elif kind == "style":
        fmt = case["format"]
        results["pycartosym"] = _verdict(adapters.pycartosym_validate_style(case["input"], fmt), expected)
        if fmt == "cscss":
            results["libCartoSym"] = _verdict(adapters.libcartosym_parse_style(case["input"], fmt), expected)
    else:
        raise ValueError(f"unknown kind {kind!r} in case {case['id']}")
    return results


def main(paths: list[str]) -> int:
    files = [Path(p) for p in paths] or sorted((ROOT / "cases").glob("*.yaml"))
    by_req: dict[str, list] = defaultdict(list)
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for f in files:
        for case in yaml.safe_load(f.read_text(encoding="utf-8")):
            results = run_case(case)
            by_req[case["requirement"]].append((case, results))
            for impl, (verdict, _) in results.items():
                totals[impl][verdict] += 1
            line = "  ".join(f"{impl}={v}" for impl, (v, _) in results.items())
            print(f"{case['id']:45} {line}")

    lines = [
        "# CartoSym draft requirements vs implementations",
        "",
        f"Generated {datetime.date.today()} with libCartoSym ({LIBCARTOSYM}) and pycartosym {version('pycartosym')}.",
        "",
        "Expected values are what the **draft requirement** says. `FAIL` means the implementation disagrees with the draft, "
        "which may mean the draft or the implementation is wrong. pycartosym does not evaluate expressions, so for expression "
        "cases it is checked on converting them to CQL2-JSON (see below). The draft renderer is `cartosym_draft` in this "
        "repository, which implements the draft requirements; a FAIL there means it does not do what the draft says.",
        "",
        "## Summary",
        "",
        "| Implementation | " + " | ".join([PASS, FAIL, UNSUPPORTED, CRASH, ERROR]) + " |",
        "|---|" + "---|" * 5,
    ]
    for impl, counts in sorted(totals.items()):
        lines.append(f"| {impl} | " + " | ".join(str(counts.get(v, 0)) for v in [PASS, FAIL, UNSUPPORTED, CRASH, ERROR]) + " |")

    cases = [case for rows in by_req.values() for case, _ in rows]
    n_json = sum(1 for c in cases if c.get("kind") == "expression" and "json" in c)
    n_draft_only = sum(1 for c in cases if c.get("draft_only"))
    n_style = sum(1 for c in cases if c.get("kind") == "style")
    lines += [
        "",
        "## How the cases are run",
        "",
        f"- **libCartoSym:** the Input text is written to `expr.cql2` and evaluated with `cs-canif eval expr.cql2` "
        f"({LIBCARTOSYM}).",
        "- **pycartosym:** pycartosym does not evaluate expressions. Where a case gives its own CQL2-JSON "
        f"({n_json} cases), the Input text is converted with `pycartosym.cql2.to_cql2_json(cql2.parse_text(input))` "
        "and passes if the result is that CQL2-JSON; otherwise it passes if `pycartosym.cql2.parse_text(input)` "
        "parses it.",
        "- **draft renderer:** `cartosym_draft.evaluate.evaluate(expression, Context(...))`. Where a case gives its own "
        "CQL2-JSON, that is what it evaluates, and the result is marked _(CQL2-JSON)_, so it does not depend on "
        "pycartosym's parser; otherwise the Input text is converted with pycartosym as above.",
        "- **Values:** feature properties, system identifiers, style variables (`@name`) and variables set by the "
        "application that a case is evaluated with are listed under its input (_with …_).",
        f"- **Draft renderer only** ({n_draft_only} cases): cases that need such values. The harness does not pass "
        "them to `cs-canif` or pycartosym, so those columns show `-`.",
    ]
    if n_style:
        lines.append(f"- **Styles** ({n_style} cases): libCartoSym converts them with `cs-canif convert style.cscss "
                     "style-out.cscss` (valid if it converts); pycartosym checks them with `cartosym validate`.")
    lines += [
        "",
        "The cases are in [`cases/`](../cases/), the calls in [`harness/adapters.py`](../harness/adapters.py), and "
        "every result with the implementation's full output in [`results.json`](results.json).",
    ]

    lines += ["", "## Results by requirement", ""]
    for req in sorted(by_req):
        lines += [f"### `{req}`", "", "| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |",
                  "|---|---|---|---|---|---|"]
        for case, results in by_req[req]:
            cells = []
            for impl in ("libCartoSym", "pycartosym", "draft renderer"):
                v, d = results.get(impl, ("-", ""))
                d = d.replace(LOCAL_WORK, "work/")  # no local paths in the report
                cell = f"{v}: {d}".replace("|", "\\|").replace("\n", " ") if d else v
                if impl == "draft renderer" and impl in results and "json" in case:
                    cell += " _(CQL2-JSON)_"
                cells.append(cell)
            inp = case["input"].strip().replace("\n", " ").replace("|", "\\|")
            if len(inp) > 60:
                inp = inp[:57] + "..."
            inp = f"`{inp}`"
            if _values(case):
                inp += "<br>with " + ", ".join(f"`{v}`".replace("|", "\\|") for v in _values(case))
            lines.append(f"| {case['id']} | {inp} | `{adapters._format(case['expect'])}` | {cells[0]} | {cells[1]} | "
                         f"{cells[2]} |")
            if case.get("note"):
                lines.append(f"| | _{case['note']}_ | | | | |")
        lines.append("")

    results_json = {case["id"]: {"requirement": req, "input": case["input"], "expect": case["expect"],
                                 **{k: case[k] for k in ("json", "properties", "system", "definitions", "variables",
                                                         "draft_only") if k in case},
                                 "results": {impl: {"verdict": v, "detail": d.replace(LOCAL_WORK, "work/")}
                                             for impl, (v, d) in results.items()}}
                    for req, rows in by_req.items() for case, results in rows}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "results.json").write_text(json.dumps(results_json, indent=1, ensure_ascii=False), encoding="utf-8")

    out = REPORTS / "report.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
