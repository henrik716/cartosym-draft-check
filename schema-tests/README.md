# Schema tests

Tests for the CartoSym-JSON schemas of Part 1 (`1-core/schemas/CartoSym-JSON.schema.json`) and Part 3 (`3-geometry/schemas/CartoSym-JSON-3-geometry.schema.json`) in [opengeospatial/cartographic-symbology](https://github.com/opengeospatial/cartographic-symbology), written for the schema PR that follows the discussion on [#140](https://github.com/opengeospatial/cartographic-symbology/issues/140). Each test document is a CartoSym-JSON style with an expected outcome, valid or invalid, and is validated against both schemas with three JSON Schema validators.

## How to run

```sh
python schema-tests/fetch_cql2_examples.py              # once: the CQL2-JSON examples
python schema-tests/run.py ../cartographic-symbology    # python-jsonschema; writes schema-tests/out/
cd schema-tests/js && npm install && cd ../..
node schema-tests/js/check.mjs ../cartographic-symbology  # Ajv and Hyperjump; needs run.py's output
```

`run.py` needs `jsonschema` (in this repository's environment). Each command prints the number of wrong results and exits with 1 if there are any. The schemas have no `$id`, so the runners give them a test base URI (`https://cartosym.test/`) to resolve the relative `$ref` from Part 3 to Part 1.

## Test documents

| Set | Documents | Where from | Expected |
|---|---|---|---|
| Expressions | 494 | [`cases_expressions.py`](cases_expressions.py): for each operator and function, valid uses and invalid ones (wrong number of arguments, an argument of the wrong kind, a malformed object), each put in a selector | As written per case |
| CartoSym-JSON examples | 11 | `1-core/examples/*.cs.json` of the checkout being tested | Valid |
| CQL2-JSON examples | 109 | The examples of OGC API - Features Part 3 (CQL2), fetched by [`fetch_cql2_examples.py`](fetch_cql2_examples.py) at commit `66faf8c`, each put in a selector | Valid |
| Other changes | 49 | [`cases_other.py`](cases_other.py): the schema changes outside expressions (dot patterns, colours, value ranges, units, stroke, system identifiers) and the examples of clause 16 | As written per case |

The expected outcome of each expression case was judged from the Part 1 requirements and from CQL2, counting the structure and the number of arguments. Argument types are counted only where the schema checks them, as the schema in the PR still does (whether to check the syntax only is open on #140). Questions of type conversion (#163) are left out.

The expected outcomes are those of the Part 3 schema, which includes Part 1. Part 1 does not define the spatial and temporal relations or the geometry functions, and accepts them as generic function calls, as it does any function it does not define. So for Part 1, the runners compare only the documents without an `s_*` or `t_*` operation (453 of 663).

## Validators

- **python-jsonschema** 4.26.0, with referencing 0.37.0: the validator also used by the gallery build in this repository
- **Hyperjump** 1.11.0: an implementation of the full 2020-12 specification, used to check that the results follow the specification rather than one implementation
- **Ajv** 8.17.1: the most widely used JSON Schema validator, used to check that the schemas work where most people will use them

The three validators must also agree with each other on every document; `check.mjs` counts any difference from python-jsonschema as a failure.

## Results

On the `schema-fixes` branch as of 2026-11-14 (not yet committed), with all three validators:
- Part 3: 0 wrong of 663
- Part 1: 0 wrong of the 453 documents without Part 3 operations
- The three validators give the same result for every document and both schemas

On `main` (c9808c0), the Part 3 schema is not a valid schema (its `$ref` to Part 1 is inside `$defs`). Read as 2020-12, the Part 1 schema fails 10 of the 11 CartoSym-JSON examples in python-jsonschema ([#165](https://github.com/opengeospatial/cartographic-symbology/issues/165)).

## How the tests were developed

The tests were written and run by Claude Code (Anthropic), working with Henrik Schuller, between 2026-11-07 and 2026-11-14. In order:


1. Nov 7 to 12, on #140: the 11 examples, then 27 valid and 7 invalid documents, then the 494 expression cases and the 109 CQL2-JSON examples. The fixes were tested on modified copies of the schema built by a script, not on the schema files: the proposals posted on #140 were compared this way, and the last variant (J7) had 0 wrong of 614.
2. Nov 13: the J7 changes were written into the schema files on the `schema-fixes` branch, with the other changes of the PR, and the 49 cases for the other changes were added. All 663 documents were run with python-jsonschema.
3. Nov 14, a second check: Hyperjump and Ajv were added. Hyperjump agreed with python-jsonschema on every document. Ajv rejected all 11 examples, because the first version extended Part 1 through `$dynamicRef` / `$dynamicAnchor`, and Ajv falls back to the root schema when a `$dynamicRef` is reached before its `$dynamicAnchor` (which suits meta-schemas, where the anchor is at the root, but not an anchor in `$defs`). The schemas were changed to use `$ref` only (the Part 3 schema checks its operations with a walk over the whole style), which gives the same Part 1 results and 0 wrong with all three validators. The same check found `fuschia` in the CartoSym-CSS colour table as well as in the schema.

## Limits

- The expected outcomes were set by Claude Code from the requirement text and CQL2; they have not been reviewed by the SWG. A wrong expectation shows up as a wrong result only if the schema disagrees with it.
- The tests check which documents a schema accepts, not what a style means or how it renders; that is what the test harness and the gallery of this repository are for.
- Some checks follow CQL2 exactly: a timestamp needs the `Z`, and the date pattern does not check that the month or day exists (`2020-13-45` passes).
