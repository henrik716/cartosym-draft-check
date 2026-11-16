"""Evaluate every case of cases.json; write results.json and print a cross-check of
the CQL2-JSON result against the result of parsing cql2_text with our own parser."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cartosym_eval as ce  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_expr(tree, case):
    ctx = ce.Context(case.get("properties"), case.get("system"), case.get("definitions"), case.get("variables"))
    try:
        return ce.evaluate(tree, ctx)
    except ce.EvalError as ex:
        return {"error": str(ex)}


def main():
    with open(os.path.join(ROOT, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)
    results = {}
    report = []
    for c in cases:
        cid = c["id"]
        if c["kind"] == "style":
            r, why = ce.check_style(c["style"])
            results[cid] = r
            report.append((cid, r, why or ""))
            continue
        notes = []
        text_tree = None
        try:
            text_tree = ce.parse_expression(c["cql2_text"], tuple(ce.canonical_sysid(k) for k in (c.get("system") or {})), notes)
            text_res = run_expr(text_tree, c)
        except (ce.LexError, ce.ParseError) as ex:
            text_res = {"error": "parse: %s" % ex}
        if "cql2_json" in c:
            res = run_expr(c["cql2_json"], c)
            src = "json"
        else:
            res = text_res
            src = "text"
        results[cid] = res
        same = json.dumps(res) == json.dumps(text_res)
        report.append((cid, json.dumps(res, ensure_ascii=False), "%s%s%s" % (
            src, "" if same else "  TEXT-DIFFERS: " + json.dumps(text_res, ensure_ascii=False),
            ("  notes=" + ",".join(notes)) if notes else "")))
    with open(os.path.join(ROOT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        f.write("\n")
    for row in report:
        print(" | ".join(str(x) for x in row))
    print("cases:", len(cases), "results:", len(results))


if __name__ == "__main__":
    main()
