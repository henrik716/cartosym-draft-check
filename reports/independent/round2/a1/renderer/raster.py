"""Anti-aliased rasterization primitives on a premultiplied RGBA float canvas (sRGB values, no linearization).

Coverage model: a pixel is a 1x1 box centred at (i + 0.5, j + 0.5).
Strokes use the distance d from the pixel centre to the stroke's centre line and the 1-D box-filter
overlap of [d - 0.5, d + 0.5] with [-w/2, w/2]. Taking the minimum distance over all segments of a
line makes the union of round-capped segments, i.e. round caps and round joins.
Fills use 4 x 4 supersampling with the even-odd rule.
"""
import numpy as np


class Canvas:
    def __init__(self, w, h, bg=None):
        self.w, self.h = w, h
        self.buf = np.zeros((h, w, 4), dtype=np.float64)
        if bg is not None:
            self.buf[..., 0:3] = np.array(bg, dtype=np.float64) / 255.0
            self.buf[..., 3] = 1.0

    def paint(self, cov, rgb, alpha, window=None):
        """Source-over a solid colour with per-pixel coverage `cov` (window = (y0, y1, x0, x1))."""
        if cov is None or alpha <= 0:
            return
        if window is None:
            y0, y1, x0, x1 = 0, self.h, 0, self.w
        else:
            y0, y1, x0, x1 = window
        a = (cov * alpha)[..., None]
        col = np.array(rgb, dtype=np.float64) / 255.0
        src = np.concatenate([col[None, None, :] * a, a], axis=2)
        dst = self.buf[y0:y1, x0:x1]
        self.buf[y0:y1, x0:x1] = src + dst * (1.0 - a)

    def composite(self, other, opacity):
        """Source-over another premultiplied canvas, multiplied by `opacity`."""
        src = other.buf * opacity
        self.buf = src + self.buf * (1.0 - src[..., 3:4])

    def to_image(self):
        from PIL import Image
        # the map canvas starts opaque (background colour), so premultiplied RGB is the final RGB
        rgb = np.clip(self.buf[..., 0:3], 0, 1)
        return Image.fromarray(np.round(rgb * 255).astype(np.uint8), "RGB")


def _window(xmin, ymin, xmax, ymax, w, h, pad):
    x0 = max(0, int(np.floor(xmin - pad)))
    x1 = min(w, int(np.ceil(xmax + pad)) + 1)
    y0 = max(0, int(np.floor(ymin - pad)))
    y1 = min(h, int(np.ceil(ymax + pad)) + 1)
    if x0 >= x1 or y0 >= y1:
        return None
    return y0, y1, x0, x1


def stroke_coverage(polylines, width, w, h):
    """Coverage of round-capped, round-joined strokes of `width` pixels along each polyline (list of Nx2 arrays).

    A polyline with a single point (or zero length) yields a disc of diameter `width`.
    Returns (cov, window) or (None, None).
    """
    if width <= 0 or not polylines:
        return None, None
    allpts = np.concatenate([np.asarray(p, dtype=np.float64) for p in polylines if len(p)])
    if len(allpts) == 0:
        return None, None
    hw = width / 2.0
    win = _window(allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 0].max(), allpts[:, 1].max(), w, h, hw + 1.5)
    if win is None:
        return None, None
    y0, y1, x0, x1 = win
    ys, xs = np.mgrid[y0:y1, x0:x1]
    px = xs + 0.5
    py = ys + 0.5
    dmin = np.full(px.shape, np.inf)
    for p in polylines:
        p = np.asarray(p, dtype=np.float64)
        if len(p) == 0:
            continue
        if len(p) == 1:
            segs = [(p[0], p[0])]
        else:
            segs = zip(p[:-1], p[1:])
        for a, b in segs:
            # restrict to the segment's own window for speed
            sw = _window(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]), w, h, hw + 1.5)
            if sw is None:
                continue
            sy0, sy1, sx0, sx1 = sw
            sy0, sy1 = max(sy0, y0) - y0, min(sy1, y1) - y0
            sx0, sx1 = max(sx0, x0) - x0, min(sx1, x1) - x0
            if sy0 >= sy1 or sx0 >= sx1:
                continue
            qx = px[sy0:sy1, sx0:sx1]
            qy = py[sy0:sy1, sx0:sx1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            l2 = dx * dx + dy * dy
            if l2 == 0:
                t = 0.0
            else:
                t = np.clip(((qx - a[0]) * dx + (qy - a[1]) * dy) / l2, 0.0, 1.0)
            cx = a[0] + t * dx
            cy = a[1] + t * dy
            d = np.hypot(qx - cx, qy - cy)
            np.minimum(dmin[sy0:sy1, sx0:sx1], d, out=dmin[sy0:sy1, sx0:sx1])
    cov = np.clip(np.minimum(hw, dmin + 0.5) - np.maximum(-hw, dmin - 0.5), 0.0, 1.0)
    if not np.any(cov > 0):
        return None, None
    return cov, win


def fill_coverage(rings, w, h, ss=4):
    """Even-odd fill coverage of the rings (list of Nx2 arrays, closed or not), 4x4 supersampled."""
    rings = [np.asarray(r, dtype=np.float64) for r in rings if len(r) >= 3]
    if not rings:
        return None, None
    allpts = np.concatenate(rings)
    win = _window(allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 0].max(), allpts[:, 1].max(), w, h, 1)
    if win is None:
        return None, None
    y0, y1, x0, x1 = win
    edges = []
    for r in rings:
        a = r
        b = np.roll(r, -1, axis=0)
        edges.append(np.concatenate([a, b], axis=1))
    E = np.concatenate(edges)
    E = E[E[:, 1] != E[:, 3]]
    nx = (x1 - x0) * ss
    ny = (y1 - y0) * ss
    mask = np.zeros((ny, nx), dtype=np.float64)
    sx_centres = x0 + (np.arange(nx) + 0.5) / ss
    for j in range(ny):
        yc = y0 + (j + 0.5) / ss
        ya, yb = E[:, 1], E[:, 3]
        hit = ((ya <= yc) & (yc < yb)) | ((yb <= yc) & (yc < ya))
        if not np.any(hit):
            continue
        e = E[hit]
        xs = e[:, 0] + (yc - e[:, 1]) * (e[:, 2] - e[:, 0]) / (e[:, 3] - e[:, 1])
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            i0 = np.searchsorted(sx_centres, xs[k], side="left")
            i1 = np.searchsorted(sx_centres, xs[k + 1], side="left")
            mask[j, i0:i1] = 1.0
    cov = mask.reshape(y1 - y0, ss, x1 - x0, ss).mean(axis=(1, 3))
    if not np.any(cov > 0):
        return None, None
    return cov, win


def dash_polyline(pts, pattern, offset=0.0):
    """Split a polyline into its 'on' pieces for the dash pattern (lengths in px), starting `offset` into the pattern.

    The pattern restarts at the first vertex and continues across vertices (/req/dashes/dash-offset).
    An odd-length pattern is repeated once (as SVG stroke-dasharray). Returns a list of polylines;
    a zero-length dash is returned as a single point.
    """
    pts = np.asarray(pts, dtype=np.float64)
    pat = [max(0.0, float(x)) for x in pattern]
    if len(pat) % 2 == 1:
        pat = pat * 2
    period = sum(pat)
    if period <= 0 or len(pts) < 2:
        return [pts]
    seglen = np.hypot(*(pts[1:] - pts[:-1]).T)
    cum = np.concatenate([[0.0], np.cumsum(seglen)])
    total = cum[-1]

    def point_at(s):
        i = int(np.searchsorted(cum, s, side="right") - 1)
        i = min(max(i, 0), len(seglen) - 1)
        L = seglen[i]
        t = 0.0 if L == 0 else (s - cum[i]) / L
        return pts[i] + t * (pts[i + 1] - pts[i])

    def piece(s0, s1):
        out = [point_at(s0)]
        for k in range(1, len(cum) - 1):
            if s0 < cum[k] < s1:
                out.append(pts[k])
        if s1 > s0:
            out.append(point_at(s1))
        return np.array(out)

    pieces = []
    # position in the pattern at s = 0
    off = float(offset) % period
    s = -off
    idx = 0
    while s < total:
        L = pat[idx % len(pat)]
        on = (idx % 2) == 0
        a, b = s, s + L
        if on:
            a2, b2 = max(a, 0.0), min(b, total)
            if b2 > a2 or (L == 0 and 0.0 <= a <= total):
                pieces.append(piece(a2, b2) if b2 > a2 else np.array([point_at(a)]))
        s = b
        idx += 1
        if idx > 1000000:
            break
    return pieces
