# Live smoke test and publication review

On 9 September 2026, the two-question OpenRouter smoke test completed all
**18 requests without retries**: 8 fresh answers, 8 pointwise scores and 2
four-answer rankings. Every completion ended naturally, every judgment passed
the local schema validator, and both model/provider identities matched the
pinned protocol: Qwen3.5-9B through Parasail BF16 and Mistral Small 2603 through
Mistral ZDR.

OpenRouter reported **$0.015073965** in total cost, with usage present for all
18 requests. The conservative sum reserved before dispatch was $0.0806643.
The active smoke contract capped spending at $1, below the owner's $2 limit.
An initial credential-resolution failure made no paid request; the successful
invocation explicitly supplied the requested key through the process environment.

The publication review added support for a local `openrouter_key.txt`, excluded
that filename and its backups from Git, and tested contract-before-credential
ordering, credential precedence, rejection of symlinks and secret-free errors.
Environment variables take precedence over `.env`, which takes precedence over
`openrouter_key.txt`; an invalid existing `.env` is reported instead of silently
using a different credential. The real key file remains local with owner-only
permissions. It is absent from tracked files and distribution archives.

The final offline suite passed **125 tests**. Evidence verification reconstructed
all 54 score means and 15 compression fractions exactly. The built wheel was
installed into a separate environment and verified with network, source-checkout
and credential reads blocked. Its Python source matched the live-tested source.
Revalidating the completed smoke run also passed with network and credential
reads blocked, making no further API requests.

The initial 119-test release validation remains recorded separately in
`validation.json`. Sanitized current evidence, source identities and artifact
hashes are in [smoke_validation.json](smoke_validation.json). Full request and
answer ledgers remain in the local, ignored run output; no real active contract
or credential is distributed.

After this review, the owner explicitly authorized public publication to
`TUMLegalTech/legal-context-compression-repro`. Existing component-specific
license terms remain unchanged; see
[third-party notices](../THIRD_PARTY_NOTICES.md). This smoke sample verifies
execution and output validity. It does not demonstrate compression-quality
preservation, reproduce compressor training, or establish equivalence to the
original local-model experiment.
