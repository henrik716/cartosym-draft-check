"""Write the generated schema test documents to cases.json, so they can be read without running Python.

Usage: python schema-tests/export_cases.py          (writes schema-tests/cases.json)
       python schema-tests/export_cases.py --check  (exits with 1 if cases.json is out of date)

cases.json holds the two sets built by code, cases_expressions.py and cases_other.py: a JSON array with
one object per document, one per line, with
  set       "expressions" or "other changes"
  name      the case name
  valid     the expected outcome against the Part 3 schema (which includes Part 1)
  part3     true if the document uses an `s_*` or `t_*` operation, which Part 1 accepts as a generic
            function call; for Part 1, compare only the documents where this is false
  group     the operator or function tested (expressions only)
  note      why the outcome is expected, where the case says so (may be empty)
  document  the CartoSym-JSON document
The other two sets of README.md are files already: the examples of the cartographic-symbology checkout
(1-core/examples/*.cs.json) and the CQL2-JSON examples (fetch_cql2_examples.py).
"""
import json, os, re, sys

here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, "cases.json")
PART3_OP = re.compile(r'"op": "(s|t)_')


def build() -> str:
    sys.path.insert(0, here)
    from cases_expressions import cases as expr_cases
    from cases_other import cases as other_cases
    rows = [{"set": "expressions", "name": name, "valid": expected == "valid", "group": group, "note": note,
             "document": {"stylingRules": [{"selector": expr}]}}
            for group, name, expected, expr, note in expr_cases]
    rows += [{"set": "other changes", "name": name, "valid": valid, "document": doc}
             for name, valid, doc in other_cases]
    for r in rows:
        r["part3"] = bool(PART3_OP.search(json.dumps(r["document"])))
    keys = ("set", "name", "valid", "part3", "group", "note", "document")
    lines = [json.dumps({k: r[k] for k in keys if k in r}, ensure_ascii=False) for r in rows]
    return "[\n" + ",\n".join(lines) + "\n]\n"


if __name__ == "__main__":
    text = build()
    if "--check" in sys.argv[1:]:
        current = open(OUT, encoding="utf8").read() if os.path.exists(OUT) else ""  # newlines read as \n
        if current != text:
            sys.exit("schema-tests/cases.json is out of date: run python schema-tests/export_cases.py")
        print("schema-tests/cases.json is up to date")
    else:
        with open(OUT, "w", encoding="utf8", newline="\n") as f:
            f.write(text)
        print(f"Wrote {OUT} ({text.count(chr(10)) - 2} documents)")
