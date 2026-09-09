# Local contracts

`legal-repro contract` creates a DRAFT with a unique ID, exact workspace/output
paths, action and limits. The owner reviews those concrete fields before
activating its single STATUS line. Agent-generated drafts are never approval.

Use `local-*.txt` names; they are Git-ignored. Never commit a real active
contract, API key, original campaign contract, or local connection settings.

For an API run, only OPENROUTER_API_KEY (environment or the exact workspace's
`.env`) is used. A publication contract permits the existing local `gh` login
solely for creation/push/verification of the named private GitHub repository.
The publication helper never modifies global Git credentials or contacts GitLab.
