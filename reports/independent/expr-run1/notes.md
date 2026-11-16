# Notes: places where the text leaves the result open

Evaluator: `evaluator/cartosym_eval.py`, runner: `evaluator/run_cases.py`. It is written from `spec/1-core` only. Results for all 123 cases are in `results.json` (120 expressions, 3 style sheets). Where a case has `cql2_json`, that is what was evaluated. As a cross-check, every `cql2_text` was also parsed with our own CartoSym-CSS parser, which follows `schemas/CartoSym-CSS-Lexer.g4` and `-Grammar.g4`, and then evaluated. Every case that has both forms gives the same result from each. One caveat: `random()` (note 8) parses only because of a deviation from the grammar.

Each note gives the requirement, the words that leave the result open, the readings considered, the one implemented, and the cases affected.

## 1. NULL operands are delegated to CQL2, and CQL2 is not in the text

- Requirement: `/req/core/operations`
- Words: "A Renderer SHALL support evaluating operation expressions with a null operand as specified by CQL2."
- Why it is open: CQL2 (OGC 21-065) is only cited (clause 3, a draft URL). Its rules are not part of the text, so this part cannot be applied from the text alone. The only hint is the NOTE under `/req/core/selector`: "A `selector` evaluating to null does not evaluate to true". It implies that expressions, comparisons included, can evaluate to null.
- Readings:
  - (a) SQL-style three-valued logic: arithmetic and comparisons with a NULL operand give NULL; `and`/`or`/`not` follow Kleene logic.
  - (b) Two-valued logic: a comparison with NULL is false. This matches the "True if and only if" wording of the tables (notes 2 and 3).
  - (c) An error.
- Implemented: (a).
- Cases:
  - `null-arithmetic` = null, `null-equal` = null, `null-not-equal` = null, `null-compare` = null, `null-like` = null.
  - `null-not` = null, `null-and-true` = null, `null-and-false` = false, `null-or-true` = true, `null-or-false` = null.
  - `null-is-null` = true (the same under every reading).

## 2. The Logical Operators table is two-valued

- Requirement: `/req/core/logical` ("as defined in the Logical Operators table")
- Words:
  - `not`: "True if and only if the operand is false"
  - `and`: "True if and only if both operands are true"
  - `or`: "True if and only if either or both of the operands is true"
- Why it is open: read literally, the result is never NULL. `not (NULL)` is false (NULL is not false), `NULL and true` is false, and `NULL or false` is false. This contradicts reading (a) of note 1. The table also does not say what a non-boolean operand gives.
- Readings: the literal table (only true or false), or Kleene logic per CQL2.
- Implemented: Kleene logic (see note 1). A non-boolean operand gives NULL.
- Cases: `null-not`, `null-and-true`, `null-or-false` (the literal table would give false for all three). Also `null-and-false` and `null-or-true`, which come out the same under both readings.

## 3. Relational operators with NULL, and comparisons across types

- Requirement: `/req/core/relational`
- Words: "notEqual `<>` … The first operand is not equal to the second one". The other rows say the same kind of thing ("is equal to", "is smaller than", …).
- Why it is open:
  - Read literally, `null <> 1` is true, because NULL is not equal to 1. Read with CQL2-style three-valued logic, it is NULL.
  - The text does not say how to compare values of different types: integer with real, number with text, ordering of booleans.
  - It does not give the ordering of text for `<` and `>` (code point or collation).
- Implemented:
  - A NULL operand gives NULL.
  - Integers and reals compare numerically (`rhs-function` compares 3 with the real 5.0 returned by `abs`).
  - Text compares by code point.
  - `=` / `<>` between different types give false / true; ordering between different types gives NULL.
- Cases: `null-not-equal`, `null-equal`, `null-compare`, `rhs-function`, `neq-compared-to-true`.

## 4. Result type of integer arithmetic

- Requirements: `/req/arithmetic/add`, `/sub`, `/mul`, `/pow`
- Words: "as the sum of its two operands", "the product…", "the first operand raised to the power of the second operand".
- Why it is open: only `div` ("real-valued quotient … including when both operands are integers") and `intDiv` ("integer quotient") state their result type. Whether `1 + 2` is the integer 3 or the real 3.0 is not stated. Neither is `2 ^ 10`, nor what `^` does with a negative exponent.
- Implemented:
  - `+`, `-`, `*` on two integers give an integer.
  - `^` gives an integer when both operands are integers and the exponent is at least 0, and a real otherwise.
  - Mixed operands give a real.
- Cases (numerically the same under both readings; they differ only in JSON form, such as 3 versus 3.0): `arith-add` 3, `arith-sub` -2, `arith-mul` 12, `arith-pow` 1024, `core-priority` 9, `param-expression` 7, `core-field-identifier` 3000, `var-reference` 6, `var-override` 10, `var-defined-by-expression` 8.

## 5. Return types of math functions ("integral value" or double)

- Requirements: `/req/math/abs`, `/ceil`, `/floor`, `/max`, `/min`, `/pow`, `/sqrt`, `/log`, together with `/req/functions/call-expressions`
- Words:
  - The UML in clause 15 declares `abs(x : double) double`, `ceil(x : double) double`, `floor(x : double) double`, `max(x : double, y : double) double`, `round(x : double) long`.
  - The requirements say "the smallest integral value greater than or equal to `x`" and "the absolute value of `x`".
  - `/req/functions/call-expressions` says "converting an integer argument to a real number, where the parameter of the Function is a real number" and "resolving the expression to the value returned by the Function, of the Function's return type".
- Why it is open: `abs(-2)` could be the integer 2 or the real 2.0, and `ceil(-2.5)` could be -2 or -2.0. Only the UML gives a type; the requirement words do not.
- Implemented: the UML types. Integer arguments are converted to double, and the result is a double, except for `round`, which returns an integer.
- Cases:
  - Doubles: `math-abs` 2.0, `fn-call` 2.0, `math-ceil` -2.0, `math-ceil-integer` 3.0, `math-floor-integer` 2.0, `math-floor` -2.0, `math-max` 3.0, `math-min` 2.0, `math-pow` 8.0, `math-sqrt` 4.0, `math-log` 0.0, `math-log10` 3.0.
  - Integers: `math-round-integer` 3, `math-round-half` 3, `math-round-negative-half` -3.
- Related gap: the text gives no precision or tolerance for real results. `log10(1000)` is exactly 3.0 here, but it can come out as 2.9999999999999996 in another math library. The same applies to `asin(1)`, `atan(1)`, `atan2`, `exp(1)` and `fn-int-to-real`. The values here are IEEE doubles from the C library.

## 6. `max` with three arguments

- Requirements: `/req/math/max` with `/req/functions/call-expressions`
- Words:
  - "a call to the `max` standard function taking two numeric arguments", and the UML `max(x : double, y : double)`.
  - "A Renderer SHALL evaluate a FunctionCallExpression whose arguments do not match the parameters of the Function, in number or type, after these conversions, to NULL."
- Why it is open: read as written, `max(1, 5, 3)` gives NULL. The case id `fn-standard` suggests 5 was expected, though. The CartoSym-JSON `functionCall` def allows any number of arguments, and the NOTE says "A Function can define itself which arguments match its parameters". Nothing says that `max` defines itself as variadic.
- Readings: NULL (the text as written), or 5 (`max` is variadic).
- Implemented: NULL.
- Case: `fn-standard` = null.
- If `max` and `min` are meant to be variadic, the requirement has to say so.

## 7. Wrong argument count or type, and the type-cast permission

- Requirements: `/req/functions/call-expressions` and `/per/functions/type-casts`
- Words:
  - "... to NULL" (quoted in note 6).
  - "A Renderer MAY convert arguments of other types to the type of the parameter, as CQL2 Permission 2 … allows. How such arguments are converted is not specified."
- Why it is open:
  - `pow(2)` is NULL; the text settles it. The README allows `{"error": …}`, but the requirement says NULL explicitly, so null was used.
  - `pow('a', 2)` is not settled by the text. A renderer may cast `'a'` to a number "not specified" how. Depending on that conversion, it can give NULL, NaN, an error or some number.
- Implemented: no casts, so the result is NULL.
- Cases: `fn-wrong-arity` = null, `fn-wrong-type` = null (open because of the permission).

## 8. `random()` cannot be written as a function call in the CartoSym-CSS grammar

- Requirements: `/req/math/random` with `/req/cscss/grammar`
- Words:
  - "a call to the `random` standard function taking no argument".
  - The grammar has `expCall: IDENTIFIER LPAR arguments RPAR ;` and `arguments: expression | arguments COMMA expression;`, which needs at least one argument.
- Why it is open: `random()` does not match `expCall`. It matches only `expInstance` (`IDENTIFIER LPAR propertyAssignmentInferredList? SEMI? RPAR`), which makes it an instance of a class named `random` with no members.
- A related gap: for `f(a, b)` with positional arguments, both `expCall` and `expInstance` match (examples: `abs(-2)`, `a_equals((1, 2), (1, 2))`, `Color(20, 100, 80)`). The text does not say how a function call is told apart from an instance with positional members. ANTLR's choice of the first alternative (`expCall`) is the only thing that decides it.
- Implemented:
  - `NAME()` is treated as a zero-argument call. This deviates from the grammar.
  - `NAME(args)` is a call when it has no `member:` initializer and no `;`.
- Case: `math-random` = true. It was evaluated from the CQL2-JSON (`"args": []`); the text form agrees only because of the deviation.

## 9. `like`: no escape character, and case sensitivity

- Requirement: `/req/text-relation/like`
- Words: "where `%` in the pattern matches any sequence of zero or more characters and `_` matches exactly one character."
- Why it is open:
  - No escape character is defined, so a pattern cannot match a literal `%` or `_`. CQL2 may define one, but CQL2 is not in the text. In the CSS lexer, `\` is an escape only before a quote (`\'`), so `'50\%'` is the three characters `5 0 \` followed by `%`.
  - The text does not say whether matching is case-sensitive.
  - It does not say what a non-text operand gives.
- Readings for `'50%' like '50\%'`:
  - (a) `\` is an ordinary character. The pattern needs the prefix `50\`, so the result is false.
  - (b) `\` escapes `%`, so the result is true.
- Implemented:
  - (a), so the result is false.
  - Matching is case-sensitive.
  - A non-text operand gives NULL.
- Cases: `text-like-escape` = false. The other `like` cases (`text-like-percent` true, `text-like-underscore` true, `text-like-no-match` false, `text-not-like` true) are not affected.

## 10. Operators the CartoSym-JSON schema cannot encode

- Requirements: `/req/json/expressions`, with `/req/text-relation/not-like`, `/req/arithmetic/int-div`, `/req/arithmetic/mod` and `/req/core/relational`
- Words: "A Producer SHALL encode Selector and Symbolizer Parameter Value expressions based on the CQL2-JSON encoding, extended as specified by the JSON Schema". The text also has "TODO(review): the JSON schema has no `notLike`".
- What is missing from the schema:
  - The `arithmeticExpression` enum is only `+ - * / ^`, so `intDiv` (`div`) and `mod` (`%`) cannot be encoded.
  - There is no `notLike`, `notBetween`, `notIn` or `isNot`/`isNotNull`.
- Why it matters: how these are written in CartoSym-JSON is open. They could be `not` around the positive form, or new op names.
- Cases: no result is affected, because `arith-int-div*`, `arith-mod*`, `text-not-like`, `core-not-between` and `core-not-in` have only `cql2_text`. The CSS parser maps them to `div`, `%`, `notLike`, `notBetween` and `notIn`.

## 11. `a_equals`: ordered arrays or sets

- Requirement: `/req/array-relations/a-equals`
- Words: "the same number of elements and each element of `a` is equal to the element of `b` at the same position". The text also has "TODO(review): this compares in order …, while CQL2 Requirement 16 B evaluates arrays as sets. … which one CartoSym follows is not settled (see #154)."
- Why it is open: the requirement is clear, but the text itself says the choice is not settled. On top of that, the text does not define how elements are compared for `a_contains`, `a_containedBy` and `a_overlaps`, for example with duplicates or with integer 1 against real 1.0.
- Readings:
  - Ordered: `a_equals((1, 2), (2, 1))` is false.
  - CQL2 sets: it is true.
- Implemented:
  - Ordered, as the requirement says.
  - Membership for the other three functions, with numeric equality across integer and real.
- Cases: `array-equals-order` = false. `array-equals` true, `core-array` true, `array-contains` true, `array-contained-by` true, `array-overlaps` true and `array-overlaps-none` false are not affected.

## 12. `casei` and `accenti`: whose names count as standard functions

- Requirements: `/req/text-manipulation/case-insensitize`, `/req/text-manipulation/accent-insensitize`, `/req/functions/standard-functions`
- Words:
  - The functions are named `caseInsensitize` and `accentInsensitize`.
  - `casei` and `accenti` appear only as "equivalent to the CQL2 `CASEI` function" and "as the CQL2 `accenti` function", and as the `casei`/`accenti` defs of the JSON schema.
  - The text has "TODO(review): align the names with the CQL2 `casei` and `accenti` … (see #140)".
- Why it is open: whether `casei(...)` and `accenti(...)` are valid calls. If they are not, the text does not say what an unknown function name evaluates to (NULL or error). It also does not say whether function names are case-sensitive (CQL2 writes `CASEI`).
- Implemented:
  - `casei` and `accenti` are aliases. `/req/cscss/expressions` requires CQL2-Text expressions to be evaluated, and the JSON schema uses these names.
  - Function names are case-sensitive.
  - An unknown function gives an error.
- Cases: `textfn-casei` true, `textfn-accenti` true, `textfn-accenti-o-stroke` true. An unknown-function reading would give an error or NULL.

## 13. What string `caseInsensitize` returns

- Requirement: `/req/text-manipulation/case-insensitize`
- Words: "such that two strings differing only in letter case compare as equal once both are case-insensitized".
- Why it is open: the returned string is not specified. It could be lower case, upper case or a Unicode case fold, so only comparisons between two results are determined.
- Implemented: Unicode case folding (Python `casefold`).
- Cases: `textfn-case-insensitize` and `textfn-casei` give true under any reading. A case returning the string itself would be open.

## 14. `accentInsensitize` folding table

- Requirement: `/req/text-manipulation/accent-insensitize`
- Words:
  - "as the CQL2 `accenti` function, implementing accent stripping and diacritic folding."
  - The NOTE: "CQL2 does not name a folding table, so implementations can differ on individual letters. Diacritic folding also folds letters that Unicode does not decompose, such as `Ø` to `O` and `Ł` to `L` … `ß` and `Æ` stay as they are … dakuten and handakuten are not removed."
- Why it is open:
  - The text names only Ø and Ł. Which other undecomposable letters fold is open, for example Đ, Ħ, Ŧ, dotless ı and Ŀ.
  - Ø → O is stated only in an informative NOTE. The normative part points to CQL2, which is not in the text.
  - The text does not say whether the function also folds case.
- Implemented:
  - Canonical decomposition (NFD), then removal of combining marks other than U+3099 and U+309A, then recomposition (NFC).
  - Extra pairs: Ø→O, ø→o, Ł→L, ł→l, Đ→D, đ→d, Ħ→H, ħ→h, Ŧ→T, ŧ→t, ı→i, Ŀ→L, ŀ→l, Ɨ→I, ɨ→i, Ƶ→Z, ƶ→z.
  - No case folding.
- Cases: `textfn-accent-insensitize` true, `textfn-accenti` true (café/cafe, settled by decomposition), `textfn-accenti-o-stroke` true (Ø, settled only by the informative NOTE).

## 15. `substitute`: the first occurrence or all of them

- Requirement: `/req/text-manipulation/substitute`
- Words:
  - The requirement says "replaces a substring with another string" (singular).
  - The table says "`s` with occurrences of `a` replaced by `b`".
- Why it is open:
  - It could be the first occurrence or all of them.
  - The text does not say whether `a` is a literal string or a pattern.
  - It does not say what an empty `a` gives.
- Readings: all occurrences, `'a+b+c'`; or the first only, `'a+b-c'`.
- Implemented:
  - All occurrences, as the table says.
  - `a` is a literal string.
  - An empty `a` leaves `s` unchanged.
- Case: `textfn-substitute` = "a+b+c".

## 16. Number of `concatenate` arguments

- Requirement: `/req/text-manipulation/concatenate`
- Words:
  - The table gives "(string a, string b)".
  - The JSON schema `concatenate` def has `"minItems": 2` and no `maxItems`, so any number of arguments from two upward.
  - The requirement itself says "concatenates strings".
- Why it is open: whether `concatenate` takes more than two arguments, and what non-text arguments give.
- Implemented:
  - Exactly two arguments; anything else gives NULL, per note 6.
  - Non-text arguments give NULL; numbers are not converted.
- Case: `textfn-concatenate` = "abcd" (not affected).

## 17. Which `format` arguments match which conversion specifiers

- Requirement: `/req/text-manipulation/format`, with the NOTE under `/req/functions/call-expressions`
- Words: "conversion specifiers of the C `printf` function (ANSI C)", and "The arguments of `format` match when they match the conversion specifiers of its format string."
- Why it is open: the text does not say whether an integer matches `%f`, whether a real matches `%d` (undefined behaviour in C), or whether a number matches `%s`. It also does not say what too many or too few arguments give.
- Implemented:
  - `%d`, `%i`, `%u`, `%o`, `%x`, `%X` and `%c` need an integer.
  - `%e`, `%f`, `%g` and `%a` take an integer or a real.
  - `%s` needs text.
  - Any mismatch, missing argument or extra argument gives NULL.
- Case: `textfn-format` = "3 items" (not affected).
- Related schema defect: the `format`, `substitute` and geometry defs of the JSON schema put their enum under `"name"` instead of `"op"`.

## 18. `viz.sd` and `visualization.scaleDenominator`

- Requirements: `/req/core/scale`, `/req/core/expressions-system-identifiers`, `/req/json/schema`
- Words:
  - Clause 7 defines `visualization.scaleDenominator` and the other `visualization.*` and `dataLayer.identifier` identifiers. `/req/core/scale` names `visualization.scaleDenominator`.
  - All examples use `viz.sd`, `viz.date` and `viz.pass`.
  - The JSON schema `sysId` enum lists only `viz.*` forms (`viz.sd` and so on) and `dataLayer.id`. `visualization.scaleDenominator` and `dataLayer.identifier` are not in it.
- Why it is open:
  - Nowhere does the text define `viz` as short for `visualization`, or `sd` for `scaleDenominator`. Whether both spellings are valid is open.
  - The CQL2-JSON of `core-scale` (`{"sysId": "visualization.scaleDenominator"}`) uses the name the requirement gives, but it does not validate against the schema.
  - In the table, `visualization.timeInterval` is defined as "Current visualization time of day".
- Readings: both spellings are aliases; or only one spelling is valid, which makes the other one an error or an unknown identifier.
- Implemented: aliases (`viz` = `visualization`, `viz.sd` = `visualization.scaleDenominator`, `dataLayer.id` = `dataLayer.identifier`).
- Cases: `core-system-identifier` = true, `core-scale` = 25000.

## 19. In CartoSym-CSS, a system identifier looks the same as a property path

- Requirements: `/req/core/expressions-system-identifiers`, `/req/core/expressions-field-identifiers`, `/req/cscss/grammar`
- Words: the grammar has only `IDENTIFIER` and `expression DOT IDENTIFIER` (member access).
- Why it is open: `viz.sd` parses exactly like member `sd` of a feature property `viz`. The text has no rule for when a name is a system identifier and when it is a property, or which one wins when a feature has a property called `viz`, `visualization` or `dataLayer`.
- Implemented: a dotted path whose root is `viz`, `visualization`, `dataLayer`, `capabilities` or `feature` is a system identifier. Any other name is a property.
- Case: `core-system-identifier` in its text form (it agrees with the JSON form).

## 20. `true`, `false` and `null` are not tokens of the grammar

- Requirements: `/req/core/literals`, `/req/cscss/grammar`, `/req/cscss/expressions`
- Words:
  - "A null literal represents an unset value (CSCSS example: `null`)" and "Boolean literals are a specialized type of enumeration literals which are either true or false (CSCSS example: `false`)".
  - The lexer has no keyword for them, so they lex as `IDENTIFIER`.
  - The enumeration rule says "In a context where an enumeration is expected, the enumeration value takes precedence over an identifier".
- Why it is open:
  - By the grammar, `null is null` and `(2 <> 3) = true` compare identifier expressions.
  - The precedence rule applies only "where an enumeration is expected". No type is expected for the operand of `=`, nor for a bare `true`, so a feature property named `true` or `null` could win.
  - The text does not say whether the literals are case-insensitive, as CQL2 keywords are.
- Implemented:
  - Unquoted `true`, `false` and `null` are always literals, in any letter case.
  - `"true"` in double quotes is an identifier.
- Cases: `core-is-null` (text only) = true; `core-literal-boolean` and `neq-compared-to-true` in their text forms.
- Related grammar gap: the grammar's `IS` accepts any right-hand expression, although the table says "Only used with `null` literal for second operand". The text does not say what `x is 3` means. Our parser rejects it.

## 21. Unary minus is not defined

- Requirements: `/req/core/operations`, `/req/arithmetic/*`
- Words: the grammar has `unaryArithmeticOperator: PLUS | MINUS` and no negative numeric literal. The model's `ArithmeticOperator` enum is add, sub, mul, div, intDiv, mod and pow, with no negation. `OperationExpression.operand1` has multiplicity 0..1, which allows unary operators, but none is defined for arithmetic.
- Why it is open: so `-7`, `abs(-2)` and `atan2(1, -1)` in CartoSym-CSS use an operator with no stated meaning. The text also does not say which requirements class a renderer needs to read a negative number: Core, or Arithmetic.
- Implemented:
  - Unary minus is negation, applied directly to a numeric literal.
  - By the grammar's precedence, `-7 div 2` is `(-7) div 2`.
- Cases: `arith-int-div-negative` = -3 and `arith-mod-negative` = -1 (the same under either grouping, because of truncation toward zero and the sign rule). Also `arith-sub` (binary minus), and the text forms of `fn-call`, `rhs-function` and `math-atan2`.

## 22. Operator precedence and associativity exist only in the ANTLR grammar

- Requirement: `/req/core/operations`
- Words: "A Renderer SHALL support evaluating operation expressions while respecting the priority of operations."
- Why it is open: no priority table is given. The order of the alternatives in `expression` decides it:
  - All relational operators (`=`, `<>`, `<`, `in`, `is`, `like`, …) share one level.
  - `^` is left-associative, so `2 ^ 3 ^ 2` = 64, not 512.
  - Unary minus binds tighter than `^`, so `-2 ^ 2` = 4, not -4.
  - `not` binds looser than comparisons.
- Implemented: the ANTLR order.
- Cases: none affected. `core-priority` uses parentheses, and `param-expression` and `neq-arithmetic` follow the usual order.

## 23. `(x)`: a parenthesised expression or an array of one element

- Requirements: `/req/core/arrays` and the grammar
- Words: `(1)` matches both `LPAR expression RPAR` and `expArray: LPAR arrayElements RPAR`.
- Why it is open: so `x in (1)` cannot be read with certainty.
- Implemented: a parenthesised expression.
- Cases: none affected.

## 24. Variables defined by expressions, and run-time overrides

- Requirements: `/req/variables/definition`, `/req/variables/expression`, `/req/json/variables`
- Words: "resolving a VariableExpression to the current value of the referenced variable", and "allowing an application to override the value of a defined variable at run time".
- Why it is open:
  - The text does not say when a variable defined by an expression is evaluated: once when the style is loaded, or for each feature. This matters for expressions with properties or `random()`.
  - It does not say whether overriding `base` changes a variable defined from `@base`.
  - It does not say whether an override may change the type of the value.
  - In CartoSym-JSON, `{"$ref": "#/$variables/x"}` is a JSON Pointer, which resolves to the stored JSON value, not to a "current value" set by the application.
- Implemented:
  - Variables are evaluated when they are referenced.
  - A run-time override replaces the value.
- Cases: `var-reference` = 6, `var-override` = 10, `var-defined-by-expression` = 8. They are not affected, but a case with an override of `base` would be open.

## 25. CQL2-JSON with a null literal does not validate against the schema

- Requirements: `/req/core/literals`, `/req/json/schema`
- Words: `arithmeticOperands`, `scalarExpression`, `characterExpression` and `isLikeOperands` have no `null` type; only `anyExpression` has one.
- Why it is open:
  - `{"op": "+", "args": [null, 1]}`, `{"op": "=", "args": [null, 1]}`, `{"op": ">", "args": [null, 1]}` and `{"op": "like", "args": [null, "a%"]}` are not valid CartoSym-JSON, although `/req/core/literals` requires null literals.
  - `/req/json/schema` binds only Producers, so the text does not say whether a Consumer must reject these expressions or evaluate them.
  - Likewise, `{"sysId": "visualization.scaleDenominator"}` is outside the `sysId` enum (note 18).
- Readings: invalid (an error), or evaluate the null literal.
- Implemented: evaluate.
- Cases: all 11 `null-*` cases (each contains a null operand in an arithmetic, comparison or `like` position), and also `core-scale`.

## 26. Style sheets: what the three cases test is settled; related gaps in the grammar

- Requirements: `/req/cscss/grammar`, `/req/core/relational`
- Cases: `neq-selector`, `neq-selector-no-spaces` and `neq-selector-and` are all valid.
  - `a<>1` lexes as `<>`, because ANTLR takes the longest match (`NEQ` against `LT`).
  - Each rule ends its assignment with `;`, as `(propertyAssignmentList SEMI)?` requires.
- Gaps found while checking, which no case tests:
  - The grammar requires a `;` after the last assignment of a rule. The clause 7 example `[viz.sd < 10000] { stroke: { blue, width: 5m } }` lacks it, so it is invalid by the grammar.
  - The clause 7 examples `opacity = 0.5;` and `zOrder = 1;` use `=`, which the grammar does not allow in a property assignment.
  - `UNIT` is defined before `IDENTIFIER`. For a tie in length, ANTLR picks the earlier rule, so the words `m`, `px`, `ft`, `pc`, `pt`, `em`, `inch`, `cm` and `mm` can never be unquoted identifiers. A property named `m` cannot be referenced without double quotes.
  - `CHARACTER_LITERAL : CHARACTER_LITERAL_PART (WS+ CHARACTER_LITERAL_PART)*` allows `'a' 'b'`, but the text does not give its value. It could be `'ab'`, as in SQL, or keep the white space. Implemented: concatenation without the white space.

## 27. Smaller gaps that no case reaches

- Requirement: `/req/core/expressions-field-identifiers`
  - Why it is open: the text does not say what a property the feature does not have gives.
  - Implemented: NULL.
- Requirements: `/req/math/*`, `/req/arithmetic/div`, `/req/arithmetic/int-div`, `/req/arithmetic/mod`
  - Why it is open: the text does not say what `log(0)`, `sqrt(-1)`, `acos(2)` or division by zero give.
  - Implemented: NULL.
- Requirement: `/req/core/relational`
  - Why it is open: the text does not say what `in` and `between` give when NULL is among the elements or bounds, nor what `in` gives with an empty array.
  - Implemented: Kleene logic; an empty array gives false.
- Requirement: `/req/math/random`
  - Why it is open: "pseudo-random" does not say whether two calls in the same expression are independent.
  - Implemented: independent. `math-random` is true either way.
