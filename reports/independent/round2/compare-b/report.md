# Round B: the text of our open PRs

Share of pixels (%) that differ clearly (a channel by more than 48); ours = the draft renderer on white, without the context layers.

| case | example | panel | ours–b1 | ours–b2 | ours–b3 | b1–b2 | b1–b3 | b2–b3 |
|---|---|---|---|---|---|---|---|---|
| case-01 | 2-vector-polygon |  | 0.0 | 0.2 | 0.1 | 0.0 | 0.0 | 0.0 |
| case-02 | 3-vector-line |  | 0.1 | 0.6 | 0.5 | 0.1 | 0.1 | 0.0 |
| case-03 | 4-vector-point |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| case-04 | requirements/font-outlines-color | color: white | 2.7 | 2.6 | 1.5 | 0.1 | 1.3 | 1.1 |
| case-05 | requirements/font-outlines-color | color: #f3e7b8 | 2.6 | 2.5 | 1.5 | 0.1 | 1.2 | 1.0 |
| case-06 | requirements/font-outlines-color | color: #e8a090 | 2.5 | 2.4 | 1.4 | 0.1 | 1.1 | 1.0 |
| case-07 | requirements/font-outlines-opacity | opacity: 0.3 | 1.2 | 1.2 | 0.4 | 0.0 | 0.7 | 0.7 |
| case-08 | requirements/font-outlines-opacity | opacity: 0.6 | 2.1 | 2.1 | 1.1 | 0.0 | 1.0 | 1.0 |
| case-09 | requirements/font-outlines-opacity | opacity: 1 | 2.7 | 2.6 | 1.5 | 0.1 | 1.3 | 1.1 |
| case-10 | requirements/font-outlines-outline | no outline | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| case-11 | requirements/font-outlines-outline | outline | 2.7 | 2.6 | 1.5 | 0.1 | 1.3 | 1.1 |
| case-12 | requirements/font-outlines-size | size: 1 | 2.1 | 2.0 | 1.3 | 0.2 | 1.0 | 0.8 |
| case-13 | requirements/font-outlines-size | size: 2 | 2.7 | 2.6 | 1.5 | 0.1 | 1.3 | 1.1 |
| case-14 | requirements/font-outlines-size | size: 3.5 | 2.9 | 2.9 | 1.6 | 0.2 | 1.5 | 1.3 |
| case-15 | requirements/labels-label | in the marker | 2.5 | 2.5 | 2.5 | 0.2 | 0.2 | 0.0 |
| case-16 | requirements/labels-label | in the label | 2.8 | 3.0 | 3.0 | 0.2 | 0.2 | 0.0 |
| case-17 | requirements/labels-line | a Text | 1.3 | 0.9 | 1.1 | 1.0 | 1.3 | 1.1 |
| case-18 | requirements/labels-line | a Dot and a Text | 1.6 | 1.1 | 1.2 | 1.2 | 1.5 | 1.2 |
| case-19 | requirements/labels-placement-priority | no priority | 7.6 | 8.6 | 5.4 | 3.2 | 4.2 | 4.0 |
| case-20 | requirements/labels-placement-priority | priority: elevation | 5.7 | 7.9 | 5.5 | 3.2 | 1.6 | 2.9 |
| case-21 | requirements/labels-placement-priority | priority: 0 - elevation | 7.9 | 9.1 | 5.5 | 3.4 | 5.0 | 3.6 |
| case-22 | requirements/labels-placement-spacing | minSpacing: 80 | 1.3 | 1.2 | 0.9 | 1.5 | 1.7 | 1.5 |
| case-23 | requirements/labels-placement-spacing | minSpacing: 150 | 0.7 | 0.5 | 0.6 | 0.7 | 0.9 | 0.7 |
| case-24 | requirements/labels-placement-spacing | minSpacing: 300 | 0.4 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| case-25 | requirements/vector-fonts | size: 9 pt | 0.0 | 0.6 | 0.6 | 0.4 | 0.4 | 0.0 |
| case-26 | requirements/vector-fonts | size: 12 pt | 0.0 | 2.2 | 2.2 | 1.9 | 1.9 | 0.0 |
| case-27 | requirements/vector-fonts | bold: true | 0.0 | 0.9 | 0.9 | 0.7 | 0.7 | 0.0 |
| case-28 | requirements/vector-fonts | italic: true | 0.0 | 0.6 | 0.6 | 0.5 | 0.5 | 0.0 |
| case-29 | requirements/vector-image | no size (own size, 24 px) | 0.1 | 0.1 | 0.1 | 0.0 | 0.0 | 0.0 |
| case-30 | requirements/vector-image | size: 10 mm | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| case-31 | requirements/vector-image | hotSpot: 0 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| case-32 | requirements/vector-image | blackTint: #3a7d44 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| case-33 | requirements/vector-text | left top (default) | 2.4 | 2.7 | 2.7 | 1.2 | 1.2 | 0.0 |
| case-34 | requirements/vector-text | center middle | 1.8 | 2.2 | 2.2 | 0.4 | 0.4 | 0.0 |
| case-35 | requirements/vector-text | right bottom | 0.0 | 1.1 | 1.1 | 1.0 | 1.0 | 0.0 |
| case-36 | requirements/vector-text | center bottom | 0.0 | 0.6 | 0.6 | 0.3 | 0.3 | 0.0 |
