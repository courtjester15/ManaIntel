# Three-month audit of “complete” outcomes

Window: August 24–November 24, 2026, America/New_York; production examined through
`74dd23d`. Read-only analysis: no extraction, model calls, status migrations or
approvals. Reconstructed 258 first-parent catalog revisions, compared historical
code/configuration, inspected every September first-complete episode record,
and checked available retained evidence and prior incident findings.

## Finding

September really had the highest rate of additions to the complete category.
The older label was substantially easier to obtain and sometimes concealed
unusable clocks or weak coverage evidence. Today’s lower complete throughput is
also a real processing problem: outages and expensive timing repairs stop work
before extraction. Neither “the old results were all good” nor “the old results
were all wrong” is supported. We cannot certify episode completeness from a
successful model response, pick count or stored summary alone.

## Reconstructed activity

| Period | New episode records | Distinct episodes newly entering complete in window | Complete on first catalog appearance |
| --- | ---: | ---: | ---: |
| Aug 24–31 | 10 | 6 | 3/10 |
| September | 38 | 36 | 21/38 |
| October | 32 | 13 | 6/32 |
| Nov 1–24, partial | 18 | 4 | 1/18 |

“Newly entering” counts an episode once after the window’s baseline, including
recovery of failures first recorded in an earlier period. It is not a rate with
new episode records as its denominator. Repeated complete-to-review-to-complete
cycles are excluded from that column. First catalog appearance is not necessarily
the first provider attempt: unsuccessful unpersisted work can precede it.
Synthetic fixtures, deploy-only jobs and unchanged/empty workflow runs do not
count as episode completions. Git establishes persistence, not verified Pages
publication for every historical revision.

Best week: **September 14–20, 12 distinct newly complete episodes**. September
7–13 had 11; together those two weeks supplied 23. The peak week had 13 entries
into complete if a repeated re-entry is counted, which overstates new progress.

Cumulative complete inventory was 29 on August 31, 64 on September 30, 75 on
October 31 and 78 now. We have not broadly removed old complete labels. Of the
36 September entrants, 33 are still complete; only FF503, FF501 and FF510 are
now needs_review. The current catalog contains 149 episodes: 78 complete,
66 needs_review and five failed. Many older complete labels still carry the
original weaker evidence; leaving the label untouched is not recertification.

## Were September’s results actually complete?

All 36 September entrants were inspected at the revision where they first
entered complete. Thirty-five have summaries; BB703 is an explicitly recorded
metadata-only no-recommendations disposition. FF500 and FF508 also have explicit
no-recommendations dispositions. Thus 33 are positive-pick extractions, not 36
independently verified recommendation captures.

Across the 35 historical summaries:

| Recorded signal | Episodes |
| --- | ---: |
| Section warning already present despite complete label | 17 |
| Timestamp adjustments recorded | 34 |
| More than 100 timestamp adjustments | 18 |
| Shared pick-start clocks | 9 |
| Pick end beyond the recorded feed duration | 7 |
| Section longer than 50 minutes | 2 |

These signals overlap. They are not an accuracy score or a verdict that all
affected picks are wrong. Feed duration may be inaccurate; shared timestamps can
represent legitimate distinct variants; small timing adjustments can be harmless.
Of the 17 section warnings, 15 accompany nonempty extractions. None of those
15 was prevented from being complete merely by its section warning.

There are nevertheless concrete failures of the old evidence contract:

* **BB678, September 15:** five approved picks and complete, despite 215 timing
  adjustments. Witty Roastmaster and Bringer of the Last Gift both start and end
  at 1800 seconds. Another pick begins after the recorded 3252-second duration.
  [Historical source summary](https://github.com/courtjester15/ManaIntel/blob/597dccc5e364002e2b80ca4085df009bae156f60/archive/episodes/0678-npr-pick-of-the-week-brainstorm-brewery-678-magic-finance/summary.json).
* **FF504, September 6:** complete with two picks; Narset’s Reversal has start=end
  1800 and Avatar Kyoshi also starts at 1800. There are 42 timing adjustments
  and an unresolved section-ending warning.
  [Historical source summary](https://github.com/courtjester15/ManaIntel/blob/887d30350d2713f41fe252d75be0b84afe58f8e6/archive/episodes/0504-monster-hunter-secret-lair-breakdown/summary.json).
* **BB677, September 16:** complete with six picks and 133 timing adjustments;
  two recommendations have zero-duration clocks at 1800, and another extends
  beyond the recorded duration.
  [Historical source summary](https://github.com/courtjester15/ManaIntel/blob/71c2e7e3750f8450cdaef4988c4d62af3c750cdf/archive/episodes/0677-generational-picks-brainstorm-brewery-677-magic-finance/summary.json).
* **BB681, September 13:** complete with seven picks, a selected section starting
  nine seconds into the show and spanning nearly an hour, and 114 timing
  adjustments. This is not sufficient evidence that a trustworthy recommendation
  block was isolated.
  [Historical source summary](https://github.com/courtjester15/ManaIntel/blob/6125634aeb20fbed8a142563e6e35e864d56e5f9/archive/episodes/0681-earthbending-like-beckham-brainstorm-brewery-681-magic-finance/summary.json).
* **FF510, September 14:** complete with two picks and 46 timing adjustments.
  Later retained transcript evidence (version 0.5.5, not the September response)
  still fails today’s timing detector on three original chunks. It cannot
  independently certify the September publication and must not be represented
  as a contemporaneous recording of that extraction.

There are 17 zero-duration pick records across the inspected summaries, including
some at exact 900-second chunk boundaries. Combined with the old clamping code,
these show that some green results did not meet basic timing-quality standards.
They do not prove which spoken recommendations were omitted or invented.

Most original September transcript artifacts are no longer available under the
14-day private retention policy. Locally retained matching evidence was found
only for FF510, from a later version. No fresh independent listening/ASR or
human source certification was performed. Consequently, **full recommendation
coverage and source accuracy remain unverified**, including for records without
an obvious summary-level contradiction. The prior [October audit](NEEDS_REVIEW_AUDIT.md)
and [failure investigation](FAILURE_RECOVERY_AUDIT_2026-10-04.md) document related
agenda selection, lost publications and false-green limitations.

## What code/configuration changed?

| Aspect | September peak | Current implementation |
| --- | --- | --- |
| Provider/model | Gemini 3.5 Flash primary; Flash Lite fallback | Flash Lite primary/default; explicit 3.6 option |
| Audio chunks | 900 seconds | Still 900 seconds; bounded shorter split/repair clips |
| Clock treatment | Numeric values clamped into chunk bounds; adjustment count recorded | Explicit clock parsing and timing/coverage gates; saved targeted repairs |
| Complete decision | Nonempty extraction, model review_reason absent, all picks approved | Also incorporates section warnings, low FF count, timing/content issues |
| Coverage checking | Basic section detector, no present-day timing gate | Stronger agenda/handoff logic and missing/timing-content checks |
| Recovery persistence | Chunk checkpointing added Sep 1; limited preservation/diagnostics | Full retained transcripts/checkpoints, preservation guards, duplicate rejection and retained rejected candidates |
| Retry bounds | Three episode attempts, six-hour cooldown | Same ordinary limits plus 48-hour/weekly renewal for explicit outages |
| Extraction context | Selected timed segments only | Oct 22 added introduction/nearby context with explicit attribution rules |

All 35 inspected historical summaries report 0.5.3. Thirty used Flash for
extraction and five used Lite; transcription was Flash-only or mixed with Lite.
This describes successful historical outputs, not an unbiased model comparison.
There is no equivalent per-request September ledger to compare against current
provider availability. Reverting defaults would need a bounded current test.

The decisive status change is [October 6, `5f90e23`](https://github.com/courtjester15/ManaIntel/commit/5f90e239366c54bbbc557fc7d9452a7590671579):
the pipeline began combining the section review reason with the model review
reason and adding a warning for fewer than four FF recommendations. The same
commit introduced suspect-timing repair gates and stronger preservation against
lossy replacements. Earlier, a section warning could remain in the summary while
the model returned a null extraction review reason, yielding complete.

The old transcriber literally bounded start/end with min/max against chunk length.
That could convert malformed clocks into many zero-length records at a boundary;
recording the number of adjustments did not stop the complete decision.
See [September-era implementation](https://github.com/courtjester15/ManaIntel/blob/5b8fb1f/src/ffw/production.py).

October 12 then simultaneously changed the primary to Gemini 3.6 Flash and removed
the 365-day automatic-selection cutoff. The inspected October 12–14 migration
sample had **30 failed 3.6 calls out of 30**, with Lite doing the usable work.
That was a demonstrated availability regression in that sample; it does not
establish the old primary’s availability now. Lite became the responding default
on October 15. See [migration investigation](RELIABILITY_REVIEW_2026-10-14.md).

The full per-attempt ledger starts October 6, so a three-month request-failure
rate cannot honestly be reconstructed. Available October records contain 627
model calls and 65 recorded 503s; November contains 419 calls and 33 recorded
503s through the audited production head. Those include retries/forced work and
are additional to timing/truncation problems. One failed required request can
prevent an episode’s entire extraction even when earlier chunk calls succeed.

## Assessment and next action

1. **Do not restore the old complete count by dropping timing/coverage guards.**
   The old count includes demonstrably weak clocks and unverified section scope.
2. **Fix the overly broad status contract separately.** The runbook says a missing
   ending alone need not force review, but current code merges every section
   warning into the blocking reason. Distinguish non-blocking diagnostics from
   unresolved source/coverage defects, with evidence requirements for each.
   The prior 22 ending-only candidates are inspection candidates, not 22 safe
   automatic approvals.
3. **Evaluate actual output, not labels.** Use the same retained audio/evidence
   to compare responding model configurations and bounded clip sizes, scoring
   recommendation coverage, identities/variants, attribution, clock quality,
   calls and usable publication. Keep failure and preserved-output denominators.
4. **Prioritize existing risks on both sides of the label.** FF539’s known missing
   final discussion and attribution remain open; old complete BB678/677/FF504
   deserve timing/source checks too. Do not mass-reprocess or approve the archive.

The evidence supports three interacting causes: a more permissive historical
label, changed model/provider behavior, and stronger checks that now expose
previously accepted damage. Their separate causal shares are not identifiable
from the surviving data. No runtime rollback or new recovery is justified merely
to make the complete counter larger.

Private reproduction scripts, numeric outputs and transcript inventory are
protected under `.tmp/three-month-audit/`. No private transcripts were committed.
