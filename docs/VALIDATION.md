# Release validation

Validated locally on 9 September 2026 using Python 3.12.11, uv 0.9.0,
NumPy 2.2.6, Matplotlib 3.10.0, and the committed dependency locks.

- **119 tests passed**. These cover input separation, original task geometry and
  anonymized ranking maps, strict judgment validation, request limits, retries,
  interrupted-run recovery, completion validation, human-app blinding, saving,
  import/recovery, two-annotator finalization and agreement, and figure rendering.
- Every one of the 54 original score means and 15 row-weighted compression
  fractions was reconstructed from bundled row-level evidence. All three ranking
  blocks (128 original, 398 additional, 526 combined) matched the accepted counts.
- The three plotted CSVs matched their original SHA-256 identities exactly.
  Four figures were exported as PNG, SVG and PDF using the existing style.
- A built wheel was installed into a separate Python environment under `/tmp`.
  An audit hook prohibited network access, source-checkout reads, and historical
  package/model imports. The installed package verified its evidence, rebuilt all
  figures and the 9,468-answer viewer, and generated pairwise, four-answer and
  two-annotator offline studies. There were zero attempted source reads, model
  calls, or human judgments.
- The full hosted evaluation was planned without execution: 9,468 answers,
  10,404 scores and 8,679 rankings, totaling 28,551 semantic calls.

Machine-readable evidence is in [validation.json](validation.json). Synthetic
transport tests use fake responses, are explicitly labeled, and cannot count as
live API verification. DOM checks used Node/jsdom; they are not exhaustive tests
in every real browser. The installed-wheel check was performed on Linux.

The original figure CSV identities are:

| File | SHA-256 |
| --- | --- |
| score_values.csv | `3e44c473084e039a2938b0815345d858bce057b9b48ea233ab85879ab85c7ceb` |
| reference_values.csv | `49225deb53f10c012d75b59a75e4900a7bbb820bcc6d078327911ac348fc2053` |
| ranking_values.csv | `28b8ebb534ae1bd00f0f4dcae7910d5bea0b453d3d7ee3ea8a84f429f7d14bc5` |

The environment emits 16 Matplotlib/Pyparsing deprecation warnings; they did not
affect these checks. GPU training/compression, the complete API rerun, and Windows
Python execution were not performed. Original numerical values are reproducible
from saved evidence; hosted runtime equivalence is not claimed.

Publication to the named private GitHub repository and the 18-call live OpenRouter
check remain pending approval of their exact active contracts and credentials.
The local offline result is complete; API availability listings are not a substitute
for a paid model test.

Source recheck: all 70 remaining allowlisted source files still match their export
hashes. The two original participant ZIP paths disappeared from the source
checkout after export. This release retains their byte-identical captured copies;
no historical/quarantine location was searched and no source files were moved or
deleted by the release work.
