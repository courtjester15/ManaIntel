# BB667 source-audio correction

November 1, 2026. Two fields were corroborated against a separate local source-audio
reading and corrected through a durable `correct_without_approval` override.
This is machine-supported evidence, not human listening or whole-episode approval.

| Field | Original extraction | Effective publication |
| --- | --- | --- |
| Printing | Final Fantasy | Final Fantasy full art |
| Entry target | USD 2.50-5 | Unknown (null) |

The original extraction remains unchanged. All three pick IDs remain unchanged;
Fire Crystal retains `pick-900c62db8f07363f`. The changed pick and effective episode
remain needs_review; no human_review provenance is created. The other two pick
objects are preserved. The existing stale-extraction guard still applies.

The original retained Gemini snapshot matches evaluation hash
`9fcd559ac2b32439b50cbddbe2bb78aafe0f1b19a170bead1df43536bf3880d5`.
A separate local Whisper small.en CPU reading of source seconds3680-3750 corroborated
historical price movement and an explicit full-art preference. Its numbers/card
spelling have ordinary ASR imperfections; it is corroboration, not certified ground
truth. Compact source/evidence hashes are in the evaluation inventory. Private
ASR output and source manifests are pinned under `.tmp/nov1-repair/`.

[Source audio at1:01:23](https://traffic.libsyn.com/brainstormbrewery/Brainstorm_Brewery_667_Colector_Booster_Boosting.mp3#t=3683).
No full private transcript or audio is committed or published. The evaluator now
checks the effective summary and passes all twelve scoped assertions. Earlier
Breaking Bulk, voice attribution, other prices and full-episode completeness
remain unscored. R2's independent source-accuracy gate remains open.
