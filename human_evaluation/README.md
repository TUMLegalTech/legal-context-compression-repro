# Published annotator answers

Two finalized returns cover the same **100 questions and 400 generated answers**.
Annotator 1 supplied 99 rankings and one ungradable judgment; annotator 2 supplied
97 rankings and three ungradable judgments. All **200 judgments**, including ties,
notes, reference-answer concerns and abstentions, are retained.

- [Read the judgments as CSV](judgments.csv): 200 rows, one per annotator and question.
- [Browse all questions and answers](index.html): download/open this HTML file locally; no installation, server or key is needed.
- [Recomputed agreement](summary.json): human–human and each human–LLM comparison.
- [Canonical annotation data](../src/legal_repro/assets/human_evaluation/annotations.json): original selected ranks and labels, tied groups, notes, dispositions and answer identities.
- [Original annotator instructions](../src/legal_repro/assets/human_evaluation/instructions.txt) and [ZIP instructions](../src/legal_repro/assets/human_evaluation/START_HERE.txt).

## Reproduce the analysis

From the repository root, after `uv sync --frozen`:

```bash
uv run --frozen legal-repro human --output outputs/human-1
```

This recreates `index.html`, `judgments.csv` and `summary.json` from the bundled
annotations and frozen reference answers. It makes no model requests. The
normal `legal-repro verify` command also validates the annotation data.

## Interpretation

The four conditions are uncompressed context (`raw`), Legal LLMLingua-2 at the
requested 1.10x ratio (`legal_llmlingua2-r1p1`), paragraph IDs
(`oracle_bgb_paragraph_ids`) and no context (`no_context`). The LLM comparison
uses the saved primary four-answer ranking for this exact panel.

**Compare answer texts and conditions, not A–D labels.** Labels were independently
shuffled for each annotator. Export matched each question and Gold answer exactly,
then uniquely matched all four answer texts against the frozen results. Every
returned packet also matched its original distributed ZIP. Neither the export
nor the public analysis reads private linkage keys.

The CSV's four condition columns contain occupied **midranks**; lower is better.
For example, a tied first pair occupies positions 1 and 2, so both receive 1.5.
The original selections are preserved separately in `original_positions` and
`original_rank_groups`; they are not rewritten into competition ranks. Notes
refer to each annotator's own labels, retained in `original_labels` and shown
beside the answers in the HTML report.

Ungradable judgments have blank analytical ranks and remain in the exports.
There are **96 jointly ranked questions**. A reference-answer concern by itself
does not exclude a completed ranking. Each human–LLM comparison uses that
annotator's ranked subset (99 or 97 questions).

The focus comparison is compressed versus uncompressed: worse / tied / better.
`focus_matrix` uses that order for rows (left participant) and columns (right
participant). `focus_exact_agreement` compares this three-way preference;
`complete_ranking_agreement` requires the same ordering and ties for all four
answers. `all_pairwise_agreement` summarizes the six within-question relations;
those six pairs are not six independent observations. Results are descriptive,
without an equivalence claim or new uncertainty estimates.

## Release provenance

The canonical data is a publication subset of the two original final JSON
returns. Anonymous annotator identifiers and all scientific judgments are kept;
export/edit timestamps, browser revision counters and internal task/study IDs
are omitted. Source-return and distributed-ZIP hashes are recorded in the data.
Legal comments were reviewed and preserved verbatim. Original files are kept
unchanged by the study organizer.

[export_annotations.py](../scripts/export_annotations.py) records the export
procedure. Public analysis uses only released files and never depends on those
original local files. Use a commit permalink for paper citations, as described
in the [prompt index](../prompts/README.md#citing-these-artifacts).
