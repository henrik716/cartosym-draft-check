"""Validate the schema test documents against the Part 1 and Part 3 CartoSym-JSON schemas.

Usage: python schema-tests/run.py [path to a cartographic-symbology checkout]  (default: ../cartographic-symbology)

Writes out/rows.json (the documents, for js/check.mjs) and out/python.json (the results),
and prints how many results differ from the expected outcome. See README.md.
"""
import glob, json, os, re, sys

here = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "..", "cartographic-symbology"))
BASE = "https://cartosym.test/"  # base URI for the relative $ref from Part 3 to Part 1; test only
SCHEMAS = {"part1": "1-core/schemas/CartoSym-JSON.schema.json",
           "part3": "3-geometry/schemas/CartoSym-JSON-3-geometry.schema.json"}
PART3_OP = re.compile(r'"op": "(s|t)_')  # documents using an operation defined in Part 3


def load_rows():
    sys.path.insert(0, here)
    from cases_expressions import cases as expr_cases
    from cases_other import cases as other_cases
    rows = []
    for group, name, expected, expr, note in expr_cases:
        rows.append({"set": "expressions", "name": name, "valid": expected == "valid",
                     "doc": {"stylingRules": [{"selector": expr}]}})
    examples = sorted(glob.glob(os.path.join(REPO, "1-core", "examples", "*.cs.json")),
                      key=lambda p: int(os.path.basename(p).split("-")[0]))
    for p in examples:
        rows.append({"set": "CartoSym-JSON examples", "name": os.path.basename(p), "valid": True,
                     "doc": json.load(open(p, encoding="utf8"))})
    cql2 = sorted(glob.glob(os.path.join(here, "cql2-examples", "*.json")))
    if not cql2:
        sys.exit("No CQL2 examples: run fetch_cql2_examples.py first")
    for p in cql2:
        rows.append({"set": "CQL2-JSON examples", "name": os.path.basename(p), "valid": True,
                     "doc": {"stylingRules": [{"selector": json.load(open(p, encoding="utf8"))}]}})
    for name, valid, doc in other_cases:
        rows.append({"set": "other changes", "name": name, "valid": valid, "doc": doc})
    for r in rows:
        r["part3_op"] = bool(PART3_OP.search(json.dumps(r["doc"])))
    return rows


def validators():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    reg, docs = Registry(), {}
    for key, rel in SCHEMAS.items():
        d = json.load(open(os.path.join(REPO, rel), encoding="utf8"))
        Draft202012Validator.check_schema(d)
        d = dict(d, **{"$id": BASE + rel})
        docs[key] = d
        reg = reg.with_resource(BASE + rel, Resource.from_contents(d))
    return {k: Draft202012Validator(docs[k], registry=reg) for k in SCHEMAS}


def summarize(label, rows, results):
    """The expected outcomes are those of Part 3. Part 1 accepts the Part 3 operations as generic
    function calls, so for Part 1 only the documents without such operations are compared."""
    p3 = [r for r, ok in zip(rows, results["part3"]) if ok != r["valid"]]
    p1 = [r for r, ok in zip(rows, results["part1"]) if ok != r["valid"] and not r["part3_op"]]
    n1 = sum(not r["part3_op"] for r in rows)
    print(f"{label:9} Part 3: {len(p3)} wrong of {len(rows)} | Part 1: {len(p1)} wrong of {n1} documents without Part 3 operations")
    for r in p3[:20]: print(f"   Part 3 wrong: [{r['set']}] {r['name']} (expected {'valid' if r['valid'] else 'invalid'})")
    for r in p1[:20]: print(f"   Part 1 wrong: [{r['set']}] {r['name']} (expected {'valid' if r['valid'] else 'invalid'})")
    return len(p3) + len(p1)


if __name__ == "__main__":
    import importlib.metadata as md
    rows = load_rows()
    V = validators()
    results = {k: [V[k].is_valid(r["doc"]) for r in rows] for k in SCHEMAS}
    os.makedirs(os.path.join(here, "out"), exist_ok=True)
    json.dump(rows, open(os.path.join(here, "out", "rows.json"), "w", encoding="utf8"))
    json.dump(results, open(os.path.join(here, "out", "python.json"), "w", encoding="utf8"))
    sets = {}
    for r in rows: sets[r["set"]] = sets.get(r["set"], 0) + 1
    print(f"Schemas from {REPO}")
    print("Documents:", ", ".join(f"{n} {s}" for s, n in sets.items()), f"({len(rows)} in all)")
    print(f"python-jsonschema {md.version('jsonschema')} (referencing {md.version('referencing')})")
    sys.exit(1 if summarize("python", rows, results) else 0)
