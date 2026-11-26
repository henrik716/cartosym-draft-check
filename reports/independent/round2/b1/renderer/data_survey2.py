import json, os, collections
import numpy as np

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cases')

def load(c, n):
    return json.load(open(os.path.join(base, c, n), encoding='utf-8'))

d = load('case-17', 'Roads.geojson')
v = load('case-17', 'view-1.json')
print(v['bbox'])
for i, f in enumerate(d['features']):
    p = f['properties']
    if p['class'] in ('european', 'national', 'county'):
        cs = f['geometry']['coordinates']
        print(i, p, len(cs), cs[0], cs[-1])

d = load('case-19', 'Places.geojson')
for f in d['features']:
    p = f['properties']
    if p['type'] == 'mountain':
        print(p, f['geometry']['coordinates'])

for c in ['case-04', 'case-15', 'case-25', 'case-33', 'case-29', 'case-03']:
    for n in os.listdir(os.path.join(base, c)):
        if n.endswith('.geojson'):
            d = load(c, n)
            print(c, n)
            for f in d['features']:
                print('   ', f['properties'], f['geometry']['type'], f['geometry']['coordinates'] if f['geometry']['type'] == 'Point' else '')

a = np.loadtxt(os.path.join(base, 'case-04', 'Elevation.elevation.asc'), skiprows=6)
print(a.shape, a.min(), a.max(), (a == -9999).sum())
print(collections.Counter(f['properties']['class'] for f in load('case-02', 'Roads.geojson')['features']))
print(collections.Counter(f['properties']['class'] for f in load('case-01', 'Landcover.geojson')['features']))
