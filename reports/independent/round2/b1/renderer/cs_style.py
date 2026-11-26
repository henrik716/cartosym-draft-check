"""CartoSym-JSON styles: Symbolizer classes, default values and rule cascading.

The resolved Symbolizer is a dict.  Object members are dicts with a '_cls' key.
Uom-qualified values are tuples (value, unit) where unit is None when no unit
is given.  Colors are (r, g, b) tuples with components 0..255.
"""
import copy

from cs_expr import evaluate, is_expression_object, to_text, is_array
from cs_colors import WEB_COLORS

UNITS = ('px', 'mm', 'cm', 'inch', 'pt', 'em', 'pc', 'm', 'ft')

# ---------------------------------------------------------------- class member types
T_NUM, T_BOOL, T_TEXT, T_COLOR, T_UNIT, T_POINT, T_ALIGN = 'num', 'bool', 'text', 'color', 'unit', 'point', 'align'
T_IMGSIZE, T_CMAP, T_OMAP, T_DASH, T_GARRAY, T_ANGLE, T_COLOR01, T_ENUM = (
    'imgsize', 'cmap', 'omap', 'dash', 'garray', 'angle', 'color01', 'enum')

CLASSES = {
    'Fill': {'color': T_COLOR, 'opacity': T_NUM, 'hatch': 'Hatch', 'dotpattern': 'Dotpattern',
             'stipple': 'Stipple', 'pattern': 'Graphic'},
    'StrokeStyling': {'color': T_COLOR, 'opacity': T_NUM, 'width': T_UNIT},
    'Stroke': {'color': T_COLOR, 'opacity': T_NUM, 'width': T_UNIT, 'casing': 'StrokeStyling',
               'center': 'StrokeStyling', 'dashPattern': T_DASH, 'dashOffset': T_UNIT, 'pattern': 'Graphic'},
    'Font': {'face': T_TEXT, 'size': T_UNIT, 'bold': T_BOOL, 'italic': T_BOOL, 'underline': T_BOOL,
             'color': T_COLOR, 'opacity': T_NUM, 'outline': 'FontOutline'},
    'FontOutline': {'size': T_NUM, 'opacity': T_NUM, 'color': T_COLOR},
    'Marker': {'elements': T_GARRAY, 'font': 'Font', 'opacity': T_NUM, 'position': T_POINT},
    'Label': {'elements': T_GARRAY, 'font': 'Font', 'opacity': T_NUM, 'position': T_POINT,
              'placement': 'LabelPlacement'},
    'MultiGraphic': {'elements': T_GARRAY, 'font': 'Font', 'opacity': T_NUM, 'position': T_POINT},
    'LabelPlacement': {'priority': T_NUM, 'minSpacing': T_UNIT, 'maxSpacing': T_UNIT},
    'Dot': {'position': T_POINT, 'opacity': T_NUM, 'size': T_UNIT, 'color': T_COLOR},
    'Text': {'position': T_POINT, 'opacity': T_NUM, 'text': T_TEXT, 'font': 'Font', 'alignment': T_ALIGN},
    'Image': {'position': T_POINT, 'opacity': T_NUM, 'image': 'Resource', 'hotSpot': T_POINT,
              'size': T_IMGSIZE, 'tint': T_COLOR, 'blackTint': T_COLOR, 'alphaThreshold': T_NUM},
    'Resource': {'uri': T_TEXT, 'url': T_TEXT, 'path': T_TEXT, 'id': T_TEXT, 'type': T_TEXT, 'ext': T_TEXT,
                 'sprite': T_TEXT},
    'HillShading': {'factor': T_NUM, 'sun': 'AzimuthElevation', 'colorMap': T_CMAP, 'opacityMap': T_OMAP},
    'AzimuthElevation': {'azimuth': T_ANGLE, 'elevation': T_ANGLE},
    'Hatch': {'width': T_UNIT, 'angle': T_NUM, 'distance': T_UNIT},
    'Dotpattern': {'distance': 'Distance'},
    'Distance': {'horizontal': T_UNIT, 'vertical': T_UNIT},
    'Stipple': {'ratio': T_NUM},
    'Color01': {'r': T_NUM, 'g': T_NUM, 'b': T_NUM},
}

SYMBOLIZER = {
    'visibility': T_BOOL, 'opacity': T_NUM, 'zOrder': T_NUM,
    'fill': 'Fill', 'stroke': 'Stroke', 'marker': 'Marker', 'label': 'Label', 'font': 'Font',
    'colorChannels': 'Color01', 'alphaChannel': T_NUM, 'singleChannel': T_NUM,
    'colorMap': T_CMAP, 'opacityMap': T_OMAP, 'hillShading': 'HillShading',
}

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def default_instance(cls):
    """Default values of clause 7 'Default class member values' (and choices for
    members the text gives none: see notes.md C-03, C-15, C-16)."""
    if cls == 'Fill':
        return {'_cls': 'Fill', 'color': WHITE, 'opacity': 1}
    if cls == 'Stroke':
        return {'_cls': 'Stroke', 'color': BLACK, 'opacity': 1, 'width': (1, 'px'),
                'casing': {'_cls': 'StrokeStyling', 'color': BLACK, 'opacity': 1, 'width': (0, 'px')},
                'center': {'_cls': 'StrokeStyling', 'color': BLACK, 'opacity': 1, 'width': (0, 'px')},
                'dashPattern': None, 'dashOffset': (0, 'px')}
    if cls == 'StrokeStyling':
        # casing / center: 'width 0 (no casing), color black'
        return {'_cls': 'StrokeStyling', 'color': BLACK, 'opacity': 1, 'width': (0, 'px')}
    if cls == 'Font':
        # members left unset (None) so that font inheritance (/req/vector/font-inheritance) applies
        return {'_cls': 'Font'}
    if cls == 'FontOutline':
        return {'_cls': 'FontOutline', 'size': 1, 'opacity': 1, 'color': WHITE}
    if cls == 'Marker':
        return {'_cls': 'Marker', 'elements': [default_instance('Dot')], 'font': None, 'opacity': 1,
                'position': None}
    if cls in ('Label', 'MultiGraphic'):
        return {'_cls': cls, 'elements': [], 'font': None, 'opacity': 1, 'position': None,
                'placement': default_instance('LabelPlacement') if cls == 'Label' else None}
    if cls == 'LabelPlacement':
        return {'_cls': 'LabelPlacement', 'priority': None, 'minSpacing': None, 'maxSpacing': None}
    if cls == 'Dot':
        return {'_cls': 'Dot', 'position': None, 'opacity': 1, 'size': (10, 'px'), 'color': WHITE}
    if cls == 'Text':
        return {'_cls': 'Text', 'position': None, 'opacity': 1, 'text': '', 'font': None,
                'alignment': ('left', 'top')}
    if cls == 'Image':
        return {'_cls': 'Image', 'position': None, 'opacity': 1, 'image': {'_cls': 'Resource'},
                'hotSpot': {'x': (50, 'pc'), 'y': (50, 'pc')}, 'size': None, 'tint': WHITE,
                'blackTint': BLACK, 'alphaThreshold': 0}
    if cls == 'HillShading':
        return {'_cls': 'HillShading', 'factor': 0,
                'sun': {'_cls': 'AzimuthElevation', 'azimuth': 315, 'elevation': 45},
                'colorMap': None, 'opacityMap': None}
    if cls == 'AzimuthElevation':
        return {'_cls': 'AzimuthElevation', 'azimuth': 315, 'elevation': 45}
    if cls == 'Hatch':
        # defaults from the figure caption 'Default hatch properties (width 1 px, angle 45, distance 10 px)'
        return {'_cls': 'Hatch', 'width': (1, 'px'), 'angle': 45, 'distance': (10, 'px')}
    if cls == 'Dotpattern':
        return {'_cls': 'Dotpattern', 'distance': default_instance('Distance')}
    if cls == 'Distance':
        return {'_cls': 'Distance', 'horizontal': (10, 'px'), 'vertical': (10, 'px')}
    if cls == 'Stipple':
        return {'_cls': 'Stipple', 'ratio': 0.5}
    if cls == 'Color01':
        return {'_cls': 'Color01', 'r': None, 'g': None, 'b': None}
    if cls == 'Resource':
        return {'_cls': 'Resource'}
    return {'_cls': cls}


def default_symbolizer():
    return {
        'visibility': True, 'opacity': 1, 'zOrder': 1,
        'fill': default_instance('Fill'), 'stroke': default_instance('Stroke'),
        'marker': default_instance('Marker'), 'label': None, 'font': None,
        'colorChannels': None, 'alphaChannel': 1, 'singleChannel': None,
        'colorMap': None, 'opacityMap': None, 'hillShading': None,
    }


# ---------------------------------------------------------------- value conversion

NULL_SCALAR = {T_NUM: 0, T_BOOL: False, T_COLOR: BLACK, T_TEXT: ''}


def to_color(v):
    if v is None:
        return None
    if isinstance(v, (list, tuple)) and len(v) == 3:
        if any(c is None for c in v):
            return None
        return tuple(float(c) for c in v)
    if isinstance(v, str):
        s = v.strip()
        if s.startswith('#') and len(s) == 7:
            return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
        c = WEB_COLORS.get(s.lower())
        if c is not None:
            return c
        return None
    return None


def to_number(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) or is_array(v):
        return v
    return None


def conv_unit(j, ctx):
    """unitValue: number, or {"px": n} etc.  Returns (value, unit) or None."""
    if isinstance(j, dict) and not is_expression_object(j):
        for u in UNITS:
            if u in j:
                return (to_number(evaluate(j[u], ctx)), u)
        return None
    return (to_number(evaluate(j, ctx)), None)


def conv_point(old, j, ctx):
    if is_expression_object(j):
        j = evaluate(j, ctx)
    if j is None:
        return None
    if isinstance(j, (list, tuple)):
        x = conv_unit(j[0], ctx) if len(j) > 0 else None
        y = conv_unit(j[1], ctx) if len(j) > 1 else None
        return {'x': x, 'y': y}
    if isinstance(j, dict):
        base = dict(old) if (j.get('alter') and old) else {'x': None, 'y': None}
        if 'x' in j:
            base['x'] = conv_unit(j['x'], ctx)
        if 'y' in j:
            base['y'] = conv_unit(j['y'], ctx)
        return base
    return None


ALIGN_H = ('hAlignment', 'horizontal', 'horzAlignment')
ALIGN_V = ('vAlignment', 'vertical', 'vertAlignment')


def conv_align(old, j, ctx):
    if is_expression_object(j):
        j = evaluate(j, ctx)
    if isinstance(j, (list, tuple)) and len(j) == 2:
        return (evaluate(j[0], ctx) or 'left', evaluate(j[1], ctx) or 'top')
    if isinstance(j, dict):
        h, v = old if (j.get('alter') and old) else ('left', 'top')
        for k in ALIGN_H:
            if k in j:
                h = evaluate(j[k], ctx)
        for k in ALIGN_V:
            if k in j:
                v = evaluate(j[k], ctx)
        return (h or 'left', v or 'top')
    return old


def conv_color(old, j, ctx):
    if isinstance(j, dict) and not is_expression_object(j):
        base = list(old) if (j.get('alter') and old) else [0, 0, 0]
        for i, k in enumerate('rgb'):
            if k in j:
                base[i] = to_number(evaluate(j[k], ctx))
        c = to_color(base)
        return c if c is not None else NULL_SCALAR[T_COLOR]
    v = evaluate(j, ctx)
    c = to_color(v)
    if c is None:
        return NULL_SCALAR[T_COLOR]
    return c


def conv_map(j, ctx, opacity):
    v = evaluate(j, ctx) if is_expression_object(j) else j
    if not isinstance(v, list):
        return None
    out = []
    for entry in v:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        val = to_number(evaluate(entry[0], ctx))
        if opacity:
            o = to_number(evaluate(entry[1], ctx))
            out.append((val, o))
        else:
            out.append((val, conv_color(None, entry[1], ctx)))
    return out


def conv_angle(j, ctx):
    if isinstance(j, dict) and not is_expression_object(j):
        if 'deg' in j:
            return to_number(evaluate(j['deg'], ctx))
        if 'rad' in j:
            import math
            r = to_number(evaluate(j['rad'], ctx))
            return None if r is None else math.degrees(r)
    return to_number(evaluate(j, ctx))


def make_graphic(j, old, ctx):
    """A graphic of a MultiGraphic's elements: Dot, Text, Image or a nested MultiGraphic."""
    if is_expression_object(j):
        j = evaluate(j, ctx)
    if not isinstance(j, dict):
        return None
    if 'elements' in j:
        cls = 'MultiGraphic'
    else:
        cls = j.get('type') or (old or {}).get('_cls')
    if cls not in ('Dot', 'Text', 'Image', 'MultiGraphic'):
        return None
    if j.get('alter') and old is not None and old.get('_cls') == cls:
        g = copy.deepcopy(old)
    else:
        g = default_instance(cls)
    apply_members(g, cls, j, ctx)
    return g


def conv_garray(old, j, ctx):
    if is_expression_object(j):
        j = evaluate(j, ctx)
    if isinstance(j, list):
        return [g for g in (make_graphic(x, None, ctx) for x in j) if g is not None]
    if isinstance(j, dict) and 'index' in j:
        arr = copy.deepcopy(old) if old else []
        i = int(j['index'])
        prev = arr[i] if i < len(arr) else None
        g = make_graphic(j.get('value'), prev, ctx)
        if i < len(arr):
            if g is None:
                arr.pop(i)
            else:
                arr[i] = g
        elif g is not None:
            # choice C-18: an index at or past the end appends the element
            arr.append(g)
        return arr
    return old


def conv_dash(old, j, ctx):
    if is_expression_object(j):
        j = evaluate(j, ctx)
    if j is None:
        return None
    if isinstance(j, list):
        return [conv_unit(x, ctx) for x in j]
    if isinstance(j, dict) and 'index' in j:
        arr = list(old) if old else []
        i = int(j['index'])
        v = conv_unit(j['value'], ctx)
        if i < len(arr):
            arr[i] = v
        else:
            arr.append(v)
        return arr
    return old


def apply_value(t, old, j, ctx):
    if t in CLASSES:
        return apply_object(t, old, j, ctx)
    if t == T_UNIT:
        v = conv_unit(j, ctx)
        if v is None or v[0] is None:
            return (0, v[1] if v else None)
        return v
    if t == T_POINT:
        return conv_point(old, j, ctx)
    if t == T_ALIGN:
        return conv_align(old, j, ctx)
    if t == T_IMGSIZE:
        if isinstance(j, (list, tuple)) or (isinstance(j, dict) and ('x' in j or 'y' in j)):
            return ('point', conv_point(old[1] if (old and old[0] == 'point') else None, j, ctx))
        u = conv_unit(j, ctx)
        return ('single', u)
    if t == T_COLOR:
        return conv_color(old, j, ctx)
    if t == T_CMAP:
        return conv_map(j, ctx, False)
    if t == T_OMAP:
        return conv_map(j, ctx, True)
    if t == T_DASH:
        return conv_dash(old, j, ctx)
    if t == T_GARRAY:
        return conv_garray(old, j, ctx)
    if t == T_ANGLE:
        v = conv_angle(j, ctx)
        return 0 if v is None else v
    v = evaluate(j, ctx)
    if t == T_NUM:
        v = to_number(v)
        return NULL_SCALAR[T_NUM] if v is None else v
    if t == T_BOOL:
        return v if isinstance(v, bool) else NULL_SCALAR[T_BOOL]
    if t == T_TEXT:
        s = to_text(v)
        return NULL_SCALAR[T_TEXT] if s is None else s
    return v


def apply_object(cls, old, j, ctx):
    if j is None:
        return None          # e.g. marker: null, fill: null (choice C-05)
    if is_expression_object(j):
        v = evaluate(j, ctx)
        if v is None:
            return None
        j = v
    if not isinstance(j, dict):
        return old
    if j.get('alter') and old is not None:
        obj = copy.deepcopy(old)
    elif j.get('alter'):
        obj = default_instance(cls)
    else:
        obj = default_instance(cls)
    apply_members(obj, cls, j, ctx)
    return obj


def apply_members(obj, cls, j, ctx):
    members = CLASSES.get(cls, {})
    if cls == 'Dot' and isinstance(j.get('stroke'), dict):
        # /req/vector/dot: the size and color of a Dot are the width and color of its stroke
        st = j['stroke']
        if 'width' in st:
            obj['size'] = apply_value(T_UNIT, obj.get('size'), st['width'], ctx)
        if 'color' in st:
            obj['color'] = apply_value(T_COLOR, obj.get('color'), st['color'], ctx)
    for k, v in j.items():
        if k in ('alter', 'type', '$comment'):
            continue
        if k == 'stroke' and cls == 'Dot':
            continue
        t = members.get(k)
        if t is None:
            continue           # unknown / vendor members are ignored (clause 7 Vendor Extensions)
        obj[k] = apply_value(t, obj.get(k), v, ctx)


def apply_symbolizer(state, sym, ctx):
    for k, v in sym.items():
        t = SYMBOLIZER.get(k)
        if t is None:
            continue
        state[k] = apply_value(t, state.get(k), v, ctx)


def resolve(rules, ctx, state=None):
    """Applies the selected rules in order (req/core/rules, selector, nested)."""
    if state is None:
        state = default_symbolizer()
    for r in rules:
        sel = r.get('selector')
        if sel is not None:
            v = evaluate(sel, ctx)
            if is_array(v):
                raise NotImplementedError('selector depending on coverage cell values')
            if v is not True:
                continue
        if r.get('symbolizer'):
            apply_symbolizer(state, r['symbolizer'], ctx)
        if r.get('nestedRules'):
            resolve(r['nestedRules'], ctx, state)
    return state
