"""Renderer for OGC Cartographic Symbology 2.0 Part 1 (draft), written from spec/ only.
Usage: render.py [case ...]   (default: all cases)
"""
import sys, os, re, json, math, datetime, random, copy
import numpy as np
import cairo
from PIL import Image
import shapely
from shapely.geometry import shape, Polygon, LineString, Point

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, 'cases')
OUT = os.path.join(ROOT, 'out')


def jload(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------- colors
def load_color_names():
    names = {}
    p = os.path.join(ROOT, 'spec', '1-core', 'sections', 'clause_17_cscss.adoc')
    with open(p, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^\s*\|?\s+(\w+)\s+\|\s+`0x([0-9a-fA-F]{6})`', line)
            if m:
                h = m.group(2)
                names[m.group(1).lower()] = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return names


COLOR_NAMES = load_color_names()


def parse_color(c, scale255=True):
    """Returns (r,g,b) in 0..1.  Default black for null (null table)."""
    if c is None:
        return (0.0, 0.0, 0.0)
    if isinstance(c, str):
        if c.startswith('#'):
            h = c[1:]
            if len(h) == 3:
                h = ''.join(ch * 2 for ch in h)
            return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return COLOR_NAMES[c.lower()]
    if isinstance(c, (list, tuple)):
        d = 255.0 if scale255 else 1.0
        return tuple(float(v) / d for v in c[:3])
    if isinstance(c, dict):
        d = 255.0 if scale255 else 1.0
        return tuple(float(c.get(k, 0)) / d for k in 'rgb')
    raise ValueError('color %r' % (c,))


# ---------------------------------------------------------------- expressions
def to_date(v):
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        try:
            return datetime.date.fromisoformat(v[:10])
        except Exception:
            return None
    return None


def cmp_vals(a, b):
    """returns (a,b) coerced for comparison, or None if null"""
    if a is None or b is None:
        return None
    if isinstance(a, datetime.date) or isinstance(b, datetime.date):
        da, db = to_date(a), to_date(b)
        if da is not None and db is not None:
            return da, db
    if isinstance(a, bool) or isinstance(b, bool):
        return a, b
    return a, b


class Ctx:
    def __init__(self, props, layer_id, layer_type, view):
        self.props = props
        self.layer_id = layer_id
        self.layer_type = layer_type
        self.view = view


def sysid(name, ctx):
    v = ctx.view
    if name in ('dataLayer.id', 'dataLayer.identifier'):
        return ctx.layer_id
    if name == 'dataLayer.type':
        return ctx.layer_type
    if name in ('viz.sd', 'visualization.scaleDenominator'):
        return float(v['scaleDenominator'])
    if name in ('viz.date', 'viz.dateTime.date', 'visualization.date'):
        return to_date(v['visualization']['date'])
    m = re.match(r'viz\.timeInterval\.(start|end)(\.date)?$', name)
    if m:
        return to_date(v['visualization']['timeInterval'][m.group(1)])
    if name == 'viz.timeInterval':
        return v['visualization']['timeInterval']
    if name.startswith('capabilities'):
        return True
    raise KeyError('system identifier ' + name)


def ev(e, ctx):
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, list):
        return [ev(x, ctx) for x in e]
    if isinstance(e, dict):
        if 'property' in e:
            return ctx.props.get(e['property']) if ctx.props is not None else None
        if 'sysId' in e:
            return sysid(e['sysId'], ctx)
        if 'op' in e:
            return do_op(e['op'], e['args'], ctx)
        for u in ('px', 'mm', 'cm', 'in', 'pt', 'em', 'pc', 'm', 'ft'):
            if u in e:
                return {u: ev(e[u], ctx)}
        return e
    return e


def tri_and(vals):
    res = True
    for v in vals:
        if v is False:
            return False
        if v is None:
            res = None
    return res


def tri_or(vals):
    res = False
    for v in vals:
        if v is True:
            return True
        if v is None:
            res = None
    return res


def do_op(op, args, ctx):
    if op == 'and':
        return tri_and([ev(a, ctx) for a in args])
    if op == 'or':
        return tri_or([ev(a, ctx) for a in args])
    if op == 'not':
        v = ev(args[0], ctx)
        return None if v is None else (not v)
    vals = [ev(a, ctx) for a in args]
    if op == 'isNull':
        return vals[0] is None
    if op in ('=', '<>', '<', '>', '<=', '>='):
        c = cmp_vals(vals[0], vals[1])
        if c is None:
            return None
        a, b = c
        try:
            return {'=': a == b, '<>': a != b, '<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op]
        except TypeError:
            return None
    if op in ('in', 'notIn'):
        if vals[0] is None:
            return None
        r = vals[0] in vals[1]
        return r if op == 'in' else not r
    if op in ('between', 'notBetween'):
        if any(v is None for v in vals):
            return None
        r = vals[1] <= vals[0] <= vals[2]
        return r if op == 'between' else not r
    if any(v is None for v in vals):
        return None
    if op in ('+', 'add'):
        return vals[0] + vals[1]
    if op in ('-', 'sub'):
        return vals[0] - vals[1]
    if op in ('*', 'mul'):
        return vals[0] * vals[1]
    if op in ('/', 'div'):
        return None if vals[1] == 0 else vals[0] / vals[1]
    if op == 'intDiv':
        return None if vals[1] == 0 else int(vals[0] / vals[1])
    if op in ('%', 'mod'):
        return None if vals[1] == 0 else math.fmod(vals[0], vals[1])
    if op in ('^', 'pow'):
        return vals[0] ** vals[1]
    raise KeyError('operator ' + op)


# ---------------------------------------------------------------- style resolution
def merge(base, upd):
    """apply symbolizer property update `upd` over `base` (both dict-like values)."""
    if isinstance(upd, dict) and upd.get('alter') is True:
        res = dict(base) if isinstance(base, dict) else {}
        for k, v in upd.items():
            if k == 'alter':
                continue
            res[k] = merge(res.get(k), v) if isinstance(v, dict) and v.get('alter') else v
        return res
    return upd


def apply_symbolizer(cur, sym):
    for k, v in sym.items():
        if k == '$comment':
            continue
        if k == 'marker' or k == 'label':
            if isinstance(v, dict) and v.get('alter') and isinstance(cur.get(k), dict):
                nv = dict(cur[k])
                for kk, vv in v.items():
                    if kk == 'alter':
                        continue
                    if kk == 'elements' and isinstance(vv, dict) and 'index' in vv:
                        els = list(nv.get('elements', []))
                        els[vv['index']] = merge(els[vv['index']], vv['value']) if isinstance(vv['value'], dict) and vv['value'].get('alter') else vv['value']
                        nv['elements'] = els
                    else:
                        nv[kk] = merge(nv.get(kk), vv) if isinstance(vv, dict) and vv.get('alter') else vv
                cur[k] = nv
            else:
                cur[k] = v
        elif isinstance(v, dict) and v.get('alter') is True:
            cur[k] = merge(cur.get(k), v)
        else:
            cur[k] = v


def resolve_rules(rules, ctx, cur):
    """rules applied in order; nested rules after their parent's symbolizer."""
    for r in rules:
        sel = r.get('selector')
        if sel is None or ev(sel, ctx) is True:
            if r.get('symbolizer'):
                apply_symbolizer(cur, r['symbolizer'])
            if r.get('nestedRules'):
                resolve_rules(r['nestedRules'], ctx, cur)


# ---------------------------------------------------------------- units
class Units:
    def __init__(self, view):
        self.mm = float(view.get('pixelSize_mm', 0.28))
        self.m_per_px = float(view['scaleDenominator']) * self.mm / 1000.0

    def px(self, v, ctx, default=0.0, none_val=0.0):
        """length value -> pixels (unitless = px)"""
        if v is None:
            return none_val
        v = ev(v, ctx)
        if v is None:
            return 0.0  # null -> 0
        if isinstance(v, dict):
            u, x = next(iter(v.items()))
            x = ev(x, ctx)
            if x is None:
                return 0.0
            return x * self.factor(u)
        return float(v)

    def factor(self, u):
        mm = self.mm
        return {'px': 1.0, 'mm': 1 / mm, 'cm': 10 / mm, 'in': 25.4 / mm, 'pt': 25.4 / 72 / mm,
                'm': 1 / self.m_per_px, 'ft': 0.3048 / self.m_per_px}[u]


# ---------------------------------------------------------------- canvas helpers
class Canvas:
    def __init__(self, view):
        self.w = int(view['width'])
        self.h = int(view['height'])
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.cr = cairo.Context(self.surf)
        self.cr.set_source_rgb(*parse_color(view.get('background', 'white')))
        self.cr.paint()
        x0, y0, x1, y1 = view['bbox']
        self.x0, self.y1 = x0, y1
        self.sx = self.w / (x1 - x0)
        self.sy = self.h / (y1 - y0)

    def px(self, X, Y):
        return ((X - self.x0) * self.sx, (self.y1 - Y) * self.sy)


def geom_to_px(g, cv):
    t = g['type']
    c = g['coordinates']
    f = lambda pt: cv.px(pt[0], pt[1])
    if t == 'Point':
        return 'points', [f(c)]
    if t == 'MultiPoint':
        return 'points', [f(p) for p in c]
    if t == 'LineString':
        return 'lines', [[f(p) for p in c]]
    if t == 'MultiLineString':
        return 'lines', [[f(p) for p in l] for l in c]
    if t == 'Polygon':
        return 'polys', [[[f(p) for p in ring] for ring in c]]
    if t == 'MultiPolygon':
        return 'polys', [[[f(p) for p in ring] for ring in poly] for poly in c]
    raise ValueError(t)


def path_rings(cr, polys):
    for poly in polys:
        for ring in poly:
            cr.move_to(*ring[0])
            for p in ring[1:]:
                cr.line_to(*p)
            cr.close_path()


def set_rgba(cr, col, a):
    cr.set_source_rgba(col[0], col[1], col[2], a)


# ---------------------------------------------------------------- maps (coverage)
def interp_map(entries, v, key):
    """entries: sorted list of (value, x) with x scalar or tuple; linear interpolation."""
    if v <= entries[0][0]:
        return entries[0][1]
    if v >= entries[-1][0]:
        return entries[-1][1]
    for (v0, a), (v1, b) in zip(entries, entries[1:]):
        if v0 <= v <= v1:
            if v1 == v0:
                return b
            t = (v - v0) / (v1 - v0)
            if isinstance(a, tuple):
                return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))
            return a + (b - a) * t
    return entries[-1][1]


def prep_color_map(cm, ctx, scale255=True):
    ents = []
    for e in cm:
        ents.append((float(ev(e[0], ctx)), parse_color(ev(e[1], ctx), scale255)))
    ents.sort(key=lambda t: t[0])
    return ents


def prep_opacity_map(om, ctx):
    ents = [(float(ev(e[0], ctx)), float(ev(e[1], ctx))) for e in om]
    ents.sort(key=lambda t: t[0])
    return ents


def map_array_color(ents, arr):
    vals = np.array([e[0] for e in ents])
    cols = np.array([e[1] for e in ents])
    out = np.zeros(arr.shape + (3,))
    for i in range(3):
        out[..., i] = np.interp(arr, vals, cols[:, i])
    return out


def map_array_scalar(ents, arr):
    return np.interp(arr, [e[0] for e in ents], [e[1] for e in ents])


def load_asc(path):
    with open(path, encoding='utf-8') as f:
        hdr = {}
        for _ in range(6):
            k, v = f.readline().split()
            hdr[k.lower()] = float(v)
        data = np.loadtxt(f)
    return hdr, data.reshape(int(hdr['nrows']), int(hdr['ncols']))


def hillshade_cells(z, cellsize, factor, az, el):
    """shade per cell: central differences over twice the cell distance, edge sample repeated."""
    zp = np.pad(z, 1, mode='edge')
    dzdx = (zp[1:-1, 2:] - zp[1:-1, :-2]) / (2 * cellsize)  # east
    dzdy = (zp[:-2, 1:-1] - zp[2:, 1:-1]) / (2 * cellsize)  # north (row 0 is north)
    nx, ny, nz = -dzdx * factor, -dzdy * factor, np.ones_like(z)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    a, e = math.radians(az), math.radians(el)
    sx, sy, sz = math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)
    return np.clip(nx * sx + ny * sy + nz * sz, 0.0, 1.0)


def render_coverage(cv, layer, sym, ctx, units):
    hdr, grids = layer['hdr'], layer['bands']
    ncols, nrows, cs = int(hdr['ncols']), int(hdr['nrows']), hdr['cellsize']
    xll, yll = hdr['xllcorner'], hdr['yllcorner']
    # pixel centers -> cells
    xs = cv.x0 + (np.arange(cv.w) + 0.5) / cv.sx
    ys = cv.y1 - (np.arange(cv.h) + 0.5) / cv.sy
    col = np.floor((xs - xll) / cs).astype(int)
    row = np.floor(((yll + nrows * cs) - ys) / cs).astype(int)
    inx = (col >= 0) & (col < ncols)
    iny = (row >= 0) & (row < nrows)
    colc, rowc = np.clip(col, 0, ncols - 1), np.clip(row, 0, nrows - 1)

    nodata = hdr.get('nodata_value', -9999)
    ctx_cells = None
    # single channel
    sc = sym.get('singleChannel')
    cc = sym.get('colorChannels')
    props_list = grids

    def band_expr(expr):
        # evaluate identifier expression to array over cells
        if isinstance(expr, dict) and 'property' in expr:
            return grids[expr['property']].copy()
        if isinstance(expr, (int, float)):
            return np.full((nrows, ncols), float(expr))
        if isinstance(expr, dict) and 'op' in expr:
            a = [band_expr(x) for x in expr['args']]
            op = expr['op']
            return {'+': a[0] + a[1] if len(a) > 1 else None, '-': a[0] - a[1] if len(a) > 1 else None,
                    '*': a[0] * a[1] if len(a) > 1 else None, '/': a[0] / a[1] if len(a) > 1 else None}[op]
        raise ValueError('coverage expression %r' % (expr,))

    rgb = np.zeros((nrows, ncols, 3))
    alpha = np.ones((nrows, ncols))
    valid = np.ones((nrows, ncols), bool)
    for g in grids.values():
        valid &= (g != nodata)
    shade = None
    if sc is not None:
        v = band_expr(sc)
        cmap = sym.get('colorMap')
        if cmap:
            rgb = map_array_color(prep_color_map(cmap, ctx), v)
        else:
            gray = np.clip(v, 0, 1)
            rgb = np.stack([gray] * 3, -1)
        omap = sym.get('opacityMap')
        if omap:
            alpha = alpha * map_array_scalar(prep_opacity_map(omap, ctx), v)
    elif cc is not None:
        for i, k in enumerate('rgb'):
            comp = cc[k] if isinstance(cc, dict) else cc[i]
            rgb[..., i] = np.clip(band_expr(comp), 0, 1)
    else:
        # default: first band(s) as color channels
        names = list(grids)
        if len(names) >= 3:
            for i in range(3):
                rgb[..., i] = np.clip(grids[names[i]], 0, 1)
        else:
            gray = np.clip(grids[names[0]], 0, 1)
            rgb = np.stack([gray] * 3, -1)
    ach = sym.get('alphaChannel')
    if ach is not None:
        alpha = alpha * np.clip(band_expr(ach), 0, 1)

    hs = sym.get('hillShading')
    if hs:
        elev = band_expr(sc) if sc is not None else list(grids.values())[0]
        sun = hs.get('sun', {})
        shade = hillshade_cells(elev, cs, float(ev(hs.get('factor', 1), ctx)),
                                float(ev(sun.get('azimuth', 0), ctx)), float(ev(sun.get('elevation', 90), ctx)))
        if hs.get('colorMap'):
            rgb = map_array_color(prep_color_map(hs['colorMap'], ctx, scale255=True), shade)
        else:
            rgb = rgb * shade[..., None]
        if hs.get('opacityMap'):
            alpha = alpha * map_array_scalar(prep_opacity_map(hs['opacityMap'], ctx), shade)

    op = float(ev(sym.get('opacity', 1), ctx) or 0)
    alpha = alpha * op * valid
    # sample into pixels (cell containing the pixel center)
    prgb = rgb[rowc][:, colc]
    pal = alpha[rowc][:, colc] * (iny[:, None] & inx[None, :])
    bgra = np.zeros((cv.h, cv.w, 4), np.uint8)
    bgra[..., 0] = np.round(prgb[..., 2] * pal * 255)
    bgra[..., 1] = np.round(prgb[..., 1] * pal * 255)
    bgra[..., 2] = np.round(prgb[..., 0] * pal * 255)
    bgra[..., 3] = np.round(pal * 255)
    data = bytearray(bgra.tobytes())
    s = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, cv.w, cv.h, cv.w * 4)
    cv.cr.set_source_surface(s, 0, 0)
    cv.cr.paint()


# ---------------------------------------------------------------- fonts / text
PT = None


class FontSpec:
    pass


def font_of(font, ctx, units):
    f = FontSpec()
    font = font or {}
    f.face = ev(font.get('face'), ctx) or 'Arial'
    size_pt = ev(font.get('size'), ctx)
    size_pt = 10.0 if size_pt is None else float(size_pt)
    f.px = size_pt * 25.4 / 72 / units.mm
    f.bold = bool(ev(font.get('bold'), ctx))
    f.italic = bool(ev(font.get('italic'), ctx))
    f.color = parse_color(ev(font.get('color'), ctx)) if font.get('color') is not None else (0.0, 0.0, 0.0)
    f.opacity = float(ev(font.get('opacity', 1), ctx))
    o = font.get('outline')
    f.outline = None
    if o:
        f.outline = (float(ev(o.get('size', 1), ctx)), parse_color(ev(o.get('color'), ctx)) if o.get('color') is not None else (0.0, 0.0, 0.0),
                     float(ev(o.get('opacity', 1), ctx)))
    return f


def fmt_text(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


_meas = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


def set_font(cr, f):
    cr.select_font_face(f.face, cairo.FONT_SLANT_ITALIC if f.italic else cairo.FONT_SLANT_NORMAL,
                        cairo.FONT_WEIGHT_BOLD if f.bold else cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(f.px)


def text_box(text, f, px, py, halign, valign):
    """box (x0,y0,x1,y1) in px and baseline origin for text anchored at (px,py)."""
    set_font(_meas, f)
    asc, desc = _meas.font_extents()[0], _meas.font_extents()[1]
    w = _meas.text_extents(text).x_advance
    x0 = {'left': px, 'center': px - w / 2, 'right': px - w}[halign]
    top = {'top': py, 'middle': py - (asc + desc) / 2, 'bottom': py - asc - desc}[valign]
    return (x0, top, x0 + w, top + asc + desc), (x0, top + asc)


def draw_text(cr, text, f, px, py, halign, valign, opacity=1.0):
    box, (bx, by) = text_box(text, f, px, py, halign, valign)
    set_font(cr, f)
    if f.outline and f.outline[0] > 0:
        size, col, oo = f.outline
        cr.save()
        cr.move_to(bx, by)
        cr.text_path(text)
        cr.set_line_width(2 * size)  # extends `size` outward from the contour
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        set_rgba(cr, col, oo * opacity)
        cr.stroke()
        cr.restore()
    cr.move_to(bx, by)
    cr.text_path(text)
    set_rgba(cr, f.color, f.opacity * opacity)
    cr.fill()
    return box


def align_of(a, ctx):
    a = ev(a, ctx)
    if a is None:
        return 'center', 'middle'
    if isinstance(a, list):
        return a[0], a[1]
    return a.get('hAlignment', a.get('horzAlignment', 'center')), a.get('vAlignment', a.get('vertAlignment', 'middle'))


# ---------------------------------------------------------------- graphics
ICON_CACHE = {}


def load_icon(case_dir, res, tint, blacktint):
    p = res.get('path')
    if p is None:
        raise FileNotFoundError('no path in resource (only path supported)')
    full = os.path.normpath(os.path.join(case_dir, p))
    key = (full, tint, blacktint)
    if key in ICON_CACHE:
        return ICON_CACHE[key]
    im = np.asarray(Image.open(full).convert('RGBA')).astype(float) / 255
    rgb, a = im[..., :3], im[..., 3]
    t = np.array(tint)[None, None, :]
    b = np.array(blacktint)[None, None, :]
    out = t * rgb + b * (1 - rgb)
    h, w = a.shape
    bgra = np.zeros((h, w, 4), np.uint8)
    bgra[..., 0] = np.round(out[..., 2] * a * 255)
    bgra[..., 1] = np.round(out[..., 1] * a * 255)
    bgra[..., 2] = np.round(out[..., 0] * a * 255)
    bgra[..., 3] = np.round(a * 255)
    data = bytearray(bgra.tobytes())
    s = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h, w * 4)
    ICON_CACHE[key] = (s, data, w, h)
    return ICON_CACHE[key]


def elem_offset(el, ctx, units):
    p = el.get('position')
    if p is None:
        return 0.0, 0.0
    p = ev(p, ctx)
    if isinstance(p, dict) and not any(k in p for k in ('px', 'mm', 'cm', 'in', 'pt', 'm', 'ft', 'em', 'pc')):
        x, y = p.get('x', 0), p.get('y', 0)
    else:
        x, y = p[0], p[1]
    return units.px(x, ctx), -units.px(y, ctx)  # +y is up on the map


def dot_params(el, ctx, units):
    size = el.get('size')
    stroke = el.get('stroke') or {}
    if size is None and 'width' in stroke:
        size = stroke['width']
    size_px = units.px(size, ctx) if size is not None else 10.0
    col = el.get('color', stroke.get('color'))
    col = parse_color(ev(col, ctx)) if col is not None else (1.0, 1.0, 1.0)
    return size_px, col


def draw_graphic(cr, el, ax, ay, ctx, units, case_dir, opacity=1.0, measure_only=False):
    """draw graphic element at anchor (ax,ay) (px); returns bbox."""
    ox, oy = elem_offset(el, ctx, units)
    x, y = ax + ox, ay + oy
    gop = float(ev(el.get('opacity', 1), ctx)) * opacity
    t = el.get('type')
    if t == 'Dot':
        size, col = dot_params(el, ctx, units)
        if size <= 0:
            return None
        if not measure_only:
            cr.new_path()
            cr.arc(x, y, size / 2, 0, 2 * math.pi)
            set_rgba(cr, col, gop)
            cr.fill()
        return (x - size / 2, y - size / 2, x + size / 2, y + size / 2)
    if t == 'Image':
        tint = parse_color(ev(el['tint'], ctx)) if el.get('tint') is not None else (1.0, 1.0, 1.0)
        bt = parse_color(ev(el['blackTint'], ctx)) if el.get('blackTint') is not None else (0.0, 0.0, 0.0)
        s, data, w, h = load_icon(case_dir, el['image'], tint, bt)
        hs = el.get('hotSpot')
        hx, hy = 0.5 * w, 0.5 * h
        if hs is not None:
            hs = ev(hs, ctx)
            if isinstance(hs, dict) and 'x' in hs:
                hs = [hs['x'], hs['y']]
            vals = []
            for i, v in enumerate(hs[:2]):
                full = w if i == 0 else h
                if isinstance(v, dict):
                    u, n = next(iter(v.items()))
                    vals.append(n / 100.0 * full if u == 'pc' else n * units.factor(u))
                else:
                    vals.append(float(v) * full)  # number without unit: fraction
            hx, hy = vals
        if not measure_only:
            cr.save()
            cr.set_source_surface(s, x - hx, y - hy)
            cr.paint_with_alpha(gop)
            cr.restore()
        return (x - hx, y - hy, x - hx + w, y - hy + h)
    if t == 'Text':
        text = fmt_text(ev(el.get('text'), ctx))
        if text == '':
            return None
        f = font_of(el.get('font'), ctx, units)
        ha, va = align_of(el.get('alignment'), ctx)
        if measure_only:
            return text_box(text, f, x, y, ha, va)[0]
        return draw_text(cr, text, f, x, y, ha, va, gop)
    raise ValueError('graphic type %r' % t)


# ---------------------------------------------------------------- feature drawing
def stroke_params(sym, ctx, units):
    st = sym.get('stroke')
    if st is None:
        st = {}
    if ev(st, ctx) is None and not st:
        pass
    width = units.px(st['width'], ctx) if 'width' in st else 1.0
    col = parse_color(ev(st['color'], ctx)) if st.get('color') is not None else (0.0, 0.0, 0.0)
    op = float(ev(st.get('opacity', 1), ctx))
    return width, col, op, st


def draw_stroke_path(cr, lines_or_polys, kind):
    cr.new_path()
    if kind == 'lines':
        for l in lines_or_polys:
            cr.move_to(*l[0])
            for p in l[1:]:
                cr.line_to(*p)
    else:
        path_rings(cr, lines_or_polys)


def rings_for_stroke(kind, geo):
    return geo


def fill_pattern(cr, cv, polys, fill, ctx, units, seed):
    col = parse_color(ev(fill['color'], ctx)) if fill.get('color') is not None else (1.0, 1.0, 1.0)
    op = float(ev(fill.get('opacity', 1), ctx))
    if fill.get('hatch') is not None:
        h = fill['hatch']
        width = units.px(h['width'], ctx) if 'width' in h else 1.0
        ang = float(ev(h.get('angle', 45), ctx))
        dist = units.px(h['distance'], ctx) if 'distance' in h else 10.0
        if dist <= 0:
            return
        th = math.radians(ang)
        d = (math.cos(th), -math.sin(th))  # counter-clockwise on the map (y down on screen)
        n = (math.sin(th), math.cos(th))
        corners = [(0, 0), (cv.w, 0), (0, cv.h), (cv.w, cv.h)]
        ks = [(px * n[0] + py * n[1]) / dist for px, py in corners]
        L = math.hypot(cv.w, cv.h)
        cr.save()
        cr.new_path()
        path_rings(cr, polys)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.clip()
        cr.new_path()
        for k in range(math.floor(min(ks)) - 1, math.ceil(max(ks)) + 2):
            cx, cy = k * dist * n[0], k * dist * n[1]
            cr.move_to(cx - d[0] * L, cy - d[1] * L)
            cr.line_to(cx + d[0] * L, cy + d[1] * L)
        cr.set_line_width(width)
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        set_rgba(cr, col, op)
        cr.stroke()
        cr.restore()
        return
    if fill.get('dotpattern') is not None:
        dist = fill['dotpattern'].get('distance')
        if isinstance(dist, list):
            hd, vd = units.px(dist[0], ctx), units.px(dist[1], ctx)
        else:
            hd, vd = units.px(dist['horizontal'], ctx), units.px(dist['vertical'], ctx)
        if hd <= 0 or vd <= 0:
            return
        cr.save()
        cr.new_path()
        path_rings(cr, polys)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.clip()
        cr.new_path()
        y = vd / 2
        while y < cv.h + 1:
            x = hd / 2
            while x < cv.w + 1:
                cr.new_sub_path()
                cr.arc(x, y, 1.0, 0, 2 * math.pi)
                x += hd
            y += vd
        set_rgba(cr, col, op)
        cr.fill()
        cr.restore()
        return
    if fill.get('stipple') is not None:
        ratio = float(ev(fill['stipple'].get('ratio', 0), ctx))
        ratio = min(max(ratio, 0.0), 1.0)
        pg = None
        for poly in polys:
            p = Polygon(poly[0], poly[1:])
            pg = p if pg is None else pg.union(p)
        if pg is None or ratio <= 0:
            return
        if ratio >= 1:
            cr.new_path()
            path_rings(cr, polys)
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            set_rgba(cr, col, op)
            cr.fill()
            return
        r = 1.0
        area = pg.area
        n = int(round(-math.log(1 - ratio) * area / (math.pi * r * r)))
        rng = np.random.default_rng(seed)
        minx, miny, maxx, maxy = pg.bounds
        pts = []
        while len(pts) < n:
            m = max(n * 2, 100)
            xs = rng.uniform(minx, maxx, m)
            ys = rng.uniform(miny, maxy, m)
            ok = shapely.contains_xy(pg, xs, ys)
            pts.extend(zip(xs[ok], ys[ok]))
        cr.new_path()
        for x, y in pts[:n]:
            cr.new_sub_path()
            cr.arc(x, y, r, 0, 2 * math.pi)
        set_rgba(cr, col, op)
        cr.fill()
        return
    # plain fill
    cr.new_path()
    path_rings(cr, polys)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    set_rgba(cr, col, op)
    cr.fill()


def marker_anchors(kind, geo):
    if kind == 'points':
        return list(geo)
    if kind == 'lines':
        return [p for l in geo for p in l]
    res = []
    for poly in geo:
        c = Polygon(poly[0], poly[1:]).centroid
        res.append((c.x, c.y))
    return res


def stroke_dash(cr, st, ctx, units):
    dp = st.get('dashPattern')
    if dp:
        dp = ev(dp, ctx)
        arr = [units.px(x, ctx) for x in dp]
        if arr and sum(arr) > 0 and all(a >= 0 for a in arr):
            off = units.px(st['dashOffset'], ctx) if st.get('dashOffset') is not None else 0.0
            cr.set_dash(arr, off)
            return
    cr.set_dash([])


def do_stroke(cr, kind, geo, width, col, op, dash_st, ctx, units):
    if width <= 0 or op <= 0:
        return
    draw_stroke_path(cr, geo, kind)
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    cr.set_line_join(cairo.LINE_JOIN_MITER)
    if dash_st is not None:
        stroke_dash(cr, dash_st, ctx, units)
    else:
        cr.set_dash([])
    set_rgba(cr, col, op)
    cr.stroke()
    cr.set_dash([])


# ---------------------------------------------------------------- main rendering
DEFAULT_SYM = {}


def render(case, vidx_name):
    cdir = os.path.join(CASES, case)
    style = jload(os.path.join(cdir, 'style.cs.json'))
    view = jload(os.path.join(cdir, vidx_name))
    units = Units(view)
    cv = Canvas(view)
    cr = cv.cr
    rules = style.get('stylingRules', [])

    # load layers
    layers = []
    for li, lid in enumerate(view['layers']):
        gp = os.path.join(cdir, lid + '.geojson')
        if os.path.exists(gp):
            gj = jload(gp)
            layers.append({'id': lid, 'type': 'vector', 'features': gj['features'], 'idx': li})
        else:
            bands = {}
            hdr = None
            for fn in sorted(os.listdir(cdir)):
                m = re.match(re.escape(lid) + r'\.(.+)\.asc$', fn)
                if m:
                    hdr, bands[m.group(1)] = load_asc(os.path.join(cdir, fn))
            layers.append({'id': lid, 'type': 'coverage', 'hdr': hdr, 'bands': bands, 'idx': li})

    items = []  # draw items
    labels = []
    for L in layers:
        if L['type'] == 'coverage':
            ctx = Ctx(None, L['id'], 'coverage', view)
            sym = {}
            resolve_rules(rules, ctx, sym)
            if ev(sym.get('visibility', True), ctx) is False or (sym.get('visibility') is not None and not ev(sym['visibility'], ctx)):
                continue
            z = ev(sym.get('zOrder', 1), ctx)
            items.append({'z': 1 if sym.get('zOrder') is None else (0 if z is None else z), 'layer': L['idx'], 'f': 0, 'kind': 'coverage',
                          'L': L, 'sym': sym, 'ctx': ctx})
            continue
        for fi, feat in enumerate(L['features']):
            ctx = Ctx(feat['properties'], L['id'], 'vector', view)
            sym = {}
            resolve_rules(rules, ctx, sym)
            vis = ev(sym['visibility'], ctx) if 'visibility' in sym else True
            if vis is None:
                vis = False
            if not vis:
                continue
            z = ev(sym['zOrder'], ctx) if 'zOrder' in sym else 1
            kind, geo = geom_to_px(feat['geometry'], cv)
            items.append({'z': 0 if z is None else z, 'layer': L['idx'], 'f': fi, 'kind': 'vector', 'gk': kind, 'geo': geo,
                          'sym': sym, 'ctx': ctx, 'L': L})

    items.sort(key=lambda it: (it['z'], it['layer'], it['f']))
    zs = sorted(set(it['z'] for it in items))
    for z in zs:
        grp = [it for it in items if it['z'] == z]
        # pass 1: casings
        for it in grp:
            if it['kind'] != 'vector':
                continue
            sym, ctx = it['sym'], it['ctx']
            if it['gk'] == 'points':
                continue
            width, col, op, st = stroke_params(sym, ctx, units)
            cas = st.get('casing')
            if cas and width > 0:
                cw = units.px(cas['width'], ctx) if 'width' in cas else 0.0
                ccol = parse_color(ev(cas['color'], ctx)) if cas.get('color') is not None else (0.0, 0.0, 0.0)
                cop = float(ev(cas.get('opacity', 1), ctx)) * float(ev(sym.get('opacity', 1), ctx))
                geo = it['geo']
                do_stroke(cr, 'lines' if it['gk'] == 'lines' else 'polys', geo, width + 2 * cw, ccol, cop, None, ctx, units)
        # pass 2: main
        for it in grp:
            sym, ctx = it['sym'], it['ctx']
            if it['kind'] == 'coverage':
                render_coverage(cv, it['L'], sym, ctx, units)
                continue
            opacity = float(ev(sym.get('opacity', 1), ctx) or 0)
            grouped = opacity < 1.0
            if grouped:
                cr.push_group()
            gk, geo = it['gk'], it['geo']
            if gk == 'polys':
                fill = sym.get('fill')
                fill = {} if fill is None else fill
                if fill.get('opacity', 1) is not None:
                    fill_pattern(cr, cv, geo, fill, ctx, units, seed=it['f'] * 7919 + it['layer'])
            if gk in ('lines', 'polys'):
                width, col, op, st = stroke_params(sym, ctx, units)
                do_stroke(cr, 'lines' if gk == 'lines' else 'polys', geo, width, col, op, st, ctx, units)
            mk = sym.get('marker', {'elements': [{'type': 'Dot'}]} if 'marker' not in sym else None)
            if 'marker' not in sym:
                mk = {'elements': [{'type': 'Dot'}]}
            if mk is not None and mk != {}:
                els = mk.get('elements', [{'type': 'Dot'}]) if isinstance(mk, dict) and 'elements' in mk else (
                    [mk] if isinstance(mk, dict) and 'type' in mk else [{'type': 'Dot'}])
                for (ax, ay) in marker_anchors(gk, geo):
                    for el in els:
                        draw_graphic(cr, el, ax, ay, ctx, units, cdir)
            if grouped:
                cr.pop_group_to_source()
                cr.paint_with_alpha(opacity)
        # pass 3: center lines
        for it in grp:
            if it['kind'] != 'vector' or it['gk'] == 'points':
                continue
            sym, ctx = it['sym'], it['ctx']
            width, col, op, st = stroke_params(sym, ctx, units)
            cen = st.get('center', st.get('centerLine'))
            if cen:
                cw = units.px(cen['width'], ctx) if 'width' in cen else 1.0
                ccol = parse_color(ev(cen['color'], ctx)) if cen.get('color') is not None else (0.0, 0.0, 0.0)
                cop = float(ev(cen.get('opacity', 1), ctx)) * float(ev(sym.get('opacity', 1), ctx))
                do_stroke(cr, 'lines' if it['gk'] == 'lines' else 'polys', it['geo'], cw, ccol, cop, None, ctx, units)

    # ---- labels (separate pass on top)
    cands = []
    for it in items:
        if it['kind'] != 'vector':
            continue
        lab = it['sym'].get('label')
        if not lab or not lab.get('elements'):
            continue
        ctx = it['ctx']
        pl = lab.get('placement') or {}
        prio = ev(pl.get('priority'), ctx) if pl.get('priority') is not None else 0
        prio = 0 if prio is None else float(prio)
        minsp = units.px(pl['minSpacing'], ctx) if pl.get('minSpacing') is not None else None
        maxsp = units.px(pl['maxSpacing'], ctx) if pl.get('maxSpacing') is not None else None
        texts = [fmt_text(ev(e.get('text'), ctx)) for e in lab['elements'] if e.get('type') == 'Text']
        key = (it['L']['id'], '|'.join(texts))
        if texts and all(t == '' for t in texts) and len(texts) == len(lab['elements']):
            continue
        cands.append({'prio': prio, 'order': (it['z'], it['layer'], it['f']), 'it': it, 'els': lab['elements'], 'minsp': minsp,
                      'maxsp': maxsp, 'key': key})
    cands.sort(key=lambda c: (-c['prio'], c['order']))
    placed_boxes = []
    placed_pts = {}

    def label_box(c, ax, ay):
        bb = None
        for el in c['els']:
            b = draw_graphic(cr, el, ax, ay, c['it']['ctx'], units, cdir, measure_only=True)
            if b is None:
                continue
            bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
        return bb

    def inside(b):
        return b[0] >= 0 and b[1] >= 0 and b[2] <= cv.w and b[3] <= cv.h

    def overlaps(b):
        for o in placed_boxes:
            if b[0] < o[2] and o[0] < b[2] and b[1] < o[3] and o[1] < b[3]:
                return True
        return False

    def try_place(c, ax, ay):
        b = label_box(c, ax, ay)
        if b is None or not inside(b) or overlaps(b):
            return False
        if c['minsp'] is not None:
            for (px_, py_) in placed_pts.get(c['key'], []):
                if math.hypot(px_ - ax, py_ - ay) < c['minsp']:
                    return False
        placed_boxes.append(b)
        placed_pts.setdefault(c['key'], []).append((ax, ay))
        for el in c['els']:
            draw_graphic(cr, el, ax, ay, c['it']['ctx'], units, cdir)
        return True

    for c in cands:
        it = c['it']
        gk, geo = it['gk'], it['geo']
        if gk == 'points':
            for p in geo:
                try_place(c, *p)
        elif gk == 'polys':
            for (ax, ay) in marker_anchors(gk, geo):
                try_place(c, ax, ay)
        else:
            for line in geo:
                ls = LineString(line)
                if ls.length == 0:
                    continue
                if c['minsp'] is None:
                    p = ls.interpolate(ls.length / 2)
                    try_place(c, p.x, p.y)
                else:
                    s = 0.0
                    while s <= ls.length:
                        p = ls.interpolate(s)
                        try_place(c, p.x, p.y)
                        s += 2.0

    os.makedirs(OUT, exist_ok=True)
    n = re.match(r'view-(\d+)\.json', vidx_name).group(1)
    outp = os.path.join(OUT, '%s-%s.png' % (case, n))
    cv.surf.write_to_png(outp)
    return outp


def main():
    names = sys.argv[1:] or sorted(d for d in os.listdir(CASES) if os.path.exists(os.path.join(CASES, d, 'style.cs.json')))
    for case in names:
        views = sorted(f for f in os.listdir(os.path.join(CASES, case)) if re.match(r'view-\d+\.json$', f))
        for v in views:
            try:
                p = render(case, v)
                print('ok  ', p)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print('FAIL', case, v, e)


if __name__ == '__main__':
    main()
