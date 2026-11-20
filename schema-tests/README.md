# Schema tests

Tests for the CartoSym-JSON schemas of Part 1 (`1-core/schemas/CartoSym-JSON.schema.json`) and Part 3 (`3-geometry/schemas/CartoSym-JSON-3-geometry.schema.json`) in [opengeospatial/cartographic-symbology](https://github.com/opengeospatial/cartographic-symbology), written for the schema PR that follows the discussion on [#140](https://github.com/opengeospatial/cartographic-symbology/issues/140). Each test document is a CartoSym-JSON style with an expected outcome, valid or invalid, and is validated against both schemas with three JSON Schema validators.

## How to run

```sh
python schema-tests/fetch_cql2_examples.py              # once: the CQL2-JSON examples
python schema-tests/run.py ../cartographic-symbology    # python-jsonschema; writes schema-tests/out/
cd schema-tests/js && npm install && cd ../..
node schema-tests/js/check.mjs ../cartographic-symbology  # Ajv and Hyperjump; needs run.py's output
```

Validation time for deeply nested expressions (see [Depth](#depth)):

```sh
python schema-tests/depth.py ../cartographic-symbology --write   # python-jsonschema; writes out/depth-docs.json
node schema-tests/js/depth.mjs ../cartographic-symbology          # Ajv and Hyperjump (ALL_ERRORS=1: Ajv with allErrors)
```

`run.py` needs `jsonschema` (in this repository's environment). Each command prints the number of wrong results and exits with 1 if there are any. The schemas have no `$id`, so the runners give them a test base URI (`https://cartosym.test/`) to resolve the relative `$ref` from Part 3 to Part 1.

## Test documents

| Set | Documents | Where from | Expected |
|---|---|---|---|
| Expressions | 512 | [`cases_expressions.py`](cases_expressions.py): for each operator and function, valid uses and invalid ones (wrong number of arguments, an argument of the wrong kind, a malformed object), each put in a selector; since 2026-11-17 also array elements, operators of the wrong type inside other operations, and two expressions 16 levels deep | As written per case |
| CartoSym-JSON examples | 11 | `1-core/examples/*.cs.json` of the checkout being tested | Valid |
| CQL2-JSON examples | 109 | The examples of OGC API - Features Part 3 (CQL2), fetched by [`fetch_cql2_examples.py`](fetch_cql2_examples.py) at commit `66faf8c`, each put in a selector | Valid |
| Other changes | 82 | [`cases_other.py`](cases_other.py): the schema changes outside expressions (dot patterns, colours, value ranges, units, stroke, system identifiers), the examples of clause 16, since 2026-11-18 graphics, markers and variable references, and since 2026-11-20 `null` as a fill or stroke | As written per case |

The two sets built by code are also published as plain JSON in [`cases.json`](cases.json), so they can be used without running Python: an array with one object per document (`set`, `name`, `valid`, `part3`, `group` and `note` where they apply, `document`), one per line. `part3` is true for the documents with an `s_*` or `t_*` operation (see below). It is written by `python schema-tests/export_cases.py`, and `--check` tells whether it is up to date with the case files. Pin a commit when downloading it.

The expected outcome of each expression case was judged from the Part 1 requirements and from CQL2, counting the structure and the number of arguments. Argument types are counted only where the schema checks them, as the schema in the PR still does (whether to check the syntax only is open on #140). Questions of type conversion (#163) are left out.

The expected outcomes are those of the Part 3 schema, which includes Part 1. Part 1 does not define the spatial and temporal relations or the geometry functions, and accepts them as generic function calls, as it does any function it does not define. So for Part 1, the runners compare only the documents without an `s_*` or `t_*` operation (499 of 709).

## Validators

- **python-jsonschema** 4.26.0, with referencing 0.37.0: the validator also used by the gallery build in this repository
- **Hyperjump** 1.11.0: an implementation of the full 2020-12 specification, used to check that the results follow the specification rather than one implementation
- **Ajv** 8.17.1: the most widely used JSON Schema validator, used to check that the schemas work where most people will use them

The three validators must also agree with each other on every document; `check.mjs` counts any difference from python-jsonschema as a failure.

## Results

On the [`schema-fixes`](https://github.com/henrik716/cartographic-symbology/tree/schema-fixes) branch at 45d78d1 (2026-11-20, `null` accepted as a fill or stroke), with all three validators:
- Part 3: 0 wrong of 714
- Part 1: 0 wrong of the 504 documents without Part 3 operations
- The three validators give the same result for every document and both schemas

At 6810d14 (2026-11-18, graphics checked by their `type`, variable references) the result was 0 wrong of the 709 documents there were then. Of the 5 added on 2026-11-20, 6810d14 gets 4 wrong: it rejects `fill: null`, `stroke: null` (also a Dot's) and the base rule that unsets fill, stroke and marker.

At a709fde (2026-11-17) the result was 0 wrong of the 681 documents there were then. Of the 28 added on 2026-11-18, a709fde gets 11 wrong: it rejects the 8 valid variable references, a property as a fill pattern and an `elements` array mixing a property and a Text (both because an expression matched two alternatives of a `oneOf`), and it accepts a marker that is an invalid operation.

At 7729a1e (2026-11-14) the result was 0 wrong of the 663 documents there were then. Of the 18 added on 2026-11-17, the six valid array elements were rejected at 7729a1e, as was the property with an `op` member, and the two documents 16 levels deep were not checked there (see [Depth](#depth)).

## Depth

[`depth.py`](depth.py) and [`js/depth.mjs`](js/depth.mjs) time three selectors at depths from 1 to 16: nested `and`s with every leaf `x < 2` (valid); the same with one leaf `x < {"foo": 1}` (invalid); and a valid expression that passes through boolean, comparison, arithmetic, conditional and text operations at every level (its size grows about four times every four levels). Each validation runs in its own process with a time limit of 20 s, on one Windows PC:

| Schema | python-jsonschema | Hyperjump | Ajv |
|---|---|---|---|
| 7729a1e, nested `and` | 0.06 s at depth 1, 0.75 s at 2, 8.4 s at 3, over 20 s at 4 | 0.02 s at 1, 1.3 s at 3, 17 s at 4 | 3 ms at every depth to 8 |
| 7729a1e, invalid leaf | 2.9 s at depth 2, over 20 s at 3 | 17 s at depth 4 | 3 ms |
| 7729a1e, mixed | 10 s at depth 1, over 20 s at 2 | 12 s at depth 1 | 7–10 ms |
| By `op`, nested `and` | 13 ms at depth 16 | 9 ms at 16 | 3 ms |
| By `op`, invalid leaf | 2 ms at depth 16 | 10 ms at 16 | 2 ms |
| By `op`, mixed | 0.9 s at depth 16 (76 kB of JSON), growing with the size | 0.12 s at 16 | 17 ms |

The Part 3 schema takes about 1.5 times as long as Part 1. Listing all errors of the invalid leaf at depth 16 takes 18 ms in python-jsonschema (one error, at the path of the leaf) and under 1 ms in jsonschema-rs 0.61; Ajv with `allErrors` stays under 20 ms. Ajv is fast with either schema because it stops at the first alternative that matches; the others try each alternative, and at 7729a1e each alternative validated the arguments again, so the time grew exponentially with the depth.

The schema now checks an object with an `op` against one definition, selected by the `op` (`operation` in the Part 1 schema), and each expression type limits which operators it accepts (`booleanOperation`, `numericOperation`, `characterOperation`, `conditionalOrFunctionCall`). An object without an `op` is checked against the values that are not operations (`numericPrimary` and so on). This was proposed by kraftto on [#188](https://github.com/opengeospatial/cartographic-symbology/pull/188), who measured the exponential time on a style of 1584 rules.

On `main` (c9808c0), the Part 3 schema is not a valid schema (its `$ref` to Part 1 is inside `$defs`). Read as 2020-12, the Part 1 schema fails 10 of the 11 CartoSym-JSON examples in python-jsonschema ([#165](https://github.com/opengeospatial/cartographic-symbology/issues/165)).

## How the tests were developed

The tests were written and run by Claude Code (Anthropic), working with Henrik Schuller, between 2026-11-07 and 2026-11-18. In order:


1. Nov 7 to 12, on #140: the 11 examples, then 27 valid and 7 invalid documents, then the 494 expression cases and the 109 CQL2-JSON examples. The fixes were tested on modified copies of the schema built by a script, not on the schema files: the proposals posted on #140 were compared this way, and the last variant (J7) had 0 wrong of 614.
2. Nov 13: the J7 changes were written into the schema files on the `schema-fixes` branch, with the other changes of the PR, and the 49 cases for the other changes were added. All 663 documents were run with python-jsonschema.
3. Nov 14, a second check: Hyperjump and Ajv were added. Hyperjump agreed with python-jsonschema on every document. Ajv rejected all 11 examples, because the first version extended Part 1 through `$dynamicRef` / `$dynamicAnchor`, and Ajv falls back to the root schema when a `$dynamicRef` is reached before its `$dynamicAnchor` (which suits meta-schemas, where the anchor is at the root, but not an anchor in `$defs`). The schemas were changed to use `$ref` only (the Part 3 schema checks its operations with a walk over the whole style), which gives the same Part 1 results and 0 wrong with all three validators. The same check found `fuschia` in the CartoSym-CSS colour table as well as in the schema.
4. Nov 17, after kraftto's comment on #188: his timings were reproduced with `depth.py` and `js/depth.mjs`, the expression definitions were changed to select by `op` as he proposed, and 18 expression cases were added (array elements, operators of the wrong type inside other operations, depth). With the earlier oneOf, a property, system identifier, function call or conditional in an array literal matched more than one type and was rejected; this is now accepted, as in CQL2.
5. Nov 18, after kraftto's second comment on #188 (errors inside a graphic reported at the marker, and variable references not accepted): graphics are now checked against one definition, selected by their `type` (or by `elements` for a MultiGraphic, or as an expression), markers by whether they have `elements`, and a variable reference (`{ "$ref": "#/$variables/…" }`, clause 16) is accepted wherever an expression is, as `/req/variables/expression` says. 28 cases were added. An error inside a Text in a marker is now reported at its own path (`marker/elements/0/text/args/0`) instead of at `marker/elements`. The 95 styles of the document figures in #192 stay valid, and the depth timings do not change.

## Limits

- The expected outcomes were set by Claude Code from the requirement text and CQL2; they have not been reviewed by the SWG. A wrong expectation shows up as a wrong result only if the schema disagrees with it.
- The tests check which documents a schema accepts, not what a style means or how it renders; that is what the test harness and the gallery of this repository are for.
- Some checks follow CQL2 exactly: a timestamp needs the `Z`, and the date pattern does not check that the month or day exists (`2020-13-45` passes).
