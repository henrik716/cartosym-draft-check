import json, math, random, re, sys, unicodedata

class CSError(Exception):
    pass

# ---------------------------------------------------------------- lexer
KEYWORDS = {'in','not','is','like','between','and','or','div'}
UNITS = {'px','m','ft','pc','pt','em','inch','cm','mm'}
TOKRE = re.compile(r"""
 (?P<ws>[ \t\r\n\u00a0]+)
|(?P<cm>/\*.*?\*/|//[^\r\n]*)
|(?P<str>'(?:''|\\'|[^'])*'(?:[ \t\r\n]+'(?:''|\\'|[^'])*')*)
|(?P<num>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)
|(?P<hex>\#[0-9a-fA-F]+)
|(?P<id>"[^"]*"|[^\W\d]\w*)
|(?P<op><>|<=|>=|[{}.;\[\](),=<>?:*/%^+\-@])
""", re.X | re.S)

def lex(s):
    pos, out = 0, []
    while pos < len(s):
        m = TOKRE.match(s, pos)
        if not m:
            raise CSError("lex error at %d: %r" % (pos, s[pos:pos+10]))
        pos = m.end()
        k = m.lastgroup
        if k in ('ws', 'cm'):
            continue
        t = m.group()
        if k == 'id':
            low = t.lower()
            if low in KEYWORDS:
                out.append(('kw', low))
            elif t in UNITS:
                out.append(('unit', t))
            else:
                out.append(('id', t))
        elif k == 'str':
            parts = re.findall(r"'((?:''|\\'|[^'])*)'", t)
            val = ''.join(p.replace("''", "'").replace("\\'", "'") for p in parts)
            out.append(('str', val))
        elif k == 'num':
            out.append(('num', float(t) if re.search(r'[.eE]', t) else int(t)))
        elif k == 'hex':
            out.append(('hex', t))
        else:
            out.append(('op', t))
    out.append(('eof', None))
    return out

# ---------------------------------------------------------------- parser
# precedence per grammar order (high to low): unary +/-, ^, * / div %, + -,
# relational, between, not, and, or, ?:
class Parser:
    def __init__(self, toks):
        self.t = toks; self.i = 0
    def peek(self, o=0): return self.t[self.i + o]
    def next(self):
        x = self.t[self.i]; self.i += 1; return x
    def isop(self, v, o=0):
        k = self.peek(o); return k[0] == 'op' and k[1] == v
    def iskw(self, v, o=0):
        k = self.peek(o); return k[0] == 'kw' and k[1] == v
    def expect(self, v):
        if not self.isop(v): raise CSError("expected %s got %r" % (v, self.peek()))
        self.i += 1

    def expression(self):
        return self.cond()
    def cond(self):
        c = self.orx()
        if self.isop('?'):
            self.next(); a = self.cond(); self.expect(':'); b = self.cond()
            return {'op': '?:', 'args': [c, a, b]}
        return c
    def orx(self):
        l = self.andx()
        while self.iskw('or'):
            self.next(); l = {'op': 'or', 'args': [l, self.andx()]}
        return l
    def andx(self):
        l = self.notx()
        while self.iskw('and'):
            self.next(); l = {'op': 'and', 'args': [l, self.notx()]}
        return l
    def notx(self):
        if self.iskw('not'):
            self.next(); return {'op': 'not', 'args': [self.notx()]}
        return self.betw()
    def betw(self):
        l = self.rel()
        # between is lower than relational per grammar order
        neg = False
        if self.iskw('not') and self.iskw('between', 1):
            self.next(); neg = True
        if self.iskw('between'):
            self.next()
            lo = self.add(); 
            if not self.iskw('and'): raise CSError('between needs and')
            self.next(); hi = self.add()
            r = {'op': 'between', 'args': [l, lo, hi]}
            return {'op': 'not', 'args': [r]} if neg else r
        return l
    def rel(self):
        l = self.add()
        while True:
            k = self.peek()
            if k[0] == 'op' and k[1] in ('=', '<>', '<', '<=', '>', '>='):
                self.next(); l = {'op': k[1], 'args': [l, self.add()]}
            elif self.iskw('in'):
                self.next(); l = {'op': 'in', 'args': [l, self.add()]}
            elif self.iskw('not') and self.iskw('in', 1):
                self.next(); self.next()
                l = {'op': 'not', 'args': [{'op': 'in', 'args': [l, self.add()]}]}
            elif self.iskw('not') and self.iskw('like', 1):
                self.next(); self.next(); l = {'op': 'notLike', 'args': [l, self.add()]}
            elif self.iskw('like'):
                self.next(); l = {'op': 'like', 'args': [l, self.add()]}
            elif self.iskw('is'):
                self.next(); neg = False
                if self.iskw('not'): self.next(); neg = True
                r = self.add()
                n = {'op': 'isNull', 'args': [l]}
                l = {'op': 'not', 'args': [n]} if neg else n
                if r != {'null': True}: raise CSError('is needs null')
            else:
                return l
    def add(self):
        l = self.mul()
        while self.isop('+') or self.isop('-'):
            o = self.next()[1]; l = {'op': o, 'args': [l, self.mul()]}
        return l
    def mul(self):
        l = self.pw()
        while True:
            if self.isop('*') or self.isop('/') or self.isop('%'):
                o = self.next()[1]
            elif self.iskw('div'):
                self.next(); o = 'div'
            else:
                return l
            l = {'op': o, 'args': [l, self.pw()]}
    def pw(self):
        l = self.unary()
        while self.isop('^'):
            self.next(); l = {'op': '^', 'args': [l, self.unary()]}
        return l
    def unary(self):
        if self.isop('-') or self.isop('+'):
            o = self.next()[1]
            e = self.unary()
            if o == '+': return e
            if isinstance(e, (int, float)) and not isinstance(e, bool): return -e
            return {'op': 'neg', 'args': [e]}
        return self.postfix()
    def postfix(self):
        e = self.primary()
        while True:
            if self.isop('.') and self.peek(1)[0] == 'id':
                self.next(); n = self.next()[1]
                if isinstance(e, dict) and 'property' in e:
                    e = {'property': e['property'] + '.' + n}
                else:
                    e = {'member': [e, n]}
            elif self.isop('[') :
                self.next(); idx = self.primary(); self.expect(']')
                e = {'index': [e, idx]}
            else:
                return e
    def primary(self):
        k = self.next()
        if k[0] == 'num':
            if self.peek()[0] == 'unit':
                self.next(); raise CSError('units of measure not evaluable')
            return k[1]
        if k[0] == 'str': return k[1]
        if k[0] == 'hex': return {'hex': k[1]}
        if k[0] == 'op' and k[1] == '@':
            n = self.next()
            if n[0] != 'id': raise CSError('bad variable')
            return {'$ref': '#/$variables/' + n[1]}
        if k[0] == 'op' and k[1] == '(':
            if self.isop(')'):
                self.next(); return {'array': []}
            items = [self.expression()]
            comma = False
            while self.isop(','):
                self.next(); comma = True; items.append(self.expression())
            self.expect(')')
            return {'array': items} if comma else items[0]
        if k[0] == 'op' and k[1] == '[':
            items = []
            if not self.isop(']'):
                items.append(self.expression())
                while self.isop(','):
                    self.next(); items.append(self.expression())
            self.expect(']')
            return {'array': items}
        if k[0] == 'id':
            name = k[1]
            if self.isop('('):
                self.next(); args = []
                if not self.isop(')'):
                    args.append(self.expression())
                    while self.isop(','):
                        self.next(); args.append(self.expression())
                self.expect(')')
                return {'op': name, 'args': args}
            low = name.lower()
            if not name.startswith('"'):
                if low == 'true': return True
                if low == 'false': return False
                if low == 'null': return {'null': True}
            else:
                name = name[1:-1]
            return {'property': name}
        raise CSError('unexpected %r' % (k,))

def parse_text(s):
    p = Parser(lex(s)); e = p.expression()
    if p.peek()[0] != 'eof': raise CSError('trailing tokens')
    return e

# ---------------------------------------------------------------- evaluation
SYS_ALIAS = {'viz': 'visualization', 'viz.sd': 'visualization.scaleDenominator'}
def isnum(x): return isinstance(x, (int, float)) and not isinstance(x, bool)

def fold(s):
    out = []
    for ch in unicodedata.normalize('NFD', s):
        if unicodedata.category(ch) == 'Mn': continue
        out.append(ch)
    t = ''.join(out)
    return t.translate(str.maketrans({'Ø': 'O', 'ø': 'o', 'Ł': 'L', 'ł': 'l', 'Đ': 'D', 'đ': 'd'}))

def like(s, p):
    rx = ''.join('.*' if c == '%' else '.' if c == '_' else re.escape(c) for c in p)
    return re.fullmatch(rx, s, re.S) is not None

def rnd_half_away(x):
    return int(math.floor(abs(x) + 0.5)) * (1 if x >= 0 else -1)

def c_format(f, args):
    idx = [0]
    def rep(m):
        if m.group(0) == '%%': return '%'
        spec = m.group(0); conv = spec[-1]
        a = args[idx[0]]; idx[0] += 1
        if conv in 'di':
            if not isnum(a): raise CSError('fmt')
            return (spec[:-1] + 'd') % int(a)
        if conv in 'feEgG':
            if not isnum(a): raise CSError('fmt')
            return spec % float(a)
        if conv == 's':
            return spec % (str(a) if isinstance(a, str) else json.dumps(a))
        if conv in 'xXou':
            if not isnum(a): raise CSError('fmt')
            return spec % int(a)
        if conv == 'c': return spec % (a if isinstance(a, str) else chr(int(a)))
        raise CSError('fmt')
    out = re.sub(r'%%|%[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|L|z)?[diouxXeEfgGcs]', rep, f)
    if idx[0] != len(args): raise CSError('fmt count')
    return out

N, S, A = 'n', 's', 'a'
FUNCS = {
 'abs': ([N], lambda x: abs(x)),
 'acos': ([N], lambda x: math.acos(x)), 'asin': ([N], lambda x: math.asin(x)),
 'atan': ([N], math.atan), 'atan2': ([N, N], math.atan2),
 'ceil': ([N], lambda x: float(math.ceil(x))), 'floor': ([N], lambda x: float(math.floor(x))),
 'cos': ([N], math.cos), 'cosh': ([N], math.cosh), 'exp': ([N], math.exp),
 'log': ([N], math.log), 'log10': ([N], math.log10),
 'max': ([N, N], lambda x, y: max(x, y)), 'min': ([N, N], lambda x, y: min(x, y)),
 'pow': ([N, N], lambda x, y: powf(x, y)), 'random': ([], random.random),
 'round': ([N], rnd_half_away), 'sin': ([N], math.sin), 'sinh': ([N], math.sinh),
 'sqrt': ([N], math.sqrt), 'tan': ([N], math.tan), 'tanh': ([N], math.tanh),
 'contains': ([S, S], lambda a, b: b in a),
 'startsWith': ([S, S], lambda a, b: a.startswith(b)),
 'endsWith': ([S, S], lambda a, b: a.endswith(b)),
 'a_containedBy': ([A, A], lambda a, b: all(x in b for x in a)),
 'a_contains': ([A, A], lambda a, b: all(x in a for x in b)),
 'a_equals': ([A, A], lambda a, b: a == b),
 'a_overlaps': ([A, A], lambda a, b: any(x in b for x in a)),
 'caseInsensitize': ([S], lambda s: s.casefold()), 'casei': ([S], lambda s: s.casefold()),
 'accentInsensitize': ([S], fold), 'accenti': ([S], fold),
 'lowerCase': ([S], lambda s: s.lower()), 'upperCase': ([S], lambda s: s.upper()),
 'concatenate': ([S, S], lambda a, b: a + b),
 'substitute': ([S, S, S], lambda s, a, b: s.replace(a, b) if a else s),
}
def powf(x, y):
    if isinstance(x, int) and isinstance(y, int) and y >= 0: return x ** y
    return float(x) ** y

def tcheck(t, v):
    return isnum(v) if t == N else isinstance(v, str) if t == S else isinstance(v, list)

class Ctx:
    def __init__(self, case):
        self.props = case.get('properties', {}) or {}
        self.sys = case.get('system', {}) or {}
        self.defs = case.get('definitions', {}) or {}
        self.vars = case.get('variables', {}) or {}
        self.stack = []

def ev(e, c):
    if e is None: return None
    if isinstance(e, (bool, int, float, str)): return e
    if isinstance(e, list): return [ev(x, c) for x in e]
    if 'null' in e: return None
    if 'array' in e: return [ev(x, c) for x in e['array']]
    if 'property' in e: return c.props.get(e['property'])
    if 'sysId' in e:
        k = e['sysId']
        return c.sys.get(k, c.sys.get(SYS_ALIAS.get(k, k)))
    if '$ref' in e:
        name = e['$ref'].split('/')[-1]
        if name in c.vars: return ev(c.vars[name], c)
        if name in c.defs:
            if name in c.stack: raise CSError('cyclic variable')
            c.stack.append(name)
            try: return ev(c.defs[name], c)
            finally: c.stack.pop()
        return None
    if 'op' not in e: raise CSError('unknown node %r' % (e,))
    op, args = e['op'], e.get('args', [])
    if op == 'and' or op == 'or':
        vals = [ev(a, c) for a in args]
        if op == 'and':
            if any(v is False for v in vals): return False
            return None if any(v is None for v in vals) else all(v is True for v in vals) or None
        if any(v is True for v in vals): return True
        return None if any(v is None for v in vals) else False
    if op == 'not':
        v = ev(args[0], c)
        return None if v is None else (not v if isinstance(v, bool) else None)
    if op == '?:':
        return ev(args[1], c) if ev(args[0], c) is True else ev(args[2], c)
    if op == 'isNull': return ev(args[0], c) is None
    vals = [ev(a, c) for a in args]
    if op in ('=', '<>', '<', '<=', '>', '>='):
        a, b = vals
        if a is None or b is None: return None
        if isnum(a) and isnum(b) or (isinstance(a, str) and isinstance(b, str)) or (isinstance(a, bool) and isinstance(b, bool)):
            return {'=': a == b, '<>': a != b, '<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b}[op] if not (op in ('<', '<=', '>', '>=') and isinstance(a, bool)) else None
        if isinstance(a, list) and isinstance(b, list) and op in ('=', '<>'):
            return (a == b) == (op == '=')
        return None
    if op == 'between':
        v, lo, hi = vals
        if None in (v, lo, hi): return None
        try: return lo <= v <= hi if (isnum(v) == isnum(lo) == isnum(hi)) else None
        except TypeError: return None
    if op == 'in':
        v, arr = vals
        if v is None or not isinstance(arr, list): return None
        return any(x == v and type(x) is not bool or x is v for x in arr)
    if op in ('like', 'notLike'):
        a, p = vals
        if not isinstance(a, str) or not isinstance(p, str): return None
        r = like(a, p)
        return r if op == 'like' else not r
    if op in ('+', '-', '*', '/', 'div', 'intDiv', '%', 'mod', '^', 'pow', 'add', 'sub', 'mul', 'neg') and not (op == 'pow' and len(vals) != 2 and False):
        if op == 'pow' and True:  # function form handled below
            pass
        if op == 'neg':
            return -vals[0] if isnum(vals[0]) else None
        if len(vals) != 2 or not all(isnum(v) for v in vals): return None
        a, b = vals
        if op in ('+', 'add'): return a + b
        if op in ('-', 'sub'): return a - b
        if op in ('*', 'mul'): return a * b
        if op == '/':
            return None if b == 0 else a / b
        if op in ('div', 'intDiv'):
            if b == 0: return None
            return int(math.trunc(a / b)) if isinstance(a, float) or isinstance(b, float) else (abs(a) // abs(b)) * (1 if (a >= 0) == (b >= 0) else -1)
        if op in ('%', 'mod'):
            if b == 0: return None
            return math.fmod(a, b) if isinstance(a, float) or isinstance(b, float) else (abs(a) % abs(b)) * (1 if a >= 0 else -1)
        if op in ('^', 'pow'):
            try: return powf(a, b)
            except (OverflowError, ZeroDivisionError, ValueError): return None
    if op == 'format':
        if not vals or not isinstance(vals[0], str): return None
        try: return c_format(vals[0], vals[1:])
        except (CSError, IndexError, ValueError, TypeError): return None
    if op in FUNCS:
        types, fn = FUNCS[op]
        if len(vals) != len(types) or not all(tcheck(t, v) for t, v in zip(types, vals)): return None
        try:
            r = fn(*vals)
            if isinstance(r, float) and (math.isnan(r) or math.isinf(r)): return None
            return r
        except (ValueError, OverflowError, ZeroDivisionError): return None
    raise CSError('unknown function ' + op)

def evaluate(case):
    c = Ctx(case)
    tree = case['cql2_json'] if 'cql2_json' in case else parse_text(case['cql2_text'])
    return ev(tree, c)

# ---------------------------------------------------------------- style check
def check_style(src):
    toks = lex(src); p = Parser(toks)
    def skip_meta_vars():
        while True:
            if p.isop('.') and p.peek(1)[0] == 'id' and p.peek(2)[0] == 'str' and not p.isop('{', 3):
                p.next(); p.next(); p.next()
            elif p.isop('@'):
                p.next(); p.next();  p.expect('='); p.expression(); p.expect(';')
            else: return
    def rule():
        while True:
            if p.peek()[0] == 'id': p.next()
            elif p.isop('['): p.next(); p.expression(); p.expect(']')
            else: break
        p.expect('{')
        if p.isop('.') and p.peek(1)[0] == 'id': p.next(); p.next(); 
        if p.peek()[0] == 'str' : p.next()
        while not p.isop('}'):
            if p.peek()[0] == 'id' and (p.isop(':', 1) or p.isop('.', 1) or p.isop('[', 1)):
                # propertyAssignment: lhValue COLON expression
                p.next()
                while p.isop('.') or p.isop('['):
                    if p.isop('.'): p.next(); p.next()
                    else: p.next(); p.next(); p.expect(']')
                p.expect(':'); p.expression()
                p.expect(';') 
            else:
                rule()
        p.expect('}')
    skip_meta_vars()
    while p.peek()[0] != 'eof': rule()
    return True
