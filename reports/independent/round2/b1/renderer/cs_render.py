"""Renderer for the closed test: reads a case's style.cs.json, data and view-1.json
and writes out/<case>-1.png.  Written from the text in spec/ only.

Run:  uv run --no-project --with numpy --with pillow --with pycairo python renderer/cs_render.py [case ...]
"""
import datetime
import glob
import json
import math
import os
import sys

import numpy as np
import cairo
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from cs_expr import EvalContext, evaluate, parse_date, to_text, is_array   # noqa: E402
from cs_style import resolve, default_instance, WHITE, BLACK                 # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..'))
CASES = os.path.join(ROOT, 'cases')
OUT = os.path.join(ROOT, 'out')

CAPABILITIES = {
    'vector': True, 'coverage': True, 'labels': True, 'hillshading': True, 'fontoutlines': True,
    'hatches': True, 'stipples': True, 'dotpatterns': True, 'dashes': True, 'casing': True,
    'parametervalues': True, 'functions': True, 'math': True, 'arrayrelations': True,
    'textmanipulation': True, 'arithmetic': True, 'textrelation': True, 'righthand': True,
    'conditional': True, 'variables': False,
}

LOG = []


def log(msg):
    LOG.append(msg)


# =========================================================================== view

class View:
    def __init__(self, d):
        self.bbox = d['bbox']
        self.width = int(d['width'])
        self.height = int(d['height'])
        self.sd = d.get('scaleDenominator')
        self.pixel_mm = d.get('pixelSize_mm', 0.28)
        self.layers = d['layers']
        self.background = d.get('background', 'white')
        viz = d.get('visualization', {})
        self.date = parse_date(viz['date']) if 'date' in viz else None
        ti = viz.get('timeInterval')
        self.interval = None
        if ti:
            self.interval = (parse_date(ti['start'][:10]), parse_date(ti['end'][:10]))
        minx, miny, maxx, maxy = self.bbox
        self.rx = (maxx - minx) / self.width     # ground metres per pixel
        self.ry = (maxy - miny) / self.height

    def to_px(self, x, y):
        return ((x - self.bbox[0]) / self.rx, (self.bbox[3] - y) / self.ry)

    def ground_per_px(self):
        return (self.rx + self.ry) / 2


# =========================================================================== units

def length_px(uv, view, em=None, pc_base=None, default_unit='px'):
    """Converts a uom-qualified value (value, unit) to map pixels (/req/vector/units)."""
    if uv is None:
        return 0.0
    v, u = uv
    if v is None:
        return 0.0
    if is_array(v):
        v = float(np.nanmean(v))
    v = float(v)
    if u is None:
        u = default_unit
    mm = view.pixel_mm
    if u == 'px':
        return v
    if u == 'mm':
        return v / mm
    if u == 'cm':
        return v * 10 / mm
    if u == 'inch':
        return v * 25.4 / mm
    if u == 'pt':
        return v * 25.4 / 72.0 / mm
    if u == 'm':
        return v / view.ground_per_px()
    if u == 'ft':
        return v * 0.3048 / view.ground_per_px()
    if u == 'em':
        return v * (em if em is not None else 16.0)
    if u == 'pc':
        return v / 100.0 * (pc_base if pc_base is not None else 0.0)
    return v


# =========================================================================== data

def load_layers(case_dir, view):
    layers = []
    for name in view.layers:
        gj = os.path.join(case_dir, name + '.geojson')
        if os.path.exists(gj):
            with open(gj, encoding='utf-8') as f:
                d = json.load(f)
            layers.append({'name': name, 'type': 'vector', 'features': d['features']})
            continue
        bands = {}
        geo = None
        for p in sorted(glob.glob(os.path.join(case_dir, name + '.*.asc'))):
            band = os.path.basename(p)[len(name) + 1:-4]
            arr, g = read_asc(p)
            bands[band] = arr
            geo = g
        if bands:
            layers.append({'name': name, 'type': 'coverage', 'bands': bands, 'geo': geo})
        else:
            log('layer %s: no data found' % name)
    return layers


def read_asc(path):
    hdr = {}
    with open(path) as f:
        lines = []
        for _ in range(6):
            pos = f.tell()
            line = f.readline()
            k, v = line.split()[:2]
            if k[0].isalpha():
                hdr[k.lower()] = float(v)
            else:
                f.seek(pos)
                break
        data = np.loadtxt(f)
    nd = hdr.get('nodata_value')
    data = data.astype(float)
    if nd is not None:
        data[data == nd] = np.nan
    cs = hdr['cellsize']
    if 'xllcorner' in hdr:
        xll = hdr['xllcorner']
        yll = hdr['yllcorner']
    else:
        xll = hdr['xllcenter'] - cs / 2
        yll = hdr['yllcenter'] - cs / 2
    nrows, ncols = data.shape
    return data, {'xll': xll, 'yll': yll, 'cs': cs, 'nrows': nrows, 'ncols': ncols,
                  'ytop': yll + nrows * cs}


def geom_dimension(g):
    if g is None:
        return None
    t = g['type']
    if t in ('Point', 'MultiPoint'):
        return 0
    if t in ('LineString', 'MultiLineString'):
        return 1
    if t in ('Polygon', 'MultiPolygon'):
        return 2
    if t == 'GeometryCollection':
        dims = {geom_dimension(x) for x in g['geometries']}
        return max(dims) if dims else None
    return None


def explode(g):
    """Simple parts: ('point', (x,y)) / ('line', [pts]) / ('polygon', [rings])."""
    if g is None:
        return []
    t = g['type']
    c = g.get('coordinates')
    if t == 'Point':
        return [('point', tuple(c[:2]))]
    if t == 'MultiPoint':
        return [('point', tuple(p[:2])) for p in c]
    if t == 'LineString':
        return [('line', [tuple(p[:2]) for p in c])]
    if t == 'MultiLineString':
        return [('line', [tuple(p[:2]) for p in l]) for l in c]
    if t == 'Polygon':
        return [('polygon', [[tuple(p[:2]) for p in r] for r in c])]
    if t == 'MultiPolygon':
        return [('polygon', [[tuple(p[:2]) for p in r] for r in poly]) for poly in c]
    if t == 'GeometryCollection':
        out = []
        for x in g['geometries']:
            out += explode(x)
        return out
    return []


def polygon_centroid(rings):
    """Area-weighted centroid of a polygon (exterior minus holes); the vertex mean
    for degenerate rings."""
    ax = ay = aa = 0.0
    for i, r in enumerate(rings):
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
            cr = x0 * y1 - x1 * y0
            a += cr
            cx += (x0 + x1) * cr
            cy += (y0 + y1) * cr
        a /= 2
        if abs(a) < 1e-12:
            continue
        cx /= (6 * a)
        cy /= (6 * a)
        w = abs(a) if i == 0 else -abs(a)
        ax += cx * w
        ay += cy * w
        aa += w
    if abs(aa) < 1e-12:
        pts = rings[0]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return (ax / aa, ay / aa)


# =========================================================================== system identifiers

def make_sysids(view, layer, feature=None):
    viz = {
        'scaleDenominator': view.sd, 'sd': view.sd,
        'date': view.date,
        'dateTime': datetime.datetime(view.date.year, view.date.month, view.date.day) if view.date else None,
        'timeOfDay': None,
        'pass': 0,
    }
    if view.interval:
        viz['timeInterval'] = {'start': {'date': view.interval[0]}, 'end': {'date': view.interval[1]}}
    dims = None
    if layer['type'] == 'vector':
        ds = {geom_dimension(f.get('geometry')) for f in layer['features']}
        dims = ds.pop() if len(ds) == 1 else None
    dl = {'identifier': layer['name'], 'id': layer['name'], 'type': layer['type'],
          'featuresGeometryDimension': dims}
    feat = {}
    if feature is not None:
        feat = {'identifier': feature.get('id'), 'id': feature.get('id'),
                'geometryDimension': geom_dimension(feature.get('geometry')), 'pass': 0}

    def lookup(name):
        parts = name.split('.')
        head = parts[0]
        if head in ('viz', 'visualization'):
            obj = viz
        elif head == 'dataLayer':
            obj = dl
        elif head == 'feature':
            obj = feat
        elif head == 'capabilities':
            if len(parts) == 2:
                return CAPABILITIES.get(parts[1], False)
            return False          # vendor capabilities: none
        else:
            return None
        for p in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(p)
            elif isinstance(obj, datetime.date):
                obj = {'year': obj.year, 'month': obj.month, 'day': obj.day}.get(p)
            else:
                return None
            if obj is None:
                return None
        if isinstance(obj, dict) and set(obj.keys()) == {'date'}:
            return obj['date']
        return obj
    return lookup


# =========================================================================== fonts / text

FONT_OPTS = cairo.FontOptions()
FONT_OPTS.set_hint_style(cairo.HINT_STYLE_NONE)
FONT_OPTS.set_hint_metrics(cairo.HINT_METRICS_OFF)
FONT_OPTS.set_antialias(cairo.ANTIALIAS_GRAY)


def resolve_font(chain, view):
    """chain: fonts from outermost (Symbolizer) to innermost (Text).  Each member is
    taken from the nearest place that sets it (/req/vector/font-inheritance)."""
    out = {'face': 'Arial', 'size': 16.0, 'bold': False, 'italic': False, 'color': BLACK,
           'opacity': 1.0, 'outline': None}
    for f in chain:
        if not f:
            continue
        for k in ('face', 'bold', 'italic', 'color', 'opacity', 'outline'):
            if f.get(k) is not None:
                out[k] = f[k]
        if f.get('size') is not None:
            out['size'] = length_px(f['size'], view, em=out['size'])
    return out


def font_em(chain, view):
    return resolve_font(chain, view)['size']


class TextLayout:
    def __init__(self, text, font):
        self.font = font
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
        c = cairo.Context(surf)
        set_font(c, font)
        sf = c.get_scaled_font()
        self.ascent, self.descent = c.font_extents()[0:2]
        self.glyphs = []          # (index, x_offset, advance)
        x = 0.0
        for ch in text:
            gl = sf.text_to_glyphs(0, 0, ch, False)
            adv = c.text_extents(ch).x_advance
            for g in gl:
                self.glyphs.append((g.index, x + g.x, adv))
            x += adv
        self.advance = c.text_extents(text).x_advance if text else 0.0
        if text:
            # use the whole-string glyph positions (kerning as cairo gives it)
            gl = sf.text_to_glyphs(0, 0, text, False)
            ext = []
            for i, g in enumerate(gl):
                nxt = gl[i + 1].x if i + 1 < len(gl) else self.advance
                ext.append((g.index, g.x, nxt - g.x))
            self.glyphs = ext


def set_font(c, font):
    c.select_font_face(font['face'] or 'Arial',
                       cairo.FONT_SLANT_ITALIC if font['italic'] else cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if font['bold'] else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(font['size'])
    c.set_font_options(FONT_OPTS)


def align_offsets(layout, halign, valign):
    dx = {'left': 0.0, 'center': -layout.advance / 2, 'right': -layout.advance}.get(halign, 0.0)
    a, d = layout.ascent, layout.descent
    base = {'top': a, 'bottom': -d, 'middle': (a - d) / 2}.get(valign, a)
    return dx, base


def draw_glyph_runs(c, runs, font, opacity):
    """runs: list of (glyph_index, origin_x, origin_y, angle).  Draws the outline of
    all glyphs first (beneath), then the glyphs (/req/font-outlines/outline)."""
    if not runs:
        return
    set_font(c, font)

    def build_path():
        c.new_path()
        for gi, ox, oy, ang in runs:
            c.save()
            c.translate(ox, oy)
            if ang:
                c.rotate(ang)
            c.glyph_path([cairo.Glyph(gi, 0, 0)])
            c.restore()
    ol = font.get('outline')
    if ol and ol.get('size', 0) and ol['size'] > 0 and ol.get('opacity', 1) > 0:
        c.push_group()
        build_path()
        r, g, b = [v / 255 for v in ol['color']]
        c.set_source_rgb(r, g, b)
        c.set_line_width(2 * ol['size'])
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.fill_preserve()
        c.stroke()
        c.pop_group_to_source()
        c.paint_with_alpha(max(0.0, min(1.0, ol.get('opacity', 1) * opacity)))
    build_path()
    r, g, b = [v / 255 for v in font['color']]
    c.set_source_rgba(r, g, b, max(0.0, min(1.0, font.get('opacity', 1) * opacity)))
    c.fill()


# =========================================================================== images

_IMG_CACHE = {}


def load_image(case_dir, res):
    path = res.get('path')
    if not path:
        log('image without a local path: %s' % res)
        return None
    full = os.path.normpath(os.path.join(case_dir, path))
    if full in _IMG_CACHE:
        return _IMG_CACHE[full]
    if not os.path.exists(full):
        log('image not found: %s' % full)
        _IMG_CACHE[full] = None
        return None
    if full.lower().endswith('.svg'):
        log('SVG images are not implemented: %s' % full)
        _IMG_CACHE[full] = None
        return None
    im = Image.open(full).convert('RGBA')
    arr = np.asarray(im).astype(float) / 255.0
    _IMG_CACHE[full] = arr
    return arr


def image_surface(arr, tint, black):
    """Recolors (/req/vector/image: tint x v + blackTint x (1 - v), per component, in
    sRGB) and returns a premultiplied cairo surface."""
    h, w = arr.shape[:2]
    rgb = arr[..., :3]
    t = np.array(tint, float) / 255
    k = np.array(black, float) / 255
    rgb = t * rgb + k * (1 - rgb)
    a = arr[..., 3:4]
    pre = np.clip(rgb * a, 0, 1)
    bgra = np.zeros((h, w, 4), np.uint8)
    bgra[..., 0] = np.round(pre[..., 2] * 255)
    bgra[..., 1] = np.round(pre[..., 1] * 255)
    bgra[..., 2] = np.round(pre[..., 0] * 255)
    bgra[..., 3] = np.round(a[..., 0] * 255)
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
    buf = np.zeros((h, stride), np.uint8)
    buf[:, :w * 4] = bgra.reshape(h, w * 4)
    surf = cairo.ImageSurface.create_for_data(bytearray(buf.tobytes()), cairo.FORMAT_ARGB32, w, h, stride)
    return surf


def image_geometry(el, arr, view, em):
    ih, iw = arr.shape[:2]
    size = el.get('size')
    w, h = float(iw), float(ih)
    if size:
        if size[0] == 'single' and size[1] is not None:
            w = h = length_px(size[1], view, em=em)
        elif size[0] == 'point' and size[1]:
            sx, sy = size[1].get('x'), size[1].get('y')
            if sx is not None and sy is not None:
                w, h = length_px(sx, view, em=em, pc_base=iw), length_px(sy, view, em=em, pc_base=ih)
            elif sx is not None:
                w = length_px(sx, view, em=em, pc_base=iw)
                h = w * ih / iw
            elif sy is not None:
                h = length_px(sy, view, em=em, pc_base=ih)
                w = h * iw / ih
    hs = el.get('hotSpot') or {'x': (50, 'pc'), 'y': (50, 'pc')}

    def hs_px(uv, scale, full):
        if uv is None:
            return full / 2
        v, u = uv
        if u is None:
            return float(v) * scale        # pixels of the image file, scaled with the image
        if u == 'pc':
            return float(v) / 100 * full
        return length_px(uv, view, em=em)
    hx = hs_px(hs.get('x'), w / iw, w)
    hy = hs_px(hs.get('y'), h / ih, h)
    return w, h, hx, hy


# =========================================================================== graphics (markers, labels)

def unit_point_px(p, view, em):
    if not p:
        return 0.0, 0.0
    return length_px(p.get('x'), view, em=em), length_px(p.get('y'), view, em=em)


def graphic_elements(mg, font_chain, view, case_dir, origin_offset=(0.0, 0.0)):
    """Flattens a MultiGraphic into drawable items in its own frame (x right, y down),
    relative to the position of the Graphic: list of dicts."""
    items = []
    chain = font_chain + [mg.get('font')]
    em_mg = font_em(chain, view)
    mx, my = unit_point_px(mg.get('position'), view, em_mg)
    ox, oy = origin_offset[0] + mx, origin_offset[1] + my
    mop = mg.get('opacity', 1)
    for el in mg.get('elements') or []:
        cls = el['_cls']
        if cls == 'MultiGraphic':
            sub = graphic_elements(el, chain, view, case_dir, (ox, oy))
            for s in sub:
                s['opacity'] *= mop
            items += sub
            continue
        if cls == 'Text':
            f = resolve_font(chain + [el.get('font')], view)
            px, py = unit_point_px(el.get('position'), view, f['size'])
            text = el.get('text') or ''
            if not text:
                continue
            items.append({'kind': 'text', 'x': ox + px, 'y': oy + py, 'font': f, 'text': text,
                          'align': el.get('alignment') or ('left', 'top'),
                          'opacity': mop * el.get('opacity', 1)})
        elif cls == 'Dot':
            px, py = unit_point_px(el.get('position'), view, em_mg)
            size = length_px(el.get('size'), view, em=em_mg)
            if size <= 0:
                continue
            items.append({'kind': 'dot', 'x': ox + px, 'y': oy + py, 'size': size,
                          'color': el.get('color') or WHITE, 'opacity': mop * el.get('opacity', 1)})
        elif cls == 'Image':
            arr = load_image(case_dir, el.get('image') or {})
            if arr is None:
                continue
            px, py = unit_point_px(el.get('position'), view, em_mg)
            w, h, hx, hy = image_geometry(el, arr, view, em_mg)
            items.append({'kind': 'image', 'x': ox + px, 'y': oy + py, 'arr': arr, 'w': w, 'h': h,
                          'hx': hx, 'hy': hy, 'tint': el.get('tint') or WHITE,
                          'black': el.get('blackTint') or BLACK, 'opacity': mop * el.get('opacity', 1)})
    return items


_SURF_CACHE = {}


def draw_items_at(c, items, x, y, opacity):
    for it in items:
        op = max(0.0, min(1.0, it['opacity'] * opacity))
        if op <= 0:
            continue
        if it['kind'] == 'dot':
            r, g, b = [v / 255 for v in it['color']]
            c.set_source_rgba(r, g, b, op)
            c.new_path()
            c.arc(x + it['x'], y + it['y'], it['size'] / 2, 0, 2 * math.pi)
            c.fill()
        elif it['kind'] == 'image':
            key = (id(it['arr']), tuple(it['tint']), tuple(it['black']))
            surf = _SURF_CACHE.get(key)
            if surf is None:
                surf = image_surface(it['arr'], it['tint'], it['black'])
                _SURF_CACHE[key] = surf
            ih, iw = it['arr'].shape[:2]
            c.save()
            c.translate(x + it['x'] - it['hx'], y + it['y'] - it['hy'])
            c.scale(it['w'] / iw, it['h'] / ih)
            c.set_source_surface(surf, 0, 0)
            c.get_source().set_filter(cairo.FILTER_BILINEAR)
            c.get_source().set_extend(cairo.EXTEND_NONE)
            c.rectangle(0, 0, iw, ih)
            c.clip()
            c.paint_with_alpha(op)
            c.restore()
        elif it['kind'] == 'text':
            lay = TextLayout(it['text'], it['font'])
            dx, base = align_offsets(lay, it['align'][0], it['align'][1])
            x0 = x + it['x'] + dx
            y0 = y + it['y'] + base
            runs = [(gi, x0 + gx, y0, 0.0) for gi, gx, adv in lay.glyphs]
            draw_glyph_runs(c, runs, it['font'], op)


def item_boxes(items, x, y):
    """Axis-aligned footprint boxes of graphic items placed at (x, y) (for labels)."""
    boxes = []
    for it in items:
        if it['kind'] == 'dot':
            r = it['size'] / 2
            boxes.append((x + it['x'] - r, y + it['y'] - r, x + it['x'] + r, y + it['y'] + r))
        elif it['kind'] == 'image':
            x0 = x + it['x'] - it['hx']
            y0 = y + it['y'] - it['hy']
            boxes.append((x0, y0, x0 + it['w'], y0 + it['h']))
        elif it['kind'] == 'text':
            lay = TextLayout(it['text'], it['font'])
            dx, base = align_offsets(lay, it['align'][0], it['align'][1])
            o = outline_size(it['font'])
            x0 = x + it['x'] + dx
            yb = y + it['y'] + base
            boxes.append((x0 - o, yb - lay.ascent - o, x0 + lay.advance + o, yb + lay.descent + o))
    return boxes


def outline_size(font):
    ol = font.get('outline')
    if ol and ol.get('size', 0) > 0 and ol.get('opacity', 1) > 0:
        return float(ol['size'])
    return 0.0


# =========================================================================== label collision mask

class Occupancy:
    M = 400

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.occ = np.zeros((h + 2 * self.M, w + 2 * self.M), bool)

    def raster(self, polys):
        im = Image.new('1', (self.w + 2 * self.M, self.h + 2 * self.M), 0)
        d = ImageDraw.Draw(im)
        for p in polys:
            d.polygon([(x + self.M, y + self.M) for x, y in p], fill=1)
        return np.asarray(im, bool)

    def free(self, mask):
        return not np.any(mask & self.occ)

    def add(self, mask):
        self.occ |= mask


def box_poly(b):
    x0, y0, x1, y1 = b
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# =========================================================================== line geometry for labels

class Polyline:
    def __init__(self, pts):
        cleaned = [pts[0]]
        for p in pts[1:]:
            if math.hypot(p[0] - cleaned[-1][0], p[1] - cleaned[-1][1]) > 1e-9:
                cleaned.append(p)
        self.pts = np.array(cleaned, float)
        seg = np.diff(self.pts, axis=0)
        self.seglen = np.hypot(seg[:, 0], seg[:, 1]) if len(seg) else np.zeros(0)
        self.cum = np.concatenate([[0.0], np.cumsum(self.seglen)])
        self.length = float(self.cum[-1])

    def point(self, s):
        s = min(max(s, 0.0), self.length)
        i = int(np.searchsorted(self.cum, s, side='right') - 1)
        i = min(max(i, 0), len(self.seglen) - 1)
        t = (s - self.cum[i]) / self.seglen[i] if self.seglen[i] > 0 else 0.0
        return self.pts[i] + t * (self.pts[i + 1] - self.pts[i])

    def reversed(self):
        return Polyline([tuple(p) for p in self.pts[::-1]])


def join_lines(lines):
    """Joins lines (lists of world points) that meet at their end points
    (/req/labels/line, third part)."""
    def key(p):
        return (round(p[0], 6), round(p[1], 6))
    chains = [list(l) for l in lines if len(l) >= 2]
    merged = True
    while merged:
        merged = False
        for i in range(len(chains)):
            a = chains[i]
            for j in range(len(chains)):
                if i == j:
                    continue
                b = chains[j]
                if key(a[-1]) == key(b[0]):
                    na = a + b[1:]
                elif key(a[-1]) == key(b[-1]):
                    na = a + b[::-1][1:]
                elif key(a[0]) == key(b[-1]):
                    na = b + a[1:]
                elif key(a[0]) == key(b[0]):
                    na = b[::-1] + a[1:]
                else:
                    continue
                chains[i] = na
                chains.pop(j)
                merged = True
                break
            if merged:
                break
    return chains


# =========================================================================== coverage

def interp_map(v, entries, n_out):
    """Piecewise linear interpolation of a colorMap / opacityMap (/req/coverage/color-map,
    /rec/coverage/map-interpolation), first/last entry outside the range."""
    entries = sorted([e for e in entries if e[0] is not None], key=lambda e: e[0])
    xs = np.array([e[0] for e in entries], float)
    out = []
    for k in range(n_out):
        ys = np.array([(e[1][k] if n_out > 1 else e[1]) for e in entries], float)
        out.append(np.interp(v, xs, ys))
    return out


def render_coverage(layer, sym, view):
    geo = layer['geo']
    H, W = view.height, view.width
    # sample positions: the cell containing each pixel centre (each cell portrayed over its area)
    ii = np.arange(W) + 0.5
    jj = np.arange(H) + 0.5
    X = view.bbox[0] + ii * view.rx
    Y = view.bbox[3] - jj * view.ry
    col = np.floor((X - geo['xll']) / geo['cs']).astype(int)
    row = np.floor((geo['ytop'] - Y) / geo['cs']).astype(int)
    vc = (col >= 0) & (col < geo['ncols'])
    vr = (row >= 0) & (row < geo['nrows'])
    colc = np.clip(col, 0, geo['ncols'] - 1)
    rowc = np.clip(row, 0, geo['nrows'] - 1)
    inside = vr[:, None] & vc[None, :]

    nr, nc = geo['nrows'], geo['ncols']
    rgb = None
    single = sym.get('singleChannel')
    if single is not None and not is_array(single):
        single = np.full((nr, nc), float(single))
    if single is None and len(layer['bands']) == 1 and sym.get('colorChannels') is None:
        single = list(layer['bands'].values())[0]
    alpha = np.ones((nr, nc))
    if sym.get('colorMap') and single is not None:
        r, g, b = interp_map(single, sym['colorMap'], 3)
        rgb = np.stack([r, g, b], -1) / 255.0
    elif sym.get('colorChannels') is not None:
        cc = sym['colorChannels']
        chans = []
        for k in 'rgb':
            v = cc.get(k)
            v = np.zeros((nr, nc)) if v is None else (v if is_array(v) else np.full((nr, nc), float(v)))
            chans.append(np.clip(v, 0, 1))
        rgb = np.stack(chans, -1)
    elif single is not None:
        g = np.clip(single, 0, 1)
        rgb = np.stack([g, g, g], -1)
    if rgb is None:
        log('coverage %s: nothing to portray' % layer['name'])
        return None
    if sym.get('opacityMap') and single is not None:
        alpha = alpha * interp_map(single, sym['opacityMap'], 1)[0]
    ac = sym.get('alphaChannel', 1)
    alpha = alpha * (ac if is_array(ac) else float(ac))

    hs = sym.get('hillShading')
    if hs and hs.get('factor', 0) and single is not None:
        f = float(hs['factor'])
        z = np.where(np.isnan(single), np.nanmean(single), single)
        zp = np.pad(z, 1, mode='edge')
        d = geo['cs']
        dzdx = (zp[1:-1, 2:] - zp[1:-1, :-2]) / (2 * d)          # towards east
        dzdy = (zp[:-2, 1:-1] - zp[2:, 1:-1]) / (2 * d)          # towards north (rows go south)
        nx, ny, nz = -f * dzdx, -f * dzdy, np.ones_like(z)
        nn = np.sqrt(nx * nx + ny * ny + nz * nz)
        sun = hs.get('sun') or {}
        az = math.radians(sun.get('azimuth', 315))
        el = math.radians(sun.get('elevation', 45))
        sx, sy, sz = math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)
        shade = np.clip((nx * sx + ny * sy + nz * sz) / nn, 0, 1)
        if hs.get('colorMap'):
            r, g, b = interp_map(shade, hs['colorMap'], 3)
            rgb = np.stack([r, g, b], -1) / 255.0
        else:
            rgb = rgb * shade[..., None]
        if hs.get('opacityMap'):
            alpha = alpha * interp_map(shade, hs['opacityMap'], 1)[0]
    if single is not None:
        alpha = np.where(np.isnan(single), 0, alpha)

    px_rgb = rgb[rowc[:, None], colc[None, :]]
    px_a = alpha[rowc[:, None], colc[None, :]] * inside
    px_a = np.clip(px_a * float(sym.get('opacity', 1)), 0, 1)
    return np.concatenate([np.clip(px_rgb, 0, 1), px_a[..., None]], -1)


def paint_rgba_array(c, rgba):
    H, W = rgba.shape[:2]
    a = rgba[..., 3]
    pre = rgba[..., :3] * a[..., None]
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, W)
    buf = np.zeros((H, stride), np.uint8)
    bgra = np.zeros((H, W, 4), np.uint8)
    bgra[..., 0] = np.round(pre[..., 2] * 255)
    bgra[..., 1] = np.round(pre[..., 1] * 255)
    bgra[..., 2] = np.round(pre[..., 0] * 255)
    bgra[..., 3] = np.round(a * 255)
    buf[:, :W * 4] = bgra.reshape(H, W * 4)
    surf = cairo.ImageSurface.create_for_data(bytearray(buf.tobytes()), cairo.FORMAT_ARGB32, W, H, stride)
    c.set_source_surface(surf, 0, 0)
    c.get_source().set_filter(cairo.FILTER_NEAREST)
    c.paint()


# =========================================================================== vector drawing

def rgba(c, color, op):
    r, g, b = [v / 255 for v in color]
    c.set_source_rgba(r, g, b, max(0.0, min(1.0, op)))


def path_rings(c, rings):
    c.new_path()
    for r in rings:
        if len(r) < 2:
            continue
        c.move_to(*r[0])
        for p in r[1:]:
            c.line_to(*p)
        c.close_path()


def path_line(c, pts):
    c.new_path()
    c.move_to(*pts[0])
    for p in pts[1:]:
        c.line_to(*p)


def draw_fill(c, it, view):
    fill = it['sym'].get('fill')
    if not fill:
        return
    polys = [p for k, p in it['parts'] if k == 'polygon']
    if not polys:
        return
    op = float(fill.get('opacity', 1))
    color = fill.get('color') or WHITE
    c.save()
    c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    hatch, dots, stip = fill.get('hatch'), fill.get('dotpattern'), fill.get('stipple')
    for rings in polys:
        if not (hatch or dots or stip):
            path_rings(c, rings)
            rgba(c, color, op)
            c.fill()
            continue
        c.save()
        path_rings(c, rings)
        c.clip()
        rgba(c, color, op)
        W, H = view.width, view.height
        if hatch:
            # lines on one pattern aligned with the map, one through its top left corner
            dist = length_px(hatch.get('distance'), view)
            width = length_px(hatch.get('width'), view)
            a = math.radians(float(hatch.get('angle', 45)))
            d = (math.cos(a), -math.sin(a))        # counter-clockwise as seen on the map
            n = (math.sin(a), math.cos(a))
            if dist > 0 and width > 0:
                corners = [(0, 0), (W, 0), (0, H), (W, H)]
                proj = [x * n[0] + y * n[1] for x, y in corners]
                k0, k1 = int(math.floor(min(proj) / dist)) - 1, int(math.ceil(max(proj) / dist)) + 1
                L = W + H
                c.new_path()
                for k in range(k0, k1 + 1):
                    px, py = n[0] * k * dist, n[1] * k * dist
                    c.move_to(px - d[0] * L * 2, py - d[1] * L * 2)
                    c.line_to(px + d[0] * L * 2, py + d[1] * L * 2)
                c.set_line_width(width)
                c.stroke()
        elif dots:
            dd = dots.get('distance') or {}
            hx = length_px(dd.get('horizontal'), view) or 10
            vy = length_px(dd.get('vertical'), view) or 10
            c.new_path()
            y = vy / 2
            while y < H + vy:
                x = hx / 2
                while x < W + hx:
                    c.new_sub_path()
                    c.arc(x, y, 1.0, 0, 2 * math.pi)
                    x += hx
                y += vy
            c.fill()
        elif stip:
            ratio = max(0.0, min(1.0, float(stip.get('ratio', 0.5))))
            bayer = np.array([[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
                              [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
                              [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
                              [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]])
            on = (bayer + 0.5) / 64 < ratio
            c.new_path()
            for y in range(H):
                for x in range(W):
                    if on[y % 8, x % 8]:
                        c.rectangle(x, y, 1, 1)
            c.fill()
        c.restore()
    c.restore()


def stroke_paths(c, it):
    """Adds the stroked geometry (lines and polygon rings) of an item to the path."""
    c.new_path()
    any_ = False
    for k, p in it['parts']:
        if k == 'line' and len(p) >= 2:
            c.move_to(*p[0])
            for q in p[1:]:
                c.line_to(*q)
            any_ = True
        elif k == 'polygon':
            for r in p:
                if len(r) < 2:
                    continue
                c.move_to(*r[0])
                for q in r[1:]:
                    c.line_to(*q)
                c.close_path()
                any_ = True
    return any_


def draw_stroke_layer(c, it, view, which):
    st = it['sym'].get('stroke')
    if not st:
        return
    main_w = length_px(st.get('width'), view)
    if which == 'casing':
        cs = st.get('casing')
        if not cs:
            return
        cw = length_px(cs.get('width'), view)
        if cw <= 0 or main_w <= 0:
            return
        w, color, op = main_w + 2 * cw, cs.get('color') or BLACK, float(cs.get('opacity', 1))
        dash = None
    elif which == 'center':
        cs = st.get('center')
        if not cs:
            return
        w = length_px(cs.get('width'), view)
        if w <= 0:
            return
        color, op = cs.get('color') or BLACK, float(cs.get('opacity', 1))
        dash = None
    else:
        w = main_w
        if w <= 0:
            return               # /req/vector/stroke: nothing for a width of 0 or less
        color, op = st.get('color') or BLACK, float(st.get('opacity', 1))
        dash = st.get('dashPattern')
    if not stroke_paths(c, it):
        return
    c.set_line_width(w)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    if dash:
        dl = [max(0.0, length_px(d, view)) for d in dash]
        if sum(dl) > 0:
            c.set_dash(dl, length_px(st.get('dashOffset'), view))
    else:
        c.set_dash([])
    rgba(c, color, op)
    c.stroke()
    c.set_dash([])


def marker_positions(it):
    out = []
    for k, p in it['parts']:
        if k == 'point':
            out.append(p)
        elif k == 'line':
            out += list(p)
        elif k == 'polygon':
            out.append(polygon_centroid(p[0:]))
    return out


# =========================================================================== main rendering

def render_case(case):
    case_dir = os.path.join(CASES, case)
    with open(os.path.join(case_dir, 'view-1.json'), encoding='utf-8') as f:
        view = View(json.load(f))
    with open(os.path.join(case_dir, 'style.cs.json'), encoding='utf-8') as f:
        style = json.load(f)
    rules = style.get('stylingRules', [])
    variables = style.get('$variables', {})
    layers = load_layers(case_dir, view)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, view.width, view.height)
    c = cairo.Context(surf)
    c.set_antialias(cairo.ANTIALIAS_GRAY)
    c.set_source_rgb(1, 1, 1)
    c.paint()

    items = []        # vector features to draw
    coverages = []    # (zOrder, layer_index, rgba)
    labels = []
    for li, layer in enumerate(layers):
        if layer['type'] == 'coverage':
            ctx = EvalContext(layer['bands'], make_sysids(view, layer), variables)
            sym = resolve(rules, ctx)
            if not sym.get('visibility'):
                continue
            arr = render_coverage(layer, sym, view)
            if arr is not None:
                coverages.append((float(sym.get('zOrder', 1)), li, arr))
            continue
        for fi, feat in enumerate(layer['features']):
            props = feat.get('properties') or {}
            ctx = EvalContext(props, make_sysids(view, layer, feat), variables)
            sym = resolve(rules, ctx)
            if not sym.get('visibility'):
                continue
            parts = []
            for k, g in explode(feat.get('geometry')):
                if k == 'point':
                    parts.append((k, view.to_px(*g)))
                elif k == 'line':
                    parts.append((k, [view.to_px(*p) for p in g]))
                else:
                    parts.append((k, [[view.to_px(*p) for p in r] for r in g]))
            it = {'sym': sym, 'parts': parts, 'layer': li, 'fi': fi, 'zOrder': float(sym.get('zOrder', 1)),
                  'opacity': max(0.0, min(1.0, float(sym.get('opacity', 1))))}
            items.append(it)
            if sym.get('label') and sym['label'].get('elements'):
                labels.append(it)

    zs = sorted({it['zOrder'] for it in items} | {z for z, _, _ in coverages})
    for z in zs:
        for cz, li, arr in coverages:
            if cz == z:
                paint_rgba_array(c, arr)
        zitems = [it for it in items if it['zOrder'] == z]
        # groups of equal Symbolizer opacity, drawn together (/rec/core/opacity-together)
        groups = []
        for it in zitems:
            for g in groups:
                if g[0] == it['opacity']:
                    g[1].append(it)
                    break
            else:
                groups.append((it['opacity'], [it]))
        for op, gitems in groups:
            if op <= 0:
                continue
            c.push_group()
            for it in gitems:
                draw_fill(c, it, view)
            for which in ('casing', 'main', 'center'):
                for it in gitems:
                    draw_stroke_layer(c, it, view, which)
            for it in gitems:
                mk = it['sym'].get('marker')
                if not mk or not mk.get('elements'):
                    continue
                gr = graphic_elements(mk, [it['sym'].get('font')], view, case_dir)
                for (x, y) in marker_positions(it):
                    draw_items_at(c, gr, x, y, 1.0)
            c.pop_group_to_source()
            c.paint_with_alpha(op)

    place_and_draw_labels(c, labels, layers, view, case_dir)

    os.makedirs(OUT, exist_ok=True)
    surf.flush()
    buf = np.frombuffer(surf.get_data(), np.uint8).reshape(view.height, surf.get_stride())
    bgra = buf[:, :view.width * 4].reshape(view.height, view.width, 4)
    rgb = np.stack([bgra[..., 2], bgra[..., 1], bgra[..., 0]], -1)
    Image.fromarray(rgb, 'RGB').save(os.path.join(OUT, '%s-1.png' % case))
    return view


# =========================================================================== labels

def label_priority(it):
    pl = it['sym']['label'].get('placement') or {}
    p = pl.get('priority')
    if p is None or is_array(p):
        return 0.0
    return float(p)


def label_key(lab_items, layer):
    return (layer, tuple((i['kind'], i.get('text')) for i in lab_items))


def place_and_draw_labels(c, labels, layers, view, case_dir):
    occ = Occupancy(view.width, view.height)
    placed = []                  # (draw-callable)
    positions = {}               # label key -> list of positions (repetitions)

    # --- build candidates: point/polygon labels per feature, line labels per joined line
    entries = []
    line_groups = {}
    for it in labels:
        lab = it['sym']['label']
        gr = graphic_elements(lab, [it['sym'].get('font')], view, case_dir)
        if not gr:
            continue
        key = label_key(gr, it['layer'])
        pl = lab.get('placement') or {}
        min_sp = length_px(pl['minSpacing'], view) if pl.get('minSpacing') else None
        max_sp = length_px(pl['maxSpacing'], view) if pl.get('maxSpacing') else None
        prio = label_priority(it)
        lines = [p for k, p in it['parts'] if k == 'line']
        pts = [p for k, p in it['parts'] if k == 'point'] + \
              [polygon_centroid(p) for k, p in it['parts'] if k == 'polygon']
        for p in pts:
            entries.append({'kind': 'point', 'prio': prio, 'order': (it['layer'], it['fi']), 'items': gr,
                            'pos': p, 'key': key, 'min': min_sp})
        if lines:
            g = line_groups.setdefault(key, {'prio': prio, 'order': (it['layer'], it['fi']), 'items': gr,
                                             'lines': [], 'key': key, 'min': min_sp, 'max': max_sp})
            g['prio'] = max(g['prio'], prio)
            g['lines'] += lines
    for key, g in line_groups.items():
        for chain in join_lines(g['lines']):
            entries.append({'kind': 'line', 'prio': g['prio'], 'order': g['order'], 'items': g['items'],
                            'chain': chain, 'key': key, 'min': g['min'], 'max': g['max']})

    # higher priority first; ties in data order (choice C-23)
    entries.sort(key=lambda e: (-e['prio'], e['order']))
    for e in entries:
        reps = positions.setdefault(e['key'], [])
        if e['kind'] == 'point':
            x, y = e['pos']
            if not (0 <= x <= view.width and 0 <= y <= view.height):
                continue
            if e['min'] and any(math.hypot(x - a, y - b) < e['min'] for a, b in reps):
                continue
            boxes = item_boxes(e['items'], x, y)
            mask = occ.raster([box_poly(b) for b in boxes])
            if not occ.free(mask):
                continue
            occ.add(mask)
            reps.append((x, y))
            placed.append(('point', e['items'], x, y))
        else:
            for cand in line_candidates(e, view):
                ax, ay = cand['anchor']
                if e['min'] is not None and any(math.hypot(ax - a, ay - b) < e['min'] for a, b in reps):
                    continue
                mask = occ.raster(cand['polys'])
                if not occ.free(mask):
                    continue
                occ.add(mask)
                reps.append((ax, ay))
                placed.append(('line', cand))
                if e['min'] is None:
                    break          # choice C-27: without minSpacing, one label per joined line
    for p in placed:
        if p[0] == 'point':
            draw_items_at(c, p[1], p[2], p[3], 1.0)   # Symbolizer opacity does not apply to labels
        else:
            draw_line_label(c, p[1])


MAX_BEND = math.radians(40)


def line_candidates(e, view, step=2.0):
    items = e['items']
    fwd = Polyline(e['chain'])          # already in map pixels
    if fwd.length <= 0:
        return []
    texts = []
    others = []
    ext_min, ext_max = math.inf, -math.inf
    for it in items:
        if it['kind'] == 'text':
            lay = TextLayout(it['text'], it['font'])
            dx, base = align_offsets(lay, it['align'][0], it['align'][1])
            x0 = it['x'] + dx
            texts.append((it, lay, x0, base))
            ext_min = min(ext_min, x0 - outline_size(it['font']))
            ext_max = max(ext_max, x0 + lay.advance + outline_size(it['font']))
        else:
            if it['kind'] == 'dot':
                hw = it['size'] / 2
                lo, hi = it['x'] - hw, it['x'] + hw
            else:
                lo, hi = it['x'] - it['hx'], it['x'] - it['hx'] + it['w']
            others.append(it)
            ext_min = min(ext_min, lo)
            ext_max = max(ext_max, hi)
    if ext_max - ext_min > fwd.length:
        return []                    # /rec/labels/line: line shorter than the label
    cands = []
    for orient, pl in (('f', fwd), ('r', fwd.reversed())):
        s = -ext_min
        while s + ext_max <= pl.length:
            cand = build_line_candidate(pl, s, texts, others, ext_min, ext_max, view)
            if cand is not None:
                cand['sort'] = s          # distance along the line in the direction the label reads
                cands.append(cand)
            s += step
    # choice C-26: repetitions packed greedily from where the line starts in reading direction
    cands.sort(key=lambda c: c['sort'])
    return cands


def build_line_candidate(pl, s, texts, others, ext_min, ext_max, view):
    p0 = pl.point(s + ext_min)
    p1 = pl.point(s + ext_max)
    if p1[0] - p0[0] < 0 or (p1[0] - p0[0] == 0 and p1[1] - p0[1] > 0):
        return None                  # would read right to left / upside down
    polys = []
    runs = []
    prev_ang = None
    W, H = view.width, view.height
    for it, lay, x0, base in texts:
        o = outline_size(it['font'])
        # y of the position is perpendicular to the line, positive towards the top of the label
        down = base - it['y']        # /req/labels/line: positive y towards the top of the label
        trun = []
        for gi, gx, adv in lay.glyphs:
            u = s + x0 + gx + adv / 2
            a = pl.point(u - max(adv / 2, 1.0))
            b = pl.point(u + max(adv / 2, 1.0))
            t = b - a
            tl = math.hypot(t[0], t[1])
            if tl == 0:
                return None
            t = t / tl
            ang = math.atan2(t[1], t[0])
            if prev_ang is not None:
                dang = (ang - prev_ang + math.pi) % (2 * math.pi) - math.pi
                if abs(dang) > MAX_BEND:
                    return None
            prev_ang = ang
            n = np.array([-t[1], t[0]])          # towards the bottom of the label
            c = pl.point(u)
            org = c - t * (adv / 2) + n * down
            trun.append((gi, float(org[0]), float(org[1]), ang))
            # footprint quad of the glyph cell (advance x ascent+descent, plus outline)
            top = org - n * (lay.ascent + o)
            bot = org + n * (lay.descent + o)
            q = [top - t * o, top + t * (adv + o), bot + t * (adv + o), bot - t * o]
            for qq in q:
                if not (0 <= qq[0] <= W and 0 <= qq[1] <= H):
                    return None          # choice C-25: line labels lie entirely inside the map
            polys.append([(float(x), float(y)) for x, y in q])
        runs.append((trun, it['font'], it['opacity']))
    dots = []
    for it in others:
        u = s + it['x']
        a = pl.point(u - 1)
        b = pl.point(u + 1)
        t = b - a
        t = t / (math.hypot(t[0], t[1]) or 1)
        n = np.array([-t[1], t[0]])
        cpos = pl.point(u) - n * it['y']
        if it['kind'] == 'dot':
            r = it['size'] / 2
            q = [(cpos[0] - r, cpos[1] - r), (cpos[0] + r, cpos[1] - r), (cpos[0] + r, cpos[1] + r),
                 (cpos[0] - r, cpos[1] + r)]
            for qq in q:
                if not (0 <= qq[0] <= W and 0 <= qq[1] <= H):
                    return None
            polys.append(q)
            dots.append((it, float(cpos[0]), float(cpos[1]), math.atan2(t[1], t[0])))
        else:
            dots.append((it, float(cpos[0]), float(cpos[1]), math.atan2(t[1], t[0])))
    anchor = pl.point(s)
    return {'anchor': (float(anchor[0]), float(anchor[1])), 'polys': polys, 'runs': runs, 'others': dots}


def draw_line_label(c, cand):
    for it, x, y, ang in cand['others']:
        if it['kind'] == 'dot':
            r, g, b = [v / 255 for v in it['color']]
            c.set_source_rgba(r, g, b, max(0.0, min(1.0, it['opacity'])))
            c.new_path()
            c.arc(x, y, it['size'] / 2, 0, 2 * math.pi)
            c.fill()
        elif it['kind'] == 'image':
            c.save()
            c.translate(x, y)
            c.rotate(ang)
            draw_items_at(c, [dict(it, x=0, y=0)], 0, 0, 1.0)
            c.restore()
    for runs, font, op in cand['runs']:
        draw_glyph_runs(c, runs, font, op)


def main(argv):
    cases = argv or sorted(os.path.basename(p) for p in glob.glob(os.path.join(CASES, 'case-*')))
    for case in cases:
        LOG.clear()
        try:
            render_case(case)
            status = 'ok'
        except Exception as ex:  # report and go on with the other cases
            import traceback
            traceback.print_exc()
            status = 'FAILED: %s' % ex
        print(case, status, '; '.join(sorted(set(LOG))))


if __name__ == '__main__':
    main(sys.argv[1:])
