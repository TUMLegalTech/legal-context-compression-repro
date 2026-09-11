# Legal context compression: reproduction release

Rebuild the published results offline, or generate new answers and judgments
with **one OpenRouter API key**. This release covers 526 questions and 18 context
conditions. It uses frozen compressed contexts; compressor training and execution
are outside its scope. Hosted reruns may produce different answers from the
original local models. No GPU, model weights, Docker or Hugging Face account is needed.

## 1. View the published material

| Material | Link |
| --- | --- |
| Original figures and plotted values | [Figures](figures/) |
| Both annotators' judgments, answer texts and agreement | [Human evaluation](human_evaluation/README.md) |
| Exact German prompts used in the study | [Prompt index](prompts/README.md) |
| English prompts and annotator instructions | [English translations](prompts/en/README.md) |
| All 31 annotator notes in German and English | [Bilingual notes](human_evaluation/en/README.md) |

These files can be inspected without installation. Download/open the
[human evaluation HTML](human_evaluation/index.html) locally to browse the
100 questions and 200 judgments. For paper citations, use version `v0.1.0` or
[commit permalinks](prompts/README.md#citing-these-artifacts), with [CITATION.cff](CITATION.cff).

## 2. Rebuild the results offline

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
git clone --branch v0.1.0 https://github.com/TUMLegalTech/legal-context-compression-repro.git
cd legal-context-compression-repro
uv sync --frozen
uv run --frozen legal-repro verify
uv run --frozen legal-repro figures --output outputs/figures-1
uv run --frozen legal-repro review --output outputs/review-1
uv run --frozen legal-repro human --output outputs/human-1
```

Python 3.12 and dependencies are locked. Installation needs internet access;
the four reproduction commands need no network, credentials or model requests.
Use a new output directory each time. Linux is the validated Python runtime.

| Output | Contents |
| --- | --- |
| `outputs/figures-1/` | Four figures as PNG/SVG/PDF and three plotted CSVs matching the originals byte-for-byte |
| `outputs/review-1/index.html` | All 9,468 saved answers, 9,468 primary scores, 7,890 primary rankings and separate reliability repeats |
| `outputs/human-1/` | The human report, 200-row judgment CSV and agreement summary, matching the published files |

Open either `index.html` directly in a browser. `verify` checks the bundled
evidence and recomputes the original means, compression fractions and ranking counts.

## 3. Run a new OpenRouter evaluation

Set a funded `OPENROUTER_API_KEY` in your shell or in the ignored `.env` file
as `OPENROUTER_API_KEY=your-key`. The key is read only after contract validation
and is never embedded in the HTML reports. [Contract and credential details](contracts/README.md).
The pinned routes use Qwen3.5-9B for answers and Mistral Small for judging;
[model settings and reproduction limits](docs/PROTOCOL.md) are recorded separately.

### Start with two questions

```bash
uv run --frozen legal-repro smoke --dry-run
uv run --frozen legal-repro contract \
  --write contracts/local-smoke-1.txt --output-root outputs/smoke-1
```

Inspect the contract's paths and limits. When you authorize the run, edit its
single `STATUS: DRAFT` line to `STATUS: ACTIVE`, then run:

```bash
uv run --frozen legal-repro smoke --contract contracts/local-smoke-1.txt
```

This makes **8 answers + 8 scores + 2 rankings**, with a $1 reservation budget,
at most 64 requests including retries, and a one-hour time limit. It downloads
a pinned 12.8 MB tokenizer file, without model weights. This checks working
inference and valid output; it does not establish reproduction of answer quality.

### Evaluate all 526 questions

This plans **28,551 calls** including reliability repeats. Choose your own dollar
budget; the runner stops before a request would exceed its reservation budget. The request
ceiling below permits the existing retry policy; it is not a cost estimate.
Commands containing `read -p` use Bash.

```bash
uv run --frozen legal-repro evaluate --dry-run
read -r -p "Maximum API budget in USD: " REPRO_MAX_USD
uv run --frozen legal-repro contract --action evaluate \
  --write contracts/local-evaluate-1.txt --output-root outputs/evaluate-1 \
  --max-usd "$REPRO_MAX_USD" --max-requests 104736
```

Inspect this new contract and change its single `STATUS: DRAFT` line to
`STATUS: ACTIVE` when you authorize the run, then execute:

```bash
uv run --frozen legal-repro evaluate --contract contracts/local-evaluate-1.txt
```

Execution is sequential, with a seven-day default time limit. Successful runs
write `COMPLETE.json`, `summary.json`, `answers.jsonl`, `scores.jsonl` and
`ranks.jsonl` under the selected output root. Request/cost ledgers are retained.
Use the same command with `--resume` after an interruption, within the original
limits and with unchanged code, inputs and contract. A full hosted rerun has not
been performed for release validation; see the [completed smoke check](docs/SMOKE_TEST.md).

## Development, citation and licensing

[Validation](docs/VALIDATION.md) · [Development and maintainer tools](docs/IMPLEMENTATION.md#development-checks)
· [Create a new annotation study](docs/IMPLEMENTATION.md#create-a-new-annotation-study).
Node/npm is needed only for development tests. The paper itself is not bundled.

Original code: [MIT](LICENSE). Bundled material retains its existing terms;
see [third-party notices](THIRD_PARTY_NOTICES.md).
