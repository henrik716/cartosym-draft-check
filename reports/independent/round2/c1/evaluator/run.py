"""Evaluate cases.json and write results.json.

Usage (from the test folder):
    uv run --no-project python evaluator/run.py
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lexer import LexError  # noqa: E402
from parser import ParseError, parse_expression  # noqa: E402
from tojson import to_json, ConvertError  # noqa: E402
from evaluate import evaluate, Context, EvalError  # noqa: E402
from style import css_to_json, json_pointer, StyleError  # noqa: E402

ROOT = os.path.dirname(HERE)


def ctx_for(case):
    return Context(case.get("properties"), case.get("system"), case.get("definitions"), case.get("variables"))


def jsonable(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return {"error": f"result is {v}"}
    return v


def eval_json(expr, case):
    try:
        return jsonable(evaluate(expr, ctx_for(case)))
    except EvalError as e:
        return {"error": str(e)}


def eval_text(text, case):
    try:
        ast = parse_expression(text)
        expr = to_json(ast)
    except (LexError, ParseError, ConvertError) as e:
        return {"error": f"syntax: {e}"}, None
    return eval_json(expr, case), expr


def run_style(case):
    try:
        doc = css_to_json(case["style"])
        return json_pointer(doc, case.get("at", ""))
    except (LexError, ParseError, ConvertError, StyleError) as e:
        return {"error": str(e)}


def main():
    random.seed(0)
    with open(os.path.join(ROOT, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)
    results, crosscheck = {}, {}
    for c in cases:
        if c["kind"] == "style":
            results[c["id"]] = run_style(c)
            continue
        text_result, text_json = eval_text(c["cql2_text"], c)
        if "cql2_json" in c:
            r = eval_json(c["cql2_json"], c)
            results[c["id"]] = r
            same_json = text_json == c["cql2_json"]
            if r != text_result or not same_json:
                crosscheck[c["id"]] = {"json_result": r, "text_result": text_result,
                                       "text_parsed_as": text_json, "same_json": same_json}
        else:
            results[c["id"]] = text_result
            crosscheck.setdefault("_text_only_parse", {})[c["id"]] = text_json
    with open(os.path.join(ROOT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "crosscheck.json"), "w", encoding="utf-8") as f:
        json.dump(crosscheck, f, ensure_ascii=False, indent=1)
    print(len(results), "cases")


if __name__ == "__main__":
    main()
