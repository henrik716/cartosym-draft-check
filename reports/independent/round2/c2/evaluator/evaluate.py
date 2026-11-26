"""Evaluator for CQL2-JSON-like expressions (CartoSym Part 1 expression classes)."""
import math
import random
import re
import unicodedata


class EvalError(Exception):
    pass


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


ALIASES = {'visualization': 'viz', 'scaleDenominator': 'sd', 'identifier': 'id'}


def norm_sys(name):
    parts = name.split('.')
    out = []
    for i, p in enumerate(parts):
        if i == 0 and p == 'visualization':
            p = 'viz'
        elif p == 'scaleDenominator' and out and out[0] == 'viz':
            p = 'sd'
        elif p == 'identifier' and out and out[0] == 'dataLayer':
            p = 'id'
        out.append(p)
    return '.'.join(out)


class Ctx:
    def __init__(self, properties=None, system=None, definitions=None, variables=None):
        self.properties = properties or {}
        self.system = {norm_sys(k): v for k, v in (system or {}).items()}
        self.definitions = definitions or {}
        self.variables = variables or {}
        self.stack = []


# ------------------------------------------------------------------ helpers

def eq(a, b):
    """Equality of two non-null values; returns True/False or None when incomparable."""
    if is_num(a) and is_num(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, bool) and isinstance(b, bool):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            r = eq(x, y) if x is not None and y is not None else None
            if r is not True:
                return r if r is None else False
        return True
    return None


def cmp(op, a, b):
    if a is None or b is None:
        return None
    if op in ('=', '<>'):
        r = eq(a, b)
        if r is None:
            return None
        return r if op == '=' else not r
    if (is_num(a) and is_num(b)) or (isinstance(a, str) and isinstance(b, str)):
        return {'<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op]
    return None


def like_regex(pattern):
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == '\\':
            if i + 1 < len(pattern):
                out.append(re.escape(pattern[i + 1]))
                i += 2
                continue
            out.append(re.escape('\\'))
        elif c == '%':
            out.append('.*')
        elif c == '_':
            out.append('.')
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile(''.join(out), re.S)


def tri_and(vals):
    res = True
    for v in vals:
        if v is False:
            return False
        if v is not True:
            res = None
    return res


def tri_or(vals):
    res = False
    for v in vals:
        if v is True:
            return True
        if v is not False:
            res = None
    return res


def trunc_div(a, b):
    if isinstance(a, int) and isinstance(b, int):
        q = abs(a) // abs(b)
        return q if (a >= 0) == (b >= 0) else -q
    return int(math.trunc(a / b))


def arith(op, a, b):
    if a is None or b is None:
        return None
    if not (is_num(a) and is_num(b)):
        return None
    try:
        if op == '+':
            return a + b
        if op == '-':
            return a - b
        if op == '*':
            return a * b
        if op == '/':
            if b == 0:
                return None
            return a / b
        if op == 'div':
            if b == 0:
                return None
            return trunc_div(a, b)
        if op == '%':
            if b == 0:
                return None
            if isinstance(a, int) and isinstance(b, int):
                return a - b * trunc_div(a, b)
            return math.fmod(a, b)
        if op == '^':
            return power(a, b)
    except OverflowError:
        return None
    raise EvalError('unknown arithmetic operator ' + op)


def power(a, b):
    if a == 0 and b < 0:
        return None
    if a < 0 and float(b) != math.floor(b):
        return None
    if isinstance(a, int) and isinstance(b, int) and b >= 0:
        return a ** b
    return float(a) ** float(b)


def accent_fold(s):
    table = {'Ø': 'O', 'ø': 'o', 'Ł': 'L', 'ł': 'l', 'Đ': 'D', 'đ': 'd', 'Ħ': 'H', 'ħ': 'h',
             'Ŧ': 'T', 'ŧ': 't',
             # Cyrillic letters with a descender, hook or bar fold to the base letter
             'ҳ': 'х', 'Ҳ': 'Х', 'ҷ': 'ч', 'Ҷ': 'Ч', 'Ҹ': 'Ч', 'ҹ': 'ч', 'ҿ': 'ҽ', 'Ҿ': 'Ҽ',
             'Ӌ': 'Ч', 'ӌ': 'ч', 'қ': 'к', 'Қ': 'К', 'ҙ': 'з', 'Ҙ': 'З', 'ң': 'н', 'Ң': 'Н',
             'ғ': 'г', 'Ғ': 'Г', 'ү': 'у', 'Ү': 'У', 'ӣ': 'и', 'Ӣ': 'И'}
    out = []
    for ch in s:
        if ch in table:
            out.append(table[ch])
            continue
        d = unicodedata.normalize('NFD', ch)
        kept = ''.join(c for c in d if not (unicodedata.category(c) == 'Mn' and c not in '゙゚'))
        out.append(unicodedata.normalize('NFC', kept))
    return ''.join(out)


def printf(fmt, args):
    specs = list(re.finditer(r'%(?:%|[-+ #0]*\d*(?:\.\d+)?[diouxXeEfgGcs])', fmt))
    conv = [m for m in specs if m.group(0) != '%%']
    if len(conv) != len(args):
        return None
    out, pos, ai = [], 0, 0
    for m in specs:
        out.append(fmt[pos:m.start()])
        pos = m.end()
        tok = m.group(0)
        if tok == '%%':
            out.append('%')
            continue
        a = args[ai]
        ai += 1
        c = tok[-1]
        if c in 'diouxXc':
            if not (isinstance(a, int) and not isinstance(a, bool)):
                return None
            if c == 'c':
                out.append(chr(a))
                continue
            tok = tok[:-1] + ('d' if c in 'iu' else c)
        elif c in 'eEfgG':
            if not is_num(a):
                return None
        elif c == 's':
            if not isinstance(a, str):
                return None
        out.append(tok % a)
    out.append(fmt[pos:])
    return ''.join(out)


def jint(x):
    if math.isnan(x) or math.isinf(x):
        return None
    r = int(x)
    if not -2 ** 63 <= r < 2 ** 63:
        return None
    return r


def f_round(x):
    return jint(math.floor(abs(x) + 0.5) * (1 if x >= 0 else -1)) if not (math.isnan(x) or math.isinf(x)) else None


def guarded(fn):
    def w(*a):
        try:
            r = fn(*a)
        except (ValueError, OverflowError, ZeroDivisionError):
            return None
        if isinstance(r, float) and (math.isnan(r) or math.isinf(r)):
            return None
        return r
    return w


# name -> (param kinds, impl); kind: n number, s string, a array, '*n' variadic number (>=1)
FUNCS = {
    'abs': (['n'], lambda x: abs(x)),
    'acos': (['n'], lambda x: None if x < -1 or x > 1 else math.acos(x)),
    'asin': (['n'], lambda x: None if x < -1 or x > 1 else math.asin(x)),
    'atan': (['n'], math.atan),
    'atan2': (['n', 'n'], math.atan2),
    'ceil': (['n'], lambda x: jint(math.ceil(x)) if not (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else None),
    'cos': (['n'], math.cos),
    'cosh': (['n'], math.cosh),
    'exp': (['n'], math.exp),
    'floor': (['n'], lambda x: jint(math.floor(x)) if not (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else None),
    'log': (['n'], lambda x: None if x <= 0 else math.log(x)),
    'log10': (['n'], lambda x: None if x <= 0 else math.log10(x)),
    'max': (['*n'], lambda *x: max(x)),
    'min': (['*n'], lambda *x: min(x)),
    'pow': (['n', 'n'], power),
    'random': ([], random.random),
    'round': (['n'], lambda x: f_round(float(x))),
    'sin': (['n'], math.sin),
    'sinh': (['n'], math.sinh),
    'sqrt': (['n'], lambda x: None if x < 0 else math.sqrt(x)),
    'tan': (['n'], math.tan),
    'tanh': (['n'], math.tanh),
    'contains': (['s', 's'], lambda a, b: b in a),
    'startsWith': (['s', 's'], lambda a, b: a.startswith(b)),
    'endsWith': (['s', 's'], lambda a, b: a.endswith(b)),
    'casei': (['s'], lambda s: s.casefold()),
    'accenti': (['s'], accent_fold),
    'lowerCase': (['s'], lambda s: s.lower()),
    'upperCase': (['s'], lambda s: s.upper()),
    'concatenate': (['s', 's'], lambda a, b: a + b),
    'substitute': (['s', 's', 's'], lambda s, a, b: s.replace(a, b) if a != '' else s),
    'a_containedBy': (['a', 'a'], None),
    'a_contains': (['a', 'a'], None),
    'a_equals': (['a', 'a'], None),
    'a_overlaps': (['a', 'a'], None),
}


def member(a, b):
    return any(x is not None and eq(x, b) is True for x in a)


def array_fn(name, a, b):
    if name == 'a_containedBy':
        return all(member(b, x) for x in a)
    if name == 'a_contains':
        return all(member(a, x) for x in b)
    if name == 'a_equals':
        return eq(a, b) is True if all(x is not None for x in a + b) else a == b
    if name == 'a_overlaps':
        return any(member(b, x) for x in a if x is not None)


def call_function(name, args):
    key = name if name in FUNCS else None
    if key is None and name == 'format':
        key = 'format'
    if key is None:
        for k in list(FUNCS) + ['format']:
            if k.lower() == name.lower():
                key = k
                break
    if key is None:
        raise EvalError('unknown function ' + name)
    if key == 'format':
        if not args or not isinstance(args[0], str):
            return None
        if any(a is None for a in args):
            return None
        return printf(args[0], args[1:])
    kinds, impl = FUNCS[key]
    if kinds == ['*n']:
        if len(args) < 1 or not all(is_num(a) for a in args):
            return None
        return guarded(impl)(*args)
    if len(args) != len(kinds):
        return None
    for a, k in zip(args, kinds):
        if a is None:
            return None
        if k == 'n' and not is_num(a):
            return None
        if k == 's' and not isinstance(a, str):
            return None
        if k == 'a' and not isinstance(a, list):
            return None
    if key.startswith('a_'):
        return array_fn(key, *args)
    return guarded(impl)(*args)


# ------------------------------------------------------------------ evaluation

def evaluate(node, ctx):
    if node is None or isinstance(node, (bool, int, float, str)):
        return node
    if isinstance(node, list):
        return [evaluate(x, ctx) for x in node]
    if not isinstance(node, dict):
        raise EvalError('unsupported node')
    if 'property' in node:
        if 'member' in node:
            v = ctx.properties.get(node['property'])
            for m in node['member']:
                v = v.get(m) if isinstance(v, dict) else None
            return v
        return ctx.properties.get(node['property'])
    if 'sysId' in node:
        k = norm_sys(node['sysId'])
        if k in ctx.system:
            return ctx.system[k]
        raise EvalError('system identifier %s has no value' % node['sysId'])
    if '$ref' in node:
        name = node['$ref'].rsplit('/', 1)[-1]
        if name in ctx.stack:
            raise EvalError('variable %s is defined in terms of itself' % name)
        if name in ctx.variables:
            return evaluate(ctx.variables[name], ctx)
        if name in ctx.definitions:
            ctx.stack.append(name)
            try:
                return evaluate(ctx.definitions[name], ctx)
            finally:
                ctx.stack.pop()
        raise EvalError('undefined variable ' + name)
    if 'op' in node:
        return operation(node['op'], node.get('args', []), ctx)
    if len(node) == 1 and next(iter(node)) in ('px', 'mm', 'cm', 'inch', 'pt', 'em', 'pc', 'm', 'ft'):
        raise EvalError('a value with a unit of measure is not an expression value here')
    raise EvalError('unsupported expression object')


def operation(op, args, ctx):
    if op == '?:':
        if len(args) != 3:
            raise EvalError('conditional needs three arguments')
        c = evaluate(args[0], ctx)
        return evaluate(args[1], ctx) if c is True else evaluate(args[2], ctx)
    if op in ('and', 'or'):
        vals = [evaluate(a, ctx) for a in args]
        vals = [v if isinstance(v, bool) else None for v in vals]
        return tri_and(vals) if op == 'and' else tri_or(vals)
    vals = [evaluate(a, ctx) for a in args]
    if op == 'not':
        v = vals[0]
        return (not v) if isinstance(v, bool) else None
    if op in ('=', '<>', '<', '>', '<=', '>='):
        if len(vals) != 2:
            raise EvalError('comparison needs two operands')
        return cmp(op, vals[0], vals[1])
    if op == 'isNull':
        return vals[0] is None
    if op == 'like':
        a, p = vals
        if a is None or p is None or not isinstance(a, str) or not isinstance(p, str):
            return None
        return like_regex(p).fullmatch(a) is not None
    if op == 'between':
        x, lo, hi = vals
        r1, r2 = cmp('>=', x, lo), cmp('<=', x, hi)
        return tri_and([r1, r2])
    if op == 'in':
        x, lst = vals
        if not isinstance(lst, list):
            lst = [lst]
        if len(lst) == 0:
            return False
        if x is None:
            return None
        found, unknown = False, False
        for e in lst:
            if e is None:
                unknown = True
                continue
            r = eq(x, e)
            if r is True:
                found = True
            elif r is None:
                unknown = True
        return True if found else (None if unknown else False)
    if op in ('+', '-', '*', '/', '^', '%', 'div'):
        if len(vals) != 2:
            if op in ('+', '-') and len(vals) == 1 and is_num(vals[0]):
                return vals[0] if op == '+' else -vals[0]
            raise EvalError('arithmetic needs two operands')
        return arith(op, vals[0], vals[1])
    return call_function(op, vals)
