# API execution contracts

`legal-repro contract` writes a DRAFT with a unique ID, the exact workspace and
fresh output directory, the selected action, and dollar/request/time limits.
Inspect those fields and change the single `STATUS: DRAFT` line to
`STATUS: ACTIVE` only when you authorize that run. A generated draft is not approval.
See the [smoke and full-evaluation examples](../README.md#3-run-a-new-openrouter-evaluation).

Use `local-*.txt` contract names and `outputs/` for results; both are Git-ignored.
Keep real keys and active contracts local. API execution needs no GitHub account,
repository permissions or publication destination.

## Credentials

The sole API credential is `OPENROUTER_API_KEY`. Resolution order is:

1. The environment variable.
2. One `OPENROUTER_API_KEY=your-key` assignment in the workspace's ignored `.env`.
3. The key alone in the workspace's ignored `openrouter_key.txt`.

A malformed higher-priority value stops the run rather than falling through.
Credential files are read only after the active contract and resume identity
checks pass. Keep their filesystem permissions private. Offline verification,
figures, reports and `--dry-run` need no key and make no model requests.

## Limits and resume

The smoke action permits at most $1 in reservations, 64 requests and one hour.
Full evaluation uses your explicit `--max-usd` budget and `--max-requests` limit;
its default time limit is seven days, adjustable with `--max-seconds`.
Reservations are conservative and may stop a run before the reported cost reaches
the budget. OpenRouter's separate per-key spending limit is an additional control.

Add `--resume` to the same execution command after an interruption. Keep the
original contract, source version, inputs and output directory unchanged. A
completed resume validates existing results without another model request.

Old API contracts containing both `GITHUB_REMOTE` and `GITHUB_VISIBILITY` still
load; those fields are retained as legacy metadata and are not used for API
execution. Partial legacy field pairs and unknown fields are rejected. This
format compatibility does not relax source-version checks: historical runs
must still use the code version with which they were created.

Publication and export tools are documented under
[release maintenance](../docs/IMPLEMENTATION.md#release-maintenance).
