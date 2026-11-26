"""Convert a CartoSym-CSS expression AST to CQL2-JSON as extended by the
CartoSym-JSON schema (spec/1-core/schemas/CartoSym-JSON.schema.json)."""

SYSTEM_ROOTS = {"visualization", "viz", "dataLayer", "capabilities", "feature"}


class ConvertError(Exception):
    pass


def dotted(node):
    """Flatten a chain of member accesses on an unquoted identifier."""
    if node[0] == "id" and not node[2]:
        return node[1]
    if node[0] == "member":
        base = dotted(node[1])
        if base is not None:
            return base + "." + node[2]
    return None


def hex_color(h):
    if len(h) != 6:
        raise ConvertError(f"#{h} is not a 6-digit hexadecimal color")
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]


def is_null_literal(node):
    return node[0] == "id" and not node[2] and node[1].lower() == "null"


def to_json(node):
    k = node[0]
    if k == "num":
        _, v, unit = node
        return v if unit is None else {unit: v}
    if k == "hex":
        return hex_color(node[1])
    if k == "str":
        return node[1]
    if k == "id":
        _, name, quoted = node
        if quoted:
            return {"property": name}
        low = name.lower()
        if low == "null":
            return None
        if low == "true":
            return True
        if low == "false":
            return False
        if name in SYSTEM_ROOTS:
            return {"sysId": name}
        return {"property": name}
    if k == "member":
        d = dotted(node)
        if d is not None:
            root = d.split(".")[0]
            if root in SYSTEM_ROOTS:
                return {"sysId": d}
            return {"property": d}
        raise ConvertError("member access on a non-identifier expression has no CQL2-JSON encoding")
    if k == "neg":
        inner = node[1]
        if inner[0] == "num" and inner[2] is None:
            return -inner[1]
        if inner[0] == "num":
            return {inner[2]: -inner[1]}
        # No unary minus in the CartoSym-JSON schema: one-argument "-" (see notes.md)
        return {"op": "-", "args": [to_json(inner)]}
    if k == "pos":
        return to_json(node[1])
    if k == "not":
        return {"op": "not", "args": [to_json(node[1])]}
    if k == "group":
        return to_json(node[1])
    if k == "array":
        return [to_json(e) for e in node[1]]
    if k == "tuple":
        return [to_json(e) for e in node[1]]
    if k == "var":
        return {"$ref": "#/$variables/" + node[1]}
    if k == "call":
        return {"op": node[1], "args": [to_json(a) for a in node[2]]}
    if k == "cond":
        return {"op": "?:", "args": [to_json(node[1]), to_json(node[2]), to_json(node[3])]}
    if k == "between":
        _, neg, x, lo, hi = node
        e = {"op": "between", "args": [to_json(x), to_json(lo), to_json(hi)]}
        return {"op": "not", "args": [e]} if neg else e
    if k == "bin":
        _, op, l, r = node
        if op in ("is", "is not"):
            if not is_null_literal(r):
                raise ConvertError("'is' / 'is not' is only used with the null literal as second operand")
            e = {"op": "isNull", "args": [to_json(l)]}
            return {"op": "not", "args": [e]} if op == "is not" else e
        if op in ("in", "not in"):
            rr = to_json(r)
            if not isinstance(rr, list):
                rr = [rr]  # x in (5): a one-element list (see notes.md)
            e = {"op": "in", "args": [to_json(l), rr]}
            return {"op": "not", "args": [e]} if op == "not in" else e
        if op == "not like":
            return {"op": "not", "args": [{"op": "like", "args": [to_json(l), to_json(r)]}]}
        return {"op": op, "args": [to_json(l), to_json(r)]}
    if k == "instance":
        _, cls, members = node
        obj = {} if cls is None else {"type": cls}
        for path, e in members:
            if path is None:
                raise ConvertError("instance member without a name has no generic CQL2-JSON encoding")
            _set_path(obj, path, to_json(e))
        return obj
    if k == "index":
        raise ConvertError("indexing has no CQL2-JSON encoding")
    raise ConvertError(f"cannot convert {k}")


def _set_path(obj, path, value):
    cur = obj
    for p in path[:-1]:
        cur = cur.setdefault(p, {})
    cur[path[-1]] = value
