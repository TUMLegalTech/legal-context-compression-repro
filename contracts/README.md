# Local contracts

`legal-repro contract` creates a DRAFT with a unique ID, exact workspace/output
paths, action and limits. The owner reviews those concrete fields before
activating its single STATUS line. Agent-generated drafts are never approval.

Use `local-*.txt` names; they are Git-ignored. Never commit a real active
contract, API key, original campaign contract, or local connection settings.

For an API run, only OPENROUTER_API_KEY (environment or the exact workspace's
`.env` or `openrouter_key.txt`) is used. A publication contract permits the existing local `gh` login
solely for creation/push/verification of the named private GitHub repository.
The publication helper never modifies global Git credentials or contacts GitLab.

On 9 September 2026 the owner separately authorized public publication to
`TUMLegalTech/legal-context-compression-repro`. Public publication uses its own
exact local contract and preserves the former private origin. The API runner and
legacy private-publication helper retain their original contract format so the
completed live smoke test remains revalidatable. The legacy helper does not
publish to the organization repository.
