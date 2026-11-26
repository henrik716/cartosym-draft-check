"""Translate a CartoSym-CSS style sheet to CartoSym-JSON.

The text gives no explicit CSS-to-JSON mapping; this follows the JSON Schema
and the paired examples in spec/1-core/examples (*.cscss / *.cs.json).
"""
from parser import parse_style
from tojson import to_json, hex_color, ConvertError

# Expected type of each member, by class.  Only what the cases and examples need.
UNIT_VALUE, UNIT_POINT, POSITION, COLOR, ANY = "unitValue", "unitPoint", "position", "color", "any"

CLASSES = {
    "Symbolizer": {"visibility": ANY, "opacity": ANY, "zOrder": ANY, "fill": "Fill", "stroke": "Stroke",
                   "marker": "Marker", "label": "Marker", "font": "Font"},
    "Fill": {"color": COLOR, "opacity": ANY},
    "Stroke": {"color": COLOR, "opacity": ANY, "width": UNIT_VALUE, "casing": "Stroke", "center": "Stroke",
               "dashOffset": UNIT_VALUE},
    "Marker": {"elements": "Graphics", "font": "Font", "position": POSITION, "opacity": ANY},
    "Font": {"face": ANY, "size": UNIT_VALUE, "bold": ANY, "italic": ANY, "underline": ANY, "color": COLOR,
             "opacity": ANY},
    "Resource": {"uri": ANY, "path": ANY, "id": ANY, "type": ANY, "ext": ANY, "sprite": ANY},
    "Dot": {"size": UNIT_VALUE, "color": COLOR, "position": POSITION, "opacity": ANY, "stroke": "Stroke"},
    "Image": {"image": "Resource", "hotSpot": UNIT_POINT, "size": "ImageSize", "tint": COLOR,
              "blackTint": COLOR, "alphaThreshold": ANY, "position": POSITION, "opacity": ANY},
    "Text": {"text": ANY, "font": "Font", "alignment": "Alignment", "position": POSITION, "opacity": ANY},
}
GRAPHIC_CLASSES = {"Dot", "Image", "Text"}


class StyleError(Exception):
    pass


def convert_value(node, typ):
    k = node[0]
    if typ == UNIT_VALUE:
        if k == "tuple":
            raise StyleError("a tuple where a single uom-qualified value is expected")
        return to_json(node)
    if typ == "ImageSize":
        # a single value sets width and height; a UnitPoint sets x and y
        if k == "tuple":
            return convert_value(node, UNIT_POINT)
        if k == "instance":
            return convert_instance(node, "UnitPoint")
        return to_json(node)
    if typ in (UNIT_POINT, POSITION):
        if k == "tuple":
            elems = node[1]
            if not 2 <= len(elems) <= 3:
                raise StyleError("a point has 2 or 3 coordinates")
            vals = [convert_value(e, UNIT_VALUE) for e in elems]
            if typ == POSITION:
                # The examples encode a position as {"x": .., "y": ..}
                return dict(zip("xyz", vals))
            # ... and a hotSpot (with units) as an array
            return vals
        if k == "instance":
            return convert_instance(node, "UnitPoint")
        # Any other expression: kept as an expression (see notes.md)
        return to_json(node)
    if typ == COLOR:
        if k == "hex":
            return hex_color(node[1])
        if k == "id" and not node[2]:
            return node[1]  # named web color (enumeration value)
        if k == "tuple":
            return [to_json(e) for e in node[1]]
        if k == "instance":
            return convert_instance(node, "Color")
        return to_json(node)
    if typ == "Alignment":
        if k == "tuple":
            return [e[1] if e[0] == "id" else to_json(e) for e in node[1]]
        return to_json(node)
    if typ == "Graphics":
        if k != "array":
            raise StyleError("elements is an array of Graphics")
        return [convert_graphic(e) for e in node[1]]
    if typ in CLASSES:
        if k == "instance":
            return convert_instance(node, typ)
        if k == "id" and not node[2] and node[1] == "null":
            return None
        return to_json(node)
    return to_json(node)


def convert_graphic(node):
    if node[0] != "instance" or node[1] not in GRAPHIC_CLASSES:
        raise StyleError("an element of a marker is a Dot, Image or Text instance")
    return convert_instance(node, node[1])


def convert_instance(node, typ):
    _, cls, members = node
    if cls is not None and cls in GRAPHIC_CLASSES:
        typ = cls
    obj = {"type": cls} if cls in GRAPHIC_CLASSES else {}
    member_types = CLASSES.get(typ, {})
    if typ == "UnitPoint":
        member_types = {"x": UNIT_VALUE, "y": UNIT_VALUE, "z": UNIT_VALUE}
    for path, e in members:
        if path is None:
            raise StyleError(f"positional members of {typ} are not supported")
        set_path(obj, path, e, typ, member_types, fresh=True)
    return obj


def member_type(cls, member):
    if cls == "UnitPoint" or cls == "ImageSize":
        return UNIT_VALUE
    t = CLASSES.get(cls, {}).get(member)
    if t is None:
        return ANY
    return t


def set_path(obj, path, node, cls, member_types, fresh):
    """Assign node to obj at path.  In a styling rule (fresh=False) an
    assignment to a member (fill.color) is a partial update ("alter": true);
    inside a new instance (fresh=True) it just sets the member."""
    cur, cur_cls = obj, cls
    for p in path[:-1]:
        if isinstance(p, int):
            raise StyleError("array element assignment is not supported here")
        nxt_cls = member_types.get(p) if cur is obj else member_type(cur_cls, p)
        if nxt_cls == "ImageSize":
            nxt_cls = "UnitPoint"
        sub = cur.get(p)
        if not isinstance(sub, dict):
            sub = {} if fresh else {"alter": True}
            cur[p] = sub
        cur, cur_cls = sub, nxt_cls
    last = path[-1]
    if cur is obj:
        t = member_types.get(last, ANY)
    else:
        t = member_type(cur_cls, last)
    cur[last] = convert_value(node, t)


def layer_selector(name):
    return {"op": "=", "args": [{"sysId": "dataLayer.id"}, name]}


def convert_rule(r):
    out = {}
    if r["name"] is not None:
        out["name"] = r["name"]
    sels = []
    if r["layers"]:
        ls = [layer_selector(n) for n in r["layers"]]
        sels.append(ls[0] if len(ls) == 1 else {"op": "or", "args": ls})
    sels += [to_json(e) for e in r["selectors"]]
    if sels:
        out["selector"] = sels[0] if len(sels) == 1 else {"op": "and", "args": sels}
    if r["assigns"]:
        sym = {}
        for path, e in r["assigns"]:
            set_path(sym, path, e, "Symbolizer", CLASSES["Symbolizer"], fresh=False)
        out["symbolizer"] = sym
    if r["nested"]:
        out["nestedRules"] = [convert_rule(n) for n in r["nested"]]
    return out


def css_to_json(text):
    ss = parse_style(text)
    doc = {}
    if ss["metadata"]:
        md = {}
        for name, value in ss["metadata"]:
            plural = {"author": "authors", "keyword": "keywords", "geoDataClass": "geoDataClasses"}
            if name in plural:
                md.setdefault(plural[name], []).append(value)
            else:
                md[name] = value
        doc["metadata"] = md
    if ss["variables"]:
        doc["$variables"] = {n: to_json(e) for n, e in ss["variables"]}
    doc["stylingRules"] = [convert_rule(r) for r in ss["rules"]]
    return doc


def json_pointer(doc, ptr):
    if ptr == "":
        return doc
    if not ptr.startswith("/"):
        raise StyleError(f"bad JSON pointer {ptr}")
    cur = doc
    for raw in ptr[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except (ValueError, IndexError):
                raise StyleError(f"{ptr}: no element {key}")
        elif isinstance(cur, dict):
            if key not in cur:
                raise StyleError(f"{ptr}: no member {key}")
            cur = cur[key]
        else:
            raise StyleError(f"{ptr}: cannot index into {cur!r}")
    return cur
