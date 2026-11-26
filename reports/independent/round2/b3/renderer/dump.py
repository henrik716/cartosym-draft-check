import json,glob,sys
def sel(s):
    if isinstance(s,dict):
        if 'sysId' in s: return '$'+s['sysId']
        if 'property' in s: return '@'+str(s['property'])
        if 'op' in s: return '('+(' %s '%s['op']).join(sel(a) for a in s.get('args',[]))+')' if 'args' in s else s['op']+'?'
        return json.dumps(s)
    return json.dumps(s)
def show(rules,ind):
    for r in rules:
        s=r.get('selector')
        print(ind+'SEL '+(sel(s) if s else 'ALL'))
        sym=r.get('symbolizer')
        if sym: print(ind+'  SYM '+json.dumps(sym,separators=(',',':')))
        show(r.get('nestedRules',[]),ind+'    ')
for f in sorted(glob.glob('cases/case-*/style.cs.json')):
    d=json.load(open(f,encoding='utf8'))
    print('=== '+f.replace(chr(92),'/').split('/')[-2]+' '+d.get('metadata',{}).get('title',''))
    show(d['stylingRules'],'')
