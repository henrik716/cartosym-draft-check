"""Produce results.json for cases.json.

Usage: python evaluator/run.py   (from the indep-expr-3 folder)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import cql2_eval  # noqa: E402
import cscss_parse  # noqa: E402

SPEC_SCHEMA = os.path.join(BASE, "spec", "1-core", "schemas", "CartoSym-JSON.schema.json")


def load_system_ids():
    with open(SPEC_SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    enum = schema["$defs"]["systemIdentifier"]["properties"]["sysId"]["enum"]
    cscss_parse.SYSTEM_IDS.update(enum)


def run_expression(case):
    ctx_args = dict(
        props=case.get("properties"),
        system=case.get("system"),
        defs=case.get("definitions"),
        overrides=case.get("variables"),
    )
    text = case.get("cql2_text")
    json_tree = case.get("cql2_json", None) if "cql2_json" in case else None
    text_tree, text_err = None, None
    if text is not None:
        try:
            text_tree = cscss_parse.parse_expression(text)
        except cscss_parse.SyntaxErr as e:
            text_err = str(e)
    primary = json_tree if json_tree is not None else text_tree
    if "cql2_json" in case and json_tree is None:
        primary = None  # JSON null is not a valid tree here
    if primary is None and json_tree is None and text_tree is None:
        return {"error": "cannot parse: " + str(text_err)}, None
    try:
        value = cql2_eval.to_result(cql2_eval.ev(primary, cql2_eval.Ctx(**ctx_args)))
        result = value
    except cql2_eval.EvalErr as e:
        result = {"error": str(e)}
    except Exception as e:  # defensive: report, do not hide
        result = {"error": "internal: %s: %s" % (type(e).__name__, e)}

    cross = None
    if json_tree is not None and text_tree is not None and "random" not in text:
        try:
            tv = cql2_eval.to_result(cql2_eval.ev(text_tree, cql2_eval.Ctx(**ctx_args)))
        except cql2_eval.EvalErr as e:
            tv = {"error": str(e)}
        if tv != result:
            cross = {"json": result, "text": tv}
    elif json_tree is not None and text_tree is None and text is not None:
        cross = {"json": result, "text": "not parseable: " + str(text_err)}
    return result, cross


def main():
    load_system_ids()
    with open(os.path.join(BASE, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)
    results = {}
    crosses = {}
    for case in cases:
        cid = case["id"]
        if case["kind"] == "style":
            results[cid] = cscss_parse.check_style(case["style"])
        elif case["kind"] == "expression":
            result, cross = run_expression(case)
            results[cid] = result
            if cross:
                crosses[cid] = cross
        else:
            raise SystemExit("unknown kind for " + cid)
    with open(os.path.join(BASE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(HERE, "crosscheck.json"), "w", encoding="utf-8") as f:
        json.dump(crosses, f, ensure_ascii=False, indent=2)
        f.write("\n")
    errors = {k: v for k, v in results.items() if isinstance(v, dict) and "error" in v}
    print("cases:", len(cases), "results:", len(results))
    print("error results:", json.dumps(errors, ensure_ascii=False))
    print("encoding cross-check differences:", json.dumps(crosses, ensure_ascii=False))


if __name__ == "__main__":
    main()
