import json, sys, os, glob, collections

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cases')
seen = set()
for f in sorted(glob.glob(os.path.join(base, 'case-*', '*.geojson'))):
    h = open(f, 'rb').read()
    key = (os.path.basename(f), len(h))
    d = json.loads(h)
    feats = d['features']
    gt = collections.Counter(ft['geometry']['type'] if ft['geometry'] else None for ft in feats)
    props = collections.Counter()
    for ft in feats:
        for k, v in (ft.get('properties') or {}).items():
            props[(k, type(v).__name__)] += 1
    print(f[len(base)+1:], len(feats), dict(gt))
    print('   props', dict(props))
    if key in seen:
        continue
    seen.add(key)
    for ft in feats[:3]:
        p = ft.get('properties')
        print('   ', json.dumps(p, ensure_ascii=False)[:300], 'id=', ft.get('id'))
    print('   other keys', [k for k in d.keys() if k != 'features'])
