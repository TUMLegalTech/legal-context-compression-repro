# Release validation

## Minimal publication cleanup: 11 September 2026

- **145 tests passed**, including 11 new cases for API contracts without GitHub
  fields, legacy contract metadata and resume behavior, rejection before credential
  access, and unchanged restrictions on the legacy private-publication action.
- A wheel installed with the locked runtime dependencies rebuilt all four figures,
  the 9,468-answer viewer and the human reports with network and source-checkout
  access blocked. The three plotted CSVs and the published human HTML/CSV/JSON
  rebuilt byte-for-byte. No model requests or source reads were attempted.
- All **32 original packaged assets** and all 60 protected evidence/reference files
  remain unchanged, including `prompts/en/README.md` and the original figures.
- Both API dry runs and the documented contract options passed with credential
  and network access blocked. Generated validation contracts remained inactive.
  Task counts remain 18 for the smoke and 28,551 for the full evaluation.
- The README has 115 lines, with complete clone/setup and API execution examples.
  Local documentation links, heading anchors and Bash syntax were checked.
  Citation metadata passed the official CFF 1.2.0 schema. The MIT code license and
  third-party notices were verified inside the wheel; attribution remains provisional.

See [cleanup_validation.json](cleanup_validation.json) for the validation receipt.
This is an offline release check, with no new paid smoke or full API evaluation.
Historical receipts below describe their original revisions and remain unchanged.

## Annotator and prompt addition: 11 September 2026

- **134 tests passed**, including an independent check that text-based annotation
  alignment gives the same results as the original private-key join on synthetic
  fixtures, tie/abstention handling, rejected ambiguous matches and safe HTML export.
- Both real final returns match their distributed packets. The published subset
  retains all 200 judgments over 100 questions (90 context clusters): 196 ranked
  judgments and four ungradable judgments, with 96 jointly ranked questions.
  Each annotator's cached LLM agreement was recomputed from the frozen answers.
- The public HTML, 200-row CSV and JSON summary rebuild byte-for-byte from the
  packaged annotation data. Seven prompt templates match their recorded original
  evidence hashes. The five previously released runtime prompts are unchanged.
- All **26 original packaged evidence assets** remain byte-identical. The current
  manifest adds six assets: three annotation/instruction files, two teacher
  templates and the prompt-source record.
- The wheel was installed into a fresh Python 3.12.11 environment. The acceptance
  check blocked network access, both source-code trees and local key-file paths;
  it rebuilt the figures, saved-answer viewer, human analysis and synthetic study
  apps with zero attempted source reads and zero model requests. Hosted task
  counts remain unchanged.

See [annotation_validation.json](annotation_validation.json) for the compact
validation receipt. These are offline checks; no new hosted model test or full
API evaluation was run for this addition.

## Initial release and hosted smoke

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

The release was published to the private
[`mpriorust/legal-context-compression-repro`](https://github.com/mpriorust/legal-context-compression-repro)
repository on 9 September 2026. A fresh GitHub clone verified the bundled evidence,
and [GitHub's offline workflow](https://github.com/mpriorust/legal-context-compression-repro/actions/runs/34337251444)
passed for the initial code release, `078c36dd269237fc0f313b41e52fbfd199b66b7c`.
Publication details are recorded in `validation.json`. The owner subsequently
authorized the public organization repository
[`TUMLegalTech/legal-context-compression-repro`](https://github.com/TUMLegalTech/legal-context-compression-repro).
The initial private-publication record is retained as historical validation.

The subsequent [live OpenRouter smoke check](SMOKE_TEST.md) completed on
9 September 2026: 18 requests, no retries, and $0.015073965 in reported API cost.
The updated offline suite passed 125 tests. All request costs were reported;
the conservative reservation total was $0.0806643 under a $1 contract cap.
Completed-run validation passed with both network and credential reads blocked.
The updated wheel verified its bundled evidence in an isolated environment with
source-checkout and network access blocked. These checks establish working
hosted inference and valid outputs; they do not establish population-level
quality or equivalence to the original local runtime.

Source recheck: all 70 remaining allowlisted source files still match their export
hashes. The two original participant ZIP paths disappeared from the source
checkout after export. This release retains their byte-identical captured copies;
no historical/quarantine location was searched and no source files were moved or
deleted by the release work.
