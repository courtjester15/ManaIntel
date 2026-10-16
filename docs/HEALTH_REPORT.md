# ManaIntel processing health

As of **2026-10-16T03:37:09Z** · trailing 14 days · generator 0.5.11

This is a report of recorded evidence, not an uptime or extraction-accuracy score. Initial attempts, retries and forced recoveries have separate denominators.

## Recorded episode outcomes

| Attempt kind | Finished | Validated usable result | Complete | Needs review | Failed | Interrupted | Old result preserved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| initial | 5 | 2/5 (40%) | 0 | 2 | 3 | 0 | 0 |
| retry | 3 | 0/3 (0%) | 0 | 0 | 3 | 0 | 0 |
| forced | 14 | 8/14 (57%) | 3 | 6 | 5 | 0 | 1 |

A validated usable result means a new complete/needs-review extraction with picks (or an explicit confirmed-no-recommendations disposition) and successful archive validation. An unexplained empty result, preserved previous output, skip, or in-progress attempt is not a new usable result. Human/source correctness is not established by this measure.

Skipped records: 0; in progress: 0; unexplained empty results: 0.

Verified persistence + Pages for usable results: **9**; completed runs without both observed: 1; unknown/in progress: 0.

## Source, version and configured-model cohorts

| Source | Pipeline | Kind | Transcription / extraction model | Finished | Usable | Failed | Needs review | Publication verified |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brainstorm Brewery | 0.5.10 | forced | gemini-3.5-flash-lite | 1 | 1 | 0 | 0 | 1 |
| Brainstorm Brewery | 0.5.5 | initial | gemini-3.5-flash | 1 | 1 | 0 | 1 | 1 |
| Brainstorm Brewery | 0.5.5 | initial | gemini-3.6-flash | 1 | 0 | 1 | 0 | 0 |
| Brainstorm Brewery | 0.5.5 | retry | gemini-3.6-flash | 2 | 0 | 2 | 0 | 0 |
| Brainstorm Brewery | 0.5.6 | initial | gemini-3.6-flash | 1 | 0 | 1 | 0 | 0 |
| Brainstorm Brewery | 0.5.6 | retry | gemini-3.6-flash | 1 | 0 | 1 | 0 | 0 |
| Brainstorm Brewery | 0.5.7 | forced | gemini-3.6-flash | 1 | 0 | 1 | 0 | 0 |
| Brainstorm Brewery | 0.5.8 | forced | gemini-3.6-flash | 1 | 0 | 1 | 0 | 0 |
| Brainstorm Brewery | 0.5.9 | forced | gemini-3.5-flash-lite | 1 | 0 | 1 | 0 | 0 |
| Brainstorm Brewery | 0.5.9 | forced | gemini-3.6-flash | 1 | 1 | 0 | 1 | 1 |
| MTG Fast Finance | 0.5.5 | forced | gemini-3.5-flash | 8 | 5 | 2 | 4 | 4 |
| MTG Fast Finance | 0.5.5 | initial | gemini-3.6-flash | 2 | 1 | 1 | 1 | 1 |
| MTG Fast Finance | 0.5.6 | forced | gemini-3.6-flash | 1 | 1 | 0 | 1 | 1 |

Initial-attempt sample on current generator/pipeline version: **0**. A short recovery experiment does not establish sustained unattended reliability; this report alone does not satisfy the 0.6 release gate.

## Observed model responses

| Model | Calls | Successful responses | Failed responses | Rejected timing responses |
| --- | --- | --- | --- | --- |
| gemini-3.5-flash | 46 | 29 | 17 | 0 |
| gemini-3.5-flash-lite | 61 | 56 | 5 | 3 |
| gemini-3.6-flash | 41 | 1 | 40 | 0 |

Checkpoint/clip reuse events: 12; retained-transcript reuse events: 11; unavailable-model skips: 11.

A successful provider response may still fail semantic timing checks. Rejection counts are additional quality signals, not extra provider calls. Missing older telemetry is not reconstructed.

## Failed/interrupted attempt causes

| Cause category | Attempts |
| --- | --- |
| provider_availability | 2 |
| transcript_timing_or_coverage | 8 |
| truncated_model_output | 1 |

These are message-based terminal categories, not independently verified root-cause verdicts. Provider response counts separately expose outages hidden inside composite repair errors. Raw exceptions, transcript bodies and private recovery notes are not copied here.

## Workflow and deployment evidence

| Workflow class | Recorded/observed run attempts |
| --- | --- |
| deploy_only_push | 17 |
| gated_skip | 5 |
| no_op | 13 |
| processing | 22 |
| queue_no_op | 8 |
| unclassified | 18 |

| Observed workflow conclusion | Run attempts |
| --- | --- |
| failure | 15 |
| success | 68 |

| Pages job outcome | Run attempts |
| --- | --- |
| no_deploy_job | 14 |
| success | 46 |
| unknown | 23 |

Observed no-op/gated runs with a successful Pages job: **11**. This exposes publication churn separately from useful processing.

Workflow results, validation, persistence and Pages are distinct. A failed workflow can deploy a valid failure record. Unknown is not success. Push runs of ffw.yml are deploy-only; unclassified manual dispatches are not guessed to be no-ops or deploy-only.

GitHub evidence: available; job requests: 60; failed job reads: 0; bounded/truncated evidence: True. The current workflow may still be running when its summary is generated.

## Current archive and review backlog

Catalog snapshot: 2026-10-16T02:57:02Z. **106 live episodes, 419 picks, 40 episodes needing review, 0 currently failed, 2 explicitly human-reviewed.**

| Source | Episodes | Picks | Needs review | Failed | Human reviewed |
| --- | --- | --- | --- | --- | --- |
| Brainstorm Brewery | 55 | 213 | 15 | 0 | 0 |
| MTG Fast Finance | 43 | 170 | 17 | 0 | 2 |
| Unknown | 8 | 36 | 8 | 0 | 0 |

| Review reason (may overlap) | Episodes |
| --- | --- |
| low_pick_count | 2 |
| name_or_printing | 3 |
| other_or_unspecified | 12 |
| section_or_boundary | 26 |

This snapshot is separate from historical attempt outcomes; a later recovery does not erase earlier failures. Machine-approved is not the same as human-reviewed. These are recorded archive counts, not total feed coverage.

## Recent episode attempts

| UTC start | Source / episode | Version | Kind | Outcome | Picks | Publication evidence | Run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-16T02:54:41Z | Brainstorm Brewery 667 | 0.5.10 | forced | complete | 3 | verified | [38842689643](https://github.com/courtjester15/ManaIntel/actions/runs/38842689643) |
| 2026-10-16T02:46:48Z | Brainstorm Brewery 667 | 0.5.9 | forced | failed | 0 | not a usable new result | [38842081267](https://github.com/courtjester15/ManaIntel/actions/runs/38842081267) |
| 2026-10-16T02:42:17Z | Brainstorm Brewery 666 | 0.5.9 | forced | needs_review | 3 | verified | [38841659910](https://github.com/courtjester15/ManaIntel/actions/runs/38841659910) |
| 2026-10-16T02:36:04Z | Brainstorm Brewery 666 | 0.5.8 | forced | failed | 0 | not a usable new result | [38841020667](https://github.com/courtjester15/ManaIntel/actions/runs/38841020667) |
| 2026-10-16T02:25:57Z | Brainstorm Brewery 666 | 0.5.7 | forced | failed | 0 | not a usable new result | [38840331812](https://github.com/courtjester15/ManaIntel/actions/runs/38840331812) |
| 2026-10-15T23:04:22Z | Brainstorm Brewery 666 | 0.5.6 | retry | failed | 0 | not a usable new result | [38821207857](https://github.com/courtjester15/ManaIntel/actions/runs/38821207857) |
| 2026-10-15T15:00:04Z | Brainstorm Brewery 666 | 0.5.6 | initial | failed | 0 | not a usable new result | [38756313025](https://github.com/courtjester15/ManaIntel/actions/runs/38756313025) |
| 2026-10-15T03:09:04Z | MTG Fast Finance 494 | 0.5.6 | forced | needs_review | 3 | verified | [38674664775](https://github.com/courtjester15/ManaIntel/actions/runs/38674664775) |
| 2026-10-14T23:13:14Z | Brainstorm Brewery 667 | 0.5.5 | retry | failed | 0 | not a usable new result | [38652629206](https://github.com/courtjester15/ManaIntel/actions/runs/38652629206) |
| 2026-10-14T15:06:57Z | MTG Fast Finance 494 | 0.5.5 | initial | failed | 0 | not a usable new result | [38586382931](https://github.com/courtjester15/ManaIntel/actions/runs/38586382931) |
| 2026-10-13T23:43:52Z | Brainstorm Brewery 667 | 0.5.5 | retry | failed | 0 | not a usable new result | [38485922136](https://github.com/courtjester15/ManaIntel/actions/runs/38485922136) |
| 2026-10-13T17:36:02Z | Brainstorm Brewery 667 | 0.5.5 | initial | failed | 0 | not a usable new result | [38439808839](https://github.com/courtjester15/ManaIntel/actions/runs/38439808839) |
| 2026-10-13T02:52:42Z | MTG Fast Finance 495 | 0.5.5 | initial | needs_review | 4 | verified | [38338866689](https://github.com/courtjester15/ManaIntel/actions/runs/38338866689) |
| 2026-10-11T03:45:21Z | MTG Fast Finance 510 | 0.5.5 | forced | needs_review | 2 | verified | [38109309180](https://github.com/courtjester15/ManaIntel/actions/runs/38109309180) |
| 2026-10-10T01:28:43Z | MTG Fast Finance 510 | 0.5.5 | forced | failed | 0 | not a usable new result | [38013252984](https://github.com/courtjester15/ManaIntel/actions/runs/38013252984) |

## Coverage and limits

Live attempt journals first recorded: 2026-10-06T22:48:37Z; latest recorded: 2026-10-16T02:54:41Z. No historical attempt backfill is implied.

The window uses UTC attempt start times and includes only dated live records. Synthetic fixtures are excluded. Source/model/version cohorts can have very different sample sizes and forced-recovery selection bias. No financial-performance or source-accuracy claims are made.

- 8 catalog entries lack an explicit supported source ID; grouped as Unknown rather than inferred.
