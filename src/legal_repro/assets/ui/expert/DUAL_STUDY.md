# Two independent annotators, 100 questions each

Scope: prepare offline applications only; do not run models or change evidence.
Preserve all previously distributed ZIPs, answers, Gold and private keys.

## Fixed design

- Both annotators independently assess the same existing random sample of 100
  questions (90 context clusters), with the unchanged Gold and four answers:
  uncompressed, Legal LLMLingua-2 r=1.10, paragraph IDs and no context.
- Separate reviewer IDs and independently randomized A–D labels. Each question
  occurs once per reviewer. No additional questions or numerical scoring task.
- Match the saved LLM rubric: legal outcome, reasoning/subsumption and legal
  basis relative to Gold; ignore style and do not replace Gold with outside law.
  Flag reference problems separately. Equal legal quality means a tie; inability
  to judge needs a reason and is not a tie. Brief reasons are encouraged.
- No discussion, viewing the other annotation, or source inspection before both
  submissions. Prior exposure to earlier packets must be recorded separately.
- Primary endpoint: exact worse/tie/better agreement for compressed versus raw.
  Report each human–LLM comparison and human–human agreement. Secondary summaries:
  linear-weighted kappa, preference reversals, favourable-rate difference,
  complete-ranking agreement and mean agreement over the six answer pairs.
  Abstentions are excluded explicitly, not converted to ties or agreement.
- These 100 questions support a limited agreement audit, not proof of equivalence
  or human validation of every method or of the three numerical scores.

## Completion and feedback

After all 100 cases are confirmed or explicitly unassessable, a separate final
submission action freezes the ratings, downloads a self-contained final JSON,
then displays agreement with the saved LLM ranking. Before final submission,
there is no agreement feedback in the normal UI. Ratings remain locked after
reload/import of a final return. Do not share feedback until both humans finish.

An offline application cannot securely hide embedded reference data from a
determined source-code reader or authenticate the identity of the person using
it. The gate is a workflow safeguard, not encryption or tamper-proof enforcement.
Only anonymous LLM rank groups and the designated comparison labels are embedded;
source IDs, seeds, generation IDs, full condition keys and pointwise scores remain
in the organizer's private files.

Autosave/readback, previous snapshots, conflict rejection and JSON backup remain.
Final returns include the question, Gold, all four verbatim answers, all 100
annotations (including reasons/abstentions), frozen submission metadata and the
descriptive agreement overview. A ZIP/HTML file does not acquire saved ratings;
the expert must return the downloaded FINAL JSON file.

The organizer gets a separate offline page for importing both final JSON files,
viewing all answers/ranks/reasons and human–human/LLM summaries, and downloading
the combined data. Never send organizer material to an annotator. Match cases by
verified private row/answer links, never by differing anonymous letters.

## Analysis boundary

On actual returns, retain both independent human judgments rather than silently
forming consensus. The immediate UI overview is descriptive: no p-values or
claims of equivalence. Subsequent inferential analysis should resample entire
context clusters with both humans and the LLM kept together. Paired directional
tests likewise need cluster adjustment; six pairs within a question are not six
independent samples. Any exploratory adjudication happens after original grades
are locked and must remain a separate annotation layer.

## Verification

Use synthetic fixture judgments only: test the exact shared sample and texts,
different labels/IDs, tied and reversed preferences, undefined kappa, abstention
denominators, no early feedback, finalization locking, save/reload/import and
storage failure, self-contained returns, cross-reviewer rejection, source-safe
HTML, organizer joins across different labels, and old-protocol compatibility.
Check ZIP contents and private-file permissions before handoff. Generated
participant packets must contain zero real or synthetic human judgments.
