# Implementation and provenance

Objective: let an independent tester reconstruct the four original figures and
exercise fresh answer generation plus independent judging with one API key.
Compression itself is frozen. Success of the small API check concerns transport,
input/output identity, natural completion and schema validity, not answer quality.

The source was the current uncommitted `ma_contextcompression_minimal` checkout,
Git base `8e293f99c7973dfe3d9d3637ede8f2af30434603`. Its accepted parent and
ranking-extension evidence were verified read-only before export. The packaged
`provenance.json` records exact source hashes, original export hashes and accepted
evidence bindings. Later portability changes are identified by this repository's
own source revision; original accepted manifests were not altered.
The score validator additionally rejects non-string explanations instead of
coercing them to strings, matching its existing JSON schema. Metric definitions,
precision and allowed score ranges are unchanged.

Reused components: exact prompts, context renderer, strict JSON parsers, rank
blinding/seed functions, context-cluster statistical kernels, plotting geometry
and shared typography, offline review assembler, and human-study logic/assets.
Portability changes replace local absolute paths, remove local-server/tokenizer
cache requirements, and permit fresh outputs outside package resources. The
OpenRouter transport and independent run ledgers are new. Their model revision
fields do not inherit unverifiable local revision claims.

The compressed input bundle retains question IDs, unchanged Gold, context-cluster
membership, deduplicated context text, typed paragraph-ID lists, frozen
compression metadata, and original task/repeat selections. Archived answers,
scores and rankings live in a separate reference bundle. Generation never loads
that bundle. All paper means and block-specific ranking counts are independently
recomputed before figure building; the frozen companion confidence-interval CSV
is preserved. New full API runs use the original statistical kernels and counts.

The participant ZIPs are byte-identical copies of the two distributed originals.
New studies generate fresh private keys. Private linkage keys are not published.
The owner's 11 September addition publishes an anonymous scientific subset of
both finalized human returns; the original exports and study keys stay local.
The existing two-reviewer extension is retained,
including its synthetic completion/organizer tests.

The release intentionally excludes compressor implementations, training data,
weights, model-serving code, operational logs, active source contracts, and the
separate campaign24 study. It is a frozen-compression evaluation release rather
than a source-level reproduction of compressor training.

Maintainer export tools read an explicit allowlist; normal release commands and
installed-wheel validation have no dependency on the source checkout. Re-export
only into a fresh scaffold, then review all differences before resealing assets.

## Human judgments and prompt references

The addition binds 200 returned judgments to the same 100 questions and four
answer conditions using exact question/Gold/answer-text matches. Export rejects
missing or ambiguous matches, altered distributed packets, unfinished returns
and mismatched LLM feedback. All scientific response fields are preserved;
timestamps and internal submission identifiers are omitted. The original
browser feedback is independently recomputed and checked during export.

The public analysis reuses the study's tie validation, occupied midranks and
question-weighted agreement calculations. It retains ungradable cases in the
data and uses the appropriate complete-case denominator for each comparison.
Success requires the published CSV, HTML and summary to rebuild identically,
the original evaluation/figure evidence to remain unchanged, and the installed
wheel to work without the source checkout, credentials or network.

The top-level prompt index links to the five existing runtime prompt files and
two teacher templates copied from the accepted original evidence. Their bytes
and source paths are recorded separately in `assets/prompts/SOURCES.json`;
the teacher is documented but is not added to hosted execution.
