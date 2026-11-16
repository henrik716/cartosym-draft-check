#!/usr/bin/env python3
"""Renderer for OGC Cartographic Symbology 2.0 Part 1 (draft), written from the
requirement text in spec/1-core only. Choices are recorded in notes.md.

Usage: render.py [case ...]   (no argument renders all cases)
"""
import sys
import os
import re
import json
import math
import glob
import traceback

import numpy as np
import cairo
from PIL import Image, ImageDraw
from shapely.geometry import shape as g_shape

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(HERE, 'spec', '1-core')
CASES = os.path.join(HERE, 'cases')
OUT = os.path.join(HERE, 'out')

PX_MM = 0.28                      # standard pixel (view pixelSize_mm)
PT_MM = 25.4 / 72.0               # point = 1/72 inch (clause 17 units table)
UNIT_MM = {'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': PT_MM}
FONT_DEFAULT_FACE = 'Arial'       # not defined by the text; choice
FONT_DEFAULT_PT = 10.0            # not defined by the text; choice
PI2 = 2 * math.pi


def read_text(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def load_json(p):
    return json.loads(read_text(p))


def load_named_colours():
    """Named web colours, values from the table in clause 17 (CartoSym-CSS)."""
    txt = read_text(os.path.join(SPEC, 'sections', 'clause_17_cscss.adoc'))
    out = {}
    pat = r'^\s*\|?\s*([A-Za-z]+)\s*\|\s*`0x[0-9a-fA-F]{6}`\s*\|\s*(\d+),\s*(\d+),\s*(\d+)'
    for m in re.finditer(pat, txt, re.M):
        out[m.group(1).lower()] = tuple(int(m.group(i)) for i in (2, 3, 4))
    return out


NAMED = load_named_colours()


def parse_colour(v, scale=255.0):
    """Colour value -> (r, g, b) floats in 0..1.  scale is the range of the
    numeric components (255 for Color, 1 for color0to1)."""
    if v is None:
        return (0.0, 0.0, 0.0)           # clause 9 table: Color null -> black
    if isinstance(v, str):
        s = v.strip()
        if s.startswith('#') and len(s) == 7:
            return tuple(int(s[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        key = s.lower()
        if key not in NAMED:
            raise ValueError('unknown colour name %r' % v)
        return tuple(c / 255.0 for c in NAMED[key])
    if isinstance(v, dict):
        comps = [v.get('r'), v.get('g'), v.get('b')]
    else:
        comps = list(v)
    out = []
    for c in comps:
        c = 0.0 if c is None else float(c)
        out.append(min(1.0, max(0.0, c / scale)))
    return tuple(out)


def num(v, default=0.0):
    if v is None:
        return default
    return float(v)


def to_px(v, mpp, em_px=FONT_DEFAULT_PT * PT_MM / PX_MM):
    """A length (unitless number, unit object or null) to device pixels.
    Unitless numbers are pixels (clause 8: pixel is the default unit)."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, dict):
        for u, n in v.items():
            if u == 'alter':
                continue
            if u == 'px':
                return num(n)
            if u in UNIT_MM:
                return num(n) * UNIT_MM[u] / PX_MM
            if u == 'm':
                return num(n) / mpp
            if u == 'ft':
                return num(n) * 0.3048 / mpp
            if u == 'em':
                return num(n) * em_px
            if u == 'pc':
                raise ValueError('percent has no meaning for a plain length')
    raise ValueError('bad length %r' % (v,))


def hot_coord(v, size_px, mpp):
    """One coordinate of an Image hotSpot: a unitless number is a fraction of
    the image size, pc is a percentage of it, another unit is a length from the
    top left corner (clause 8, /req/vector/image)."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) * size_px
    if isinstance(v, dict) and 'pc' in v:
        return num(v['pc']) / 100.0 * size_px
    return to_px(v, mpp)


# ----------------------------------------------------------------- expressions

def is_expr(n):
    return isinstance(n, dict) and ('op' in n or 'property' in n or 'sysId' in n)


def sysval(name, env):
    m = {
        'dataLayer.id': env['layer'],
        'dataLayer.identifier': env['layer'],
        'dataLayer.type': env['ltype'],
        'viz.sd': env['scale'],
        'visualization.scaleDenominator': env['scale'],
        'viz.date': env['date'],
        'visualization.date': env['date'],
        'viz.timeInterval.start.date': env['start'],
        'viz.timeInterval.end.date': env['end'],
        'feature.id': env.get('fid'),
        'feature.geometryDimensions': env.get('gdim'),
    }
    return m.get(name)


def _cmp(op, a, b):
    if a is None or b is None:
        return None
    if isinstance(a, bool) or isinstance(b, bool):
        if not (isinstance(a, bool) and isinstance(b, bool)):
            return None
        a, b = int(a), int(b)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        pass
    elif isinstance(a, str) and isinstance(b, str):
        pass          # ISO dates compare correctly as strings
    else:
        return None
    return {'=': a == b, '<>': a != b, '<': a < b, '>': a > b,
            '<=': a <= b, '>=': a >= b}[op]


def _arith(op, a, b):
    if a is None or b is None:
        return None
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == '/':
        return None if b == 0 else a / b
    return None


def _logic(op, vals):
    if op == 'and':
        if any(v is False for v in vals):
            return False
        if any(v is None for v in vals):
            return None
        return True
    if any(v is True for v in vals):
        return True
    if any(v is None for v in vals):
        return None
    return False


def _like(text, pattern):
    if text is None or pattern is None:
        return None
    rx = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == '\\' and i + 1 < len(pattern):
            rx.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if ch == '%':
            rx.append('.*')
        elif ch == '_':
            rx.append('.')
        else:
            rx.append(re.escape(ch))
        i += 1
    return re.fullmatch(''.join(rx), str(text), re.S) is not None


def ev(n, env):
    """Evaluate an encoded expression for one feature (or coverage layer)."""
    if isinstance(n, dict):
        if 'property' in n:
            return env['props'].get(n['property'])
        if 'sysId' in n:
            return sysval(n['sysId'], env)
        if 'op' in n:
            op = n['op']
            args = n.get('args', [])
            if op in ('and', 'or'):
                return _logic(op, [ev(a, env) for a in args])
            if op == 'not':
                v = ev(args[0], env)
                return None if v is None else (not v)
            if op == '?:':
                c = ev(args[0], env)
                return ev(args[1], env) if c is True else ev(args[2], env)
            vals = [ev(a, env) for a in args]
            if op in ('=', '<>', '<', '>', '<=', '>='):
                return _cmp(op, vals[0], vals[1])
            if op in ('+', '-', '*', '/'):
                return _arith(op, vals[0], vals[1])
            if op == 'between':
                x, lo, hi = vals
                if None in (x, lo, hi):
                    return None
                return lo <= x <= hi
            if op == 'in':
                x, arr = vals[0], vals[1]
                if x is None or arr is None:
                    return None
                return any(x == e for e in arr if e is not None)
            if op == 'like':
                return _like(vals[0], vals[1])
            if op == 'isNull':
                return vals[0] is None
            return None   # unknown operator: null (choice, see notes)
        return None
    if isinstance(n, list):
        return [ev(x, env) for x in n]
    return n


def resolve(n, env):
    """Replace every expression in a (merged) symbolizer fragment by its value."""
    if is_expr(n):
        return ev(n, env)
    if isinstance(n, dict):
        return {k: resolve(v, env) for k, v in n.items()}
    if isinstance(n, list):
        return [resolve(x, env) for x in n]
    return n


# ------------------------------------------------------- cascading of rules

def merge_prop(base, new):
    """Merge one symbolizer property into the value set by earlier rules.
    alter: true -> partial update of an object; index/value -> one array element;
    otherwise the object is a complete new instance (missing members = defaults)."""
    if not isinstance(new, dict) or is_expr(new):
        return new
    if new.get('alter') is True:
        b = base if isinstance(base, dict) else {}
        out = dict(b)
        for k, v in new.items():
            if k == 'alter':
                continue
            out[k] = merge_prop(b.get(k), v)
        return out
    if 'index' in new and 'value' in new and isinstance(base, list):
        out = list(base)
        i = int(new['index'])
        if 0 <= i < len(out):
            out[i] = new['value']
        elif i == len(out):
            out.append(new['value'])
        return out
    return new


def merge_symbolizer(state, sym):
    for k, v in sym.items():
        if k.startswith('$'):
            continue
        state[k] = merge_prop(state.get(k), v)


def apply_rules(rules, env, state):
    for r in rules:
        sel = r.get('selector')
        if sel is not None and ev(sel, env) is not True:
            continue
        if r.get('symbolizer') is not None:
            merge_symbolizer(state, r['symbolizer'])
        if r.get('nestedRules'):
            apply_rules(r['nestedRules'], env, state)
    return state


# --------------------------------------------------------------- data loading

class Frame:
    """Map frame: device pixels, origin top left, 0.28 mm per pixel."""

    def __init__(self, view):
        self.W = int(view['width'])
        self.H = int(view['height'])
        minx, miny, maxx, maxy = view['bbox']
        self.minx, self.miny, self.maxx, self.maxy = minx, miny, maxx, maxy
        mx = (maxx - minx) / self.W
        my = (maxy - miny) / self.H
        assert abs(mx - my) < 1e-6 * mx, 'non-square pixels'
        self.mpp = mx                          # metres per device pixel
        self.scale = float(view['scaleDenominator'])
        expect = self.scale * PX_MM / 1000.0
        assert abs(expect - self.mpp) / self.mpp < 0.01, ('bbox vs scale', expect, self.mpp)
        vis = view.get('visualization', {})
        self.date = vis.get('date')
        ti = vis.get('timeInterval', {})
        self.start = ti.get('start')
        self.end = ti.get('end')

    def to_dev(self, x, y):
        return ((x - self.minx) / self.mpp, (self.maxy - y) / self.mpp)


def read_asc(path):
    lines = read_text(path).splitlines()
    hdr = {}
    i = 0
    while i < len(lines):
        parts = lines[i].split()
        if len(parts) == 2 and parts[0].lower() in ('ncols', 'nrows', 'xllcorner', 'yllcorner',
                                                    'cellsize', 'nodata_value', 'xllcenter', 'yllcenter'):
            hdr[parts[0].lower()] = float(parts[1])
            i += 1
        else:
            break
    rows = [[float(x) for x in ln.split()] for ln in lines[i:] if ln.strip()]
    arr = np.array(rows, dtype=float)
    nod = hdr.get('nodata_value')
    if nod is not None:
        arr[arr == nod] = np.nan
    assert arr.shape == (int(hdr['nrows']), int(hdr['ncols'])), arr.shape
    return {'arr': arr, 'xll': hdr['xllcorner'], 'yll': hdr['yllcorner'], 'cs': hdr['cellsize']}


def load_layer(case_dir, lid):
    """Return ('vector', geojson_dict) or ('coverage', {band: grid})."""
    gj = os.path.join(case_dir, lid + '.geojson')
    if os.path.exists(gj):
        return 'vector', load_json(gj)
    bands = {}
    for p in glob.glob(os.path.join(case_dir, lid + '.*.asc')):
        base = os.path.basename(p)
        band = base[len(lid) + 1:-len('.asc')]
        bands[band] = read_asc(p)
    if bands:
        return 'coverage', bands
    raise FileNotFoundError('no data for layer %s in %s' % (lid, case_dir))


# ------------------------------------------------------ geometry in device px

def convert_geometry(geom, frame):
    t = geom['type']
    c = geom['coordinates']
    tr = frame.to_dev
    pts, lines, polys = [], [], []
    if t == 'Point':
        pts = [tr(*c)]
    elif t == 'MultiPoint':
        pts = [tr(*p) for p in c]
    elif t == 'LineString':
        lines = [[tr(*p) for p in c]]
    elif t == 'MultiLineString':
        lines = [[tr(*p) for p in part] for part in c]
    elif t == 'Polygon':
        polys = [[[tr(*p) for p in ring] for ring in c]]
    elif t == 'MultiPolygon':
        polys = [[[tr(*p) for p in ring] for ring in poly] for poly in c]
    else:
        raise ValueError('geometry type ' + t)
    return pts, lines, polys


def polyline_lengths(pl):
    segs = []
    tot = 0.0
    for a, b in zip(pl[:-1], pl[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append(d)
        tot += d
    return segs, tot


def point_at(pl, segs, s):
    acc = 0.0
    for (a, b), d in zip(zip(pl[:-1], pl[1:]), segs):
        if acc + d >= s and d > 0:
            t = (s - acc) / d
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        acc += d
    return pl[-1]


# ------------------------------------------------------------- style helpers

def opacity_of(d, default=1.0):
    if d is None:
        return 0.0
    if 'opacity' not in d:
        return default
    return min(1.0, max(0.0, num(d['opacity'])))


def get_fill(sym):
    if 'fill' not in sym:
        return {'colour': (1.0, 1.0, 1.0), 'alpha': 1.0, 'hatch': None, 'dot': None, 'stipple': None}
    f = sym['fill']
    if f is None:
        return None
    colour = parse_colour(f['color']) if 'color' in f else (1.0, 1.0, 1.0)
    return {'colour': colour, 'alpha': opacity_of(f),
            'hatch': f.get('hatch'), 'dot': f.get('dotpattern'), 'stipple': f.get('stipple')}


def get_stroke(sym, mpp):
    if 'stroke' not in sym:
        return {'colour': (0.0, 0.0, 0.0), 'alpha': 1.0, 'width': 1.0, 'dash': None,
                'offset': 0.0, 'casing': None, 'center': None}
    s = sym['stroke']
    if s is None:
        return None
    return strokestyle(s, mpp, full=True)


def strokestyle(s, mpp, full=False):
    colour = parse_colour(s['color']) if 'color' in s else (0.0, 0.0, 0.0)
    width = to_px(s['width'], mpp) if 'width' in s else 1.0
    out = {'colour': colour, 'alpha': opacity_of(s), 'width': width}
    if full:
        dp = s.get('dashPattern')
        dash = None
        if isinstance(dp, list) and dp:
            dash = [to_px(x, mpp) for x in dp]
            if sum(dash) <= 0:
                dash = None
        out['dash'] = dash
        out['offset'] = to_px(s['dashOffset'], mpp) if 'dashOffset' in s else 0.0
        out['casing'] = strokestyle(s['casing'], mpp) if isinstance(s.get('casing'), dict) else None
        cen = s.get('center', s.get('centerLine'))     # text says center, schema says centerLine
        out['center'] = strokestyle(cen, mpp) if isinstance(cen, dict) else None
    return out


def get_markers(sym):
    if 'marker' not in sym:
        return [{'type': 'Dot', 'size': 10.0, 'color': 'white'}]   # default Marker (clause 7 defaults)
    m = sym['marker']
    if m is None:
        return []
    if isinstance(m, dict) and 'elements' in m:
        els = m['elements']
        return els if isinstance(els, list) else []
    if isinstance(m, dict) and not m:
        return [{'type': 'Dot', 'size': 10.0, 'color': 'white'}]   # empty object still yields the default Dot (clause 7 NOTE)
    if isinstance(m, dict):
        return [m]
    return []


def get_label(sym):
    if 'label' not in sym or sym['label'] is None:
        return None
    lab = sym['label']
    els = lab.get('elements') if isinstance(lab, dict) else None
    if not isinstance(els, list):
        return None
    return {'elements': els, 'placement': lab.get('placement') if isinstance(lab.get('placement'), dict) else {}}


# ----------------------------------------------------------- cairo drawing

def set_rgba(cr, colour, alpha):
    cr.set_source_rgba(colour[0], colour[1], colour[2], alpha)


def polygon_path(cr, polys):
    for poly in polys:
        for ring in poly:
            if not ring:
                continue
            cr.move_to(*ring[0])
            for p in ring[1:]:
                cr.line_to(*p)
            cr.close_path()


def line_path(cr, lines, polys):
    for pl in lines:
        if len(pl) < 2:
            continue
        cr.move_to(*pl[0])
        for p in pl[1:]:
            cr.line_to(*p)
    for poly in polys:
        for ring in poly:
            if len(ring) < 2:
                continue
            cr.move_to(*ring[0])
            for p in ring[1:]:
                cr.line_to(*p)
            cr.close_path()


def stroke_geom(cr, it, width, colour, alpha, dash=None, offset=0.0):
    if width <= 0 or alpha <= 0:
        return
    cr.new_path()
    line_path(cr, it['lines'], it['polys'])
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)     # clause 8: butt caps by default
    cr.set_line_join(cairo.LINE_JOIN_MITER)  # and miter joins
    if dash:
        cr.set_dash(dash, offset)
    else:
        cr.set_dash([], 0)
    set_rgba(cr, colour, alpha)
    cr.stroke()
    cr.set_dash([], 0)


def paint_rgba(cr, rgb, alpha, W, H, opacity=1.0):
    """Paint a per-pixel colour (H,W,3 in 0..1) with alpha (H,W in 0..1)."""
    a = np.clip(np.nan_to_num(alpha, nan=0.0), 0.0, 1.0)
    c = np.clip(np.nan_to_num(rgb, nan=0.0), 0.0, 1.0)
    bgra = np.empty((H, W, 4), dtype=np.uint8)
    bgra[..., 0] = np.round(c[..., 2] * a * 255).astype(np.uint8)
    bgra[..., 1] = np.round(c[..., 1] * a * 255).astype(np.uint8)
    bgra[..., 2] = np.round(c[..., 0] * a * 255).astype(np.uint8)
    bgra[..., 3] = np.round(a * 255).astype(np.uint8)
    surf = cairo.ImageSurface.create_for_data(memoryview(bgra), cairo.FORMAT_ARGB32, W, H, W * 4)
    cr.save()
    cr.set_source_surface(surf, 0, 0)
    cr.paint_with_alpha(opacity)
    cr.restore()


def draw_hatch(cr, polys, colour, alpha, width, angle_deg, dist, W, H):
    if width <= 0 or dist <= 0 or alpha <= 0:
        return
    cr.save()
    cr.new_path()
    polygon_path(cr, polys)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.clip()
    th = math.radians(angle_deg)
    dx, dy = math.cos(th), -math.sin(th)     # counter-clockwise as seen on the map (y is down here)
    nx, ny = math.sin(th), math.cos(th)      # normal to the lines
    corners = [(0, 0), (W, 0), (0, H), (W, H)]
    ss = [px * nx + py * ny for px, py in corners]
    k0 = int(math.floor(min(ss) / dist)) - 1
    k1 = int(math.ceil(max(ss) / dist)) + 1
    L = W + H
    cr.new_path()
    for k in range(k0, k1 + 1):
        s = k * dist                         # the line through the top left corner is k = 0
        px0, py0 = nx * s, ny * s
        cr.move_to(px0 - dx * L, py0 - dy * L)
        cr.line_to(px0 + dx * L, py0 + dy * L)
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    set_rgba(cr, colour, alpha)
    cr.stroke()
    cr.restore()


def draw_dotpattern(cr, polys, colour, alpha, hdist, vdist, W, H):
    if hdist <= 0 or vdist <= 0 or alpha <= 0:
        return
    cr.save()
    cr.new_path()
    polygon_path(cr, polys)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.clip()
    set_rgba(cr, colour, alpha)
    j = 0
    while (j + 0.5) * vdist < H:
        y = (j + 0.5) * vdist
        i = 0
        while (i + 0.5) * hdist < W:
            x = (i + 0.5) * hdist
            cr.new_path()
            cr.arc(x, y, 1.0, 0, PI2)          # 2 px diameter (clause 12, /req/dot-patterns/dotpattern)
            cr.fill()
            i += 1
        j += 1
    cr.restore()


def polygon_mask(polys, W, H):
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    for poly in polys:
        d.polygon([tuple(p) for p in poly[0]], fill=1)
        for hole in poly[1:]:
            d.polygon([tuple(p) for p in hole], fill=0)
    return np.asarray(im).astype(bool)


def draw_stipple(cr, polys, ratio, colour, alpha, seed, W, H):
    """Random dots of 2 px diameter, placed until they cover `ratio` of the area
    of the polygon (pixel-centre count). Seeded per feature for repeatability."""
    if ratio <= 0 or alpha <= 0:
        return
    mask = polygon_mask(polys, W, H)
    total = int(mask.sum())
    if total == 0:
        return
    target = ratio * total
    ys, xs = np.nonzero(mask)
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1
    rng = np.random.default_rng(seed)
    covered = np.zeros_like(mask)
    count = 0
    cr.save()
    cr.new_path()
    polygon_path(cr, polys)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.clip()
    set_rgba(cr, colour, alpha)
    tries = 0
    while count < target and tries < 3000000:
        px = rng.uniform(x0, x1)
        py = rng.uniform(y0, y1)
        tries += 1
        ix, iy = int(px), int(py)
        if not mask[iy, ix]:
            continue
        cr.new_path()
        cr.arc(px, py, 1.0, 0, PI2)
        cr.fill()
        wx0, wx1 = max(0, ix - 2), min(W, ix + 3)
        wy0, wy1 = max(0, iy - 2), min(H, iy + 3)
        gx = np.arange(wx0, wx1) + 0.5
        gy = np.arange(wy0, wy1) + 0.5
        disk = ((gx[None, :] - px) ** 2 + (gy[:, None] - py) ** 2) <= 1.0
        sub_m = mask[wy0:wy1, wx0:wx1]
        sub_c = covered[wy0:wy1, wx0:wx1]
        newly = disk & sub_m & ~sub_c
        count += int(newly.sum())
        sub_c |= disk & sub_m
    cr.restore()


# ------------------------------------------------------------------ text

def font_px(pt):
    """Points (1/72 inch) to device pixels of 0.28 mm."""
    return pt * PT_MM / PX_MM


def text_layout(cr, text, font, align, x, y):
    size_px = font_px(num(font.get('size'), FONT_DEFAULT_PT))
    slant = cairo.FONT_SLANT_ITALIC if font.get('italic') is True else cairo.FONT_SLANT_NORMAL
    weight = cairo.FONT_WEIGHT_BOLD if font.get('bold') is True else cairo.FONT_WEIGHT_NORMAL
    face = font.get('face') or FONT_DEFAULT_FACE
    cr.select_font_face(face, slant, weight)
    cr.set_font_size(size_px)
    fe = cr.font_extents()
    asc, desc = fe[0], fe[1]
    w = cr.text_extents(text).x_advance
    h, v = align
    if h == 'left':
        x0 = x
    elif h == 'right':
        x0 = x - w
    else:
        x0 = x - w / 2.0
    if v == 'top':
        by = y + asc
    elif v == 'bottom':
        by = y - desc
    else:
        by = y + (asc - desc) / 2.0
    box = (x0, by - asc, x0 + w, by + desc)
    return {'text': text, 'font': font, 'x0': x0, 'by': by, 'box': box,
            'size_px': size_px, 'face': face, 'slant': slant, 'weight': weight}


def draw_text_layout(cr, L, colour, alpha, outline):
    cr.save()
    cr.select_font_face(L['face'], L['slant'], L['weight'])
    cr.set_font_size(L['size_px'])
    if outline and num(outline.get('size')) > 0 and opacity_of(outline) > 0:
        ocol = parse_colour(outline['color']) if 'color' in outline else (0.0, 0.0, 0.0)
        ow = 2.0 * num(outline.get('size'))   # outward extension of `size` px (clause 10)
        cr.new_path()
        cr.move_to(L['x0'], L['by'])
        cr.text_path(L['text'])
        cr.set_line_width(ow)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        set_rgba(cr, ocol, opacity_of(outline, 1.0) * alpha)
        cr.stroke()
    cr.new_path()
    cr.move_to(L['x0'], L['by'])
    set_rgba(cr, colour, alpha)
    cr.show_text(L['text'])
    cr.restore()


def text_string(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def text_element_layout(cr, el, ax, ay, mpp):
    font = el.get('font') if isinstance(el.get('font'), dict) else {}
    al = el.get('alignment')
    if isinstance(al, list) and len(al) == 2:
        align = (al[0] or 'center', al[1] or 'middle')
    elif isinstance(al, dict):
        align = (al.get('horzAlignment') or 'center', al.get('vertAlignment') or 'middle')
    else:
        align = ('center', 'middle')
    dx, dy = element_offset(el, mpp)
    text = text_string(el.get('text'))
    L = text_layout(cr, text, font, align, ax + dx, ay - dy)
    colour = parse_colour(font['color']) if 'color' in font else (0.0, 0.0, 0.0)
    alpha = opacity_of(font) * opacity_of(el)
    outline = font.get('outline') if isinstance(font.get('outline'), dict) else None
    outw = num(outline.get('size')) if outline else 0.0
    b = L['box']
    L['box'] = (b[0] - outw, b[1] - outw, b[2] + outw, b[3] + outw)
    L['colour'] = colour
    L['alpha'] = alpha
    L['outline'] = outline
    return L


def element_offset(el, mpp):
    p = el.get('position')
    if p is None:
        return 0.0, 0.0
    if isinstance(p, list):
        return to_px(p[0], mpp), to_px(p[1], mpp)
    return to_px(p.get('x'), mpp), to_px(p.get('y'), mpp)


# ------------------------------------------------------------- markers

def draw_element(cr, el, ax, ay, mpp, base_alpha=1.0):
    t = el.get('type')
    dx, dy = element_offset(el, mpp)
    x, y = ax + dx, ay - dy
    eop = opacity_of(el)
    if t == 'Dot':
        st = el.get('stroke') if isinstance(el.get('stroke'), dict) else None
        if 'size' in el:
            size = to_px(el['size'], mpp)
        elif st is not None and 'width' in st:
            size = to_px(st['width'], mpp)
        else:
            size = 10.0
        if 'color' in el:
            col = parse_colour(el['color'])
        elif st is not None and 'color' in st:
            col = parse_colour(st['color'])
        else:
            col = (1.0, 1.0, 1.0)
        if size <= 0:
            return
        cr.save()
        cr.new_path()
        cr.arc(x, y, size / 2.0, 0, PI2)
        set_rgba(cr, col, eop * base_alpha)
        cr.fill()
        cr.restore()
    elif t == 'Text':
        L = text_element_layout(cr, el, x, y, mpp)
        draw_text_layout(cr, L, L['colour'], L['alpha'] * base_alpha, L['outline'])
    elif t == 'Image':
        draw_image(cr, el, x, y, mpp, eop * base_alpha)


_IMG_CACHE = {}


def draw_image(cr, el, x, y, mpp, alpha):
    res = el.get('image') or {}
    rel = res.get('path')
    if rel is None:
        return
    path = os.path.normpath(os.path.join(CASE_DIR[0], rel))
    if path not in _IMG_CACHE:
        im = Image.open(path).convert('RGBA')
        arr = np.asarray(im).astype(float) / 255.0
        tint = parse_colour(el['tint']) if 'tint' in el else (1.0, 1.0, 1.0)
        btint = parse_colour(el['blackTint']) if 'blackTint' in el else (0.0, 0.0, 0.0)
        v = arr[..., :3]
        out_rgb = np.empty_like(v)
        for c in range(3):
            out_rgb[..., c] = tint[c] * v[..., c] + btint[c] * (1.0 - v[..., c])
        _IMG_CACHE[path] = (out_rgb, arr[..., 3])
    rgb, a = _IMG_CACHE[path]
    h, w = a.shape
    hs = el.get('hotSpot')
    if isinstance(hs, list) and len(hs) == 2:
        hx = hot_coord(hs[0], w, mpp)
        hy = hot_coord(hs[1], h, mpp)
    elif isinstance(hs, dict):
        hx = hot_coord(hs.get('x'), w, mpp)
        hy = hot_coord(hs.get('y'), h, mpp)
    else:
        hx, hy = 0.5 * w, 0.5 * h
    left = int(round(x - hx))
    top = int(round(y - hy))
    # the image is drawn at its own pixel size (1 image pixel = 1 device pixel): choice, see notes
    bgra = np.empty((h, w, 4), dtype=np.uint8)
    al = a
    bgra[..., 0] = np.round(rgb[..., 2] * al * 255).astype(np.uint8)
    bgra[..., 1] = np.round(rgb[..., 1] * al * 255).astype(np.uint8)
    bgra[..., 2] = np.round(rgb[..., 0] * al * 255).astype(np.uint8)
    bgra[..., 3] = np.round(al * 255).astype(np.uint8)
    surf = cairo.ImageSurface.create_for_data(memoryview(bgra), cairo.FORMAT_ARGB32, w, h, w * 4)
    cr.save()
    cr.set_source_surface(surf, left, top)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.rectangle(left, top, w, h)
    cr.clip()
    cr.paint_with_alpha(alpha)
    cr.restore()


CASE_DIR = ['']


# ------------------------------------------------------------- coverage

def colour_map(vals, entries):
    xs = np.array([e[0] for e in entries], dtype=float)
    cols = np.array([e[1] for e in entries], dtype=float)
    out = np.empty(vals.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(vals, xs, cols[:, c])
    return out


def opacity_map(vals, entries):
    xs = np.array([e[0] for e in entries], dtype=float)
    ys = np.array([e[1] for e in entries], dtype=float)
    return np.interp(vals, xs, ys)


def parse_map(lst, kind):
    out = []
    for e in lst:
        if kind == 'colour':
            out.append((num(e[0]), parse_colour(e[1])))
        else:
            out.append((num(e[0]), num(e[1])))
    out.sort(key=lambda t: t[0])
    return out


def render_coverage(cr, bands, sym, env, frame):
    W, H, mpp = frame.W, frame.H, frame.mpp
    sc = sym.get('singleChannel')
    band = sc.get('property') if isinstance(sc, dict) else None
    if band is None or band not in bands:
        return
    g = bands[band]
    arr, cs = g['arr'], g['cs']
    nr, nc = arr.shape
    top = g['yll'] + nr * cs
    gx = frame.minx + (np.arange(W) + 0.5) * mpp
    gy = frame.maxy - (np.arange(H) + 0.5) * mpp
    ci = np.floor((gx - g['xll']) / cs).astype(int)
    ri = np.floor((top - gy) / cs).astype(int)
    if mpp <= cs * (1 + 1e-9):
        # map is as fine as or finer than the coverage: samples are the cells
        Z = arr
        d = cs
        RI = np.clip(ri, 0, nr - 1)[:, None]
        CI = np.clip(ci, 0, nc - 1)[None, :]
        valid = ((ri >= 0) & (ri < nr))[:, None] & ((ci >= 0) & (ci < nc))[None, :]
    else:
        # map is coarser: the coverage is resampled (nearest cell) to the map pixels
        RIc = np.clip(ri, 0, nr - 1)
        CIc = np.clip(ci, 0, nc - 1)
        valid = ((ri >= 0) & (ri < nr))[:, None] & ((ci >= 0) & (ci < nc))[None, :]
        Z = arr[RIc[:, None], CIc[None, :]].copy()
        Z[~valid] = np.nan
        d = mpp
        RI = np.arange(H)[:, None]
        CI = np.arange(W)[None, :]
        valid = np.ones((H, W), dtype=bool)
    Zs = Z
    Sh = None
    hs = sym.get('hillShading')
    if isinstance(hs, dict):
        f = num(hs['factor'], 1.0) if 'factor' in hs else 1.0
        sun = hs.get('sun') if isinstance(hs.get('sun'), dict) else {}
        az = math.radians(num(sun.get('azimuth'), 315.0) if 'azimuth' in sun else 315.0)
        el = math.radians(num(sun.get('elevation'), 45.0) if 'elevation' in sun else 45.0)
        zp = np.pad(Zs, 1, mode='edge')
        dzdE = (zp[1:-1, 2:] - zp[1:-1, :-2]) / (2 * d)
        dzdN = (zp[:-2, 1:-1] - zp[2:, 1:-1]) / (2 * d)   # north is the row above
        nx, ny, nz = -f * dzdE, -f * dzdN, np.ones_like(dzdE)
        nl = np.sqrt(nx * nx + ny * ny + nz * nz)
        sx, sy, sz = math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)
        Sh = np.clip((nx * sx + ny * sy + nz * sz) / nl, 0.0, 1.0)
    Vpx = Zs[RI, CI]
    finite = np.isfinite(Vpx) & valid
    if 'colorMap' in sym and isinstance(sym['colorMap'], list):
        cm = parse_map(sym['colorMap'], 'colour')
        rgb = colour_map(np.nan_to_num(Vpx, nan=0.0), cm)
    else:
        rgb = np.ones((H, W, 3))
    alpha = np.ones((H, W))
    if Sh is not None:
        Shpx = Sh[RI, CI]
        if isinstance(hs.get('colorMap'), list):
            hcm = parse_map(hs['colorMap'], 'colour')
            rgb = colour_map(np.nan_to_num(Shpx, nan=0.0), hcm)
        else:
            rgb = rgb * np.nan_to_num(Shpx, nan=0.0)[..., None]
        if isinstance(hs.get('opacityMap'), list):
            hom = parse_map(hs['opacityMap'], 'opacity')
            alpha = alpha * opacity_map(np.nan_to_num(Shpx, nan=0.0), hom)
    if isinstance(sym.get('opacityMap'), list):
        om = parse_map(sym['opacityMap'], 'opacity')
        alpha = alpha * opacity_map(np.nan_to_num(Vpx, nan=0.0), om)
    alpha = np.where(finite, alpha, 0.0)
    paint_rgba(cr, rgb, alpha, W, H, opacity_of(sym))


# ------------------------------------------------------------- vector main

def shape_centroid(geom):
    return g_shape(geom).centroid


def draw_vector_main(cr, it, frame, idx):
    sym = it['sym']
    mpp = frame.mpp
    op = opacity_of(sym)
    if op <= 0:
        return
    grouped = op < 1.0
    if grouped:
        cr.push_group()                      # opacity applied to the feature as a whole (rec/core/opacity-together)
    fill = get_fill(sym) if it['polys'] else None
    if fill is not None and fill['alpha'] > 0:
        W, H = frame.W, frame.H
        if fill['hatch'] is not None or fill['dot'] is not None or fill['stipple'] is not None:
            # hatch, dot pattern and stipple paint no area between their marks
            if isinstance(fill['hatch'], dict):
                h = fill['hatch']
                draw_hatch(cr, it['polys'], fill['colour'], fill['alpha'],
                           to_px(h['width'], mpp) if 'width' in h else 1.0,
                           num(h['angle'], 45.0) if 'angle' in h else 45.0,
                           (to_px(h['distance'], mpp) if 'distance' in h else 10.0), W, H)
            if isinstance(fill['dot'], dict):
                dd = fill['dot'].get('distance')
                if isinstance(dd, dict):
                    hd = to_px(dd['horizontal'], mpp) if 'horizontal' in dd else 10.0
                    vd = to_px(dd['vertical'], mpp) if 'vertical' in dd else 10.0
                elif isinstance(dd, list) and len(dd) == 2:
                    hd, vd = to_px(dd[0], mpp), to_px(dd[1], mpp)
                else:
                    hd = vd = 10.0
                draw_dotpattern(cr, it['polys'], fill['colour'], fill['alpha'], hd, vd, W, H)
            if isinstance(fill['stipple'], dict):
                ratio = num(fill['stipple'].get('ratio'), 0.0)
                draw_stipple(cr, it['polys'], ratio, fill['colour'], fill['alpha'], 1000 + idx, W, H)
        else:
            cr.new_path()
            polygon_path(cr, it['polys'])
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            set_rgba(cr, fill['colour'], fill['alpha'])
            cr.fill()
    st = get_stroke(sym, mpp)
    if st is not None and st['width'] > 0:
        stroke_geom(cr, it, st['width'], st['colour'], st['alpha'], st['dash'], st['offset'])
    # markers
    els = get_markers(sym)
    if els:
        anchors = marker_anchors(it, frame)
        for ax, ay in anchors:
            for el in els:
                if isinstance(el, dict):
                    draw_element(cr, resolve_el(el), ax, ay, mpp)
    if grouped:
        cr.pop_group_to_source()
        cr.paint_with_alpha(op)


def resolve_el(el):
    return el


def marker_anchors(it, frame):
    """Points for markers: points, every vertex of a line, the centroid of a polygon."""
    out = list(it['pts'])
    for pl in it['lines']:
        out.extend(pl)
    if it['polys']:
        c = it['centroid_dev']
        if c is not None:
            out.append(c)
    return out


def draw_casing_and_center(cr, it, frame, phase):
    sym = it['sym']
    mpp = frame.mpp
    op = opacity_of(sym)
    if op <= 0:
        return
    st = get_stroke(sym, mpp)
    if st is None:
        return
    if phase == 'casing' and st['casing'] is not None:
        c = st['casing']
        total = st['width'] + 2.0 * c['width']
        grouped = op < 1.0
        if grouped:
            cr.push_group()
        stroke_geom(cr, it, total, c['colour'], c['alpha'])
        if grouped:
            cr.pop_group_to_source()
            cr.paint_with_alpha(op)
    if phase == 'center' and st['center'] is not None:
        c = st['center']
        grouped = op < 1.0
        if grouped:
            cr.push_group()
        stroke_geom(cr, it, c['width'], c['colour'], c['alpha'])
        if grouped:
            cr.pop_group_to_source()
            cr.paint_with_alpha(op)


# ------------------------------------------------------------- labels

def label_candidates(it, lab, frame, cr):
    """Candidate anchors for a label of one feature. Returns list of candidate dicts."""
    pl = lab['placement']
    prio = num(ev_prio(pl), 0.0)
    cands = []
    text_key = ''.join(text_string(e.get('text')) for e in lab['elements'] if e.get('type') == 'Text')
    minsp = None
    if 'minSpacing' in pl and pl['minSpacing'] is not None:
        minsp = to_px(pl['minSpacing'], frame.mpp)
    for x, y in it['pts']:
        cands.append({'kind': 'point', 'anchor': (x, y), 'prio': prio, 'it': it, 'lab': lab, 'key': None})
    if it['polys'] and it['centroid_dev'] is not None:
        cands.append({'kind': 'point', 'anchor': it['centroid_dev'], 'prio': prio, 'it': it, 'lab': lab, 'key': None})
    for pl_ in it['lines']:
        if len(pl_) < 2:
            continue
        if minsp is not None:
            cands.append({'kind': 'line-rep', 'line': pl_, 'prio': prio, 'it': it, 'lab': lab,
                          'key': (it['layer'], text_key), 'minsp': minsp})
        else:
            segs, tot = polyline_lengths(pl_)
            cands.append({'kind': 'point', 'anchor': point_at(pl_, segs, tot / 2.0), 'prio': prio,
                          'it': it, 'lab': lab, 'key': None})
    return cands


def ev_prio(pl):
    p = pl.get('priority')
    return p


def label_boxes(cr, lab, ax, ay, frame):
    Ls = []
    for el in lab['elements']:
        if el.get('type') == 'Text':
            Ls.append(text_element_layout(cr, el, ax, ay, frame.mpp))
    return Ls


def boxes_ok(Ls, frame, placed):
    for L in Ls:
        b = L['box']
        if b[0] < 0 or b[1] < 0 or b[2] > frame.W or b[3] > frame.H:
            return False
    for L in Ls:
        b = L['box']
        for p in placed:
            for q in p:
                if b[0] < q['box'][2] and q['box'][0] < b[2] and b[1] < q['box'][3] and q['box'][1] < b[3]:
                    return False
    return True


def place_labels(cr, items, frame):
    cands = []
    for it in items:
        if it.get('lab') is None:
            continue
        cands.extend(label_candidates(it, it['lab'], frame, cr))
    # higher priority placed first; ties keep layer and feature order
    order = sorted(range(len(cands)), key=lambda i: (-cands[i]['prio'], cands[i]['it']['li'], cands[i]['it']['fi'], i))
    placed = []           # list of lists of text layouts already placed
    groups = {}           # repetition group -> accepted anchors
    drawn = []
    for i in order:
        c = cands[i]
        lab = c['lab']
        if c['kind'] == 'point':
            ax, ay = c['anchor']
            Ls = label_boxes(cr, lab, ax, ay, frame)
            if Ls and boxes_ok(Ls, frame, placed):
                placed.append(Ls)
                drawn.append((c, ax, ay, Ls))
        else:
            pl_ = c['line']
            segs, tot = polyline_lengths(pl_)
            acc = groups.setdefault(c['key'], [])
            s = 0.0
            while s <= tot:
                ax, ay = point_at(pl_, segs, s)
                s += 1.0
                if any(math.hypot(ax - bx, ay - by) < c['minsp'] for bx, by in acc):
                    continue
                Ls = label_boxes(cr, lab, ax, ay, frame)
                if not Ls or not boxes_ok(Ls, frame, placed):
                    continue
                placed.append(Ls)
                acc.append((ax, ay))
                drawn.append((c, ax, ay, Ls))
    for c, ax, ay, Ls in drawn:
        for el in c['lab']['elements']:
            if el.get('type') == 'Dot':
                draw_element(cr, el, ax, ay, frame.mpp)
        for L in Ls:
            draw_text_layout(cr, L, L['colour'], L['alpha'], L['outline'])


# ------------------------------------------------------------- driver

def build_items(style, view, case_dir, frame):
    rules = style.get('stylingRules', [])
    items = []
    layer_ids = view['layers']
    for li, lid in enumerate(layer_ids):
        kind, data = load_layer(case_dir, lid)
        if kind == 'vector':
            feats = data['features']
            for fi, f in enumerate(feats):
                props = f.get('properties') or {}
                env = {'layer': lid, 'ltype': 'vector', 'props': props, 'scale': frame.scale,
                       'date': frame.date, 'start': frame.start, 'end': frame.end,
                       'fid': fi, 'gdim': None}
                state = apply_rules(rules, env, {})
                sym = resolve(state, env)
                if sym.get('visibility', True) is not True and 'visibility' in sym:
                    continue
                pts, lines, polys = convert_geometry(f['geometry'], frame)
                shp = g_shape(f['geometry'])
                cen = None
                if polys:
                    c = shp.centroid
                    cen = frame.to_dev(c.x, c.y)
                z = 1 if 'zOrder' not in sym else num(sym['zOrder'])
                items.append({'kind': 'vector', 'z': z, 'li': li, 'fi': fi, 'layer': lid, 'sym': sym,
                              'pts': pts, 'lines': lines, 'polys': polys, 'centroid_dev': cen,
                              'lab': get_label(sym)})
        else:
            env = {'layer': lid, 'ltype': 'coverage', 'props': {}, 'scale': frame.scale,
                   'date': frame.date, 'start': frame.start, 'end': frame.end, 'fid': None, 'gdim': None}
            state = apply_rules(rules, env, {})
            band_ref = state.get('singleChannel')      # keep the band name (a property reference)
            state = {k: v for k, v in state.items() if k != 'singleChannel'}
            sym = resolve(state, env)
            if band_ref is not None:
                sym['singleChannel'] = band_ref
            if sym.get('visibility', True) is not True and 'visibility' in sym:
                continue
            z = 1 if 'zOrder' not in sym else num(sym['zOrder'])
            items.append({'kind': 'coverage', 'z': z, 'li': li, 'fi': 0, 'layer': lid, 'sym': sym,
                          'bands': data, 'pts': [], 'lines': [], 'polys': [], 'centroid_dev': None,
                          'lab': None})
    return items


def render(case, n, view_path, frame_out):
    case_dir = os.path.join(CASES, case)
    CASE_DIR[0] = case_dir
    style = load_json(os.path.join(case_dir, 'style.cs.json'))
    view = load_json(view_path)
    frame = Frame(view)
    W, H = frame.W, frame.H
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    bg = parse_colour(view.get('background', 'white'))
    cr.set_source_rgb(*bg)
    cr.paint()
    items = build_items(style, view, case_dir, frame)
    zs = sorted(set(it['z'] for it in items))
    for z in zs:
        grp = [it for it in items if it['z'] == z]
        # casings of all features of this zOrder beneath all main strokes
        for it in grp:
            if it['kind'] == 'vector':
                draw_casing_and_center(cr, it, frame, 'casing')
        for it in grp:
            if it['kind'] == 'coverage':
                render_coverage(cr, it['bands'], it['sym'], {'props': {}}, frame)
            else:
                draw_vector_main(cr, it, frame, idx=it['li'] * 100000 + it['fi'])
        # centre lines of all features of this zOrder on top of all main strokes
        for it in grp:
            if it['kind'] == 'vector':
                draw_casing_and_center(cr, it, frame, 'center')
    place_labels(cr, [it for it in items if it['kind'] == 'vector'], frame)
    surf.write_to_png(frame_out)


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    cases = argv or sorted(d for d in os.listdir(CASES) if os.path.isdir(os.path.join(CASES, d)))
    failed = []
    for case in cases:
        cdir = os.path.join(CASES, case)
        views = sorted(glob.glob(os.path.join(cdir, 'view-*.json')))
        for vp in views:
            n = re.search(r'view-(\d+)\.json$', vp).group(1)
            out = os.path.join(OUT, '%s-%s.png' % (case, n))
            try:
                render(case, n, vp, out)
                print('ok', os.path.relpath(out, HERE))
            except Exception:
                failed.append(case + '-' + n)
                print('FAILED', case, n)
                traceback.print_exc()
    print('failed:', failed)


if __name__ == '__main__':
    main(sys.argv[1:])
