# Notes: where the text does not give the result

All 177 cases were evaluated (`results.json`). The code is in `evaluator/` (`parser.py`, `evaluate.py`, `run.py`) and uses only the Python standard library. Where a case has both `cql2_json` and `cql2_text`, I evaluated both and compared them. They agreed for every case, so the text and JSON encodings do not conflict. I ran the JSON as the README asks.

Each item gives the identifier, the words that leave it open, the readings, the one I implemented and the words I relied on. The ones I think matter most are marked **(major)**.

## A. Operator precedence and tuples (CartoSym-CSS)

### A1 (major). Unary minus against `^`: `-2 ^ 2`, `- 2 ^ 2`, `-a ^ 2`, `-2 ^ 0.5` (minus-01, -02, -03, -09)
- Requirement: `/req/arithmetic/pow`, `/req/cscss/expressions`, `/req/cscss/grammar`.
- Words: the requirement text says only "the first operand raised to the power of the second operand". It never gives precedence or associativity. Only the ANTLR grammar does. `unaryArithmeticOperator expression` is listed before `arithmeticOperatorExp`, and the grammar has no `<assoc=right>` on `^`.
- Readings:
  1. Mathematical convention, `-(2^2) = -4`.
  2. The grammar's alternative order, `(-2)^2 = 4`.
  3. For `2 ^ 3 ^ 2`, left association (64) or right association (512). No case tests this one.
- Implemented: reading 2, because the grammar is the only normative statement. minus-01 gives 4, minus-02 gives 4, minus-03 gives 9 and minus-09 gives NULL (negative base, non-integer exponent). `^` is left associative.
- Relied on: the order of the alternatives in `CartoSym-CSS-Grammar.g4`, assuming ANTLR4 gives earlier alternatives higher precedence. The prose never states this.
- Risk: the result differs from what most readers expect. The prose should state the precedence table.

### A2 (major). `-` after whitespace before a digit: tuple or subtraction (minus-06, -10, css-01 to css-06, cscss-tuple-negative)
- Requirement: `/req/cscss/expressions`. The words are in clause 16, "Tuples": "A `-` that follows whitespace and comes directly before a number is the sign of that number, which then starts a new element of the tuple".
- Open points:
  1. `10 -4` outside a tuple context (minus-10 is an expression case, not a style). Readings: (a) the array `[10, -4]`; (b) the subtraction 6; (c) an error. The rule says a new tuple element starts, so I implemented (a). The result format of a tuple that is not a coordinate list is not stated.
  2. `a -4` and `1 + 1 -3` are tuples too under this rule, so they are not subtractions. I implemented that, because the lexer makes the token a negative literal. A reader could find it surprising.
  3. `3 - -2` works as 5: the first `-` is followed by a space, so it is a plain minus, and the second is a sign.
  4. `2 * -a` and `-a * 2` are unary minus (-6). A sign applies only before a number, so unary minus before an identifier is the ordinary operator.
  5. `10 (-4)` (css-06). The grammar has no juxtaposition of a number and a parenthesised expression. I returned an error (syntax error). Alternative: a tuple with a grouped element. The text says tuple elements are "numeric literals or identifiers", so this supports the error.
  6. `Dot { size: 10 -4 }` (css-04). The syntax is valid, but a tuple is not a valid `size` for a Dot (a single number). Readings: (a) error; (b) accept the tuple and ignore the value. I implemented (a). Relied on: "A tuple must be able to replace either an array of coordinate values, an instance of a class defining a single property being such an array, or a class identified as being replaceable by a tuple." Dot is not on the list of tuple classes.
  7. `position: 10 - 4` and `position: 10-4` (css-01, css-02). The syntax is a subtraction. Readings: (a) the expression `{"op":"-","args":[10,4]}`; (b) an error because a UnitPoint is expected and an arithmetic result is a number. I implemented (a). The JSON schema's `unitPoint` accepts an expression object only through `idOrFnExpression`, which excludes arithmetic operators (`conditionalOrFunctionCall`). So the result may not validate against the schema. The text does not say what a number where a point is expected means.
  8. `position: -10 -4` (css-05): the space after the colon makes the first `-10` a negative literal as well. The result is (-10, -4). This depends on whitespace after `:` being counted as "follows whitespace".
- Relied on: the `NEGATIVE_NUMERIC_LITERAL` lexer rule, and the `tuple` rule of the grammar.

### A3. Grammar precedence of the other operators
- Requirement: `/req/core/operations` ("while respecting the priority of operations") does not list the priorities.
- I took the order of the grammar from low to high: `?:`, `or`, `and`, `not`, `between`, relational, additive, multiplicative (including `div` and `%`), `^`, unary minus. For example, `not 1 = 2` is `not (1 = 2)`, and `7 div 2 * 3` is `(7 div 2) * 3` (same level, left to right).
- A reader who knows SQL or CQL2 might expect a different level for `not` and `between`. The prose does not say. No case isolates it except `not (...)` with parentheses.

### A4. `a <> 1` selectors without `at` (neq-selector, neq-selector-no-spaces, neq-selector-and)
- The README says the result of a style is the value at `at`, but these cases have no `at`.
- Readings: (a) the whole style; (b) the selector; (c) just "valid", true.
- I returned the selector at `/stylingRules/0/selector`. In `a<>1` I read the tokens as `a`, `<>`, `1`. The result is `{"op":"<>","args":[{"property":"a"},1]}`. The `and` selector is the same form as the CQL2-JSON `and`.

## B. Numeric types and arithmetic

### B1 (major). Integer or real result types (arith-add, arith-div-integers, math-pow and others)
- Requirement: `/req/arithmetic/*`, clause 7 "Data Types".
- Words: "`number`: ... generally represented as a double-precision floating-point value, but this Standard does not require that representation." `/req/arithmetic/div`: "real-valued quotient ..., including when both operands are integers".
- Readings for JSON output of `1 + 2`: `3` (integer) or `3.0` (real). I kept Python's types: integer operands give an integer for `+ - * div %`, and a number for `/`. `acos(1)` returns `0.0`.
- If a comparison treats `3` and `3.0` as different, results differ. The text does not say which JSON form a conforming result takes.
- Integer overflow: `integer` is a signed 64-bit integer. The text does not say what `9223372036854775807 + 1` gives (NULL, wrap, promote to number). I did not limit it.

### B2. `^` and `pow` result for integer operands (arith-pow, math-pow)
- `2 ^ 10` is given as `number`. I return the integer 1024 when both operands are integers and the exponent is not negative, else a real. The text says only "the first operand raised to the power of the second".
- Also open: `0 ^ 0` (I return 1), a very large result that overflows a double (I return NULL).

### B3. `mod` and `intDiv` with real operands, and sign
- `/req/arithmetic/int-div`: "integer quotient ..., truncated toward zero". `/req/arithmetic/mod`: "consistent with the `intDiv` operator (i.e., the result has the sign of the first operand)".
- For reals (7.5 div 2, 7.5 % 2), I truncate the real quotient and use `a - b*trunc(a/b)` (`fmod`). The text defines these only by "two numeric operands", not integers.

### B4 (major). NULL, error and out-of-domain results
- `/req/arithmetic/div` and others say "to NULL", so division by zero, `pow` and the math domain rules are clear. Open points:
  - Overflow: `exp(1000)`, `1e308 * 10`, `sinh(1000)`. Not stated. I return NULL (the same as NaN or infinity for `round`, `floor`, `ceil` in clause 7). JSON cannot carry infinity.
  - `tan(pi/2)` and `atan2(0, 0)`: I return the double result (and 0 for `atan2(0,0)`).
  - `log(x)` with `x` NULL: NULL.
  - Mixed types, `'a' + 1` and `true + 1`: not stated. I return NULL (an arithmetic operand that is not a number). Alternative: error.
  - `div`/`%` with a NULL operand: NULL.

### B5. `round`, `ceil`, `floor`
- `/req/math/round`: "the integer closest to `x`, rounding halfway cases away from zero". Clear (2.5 gives 3, -2.5 gives -3). The values returned are `integer`, so `ceil(-2.5)` is `-2` (not `-2.0`). A reader who keeps a double would give `-2.0`. The result type is the same issue as B1.

### B6. `max`, `min` with mixed integers and reals, with NULL
- `/req/math/max`: "the greatest of its arguments". I return the argument itself (type kept). A NULL argument: I return NULL. Not stated. Arguments of the wrong type: NULL (following `/req/functions/call-expressions`).

### B7. `random()`
- Any value in [0, 1) is acceptable, so the case is written as a test on range. Nothing to resolve.

## C. NULL handling and relational operators

### C1 (major). "as specified by CQL2" (`/req/core/operations`)
- Words: "A Renderer SHALL support evaluating operation expressions with a null operand as specified by CQL2." I did not read CQL2 (outside the folder), so for NULL operands of comparison, `like`, arithmetic and `between` I could rely only on the NOTE in the same clause, which describes `and`, `or`, `not` and `in`.
- I assumed three-valued logic: any comparison, arithmetic operation or `like` with a NULL operand is NULL. `null = 1`, `null <> 1`, `null > 1`, `null + 1`, `null like 'a%'` are all NULL. `not NULL` is NULL.
- `is null` / `is not null` is the only test that gives true or false for NULL.
- A text that did not rely on an external standard would let an implementer work without CQL2.

### C2. Logical operators with non-boolean operands
- `/req/core/logical`, table of Logical Operators: "True if and only if the operand is false". `not 5` is not defined. I return NULL for non-boolean operands of `and`, `or`, `not`. Alternative: error.

### C3 (major). Comparison of values of different types and ordering rules
- `/req/core/relational`: "The first operand is smaller than the second one". Not stated:
  - `1 = 'a'` (and `1 < 'a'`): I return NULL. Alternative: false, or error.
  - `true = 1`: NULL (a boolean is not a number).
  - Ordering of booleans: NULL.
  - Ordering of strings: by Unicode code point, not locale. The text does not say.
  - Equality of arrays, for `=`: element by element. Not stated.
  - Equality of `1` and `1.0`: equal.
- The NOTE in `/req/core/relational` says boolean expressions are valid operands (`(a = 5) <> (b = 6)`), which I follow (`(2 <> 3) = true`).

### C4. `in`
- `/req/core/relational`: empty array gives false even for NULL; an array with a NULL element gives NULL unless the first operand equals another element. Clear for the cases given.
- Not stated:
  - `x in (2)` (one element in parentheses). Under the grammar, `( expression )` is tried before the array form, so the right operand is the scalar 2, not an array. I treat a scalar right operand as a one-element list.
  - NULL first operand and a non-empty array with no NULL: I return NULL ("an unknown value"). By the NOTE's logic it should be unknown. The text covers only the empty array for this case.
  - A NULL first operand when another element is... (not applicable.)
- `not in` is `not` of `in` (stated).

### C5. `between` / `not between`
- Table: "between the second and third operands (inclusively)". Not stated: low greater than high (`5 between 10 and 1`): I return false (no swapping). A NULL bound: if either comparison is false, the result is false, else NULL (three-valued `and` of `x >= lo` and `x <= hi`). Non-numeric operands: strings compare by the code-point order.

### C6. `like` / `notLike` (`/req/text-relation/like`)
- Whole string must match: "true if and only if the first operand matches the pattern". I match the whole string (anchored).
- `%` and `_` match any character including a newline. Not stated.
- Case: sensitive (no mention). NULL operands: NULL. A non-string operand: NULL.
- Backslash. The text says "a backslash (`\`) in the pattern making the character that follows it match only itself, so `'50\%'` matches `50%` and `'\\'` matches a single backslash." Open points:
  1. Whether the text literal `'50\%'` keeps the backslash. The lexer treats only `''` and `\'` as escapes in a literal, so I keep `\%` and `\\` as written. If a reader treated `\\` in a literal as one backslash, the pattern would be one backslash, which then escapes the next character. The text implies the first reading, because it shows `'\\'` as a pattern matching a single backslash.
  2. A trailing lone backslash: I treat it as matching a backslash. Not stated.
  3. A backslash before an ordinary character (`\a`): matches `a`.
- `notLike` is the negation, NULL stays NULL.

### C7. Conditional expression (`/req/conditional/*`)
- Clear: the `else` branch is taken when the condition "does not evaluate to true", so a NULL or non-boolean condition takes `elseExp`. Only one branch is evaluated (I do this; matters if the other branch has an error).
- Result type: any.

## D. Functions

### D1 (major). Wrong arity or type, unknown functions (`/req/functions/call-expressions`)
- Clear: arguments that do not match the parameters "in number or type, after these conversions" give NULL (fn-wrong-arity, fn-wrong-type, fn-standard-wrong-arity all NULL).
- Not stated:
  - An unknown function name. I return `{"error": ...}`. Alternative: NULL (the same rule: arguments cannot match any function). The README distinguishes errors where "the text says the expression is invalid or cannot be evaluated". The text does not say this for unknown names.
  - Case of function names: I accept the exact name, then fall back to a case-insensitive match. Not stated (CQL2 says function names are case-insensitive, but I did not check).
  - NULL arguments: I return NULL for every standard function (math, text, array, text relation) when any argument is NULL. Not stated.
  - `integer` for `number`: allowed, stated. `number` for `integer`: no function takes an integer parameter. The permission `/per/functions/type-casts` ("How such arguments are converted is not specified") means `pow('2', 3)` may be 8. I did not convert (NULL).

### D2 (major). `accenti` (textfn-accenti-o-stroke, -accenti, -accenti-tajik, -accenti-cyrillic-seven)
- Requirement: `/req/text-manipulation/accent-insensitize`. Words: "strips accents and folds diacritics", with a NOTE that "CQL2 does not name a folding table, so implementations can differ on individual letters".
- The NOTE names `Ø` -> `O` and `Ł` -> `L`, keeps `ß` and `Æ`, keeps Japanese dakuten, and points to `DiacriticFolding.txt` (a link; I could not open it). The two Cyrillic cases (`ҷ`, `ҳ`, `Ҹ`, `ҿ`, `Ӌ`, `ӌ`) depend on that table. Unicode does not decompose them.
- Readings: (a) apply the table, which I could not read; (b) NFD and strip only combining marks, which would make the Tajik cases false (ҷ is a different letter from ч).
- I implemented: NFD, remove combining marks except U+3099 and U+309A, plus a small hand table: Ø Ł Đ Ħ Ŧ and Cyrillic letters with a descender, bar or hook to their base letter (ҳ->х, ҷ->ч, Ҷ->Ч, Ҹ->Ч, ҿ->ҽ, Ӌ->Ч, ӌ->ч and a few others). Both Cyrillic cases then give true.
- The text names only two letters and one link, so the result for any other letter cannot be derived from the requirement. A table has to be normative or the cases cannot be expected to agree.

### D3. `casei`, `lowerCase`, `upperCase`
- `casei` is "as the CQL2 `casei` function ... differing only in letter case compare as equal". I used Unicode case folding (`casefold`), so `ß` folds to `ss`. Lowercasing would not. The text does not say which. `lowerCase` / `upperCase` use full Unicode mapping (`'ß'.upper()` is `'SS'`). Locale: none (not stated, so Turkish dotless i is not handled).
- The return value of `casei('ABC')` itself (not tested) is not defined, only the comparison property. A reader who returns the lowercase string and one who returns the folded string give different outputs, though both satisfy the requirement.

### D4. `concatenate`, `substitute`, `contains`, `startsWith`, `endsWith`
- `substitute(s, a, b)`: "occurrences of `a` replaced by `b`". I replace all non-overlapping occurrences left to right. Not stated: first only or all; empty `a` (I return `s` unchanged); overlap.
- `contains(a, '')`: true (the empty string is a substring of everything). Not stated.
- Comparisons are case sensitive and by code point.

### D5 (major). `format` (`/req/text-manipulation/format`)
- Words: "conversion specifiers of the C `printf` function (ANSI C)". Open points: which specifiers; flags and width; how the argument types match (the NOTE says arguments "match when they match the conversion specifiers"). I implemented `%d %i %u %o %x %X %c %e %E %f %g %G %s %%` with flags, width and precision, using Python `%`.
- `%d` requires an integer (a real gives NULL), `%f` requires a number (an integer is accepted), `%s` requires a string (a number gives NULL; C would not allow it either). A count mismatch gives NULL. A NULL argument gives NULL. `%5.2f` rounding follows Python (round-half-even of the exact binary value), as C does.
- Not stated: `%ld`, `%lld`, `%p`, `%n`, locale decimal separator, `%s` with a number.

### D6. Array functions (`/req/array-relations/*`)
- `a_equals`: ordered. The requirement text says "the same number of elements and each element of `a` is equal to the element of `b` at the same position", so a_equals((1,2),(2,1)) is false. A TODO comment in the source says CQL2 evaluates arrays as sets and CartoSym has not settled which. I followed the requirement text.
- Not stated: duplicates (`a_contains((1,1),(1))` true under the "every element" wording), empty arrays (`a_containedBy((), x)` true, `a_overlaps((), x)` false), NULL elements inside arrays (I ignore NULLs when searching and never match NULL to NULL), nested arrays (compared element by element), and `1` against `1.0` (equal).

### D7. Variables (`/req/variables/*`)
- Clear: an application can override a defined variable, and a reference resolves to the "current value".
- Not stated:
  - An undefined variable: `{"error": ...}`. Alternative: NULL.
  - Whether an overriding value is a literal or an expression. I evaluate it as an expression (a plain value stays a value).
  - Dependencies: if `double` is defined as `@base * 2` and the application overrides `base`, `double` uses the overridden `base`. I resolve references at use, so yes. The text says "current value of the referenced variable", which supports this.
  - A cycle (a variable defined in terms of itself): error.
  - Whether the override can name a variable that is not defined (I allow it).
  - In text, variables are only defined with `@name = expression;` before the rules. In my expression cases the definitions come as JSON.

## E. Identifiers

### E1. Property not present (null-property-missing-*, `/req/core/expressions-field-identifiers`)
- Words: "resolving an Identifier Expression to the value of the named feature property". Nothing about an absent property. I return NULL. Alternative: error (an unknown field).

### E2. Quoted and unquoted `null`, `true`, `false` (null-property-named-*)
- The lexer has no keyword for them: they are `IDENTIFIER` tokens. `"null"` with double quotes is a property named null. The text-literal rule in clause 16 (Enumeration values) says: "Enumeration values ... may not be enclosed within double-quotes", and the core clause says the CSCSS example `null` is the null literal. I read unquoted `null`, `true`, `false` as literals and double-quoted ones as properties. This is also what the JSON cases show.
- Open: case. `NULL`, `True`. The lexer makes keywords like `AND`, `IN` case-insensitive but not these three. I accept any case for them (CQL2-Text booleans are case-insensitive, but I did not check).
- Also open: a property named like a unit (`m`, `em`, `pt`, `px`, `ft`, `cm`, `mm`, `pc`, `inch`) lexes as `UNIT` (it comes first in the lexer), so `[m > 1]` is a syntax error unless quoted. I did not special-case it. The text gives no guidance.

### E3. System identifier names (core-system-identifier, core-scale)
- Clause 7 lists `visualization.scaleDenominator` and `dataLayer.identifier`; the schema and the examples use `viz.sd` and `dataLayer.id`. The text never says they are aliases. I treat `visualization` = `viz`, `scaleDenominator` = `sd` and `dataLayer.identifier` = `dataLayer.id` as the same identifier. The cases use each form with the matching key in `system`, so they pass either way.
- A system identifier with no value in `system`: error. Alternative: NULL. In text, `viz.sd` is lexed as an identifier followed by `.` and a member, so I decide by the first name (`viz`, `visualization`, `dataLayer`, `feature`, `capabilities`). A property whose name begins with one of these would be read as a system identifier. The text does not say how to tell them apart.
- `capabilities.*` identifiers are not tested.

### E4. Text literal rules (clause 16, "Text literals")
- Clear: adjacent quoted parts separated by whitespace are joined with nothing between. I do this.
- Not stated: `\` followed by `'` at the end of a literal (`'a\'`): is the quote escaped or is it the closing quote? I prefer the reading that lets the literal close. `\n` and other backslash escapes are kept as two characters. `''` is one quote.

### E5. Member access and indexing in expressions
- `a.b` and `a[1]` exist in the grammar. The text says nothing about their evaluation (a NOTE in a comment says "Consider adding a member and array element access expression"). Not tested; I implemented member access on object-valued properties only and left indexing unevaluated (unknown operator, so an error).

## F. Style sheets to JSON (clause 16 and 17)

### F1. Representation of a point
- `position: 10 4` gives `{"x": 10.0, "y": 4.0}`. The schema allows an array of 2 to 3 unit values or an object with `x`, `y`. The examples in the folder use the object, with real numbers. I followed the examples. The text of clause 16/17 does not say which form is correct, and numbers could be `10` or `10.0`.
- Image `size: 6 mm 4 mm` gives `{"x":{"mm":6},"y":{"mm":4}}` (the schema allows `unitPoint` for `size`, and the schema comment says so).

### F2. Units
- `12 pt` gives `{"pt": 12}`; `12` with no unit gives `12`. The unit-less value is not converted to `{"px": 12}` even though clause 16 says the default for screen-space objects is pixels. I kept the plain number (the examples do so for Dot sizes).

### F3. Partial update `size.x: 6 mm` (cscss-image-size-x)
- `/req/json/partial-update` and the example in clause 17 (`fill.color.r: 100`) give `{"alter": true, ...}`. For `size.x` inside the new `Image {...}` I produce `{"alter": true, "x": {"mm": 6}}`. Readings: (a) that; (b) `{"x": {"mm": 6}}` without `alter` because it is inside a new instance, where nothing is inherited. I chose (a), following the one example. The default for Image `size` is the image's own size, which makes alter meaningful, but the text does not say.

### F4. Other conversion choices
- Short-hand selectors become `{"op":"=","args":[{"sysId":"dataLayer.id"},"Huts"]}`, as in the examples. This is not tested by the cases, since all `at` pointers go into symbolizers.
- An instance without a class (`marker: { elements: ... }`) has no `type`. An instance with a class gets `"type"`. Bare identifiers in value position become `{"property": name}` (the enumeration rule needs the property's expected type, which I do not model).
- Clause 16 says a style sheet may have a trailing `;` after the last property; the grammar allows `Dot { position: 10 4; size: 6 }` without one. I accept both.
- Style validity beyond the grammar (unknown property names, wrong value types) is not checked. I only return an error for syntax errors and for the tuple-size case in A2.

## G. Other points where the text and grammar disagree or are silent

- `/req/core/relational` lists the `is` operator as "Only used with `null` literal". I return a syntax error for `a is 5`.
- Clause 14 uses `div` and `%`; the JSON schema `numericOperators` list `div` and `%` too. The JSON encoding has no operator named `intDiv` or `mod`, so the table of operator names (`intDiv`, `mod`) does not match the encoded names. I used the encoded names (`div`, `%`).
- `/req/core/time` mentions `visualization.timeInterval`; clause 7 lists no such identifier in the diagram. Not tested.
- The grammar allows `=` between `betweenBound`s only with arithmetic; `x between 1 and 10 and y > 2` parses as `(x between 1 and 10) and (y > 2)`. I rely on the comment in the grammar.

## Files read outside this folder

none
