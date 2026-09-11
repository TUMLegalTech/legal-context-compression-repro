# Exact prompts used in the study

The links below point to the **canonical, unedited UTF-8 templates**. The hosted
runner reads the answer-generation and evaluation files directly; there is no
separate copy to keep in sync. Their original evidence paths and SHA-256 values
are recorded in [SOURCES.json](../src/legal_repro/assets/prompts/SOURCES.json).

[English reference translations](en/README.md) are available for all texts below.
The experiments and reproduction runner use the German originals; the English
versions are provided for reading and citation.

| Stage | Exact German text | English reference | Message role / purpose |
| --- | --- | --- | --- |
| Answer generation | [qa_user.txt](../src/legal_repro/assets/prompts/qa_user.txt) | [Translation](en/README.md#answer-generation) | One `user` message for every context condition |
| Pointwise scoring | [score_developer.txt](../src/legal_repro/assets/prompts/score_developer.txt), [score_user.txt](../src/legal_repro/assets/prompts/score_user.txt) | [Instructions](en/README.md#pointwise-scoring-instructions), [input](en/README.md#pointwise-scoring-input) | `system` instructions, then `user` question, Gold and one answer |
| Four-answer ranking | [rank_developer.txt](../src/legal_repro/assets/prompts/rank_developer.txt), [rank_user.txt](../src/legal_repro/assets/prompts/rank_user.txt) | [Instructions](en/README.md#four-answer-ranking-instructions), [input](en/README.md#four-answer-ranking-input) | `system` instructions, then `user` question, Gold and four blinded answers |
| Training teacher | [teacher_developer.txt](../src/legal_repro/assets/prompts/teacher_developer.txt), [teacher_user.txt](../src/legal_repro/assets/prompts/teacher_user.txt) | [Instructions](en/README.md#training-teacher-instructions), [input](en/README.md#training-teacher-input) | Original essential/supporting text-unit labeling instructions and training input template; archived for methods reference |
| Human annotation | [instructions.txt](../src/legal_repro/assets/human_evaluation/instructions.txt), [START_HERE.txt](../src/legal_repro/assets/human_evaluation/START_HERE.txt) | [Application](en/README.md#human-annotation-instructions), [ZIP](en/README.md#annotator-zip-instructions) | Exact instruction text extracted from both distributed annotator packages; ZIP instructions preserved byte-for-byte |

## Answer generation

`{context_kind}` is `gesetzestext`, `paragraphenliste`, or `kein_kontext`.
`{context}` is the frozen statutory text, an ordered compact JSON array of BGB
paragraph IDs, or `[KEIN KONTEXT BEREITGESTELLT]`, respectively. `{question}` is
the unchanged evaluation question. Gold answers are **not** supplied to the
generator. There is no task-specific generation system message.

## Pointwise scoring

The user template receives `{question}`, `{gold}` and `{answer}`. The three
dimensions are outcome, legal reasoning and legal basis correctness, each on
0–1 with at most two decimal places. Despite the historical `_developer.txt`
filename, the recorded instruction role is `system`.

## Four-answer ranking

`{candidates_json}` contains exactly four anonymized answers: one compressed
condition and the three controls. The task is a direct ranking with ties, not
a ranking derived from the pointwise scores. LLM labels (`C01`–`C04`) and human
labels (`A`–`D`) belong to separate blinding procedures.

The [message assembly](../src/legal_repro/planning.py),
[response schemas](../src/legal_repro/schemas.py), and
[recorded model/settings configuration](../src/legal_repro/assets/protocol.json)
complete the prompt specification. See [protocol differences](../docs/PROTOCOL.md)
for the hosted adaptation and retry behavior.

## Training teacher

Both teacher templates were copied byte-for-byte from the original accepted
run's `report_evidence/prompts/`, not reconstructed from a description. They
label exact text units using training questions and training reference answers.
The release reruns answer generation and evaluation on already-compressed
contexts; it does not execute teacher labeling or compressor training.

## Citing these artifacts

In the paper, link to this index and to [the human evaluation](../human_evaluation/README.md).
Use GitHub's **Copy permalink** (or press `y` on a file page) to replace `main`
with the full release commit, so the cited prompt text and annotation data stay
fixed. [CITATION.cff](../CITATION.cff) supplies the repository citation metadata.
