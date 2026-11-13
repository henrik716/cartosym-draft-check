"""Test cases for the schema changes outside the expression definitions.

Each case: (name, expected valid, CartoSym-JSON document). Written for the schema PR (2026-11-13/14).
"""
sym = lambda s: {"stylingRules": [{"symbolizer": s}]}
sel = lambda x: {"stylingRules": [{"selector": x}]}
S = lambda n: {"sysId": n}
P = lambda n: {"property": n}
op = lambda o, *a: {"op": o, "args": list(a)}

cases = [
    # dotpattern (#166)
    ("dotpattern distance array", True, sym({"fill": {"dotpattern": {"distance": [{"px": 5}, {"px": 5}]}}})),
    ("dotpattern distance object", True, sym({"fill": {"dotpattern": {"distance": {"horizontal": 5, "vertical": {"mm": 2}}}}})),
    ("dotpattern distance property", True, sym({"fill": {"dotpattern": {"distance": P("d")}}})),
    ("dotpattern distance 3 items", False, sym({"fill": {"dotpattern": {"distance": [1, 2, 3]}}})),
    ("dotpattern distance junk key", False, sym({"fill": {"dotpattern": {"distance": {"foo": 1}}}})),
    # colours (#165, #166)
    ("color {r,g,b}", True, sym({"fill": {"color": {"r": 1, "g": 2, "b": 3}}})),
    ("color {property}", True, sym({"fill": {"color": P("c")}})),
    ("color {sysId}", True, sym({"fill": {"color": S("viz.sd")}})),
    ("color hex", True, sym({"fill": {"color": "#FF6432"}})),
    ("color hex short", False, sym({"fill": {"color": "#F63"}})),
    ("color fuchsia", True, sym({"fill": {"color": "fuchsia"}})),
    ("color fuschia", False, sym({"fill": {"color": "fuschia"}})),
    ("color r = 300", False, sym({"fill": {"color": [300, 0, 0]}})),
    ("color r = -1", False, sym({"fill": {"color": [-1, 0, 0]}})),
    ("color r = 255.5", False, sym({"fill": {"color": [255.5, 0, 0]}})),
    ("color r = expression", True, sym({"fill": {"color": [op("*", P("a"), 2), 0, 0]}})),
    ("opacity 1.5", False, sym({"opacity": 1.5})),
    ("opacity 0.5", True, sym({"opacity": 0.5})),
    ("opacity expression", True, sym({"opacity": op("/", P("a"), 100)})),
    ("hillShading colorMap key 0.5", True, sym({"hillShading": {"colorMap": [[0.5, "gray"]]}})),
    ("colorChannels {property}", True, sym({"colorChannels": P("c")})),
    # stroke and units (#120, #169)
    ("stroke center", True, sym({"stroke": {"width": 3, "center": {"color": "white", "width": 1}}})),
    ("stroke dashOffset", True, sym({"stroke": {"dashPattern": [{"px": 5}, {"px": 5}], "dashOffset": {"px": 2}}})),
    ("unit inch", True, sym({"stroke": {"width": {"inch": 0.1}}})),
    ("unit in (old)", False, sym({"stroke": {"width": {"in": 0.1}}})),
    # system identifiers (#166)
    ("viz.pass", True, sel(op("=", S("viz.pass"), 1))),
    ("feature.pass", True, sel(op("=", S("feature.pass"), 1))),
    ("capabilities.dashes", True, sel(op("=", S("capabilities.dashes"), True))),
    ("capabilities.vendor.acme.glow", True, sel(op("=", S("capabilities.vendor.acme.glow"), True))),
    ("capabilities.vendor.acme", False, sel(op("=", S("capabilities.vendor.acme"), True))),
    ("sysId unknown", False, sel(op("=", S("viz.foo"), 1))),
    # expression forms touched by the PR
    ("format with op", True, sym({"label": {"elements": [{"type": "Text", "text": op("format", "%d", P("n"))}]}})),
    ("format with name (old)", False, sym({"label": {"elements": [{"type": "Text", "text": {"name": "format", "args": ["%d", 1]}}]}})),
    ("substitute", True, sel(op("=", op("substitute", P("n"), "a", "b"), "x"))),
    ("pow as generic call", True, sym({"opacity": op("pow", op("/", P("B04"), 2500), 0.5)})),
    ("?: three arguments", True, sym({"opacity": op("?:", op("<", P("x"), 1), 0.5, 1)})),
    ("?: third argument junk", False, sym({"opacity": op("?:", op("<", P("x"), 1), 0.5, {"foo": 1})})),
    ("not like", True, sel(op("not", op("like", P("name"), "a%")))),
    ("notLike op (an unknown function, like any other name)", True, sel(op("notLike", P("name"), "a%"))),
    ("LIKE upper case (an unknown function)", True, sel(op("LIKE", P("name"), "a%"))),
    ("isNull one arg", True, sel(op("isNull", P("a")))),
    ("isNull two args", False, sel(op("isNull", P("a"), None))),
    ("geometry literal", True, sel(op("myFn", {"type": "Point", "coordinates": [1, 2]}))),
    ("bbox literal", True, sel(op("myFn", {"bbox": [0, 0, 1, 1]}))),
    ("mod", True, sym({"zOrder": op("%", P("a"), 2)})),
    ("intDiv", True, sym({"zOrder": op("div", P("a"), 2)})),
    ("hex number with junk", False, sym({"zOrder": op("bitAnd", "ffzz", 1)})),
    ("clause 16 alter example", True, sym({"fill": {"alter": True, "color": {"alter": True, "r": 100}}})),
    ("clause 16 elements index example", True, sym({"marker": {"alter": True, "elements": {"index": 1, "value": {"type": "Text", "text": "Marker"}}}})),
]
