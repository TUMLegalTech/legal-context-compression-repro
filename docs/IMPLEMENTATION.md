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
New studies generate fresh private keys. Analyst material and actual human
judgments are not published. The existing two-reviewer extension is retained,
including its synthetic completion/organizer tests.

The release intentionally excludes compressor implementations, training data,
weights, model-serving code, operational logs, active source contracts, and the
separate campaign24 study. It is a frozen-compression evaluation release rather
than a source-level reproduction of compressor training.

Maintainer export tools read an explicit allowlist; normal release commands and
installed-wheel validation have no dependency on the source checkout. Re-export
only into a fresh scaffold, then review all differences before resealing assets.
