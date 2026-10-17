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
