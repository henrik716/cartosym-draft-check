import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import cs
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cases = json.load(open(os.path.join(here, 'cases.json'), encoding='utf-8'))
res = {}
for c in cases:
    try:
        if c['kind'] == 'style':
            try: cs.check_style(c['style']); res[c['id']] = 'valid'
            except cs.CSError: res[c['id']] = 'invalid'
        else:
            res[c['id']] = cs.evaluate(c)
    except Exception as ex:
        res[c['id']] = {'error': '%s: %s' % (type(ex).__name__, ex)}
json.dump(res, open(os.path.join(here, 'results.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
for c in cases:
    print(c['id'], '|', c.get('cql2_text', '')[:50].replace('\n', ' '), '=>', res[c['id']])
