"""Run all test cases and write reports/report.md.

Usage: uv run python harness/run.py [cases/<file>.yaml ...]
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path

import yaml

import adapters

ROOT = Path(__file__).resolve().parent.parent

PASS, FAIL, UNSUPPORTED, CRASH, ERROR = "pass", "FAIL", "unsupported", "CRASH", "error"


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


def run_case(case: dict) -> dict[str, tuple[str, str]]:
    kind, expected = case["kind"], case["expect"]
    results = {}
    if kind == "expression":
        if not case.get("draft_only"):
            results["libCartoSym"] = _verdict(adapters.libcartosym_eval(case["input"]), expected)
            parsed = adapters.pycartosym_parse_expression(case["input"])
            results["pycartosym"] = (PASS, "parses") if parsed.status == "ok" else (UNSUPPORTED, "does not parse as CQL2")
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
        f"Generated {datetime.date.today()} with libCartoSym (cs-canif from `cartosym` {version('cartosym')}, "
        f"`ecrt` {version('ecrt')}) and pycartosym {version('pycartosym')}.",
        "",
        "Expected values are what the **draft requirement** says. `FAIL` means the implementation disagrees with the draft, "
        "which may mean the draft or the implementation is wrong. pycartosym does not evaluate expressions, so for expression "
        "cases it only reports whether the expression parses. The draft renderer is `cartosym_draft` in this "
        "repository, which implements the draft requirements; a FAIL there means it does not do what the draft says.",
        "",
        "## Summary",
        "",
        "| Implementation | " + " | ".join([PASS, FAIL, UNSUPPORTED, CRASH, ERROR]) + " |",
        "|---|" + "---|" * 5,
    ]
    for impl, counts in sorted(totals.items()):
        lines.append(f"| {impl} | " + " | ".join(str(counts.get(v, 0)) for v in [PASS, FAIL, UNSUPPORTED, CRASH, ERROR]) + " |")

    lines += ["", "## Results by requirement", ""]
    for req in sorted(by_req):
        lines += [f"### `{req}`", "", "| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |",
                  "|---|---|---|---|---|---|"]
        for case, results in by_req[req]:
            cells = []
            for impl in ("libCartoSym", "pycartosym", "draft renderer"):
                v, d = results.get(impl, ("-", ""))
                cells.append(f"{v}: {d}".replace("|", "\\|").replace("\n", " ") if d else v)
            inp = case["input"].strip().replace("\n", " ").replace("|", "\\|")
            if len(inp) > 60:
                inp = inp[:57] + "..."
            lines.append(f"| {case['id']} | `{inp}` | `{case['expect']}` | {cells[0]} | {cells[1]} | {cells[2]} |")
            if case.get("note"):
                lines.append(f"| | _{case['note']}_ | | | | |")
        lines.append("")

    results_json = {case["id"]: {"requirement": req, "input": case["input"], "expect": case["expect"],
                                 "results": {impl: {"verdict": v, "detail": d} for impl, (v, d) in results.items()}}
                    for req, rows in by_req.items() for case, results in rows}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "results.json").write_text(json.dumps(results_json, indent=1, ensure_ascii=False), encoding="utf-8")

    out = ROOT / "reports" / "report.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
