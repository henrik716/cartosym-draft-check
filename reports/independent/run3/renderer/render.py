"""Independent renderer for OGC CartoSym 2.0 Part 1 (draft), written from spec/ text only."""
import json, math, os, re, sys, copy, datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape, LineString, Polygon, Point, MultiPolygon, MultiLineString, box
from shapely.ops import unary_union, substring

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SS = 4  # supersampling factor for anti-aliasing

# ---------------------------------------------------------------- colors
def load_color_table():
    t = {}
    p = os.path.join(ROOT, 'spec', '1-core', 'sections', 'clause_17_cscss.adoc')
    for line in open(p, encoding='utf8'):
        m = re.match(r'^\s*\|?\s*(\w+)\s*\|\s*`0x([0-9a-fA-F]{6})`', line)
        if m:
            h = m.group(2)
            t[m.group(1).lower()] = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return t
COLORS = load_color_table()

def parse_color(v, ctx=None, ranged255=True):
    """-> (r,g,b) floats 0..1, or None"""
    if ctx is not None:
        v = ctx.ev(v)
    if v is None:
        return (0.0, 0.0, 0.0)  # table-parameter-values-null: Color -> black
    if isinstance(v, str):
        if v.startswith('#'):
            h = v[1:]
            if len(h) == 3:
                h = ''.join(c * 2 for c in h)
            return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return COLORS.get(v.lower(), (0.0, 0.0, 0.0))
    if isinstance(v, (list, tuple)):
        vals = [ctx.ev(x) if ctx else x for x in v]
        return tuple(min(max(float(x) / 255.0, 0), 1) for x in vals[:3])
    if isinstance(v, dict):
        return tuple(min(max(float(ctx.ev(v.get(k, 0)) if ctx else v.get(k, 0)) / 255.0, 0), 1) for k in 'rgb')
    return (0.0, 0.0, 0.0)

# ---------------------------------------------------------------- context / expressions
def parse_dt(s):
    if isinstance(s, (datetime.date, datetime.datetime)):
        return s
    try:
        if 'T' in s:
            return datetime.datetime.fromisoformat(s.replace('Z', ''))
        return datetime.date.fromisoformat(s)
    except Exception:
        return None

def to_cmp(a, b):
    """coerce two operands to comparable types"""
    isd = lambda x: isinstance(x, (datetime.date, datetime.datetime))
    if isd(a) or isd(b):
        if isinstance(a, str): a = parse_dt(a)
        if isinstance(b, str): b = parse_dt(b)
        if a is None or b is None: return None, None
        if isinstance(a, datetime.datetime) != isinstance(b, datetime.datetime):
            f = lambda x: x if isinstance(x, datetime.datetime) else datetime.datetime(x.year, x.month, x.day)
            a, b = f(a), f(b)
    return a, b

class Ctx:
    def __init__(self, view, layer_id, layer_type, props=None):
        self.view = view
        self.layer_id = layer_id
        self.layer_type = layer_type
        self.props = props or {}
        v = view['visualization']
        iv = v.get('timeInterval', {})
        def inst(s):
            d = parse_dt(s)
            if isinstance(d, datetime.datetime):
                return {'date': d.date(), 'time': {'hour': d.hour, 'minutes': d.minute, 'seconds': d.second}}
            return {'date': d, 'time': {'hour': 0, 'minutes': 0, 'seconds': 0}}
        dt = parse_dt(v.get('date'))
        if isinstance(dt, datetime.datetime):
            dd, dtt = dt.date(), dt
        else:
            dd, dtt = dt, datetime.datetime(dt.year, dt.month, dt.day) if dt else None
        self.viz = {'scaleDenominator': view['scaleDenominator'], 'date': dd, 'dateTime': dtt,
                    'timeOfDay': {'hour': dtt.hour, 'minutes': dtt.minute, 'seconds': dtt.second} if dtt else None,
                    'timeInterval': {'start': inst(iv.get('start')), 'end': inst(iv.get('end'))}}

    def sys(self, name):
        parts = name.split('.')
        alias = {'viz': 'visualization', 'sd': 'scaleDenominator', 'id': 'identifier'}
        parts = [alias.get(p, p) for p in parts]
        if parts[0] == 'dataLayer':
            if len(parts) == 1: return {'identifier': self.layer_id, 'type': self.layer_type}
            if parts[1] == 'identifier': return self.layer_id
            if parts[1] == 'type': return self.layer_type
            return None
        if parts[0] == 'capabilities':
            return True
        if parts[0] == 'visualization':
            cur = self.viz
            for p in parts[1:]:
                if isinstance(cur, dict): cur = cur.get(p)
                elif isinstance(cur, (datetime.date, datetime.datetime)):
                    cur = getattr(cur, p, None) if p != 'date' else (cur.date() if isinstance(cur, datetime.datetime) else cur)
                else: return None
            return cur
        return None

    def ev(self, e):
        if isinstance(e, dict):
            if 'property' in e:
                return self.props.get(e['property'])
            if 'sysId' in e:
                return self.sys(e['sysId'])
            if 'op' in e:
                return self.op(e['op'], e.get('args', []))
            if set(e.keys()) == {'date'}:
                return parse_dt(e['date'])
            if set(e.keys()) == {'timestamp'}:
                return parse_dt(e['timestamp'])
            return e
        if isinstance(e, list):
            return [self.ev(x) for x in e]
        return e

    def op(self, op, args):
        if op in ('and', 'or'):
            vals = [self.ev(a) for a in args]
            vals = [None if v is None else bool(v) for v in vals]
            if op == 'and':
                if any(v is False for v in vals): return False
                return None if any(v is None for v in vals) else True
            if any(v is True for v in vals): return True
            return None if any(v is None for v in vals) else False
        if op == 'not':
            v = self.ev(args[0]); return None if v is None else (not v)
        if op == '?:':
            c = self.ev(args[0])
            return self.ev(args[1]) if c else self.ev(args[2])
        vals = [self.ev(a) for a in args]
        if op in ('=', '<>', '<', '>', '<=', '>='):
            a, b = vals
            if a is None or b is None: return None
            a, b = to_cmp(a, b)
            if a is None: return None
            try:
                return {'=': a == b, '<>': a != b, '<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op]
            except TypeError:
                return None
        if op == 'isNull': return vals[0] is None
        if op == 'in':
            if vals[0] is None: return None
            return vals[0] in vals[1]
        if op == 'between':
            if any(v is None for v in vals): return None
            return vals[1] <= vals[0] <= vals[2]
        if op in ('+', '-', '*', '/', '^', 'add', 'sub', 'mul', 'div', 'pow', 'intDiv', 'mod', '%'):
            if any(v is None for v in vals): return None
            a, b = vals
            if op in ('+', 'add'): return a + b
            if op in ('-', 'sub'): return a - b
            if op in ('*', 'mul'): return a * b
            if op in ('/', 'div'): return a / b if b != 0 else None
            if op in ('^', 'pow'): return a ** b
            if op == 'intDiv': return int(a / b)
            if op in ('mod', '%'): return math.fmod(a, b)
        if op in ('lowerCase',): return None if vals[0] is None else str(vals[0]).lower()
        if op in ('upperCase',): return None if vals[0] is None else str(vals[0]).upper()
        if op == 'concatenate': return ''.join(str(v) for v in vals)
        if op == 'like':
            if vals[0] is None: return None
            pat = '^' + re.escape(str(vals[1])).replace('%', '.*').replace('_', '.') + '$'
            return re.match(pat, str(vals[0])) is not None
        if op in ('contains', 'startsWith', 'endsWith'):
            a, b = str(vals[0]), str(vals[1])
            return {'contains': b in a, 'startsWith': a.startswith(b), 'endsWith': a.endswith(b)}[op]
        raise ValueError('unsupported op ' + op)

# ---------------------------------------------------------------- units
class Units:
    def __init__(self, view):
        self.pix_mm = view['pixelSize_mm']
        self.m_per_px = view['scaleDenominator'] * self.pix_mm / 1000.0

    def px(self, v, ctx, ref=None, font_px=None):
        """uom-qualified value -> pixels (bare number = pixels)"""
        v = ctx.ev(v)
        if v is None: return 0.0
        if isinstance(v, dict):
            for u, f in (('px', 1.0), ('mm', 1 / self.pix_mm), ('cm', 10 / self.pix_mm), ('in', 25.4 / self.pix_mm),
                         ('pt', (25.4 / 72) / self.pix_mm), ('m', 1 / self.m_per_px), ('ft', 0.3048 / self.m_per_px)):
                if u in v:
                    x = ctx.ev(v[u]); return 0.0 if x is None else float(x) * f
            if 'em' in v:
                return float(ctx.ev(v['em'])) * (font_px or 10 * (25.4 / 72) / self.pix_mm)
            if 'pc' in v:
                return float(ctx.ev(v['pc'])) / 100.0 * (ref if ref is not None else 0.0)
            return 0.0
        return float(v)

    def pt_to_px(self, pt):
        return pt * (25.4 / 72) / self.pix_mm

# ---------------------------------------------------------------- style resolution
DEFAULT_SYMB = {'visibility': True, 'opacity': 1.0, 'zOrder': 1}

def merge_obj(old, new):
    """apply property `new` onto `old` following replace / alter semantics"""
    if isinstance(new, dict) and new.get('alter') is True:
        if not isinstance(old, dict):
            old = {}
        res = dict(old)
        for k, v in new.items():
            if k == 'alter': continue
            if k == 'elements' and isinstance(v, dict) and 'index' in v and 'value' in v:
                els = list(res.get('elements', []))
                i = v['index']
                while len(els) <= i: els.append({})
                els[i] = merge_obj(els[i], v['value']) if isinstance(v['value'], dict) and v['value'].get('alter') else v['value']
                res['elements'] = els
            else:
                res[k] = merge_obj(res.get(k), v)
        return res
    return copy.deepcopy(new)

def resolve_symbolizer(rules, ctx):
    sym = {}
    def walk(rs):
        for r in rs:
            sel = r.get('selector')
            ok = True if sel is None else (ctx.ev(sel) is True or ctx.ev(sel) == True)
            if sel is not None:
                v = ctx.ev(sel)
                ok = bool(v) if v is not None else False
            if not ok: continue
            for k, v in (r.get('symbolizer') or {}).items():
                if k == '$comment': continue
                sym[k] = merge_obj(sym.get(k), v)
            walk(r.get('nestedRules', []))
    walk(rules)
    return sym

# ---------------------------------------------------------------- canvas & rasterisation
class Target:
    def __init__(self, W, H, white=False):
        self.W, self.H = W, H
        self.rgb = np.ones((H, W, 3)) if white else np.zeros((H, W, 3))
        self.a = np.ones((H, W)) if white else np.zeros((H, W))
        self.box = None

    def paint(self, win, color, alpha=1.0):
        if win is None: return
        x0, y0, m = win
        h, w = m.shape
        a = m * alpha
        if np.ndim(a) == 0: return
        sl = (slice(y0, y0 + h), slice(x0, x0 + w))
        col = np.asarray(color, dtype=float)
        self.rgb[sl] = col * a[..., None] + self.rgb[sl] * (1 - a[..., None])
        self.a[sl] = a + self.a[sl] * (1 - a)
        b = (x0, y0, x0 + w, y0 + h)
        self.box = b if self.box is None else (min(b[0], self.box[0]), min(b[1], self.box[1]), max(b[2], self.box[2]), max(b[3], self.box[3]))

    def composite_onto(self, canvas, opacity):
        if self.box is None: return
        x0, y0, x1, y1 = self.box
        sl = (slice(y0, y1), slice(x0, x1))
        o = opacity
        canvas.rgb[sl] = self.rgb[sl] * o + canvas.rgb[sl] * (1 - self.a[sl, None][0] * o) if False else \
            self.rgb[sl] * o + canvas.rgb[sl] * (1 - (self.a[sl] * o)[..., None])
        canvas.a[sl] = self.a[sl] * o + canvas.a[sl] * (1 - self.a[sl] * o)

def window_for(bounds, W, H, pad=1):
    x0 = max(int(math.floor(bounds[0])) - pad, 0); y0 = max(int(math.floor(bounds[1])) - pad, 0)
    x1 = min(int(math.ceil(bounds[2])) + pad, W); y1 = min(int(math.ceil(bounds[3])) + pad, H)
    if x1 <= x0 or y1 <= y0: return None
    return x0, y0, x1, y1

def draw_polys(draw, geom, x0, y0):
    polys = []
    if geom.is_empty: return
    if geom.geom_type == 'Polygon': polys = [geom]
    elif geom.geom_type in ('MultiPolygon', 'GeometryCollection'):
        polys = [g for g in geom.geoms if g.geom_type == 'Polygon']
        for g in geom.geoms:
            if g.geom_type == 'MultiPolygon': polys += list(g.geoms)
    for p in polys:
        draw.polygon([((x - x0) * SS, (y - y0) * SS) for x, y in p.exterior.coords], fill=255)
        for r in p.interiors:
            draw.polygon([((x - x0) * SS, (y - y0) * SS) for x, y in r.coords], fill=0)

def ss_mask(geom, W, H, pad=1):
    """-> (x0,y0,x1,y1, uint8 array at SS resolution) or None"""
    if geom is None or geom.is_empty: return None
    win = window_for(geom.bounds, W, H, pad)
    if win is None: return None
    x0, y0, x1, y1 = win
    img = Image.new('L', ((x1 - x0) * SS, (y1 - y0) * SS), 0)
    draw_polys(ImageDraw.Draw(img), geom, x0, y0)
    return x0, y0, x1, y1, np.asarray(img) > 127

def down(arr, h, w):
    return arr.reshape(h, SS, w, SS).mean(axis=(1, 3))

def geom_mask(geom, W, H):
    r = ss_mask(geom, W, H)
    if r is None: return None
    x0, y0, x1, y1, a = r
    return x0, y0, down(a.astype(float), y1 - y0, x1 - x0)

# ---------------------------------------------------------------- strokes
def ring_stroke(coords_poly, hw):
    p = Polygon(coords_poly)
    if not p.is_valid: p = p.buffer(0)
    outer = p.buffer(hw, join_style=2, mitre_limit=4.0)
    inner = p.buffer(-hw, join_style=2, mitre_limit=4.0)
    return outer.difference(inner)

def line_stroke(line, hw):
    return line.buffer(hw, cap_style=2, join_style=2, mitre_limit=4.0)

def dash_line(line, pattern, offset):
    pat = list(pattern)
    if len(pat) % 2: pat = pat * 2
    tot = sum(pat)
    if tot <= 0: return [line]
    L = line.length
    out = []
    # SVG-style: dash phase starts `offset` into the pattern
    pos = -(offset % tot)
    i = 0
    while pos < L:
        ln = pat[i % len(pat)]
        if i % 2 == 0:
            a, b = max(pos, 0), min(pos + ln, L)
            if b > a: out.append(substring(line, a, b))
        pos += ln
        i += 1
        if len(out) > 20000: break
    return out

def stroke_geometry(geom, width, pattern=None, offset=0.0, grow=0.0):
    """geom: shapely in pixel coords. returns polygonal geometry of the stroke"""
    hw = width / 2.0 + grow
    parts = []
    def lines_of(g):
        if g.geom_type == 'LineString': return [g]
        if g.geom_type == 'MultiLineString': return list(g.geoms)
        return []
    def do_line(l):
        if pattern:
            for d in dash_line(l, pattern, offset): parts.append(line_stroke(d, hw))
        else:
            parts.append(line_stroke(l, hw))
    if geom.geom_type in ('LineString', 'MultiLineString'):
        for l in lines_of(geom): do_line(l)
    elif geom.geom_type in ('Polygon', 'MultiPolygon'):
        polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
        for p in polys:
            rings = [p.exterior] + list(p.interiors)
            for r in rings:
                if pattern: do_line(LineString(r.coords))
                else: parts.append(ring_stroke(r.coords, hw))
    if not parts: return None
    return unary_union(parts)

# ---------------------------------------------------------------- fills with patterns
def pattern_mask(kind, geom, W, H, params):
    r = ss_mask(geom, W, H)
    if r is None: return None
    x0, y0, x1, y1, a = r
    h, w = (y1 - y0) * SS, (x1 - x0) * SS
    ys, xs = np.mgrid[0:h, 0:w]
    X = x0 + (xs + 0.5) / SS  # pixel coords of sample centres
    Y = y0 + (ys + 0.5) / SS
    if kind == 'hatch':
        th = math.radians(params['angle'])  # clockwise on screen (y down) from the x axis
        d, wd = params['distance'], params['width']
        u = -math.sin(th) * X + math.cos(th) * Y
        f = np.abs(((u + d / 2) % d) - d / 2)
        pm = f <= wd / 2
    elif kind == 'dots':
        hx, vy, rad = params['h'], params['v'], params['r']
        dx = ((X - hx / 2) + hx / 2) % hx - hx / 2   # grid points at (i*hx + hx/2)
        dx = ((X - hx / 2 + hx / 2) % hx) - hx / 2
        gx = (X % hx) - hx / 2
        gy = (Y % vy) - vy / 2
        pm = gx * gx + gy * gy <= rad * rad
    m = (a & pm).astype(float)
    return x0, y0, down(m, y1 - y0, x1 - x0)

# ---------------------------------------------------------------- fonts / text
FONT_DIR = r'C:\Windows\Fonts'
def font_path(face, bold, italic):
    f = (face or 'Arial').lower()
    if 'times' in f:
        base = {(0, 0): 'times.ttf', (1, 0): 'timesbd.ttf', (0, 1): 'timesi.ttf', (1, 1): 'timesbi.ttf'}
    else:
        base = {(0, 0): 'arial.ttf', (1, 0): 'arialbd.ttf', (0, 1): 'ariali.ttf', (1, 1): 'arialbi.ttf'}
    return os.path.join(FONT_DIR, base[(int(bool(bold)), int(bool(italic)))])

_font_cache = {}
def get_font(face, bold, italic, size_px):
    k = (face, bool(bold), bool(italic), round(size_px * SS, 2))
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(font_path(face, bold, italic), max(1, int(round(size_px * SS))))
    return _font_cache[k]

def fmt_text(v):
    if v is None: return ''
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v)

# ---------------------------------------------------------------- element building (graphics)
class Elem:
    """A drawable graphic placed at a pixel position: has bbox and paint(target, opacity)."""
    def __init__(self, kind, **kw):
        self.kind = kind; self.__dict__.update(kw)

def build_elements(marker, ctx, U, anchor, W, H):
    """marker: resolved dict with elements list -> list of Elem placed at anchor (px coords)."""
    out = []
    if marker is None: return out
    els = marker.get('elements') if isinstance(marker, dict) else None
    if els is None: els = [{'type': 'Dot'}] if not (isinstance(marker, dict) and 'elements' in marker) else []
    for e in els:
        if not isinstance(e, dict): continue
        t = e.get('type', 'Dot')
        pos = e.get('position')
        px_, py_ = 0.0, 0.0
        if pos is not None:
            pos = ctx.ev(pos)
            if isinstance(pos, list): px_, py_ = U.px(pos[0], ctx), U.px(pos[1], ctx)
            elif isinstance(pos, dict) and 'op' not in pos: px_, py_ = U.px(pos.get('x', 0), ctx), U.px(pos.get('y', 0), ctx)
        ax, ay = anchor[0] + px_, anchor[1] + py_  # y grows downwards
        gop = ctx.ev(e.get('opacity', 1.0))
        gop = 1.0 if gop is None else float(gop)
        if t == 'Dot':
            stroke = e.get('stroke') or {}
            size = e.get('size', stroke.get('width') if isinstance(stroke, dict) else None)
            col = e.get('color', stroke.get('color') if isinstance(stroke, dict) else None)
            d = U.px(size, ctx) if size is not None else 10.0
            c = parse_color(col, ctx) if col is not None else (1.0, 1.0, 1.0)
            if d <= 0: continue
            out.append(Elem('dot', x=ax, y=ay, r=d / 2, color=c, op=gop, bbox=(ax - d / 2, ay - d / 2, ax + d / 2, ay + d / 2)))
        elif t == 'Image':
            res = e.get('image') or {}
            path = ctx.ev(res.get('path')) if res.get('path') else None
            im = load_image(path)
            if im is None: continue
            iw, ih = im.size
            hs = e.get('hotSpot')
            hx, hy = 0.5 * iw, 0.5 * ih
            if hs is not None:
                hs = ctx.ev(hs)
                def hv(v, size):
                    v = ctx.ev(v)
                    if isinstance(v, dict):
                        if 'pc' in v: return float(v['pc']) / 100.0 * size
                        return U.px(v, ctx)
                    return float(v) * size  # bare number: fraction of the image size
                if isinstance(hs, list): hx, hy = hv(hs[0], iw), hv(hs[1], ih)
                elif isinstance(hs, dict): hx, hy = hv(hs.get('x', 0.5), iw), hv(hs.get('y', 0.5), ih)
            tint = parse_color(e['tint'], ctx) if 'tint' in e else (1.0, 1.0, 1.0)
            btint = parse_color(e['blackTint'], ctx) if 'blackTint' in e else (0.0, 0.0, 0.0)
            ix, iy = int(round(ax - hx)), int(round(ay - hy))
            out.append(Elem('image', im=im, x=ix, y=iy, tint=tint, btint=btint, op=gop, bbox=(ix, iy, ix + iw, iy + ih)))
        elif t == 'Text':
            f = e.get('font') or {}
            f = ctx.ev(f) if not isinstance(f, dict) else f
            size_pt = ctx.ev(f.get('size')) if f.get('size') is not None else 10.0
            size_px = U.pt_to_px(float(size_pt if size_pt is not None else 0))
            face = ctx.ev(f.get('face')) if f.get('face') is not None else 'Arial'
            bold = bool(ctx.ev(f.get('bold'))) if f.get('bold') is not None else False
            ital = bool(ctx.ev(f.get('italic'))) if f.get('italic') is not None else False
            col = parse_color(f['color'], ctx) if f.get('color') is not None else (0.0, 0.0, 0.0)
            fop = ctx.ev(f.get('opacity', 1.0)); fop = 1.0 if fop is None else float(fop)
            ol = f.get('outline')
            outline = None
            if isinstance(ol, dict):
                osz = ctx.ev(ol.get('size', 1)); osz = 0.0 if osz is None else float(osz)
                oop = ctx.ev(ol.get('opacity', 1.0)); oop = 1.0 if oop is None else float(oop)
                outline = (osz, oop, parse_color(ol.get('color'), ctx) if ol.get('color') is not None else (0.0, 0.0, 0.0))
            text = fmt_text(ctx.ev(e.get('text')))
            if text == '' or size_px <= 0: continue
            al = e.get('alignment')
            ha, va = 'center', 'middle'
            if al is not None:
                al = ctx.ev(al)
                if isinstance(al, list): ha, va = al[0], al[1]
                elif isinstance(al, dict):
                    ha = al.get('horzAlignment', al.get('hAlignment', al.get('horizontal', ha)))
                    va = al.get('vertAlignment', al.get('vAlignment', al.get('vertical', va)))
            font = get_font(face, bold, ital, size_px)
            wpx = font.getlength(text) / SS
            asc, desc = font.getmetrics()
            hpx = (asc + desc) / SS
            x0 = ax - {'left': 0, 'center': wpx / 2, 'right': wpx}[ha]
            y0 = ay - {'top': 0, 'middle': hpx / 2, 'bottom': hpx}[va]
            pad = (outline[0] if outline else 0) + 1
            out.append(Elem('text', text=text, font=font, x=x0, y=y0, w=wpx, h=hpx, color=col, fop=fop, outline=outline,
                            op=gop, bbox=(x0 - (outline[0] if outline else 0), y0 - (outline[0] if outline else 0),
                                          x0 + wpx + (outline[0] if outline else 0), y0 + hpx + (outline[0] if outline else 0))))
    return out

_img_cache = {}
def load_image(path):
    if not path: return None
    cand = [os.path.join(CASE_DIR, path), os.path.join(CASE_DIR, 'icons', os.path.basename(path)),
            os.path.join(CASE_DIR, '..', 'icons', os.path.basename(path))]
    for c in cand:
        if os.path.exists(c):
            if c not in _img_cache: _img_cache[c] = Image.open(c).convert('RGBA')
            return _img_cache[c]
    return None

def paint_elem(T, el, W, H, sym_opacity=1.0):
    k = el.kind
    op = el.op * sym_opacity
    if k == 'dot':
        c = Point(el.x, el.y).buffer(el.r, quad_segs=24)
        T.paint(geom_mask(c, W, H), el.color, op)
    elif k == 'image':
        im = el.im; iw, ih = im.size
        a = np.asarray(im).astype(float) / 255.0
        rgb, al = a[..., :3], a[..., 3]
        col = np.array(el.tint) * rgb + np.array(el.btint) * (1 - rgb)
        x0, y0 = el.x, el.y
        cx0, cy0 = max(x0, 0), max(y0, 0); cx1, cy1 = min(x0 + iw, W), min(y0 + ih, H)
        if cx1 <= cx0 or cy1 <= cy0: return
        sl = (slice(cy0 - y0, cy1 - y0), slice(cx0 - x0, cx1 - x0))
        T.paint((cx0, cy0, al[sl]), col[sl], op)
    elif k == 'text':
        pad = int(math.ceil((el.outline[0] if el.outline else 0))) + 2
        bx0, by0 = int(math.floor(el.x)) - pad, int(math.floor(el.y)) - pad
        bx1, by1 = int(math.ceil(el.x + el.w)) + pad, int(math.ceil(el.y + el.h)) + pad
        cx0, cy0, cx1, cy1 = max(bx0, 0), max(by0, 0), min(bx1, W), min(by1, H)
        if cx1 <= cx0 or cy1 <= cy0: return
        def tmask(stroke):
            img = Image.new('L', ((bx1 - bx0) * SS, (by1 - by0) * SS), 0)
            d = ImageDraw.Draw(img)
            pos = ((el.x - bx0) * SS, (el.y - by0) * SS)
            if stroke > 0:
                d.text(pos, el.text, font=el.font, fill=255, anchor='la', stroke_width=int(round(stroke * SS)), stroke_fill=255)
            else:
                d.text(pos, el.text, font=el.font, fill=255, anchor='la')
            a = np.asarray(img).astype(float) / 255.0
            m = down(a, by1 - by0, bx1 - bx0)
            return m[cy0 - by0:cy1 - by0, cx0 - bx0:cx1 - bx0]
        if el.outline and el.outline[0] > 0:
            T.paint((cx0, cy0, tmask(el.outline[0])), el.outline[2], el.outline[1] * op)
        T.paint((cx0, cy0, tmask(0)), el.color, el.fop * op)

# ---------------------------------------------------------------- vector features
class Frame:
    def __init__(self, view):
        self.view = view
        bx0, by0, bx1, by1 = view['bbox']
        self.W, self.H = view['width'], view['height']
        self.sx = self.W / (bx1 - bx0); self.sy = self.H / (by1 - by0)
        self.bx0, self.by1 = bx0, by1
        self.bbox = view['bbox']
    def pt(self, x, y):
        return ((x - self.bx0) * self.sx, (self.by1 - y) * self.sy)
    def geom(self, g):
        from shapely.ops import transform
        return transform(lambda x, y, z=None: ((np.asarray(x) - self.bx0) * self.sx, (self.by1 - np.asarray(y)) * self.sy), g)

def num(ctx, v, default=None):
    v = ctx.ev(v)
    if v is None: return default
    return float(v)

def stroke_params(st, ctx, U):
    """resolved stroke dict -> dict(width px, color, opacity, dash, offset)"""
    st = st if isinstance(st, dict) else {}
    w = U.px(st['width'], ctx) if 'width' in st else 1.0
    c = parse_color(st['color'], ctx) if 'color' in st else (0.0, 0.0, 0.0)
    o = num(ctx, st.get('opacity', 1.0), 0.0)
    dp = None; off = 0.0
    if st.get('dashPattern') is not None:
        dpv = ctx.ev(st['dashPattern'])
        if isinstance(dpv, list): dp = [U.px(x, ctx) for x in dpv]
    if st.get('dashOffset') is not None: off = U.px(st['dashOffset'], ctx)
    return dict(width=w, color=c, opacity=o, dash=dp, offset=off)

def anchors_of(geom_px):
    t = geom_px.geom_type
    if t == 'Point': return [(geom_px.x, geom_px.y)]
    if t == 'MultiPoint': return [(p.x, p.y) for p in geom_px.geoms]
    if t == 'LineString': return list(geom_px.coords)
    if t == 'MultiLineString': return [c for l in geom_px.geoms for c in l.coords]
    if t == 'Polygon': return [(geom_px.centroid.x, geom_px.centroid.y)]
    if t == 'MultiPolygon': return [(p.centroid.x, p.centroid.y) for p in geom_px.geoms]
    return []

def load_vector(path):
    d = json.load(open(path, encoding='utf8'))
    return d['features']

class Drawable:
    pass

def make_vector_drawables(layer_id, layer_idx, feats, rules, view, F, U, labels_out):
    out = []
    W, H = F.W, F.H
    x0, y0, x1, y1 = view['bbox']
    margin = 100 / F.sx
    for fi, f in enumerate(feats):
        g = shape(f['geometry'])
        bx = g.bounds
        if bx[2] < x0 - margin or bx[0] > x1 + margin or bx[3] < y0 - margin or bx[1] > y1 + margin:
            continue
        ctx = Ctx(view, layer_id, 'vector', f.get('properties', {}))
        sym = resolve_symbolizer(rules, ctx)
        vis = ctx.ev(sym.get('visibility', True))
        vis = False if vis is None else bool(vis)
        if not vis: continue
        gp = F.geom(g)
        d = Drawable()
        d.kind = 'vector'; d.layer_idx = layer_idx; d.fi = fi; d.geom = gp; d.ctx = ctx; d.sym = sym
        z = ctx.ev(sym.get('zOrder', 1)); d.z = 0 if z is None else z
        op = ctx.ev(sym.get('opacity', 1.0)); d.opacity = 0.0 if op is None else float(op)
        out.append(d)
        # label
        lab = sym.get('label')
        if lab is not None:
            labels_out.append((d, lab))
    return out

def draw_vector(d, canvas, F, U, casing_only=False):
    W, H = F.W, F.H
    ctx, sym, g = d.ctx, d.sym, d.geom
    is_poly = g.geom_type in ('Polygon', 'MultiPolygon')
    is_line = g.geom_type in ('LineString', 'MultiLineString')
    has_stroke_prop = not ('stroke' in sym and sym['stroke'] is None)
    sp = stroke_params(sym.get('stroke') or {}, ctx, U)
    stobj = sym.get('stroke') if isinstance(sym.get('stroke'), dict) else {}
    casing = stobj.get('casing')
    center = stobj.get('center', stobj.get('centerLine'))
    if casing_only:
        if casing is not None and (is_line or is_poly) and has_stroke_prop:
            cp = stroke_params(casing, ctx, U)
            geom = stroke_geometry(g, sp['width'], None, 0.0, grow=cp['width'])
            return ('casing', geom, cp)
        return None
    T = canvas if d.opacity >= 1.0 else Target(W, H)
    # fill
    if is_poly:
        fl = sym.get('fill') if 'fill' in sym else {}
        if fl is not None:
            fl = ctx.ev(fl) if not isinstance(fl, dict) else fl
            fc = parse_color(fl['color'], ctx) if 'color' in fl else (1.0, 1.0, 1.0)
            fo = num(ctx, fl.get('opacity', 1.0), 0.0)
            if 'hatch' in fl and fl['hatch'] is not None:
                h = fl['hatch']
                wd = U.px(h.get('width', 1.0), ctx)
                dist = U.px(h.get('distance', 10.0), ctx)
                ang = num(ctx, h.get('angle', 45.0), 0.0)
                if dist > 0:
                    T.paint(pattern_mask('hatch', g, W, H, dict(angle=ang, distance=dist, width=wd)), fc, fo)
            elif 'dotpattern' in fl and fl['dotpattern'] is not None:
                dd = fl['dotpattern'].get('distance', {})
                if isinstance(dd, list): hx, vy = U.px(dd[0], ctx), U.px(dd[1], ctx)
                else: hx, vy = U.px(dd.get('horizontal', 10), ctx), U.px(dd.get('vertical', 10), ctx)
                if hx > 0 and vy > 0:
                    T.paint(pattern_mask('dots', g, W, H, dict(h=hx, v=vy, r=DOT_RADIUS)), fc, fo)
            elif 'stipple' in fl and fl['stipple'] is not None:
                ratio = num(ctx, fl['stipple'].get('ratio', 0.5), 0.0)
                ratio = min(max(ratio, 0.0), 1.0)
                if ratio > 0:
                    s = math.sqrt(math.pi * DOT_RADIUS ** 2 / ratio)   # square grid, dot area / cell area = ratio
                    s = max(s, 2 * DOT_RADIUS)
                    T.paint(pattern_mask('dots', g, W, H, dict(h=s, v=s, r=DOT_RADIUS)), fc, fo)
            else:
                T.paint(geom_mask(g, W, H), fc, fo)
    # stroke
    if (is_poly or is_line) and has_stroke_prop and sp['width'] > 0:
        sg = stroke_geometry(g, sp['width'], sp['dash'], sp['offset'])
        if sg is not None: T.paint(geom_mask(sg, W, H), sp['color'], sp['opacity'])
        if center is not None:
            cp = stroke_params(center, ctx, U)
            cg = stroke_geometry(g, cp['width'])
            if cg is not None: T.paint(geom_mask(cg, W, H), cp['color'], cp['opacity'])
    # markers
    if 'marker' in sym:
        mk = sym['marker']
    else:
        mk = {}  # default Marker: single default Dot
    if mk is not None:
        mk = ctx.ev(mk) if not isinstance(mk, dict) else mk
        if mk is not None:
            for (ax, ay) in anchors_of(g):
                if ax < -200 or ay < -200 or ax > W + 200 or ay > H + 200: continue
                els = build_elements(mk if 'elements' in mk else {'elements': [{'type': 'Dot'}]}, ctx, U, (ax, ay), W, H)
                for el in els: paint_elem(T, el, W, H)
    if T is not canvas:
        T.composite_onto(canvas, d.opacity)

DOT_RADIUS = 1.0

# ---------------------------------------------------------------- labels
def label_candidates(d, lab, F, U):
    """yield (priority, key, bbox, elems, anchor, minspacing)"""
    ctx, g = d.ctx, d.geom
    W, H = F.W, F.H
    pl = lab.get('placement') or {}
    prio = num(ctx, pl.get('priority', 0), 0.0) if pl.get('priority') is not None else 0.0
    minsp = U.px(pl['minSpacing'], ctx) if pl.get('minSpacing') is not None else None
    maxsp = U.px(pl['maxSpacing'], ctx) if pl.get('maxSpacing') is not None else None
    anchors = []
    t = g.geom_type
    if t in ('Point', 'MultiPoint'):
        anchors = anchors_of(g)
    elif t in ('Polygon', 'MultiPolygon'):
        poly = g if t == 'Polygon' else max(g.geoms, key=lambda p: p.area)
        anchors = [(poly.centroid.x, poly.centroid.y)]
    else:
        vis = g.intersection(box(0, 0, W, H))
        pieces = [vis] if vis.geom_type == 'LineString' else [x for x in getattr(vis, 'geoms', []) if x.geom_type == 'LineString']
        if minsp:
            for pc in pieces:
                L = pc.length
                s = minsp
                if L < s: positions = [L / 2]
                else:
                    positions = []; p = s / 2
                    while p <= L: positions.append(p); p += s
                for p in positions:
                    q = pc.interpolate(p); anchors.append((q.x, q.y))
        elif pieces:
            pc = max(pieces, key=lambda x: x.length)
            q = pc.interpolate(pc.length / 2); anchors = [(q.x, q.y)]
    res = []
    for a in anchors:
        els = build_elements(lab, ctx, U, a, W, H)
        if not els: continue
        bb = (min(e.bbox[0] for e in els), min(e.bbox[1] for e in els), max(e.bbox[2] for e in els), max(e.bbox[3] for e in els))
        key = '|'.join(e.text for e in els if e.kind == 'text')
        res.append((prio, key, bb, els, a, minsp))
    return res

def boxes_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

def place_labels(labels, canvas, F, U):
    cands = []
    seq = 0
    for d, lab in labels:
        for c in label_candidates(d, lab, F, U):
            cands.append((-c[0], seq, c)); seq += 1
    cands.sort(key=lambda t: (t[0], t[1]))   # higher priority value first; ties in drawing order
    placed = []
    for _, _, (prio, key, bb, els, anchor, minsp) in cands:
        if bb[2] < 0 or bb[0] > F.W or bb[3] < 0 or bb[1] > F.H: continue
        if any(boxes_overlap(bb, p[0]) for p in placed): continue
        if minsp and any(p[1] == key and key and math.hypot(p[2][0] - anchor[0], p[2][1] - anchor[1]) < minsp for p in placed): continue
        placed.append((bb, key, anchor))
        for el in els: paint_elem(canvas, el, F.W, F.H, 1.0)   # labels ignore symbolizer opacity

# ---------------------------------------------------------------- coverage
def load_asc(path):
    with open(path) as f:
        hdr = {}
        for _ in range(6):
            k, v = f.readline().split(); hdr[k.lower()] = float(v)
        data = np.loadtxt(f)
    return hdr, data.reshape(int(hdr['nrows']), int(hdr['ncols']))

def interp_map(vals, entries, ncomp):
    """entries: sorted list of (value, comp tuple); linear interpolation, clamp outside"""
    xs = np.array([e[0] for e in entries])
    out = np.zeros(vals.shape + (ncomp,))
    for c in range(ncomp):
        ys = np.array([e[1][c] for e in entries])
        out[..., c] = np.interp(vals, xs, ys)
    return out

def parse_cmap(cm, ctx, opacity=False):
    es = []
    for ent in cm:
        v = float(ctx.ev(ent[0]))
        if opacity: es.append((v, (float(ctx.ev(ent[1])),)))
        else: es.append((v, parse_color(ent[1], ctx)))
    es.sort(key=lambda e: e[0])
    return es

def render_coverage(layer_id, layer_idx, case_dir, rules, view, F, U):
    hdr, Z = load_asc(os.path.join(case_dir, layer_id + '.elevation.asc')) if os.path.exists(os.path.join(case_dir, layer_id + '.elevation.asc')) else (None, None)
    return hdr, Z

def coverage_layer(layer_id, bands, rules, view, F, U):
    hdr = None; B = {}
    for name, path in bands.items():
        h, z = load_asc(path); hdr = h; B[name] = z
    nr, nc, cs = int(hdr['nrows']), int(hdr['ncols']), hdr['cellsize']
    ctx = Ctx(view, layer_id, 'coverage', {})
    sym = resolve_symbolizer(rules, ctx)
    ctxarr = Ctx(view, layer_id, 'coverage', B)
    vis = ctx.ev(sym.get('visibility', True))
    if vis is None or not vis: return None
    op = num(ctx, sym.get('opacity', 1.0), 0.0)
    # per-pixel cell lookup
    W, H = F.W, F.H
    xs = F.bbox[0] + (np.arange(W) + 0.5) / F.sx
    ys = F.bbox[3] - (np.arange(H) + 0.5) / F.sy
    col = np.floor((xs - hdr['xllcorner']) / cs).astype(int)
    row = np.floor((hdr['yllcorner'] + nr * cs - ys) / cs).astype(int)
    inside = ((row >= 0) & (row < nr))[:, None] & ((col >= 0) & (col < nc))[None, :]
    R = np.clip(row, 0, nr - 1)[:, None]; C = np.clip(col, 0, nc - 1)[None, :]
    nodata = hdr.get('nodata_value', -9999)
    cellprops = {k: v for k, v in B.items()}
    cx = Ctx(view, layer_id, 'coverage', cellprops)  # props are whole arrays -> vector evaluation
    rgb = None; alpha = np.ones((nr, nc))
    single = cx.ev(sym['singleChannel']) if sym.get('singleChannel') is not None else None
    valid = np.ones((nr, nc), bool)
    for k, v in B.items(): valid &= (v != nodata)
    if sym.get('colorChannels') is not None:
        cc = sym['colorChannels']
        if isinstance(cc, dict) and 'op' not in cc:
            rgb = np.stack([np.broadcast_to(np.asarray(cx.ev(cc.get(k, 0)), float), (nr, nc)) for k in 'rgb'], -1)
        elif isinstance(cc, list):
            rgb = np.stack([np.broadcast_to(np.asarray(cx.ev(x), float), (nr, nc)) for x in cc], -1)
        else:
            rgb = np.broadcast_to(np.array(parse_color(cc, ctx)), (nr, nc, 3)).copy()
        rgb = np.clip(rgb, 0, 1)
    elif single is not None:
        single = np.asarray(single, float)
        if sym.get('colorMap'):
            rgb = interp_map(single, parse_cmap(sym['colorMap'], ctx), 3)
        else:
            rgb = np.repeat(np.clip(single, 0, 1)[..., None], 3, -1)
    if sym.get('alphaChannel') is not None:
        alpha = alpha * np.clip(np.broadcast_to(np.asarray(cx.ev(sym['alphaChannel']), float), (nr, nc)), 0, 1)
    if sym.get('opacityMap') and single is not None:
        alpha = alpha * np.clip(interp_map(single, parse_cmap(sym['opacityMap'], ctx, True), 1)[..., 0], 0, 1)
    hs = sym.get('hillShading')
    if hs is not None and B:
        z = list(B.values())[0] if 'elevation' not in B else B['elevation']
        factor = num(ctx, hs.get('factor', 1.0), 1.0)
        sun = hs.get('sun', {})
        def ang(a, dflt):
            a = ctx.ev(a) if a is not None else dflt
            if isinstance(a, dict):
                if 'rad' in a: return float(a['rad'])
                return math.radians(float(a['deg']))
            return math.radians(float(a))
        az, el = ang(sun.get('azimuth'), 315.0), ang(sun.get('elevation'), 45.0)
        zp = np.pad(z, 1, mode='edge')
        dzdx = (zp[1:-1, 2:] - zp[1:-1, :-2]) / (2 * cs)          # towards east
        dzdy = (zp[:-2, 1:-1] - zp[2:, 1:-1]) / (2 * cs)          # towards north (rows go south)
        n = np.stack([-dzdx * factor, -dzdy * factor, np.ones_like(z)], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        s = np.array([math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)])
        shade = np.clip(n @ s, 0, 1)
        if hs.get('colorMap') or hs.get('opacityMap'):
            if hs.get('colorMap'): rgb = interp_map(shade, parse_cmap(hs['colorMap'], ctx), 3)
            if hs.get('opacityMap'): alpha = alpha * np.clip(interp_map(shade, parse_cmap(hs['opacityMap'], ctx, True), 1)[..., 0], 0, 1)
        else:
            if rgb is None: rgb = np.ones((nr, nc, 3))
            rgb = rgb * shade[..., None]
    if rgb is None: return None
    pr = rgb[R, C]; pa = (alpha * valid)[R, C] * inside
    return pr, pa * op, sym

# ---------------------------------------------------------------- main
def render_case(case_dir, view_path, out_path):
    global CASE_DIR
    CASE_DIR = case_dir
    style = json.load(open(os.path.join(case_dir, 'style.cs.json'), encoding='utf8'))
    rules = style['stylingRules']
    view = json.load(open(view_path))
    F = Frame(view); U = Units(view)
    W, H = F.W, F.H
    canvas = Target(W, H, white=True)
    items = []   # (z, layer_idx, seq, kind, payload)
    labels = []
    for li, lid in enumerate(view['layers']):
        gj = os.path.join(case_dir, lid + '.geojson')
        if os.path.exists(gj):
            feats = load_vector(gj)
            for d in make_vector_drawables(lid, li, feats, rules, view, F, U, labels):
                items.append((d.z, li, d.fi, 'vec', d))
        else:
            bands = {}
            for fn in os.listdir(case_dir):
                m = re.match(re.escape(lid) + r'\.(.+)\.asc$', fn)
                if m: bands[m.group(1)] = os.path.join(case_dir, fn)
            if bands:
                r = coverage_layer(lid, bands, rules, view, F, U)
                if r is not None:
                    pr, pa, sym = r
                    z = Ctx(view, lid, 'coverage').ev(sym.get('zOrder', 1))
                    items.append((z, li, 0, 'cov', (pr, pa)))
    items.sort(key=lambda t: (t[0], t[1], t[2]))
    # group by zOrder
    zs = sorted(set(t[0] for t in items))
    for z in zs:
        grp = [t for t in items if t[0] == z]
        # casing pass (beneath main strokes of all features with this zOrder)
        cas = {}
        order = []
        for t in grp:
            if t[3] == 'vec':
                r = draw_vector(t[4], canvas, F, U, casing_only=True)
                if r is not None and r[1] is not None:
                    _, geom, cp = r
                    d = t[4]
                    key = (cp['color'], cp['opacity'] * d.opacity)
                    if key not in cas: cas[key] = []; order.append(key)
                    cas[key].append(geom)
        for key in order:
            canvas.paint(geom_mask(unary_union(cas[key]), W, H), key[0], key[1])
        for t in grp:
            if t[3] == 'vec': draw_vector(t[4], canvas, F, U)
            else:
                pr, pa = t[4]
                canvas.paint((0, 0, pa), pr, 1.0)
    place_labels(labels, canvas, F, U)
    img = np.clip(canvas.rgb * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(img, 'RGB').save(out_path)

if __name__ == '__main__':
    cases_dir = os.path.join(ROOT, 'cases')
    only = sys.argv[1:]
    n = 0
    for c in sorted(os.listdir(cases_dir)):
        cd = os.path.join(cases_dir, c)
        if not os.path.exists(os.path.join(cd, 'style.cs.json')): continue
        if only and c not in only: continue
        for fn in sorted(os.listdir(cd)):
            m = re.match(r'view-(\d+)\.json$', fn)
            if m:
                out = os.path.join(ROOT, 'out', '%s-%s.png' % (c, m.group(1)))
                try:
                    render_case(cd, os.path.join(cd, fn), out); n += 1
                    print('ok', out)
                except Exception as ex:
                    import traceback; traceback.print_exc(); print('FAIL', c, fn, ex)
    print(n, 'rendered')
