# Reproduction boundary

## Original evidence

The original study used Qwen/Qwen3.5-9B at revision
`c202236235762e1c871ad0ccb60c8ee5ba337b9a` and
Mistral-Small-4-119B-2603-NVFP4 at revision
`b1a9048590131d38491bd23a7c9f6ed0962f0358`. The teacher and all compressor
training/execution are outside this release's rerun scope.

The 526 unchanged validation questions form 360 context clusters. Each has
three controls and five frozen compressors at three requested ratios. Paragraph
IDs are a privileged ground-truth control, not a retrieval system. Inputs come
from DomainLLM/gerlayqa-bgb-paraphrased, revision
`fb8038ff4d7b1caaab2b88230f7821d9e09542c4`.

Only primary pointwise replicate 1 contributes to score means. Replicate 2 on
52 original rows measures reliability. Ranking comparisons are four-way panels
with one compressed answer and the three controls. Original 128-row and later
398-row blocks are retained separately. The extension was post-results and
descriptive; it was not newly prespecified. No all-method leaderboard is inferred.

The plotted compression axis uses realized original/retained token ratios;
requested 1.10x/1.25x/2.00x targets remain separate. Twenty-four saved DAC
question/condition rows expand under downstream retokenization and remain
included as recorded. Offline reconstruction preserves the original plotted
CSVs byte-for-byte.

## Hosted adaptation

The [Qwen listing](https://openrouter.ai/qwen/qwen3.5-9b) and
[Mistral listing](https://openrouter.ai/mistralai/mistral-small-2603) establish
matching model families, not the original model-file revisions. Initial routes
are Parasail BF16 and Mistral ZDR. Mistral's hosted quantization is undisclosed
in the inspected catalog. Hosted revision fields are recorded as unknown.

Generation retains the original user prompt, temperature zero, 2,048 completion
tokens and disabled thinking. Local `chat_template_kwargs.enable_thinking=false`
is represented as OpenRouter `reasoning.enabled=false`. The original tokenizer
checks repeated eight-grams, and retries apply repetition penalty 1.1.

The independent judge retains the original system/user prompts, temperature
0.7, high reasoning, 8,192 first-attempt tokens and 16,384 retry tokens. The
adapter uses OpenRouter's reasoning object and strict JSON response format.
Provider-side schema enforcement is supplemented by the unchanged local score
and ranking parsers; invalid output is retained as a failed attempt, not repaired
or imputed. See [reasoning controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
and [structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

Semantic generation IDs and deterministic seed derivation are retained, while
every hosted run has a separate contract/output/protocol identity. The runner
retains original anonymized ranking maps and repeat membership. It never seeds
a new run with archived answers. Model/provider changes fail closed; no fallback
is selected automatically. See [provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

Local server topology, throughput profiles, latency and GPU bit equivalence do
not transfer to hosted inference. Statistical outputs remain descriptive; neither
scores nor rankings establish no-loss, non-inferiority or retained-context grounding.

## Hosted workloads

The two-question smoke uses uncompressed text, Legal LLMLingua-2 1.10x,
paragraph IDs and no context: 8 answers, 8 scores and 2 rankings. The full
526-question plan creates 9,468 answers, 10,404 pointwise judgments (936 reliability
repeats) and 8,679 rankings (789 repeats), totaling 28,551 semantic calls.
Execution is sequential; the complete retry allowance is 104,736 requests.

Full-run summaries also compute the original paired context-cluster contrasts
with 10,000 bootstrap replicates, 100,000 sign randomizations and family-wise
Holm correction. This complete hosted workload has not been run for release
validation. The [recorded live smoke check](SMOKE_TEST.md) verifies transport,
identity and output validity, without establishing population-level quality.

## Billing and recovery

The sole credential is OPENROUTER_API_KEY, from the environment or the contracted
workspace's ignored `.env` or `openrouter_key.txt`. Each request reserves a conservative
cost from UTF-8 input size, a wrapper allowance, the completion-token ceiling,
and fixed per-million-token price ceilings. Failed/uncertain requests keep their
reservation. This deliberately stops early rather than relying on missing usage
fields. Actual reported cost is recorded separately; a provider-side key spending
limit is an additional spending control. Reasoning tokens are included in
completion cost. HTTP 408/429/5xx, connection failures, truncated or invalid
completions have bounded retries; identity and authentication failures stop.

Append-only ledgers preserve accepted rows and failures. A crash with an
incomplete JSONL tail stops recovery for inspection instead of deleting data.
One process locks each output. A completed run is revalidated without inference.
