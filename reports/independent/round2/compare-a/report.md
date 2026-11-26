# Round A: rendering passes

Share of pixels (%) that differ clearly (a channel by more than 48). Rows: our readings of the kit (the draft's, then the variants in `passes.py`). Columns: the runs.

## case-01: passes-01-nested-override

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.0 | 0.0 |

Between runs: indep-a1–indep-a2 0.0, indep-a1–indep-a3 0.0, indep-a2–indep-a3 0.0

## case-02: passes-02-toplevel-override

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.0 | 0.0 |

Between runs: indep-a1–indep-a2 0.0, indep-a1–indep-a3 0.0, indep-a2–indep-a3 0.0

## case-03: passes-03-feature-pass

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.0 | 0.0 |

Between runs: indep-a1–indep-a2 0.1, indep-a1–indep-a3 0.1, indep-a2–indep-a3 0.0

## case-04: passes-03-feature-pass (style-wide)

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.1 | 0.1 |

Between runs: indep-a1–indep-a2 0.1, indep-a1–indep-a3 0.1, indep-a2–indep-a3 0.0

## case-05: passes-04-viz-pass

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.0 | 0.0 |

Between runs: indep-a1–indep-a2 0.1, indep-a1–indep-a3 0.1, indep-a2–indep-a3 0.0

## case-06: passes-04-viz-pass (style-wide)

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.1 | 0.1 |

Between runs: indep-a1–indep-a2 0.1, indep-a1–indep-a3 0.1, indep-a2–indep-a3 0.0

## case-07: passes-05-casing

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.0 | 0.0 |

Between runs: indep-a1–indep-a2 0.1, indep-a1–indep-a3 0.1, indep-a2–indep-a3 0.0

## case-08: passes-06-rule-without-pass

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 3.2 | 3.7 | 1.0 |

Between runs: indep-a1–indep-a2 0.5, indep-a1–indep-a3 3.3, indep-a2–indep-a3 2.8

## case-09: passes-07-feature-and-viz-pass

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 1.4 | 1.1 | 0.6 |

Between runs: indep-a1–indep-a2 0.2, indep-a1–indep-a3 0.8, indep-a2–indep-a3 0.9

## case-10: passes-08-zorder

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.0 | 0.0 |

Between runs: indep-a1–indep-a2 0.0, indep-a1–indep-a3 0.0, indep-a2–indep-a3 0.0

## case-11: passes-09-center-line

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.1 | 0.1 |

Between runs: indep-a1–indep-a2 0.0, indep-a1–indep-a3 0.0, indep-a2–indep-a3 0.0

## case-12: passes-09-center-line (style-passes)

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.1 | 0.1 |

Between runs: indep-a1–indep-a2 0.0, indep-a1–indep-a3 0.0, indep-a2–indep-a3 0.0

## case-13: passes-10-labels-pass

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 1.2 | 1.6 | 1.3 |
| Labels at the end of their pass | 0.8 | 1.3 | 0.9 |

Between runs: indep-a1–indep-a2 1.6, indep-a1–indep-a3 1.4, indep-a2–indep-a3 0.8

## case-14: passes-11-feature-pass-minus-one

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.8 | 0.2 |

Between runs: indep-a1–indep-a2 0.0, indep-a1–indep-a3 0.2, indep-a2–indep-a3 0.3

## case-15: passes-12-shared-zorder

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 0.0 | 0.4 | 0.4 |
| Each data layer complete before the next | 0.2 | 0.7 | 0.7 |

Between runs: indep-a1–indep-a2 0.5, indep-a1–indep-a3 0.4, indep-a2–indep-a3 0.9

## case-16: passes-13-translucent-passes

| reading | indep-a1 | indep-a2 | indep-a3 |
|---|---|---|---|
| draft | 3.8 | 4.1 | 0.5 |
| One group for all passes | 5.5 | 5.6 | 2.9 |
| Each stroke on its own | 3.7 | 3.9 | 0.5 |

Between runs: indep-a1–indep-a2 0.0, indep-a1–indep-a3 3.2, indep-a2–indep-a3 3.3

## case-17: passes-14-xplanung

Between runs: indep-a1–indep-a2 19.7, indep-a1–indep-a3 17.7, indep-a2–indep-a3 4.6

## case-18: label-pass

Between runs: indep-a1–indep-a2 0.9, indep-a1–indep-a3 1.0, indep-a2–indep-a3 0.4

