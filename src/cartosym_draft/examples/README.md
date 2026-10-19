Coverage examples 5 to 9 from `1-core/examples` in opengeospatial/cartographic-symbology (PR #133 branch `requirements-placeholders`), as CS-JSON. Example 8 is the repository's own `.cs.json`; the others were converted from `.cscss` with pycartosym (`cartosym --to-format csjson`).

Example 6's `colorChannels` (`colorChannels.r: B04 / 2500` and so on) is written by hand: pycartosym (0.4.1 to 0.6.0) drops `colorChannels` when its channels are expressions.
