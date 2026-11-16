"""Renderer for OGC Cartographic Symbology 2.0 Part 1 (draft), written from spec/ text only.
Usage: render.py <case-dir> [out-dir]
"""
import sys, os, json, math, copy, datetime, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape, LineString, Polygon, MultiPolygon, box, Point
from shapely import ops as sops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colors import NAMED

SS = 4  # supersampling factor
MITRE_LIMIT = 4.0
FONT_DIR = 'C:/Windows/Fonts/'
PT_MM = 25.4 / 72.0

# ---------------------------------------------------------------- expressions
class Ctx:
    def __init__(self, props, sysmap):
        self.props = props
        self.sys = sysmap


def to_date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        try:
            return datetime.date.fromisoformat(v[:10])
        except Exception:
            return None
    return None


def coerce_pair(a, b):
    if isinstance(a, (datetime.date,)) and isinstance(b, str):
        d = to_date(b)
        if d: return a, d
    if isinstance(b, (datetime.date,)) and isinstance(a, str):
        d = to_date(a)
        if d: return d, b
    return a, b


def ev(e, ctx):
    """Evaluate an expression (CartoSym-JSON / CQL2-JSON) to a python value; None = null."""
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, list):
        return [ev(x, ctx) for x in e]
    if isinstance(e, dict):
        if 'property' in e:
            return ctx.props.get(e['property'])
        if 'sysId' in e:
            return ctx.sys.get(e['sysId'])
        if 'date' in e and len(e) == 1:
            return to_date(e['date'])
        if 'timestamp' in e and len(e) == 1:
            return datetime.datetime.fromisoformat(e['timestamp'].replace('Z', ''))
        if 'condition' in e:
            c = ev(e['condition'], ctx)
            return ev(e['thenExp'], ctx) if c is True else ev(e['elseExp'], ctx)
        if 'op' in e:
            return ev_op(e['op'], e['args'], ctx)
    return e


def ev_op(op, args, ctx):
    if op == 'and':
        vals = [ev(a, ctx) for a in args]
        if any(v is False for v in vals): return False
        if any(v is None for v in vals): return None
        return True
    if op == 'or':
        vals = [ev(a, ctx) for a in args]
        if any(v is True for v in vals): return True
        if any(v is None for v in vals): return None
        return False
    if op == 'not':
        v = ev(args[0], ctx)
        return None if v is None else (not v)
    vals = [ev(a, ctx) for a in args]
    if op == 'isNull':
        return vals[0] is None
    if op == 'in':
        if vals[0] is None: return None
        return vals[0] in vals[1]
    if op == 'between':
        if None in vals: return None
        return vals[1] <= vals[0] <= vals[2]
    if any(v is None for v in vals):
        return None
    if op in ('=', '<>', '<', '>', '<=', '>='):
        a, b = coerce_pair(vals[0], vals[1])
        try:
            return {'=': a == b, '<>': a != b, '<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op]
        except TypeError:
            return None
    a = vals[0]
    b = vals[1] if len(vals) > 1 else None
    if op == '+': return a + b
    if op == '-': return a - b if b is not None else -a
    if op == '*': return a * b
    if op == '/': return a / b if b != 0 else None
    if op == 'div': return int(a // b)
    if op == '%': return a % b
    if op == '^': return a ** b
    raise ValueError('unsupported op ' + op)


# ---------------------------------------------------------------- value resolvers
def num(v, default=0.0):
    """Resolve to a real number; null -> 0 (table-parameter-values-null)."""
    if v is None: return 0.0
    if isinstance(v, bool): return 1.0 if v else 0.0
    if isinstance(v, (int, float)): return float(v)
    try: return float(v)
    except Exception: return 0.0


def to_color(v):
    """-> (r,g,b) 0..1.  null -> black."""
    if v is None: return (0.0, 0.0, 0.0)
    if isinstance(v, str):
        s = v.strip()
        if s.startswith('#'):
            h = s[1:]
            if len(h) == 3: h = ''.join(c * 2 for c in h)
            return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        k = s.lower()
        if k in NAMED:
            h = NAMED[k]
            return ((h >> 16) & 255) / 255.0, ((h >> 8) & 255) / 255.0, (h & 255) / 255.0
        raise ValueError('unknown colour ' + v)
    if isinstance(v, (list, tuple)):
        return tuple(num(x) / 255.0 for x in v[:3])
    if isinstance(v, dict):
        return (num(v.get('r', 0)) / 255.0, num(v.get('g', 0)) / 255.0, num(v.get('b', 0)) / 255.0)
    return (0.0, 0.0, 0.0)


class View:
    def __init__(self, v):
        self.v = v
        self.w, self.h = v['width'], v['height']
        self.bbox = v['bbox']
        self.px_mm = v.get('pixelSize_mm', 0.28)
        self.sd = v['scaleDenominator']
        self.m_per_px = self.sd * self.px_mm / 1000.0
        self.res_x = (self.bbox[2] - self.bbox[0]) / self.w
        self.res_y = (self.bbox[3] - self.bbox[1]) / self.h

    def unit_px(self, val, unit, font_px=None):
        if unit in (None, 'px'): return val
        if unit == 'mm': return val / self.px_mm
        if unit == 'cm': return val * 10 / self.px_mm
        if unit == 'in': return val * 25.4 / self.px_mm
        if unit == 'pt': return val * PT_MM / self.px_mm
        if unit == 'm': return val / self.m_per_px
        if unit == 'ft': return val * 0.3048 / self.m_per_px
        if unit == 'em': return val * (font_px or 10 * PT_MM / self.px_mm)
        if unit == 'pc': return val / 100.0  # context dependent; handled by caller
        raise ValueError(unit)


def length_px(v, ctx, view, default_unit='px'):
    """Resolve unit value {px:..}/{mm:..}/number/expression -> pixels (output)."""
    if isinstance(v, dict) and len(v) == 1 and next(iter(v)) in ('px', 'mm', 'cm', 'in', 'pt', 'em', 'm', 'ft', 'pc'):
        u = next(iter(v))
        return view.unit_px(num(ev(v[u], ctx)), u)
    return view.unit_px(num(ev(v, ctx)), default_unit)


# ---------------------------------------------------------------- style cascade
OBJ_PROPS = None


def merge_obj(base, upd):
    out = copy.deepcopy(base) if isinstance(base, dict) else {}
    for k, v in upd.items():
        if k == 'alter': continue
        if isinstance(v, dict) and v.get('alter') is True:
            out[k] = merge_obj(out.get(k), v)
        elif isinstance(v, dict) and 'index' in v and 'value' in v and not isinstance(out.get(k), dict) and (k in ('elements', 'dashPattern') or isinstance(out.get(k), list)):
            arr = list(out.get(k) or [])
            i = v['index']
            while len(arr) <= i: arr.append(None)
            arr[i] = v['value']
            out[k] = arr
        else:
            out[k] = copy.deepcopy(v)
    return out


def apply_sym(state, sym):
    for k, v in sym.items():
        if k == '$comment': continue
        if isinstance(v, dict) and v.get('alter') is True:
            state[k] = merge_obj(state.get(k), v)
        elif isinstance(v, dict) and 'index' in v and 'value' in v and k in ('dashPattern',):
            state[k] = merge_obj({k: state.get(k)}, {k: v})[k]
        else:
            state[k] = copy.deepcopy(v)


def cascade(rules, ctx, state, flags):
    for r in rules:
        sel = r.get('selector')
        ok = True if sel is None else (ev(sel, ctx) is True)
        if not ok: continue
        flags['selected'] = True
        if 'symbolizer' in r:
            apply_sym(state, r['symbolizer'])
        if 'nestedRules' in r:
            cascade(r['nestedRules'], ctx, state, flags)


# ---------------------------------------------------------------- surfaces
class Surface:
    """Premultiplied RGBA float surface at supersampled resolution, with absolute origin."""
    def __init__(self, x0, y0, w, h, white=False):
        self.x0, self.y0, self.w, self.h = x0, y0, w, h
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)
        if white:
            self.rgb[:] = 1.0
            self.a[:] = 1.0

    def paint(self, mx, my, mask, color, alpha):
        """mask: uint8/float array (0..255 or 0..1 float) placed with top-left at absolute (mx,my)."""
        h, w = mask.shape
        x0 = max(mx, self.x0); y0 = max(my, self.y0)
        x1 = min(mx + w, self.x0 + self.w); y1 = min(my + h, self.y0 + self.h)
        if x1 <= x0 or y1 <= y0: return
        m = mask[y0 - my:y1 - my, x0 - mx:x1 - mx]
        if m.dtype == np.uint8:
            m = m.astype(np.float32) / 255.0
        a = m * alpha
        if np.isscalar(color) or len(np.shape(color)) == 1:
            col = np.asarray(color, np.float32)[None, None, :]
        else:
            col = color[y0 - my:y1 - my, x0 - mx:x1 - mx]
        sy0, sx0 = y0 - self.y0, x0 - self.x0
        sy1, sx1 = sy0 + (y1 - y0), sx0 + (x1 - x0)
        d_rgb = self.rgb[sy0:sy1, sx0:sx1]
        d_a = self.a[sy0:sy1, sx0:sx1]
        self.rgb[sy0:sy1, sx0:sx1] = col * a[..., None] + d_rgb * (1 - a[..., None])
        self.a[sy0:sy1, sx0:sx1] = a + d_a * (1 - a)

    def composite(self, other, opacity):
        h, w = other.a.shape
        x0 = max(other.x0, self.x0); y0 = max(other.y0, self.y0)
        x1 = min(other.x0 + w, self.x0 + self.w); y1 = min(other.y0 + h, self.y0 + self.h)
        if x1 <= x0 or y1 <= y0: return
        o_rgb = other.rgb[y0 - other.y0:y1 - other.y0, x0 - other.x0:x1 - other.x0] * opacity
        o_a = other.a[y0 - other.y0:y1 - other.y0, x0 - other.x0:x1 - other.x0] * opacity
        sy0, sx0 = y0 - self.y0, x0 - self.x0
        sy1, sx1 = sy0 + (y1 - y0), sx0 + (x1 - x0)
        self.rgb[sy0:sy1, sx0:sx1] = o_rgb + self.rgb[sy0:sy1, sx0:sx1] * (1 - o_a[..., None])
        self.a[sy0:sy1, sx0:sx1] = o_a + self.a[sy0:sy1, sx0:sx1] * (1 - o_a)


def geom_mask(geom, clipbox):
    """Rasterise a shapely (Multi)Polygon (coords already in SS pixel space) -> (x0,y0,uint8 mask) or None."""
    if geom is None or geom.is_empty: return None
    g = geom.intersection(clipbox)
    if g.is_empty: return None
    polys = []
    if g.geom_type == 'Polygon': polys = [g]
    elif g.geom_type in ('MultiPolygon', 'GeometryCollection'):
        polys = [p for p in g.geoms if p.geom_type == 'Polygon']
        for p in g.geoms:
            if p.geom_type == 'MultiPolygon': polys += list(p.geoms)
    if not polys: return None
    minx, miny, maxx, maxy = g.bounds
    x0 = int(math.floor(minx)) - 1; y0 = int(math.floor(miny)) - 1
    x1 = int(math.ceil(maxx)) + 1; y1 = int(math.ceil(maxy)) + 1
    img = Image.new('L', (x1 - x0, y1 - y0), 0)
    d = ImageDraw.Draw(img)
    for p in polys:
        d.polygon([(x - x0, y - y0) for x, y in p.exterior.coords], fill=255)
        for r in p.interiors:
            d.polygon([(x - x0, y - y0) for x, y in r.coords], fill=0)
    return x0, y0, np.asarray(img)


# ---------------------------------------------------------------- fonts / text
_font_cache = {}


def get_font(face, size_px, bold, italic):
    key = (face, round(size_px, 2), bold, italic)
    if key in _font_cache: return _font_cache[key]
    fam = (face or 'Arial').lower()
    if 'times' in fam:
        names = {(0, 0): 'times.ttf', (1, 0): 'timesbd.ttf', (0, 1): 'timesi.ttf', (1, 1): 'timesbi.ttf'}
    else:
        names = {(0, 0): 'arial.ttf', (1, 0): 'arialbd.ttf', (0, 1): 'ariali.ttf', (1, 1): 'arialbi.ttf'}
    f = ImageFont.truetype(FONT_DIR + names[(int(bool(bold)), int(bool(italic)))], max(1, int(round(size_px))))
    _font_cache[key] = f
    return f


def fmt_text(v):
    if v is None: return ''
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, float) and v == int(v): return str(int(v))
    return str(v)


# ---------------------------------------------------------------- data loading
class Layer:
    def __init__(self, ident, kind):
        self.id, self.kind = ident, kind
        self.features = []  # (props, geom)
        self.grid = None


def load_layer(case, ident):
    gj = os.path.join(case, ident + '.geojson')
    if os.path.exists(gj):
        d = json.load(open(gj, encoding='utf-8'))
        L = Layer(ident, 'vector')
        for f in d['features']:
            L.features.append((f.get('properties') or {}, shape(f['geometry'])))
        return L
    ascs = sorted(glob.glob(os.path.join(case, ident + '.*.asc')))
    if ascs:
        L = Layer(ident, 'coverage')
        L.bands = {}
        for a in ascs:
            band = os.path.basename(a)[len(ident) + 1:-4]
            hdr = {}
            with open(a) as fh:
                for _ in range(6):
                    k, v = fh.readline().split()
                    hdr[k.lower()] = float(v)
                data = np.loadtxt(fh, dtype=np.float64)
            data = data.reshape(int(hdr['nrows']), int(hdr['ncols']))
            data[data == hdr.get('nodata_value', -9999)] = np.nan
            L.bands[band] = data
            L.hdr = hdr
        return L
    raise FileNotFoundError(ident)


# ---------------------------------------------------------------- drawing helpers
class Renderer:
    def __init__(self, case, style, view):
        self.case, self.style, self.view = case, style, view
        self.W, self.H = view.w * SS, view.h * SS
        self.canvas = Surface(0, 0, self.W, self.H, white=True)
        self.clipbox = box(0, 0, self.W, self.H)
        self.labels = []  # deferred label items
        vz = view.v.get('visualization', {})
        self.sysbase = self.make_sys(vz)

    def make_sys(self, vz):
        s = {'viz.sd': self.view.sd, 'viz.scaleDenominator': self.view.sd}
        d = to_date(vz.get('date'))
        s['viz.date'] = d
        s['viz.dateTime.date'] = d
        s['viz.pass'] = 1
        if d:
            s['viz.date.year'], s['viz.date.month'], s['viz.date.day'] = d.year, d.month, d.day
        ti = vz.get('timeInterval')
        if ti:
            for k in ('start', 'end'):
                dd = to_date(ti[k])
                s['viz.timeInterval.%s' % k] = dd
                s['viz.timeInterval.%s.date' % k] = dd
                if dd:
                    s['viz.timeInterval.%s.date.year' % k] = dd.year
                    s['viz.timeInterval.%s.date.month' % k] = dd.month
                    s['viz.timeInterval.%s.date.day' % k] = dd.day
        return s

    # coordinates: ground -> SS pixel
    def tx(self, x, y):
        b = self.view.bbox
        return ((x - b[0]) / self.view.res_x * SS, (b[3] - y) / self.view.res_y * SS)

    def tgeom(self, g):
        return sops.transform(lambda x, y, z=None: ((np.asarray(x) - self.view.bbox[0]) / self.view.res_x * SS,
                                                    (self.view.bbox[3] - np.asarray(y)) / self.view.res_y * SS), g)

    # ------------------------------------------------------------ resolution
    def resolve(self, layer, props, ftype):
        sysm = dict(self.sysbase)
        sysm['dataLayer.id'] = layer.id
        sysm['dataLayer.identifier'] = layer.id
        sysm['dataLayer.type'] = layer.kind
        sysm['dataLayer'] = layer.id
        ctx = Ctx(props, sysm)
        state, flags = {}, {'selected': False}
        cascade(self.style['stylingRules'], ctx, state, flags)
        return ctx, state, flags

    # ------------------------------------------------------------ main loop
    def run(self):
        items = []
        seq = 0
        for lid in self.view.v['layers']:
            L = load_layer(self.case, lid)
            if L.kind == 'vector':
                bb = box(*self.view.bbox)
                margin = 400 * self.view.res_x
                bbm = box(self.view.bbox[0] - margin, self.view.bbox[1] - margin, self.view.bbox[2] + margin, self.view.bbox[3] + margin)
                for props, geom in L.features:
                    if not geom.intersects(bbm): continue
                    ctx, st, fl = self.resolve(L, props, geom.geom_type)
                    z = num(ev(st.get('zOrder', 1), ctx), 1.0) if 'zOrder' in st else 1.0
                    items.append((z, seq, 'v', L, props, geom, ctx, st, fl)); seq += 1
            else:
                ctx, st, fl = self.resolve(L, {}, 'cell')
                z = num(ev(st.get('zOrder', 1), ctx), 1.0) if 'zOrder' in st else 1.0
                items.append((z, seq, 'c', L, None, None, ctx, st, fl)); seq += 1
        items.sort(key=lambda t: (t[0], t[1]))
        i = 0
        while i < len(items):
            j = i
            while j < len(items) and items[j][0] == items[i][0]: j += 1
            self.draw_group(items[i:j])
            i = j
        self.draw_labels()
        return self.finish()

    def draw_group(self, grp):
        vis = []
        for it in grp:
            z, seq, kind, L, props, geom, ctx, st, fl = it
            v = ev(st['visibility'], ctx) if 'visibility' in st else True
            if v is None: v = False
            if v is False: continue
            vis.append(it)
        # phase A: casings of all features
        for it in vis:
            if it[2] != 'v': continue
            self.draw_casing(it)
        # phase B: each item
        for it in vis:
            if it[2] == 'v': self.draw_feature(it)
            else: self.draw_coverage(it)
        # phase C: centre lines
        for it in vis:
            if it[2] != 'v': continue
            self.draw_center(it)

    # ------------------------------------------------------------ stroke handling
    def stroke_params(self, st, ctx, key='stroke'):
        s = st.get(key)
        if s is None and key in st: return None
        if key not in st: s = {}
        if not isinstance(s, dict): return None
        w = length_px(s['width'], ctx, self.view) if 'width' in s else 1.0
        col = to_color(ev(s['color'], ctx)) if 'color' in s else (0.0, 0.0, 0.0)
        op = num(ev(s['opacity'], ctx)) if 'opacity' in s else 1.0
        return {'w': w, 'color': col, 'opacity': op, 'raw': s}

    def lines_of(self, geom):
        """Return list of coordinate arrays (in SS px) to stroke: lines and polygon rings."""
        out = []
        g = geom
        parts = list(g.geoms) if hasattr(g, 'geoms') else [g]
        for p in parts:
            if p.geom_type == 'LineString': out.append(np.array(p.coords))
            elif p.geom_type == 'Polygon':
                out.append(np.array(p.exterior.coords))
                for r in p.interiors: out.append(np.array(r.coords))
            elif p.geom_type == 'MultiLineString':
                for l in p.geoms: out.append(np.array(l.coords))
        return out

    def dash_lines(self, coords, pattern, offset):
        """pattern, offset in SS px. Returns list of LineStrings (dashes)."""
        ls = LineString(coords)
        L = ls.length
        P = sum(pattern)
        if P <= 0: return [ls]
        pat = list(pattern)
        if len(pat) % 2 == 1: pat = pat * 2
        P = sum(pat)
        out = []
        ph = offset % P
        idx = 0
        acc = 0.0
        while idx < len(pat) and acc + pat[idx] <= ph:
            acc += pat[idx]; idx += 1
        rem = pat[idx] - (ph - acc)  # remaining length of current element
        t = 0.0
        on = (idx % 2 == 0)
        while t < L:
            seg = min(rem, L - t)
            if on and seg > 0:
                out.append(sops.substring(ls, t, t + seg))
            t += seg
            idx = (idx + 1) % len(pat)
            rem = pat[idx]
            on = (idx % 2 == 0)
            if rem <= 0 and not on:
                pass
        return out

    def stroke_geoms(self, geom_ss, sp, st, ctx, width_px):
        """Polygon geometry (SS px) of the stroke of geom with width width_px (output px)."""
        wss = width_px * SS
        if wss <= 0: return None
        pat = None
        raw = sp['raw']
        if 'dashPattern' in raw and raw['dashPattern']:
            dp = raw['dashPattern']
            if isinstance(dp, list):
                pat = [length_px(x, ctx, self.view) * SS for x in dp]
        off = length_px(raw['dashOffset'], ctx, self.view) * SS if 'dashOffset' in raw else 0.0
        polys = []
        for coords in self.lines_of(geom_ss):
            if len(coords) < 2: continue
            if pat and sum(pat) > 0:
                pieces = self.dash_lines(coords, pat, off)
            else:
                pieces = [LineString(coords)]
            for pc in pieces:
                # clip roughly to view to limit work
                b = pc.bounds
                if b[2] < -wss or b[0] > self.W + wss or b[3] < -wss or b[1] > self.H + wss: continue
                polys.append(pc.buffer(wss / 2.0, cap_style='flat', join_style='mitre', mitre_limit=MITRE_LIMIT))
        if not polys: return None
        return sops.unary_union(polys)

    def paint_geom(self, surf, g, color, alpha):
        m = geom_mask(g, self.clipbox)
        if m: surf.paint(m[0], m[1], m[2], color, alpha)

    def draw_casing(self, it):
        z, seq, kind, L, props, geom, ctx, st, fl = it
        if geom.geom_type in ('Point', 'MultiPoint'): return
        sp = self.stroke_params(st, ctx)
        if not sp or 'casing' not in sp['raw']: return
        cs = sp['raw']['casing']
        if not isinstance(cs, dict): return
        cw = length_px(cs['width'], ctx, self.view) if 'width' in cs else 1.0
        ccol = to_color(ev(cs['color'], ctx)) if 'color' in cs else (0, 0, 0)
        cop = num(ev(cs['opacity'], ctx)) if 'opacity' in cs else 1.0
        opacity = num(ev(st['opacity'], ctx)) if 'opacity' in st else 1.0
        total = sp['w'] + 2 * cw
        g = self.tgeom(geom)
        sp2 = dict(sp); sp2['raw'] = {k: v for k, v in sp['raw'].items() if k not in ('dashPattern', 'dashOffset')}
        poly = self.stroke_geoms(g, sp2, st, ctx, total)
        if poly is not None: self.paint_geom(self.canvas, poly, ccol, cop * opacity)

    def draw_center(self, it):
        z, seq, kind, L, props, geom, ctx, st, fl = it
        if geom.geom_type in ('Point', 'MultiPoint'): return
        sp = self.stroke_params(st, ctx)
        if not sp or 'center' not in sp['raw']: return
        cs = sp['raw']['center']
        if not isinstance(cs, dict): return
        cw = length_px(cs['width'], ctx, self.view) if 'width' in cs else 1.0
        ccol = to_color(ev(cs['color'], ctx)) if 'color' in cs else (0, 0, 0)
        cop = num(ev(cs['opacity'], ctx)) if 'opacity' in cs else 1.0
        opacity = num(ev(st['opacity'], ctx)) if 'opacity' in st else 1.0
        g = self.tgeom(geom)
        sp2 = dict(sp); sp2['raw'] = {k: v for k, v in sp['raw'].items() if k not in ('dashPattern', 'dashOffset')}
        poly = self.stroke_geoms(g, sp2, st, ctx, cw)
        if poly is not None: self.paint_geom(self.canvas, poly, ccol, cop * opacity)

    # ------------------------------------------------------------ vector feature
    def draw_feature(self, it):
        z, seq, kind, L, props, geom, ctx, st, fl = it
        opacity = num(ev(st['opacity'], ctx)) if 'opacity' in st else 1.0
        g = self.tgeom(geom)
        if opacity < 1.0:
            b = g.bounds
            pad = 200 * SS
            x0 = int(max(0, math.floor(b[0]) - pad)); y0 = int(max(0, math.floor(b[1]) - pad))
            x1 = int(min(self.W, math.ceil(b[2]) + pad)); y1 = int(min(self.H, math.ceil(b[3]) + pad))
            if x1 <= x0 or y1 <= y0: surf = None
            else: surf = Surface(x0, y0, x1 - x0, y1 - y0)
        else:
            surf = self.canvas
        if surf is not None:
            gt = geom.geom_type
            if gt in ('Polygon', 'MultiPolygon'):
                self.draw_fill(surf, g, st, ctx)
            if gt not in ('Point', 'MultiPoint'):
                sp = self.stroke_params(st, ctx)
                if sp and sp['w'] > 0:
                    poly = self.stroke_geoms(g, sp, st, ctx, sp['w'])
                    if poly is not None: self.paint_geom(surf, poly, sp['color'], sp['opacity'])
            # marker
            anchors = self.marker_anchors(g)
            mk = st['marker'] if 'marker' in st else {}
            elems = self.marker_elements(mk)
            for ax, ay in anchors:
                for el in elems:
                    self.draw_graphic(surf, el, ctx, ax, ay)
            if surf is not self.canvas:
                self.canvas.composite(surf, opacity)
        # label registration
        lab = st.get('label')
        if lab and isinstance(lab, dict) and lab.get('elements'):
            self.labels.append((L, props, geom, g, ctx, lab))

    def marker_elements(self, mk):
        if mk is None: return []
        if isinstance(mk, dict):
            if 'elements' in mk:
                return [e for e in (mk['elements'] or []) if e]
            if 'type' in mk:
                return [mk]
            return [{'type': 'Dot'}]  # default Dot
        return []

    def marker_anchors(self, g):
        pts = []
        parts = list(g.geoms) if hasattr(g, 'geoms') else [g]
        for p in parts:
            if p.geom_type == 'Point': pts.append((p.x, p.y))
            elif p.geom_type == 'LineString': pts += [(x, y) for x, y in p.coords]
            elif p.geom_type == 'Polygon':
                c = p.centroid; pts.append((c.x, c.y))
        return pts

    # ------------------------------------------------------------ fill
    def draw_fill(self, surf, g, st, ctx):
        f = st.get('fill', {})
        if f is None: return
        if not isinstance(f, dict): f = {}
        col = to_color(ev(f['color'], ctx)) if 'color' in f else (1.0, 1.0, 1.0)
        op = num(ev(f['opacity'], ctx)) if 'opacity' in f else 1.0
        m = geom_mask(g, self.clipbox)
        if not m: return
        mx, my, mask = m
        h, w = mask.shape
        pat = None
        if 'hatch' in f and isinstance(f['hatch'], dict):
            hh = f['hatch']
            wd = length_px(hh['width'], ctx, self.view) if 'width' in hh else 1.0
            ang = num(ev(hh['angle'], ctx)) if 'angle' in hh else 45.0
            ds = length_px(hh['distance'], ctx, self.view) if 'distance' in hh else 10.0
            th = math.radians(ang)
            nx, ny = -math.sin(th), math.cos(th)  # screen coords (y down), clockwise angle from +x
            X = (np.arange(w) + mx + 0.5) / SS
            Y = (np.arange(h) + my + 0.5) / SS
            s = X[None, :] * nx + Y[:, None] * ny
            r = np.mod(s + ds / 2, ds) - ds / 2  # signed distance to nearest line
            pat = (np.abs(r) <= wd / 2).astype(np.uint8) * 255
        elif 'dotpattern' in f and isinstance(f['dotpattern'], dict):
            dd = f['dotpattern'].get('distance', {})
            hd = length_px(dd['horizontal'], ctx, self.view) if 'horizontal' in dd else 10.0
            vd = length_px(dd['vertical'], ctx, self.view) if 'vertical' in dd else 10.0
            pat = self.dot_grid(mx, my, w, h, hd, vd, 2.0)
        elif 'stipple' in f and isinstance(f['stipple'], dict):
            ratio = num(ev(f['stipple'].get('ratio', 0.5), ctx))
            ratio = min(max(ratio, 1e-4), 1.0)
            dia = 2.0
            sp = math.sqrt(math.pi * (dia / 2) ** 2 / ratio)
            pat = self.dot_grid(mx, my, w, h, sp, sp, dia)
        if pat is not None:
            mask = (mask.astype(np.uint16) * pat.astype(np.uint16) // 255).astype(np.uint8)
        surf.paint(mx, my, mask, col, op)

    def dot_grid(self, mx, my, w, h, hd, vd, dia):
        img = Image.new('L', (w, h), 0)
        d = ImageDraw.Draw(img)
        r = dia / 2 * SS
        i0 = int(math.floor((mx / SS) / hd)) - 1
        i1 = int(math.ceil(((mx + w) / SS) / hd)) + 1
        j0 = int(math.floor((my / SS) / vd)) - 1
        j1 = int(math.ceil(((my + h) / SS) / vd)) + 1
        for j in range(j0, j1 + 1):
            cy = j * vd * SS - my
            for i in range(i0, i1 + 1):
                cx = i * hd * SS - mx
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        return np.asarray(img)

    # ------------------------------------------------------------ graphics
    def pos_offset(self, el, ctx):
        p = el.get('position')
        if p is None: return 0.0, 0.0
        if isinstance(p, dict):
            x = length_px(p.get('x', 0), ctx, self.view); y = length_px(p.get('y', 0), ctx, self.view)
        else:
            x = length_px(p[0], ctx, self.view); y = length_px(p[1], ctx, self.view)
        return x, y  # +y downward on screen (see notes)

    def draw_graphic(self, surf, el, ctx, ax, ay, collect=None):
        t = el.get('type', 'Dot')
        ox, oy = self.pos_offset(el, ctx)
        cx, cy = ax + ox * SS, ay + oy * SS
        gop = num(ev(el['opacity'], ctx)) if 'opacity' in el else 1.0
        if t == 'Dot':
            stroke = el.get('stroke') if isinstance(el.get('stroke'), dict) else {}
            if 'size' in el: size = length_px(el['size'], ctx, self.view)
            elif 'width' in stroke: size = length_px(stroke['width'], ctx, self.view)
            else: size = 10.0
            if 'color' in el: col = to_color(ev(el['color'], ctx))
            elif 'color' in stroke: col = to_color(ev(stroke['color'], ctx))
            else: col = (1.0, 1.0, 1.0)
            r = size / 2 * SS
            if r <= 0: return
            x0 = int(math.floor(cx - r)) - 1; y0 = int(math.floor(cy - r)) - 1
            n = int(math.ceil(2 * r)) + 3
            img = Image.new('L', (n, n), 0)
            ImageDraw.Draw(img).ellipse([cx - r - x0, cy - r - y0, cx + r - x0, cy + r - y0], fill=255)
            surf.paint(x0, y0, np.asarray(img), col, gop)
        elif t == 'Image':
            self.draw_image(surf, el, ctx, cx, cy, gop)
        elif t == 'Text':
            self.draw_text(surf, el, ctx, cx, cy, gop, collect)

    _img_cache = {}

    def draw_image(self, surf, el, ctx, cx, cy, gop):
        res = el['image']
        path = res.get('path')
        im = None
        if path:
            for base in (self.case, os.path.dirname(self.case)):
                pth = os.path.normpath(os.path.join(base, path))
                if os.path.exists(pth):
                    im = Image.open(pth).convert('RGBA'); break
            if im is None:
                pth = os.path.normpath(os.path.join(self.case, path))
                alt = os.path.join(self.case, 'icons', os.path.basename(path))
                if os.path.exists(alt): im = Image.open(alt).convert('RGBA')
        if im is None: return
        w, h = im.size
        hs = el.get('hotSpot')
        if hs is None: hx, hy = 0.5, 0.5
        else:
            hx, hy = [self.hot(v, ctx) for v in (hs if isinstance(hs, list) else [hs['x'], hs['y']])]
        arr = np.asarray(im).astype(np.float32) / 255.0
        tint = np.array(to_color(ev(el['tint'], ctx)) if 'tint' in el else (1, 1, 1), np.float32)
        btint = np.array(to_color(ev(el['blackTint'], ctx)) if 'blackTint' in el else (0, 0, 0), np.float32)
        rgb = arr[..., :3] * tint + (1 - arr[..., :3]) * btint
        a = arr[..., 3]
        # scale to SS
        big = Image.fromarray(np.dstack([(np.clip(rgb, 0, 1) * 255).astype(np.uint8), (a * 255).astype(np.uint8)]), 'RGBA').resize((w * SS, h * SS), Image.BICUBIC)
        b = np.asarray(big).astype(np.float32) / 255.0
        x0 = int(round(cx - hx * w * SS)); y0 = int(round(cy - hy * h * SS))
        surf.paint(x0, y0, b[..., 3], b[..., :3], gop)

    def hot(self, v, ctx):
        # returns fraction of image size
        if isinstance(v, dict) and len(v) == 1 and 'pc' in v: return num(ev(v['pc'], ctx)) / 100.0
        return num(ev(v, ctx))

    def text_box(self, el, ctx, cx, cy):
        txt = fmt_text(ev(el.get('text'), ctx))
        if not txt: return None
        f = el.get('font') or {}
        face = ev(f.get('face'), ctx) if 'face' in f else 'Arial'
        size_pt = num(ev(f['size'], ctx)) if 'size' in f else 10.0
        size_px = size_pt * PT_MM / self.view.px_mm  # output px
        bold = ev(f.get('bold'), ctx) is True
        italic = ev(f.get('italic'), ctx) is True
        font = get_font(face, size_px * SS, bold, italic)
        asc, desc = font.getmetrics()
        wid = font.getlength(txt)
        hgt = asc + desc
        al = el.get('alignment')
        hal, val = 'center', 'middle'
        if isinstance(al, list): hal, val = al[0], al[1]
        elif isinstance(al, dict):
            hal = al.get('hAlignment', al.get('horzAlignment', 'center')); val = al.get('vAlignment', al.get('vertAlignment', 'middle'))
        x = cx - {'left': 0, 'center': wid / 2, 'right': wid}[hal]
        y = cy - {'top': 0, 'middle': hgt / 2, 'bottom': hgt}[val]
        return txt, font, x, y, wid, hgt, f

    def draw_text(self, surf, el, ctx, cx, cy, gop, collect=None):
        tb = self.text_box(el, ctx, cx, cy)
        if tb is None: return
        txt, font, x, y, wid, hgt, f = tb
        ol = f.get('outline')
        osz = 0.0
        if isinstance(ol, dict):
            osz = (length_px(ol['size'], ctx, self.view) if 'size' in ol else 1.0) * SS
        pad = int(math.ceil(osz)) + 2
        n_w, n_h = int(math.ceil(wid)) + 2 * pad + 2, int(math.ceil(hgt)) + 2 * pad + 2
        x0 = int(math.floor(x)) - pad; y0 = int(math.floor(y)) - pad
        if isinstance(ol, dict) and osz > 0:
            img = Image.new('L', (n_w, n_h), 0)
            ImageDraw.Draw(img).text((x - x0, y - y0), txt, font=font, fill=255, anchor='la', stroke_width=int(round(osz)), stroke_fill=255)
            ocol = to_color(ev(ol['color'], ctx)) if 'color' in ol else (0, 0, 0)
            oop = num(ev(ol['opacity'], ctx)) if 'opacity' in ol else 1.0
            surf.paint(x0, y0, np.asarray(img), ocol, oop)
        img = Image.new('L', (n_w, n_h), 0)
        ImageDraw.Draw(img).text((x - x0, y - y0), txt, font=font, fill=255, anchor='la')
        col = to_color(ev(f['color'], ctx)) if 'color' in f else (0, 0, 0)
        fop = num(ev(f['opacity'], ctx)) if 'opacity' in f else 1.0
        surf.paint(x0, y0, np.asarray(img), col, fop * gop)

    # ------------------------------------------------------------ coverage
    def draw_coverage(self, it):
        z, seq, kind, L, props, geom, ctx0, st, fl = it
        v = self.view
        W, H = v.w, v.h
        hdr = L.hdr
        cs = hdr['cellsize']; xll, yll = hdr['xllcorner'], hdr['yllcorner']
        nr, nc = int(hdr['nrows']), int(hdr['ncols'])
        xs = v.bbox[0] + (np.arange(W) + 0.5) * v.res_x
        ys = v.bbox[3] - (np.arange(H) + 0.5) * v.res_y
        col_f = (xs - xll) / cs
        row_f = (yll + nr * cs - ys) / cs
        ci = np.floor(col_f).astype(int); ri = np.floor(row_f).astype(int)
        inx = (ci >= 0) & (ci < nc); iny = (ri >= 0) & (ri < nr)
        inside = iny[:, None] & inx[None, :]
        cic = np.clip(ci, 0, nc - 1); ric = np.clip(ri, 0, nr - 1)
        props = {b: arr[ric[:, None], cic[None, :]] for b, arr in L.bands.items()}
        ctx = Ctx(props, ctx0.sys)
        sing = st.get('singleChannel')
        sc = ev(sing, ctx) if sing is not None else None
        if sc is not None and not isinstance(sc, np.ndarray):
            sc = np.full((H, W), num(sc))
        valid = inside.copy()
        if sc is not None: valid &= ~np.isnan(sc)
        rgb = np.zeros((H, W, 3), np.float32)
        alpha = np.ones((H, W), np.float32)
        cm = st.get('colorMap')
        if sc is not None and cm:
            rgb = self.map_color(cm, sc, ctx)
        elif 'colorChannels' in st:
            cc = st['colorChannels']
            comps = cc if isinstance(cc, list) else [cc.get('r'), cc.get('g'), cc.get('b')]
            rgb = np.dstack([np.broadcast_to(np.asarray(ev(c, ctx), np.float32), (H, W)) for c in comps]).clip(0, 1)
        elif sc is not None:
            g = np.clip(sc, 0, 1).astype(np.float32); rgb = np.dstack([g, g, g])
        om = st.get('opacityMap')
        if sc is not None and om:
            xs_ = [num(ev(e[0], ctx)) for e in om]; ys_ = [num(ev(e[1], ctx)) for e in om]
            alpha = np.interp(np.nan_to_num(sc), xs_, ys_).astype(np.float32)
        if 'alphaChannel' in st:
            alpha = alpha * np.clip(np.asarray(ev(st['alphaChannel'], ctx), np.float32), 0, 1)
        hs = st.get('hillShading')
        if hs and isinstance(hs, dict) and sc is not None:
            shade = self.hillshade(L, hs, ctx)
            if hs.get('colorMap'):
                rgb = self.map_color(hs['colorMap'], shade, ctx)
            else:
                rgb = rgb * shade[..., None]
            if hs.get('opacityMap'):
                om2 = hs['opacityMap']
                alpha = alpha * np.interp(shade, [num(e[0]) for e in om2], [num(e[1]) for e in om2]).astype(np.float32)
        opacity = num(ev(st['opacity'], ctx)) if 'opacity' in st else 1.0
        alpha = np.where(valid, alpha * opacity, 0).astype(np.float32)
        rgbs = np.repeat(np.repeat(rgb.astype(np.float32), SS, 0), SS, 1)
        als = np.repeat(np.repeat(alpha, SS, 0), SS, 1)
        self.canvas.paint(0, 0, als, rgbs, 1.0)

    def map_color(self, cm, vals, ctx):
        xs_ = [num(ev(e[0], ctx)) for e in cm]
        cols = np.array([to_color(ev(e[1], ctx)) for e in cm])
        v = np.nan_to_num(vals)
        order = np.argsort(xs_)
        xs_ = np.array(xs_)[order]; cols = cols[order]
        return np.dstack([np.interp(v, xs_, cols[:, k]) for k in range(3)]).astype(np.float32)

    def hillshade(self, L, hs, ctx):
        v = self.view
        hdr = L.hdr
        cs = hdr['cellsize']; xll, yll = hdr['xllcorner'], hdr['yllcorner']
        nr, nc = int(hdr['nrows']), int(hdr['ncols'])
        # elevation band: the band used as singleChannel input
        grid = next(iter(L.bands.values()))
        for b, arr in L.bands.items():
            if b == 'elevation': grid = arr
        xs = v.bbox[0] + (np.arange(v.w) + 0.5) * v.res_x
        ys = v.bbox[3] - (np.arange(v.h) + 0.5) * v.res_y
        u = np.clip((xs - xll) / cs - 0.5, 0, nc - 1)   # cell centres at integer idx
        w_ = np.clip((yll + nr * cs - ys) / cs - 0.5, 0, nr - 1)
        u0 = np.floor(u).astype(int); u1 = np.minimum(u0 + 1, nc - 1); fu = u - u0
        v0 = np.floor(w_).astype(int); v1 = np.minimum(v0 + 1, nr - 1); fv = w_ - v0
        g = np.nan_to_num(grid, nan=float(np.nanmean(grid)))
        z = (g[v0[:, None], u0[None, :]] * (1 - fu)[None, :] * (1 - fv)[:, None]
             + g[v0[:, None], u1[None, :]] * fu[None, :] * (1 - fv)[:, None]
             + g[v1[:, None], u0[None, :]] * (1 - fu)[None, :] * fv[:, None]
             + g[v1[:, None], u1[None, :]] * fu[None, :] * fv[:, None])
        dz_dcol = np.gradient(z, axis=1) / v.res_x
        dz_drow = np.gradient(z, axis=0) / v.res_y
        p = dz_dcol            # d z / d east
        q = -dz_drow           # d z / d north (rows go south)
        f = num(ev(hs['factor'], ctx)) if 'factor' in hs else 1.0
        sun = hs.get('sun') or {}
        az = math.radians(self.angle(sun.get('azimuth', 315.0), ctx))
        el = math.radians(self.angle(sun.get('elevation', 45.0), ctx))
        nx, ny, nz = -p * f, -q * f, np.ones_like(p)
        nrm = np.sqrt(nx * nx + ny * ny + nz * nz)
        lx, ly, lz = math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)
        shade = (nx * lx + ny * ly + nz * lz) / nrm
        return np.clip(shade, 0, 1).astype(np.float32)

    def angle(self, a, ctx):
        if isinstance(a, dict):
            if 'rad' in a: return math.degrees(num(ev(a['rad'], ctx)))
            if 'deg' in a: return num(ev(a['deg'], ctx))
        return num(ev(a, ctx))

    # ------------------------------------------------------------ labels
    def draw_labels(self):
        cand = []
        for (L, props, geom, g, ctx, lab) in self.labels:
            pl = lab.get('placement') or {}
            prio = num(ev(pl['priority'], ctx)) if 'priority' in pl else 0.0
            mn = length_px(pl['minSpacing'], ctx, self.view) if 'minSpacing' in pl else None
            mx = length_px(pl['maxSpacing'], ctx, self.view) if 'maxSpacing' in pl else None
            anchors = []
            parts = list(g.geoms) if hasattr(g, 'geoms') else [g]
            for p in parts:
                if p.geom_type == 'Point': anchors.append((p.x, p.y))
                elif p.geom_type == 'Polygon':
                    c = p.centroid; anchors.append((c.x, c.y))
                elif p.geom_type == 'LineString':
                    anchors += self.line_anchors(p, mn, mx)
            elems = lab['elements']
            for (ax, ay) in anchors:
                if not (0 <= ax <= self.W and 0 <= ay <= self.H): continue
                cand.append((prio, len(cand), ax, ay, ctx, elems, lab))
        cand.sort(key=lambda t: (-t[0], t[1]))
        placed = []
        for prio, _, ax, ay, ctx, elems, lab in cand:
            boxes = []
            for el in elems:
                bx = self.element_box(el, ctx, ax, ay)
                if bx: boxes.append(bx)
            if not boxes: continue
            if any(self.overlap(b, p) for b in boxes for p in placed): continue
            placed += boxes
            for el in elems:
                self.draw_graphic(self.canvas, el, ctx, ax, ay)

    def overlap(self, a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    def element_box(self, el, ctx, ax, ay):
        t = el.get('type', 'Dot')
        ox, oy = self.pos_offset(el, ctx)
        cx, cy = ax + ox * SS, ay + oy * SS
        if t == 'Text':
            tb = self.text_box(el, ctx, cx, cy)
            if tb is None: return None
            txt, font, x, y, wid, hgt, f = tb
            ol = f.get('outline')
            o = (length_px(ol['size'], ctx, self.view) if isinstance(ol, dict) and 'size' in ol else 0.0) * SS
            return (x - o, y - o, x + wid + o, y + hgt + o)
        if t == 'Dot':
            size = length_px(el['size'], ctx, self.view) if 'size' in el else 10.0
            r = size / 2 * SS
            return (cx - r, cy - r, cx + r, cy + r)
        if t == 'Image':
            return (cx - 12 * SS, cy - 12 * SS, cx + 12 * SS, cy + 12 * SS)
        return None

    def line_anchors(self, ls, mn, mx):
        view = self.clipbox
        clipped = ls.intersection(view)
        pieces = []
        if clipped.is_empty: return []
        if clipped.geom_type == 'LineString': pieces = [clipped]
        elif hasattr(clipped, 'geoms'):
            pieces = [p for p in clipped.geoms if p.geom_type == 'LineString']
        out = []
        for p in pieces:
            Lp = p.length
            if mn is None or mn <= 0:
                n = 1
            else:
                n = max(1, int(Lp // (mn * SS)))
                if mx and Lp / n > mx * SS:
                    n2 = int(math.ceil(Lp / (mx * SS)))
                    if Lp / n2 >= mn * SS: n = n2
            for i in range(n):
                pt = p.interpolate(Lp * (i + 0.5) / n)
                out.append((pt.x, pt.y))
        return out

    # ------------------------------------------------------------ output
    def finish(self):
        rgb = self.canvas.rgb  # opaque white backed
        h, w = self.view.h, self.view.w
        small = rgb.reshape(h, SS, w, SS, 3).mean(axis=(1, 3))
        return Image.fromarray((np.clip(small, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')


def main():
    case = os.path.abspath(sys.argv[1])
    outdir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out')
    os.makedirs(outdir, exist_ok=True)
    style = json.load(open(os.path.join(case, 'style.cs.json'), encoding='utf-8'))
    name = os.path.basename(case)
    for vf in sorted(glob.glob(os.path.join(case, 'view-*.json'))):
        n = os.path.basename(vf)[5:-5]
        view = View(json.load(open(vf, encoding='utf-8')))
        r = Renderer(case, style, view)
        img = r.run()
        img.save(os.path.join(outdir, '%s-%s.png' % (name, n)))
        print('wrote', name, n, img.size)


if __name__ == '__main__':
    main()
