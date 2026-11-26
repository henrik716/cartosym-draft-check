# Notes: where the text does not settle the result

I evaluated 177 cases (159 expressions, 18 style sheets). The evaluator is in `evaluator/`, run with `uv run --no-project python -I evaluator/run.py`, and it writes `results.json`. For the 103 expression cases that have a `cql2_json`, I also parsed the `cql2_text` with my own parser. Each one produced exactly the given `cql2_json` and the same result, so none of the points below comes from a text/JSON mismatch in the cases. For each point I give the requirement, the words that leave it open, the readings, what I implemented, and the words I relied on. The ten most important points come first.

---

## 1. Unary minus binds tighter than `^`, so `-2 ^ 2` is 4

- **Requirement:** /req/arithmetic/pow, /req/core/operations
- **Cases:** minus-01 (`-2 ^ 2`), minus-02 (`- 2 ^ 2`), minus-03 (`-a ^ 2`), minus-09 (`-2 ^ 0.5`)
- **Words that leave it open:** /req/core/operations: "A Renderer SHALL support evaluating operation expressions while respecting the priority of operations." No prose says what the priority is. The only source is the order of the alternatives in the ANTLR `expression` rule, where `unaryArithmeticOperator expression` comes before `expression arithmeticOperatorExp expression`.
- **Readings:**
  - A. ANTLR 4 semantics: an alternative listed earlier binds tighter, and a prefix operator's operand is parsed at the operator's own level. So `-2 ^ 2` = `(-2) ^ 2` = 4, `-a ^ 2` = 9 (with a = 3), and `-2 ^ 0.5` = `(-2) ^ 0.5` = NULL (negative base, non-integer exponent).
  - B. Usual mathematical convention, used by Python, Fortran and most CAS tools: `^` binds tighter than unary minus. That gives -4, -9 and -1.4142135623730951.
- **Implemented:** A.
- **Relied on:** the order of the alternatives in `CartoSym-CSS-Grammar.g4`. Reading B also has a trap. The lexer turns ` -2` (with a space before it) into a single `NEGATIVE_NUMERIC_LITERAL`, so under B the same expression gives 4 or -4 depending on whether a space comes before the minus, for example in `size: -2 ^ 2` compared with `size:-2 ^ 2`. Under A the result doesn't depend on the space. minus-05 (`-(2 ^ 2)` = -4), minus-07 and minus-08 (-6) are the same under both readings. arith-int-div-negative (`-7 div 2` = -3) and arith-mod-negative (`-7 % 3` = -1) also come out the same under both.

## 2. `10 -4` as a standalone expression: a tuple, a subtraction or an error?

- **Requirement:** /req/cscss/expressions, /req/arithmetic/sub
- **Case:** minus-10 (`10 -4`)
- **Words:** clause 16: "A `-` that follows whitespace and comes directly before a number is the sign of that number, which then starts a new element of the tuple, as in CSS: `position: 10 -4` is the point (10, -4)." Against this, /req/cscss/expressions says "A Renderer SHALL support evaluating CQL2-Text expressions … used directly as a selector or symbolizer parameter value", and the NOTE in clause 16 says "A CQL2-Text expression … can therefore be used directly". In CQL2-Text, `10 -4` is a subtraction or a syntax error, never a tuple.
- **Readings:**
  - A. A tuple, so the array `[10, -4]`.
  - B. A subtraction, as a CQL2-Text reader would take it: 6.
  - C. An error, because a tuple is only defined "where a POINT is expected" and nothing is expected here.
- **Implemented:** A, giving `[10, -4]`.
- **Relied on:** the lexer token `NEGATIVE_NUMERIC_LITERAL` and the grammar's `tuple` alternative, and "A tuple must be able to replace … an array of coordinate values". The same rule changes the meaning of valid-looking CQL2-Text such as `x > 10 -4`: my parser reads it as `x > (10, -4)`, a comparison with an array, so the statement that CQL2-Text can be used directly does not fully hold.

## 3. Parentheses: grouping or a one-element array?

- **Requirement:** /req/core/operations, /req/core/arrays
- **Cases:** core-priority `(1 + 2) * 3`, core-not, core-not-in-and, null-pow-zero-negative `0 ^ (0 - 1)`, null-pow-negative-fraction, null-pow-negative-integer, minus-05, null-not, null-and-*, null-or-*, null-is-null, neq-compared-to-true, neq-not
- **Words:** grammar `expression: … | expArray | expInstance | LPAR expression RPAR …` and `expArray: … | LPAR arrayElements? RPAR`. `(1 + 2)` matches both. ANTLR resolves this ambiguity in favour of the alternative listed first, which is `expArray`. The prose only says "prioritizing operations (typically encoded using parentheses)".
- **Readings:**
  - A. Grouping: `(1 + 2) * 3` = 9.
  - B. Strictly as the grammar resolves it: `(1 + 2)` is the array `[3]`, so `[3] * 3` is a type error, `not (1 = 2)` is `not [false]`, and so on.
- **Implemented:** A. A single parenthesized expression without a comma is a group; `()` and `(a, b, …)` are arrays. Where an array is required (`x in (5)`), a single value counts as a one-element list.
- **Relied on:** /req/core/operations: "An Encoding SHALL support defining the priority of expressions using multiple operators (e.g., using parentheses: `(` `)`)". The grammar needs a disambiguating rule, such as "`(e)` with one element and no comma is a group".

## 4. `accenti`: which letters are folded

- **Requirement:** /req/text-manipulation/accent-insensitize
- **Cases:** textfn-accenti-o-stroke, textfn-accenti-tajik, textfn-accenti-cyrillic-seven (textfn-accenti `café` is clear)
- **Words:** "A Renderer SHALL support evaluating the `accenti` function as the CQL2 `accenti` function, implementing accent stripping and diacritic folding." The NOTE adds: "CQL2 does not name a folding table, so implementations can differ on individual letters. Diacritic folding also folds letters that Unicode does not decompose, such as `Ø` to `O` and `Ł` to `L`, as libCartoSym does … The closest published table is … `DiacriticFolding.txt` of Unicode Technical Report #30, a withdrawn draft". Neither table is in the folder, and "as libCartoSym does" points to an implementation I may not read.
- **Readings:**
  - A. Unicode decomposition only (NFD, drop combining marks): `Ø`, `ҷ` and the Khakassian che are unchanged. o-stroke false, tajik false, seven false.
  - B. Decomposition plus folding of every letter whose Unicode name is "<base letter> WITH <mark>" to that base letter: `Ø`→`O`, `ҷ`→`ч`, `Ҹ`→`Ч`, `ҿ`→`ҽ`, `ҳ`→`х`, but `Ӌ`/`ӌ` (CYRILLIC … KHAKASSIAN CHE, no "WITH" in the name) stay. o-stroke true, tajik true, seven false.
  - C. A real diacritic-folding table such as UTR #30, which may also map `Ӌ`→`Ч` and `ӌ`→`ч`. seven would then be true.
- **Implemented:** B, which keeps U+3099/U+309A (dakuten) as the NOTE asks.
- **Relied on:** the NOTE's "folds letters that Unicode does not decompose, such as `Ø` to `O` and `Ł` to `L`", and "letters that would need a one-to-many folding, such as `ß` and `Æ`, stay as they are". Whether a descender, a vertical stroke or the Khakassian che counts as a "diacritic" can't be decided from the text. The `textfn-accenti-cyrillic-seven` result (false) is the one I trust least.

## 5. NULL operands of comparisons, arithmetic and `like` depend on CQL2, which isn't in the folder

- **Requirement:** /req/core/operations
- **Cases:** null-arithmetic, null-equal, null-not-equal, null-compare, null-like, null-not, null-and-true, null-or-false, null-is-null, null-property-missing-compare
- **Words:** "A Renderer SHALL support evaluating operation expressions with a null operand as specified by CQL2." Only the logical operators are spelled out ("`false and null` is false, `true or null` is true, and `not null`, `true and null`, `false or null` and `null and null` are NULL"). For `=`, `<>`, `<`, `+` and `like` the folder gives no rule, only hints: "As in SQL, `5 in (1, null)` is NULL"; "An operation whose result is not defined for its operands … also evaluates to NULL"; "A `selector` evaluating to null does not evaluate to true".
- **Readings:**
  - A. SQL three-valued logic: any comparison, arithmetic or `like` with a NULL operand is NULL.
  - B. Two-valued equality (`null = 1` false, `null <> 1` true), as some JSON-based filter engines do.
  - C. An error.
- **Implemented:** A: `null + 1`, `null = 1`, `null <> 1`, `null > 1`, `null like 'a%'` and `not (null > 1)` are all NULL.
- **Relied on:** the "As in SQL" NOTE and the word "also" in the NOTE on undefined operations. The rule should be stated in the text instead of by reference, at least for `=` and `<>`.

## 6. A property the feature doesn't have

- **Requirement:** /req/core/expressions-field-identifiers (the cases are labelled /req/core/operations)
- **Cases:** null-property-missing-is-null (true), null-property-missing-compare (NULL)
- **Words:** "A Renderer SHALL support resolving an Identifier Expression to the value of the named feature property or coverage range field for the feature or coverage cell being portrayed." Nothing says what happens when there is no such property.
- **Readings:**
  - A. NULL.
  - B. An error, because the expression can't be evaluated.
  - C. The rule is skipped, by analogy with "If a custom System Identifier is used in the Selector of a Rule, the entire Rule should be ignored".
- **Implemented:** A.
- **Relied on:** nothing explicit, only the general NULL handling of /req/core/operations. This needs a sentence.

## 7. `"null"`, `"true"`, `"false"` in double quotes

- **Requirement:** /req/core/expressions-field-identifiers, /req/core/literals
- **Cases:** null-property-named-null (5), null-property-named-null-is-null (false), null-property-named-null-compare (true), null-property-named-true (false), null-property-named-false (true)
- **Words:** the lexer has no token for `null`, `true` or `false`: all three are `IDENTIFIER`s, and so are their double-quoted forms. The only rule that tells them apart is about enumerations (clause 16, Enumeration values): "Enumeration values … may not be enclosed within double-quotes. … In order to explicitly refer to the identifier, the identifier can be enclosed in double-quotes." Booleans are enumeration literals (clause 7), but the null literal is not an enumeration value.
- **Readings:**
  - A. A double-quoted name is always a property reference.
  - B. `"null"` is still the null literal, since the enumeration rule doesn't cover it.
- **Implemented:** A.
- **Relied on:** the enumeration paragraph, extended to `null`. The text also doesn't say whether a bare `true` means the boolean or a property named `true` in a context where no enumeration is expected. I took the literal.

## 8. Function arguments that don't match: NULL, error or conversion

- **Requirement:** /req/functions/call-expressions, /per/functions/type-casts
- **Cases:** fn-wrong-arity `pow(2)`, fn-wrong-type `pow('a', 2)`, fn-standard-wrong-arity `atan2(1, 1, 1)`, all NULL
- **Words:** "A Renderer SHALL evaluate a FunctionCallExpression whose arguments do not match the parameters of the Function, in number or type, after these conversions, to NULL." But /per/functions/type-casts: "A Renderer MAY convert arguments of other types to the type of the parameter … How such arguments are converted is not specified."
- **Readings:**
  - A. NULL.
  - B. An error at parse/validation time: the CartoSym-JSON schema's `functionCall` accepts any arguments, so the schema doesn't catch these.
  - C. Under the permission, a renderer may convert `'a'`, and the result is then unspecified.
- **Implemented:** A, because the SHALL is explicit. The permission still means two conforming renderers can differ on `pow('2', 2)`.

## 9. `a_equals` compares in order, but the text marks this as unsettled

- **Requirement:** /req/array-relations/a-equals
- **Case:** array-equals-order `a_equals((1, 2), (2, 1))`
- **Words:** "…true if and only if arrays `a` and `b` have the same number of elements and each element of `a` is equal to the element of `b` at the same position." Right after it: "TODO(review): this compares in order, as libCartoSym does, while CQL2 Requirement 16 B evaluates arrays as sets … which one CartoSym follows is not settled".
- **Readings:**
  - A. Ordered: false.
  - B. As sets, following CQL2: true.
- **Implemented:** A, following the normative text. The result changes if the TODO is resolved the other way.

## 10. CSS to JSON: how a tuple is encoded (`position`, Image `size`)

- **Requirement:** /req/cscss/expressions, /req/vector/graphics, /req/vector/image
- **Cases:** cscss-tuple, cscss-tuple-negative, css-03, css-05 (position); cscss-image-size-tuple; cscss-image-size-x
- **Words:** no clause gives the mapping from CartoSym-CSS to CartoSym-JSON. The schema's `unitPoint` allows both an array (`minItems 2`) and an object `{x, y, z}`. The examples use both forms: every `position` is `{"x": 10.0, "y": -4.0}`, while `hotSpot: 50 pc 100 pc` becomes `[{"pc": 50}, {"pc": 100}]`.
- **Readings for `position: 10 4`:**
  - A. `{"x": 10, "y": 4}`.
  - B. `[10, 4]`.
- **Readings for `size: 6 mm 4 mm`:**
  - A. `[{"mm": 6}, {"mm": 4}]`.
  - B. `{"x": {"mm": 6}, "y": {"mm": 4}}`.
- **Readings for `size.x: 6 mm` inside a new `Image { … }`:**
  - A. `{"x": {"mm": 6}}`.
  - B. `{"alter": true, "x": {"mm": 6}}`, which is the form used for a member assignment in a styling rule (core-selector example: `fill.color` becomes `"fill": {"alter": true, …}`).
- **Implemented:** position as an object; uom-qualified size tuples as an array, like `hotSpot`; `size.x` without `alter`, because the instance is new and the schema comment on Image `size` says "a point sets the width (x) and the height (y), either of which can be left out".
- **Relied on:** the paired examples. The examples write `10.0` where the CSS has `10`. In JSON these are the same number, and I output `10`.

---

## Other points

### 11. `position: 10 - 4` and `position: 10-4` (a number where a point is expected)

- **Requirement:** /req/cscss/expressions, /req/core/parameters, /req/parameter-values/expressions
- **Cases:** css-01, css-02
- **Words:** clause 16: "With whitespace after the `-` … or none before it … the `-` is a subtraction." /req/core/parameters: "only Literal Expressions compatible with the expected data type are allowed as Parameter Values"; /req/parameter-values/expressions: "resolving the result to the data type expected by the Symbolizer property". Nothing says how a number resolves to a UnitPoint. The schema's `unitPoint` allows an expression object only through `idOrFnExpression`, which rejects the numeric operators.
- **Readings:**
  - A. The expression itself: `{"op": "-", "args": [10, 4]}`. It is a faithful translation, but invalid under the schema.
  - B. A folded value of 6, which still isn't a point.
  - C. An error.
- **Implemented:** A.

### 12. A tuple where a single value is expected

- **Requirement:** /req/cscss/expressions, /req/vector/dot
- **Case:** css-04 (`Dot { size: 10 -4 }`)
- **Words:** "A tuple must be able to replace either: an array of coordinate values, an instance of a class defining a single property being such an array (e.g., Point), or a class identified as being replaceable by a tuple." Dot `size` is a single uom-qualified value.
- **Readings:**
  - A. An error.
  - B. `[10, -4]`, accepted by the grammar but invalid under the schema.
  - C. A subtraction, 6, as a reader who expects a number might take it.
- **Implemented:** A.

### 13. `position: 10 (-4)`

- **Requirement:** /req/cscss/expressions
- **Case:** css-06
- **Words:** grammar `tuple: idOrConstant idOrConstant | tuple idOrConstant`; clause 16: "The element of tuples can be either numeric literals or identifiers."
- **Readings:**
  - A. A syntax error.
  - B. The point (10, -4), if an implementation allowed parenthesized tuple elements.
- **Implemented:** A.

### 14. Unary minus and the NULL literal have no CartoSym-JSON encoding in these positions

- **Requirement:** /req/json/expressions
- **Cases:** minus-03, minus-05, minus-07, minus-08 (text only); null-arithmetic, null-equal, null-not-equal, null-compare, null-like, null-in-null-element (given `cql2_json`)
- **Words:** the schema's `numericOperators` has no negation, and `arithmeticOperands` requires exactly 2 items. `numericPrimary`, `scalarExpression` and `isLikeOperands` don't admit `null`. So `-a` can only be written as `0 - a` or `-1 * a`, and the given `{"op": "+", "args": [null, 1]}` doesn't validate.
- **Implemented:** inside the evaluator I use a one-argument `"-"`, and I evaluate the schema-invalid JSON anyway. A producer following /req/json/schema can't write these cases.

### 15. Names of System Identifiers: `viz.sd` vs `visualization.scaleDenominator`, `dataLayer.id` vs `dataLayer.identifier`

- **Requirement:** /req/core/scale, /req/core/expressions-system-identifiers, /req/core/layers, /req/cscss/selectors
- **Cases:** core-scale, core-system-identifier, and every style case with a layer name (`Huts`)
- **Words:** clause 7 defines `visualization.scaleDenominator` and `dataLayer.identifier`, and says "the <layerid> syntax is equivalent to [dataLayer.identifier = '<layerid>']". Its examples, all the JSON examples and the schema's `systemIdentifier` enum use `viz.sd` and `dataLayer.id`. The enum has no `visualization.*` and no `dataLayer.identifier`, so the given `{"sysId": "visualization.scaleDenominator"}` is invalid under the schema. The abbreviations are never defined.
- **Implemented:** I treat `viz`/`visualization`, `sd`/`scaleDenominator` and `id`/`identifier` as aliases when looking up values, and translate a layer name to `dataLayer.id`, as the examples do.

### 16. A unitless font size

- **Requirement:** /req/vector/fonts
- **Case:** cscss-font-size
- **Words:** "a uom-qualified `size` (in pixels when no unit is given …)". The schema's `unitValue` allows a plain number.
- **Readings:**
  - A. `12`.
  - B. `{"px": 12}`, normalized by the encoder.
- **Implemented:** A, as in the examples (`width: 0` becomes `0.0`). The other font cases (`{"pt": 12}`, `{"pt": 10}`, `{"pt": 14}`) and `{"mm": 6}` are unambiguous.

### 17. `substitute`: the first occurrence or all of them

- **Requirement:** /req/text-manipulation/substitute
- **Case:** textfn-substitute
- **Words:** the requirement says "replaces a substring with another string". The table says "`s` with occurrences of `a` replaced by `b`".
- **Readings:**
  - A. All occurrences: `a+b+c`.
  - B. Only the first: `a+b-c`.
- **Implemented:** A, from the plural "occurrences" in the table.

### 18. Backslashes in text literals

- **Requirement:** /req/text-relation/like (related: clause 16, Text literals)
- **Case:** text-like-escape (true under every reading)
- **Words:** the lexer's `ESCAPED_QUOTE : '\'\'' | '\\\''` makes `\'` an escaped quote, but no text says whether `\\` in a literal is one backslash or two. The requirement example "the pattern `'\\'` matches a single backslash" only works if literals keep both backslashes and `like` then removes one. It is also unclear whether `'\'` is a complete literal.
- **Implemented:** in a literal only `''` and `\'` are escapes. `like` treats `\` as escaping the next character.

### 19. Style cases without `at`

- **Requirement:** /req/core/relational (README task)
- **Cases:** neq-selector, neq-selector-no-spaces, neq-selector-and
- **Words:** README: "the result is the CartoSym-JSON value found at `at`". These cases have no `at`.
- **Implemented:** the whole document (the empty JSON Pointer). The selector is `{"op": "<>", "args": [{"property": "a"}, 1]}`, with or without spaces around `<>`.

### 20. Smaller gaps that don't change any case here

- **/req/arithmetic/pow:** "when … its second operand is not an integer" could mean the type (`2.0` is a `number`) or the value. I used the value.
- **/req/arithmetic/\*:** the result type of `+`, `-`, `*` and `^` on two integers is not stated (the table says `number`). `abs` returns `number`, so it could be 2 or 2.0. JSON can't tell the difference, and I output integers.
- **/req/text-manipulation/case-insensitize:** only the comparison is defined, not the string that `casei` returns. I used Unicode case folding.
- **/req/variables/definition:** when a variable is defined from another one (var-defined-by-expression) and the application overrides the base variable, the text doesn't say whether the derived one follows. I evaluate lazily, so it follows.
- **Grammar:** `Name(…)` matches both `expCall` and `expInstance`, and the call comes first, so `Color(20, 100, 80)` parses as a function call. The tokens `UNIT` (`m`, `px`, `pt`, `mm`, …) and `div` make properties with those names unreachable without double quotes. The examples in clause 7 use `opacity = 0.5;` and `{ stroke: { blue, width: 5m } }` without a final `;`, and the grammar accepts neither.

---

## Files read outside this folder

none
