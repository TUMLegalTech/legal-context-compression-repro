# Legal context compression: reproduction release

Reconstruct the published figures offline, or generate new answers and judgments
with **one OpenRouter API key**. The supplied Gold answers and frozen compressed
contexts are unchanged. No GPU, model weights, Docker, training, or Hugging Face
account is needed.

This release covers the completed 526-question experiment and its full-526
ranking extension. It does not retrain or rerun the compressors. An API rerun
uses hosted versions of the original model families; it does not claim the
original local model revisions, quantization, or identical answers.

## Start with the offline checks

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
these commands from this checkout. Python 3.12 and dependencies are locked.

```bash
uv sync --frozen
uv run legal-repro verify
uv run legal-repro figures --output outputs/figures-1
uv run legal-repro review --output outputs/review-1
```

Open `outputs/review-1/index.html` locally. It contains all 526 questions,
9,468 saved answers, 9,468 primary scores, 7,890 primary rankings, and separately
labeled reliability repeats. All commands above work without credentials or
model requests. Use a new output directory for each build.

The four original PNG/SVG/PDF figures are already in [figures/](figures/).
The builder reproduces the original three plotted CSVs byte-for-byte. The
numerical figures use realized original/retained token ratios; requested
1.10x/1.25x/2.00x targets remain separate. Twenty-four saved DAC question/condition
rows expand under downstream retokenization; they remain included as recorded.

## Verify the API on two questions

Use a funded **`OPENROUTER_API_KEY`**, set locally in your shell or secret manager.
Alternatively, put the single assignment `OPENROUTER_API_KEY=your-key` in the
Git-ignored `.env` in this checkout, or put the key alone in the Git-ignored
`openrouter_key.txt`. Resolution order is environment, `.env`, then
`openrouter_key.txt`. These files are read only after an active contract is
validated; keep their filesystem permissions private.
It is read only by the Python API runner and is never embedded in the offline
apps. A key spending limit of $1 also provides a provider-side billing ceiling.

Hosted mappings are `qwen/qwen3.5-9b` through `parasail/bf16` for generation and
`mistralai/mistral-small-2603` through `mistral/zdr` for evaluation. The runner
checks current endpoint availability and required parameters, disables fallback,
and stops if the pinned route or price ceiling is unavailable. See
[protocol differences](docs/PROTOCOL.md).

```bash
uv run legal-repro smoke --dry-run
uv run legal-repro contract --write contracts/local-smoke-1.txt --output-root outputs/smoke-1
```

Inspect the generated contract's exact workspace, output path, and limits.
When you authorize that run, change its single `STATUS: DRAFT` line to
`STATUS: ACTIVE`, then execute:

```bash
uv run legal-repro smoke --contract contracts/local-smoke-1.txt
```

The fixed two questions each receive uncompressed text, Legal LLMLingua-2 1.10x,
paragraph IDs, and no context: **8 answers + 8 scores + 2 rankings = 18 semantic
calls**. It permits at most 64 requests including retries, reserves a conservative
maximum $1, and stops after one hour. A 12.8 MB public tokenizer file is fetched
into the run output and verified against its pinned SHA-256; no model weights
are downloaded.

Inspect `COMPLETE.json`, `summary.json`, and the answer/score/rank JSONL files.
Requests, costs, failures, settings and source identities are retained. Successful
rows are never replaced. Resume an interrupted run within the same contract's
time limit with `--resume`; changes to code, inputs or configuration are rejected.
A completed resume validates its artifacts and makes no API calls.

This small check establishes working inference and valid evaluation output.
It cannot establish matching population scores, preservation of legal quality,
or equivalence to the original local runtime. Test fixtures are explicitly
labeled `synthetic_transport_test` and never count as a live API verification.

The [9 September 2026 live smoke check](docs/SMOKE_TEST.md) completed all 18
requests without retries, with $0.015073965 in reported API cost. The accompanying
offline suite passed 125 tests.

## Run the complete hosted evaluation

```bash
uv run legal-repro evaluate --dry-run
```

This plans 28,551 semantic calls: 9,468 new answers, 10,404 pointwise judgments
including 936 reliability repeats, and 8,679 rankings including 789 repeats.
To run it, create a separate contract with `--action evaluate`, choose an explicit
`--max-usd` budget and `--max-requests` allowance, inspect it, activate it, and
pass it to `legal-repro evaluate --contract ...`. The retry ceiling for the
complete task set is 104,736 requests. Full contracts default to a seven-day
wall-clock limit; `--max-seconds` changes that limit. Execution is sequential.
The full run also computes the original paired context-cluster contrasts using
10,000 bootstrap replicates, 100,000 sign randomizations and family-wise Holm
correction. This complete API workload is not part of release smoke verification.

## Keep the human evaluation offline

The preserved [participant ZIPs](participant_apps/) can be opened without any
installation or API key. Send only a participant ZIP, never this full repository
or an analyst directory, to an annotator. Their downloaded JSON contains their
judgments; the HTML/ZIP itself does not acquire saved annotations.

Rebuild a new pairwise study and its separate private linkage key:

```bash
uv run legal-repro expert build --output outputs/pairwise-1 --private-output outputs/pairwise-key-1 --panel pairwise
uv run legal-repro expert build --output outputs/four-1 --private-output outputs/four-key-1 --panel four-contexts --seed-from outputs/pairwise-key-1/linkage.json
uv run legal-repro expert dual-build --output outputs/dual-1 --private-output outputs/dual-key-1 --seed-from outputs/four-key-1/linkage.json
```

This samples 100 questions with a new private seed; the later commands retain
that same sample. The original distributed ZIPs remain unchanged. Their original
private keys are intentionally absent, so returns from those original ZIPs must
be linked by the original study organizer.

`legal-repro expert link --help` links a single return. `dual-join --help`
compares two final returns. The dual study preserves separate identities,
independently randomized labels, finalization locks, post-submission feedback,
and an offline organizer page. Ties, drafts, abstentions and missing returns
remain distinct. Do not count synthetic tests as human evaluations.

## Installation and validation

The source checkout plus `uv sync --frozen` is the supported locked installation.
The built wheel also includes all runtime assets and is checked from a separate
directory. Linux with Python 3.12 is the validated runtime. Participant HTML
apps are portable desktop-browser files. Browser tests use Node/jsdom and do
not establish behavior in every real browser.

```bash
npm ci --ignore-scripts --no-audit --no-fund
uv run --frozen pytest -q
uv build --wheel --out-dir outputs/wheel-1
```

`npm` is needed only for development tests. The human apps have no external
JavaScript dependencies. CI runs offline evidence and synthetic transport tests;
it never reads an API key or runs models.

See [release validation](docs/VALIDATION.md), [implementation provenance](docs/IMPLEMENTATION.md),
and [third-party notices](THIRD_PARTY_NOTICES.md). The public repository is
[`TUMLegalTech/legal-context-compression-repro`](https://github.com/TUMLegalTech/legal-context-compression-repro).
Public availability does not assign a blanket open-source license to all bundled
material; the component-specific rights and attribution notices remain applicable.
