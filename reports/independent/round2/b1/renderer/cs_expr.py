"""Evaluation of CartoSym-JSON expressions (CQL2-JSON based, clause 7, 13, 14, 15, 17).

Values: None is NULL; datetime.date / datetime.datetime for temporal instants;
str, int, float, bool; lists for arrays.  For coverages, a property may be a
numpy array (one value per cell); arithmetic then works per cell.
"""
import datetime
import math
import random
import re
import unicodedata

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
TS_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?$')


def is_array(v):
    return np is not None and isinstance(v, np.ndarray)


def parse_date(s):
    return datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def parse_ts(s):
    s = s.rstrip('Z')
    if '.' in s:
        return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%f')
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')


class EvalContext:
    """What an expression can see: feature properties, system identifiers, variables."""

    def __init__(self, props, sysids, variables=None):
        self.props = props
        self.sysids = sysids
        self.variables = variables or {}

    def prop(self, name):
        return self.props.get(name)

    def sysid(self, name):
        return self.sysids(name)


# --------------------------------------------------------------------------- helpers

def _coerce_pair(a, b):
    """Bring two operands of a comparison to comparable types.

    Choice (see notes.md, C-07): an ISO date string compared with a Date (or a
    timestamp string with a DateTime) is read as that Date.  Integers and
    numbers compare as numbers.  Otherwise mismatched types give None (NULL).
    """
    if isinstance(a, bool) or isinstance(b, bool):
        if isinstance(a, bool) and isinstance(b, bool):
            return a, b
        return None
    num = (int, float)
    if isinstance(a, num) and isinstance(b, num):
        return a, b
    if is_array(a) or is_array(b):
        return a, b
    if isinstance(a, datetime.datetime) or isinstance(b, datetime.datetime):
        a2, b2 = a, b
        if isinstance(a2, str) and TS_RE.match(a2):
            a2 = parse_ts(a2)
        if isinstance(b2, str) and TS_RE.match(b2):
            b2 = parse_ts(b2)
        if isinstance(a2, datetime.date) and not isinstance(a2, datetime.datetime):
            a2 = datetime.datetime(a2.year, a2.month, a2.day)
        if isinstance(b2, datetime.date) and not isinstance(b2, datetime.datetime):
            b2 = datetime.datetime(b2.year, b2.month, b2.day)
        if isinstance(a2, datetime.datetime) and isinstance(b2, datetime.datetime):
            return a2, b2
        return None
    if isinstance(a, datetime.date) or isinstance(b, datetime.date):
        a2, b2 = a, b
        if isinstance(a2, str) and DATE_RE.match(a2):
            a2 = parse_date(a2)
        if isinstance(b2, str) and DATE_RE.match(b2):
            b2 = parse_date(b2)
        if isinstance(a2, datetime.date) and isinstance(b2, datetime.date):
            return a2, b2
        return None
    if isinstance(a, str) and isinstance(b, str):
        return a, b
    if isinstance(a, list) and isinstance(b, list):
        return a, b
    return None


def _cmp(op, a, b):
    if a is None or b is None:
        return None
    p = _coerce_pair(a, b)
    if p is None:
        return None
    a, b = p
    if op == '=':
        return a == b
    if op == '<>':
        return a != b
    if op == '<':
        return a < b
    if op == '>':
        return a > b
    if op == '<=':
        return a <= b
    if op == '>=':
        return a >= b
    raise ValueError(op)


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) or is_array(v):
        return v
    return None


def _like(text, pattern):
    if text is None or pattern is None:
        return None
    if not isinstance(text, str) or not isinstance(pattern, str):
        return None
    rx = ''
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == '\\' and i + 1 < len(pattern):
            rx += re.escape(pattern[i + 1])
            i += 2
            continue
        if c == '%':
            rx += '.*'
        elif c == '_':
            rx += '.'
        else:
            rx += re.escape(c)
        i += 1
    return re.fullmatch(rx, text, re.S) is not None


def to_text(v):
    """Conversion of a value to a string where a string is expected.

    Choice (C-12): integers are written in decimal without a fraction, other
    numbers with Python's shortest repr ('2.5'), booleans as 'true'/'false',
    dates as ISO dates.  NULL stays NULL.
    """
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return repr(v)
    if isinstance(v, datetime.date):
        return v.isoformat()
    return str(v)


_FOLD_EXTRA = {'Ø': 'O', 'ø': 'o', 'Ł': 'L', 'ł': 'l', 'Đ': 'D', 'đ': 'd', 'Ħ': 'H', 'ħ': 'h'}


def _accenti(s):
    out = []
    for ch in s:
        if ch in _FOLD_EXTRA:
            out.append(_FOLD_EXTRA[ch])
            continue
        d = unicodedata.normalize('NFD', ch)
        out.append(''.join(c for c in d if unicodedata.category(c) != 'Mn'))
    return unicodedata.normalize('NFC', ''.join(out))


def _printf(fmt, args):
    # C printf conversion specifiers, via Python's % operator (close to ANSI C).
    spec = re.compile(r'%[-+ #0]*(\d+|\*)?(\.(\d+|\*))?[hlLqjzt]*([diouxXeEfgGcs%])')
    out = []
    pos = 0
    ai = 0
    for m in spec.finditer(fmt):
        out.append(fmt[pos:m.start()])
        pos = m.end()
        conv = m.group(4)
        if conv == '%':
            out.append('%')
            continue
        if ai >= len(args):
            return None
        a = args[ai]
        ai += 1
        token = re.sub(r'[hlLqjzt]', '', m.group(0))
        if conv in 'diouxXc':
            if isinstance(a, float) and a.is_integer():
                a = int(a)
            if not isinstance(a, int) or isinstance(a, bool):
                return None
            if conv == 'u':
                token = token[:-1] + 'd'
        elif conv in 'eEfgG':
            if not isinstance(a, (int, float)) or isinstance(a, bool):
                return None
        elif conv == 's':
            if not isinstance(a, str):
                return None
        try:
            out.append(token % a)
        except (TypeError, ValueError):
            return None
    out.append(fmt[pos:])
    if ai != len(args):
        return None
    return ''.join(out)


def _int_or_null(x):
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    r = int(x)
    if r < -2 ** 63 or r >= 2 ** 63:
        return None
    return r


def _round_half_away(x):
    if x is None:
        return None
    if is_array(x):
        return np.sign(x) * np.floor(np.abs(x) + 0.5)
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return _int_or_null(math.copysign(math.floor(abs(x) + 0.5), x))


def _math1(name, x):
    if x is None:
        return None
    x = _num(x)
    if x is None:
        return None
    if is_array(x):
        f = {'abs': np.abs, 'acos': np.arccos, 'asin': np.arcsin, 'atan': np.arctan, 'cos': np.cos,
             'cosh': np.cosh, 'exp': np.exp, 'log': np.log, 'log10': np.log10, 'sin': np.sin,
             'sinh': np.sinh, 'sqrt': np.sqrt, 'tan': np.tan, 'tanh': np.tanh,
             'ceil': np.ceil, 'floor': np.floor, 'round': _round_half_away}[name]
        with np.errstate(all='ignore'):
            return f(x)
    try:
        if name == 'abs':
            return abs(x)
        if name == 'acos':
            return math.acos(x) if -1 <= x <= 1 else None
        if name == 'asin':
            return math.asin(x) if -1 <= x <= 1 else None
        if name == 'atan':
            return math.atan(x)
        if name == 'cos':
            return math.cos(x)
        if name == 'cosh':
            return math.cosh(x)
        if name == 'exp':
            return math.exp(x)
        if name == 'log':
            return math.log(x) if x > 0 else None
        if name == 'log10':
            return math.log10(x) if x > 0 else None
        if name == 'sin':
            return math.sin(x)
        if name == 'sinh':
            return math.sinh(x)
        if name == 'sqrt':
            return math.sqrt(x) if x >= 0 else None
        if name == 'tan':
            return math.tan(x)
        if name == 'tanh':
            return math.tanh(x)
        if name == 'ceil':
            return _int_or_null(math.ceil(x)) if not (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else None
        if name == 'floor':
            return _int_or_null(math.floor(x)) if not (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else None
        if name == 'round':
            return _round_half_away(x)
    except (OverflowError, ValueError):
        return None
    raise KeyError(name)


def _pow(a, b):
    a = _num(a)
    b = _num(b)
    if a is None or b is None:
        return None
    if is_array(a) or is_array(b):
        with np.errstate(all='ignore'):
            return np.power(np.asarray(a, float), b)
    if a == 0 and b < 0:
        return None
    if a < 0 and not float(b).is_integer():
        return None
    try:
        r = a ** b
    except OverflowError:
        return None
    return r


ARITH = {'+', '-', '*', '/', '^', '%', 'div'}


def _arith(op, a, b):
    a = _num(a)
    b = _num(b)
    if a is None or b is None:
        return None
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == '/':
        if is_array(a) or is_array(b):
            with np.errstate(all='ignore'):
                r = np.true_divide(a, b)
            return r
        if b == 0:
            return None
        return a / b
    if op == 'div':
        if not is_array(b) and b == 0:
            return None
        q = a / b
        if is_array(q):
            return np.trunc(q)
        return int(math.trunc(q))
    if op == '%':
        if not is_array(b) and b == 0:
            return None
        if is_array(a) or is_array(b):
            return np.fmod(a, b)
        r = math.fmod(a, b)
        if isinstance(a, int) and isinstance(b, int):
            return int(r)
        return r
    if op == '^':
        return _pow(a, b)
    raise ValueError(op)


# --------------------------------------------------------------------------- evaluator

def is_expression_object(v):
    return isinstance(v, dict) and any(k in v for k in ('op', 'property', 'sysId', '$ref'))


def evaluate(e, ctx):
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if is_array(e):
        return e
    if isinstance(e, list):
        return [evaluate(x, ctx) for x in e]
    if isinstance(e, dict):
        if 'property' in e:
            return ctx.prop(e['property'])
        if 'sysId' in e:
            return ctx.sysid(e['sysId'])
        if '$ref' in e:
            ref = e['$ref']
            name = ref.split('/')[-1]
            if name in ctx.variables:
                return evaluate(ctx.variables[name], ctx)
            return None
        if 'date' in e and len(e) == 1:
            return parse_date(evaluate(e['date'], ctx))
        if 'timestamp' in e and len(e) == 1:
            return parse_ts(evaluate(e['timestamp'], ctx))
        if 'interval' in e and len(e) == 1:
            return tuple(evaluate(x, ctx) for x in e['interval'])
        if 'op' in e:
            return _operation(e['op'], e.get('args', []), ctx)
        # an object literal that is not an expression: returned as is
        return e
    return e


def _operation(op, args, ctx):
    if op == 'and':
        res = True
        for a in args:
            v = evaluate(a, ctx)
            if v is False:
                return False
            if v is None or not isinstance(v, bool):
                res = None
        return res
    if op == 'or':
        res = False
        for a in args:
            v = evaluate(a, ctx)
            if v is True:
                return True
            if v is None or not isinstance(v, bool):
                res = None
        return res
    if op == 'not':
        v = evaluate(args[0], ctx)
        if isinstance(v, bool):
            return not v
        return None
    if op in ('=', '<>', '<', '>', '<=', '>='):
        a = evaluate(args[0], ctx)
        b = evaluate(args[1], ctx)
        return _cmp(op, a, b)
    if op == 'like':
        return _like(evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op == 'between':
        a, lo, hi = (evaluate(x, ctx) for x in args)
        r1 = _cmp('>=', a, lo)
        r2 = _cmp('<=', a, hi)
        return _operation('and', [r1, r2], ctx)
    if op == 'in':
        a = evaluate(args[0], ctx)
        arr = evaluate(args[1], ctx)
        if not isinstance(arr, list):
            return None
        if len(arr) == 0:
            return False
        if a is None:
            return None
        has_null = False
        for x in arr:
            if x is None:
                has_null = True
                continue
            if _cmp('=', a, x) is True:
                return True
        return None if has_null else False
    if op == 'isNull':
        return evaluate(args[0], ctx) is None
    if op in ARITH:
        return _arith(op, evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op == '?:':
        c = evaluate(args[0], ctx)
        return evaluate(args[1], ctx) if c is True else evaluate(args[2], ctx)
    # function calls
    vals = [evaluate(a, ctx) for a in args]
    return call_function(op, vals)


def _texts(vals):
    """Text arguments, with the type-cast permission /per/functions/type-casts used
    for numbers (choice C-12).  Returns None if any is NULL or not convertible."""
    out = []
    for v in vals:
        if v is None:
            return None
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, (int, float, bool)):
            out.append(to_text(v))
        else:
            return None
    return out


def call_function(name, vals):
    if name in ('concatenate',):
        t = _texts(vals)
        if t is None or len(t) < 2:
            return None
        return ''.join(t)
    if name in ('lowerCase', 'upperCase', 'casei', 'accenti'):
        t = _texts(vals)
        if t is None or len(t) != 1:
            return None
        s = t[0]
        if name == 'lowerCase':
            return s.lower()
        if name == 'upperCase':
            return s.upper()
        if name == 'casei':
            return s.casefold()
        return _accenti(s)
    if name == 'substitute':
        t = _texts(vals)
        if t is None or len(t) != 3:
            return None
        return t[0].replace(t[1], t[2])
    if name == 'format':
        if not vals or not isinstance(vals[0], str) or any(v is None for v in vals):
            return None
        return _printf(vals[0], vals[1:])
    if name in ('contains', 'startsWith', 'endsWith'):
        if len(vals) != 2 or not all(isinstance(v, str) for v in vals):
            return None
        a, b = vals
        return (b in a) if name == 'contains' else (a.startswith(b) if name == 'startsWith' else a.endswith(b))
    if name in ('a_containedBy', 'a_contains', 'a_equals', 'a_overlaps'):
        if len(vals) != 2 or not all(isinstance(v, list) for v in vals):
            return None
        a, b = vals
        if name == 'a_containedBy':
            return all(x in b for x in a)
        if name == 'a_contains':
            return all(x in a for x in b)
        if name == 'a_equals':
            return len(a) == len(b) and all(x == y for x, y in zip(a, b))
        return any(x in b for x in a)
    if name in ('abs', 'acos', 'asin', 'atan', 'ceil', 'cos', 'cosh', 'exp', 'floor', 'log',
                'log10', 'round', 'sin', 'sinh', 'sqrt', 'tan', 'tanh'):
        if len(vals) != 1:
            return None
        return _math1(name, vals[0])
    if name == 'atan2':
        if len(vals) != 2 or _num(vals[0]) is None or _num(vals[1]) is None:
            return None
        if is_array(vals[0]) or is_array(vals[1]):
            return np.arctan2(vals[0], vals[1])
        return math.atan2(vals[0], vals[1])
    if name in ('max', 'min'):
        if len(vals) < 1 or any(_num(v) is None for v in vals):
            return None
        if any(is_array(v) for v in vals):
            f = np.maximum if name == 'max' else np.minimum
            r = vals[0]
            for v in vals[1:]:
                r = f(r, v)
            return r
        return max(vals) if name == 'max' else min(vals)
    if name == 'pow':
        if len(vals) != 2:
            return None
        return _pow(vals[0], vals[1])
    if name == 'random':
        if vals:
            return None
        return random.random()
    # unknown function: NULL
    return None
