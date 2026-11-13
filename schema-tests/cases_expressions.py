"""Per-operator test cases for CartoSym-JSON expressions.

Each case: (group, name, expected, selector-expression, note).
Expected is "valid" or "invalid", judged from the Part 1 requirements and CQL2,
counting only arity and structure; type-conversion questions (#163) are left out.
The spatial and temporal cases are judged against Part 3, which defines those operations.

Written on 2026-11-10 for the schema discussion on opengeospatial/cartographic-symbology#140,
and used unchanged for the schema PR.
"""
P = lambda n: {"property": n}
S = lambda n: {"sysId": n}
op = lambda o, *a: {"op": o, "args": list(a)}
TS = {"timestamp": "2020-01-01T00:00:00Z"}
DATE = {"date": "2020-01-01"}
IV = {"interval": ["2020-01-01", "2020-12-31"]}
IV_OPEN = {"interval": ["..", "2020-12-31"]}
PT = {"type": "Point", "coordinates": [1, 2]}
LINE = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
POLY = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
BBOX = {"bbox": [0, 0, 1, 1]}
JUNK = {"foo": 1}
COND = op("?:", op(">", P("x"), 1), 1, 0)
B = op("<", P("x"), 2)  # a boolean expression

# wrappers: put an expression of a given type into a selector
num = lambda e: op("<", e, 1)
chr_ = lambda e: op("=", e, "a")
geo = lambda e: op("s_intersects", e, P("geom"))
tmp = lambda e: op("t_after", e, P("t"))
arr = lambda e: op("a_contains", e, [1])

cases = []
def add(group, name, exp, expr, note=""):
    cases.append((group, name, exp, expr, note))

# --- logical
for o in ("and", "or"):
    add(o, f"{o}(B, B)", "valid", op(o, B, B))
    add(o, f"{o}(B, B, B)", "valid", op(o, B, B, B), "CQL2 and/or take 2 or more")
    add(o, f"{o}(true, B)", "valid", op(o, True, B))
    add(o, f"{o}(not B, {o}(B, B))", "valid", op(o, op("not", B), op(o, B, B)))
    add(o, f"{o}(B)", "invalid", op(o, B))
    add(o, f"{o}()", "invalid", op(o))
    add(o, f"{o}(B, 1)", "invalid", op(o, B, 1))
    add(o, f"{o}(B, junk)", "invalid", op(o, B, JUNK))
add("not", "not(B)", "valid", op("not", B))
add("not", "not(true)", "valid", op("not", True))
add("not", "not(not(B))", "valid", op("not", op("not", B)))
add("not", "not(s_intersects(..))", "valid", op("not", op("s_intersects", P("g"), PT)))
add("not", "not()", "invalid", op("not"))
add("not", "not(B, B)", "invalid", op("not", B, B))
add("not", "not(1)", "invalid", op("not", 1))
add("not", "not('a')", "invalid", op("not", "a"))
add("boolean", "true", "valid", True)
add("boolean", "1 as selector", "invalid", 1)
add("boolean", "'a' as selector", "invalid", "a")

# --- comparison
for o in ("=", "<>", "<", ">", "<=", ">="):
    add(o, f"x {o} 1", "valid", op(o, P("x"), 1))
    add(o, f"1 {o} x", "valid", op(o, 1, P("x")))
    add(o, f"x + 1 {o} y", "valid", op(o, op("+", P("x"), 1), P("y")))
    add(o, f"viz.sd {o} 1000", "valid", op(o, S("viz.sd"), 1000))
    add(o, f"?: {o} 1", "valid", op(o, COND, 1))
    add(o, f"t {o} timestamp", "valid", op(o, P("t"), TS))
    add(o, f"f(x) {o} 1", "valid", op(o, op("pow", P("x"), 2), 1))
    add(o, f"{o}(x)", "invalid", op(o, P("x")))
    add(o, f"{o}(x, 1, 2)", "invalid", op(o, P("x"), 1, 2))
    add(o, f"x {o} junk", "invalid", op(o, P("x"), JUNK))
    add(o, f"x {o} [1, 2]", "invalid", op(o, P("x"), [1, 2]))
for o in ("=", "<>"):
    add(o, f"name {o} 'a'", "valid", op(o, P("name"), "a"))
    add(o, f"casei(name) {o} casei('a')", "valid", op(o, op("casei", P("name")), op("casei", "a")))
    add(o, f"dataLayer.id {o} 'Roads'", "valid", op(o, S("dataLayer.id"), "Roads"))
    add(o, f"b {o} true", "valid", op(o, P("b"), True))
    add(o, f"(x < 1) {o} true", "valid", op(o, B, True))

# --- like
add("like", "name like 'a%'", "valid", op("like", P("name"), "a%"))
add("like", "casei(name) like casei('a%')", "valid", op("like", op("casei", P("name")), op("casei", "a%")))
add("like", "accenti(name) like accenti('é%')", "valid", op("like", op("accenti", P("name")), op("accenti", "é%")))
add("like", "name like casei(accenti('a%'))", "valid", op("like", P("name"), op("casei", op("accenti", "a%"))))
add("like", "lowerCase(name) like 'a%'", "valid", op("like", op("lowerCase", P("name")), "a%"))
add("like", "like(name)", "invalid", op("like", P("name")))
add("like", "like()", "invalid", op("like"))
add("like", "like(name, 'a%', 'b')", "invalid", op("like", P("name"), "a%", "b"))
add("like", "name like 1", "invalid", op("like", P("name"), 1))
add("like", "name like other (pattern not a literal)", "invalid", op("like", P("name"), P("other")), "CQL2 requires a literal pattern; #156 may relax this")

# --- text relations (CartoSym)
for o in ("contains", "startsWith", "endsWith"):
    add(o, f"{o}(name, 'a')", "valid", op(o, P("name"), "a"))
    add(o, f"{o}(name, other)", "valid", op(o, P("name"), P("other")))
    add(o, f"{o}(lowerCase(name), 'a')", "valid", op(o, op("lowerCase", P("name")), "a"))
    add(o, f"{o}(name)", "invalid", op(o, P("name")))
    add(o, f"{o}()", "invalid", op(o))
    add(o, f"{o}(name, 'a', 'b')", "invalid", op(o, P("name"), "a", "b"))
    add(o, f"{o}(name, junk)", "invalid", op(o, P("name"), JUNK))

# --- between, in, isNull
add("between", "x between 1 and 5", "valid", op("between", P("x"), 1, 5))
add("between", "1 between 0 and 2", "valid", op("between", 1, 0, 2))
add("between", "x + 1 between lo and hi", "valid", op("between", op("+", P("x"), 1), P("lo"), P("hi")))
add("between", "viz.sd between 0 and 1e6", "valid", op("between", S("viz.sd"), 0, 1000000))
add("between", "between(x, 1)", "invalid", op("between", P("x"), 1))
add("between", "between(x, 1, 2, 3)", "invalid", op("between", P("x"), 1, 2, 3))
add("between", "x between 'a' and 'b'", "invalid", op("between", P("x"), "a", "b"), "CQL2 between is numeric")
add("between", "x between junk and 2", "invalid", op("between", P("x"), JUNK, 2))
add("in", "x in (1, 2)", "valid", op("in", P("x"), [1, 2]))
add("in", "name in ('a', 'b')", "valid", op("in", P("name"), ["a", "b"]))
add("in", "casei(name) in (casei('a'))", "valid", op("in", op("casei", P("name")), [op("casei", "a")]))
add("in", "x + 1 in (y, 2)", "valid", op("in", op("+", P("x"), 1), [P("y"), 2]))
add("in", "in(x)", "invalid", op("in", P("x")))
add("in", "x in 1 (list not an array)", "invalid", op("in", P("x"), 1))
add("in", "in(x, [1], [2])", "invalid", op("in", P("x"), [1], [2]))
add("in", "x in (junk)", "invalid", op("in", P("x"), [JUNK]))
add("isNull", "x is null", "valid", op("isNull", P("x")))
add("isNull", "x + 1 is null", "valid", op("isNull", op("+", P("x"), 1)))
add("isNull", "casei(name) is null", "valid", op("isNull", op("casei", P("name"))))
add("isNull", "geom function is null", "valid", op("isNull", op("s_buffer", P("geom"), 1)))
add("isNull", "isNull()", "invalid", op("isNull"))
add("isNull", "isNull(x, y)", "invalid", op("isNull", P("x"), P("y")))
add("isNull", "isNull with args not an array", "invalid", {"op": "isNull", "args": P("x")})
add("isNull", "isNull(junk)", "invalid", op("isNull", JUNK))

# --- spatial predicates
for o in ("s_contains", "s_crosses", "s_disjoint", "s_equals", "s_intersects",
          "s_overlaps", "s_touches", "s_within", "s_covers", "s_coveredBy"):
    add(o, f"{o}(geom, point)", "valid", op(o, P("geom"), PT))
    add(o, f"{o}(geom, other)", "valid", op(o, P("geom"), P("other")))
    add(o, f"{o}(geom)", "invalid", op(o, P("geom")))
    add(o, f"{o}(geom, point, point)", "invalid", op(o, P("geom"), PT, PT))
    add(o, f"{o}(geom, 1)", "invalid", op(o, P("geom"), 1))
add("s_intersects", "s_intersects(line, polygon)", "valid", op("s_intersects", LINE, POLY))
add("s_intersects", "s_intersects(geom, bbox)", "valid", op("s_intersects", P("geom"), BBOX))
add("s_intersects", "s_intersects(feature.geometry, point)", "valid", op("s_intersects", S("feature.geometry"), PT))
add("s_intersects", "s_intersects(geom, ?:)", "valid", op("s_intersects", P("geom"), op("?:", B, PT, POLY)))
add("s_intersects", "s_intersects(geom, Point without coordinates)", "invalid", op("s_intersects", P("geom"), {"type": "Point"}))
add("s_intersects", "s_intersects()", "invalid", op("s_intersects"))

# --- geometry functions (CartoSym)
for o in ("s_intersection", "s_union", "s_difference", "s_symDifference"):
    add(o, f"{o}(geom, point)", "valid", geo(op(o, P("geom"), PT)))
    add(o, f"{o}(point, polygon)", "valid", geo(op(o, PT, POLY)))
    add(o, f"{o}(geom)", "invalid", geo(op(o, P("geom"))))
    add(o, f"{o}(geom, point, point)", "invalid", geo(op(o, P("geom"), PT, PT)))
for o in ("s_convexHull", "s_envelope"):
    add(o, f"{o}(geom)", "valid", geo(op(o, P("geom"))))
    add(o, f"{o}(polygon)", "valid", geo(op(o, POLY)))
    add(o, f"{o}()", "invalid", geo(op(o)))
    add(o, f"{o}(geom, geom)", "invalid", geo(op(o, P("geom"), P("geom"))))
add("s_buffer", "s_buffer(geom, 10)", "valid", geo(op("s_buffer", P("geom"), 10)))
add("s_buffer", "s_buffer(point, d)", "valid", geo(op("s_buffer", PT, P("d"))))
add("s_buffer", "s_buffer(geom)", "invalid", geo(op("s_buffer", P("geom"))))
add("s_buffer", "s_buffer(geom, 10, 1)", "invalid", geo(op("s_buffer", P("geom"), 10, 1)))
add("s_buffer", "s_buffer(geom, 'a')", "invalid", geo(op("s_buffer", P("geom"), "a")))

# --- temporal predicates
for o in ("t_after", "t_before", "t_contains", "t_disjoint", "t_during", "t_equals",
          "t_finishedBy", "t_finishes", "t_intersects", "t_meets", "t_metBy",
          "t_overlappedBy", "t_overlaps", "t_startedBy", "t_starts"):
    add(o, f"{o}(t, timestamp)", "valid", op(o, P("t"), TS))
    add(o, f"{o}(t, interval)", "valid", op(o, P("t"), IV))
    add(o, f"{o}(t)", "invalid", op(o, P("t")))
    add(o, f"{o}(t, ts, ts)", "invalid", op(o, P("t"), TS, TS))
    add(o, f"{o}(t, 1)", "invalid", op(o, P("t"), 1))
add("t_intersects", "t_intersects(date, open interval)", "valid", op("t_intersects", DATE, IV_OPEN))
add("t_intersects", "t_intersects(viz.timeInterval, interval of properties)", "valid", op("t_intersects", S("viz.timeInterval"), {"interval": [P("start"), P("end")]}))
add("t_intersects", "t_intersects(t, junk)", "invalid", op("t_intersects", P("t"), JUNK))
add("t_intersects", "t_intersects(t, interval of 3)", "invalid", op("t_intersects", P("t"), {"interval": ["2020-01-01", "2020-06-01", "2020-12-31"]}))

# --- array predicates
for o in ("a_containedBy", "a_contains", "a_equals", "a_overlaps"):
    add(o, f"{o}(a, [1, 2])", "valid", op(o, P("a"), [1, 2]))
    add(o, f"{o}([1], [1, 2])", "valid", op(o, [1], [1, 2]))
    add(o, f"{o}(a, b)", "valid", op(o, P("a"), P("b")))
    add(o, f"{o}(['a'], a)", "valid", op(o, ["a"], P("a")))
    add(o, f"{o}(a)", "invalid", op(o, P("a")))
    add(o, f"{o}(a, [1], [2])", "invalid", op(o, P("a"), [1], [2]))
    add(o, f"{o}(a, 1)", "invalid", op(o, P("a"), 1))

# --- arithmetic
for o in ("+", "-", "*", "/", "^"):
    add(o, f"x {o} 1", "valid", num(op(o, P("x"), 1)))
    add(o, f"1 {o} 2", "valid", num(op(o, 1, 2)))
    add(o, f"(x + 1) {o} viz.sd", "valid", num(op(o, op("+", P("x"), 1), S("viz.sd"))))
    add(o, f"pow(x, 2) {o} ?:", "valid", num(op(o, op("pow", P("x"), 2), COND)))
    add(o, f"{o}(x)", "invalid", num(op(o, P("x"))))
    add(o, f"{o}(x, 1, 2)", "invalid", num(op(o, P("x"), 1, 2)))
    add(o, f"x {o} 'a'", "invalid", num(op(o, P("x"), "a")))
    add(o, f"x {o} junk", "invalid", num(op(o, P("x"), JUNK)))
for o in ("%", "div"):
    add(o, f"x {o} 2 (CQL2 operator)", "valid", num(op(o, P("x"), 2)), "not defined in CartoSym-JSON; passes as a function call")

# --- bitwise
for o in ("bitAnd", "bitOr", "bitXor", "<<", ">>"):
    add(o, f"{o}(x, 1)", "valid", num(op(o, P("x"), 1)))
    add(o, f"{o}(x + 1, y)", "valid", num(op(o, op("+", P("x"), 1), P("y"))))
    add(o, f"{o}(x)", "invalid", num(op(o, P("x"))))
    add(o, f"{o}(x, 1, 2)", "invalid", num(op(o, P("x"), 1, 2)))
    add(o, f"{o}(x, 2.5)", "invalid", num(op(o, P("x"), 2.5)), "bitwise operands are integers")
add("bitAnd", "bitAnd(x, 'FF') (hex)", "valid", num(op("bitAnd", P("x"), "FF")))
add("bitAnd", "bitAnd(x, 'FFzz') (not hex)", "invalid", num(op("bitAnd", P("x"), "FFzz")))
add("bitNot", "bitNot(x)", "valid", num(op("bitNot", P("x"))))
add("bitNot", "bitNot(bitAnd(x, 1))", "valid", num(op("bitNot", op("bitAnd", P("x"), 1))))
add("bitNot", "bitNot()", "invalid", num(op("bitNot")))
add("bitNot", "bitNot(x, 1)", "invalid", num(op("bitNot", P("x"), 1)))

# --- conditional
add("?:", "x > 1 ? 1 : 0", "valid", num(COND))
add("?:", "b ? 'a' : 'b'", "valid", chr_(op("?:", B, "a", "b")))
add("?:", "nested ?:", "valid", num(op("?:", B, 1, COND)))
add("?:", "?: as selector (b ? true : false)", "valid", op("?:", B, True, False))
add("?:", "?:(B, 1)", "invalid", num(op("?:", B, 1)))
add("?:", "?:(B, 1, 0, 2)", "invalid", num(op("?:", B, 1, 0, 2)))
add("?:", "?:(1, 1, 0) (condition not boolean)", "invalid", num(op("?:", 1, 1, 0)))
add("?:", "?:(B, 1, junk)", "invalid", num(op("?:", B, 1, JUNK)))

# --- character functions
for o in ("casei", "accenti", "lowerCase", "upperCase"):
    add(o, f"{o}(name)", "valid", chr_(op(o, P("name"))))
    add(o, f"{o}('A')", "valid", chr_(op(o, "A")))
    add(o, f"{o}(concatenate(a, b))", "valid", chr_(op(o, op("concatenate", P("a"), P("b")))))
    add(o, f"{o}()", "invalid", chr_(op(o)))
    add(o, f"{o}(a, b)", "invalid", chr_(op(o, P("a"), P("b"))))
    add(o, f"{o}(junk)", "invalid", chr_(op(o, JUNK)))
add("concatenate", "concatenate(a, 'b')", "valid", chr_(op("concatenate", P("a"), "b")))
add("concatenate", "concatenate('a', 'b', 'c')", "valid", chr_(op("concatenate", "a", "b", "c")))
add("concatenate", "concatenate(lowerCase(a), b)", "valid", chr_(op("concatenate", op("lowerCase", P("a")), P("b"))))
add("concatenate", "concatenate(a)", "invalid", chr_(op("concatenate", P("a"))))
add("concatenate", "concatenate()", "invalid", chr_(op("concatenate")))
add("concatenate", "concatenate(a, junk)", "invalid", chr_(op("concatenate", P("a"), JUNK)))
add("substitute", "substitute(n, 'a', 'b')", "valid", chr_(op("substitute", P("n"), "a", "b")))
add("substitute", "substitute(lowerCase(n), p, q)", "valid", chr_(op("substitute", op("lowerCase", P("n")), P("p"), P("q"))))
add("substitute", "substitute(n, 'a')", "invalid", chr_(op("substitute", P("n"), "a")))
add("substitute", "substitute(n, 'a', 'b', 'c')", "invalid", chr_(op("substitute", P("n"), "a", "b", "c")))
add("substitute", "substitute(n, 'a', junk)", "invalid", chr_(op("substitute", P("n"), "a", JUNK)))
add("format", "format('%d', x)", "valid", chr_(op("format", "%d", P("x"))))
add("format", "format('%s %s', a, b)", "valid", chr_(op("format", "%s %s", P("a"), P("b"))))
add("format", "format('x')", "valid", chr_(op("format", "x")))
add("format", "format(f, x + 1)", "valid", chr_(op("format", P("f"), op("+", P("x"), 1))))
add("format", "format()", "invalid", chr_(op("format")))
add("format", "format(1, x) (format not a string)", "invalid", chr_(op("format", 1, P("x"))))
add("format", "format('%d', junk)", "invalid", chr_(op("format", "%d", JUNK)))

# --- function calls (clause 15 and custom)
for f, args in (("pow", (P("x"), 2)), ("sqrt", (P("x"),)), ("abs", (op("-", P("x"), 1),)),
                ("min", (P("x"), P("y"))), ("max", (1, COND)), ("round", (S("viz.sd"),)),
                ("floor", (P("x"),)), ("sin", (op("*", P("a"), 2),)), ("myFn", ()),
                ("myFn", (P("x"), "a", True, [1, 2]))):
    add("function", f"{f}({len(args)} args)", "valid", num(op(f, *args)))
add("function", "myFn(geom) in a spatial predicate", "valid", geo(op("myFn", P("geom"))))
add("function", "myFn(t) in a temporal predicate", "valid", tmp(op("myFn", P("t"))))
add("function", "myFn(a) in an array predicate", "valid", arr(op("myFn", P("a"))))
add("function", "myBool(x) as selector", "valid", op("myBool", P("x")))
add("function", "myFn(junk)", "invalid", num(op("myFn", JUNK)))
add("function", "args not an array", "invalid", num({"op": "myFn", "args": P("x")}))
add("function", "no args member", "invalid", num({"op": "myFn"}))

# --- identifiers and literals
add("identifiers", "unknown sysId", "invalid", op("=", S("viz.nothing"), 1))
add("identifiers", "property not a string", "invalid", op("=", {"property": 1}, 1))
add("literals", "date literal", "valid", op("t_after", P("t"), DATE))
add("literals", "bare date string as instant", "invalid", op("t_after", P("t"), "2020-01-01"), "CQL2-JSON instants are objects")
