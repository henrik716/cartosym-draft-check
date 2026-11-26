# Round C: expressions

Cases where a run's result differs from the harness's expected value, or the runs differ among themselves (probes have no expected value).
All three runs give the expected value in 143 of 161 cases.


| id | expected | c1 | c2 | c3 |
|---|---|---|---|---|
| cscss-tuple-negative | {"x": 10.0, "y": -4.0} | {"x": 10.0, "y": -4.0} | {"x": 10.0, "y": -4.0} | [10.0, -4.0] |
| cscss-tuple | {"x": 10.0, "y": 4.0} | {"x": 10.0, "y": 4.0} | {"x": 10.0, "y": 4.0} | [10.0, 4.0] |
| cscss-font-size | "12" | 12.0 | 12.0 | 12.0 |
| cscss-image-size-tuple | {"x": {"mm": 6.0}, "y": {"mm": 4.0}} | [{"mm": 6.0}, {"mm": 4.0}] | {"x": {"mm": 6.0}, "y": {"mm": 4.0}} | [{"mm": 6.0}, {"mm": 4.0}] |
| cscss-image-size-x | {"x": {"mm": 6.0}} | {"x": {"mm": 6.0}} | {"alter": true, "x": {"mm": 6.0}} | {"x": {"mm": 6.0}} |
| math-ceil-integer | "3" | 3.0 | 3.0 | 3.0 |
| math-floor-integer | "2" | 2.0 | 2.0 | 2.0 |
| math-round-integer | "3" | 3.0 | 3.0 | 3.0 |
| textfn-accenti-tajik | true | true | true | false |
| textfn-accenti-cyrillic-seven | true | false | true | false |
| textfn-upper-case | "'ABC'" | "ABC" | "ABC" | "ABC" |
| textfn-lower-case | "'abc'" | "abc" | "abc" | "abc" |
| textfn-concatenate | "'abcd'" | "abcd" | "abcd" | "abcd" |
| textfn-substitute | "'a+b+c'" | "a+b+c" | "a+b+c" | "a+b+c" |
| textfn-format | "'3 items'" | "3 items" | "3 items" | "3 items" |
| neq-selector | "valid" | {"stylingRules": [{"selector": {"op": "<>", "args": [{"prope | {"op": "<>", "args": [{"property": "a"}, 1.0]} | {"stylingRules": [{"selector": {"op": "<>", "args": [{"prope |
| neq-selector-no-spaces | "valid" | {"stylingRules": [{"selector": {"op": "<>", "args": [{"prope | {"op": "<>", "args": [{"property": "a"}, 1.0]} | {"stylingRules": [{"selector": {"op": "<>", "args": [{"prope |
| neq-selector-and | "valid" | {"stylingRules": [{"selector": {"op": "and", "args": [{"op": | {"op": "and", "args": [{"op": "<>", "args": [{"property": "a | {"stylingRules": [{"selector": {"op": "and", "args": [{"op": |
| minus-01 | (probe) | 4.0 | 4.0 | 4.0 |
| minus-02 | (probe) | 4.0 | 4.0 | 4.0 |
| minus-03 | (probe) | 9.0 | 9.0 | 9.0 |
| minus-04 | (probe) | 0.5 | 0.5 | 0.5 |
| minus-05 | (probe) | -4.0 | -4.0 | -4.0 |
| minus-06 | (probe) | 5.0 | 5.0 | 5.0 |
| minus-07 | (probe) | -6.0 | -6.0 | -6.0 |
| minus-08 | (probe) | -6.0 | -6.0 | -6.0 |
| minus-09 | (probe) | null | null | null |
| minus-10 | (probe) | [10.0, -4.0] | [10.0, -4.0] | "error" |
| css-01 | (probe) | {"op": "-", "args": [10.0, 4.0]} | {"op": "-", "args": [10.0, 4.0]} | {"op": "-", "args": [10.0, 4.0]} |
| css-02 | (probe) | {"op": "-", "args": [10.0, 4.0]} | {"op": "-", "args": [10.0, 4.0]} | {"op": "-", "args": [10.0, 4.0]} |
| css-03 | (probe) | {"x": 10.0, "y": -4.0} | {"x": 10.0, "y": -4.0} | [10.0, -4.0] |
| css-04 | (probe) | "error" | "error" | "error" |
| css-05 | (probe) | {"x": -10.0, "y": -4.0} | {"x": -10.0, "y": -4.0} | [-10.0, -4.0] |
| css-06 | (probe) | "error" | "error" | "error" |
