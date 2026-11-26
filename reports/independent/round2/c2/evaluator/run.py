import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser import ParseError, parse_expression, parse_style, to_json  # noqa: E402
from evaluate import Ctx, EvalError, evaluate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pointer(doc, ptr):
    cur = doc
    for part in ptr.split('/')[1:]:
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(ptr)
    return cur


def run_expr(case, source):
    ctx = Ctx(case.get('properties'), case.get('system'), case.get('definitions'), case.get('variables'))
    try:
        if source == 'json':
            node = case['cql2_json']
        else:
            node = to_json(parse_expression(case['cql2_text']))
        return evaluate(node, ctx)
    except (ParseError, EvalError) as e:
        return {'error': str(e)}


def main():
    cases = json.load(open(os.path.join(ROOT, 'cases.json'), encoding='utf-8'))
    results = {}
    for c in cases:
        if c['kind'] == 'expression':
            if 'cql2_json' in c:
                r = run_expr(c, 'json')
                if 'random' not in c['id']:
                    t = run_expr(c, 'text')
                    if t != r:
                        print('MISMATCH text vs json', c['id'], t, r)
            else:
                r = run_expr(c, 'text')
        else:
            try:
                style = parse_style(c['style'])
                at = c.get('at') or '/stylingRules/0/selector'
                r = pointer(style, at)
            except (ParseError, KeyError, IndexError, ValueError) as e:
                r = {'error': 'invalid style: %s' % e}
        results[c['id']] = r
    with open(os.path.join(ROOT, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    for k, v in results.items():
        print(k, json.dumps(v, ensure_ascii=False))
    print(len(results))


if __name__ == '__main__':
    main()
