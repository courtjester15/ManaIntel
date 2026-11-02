# November 1 recovery review

Baseline captured November1 at20:25 EST, trailing seven days, before tonight's
live pilot. Existing health-report CLI; read-only GitHub observation was bounded
and completed with33 job reads, zero read errors, no truncation. Private report
and sanitized observation evidence are pinned under `.tmp/nov1-repair/`.

| Attempt cohort | Finished | New validated usable result | Prior publication preserved |
| --- | --- | --- | --- |
| Initial | 10 | 6 | 0 |
| Retry | 4 | 3 | 0 |
| Forced | 9 | 0 | 8 |

There were220 model calls:211 successful responses,9 failed responses and19
semantic timing rejections. Ten checkpoint/clip reuse events and11 transcript
reuse events were recorded. Nine usable results have verified persistence plus
Pages. No no-op/gated Pages churn was observed. The archive baseline was132 live
episodes,519 picks,55 needing review and two failed. Counts are processing and
publication measures, not source-accuracy scores; the0.6 release gate is not met.

Forced work with preserved output can still save useful repair checkpoints.
Zero new usable publications does not mean zero progress, and manual inspected
data corrections are distinct from a successful episode-processing journal.
Do not manufacture more runs to improve these denominators.

FF482's first attempt saved repairs of original chunks2/3 and needs chunk4.
It remains in cooldown until November2 at00:41 EST. FF492's optional review
attempt saved chunks1/2, with3-6 outstanding; four original picks remain
published. This is expected bounded continuation, not evidence that those
saved repairs were lost. FF484's final chunk has separate machine-supported
non-speech evidence and an exact-source-bound disposition; one inspected pilot
is warranted. Its remaining source uncertainty must stay needs_review.

BB667's Fire Crystal printing and entry target were checked separately against
local Whisper source-audio output and corrected without approval. All original
extraction/pick identities remain; machine provenance is distinct from human
review. See [the source-check record](BB667_REVIEW.md). The two existing
representative cases now pass31 scoped assertions together, while exact voice
attribution, full-episode completeness and human-certified ground truth remain
outside those assertions.

Production/pilot outcomes are recorded in the roadmap closeout after inspection.

## Verified closeout

[Release41373878662](https://github.com/courtjester15/ManaIntel/actions/runs/41373878662)
passed all246 tests, validation and Pages after correcting the stale inventory
assertion in the first pre-deployment run. No model calls were made in those
release checks.

[FF484 pilot41374027074](https://github.com/courtjester15/ManaIntel/actions/runs/41374027074)
published four recommendations using one extraction call and no new transcription.
Needs-review coverage remains. Two raw card names retain not-found/suggested
catalog status; no automatic canonical-name approval was manufactured.

[FF492 continuation41374375058](https://github.com/courtjester15/ManaIntel/actions/runs/41374375058)
completed chunk3 and saved chunk4's first clip with nine calls before the shared
optional budget stopped it at32/48. Its four old picks are unchanged. Retained
transcript repairs1/2/3 were inspected;4/5/6 remain. The episode/workflow failed,
while validation, persistence and Pages passed. The manual attempt counts toward
the existing cohort and daily optional episode caps. All16 primary requests
remain reserved; no further optional calls were made.

As of November1 at20:52 EST, the refreshed seven-day report has initial6/10,
retry3/4 and forced1/11 new usable outcomes, ten verified usable publications,
230 model calls,221 successful responses and21 timing rejections. Catalog:
132 episodes,523 picks,57 needing review, one failed and two human-reviewed.
This pass used ten provider calls. BB667's two corrected fields do not count as
a human review or a new episode-processing publication. Reports are dated
observations; private compact evidence is retained, temporary models and media
were removed. The0.6 release gate remains open.

Next work follows the existing gates: FF482 ordinary retry after00:41 EST on
November2; FF492 after fresh optional capacity/cooldown and cohort-limit checks;
FF484 names/variants need source checking before correction. No new automation
or broad historical rerun was created.
