# Review workspace: November 14, 2026

Release 0.5.27 makes the existing static review workflow usable for more complete
corrections without changing extraction defaults, sources, spending or retention.

## Findings and result

| Finding | Result |
| --- | --- |
| Correcting an unknown speaker fills the show host list and requires attribution. | Pick speakers remain blank when unknown, including newly added picks. The backend accepts an explicit empty list. The summary schema now describes the empty-speaker representation already used by 77 of the 546 published records. |
| The editor cannot correct historical prices stored as entry targets, a hold period, reasoning or caveats. | Expose mentioned-price context, entry/exit targets with source wording and optional bounds/currency, hold, reasoning/caveats and optional end timestamps. A single clear-target action removes an unsupported target. No prices are inferred from prose. |
| Every prepared review silently requests approval of the whole episode. | Require an explicit outcome. Whole-episode approval retains the existing authenticated human-review path. Limited corrections keep needs review and the existing strict printing/clear-entry-only scope, with a required evidence note. |
| Raw JSON is the only prepared-change preview. | Show included/excluded/added counts and escaped field-by-field published-value/result comparisons before the copyable payload. Reverting a prior correction is visible. Form changes and failed preparation clear the preview and payload. |
| Loading original extraction can discard a saved correction on a later Keep approval. | Load effective values, preserve prior corrections in the cumulative override, and fail closed when effective data is unavailable or mismatches its public revision. BB667 is the retained-evidence regression example; its publication is unchanged. |
| Extraction expectations alone cannot detect another review of the same extraction. | Review payload 1.1.0 includes the current durable-review hash. Reject stale revisions before writing. Legacy stored 1.0.0 reviews remain readable; legacy submissions cannot overwrite existing reviews. |
| The limited-correction human-review guard checks only the immutable extraction, which lacks a later durable human approval. | Also inspect the current durable review before replacement. A limited correction cannot replace a human approval even with its current revision token. |
| Machine-checked complete episodes cannot open review, including FF538. | Offer review for published, not-yet-human-reviewed machine output from details and summary pages. Failed output and already human-reviewed episodes do not open an editable draft. |

## Verification

Dependency-free Node checks exercise unknown attribution, target parsing and
validation, semantic target equality, limited-correction scope, existing-correction
preservation, explicit outcomes, preview escaping/reversions, stale-output
invalidation, optional lookup failure and saved-review mismatch. Python tests
exercise durable price/hold changes, unknown-speaker additions, repeated rebuilds,
stale revisions, legacy compatibility, protection of human approvals and rejection
of invalid targets, clocks and duplicate identities before overwriting a review.

Separate scratch jsdom journeys use real FF538 and BB667 archive data. Approval
after a prior correction, price/hold edits, exclude/add and limited printing
correction all produce payloads accepted by the backend in isolation. These are
QA drafts, never source-certified corrections and never written to production.
Missing/mismatched effective data blocks preparation. Optional card-resolution
failure does not block it. Existing clipboard fallback and source playback remain.

An isolated production rebuild preserves all 546 published pick records exactly.
The final live-mode rebuild preserves all 293 original extraction, episode
metadata and durable-review files byte-for-byte. Only the public index and three
effective summaries receive review-revision projection metadata. The version is
0.5.27; archive schema remains 1.1.0 and extraction/transcription prompts and
provider policy are unchanged. All 45 scoped R2 assertions still pass.

The in-app browser timed out. No external browser or desktop automation was used.
DOM checks do not establish desktop/mobile pixel layout, real clipboard permission
or audio-host playback. Visual QA remains open. R2's independent FF538 source
check and the 0.6 sustained-reliability gate remain open as well.

Final local checks: 262 Python tests, 26 dependency-free Node checks, production
archive validation and all 45 scoped evaluation assertions pass. The production
projection metadata is checked in with the implementation so the next scheduled
preflight agrees with the new effective-summary representation.


## Production closeout

Implementation `9e07ca6`; [release 43673378244](https://github.com/courtjester15/ManaIntel/actions/runs/43673378244)
passed all 262 production tests, archive validation, publish and Pages. Served
0.5.27 has 142 episodes and 546 picks, with 62 needs-review, 78 complete and two
failed episodes. All seven served JS/CSS assets match the release; all three HTML
entrypoints reference 0.5.27. The three effective summaries match their public
review-revision tokens. No actual review was submitted by this batch.

Compared the preceding production Pages artifact (43655492596) with this release:
the published card payload is byte-for-byte identical, SHA-256
`abafdb59dca82acfa5eb04130da5f0a32ccade84bc7a692483b2f5fb9c847aef`.
The three effective summaries are identical apart from the new revision token.
This verifies preservation against the actual prior publication as well as the
separate local/source preservation checks.

A separate existing publication discrepancy was observed during verification:
29 projected pick records differ from checked-in source in punctuation/text
characters (for example, a curly apostrophe or ellipsis becomes a replacement
character). It is present in both old and new Pages artifacts; original metadata
in the same artifact still matches immutable Git source. The cause is not yet
established. Do not silently normalize the comparison or call source/publication
text an exact match. Retained both Pages artifacts, a compact example, verification
hashes and relevant QA evidence under pinned `.tmp/review-workbench/` for the next
bounded diagnosis. Downloaded test dependencies and copied preview files are
disposable; no podcast audio/transcripts or model outputs were created.

Housekeeping: scratch preview/apply found 0 MiB eligible for age cleanup. Removed
the new jsdom installation and copied preview site after verification; retained
only pinned QA/publication evidence. Checkout was synchronized before closeout.
