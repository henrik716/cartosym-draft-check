"""Debug helper: which anchor positions along each joined road can hold a label."""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_render as R

case = sys.argv[1] if len(sys.argv) > 1 else 'case-22'
case_dir = os.path.join(R.CASES, case)
view = R.View(json.load(open(os.path.join(case_dir, 'view-1.json'))))
style = json.load(open(os.path.join(case_dir, 'style.cs.json')))
layers = R.load_layers(case_dir, view)
lay = layers[0]
groups = {}
for fi, feat in enumerate(lay['features']):
    ctx = R.EvalContext(feat['properties'], R.make_sysids(view, lay, feat))
    sym = R.resolve(style['stylingRules'], ctx)
    if sym['visibility'] and sym.get('label'):
        gr = R.graphic_elements(sym['label'], [sym.get('font')], view, case_dir)
        pts = [view.to_px(*p) for p in feat['geometry']['coordinates']]
        groups.setdefault(gr[0]['text'], [gr, []])[1].append(pts)
for k, (gr, lines) in groups.items():
    for chain in R.join_lines(lines):
        cands = R.line_candidates({'items': gr, 'chain': chain}, view, step=2.0)
        ss = sorted(round(c['sort']) for c in cands)
        print(k, 'chain length', round(R.Polyline(chain).length), 'valid anchors', len(ss))
        # print runs of valid positions
        runs = []
        for s in ss:
            if runs and s - runs[-1][1] <= 3:
                runs[-1][1] = s
            else:
                runs.append([s, s])
        print('   ', runs)
