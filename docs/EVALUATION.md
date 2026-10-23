# Representative quality evaluation

R2 first batch, October 16, 2026. These offline checks exercise known failure shapes, not model accuracy. All new spoken examples and card labels are invented minimal cases; no private transcript excerpts or audio are committed.

Run with `PYTHONPATH=src python -m unittest discover -s tests -v` (set the environment variable using your shell).

| Risk / incident lesson | Executable evidence | What it establishes |
| --- | --- | --- |
| FF 494 weak or incomplete section evidence | `test_representative_evaluation.py`: both shows without an explicit ending; `test_production.py`: FF 532 late agenda | Locating a section does not silently remove boundary uncertainty. These are analogous cases, not a source replay of FF 494. |
| BB 666/667 separated recommendation segments | `test_representative_evaluation.py`: early Breaking Bulk and late Pick of the Week with intervening discussion | Both recommendation windows survive selection; absent ending remains reviewable. Does not prove every spoken pick was transcribed. |
| Missing recommendation content despite plausible clocks | `test_representative_evaluation.py`: full text has a pick missing from timed segments; `test_520_regressions.py` | Timing can pass while content coverage fails. Evidence remains unchanged; adding the missing timed text clears the signal. |
| BB 666/667 bad clocks and repair failures | `test_transcript_timing.py`; `test_reliability.py`: explicit clock schema, repair bounds, retained rejected payloads, incremental repair reuse | Compressed, clamped and missing chunk coverage is detected; repair evidence is retained and published results survive later failures. |
| Ambiguous card names | `test_production.py`: targeted second listen requires catalog verification; `test_reliability.py`: unavailable verification preserves ambiguity | An unavailable check cannot automatically approve an uncertain name. Catalog spelling alone does not prove audio identity. |

## Limits and next action

Structural checks (JSON/schema/archive validation) and these semantic guard checks are distinct from independent source accuracy. This inventory is not a passing percentage for Gemini or a claim of representative statistical coverage. It does not establish that an entire episode is complete, or that names, attribution and quotations match audio.

R2 remains in progress. Next: add a small independently checked expected-pick inventory for both shows, using only suitable sanitized evidence and explicit unknowns. Compare candidate extraction against that inventory before changing model/prompt defaults under R4. Do not generate inference calls simply to fill an evaluation sample. R3 can proceed independently while evidence is collected.

## Review automation regression batch (0.5.13)

`tests/test_review_issues.py` adds twelve tests: mixed identity/printing/intent/scope/timing reasons cannot be cleared by name confirmation; identity-only correction retains original reason; unknown prose abstains; boundary reasons survive; out-of-audio/out-of-section picks receive independent issues; explicit recommendations may retain source caveats; casual advertised-topic handoff needs supporting terms and cannot cut off another pick; wrong audio indices make no inference request. `test_reliability.py` checks extraction prompt changes do not invalidate unchanged transcription evidence.

Offline replay of the five previously inspected retained snapshots changes FF 495 from an unbounded 638–1839 section to an advertised-topic-bounded 638–1406 section. FF 494, FF 510, BB 666 and BB 721 retain their warnings. This is boundary behavior evidence, not proof of transcript accuracy; FF 495's saved transcript contains interleaved material and its timing concerns remain unresolved.

0.5.14 preservation cases cover lost/simplified printing, lost known foil state, case-only equivalence, candidate multiplicity, unknown-to-specific printing, and end-to-end forced rerun preservation of exact records/IDs. FF 495's live retained-transcript pilot exposed this gap; its old records were restored, with candidate evidence kept in the private comparison artifact. Timing remains unresolved and no human/source accuracy approval was manufactured.

## October 23: scoped expected-pick inventory

`tests/fixtures/evaluation_inventory.json` records seven expected picks: four from FF537's cards-to-watch discussion and three from BB667's late Pick of the Week. An agent inspected retained transcript discussion separately from candidate summaries, then wrote sanitized paraphrases, explicit field expectations, navigation windows and private-snapshot hashes. No private transcript excerpts or model response payloads are added. Explicit aliases preserve the known raw Ojer spelling and Fire Crystal naming variation without general fuzzy matching.

This is **transcript-checked evidence, not independently verified audio ground truth**. Source transcripts remain model output. All per-pick voice attribution, exact audio alignment and full-episode completeness are unscored; BB667's earlier Breaking Bulk is outside this case. FF537's two-reading audio recovery remains separate model-derived evidence, not a gold host label. R2's independent source-accuracy gate remains open.

Run the read-only comparison from the repository root:

```powershell
python tools/evaluate_picks.py
python tools/evaluate_picks.py --case bb667-pick-of-the-week --candidate path/to/candidate-summary.json
```

The command emits JSON and exits 1 for findings, 0 when the scoped assertions match, and 2 for invalid input. A zero exit is not whole-episode approval. Candidates must match the case's episode GUID. Missing picks and ambiguous multiplicity are findings; the tool never chooses a convenient duplicate. Unlisted fields and additional recommendations are unscored rather than counted as correct or incorrect. Comparison does not mutate archive data, overrides or review states.

Initial production comparison (October 23): FF537 matches 19 scoped assertions. BB667 has two findings across 12 assertions: Fire Crystal's 2.50-to-5 historical price movement is stored as an entry target, and its explicit full-art preference is absent from printing. These are retained-transcript findings, not audio-certified corrections; publication remains unchanged. The comparison intentionally exits 1 on this baseline. Unit tests exercise omissions despite unchanged pick count, lost variant details, historical-price confusion, bad clocks, duplicate ambiguity, wrong-episode rejection and explicit unknowns. Tests do not require the production baseline to be clean.

Next: verify the two BB667 findings against source audio before a durable correction; extend independent checks to both shows before comparing model/prompt defaults. Do not spend inference calls merely to fill the sample.
