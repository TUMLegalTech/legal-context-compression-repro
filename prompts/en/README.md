# English reference translations

These are English translations of the seven model prompt templates and the two
annotator instruction texts in the [German originals](../README.md), as released
in commit `77365bf409fbd4c2a15cee2cfb4bb7de58872e09`.
**The study and reproduction runner use the German originals. These English
translations are for reading and citation; they were not used to produce the
reported results.**

[English translations of the annotators' free-text notes](../../human_evaluation/en/README.md)
are available separately, alongside their German originals.

Placeholders, metric names, `unit_id`, `essential` and `supporting` are preserved.
The context identifiers `gesetzestext`, `paragraphenliste` and `kein_kontext`
also retain their original spellings; they mean statutory text, a list of
section identifiers, and no context. BGB refers to the German Civil Code.
In the annotator instructions, German interface labels are retained with an
English gloss so that they can still be matched to the original application.

| Text | English section |
| --- | --- |
| Answer-generation user prompt | [Answer generation](#answer-generation) |
| Pointwise-scoring instructions | [Pointwise scoring instructions](#pointwise-scoring-instructions) |
| Pointwise-scoring user template | [Pointwise scoring input](#pointwise-scoring-input) |
| Four-answer ranking instructions | [Four-answer ranking instructions](#four-answer-ranking-instructions) |
| Four-answer ranking user template | [Four-answer ranking input](#four-answer-ranking-input) |
| Training-teacher instructions | [Training teacher instructions](#training-teacher-instructions) |
| Training-teacher user template | [Training teacher input](#training-teacher-input) |
| Annotator application instructions | [Human annotation instructions](#human-annotation-instructions) |
| Annotator ZIP instructions | [Annotator ZIP instructions](#annotator-zip-instructions) |

For a paper citation, use a commit permalink to this page and the relevant
section anchor. Suggested wording: “English reference translations of the
German prompts used in the experiments are provided in the reproduction
repository.” See the [citation guidance](../README.md#citing-these-artifacts).

## Answer generation

Original: [qa_user.txt](../../src/legal_repro/assets/prompts/qa_user.txt).
Role: `user`.

```text
Answer the legal question in accordance with the specified context type.

For the context type “gesetzestext”, the supplied statutory text is either uncompressed or compressed. Treat both forms alike and answer the legal question exclusively on the basis of this nonempty statutory text.
For the context type “paragraphenliste”, the context consists of an ordered JSON array of BGB section identifiers without the wording of the provisions. Use only these identified sections as the supplied selection of legal provisions; you may draw on the legal knowledge already contained in your model to determine their content.
For the context type “kein_kontext”, no context has been supplied. Answer the legal question using your own legal knowledge already contained in the model.

State the decisive requirements and applicable legal provisions precisely. Provide a complete but concise answer, and end after the reasoned conclusion. Do not repeat the context or points already made.

Context type:
{context_kind}

Context:
{context}

Question:
{question}
```

## Pointwise scoring instructions

Original: [score_developer.txt](../../src/legal_repro/assets/prompts/score_developer.txt).
Recorded role: `system`, despite the historical filename.

```text
You are a German legal expert evaluating exactly one anonymized answer exclusively against the supplied reference answer (Gold).

Evaluate only the legal content:
1. outcome_correctness: Is the legal outcome correct compared with Gold?
2. legal_reasoning_correctness: Are the legal reasoning and application of the law to the facts substantively consistent with Gold?
3. legal_basis_correctness: Are the legal provisions and statutory elements applied consistent with Gold?

Each score lies between 0.0 and 1.0 and has at most two decimal places. 1.0 means fully consistent with Gold; 0.0 means wholly incompatible.

Style, tone, language, length, structure and level of detail are irrelevant. Do not incorporate external knowledge or your own legal views. Deduct points for additional legal statements that Gold does not support or that contradict Gold.

Justify each score in 1–2 sentences exclusively by comparison with Gold. Do not provide a ranking or a comparison with other answers.

Output only JSON conforming to the specified schema. No additional text or reasoning traces.
```

## Pointwise scoring input

Original: [score_user.txt](../../src/legal_repro/assets/prompts/score_user.txt).
Role: `user`.

```text
Question:
{question}

Reference answer (Gold):
{gold}

Anonymized answer to be evaluated:
{answer}
```

## Four-answer ranking instructions

Original: [rank_developer.txt](../../src/legal_repro/assets/prompts/rank_developer.txt).
Recorded role: `system`, despite the historical filename.

```text
You are a German legal expert. Compare exactly four anonymized answers directly with one another and exclusively against the reference answer (Gold).

Do not assign numerical scores. Compare the answers on the following three aspects:
1. Correctness of the legal outcome.
2. Correctness of the legal reasoning and application of the law to the facts.
3. Correctness of the legal provisions and statutory elements.

Style, tone, language, length, structure and level of detail are irrelevant. Do not incorporate external knowledge or your own legal views.

Arrange all four candidates into rank groups from best to worst. Legally equivalent candidates must belong to the same rank group. Each candidate must appear exactly once.

Briefly justify the placement of each candidate, then provide a direct comparative justification of the ranking. Do not assign scores or derive the ranking from a numerical assessment.

Output only JSON conforming to the specified schema. No additional text or reasoning traces.
```

## Four-answer ranking input

Original: [rank_user.txt](../../src/legal_repro/assets/prompts/rank_user.txt).
Role: `user`.

```text
Question:
{question}

Reference answer (Gold):
{gold}

Exactly four anonymized answers as a JSON object:
{candidates_json}
```

## Training teacher instructions

Original: [teacher_developer.txt](../../src/legal_repro/assets/prompts/teacher_developer.txt).
The teacher is documented for methods reference; this release does not rerun
teacher labeling or compressor training.

```text
You annotate only training data for a compressor of German statutory texts that is blind to the question. You are given a training question, its training reference answer and a complete list of exact text units from a known statutory context.

Mark a unit as essential if removing it is likely to change the legal outcome, the application of the law to the facts, a decisive requirement, an exception, a negation, a deadline, a legal consequence or the legal basis of the training answer. Mark it as supporting if it is useful but not decisive. Leave all other units unmarked.

Use only existing unit_id values. The essential and supporting sets must be disjoint. Do not evaluate any subsequent evaluation questions or invent a new legal provision. Output only JSON conforming to the specified schema.
```

## Training teacher input

Original: [teacher_user.txt](../../src/legal_repro/assets/prompts/teacher_user.txt).

```text
Training question:
{training_question}

Training reference answer:
{training_answer}

Exact context units as JSON:
{units_json}
```

## Human annotation instructions

Original: [instructions.txt](../../src/legal_repro/assets/human_evaluation/instructions.txt).
The tie examples reproduce the original instructions, including `1, 1, 2, 3`.

```text
How the evaluation works

Read the question and the reference answer. The reference is not a fifth candidate answer.

Evaluate the four answers according to the legal outcome, legal reasoning/application of the law to the facts and legal bases. Style and length should not determine the ranking.

Select a rank below each answer: 1 = best answer, 4 = worst. The same rank may be assigned more than once and indicates a tie. At least one answer must receive rank 1.

Confirm your evaluation. You may skip cases and return to them later. If you cannot assess a case, select the corresponding option and explain why.

At the end, download your results file and send it to the study organizer.

The letters are neutral labels assigned afresh for each case. If you have doubts about the reference, flag and explain them separately. Use only this package during the evaluation.

Evaluate exclusively relative to the reference, without using external sources or incorporating your own differing legal views. A tie means equal legal quality, not uncertainty. Example: A and B are equally good, followed by C, then D → 1, 1, 2, 3. All equally good → 1, 1, 1, 1. A brief explanation under “Anmerkung” (“Notes”) helps with the later analysis. Work independently and discuss your assessments only after both final submissions. The LLM overview appears only after the separate finalization step; evaluations are then locked. Please do not view the source code beforehand.
```

## Annotator ZIP instructions

Original: [START_HERE.txt](../../src/legal_repro/assets/human_evaluation/START_HERE.txt).

```text
LEGAL ANSWER EVALUATION

1. First extract the ZIP file completely (e.g. right-click > Extract All).
2. Open the extracted index.html in an up-to-date desktop web browser.
   No installation, account or internet connection is required.
3. For each case, read the question and reference, then rank the four answers by legal quality.
   1 = best answer. Identical rank numbers indicate a tie.
   The reference is not a fifth answer. If you have doubts about it, flag them and explain.
4. Explicitly confirm your evaluations. Cases that cannot be assessed require an explanation.
   Each selection is immediately saved as a draft; only confirmation completes the case.
   The storage status indicates whether saving in the browser has been verified.
5. Before every break, click 'Ergebnisse / Sicherung herunterladen' ('Download results / backup'). Keep the JSON file.
   To resume, open index.html and, if necessary, select the latest JSON file using 'Sicherung laden' ('Load backup').
6. At the end, download again and send this latest JSON file to the study organizer.
   Do not return the HTML or ZIP file: they do not contain your evaluations!

Please check the download in your Downloads folder. There is no automatic transfer.
Browser storage alone is not a reliable submission. Do not use private/incognito windows.
If a storage error occurs, download a JSON backup before switching to another case.
Use this package only for the assigned person and not in multiple tabs at the same time.

FINALIZATION AND AGREEMENT
Evaluate independently and exclusively relative to the reference. No external sources.
A tie means legal equivalence, not uncertainty. Brief explanations are helpful.
After completing all cases, select 'Endgültig abschließen & Übersicht anzeigen' ('Finalize submission & show overview').
The evaluations are locked; only then does your comparison with the LLM appear.
The automatically downloaded FINAL_…json contains all questions, answers and evaluations.
Send this FINAL file to the study organizer. Please check that it has downloaded.
Do not discuss your assessments with the other person until both have finalized their submissions.
Do not use the source-code view: the offline finalization mechanism is not encryption.
```
