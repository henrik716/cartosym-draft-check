"""Time validation of deeply nested expressions against the Part 1 and Part 3 schemas.

Usage: python schema-tests/depth.py [checkout] [--max-depth N] [--timeout S] [--write]

For each depth d, three selectors are validated with python-jsonschema, each in its own process with a
time limit:
  and   d nested `and`s, every leaf `x < 2` (valid)
  junk  the same, with one leaf `x < {"foo": 1}` (invalid)
  mixed d nested levels that alternate the expression types: and / = / + / ?: / concatenate (valid)

Written on 2026-11-17 after kraftto's comment on opengeospatial/cartographic-symbology#188, which reported
that validation time grew exponentially with nesting depth. With --write, the documents are also written to
out/depth-docs.json for js/depth.mjs (Ajv and Hyperjump).
"""
import json, multiprocessing as mp, os, sys, time

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)

op = lambda o, *a: {"op": o, "args": list(a)}
P = lambda n: {"property": n}
LEAF = op("<", P("x"), 2)
BAD = op("<", P("x"), {"foo": 1})


def nested_and(d, bad=False):
    e = BAD if bad else LEAF
    for _ in range(d):
        e = op("and", e, LEAF)
    return e


def mixed(d):
    """A valid boolean expression with d levels that pass through every expression type."""
    num, s = op("+", P("x"), 1), "a"
    b = LEAF
    for i in range(d):
        k = i % 4
        if k == 0: num = op("+", op("?:", b, num, 1), 1)          # numeric, through ?:
        elif k == 1: s = op("concatenate", op("lowerCase", s), op("format", "%d", num))  # text, holding a numeric
        elif k == 2: b = op("and", op("=", s, "b"), b)               # boolean, holding text
        else: b = op("or", op("<", num, 3), op("not", b))           # boolean, holding numeric
    return op("and", b, op("=", s, "c"), op("<", num, 4))


def docs(d):
    return {"and": nested_and(d), "junk": nested_and(d, True), "mixed": mixed(d)}


def _run(repo, key, kind, d, q):
    from run import validators, REPO
    import run
    run.REPO = repo
    V = validators()
    doc = {"stylingRules": [{"selector": docs(d)[kind]}]}
    t = time.perf_counter()
    ok = V[key].is_valid(doc)
    q.put((ok, time.perf_counter() - t))


def timed(repo, key, kind, d, timeout):
    q = mp.Queue()
    p = mp.Process(target=_run, args=(repo, key, kind, d, q))
    p.start(); p.join(timeout)
    if p.is_alive():
        p.terminate(); p.join()
        return None, None
    return q.get()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    repo = os.path.abspath(args[0] if args else os.path.join(here, "..", "..", "cartographic-symbology"))
    opt = lambda name, default: next((type(default)(sys.argv[i + 1]) for i, a in enumerate(sys.argv) if a == name), default)
    max_depth, timeout = opt("--max-depth", 16), opt("--timeout", 30.0)
    if "--write" in sys.argv:
        os.makedirs(os.path.join(here, "out"), exist_ok=True)
        json.dump({d: docs(d) for d in range(1, max_depth + 1)}, open(os.path.join(here, "out", "depth-docs.json"), "w"))
    print(f"Schemas from {repo}; time limit {timeout:g} s")
    expected = {"and": True, "junk": False, "mixed": True}
    bad = 0
    for key in ("part1", "part3"):
        for kind in ("and", "junk", "mixed"):
            cells = []
            for d in (1, 2, 3, 4, 6, 8, 12, 16):
                if d > max_depth: break
                ok, t = timed(repo, key, kind, d, timeout)
                if t is None:
                    cells.append(f"{d}: >{timeout:g}s"); bad += 1
                    break
                if ok != expected[kind]: bad += 1
                cells.append(f"{d}: {t*1000:.0f}ms" + ("" if ok == expected[kind] else " WRONG"))
            print(f"{key} {kind:5} | " + " | ".join(cells))
    sys.exit(1 if bad else 0)
