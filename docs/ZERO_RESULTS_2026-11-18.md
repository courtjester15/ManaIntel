# Recent zero-result investigation

Inspected production through `1bf85ad` and run
[44440121805](https://github.com/courtjester15/ManaIntel/actions/runs/44440121805),
including retained transcripts, attempt events, capacity reservations, source
summaries, detector inputs and workflow persistence/deployment steps.
Dates below use America/New_York (EST).

## What the zeros mean

November 12–18 inclusive contains 14 ordinary episode attempts: five initial
and nine retries. Nine failed, two finished with unexplained empty extractions,
and three produced picks. Initial attempts: one with picks, one empty, three
failed. Retries: two with picks, one empty, six failed. These are attempt counts,
not distinct episodes, and do not establish source accuracy.

Eight of the nine failures encountered a recorded Gemini HTTP 503. The other
hit a bounded timing-repair call limit. Some successful HTTP responses were
truncated or had unusable timing, requiring more split/repair requests before
extraction could begin. The 30-minute shared outage guard intentionally prevents
an immediate retry after 503. Repeated outages still consume ordinary episode
attempts; after three, the episode remains quarantined until inspected recovery.
The recent capacity ledger does not show daily quota exhaustion: November 15,
16 and 17 Pacific-day request totals were only 6, 8 and 6 respectively, against
the configured 48-request application budget. Provider overload is distinct from
that budget and from an observed daily-quota refusal.

Eight forced cleanup/recovery attempts in the same date window are separate:
three failed, four published machine output and one retained its previous
publication after a replacement regression. None establishes an empty episode.

At the inspected production baseline, 10 of 146 episodes have zero published
picks: four failures (BB653, BB652, BB650, FF478), three unresolved empties
(FF539, BB651, BB659), and three previously confirmed no-recommendations
dispositions (BB703, FF508, FF500). Existing publications were not erased by
recent failures. FF540's zero has already recovered to three needs-review picks
on its third ordinary attempt, with successful persistence and Pages deployment.

## FF539: demonstrated selection bug plus model omission

[Run 43565725335](https://github.com/courtjester15/ManaIntel/actions/runs/43565725335)
completed transcription after two earlier failures. The selected section began
at 1363 seconds, at a final-card handoff, despite earlier recommendation content.
The start detector prioritized the later explicit card-to-watch phrase over
earlier recommendation language. This excluded approximately 14 minutes from
the supplied extraction evidence. Retained text supports discussion of
Shang-Chi, Dawnsire, Sensei's Divining Top, Esper Sentinel and SOLDIER Military
Program, with variant/name uncertainty requiring ordinary checks.

The model also returned zero picks even from the selected final-card discussion.
The successful extraction response used only 19 output tokens and passed the
schema because an empty recommendations array is valid. The journals record no
provider explanation for that omission. The boundary defect is demonstrated;
it does not fully explain why the remaining final-card evidence was omitted.

Version 0.5.31 treats a later other/final-card marker as continuation when an
earlier first-pick handoff or explicit watch-language opening is present. Generic
market-mover mentions do not supply that earlier start. Offline comparison across
47 retained episode transcripts changes exactly FF539, from 1363–1992 seconds
to 507–1992 seconds. The other 46 selections are unchanged. Sanitized regressions
cover the earlier picks and the market-commentary exclusion.

## BB651: different evidence, no invented recovery

[Run 43685448695](https://github.com/courtjester15/ManaIntel/actions/runs/43685448695)
finished with an empty 19-token extraction response after 20 successful model
calls including timing repair. No 503 caused this empty result. Its selected
1589–2603-second passage starts with a generic question during discussion of a
card's illustration. Full retained text has no Breaking Bulk or matching pick
segment marker, and the closing refers listeners to the patrons' spreadsheet.
This is consistent with a special set-review episode, but retained ASR alone
does not certify that no recommendations exist. Leave needs_review; do not
manufacture picks, declare verified absence or spend an unchanged rerun.

## Why the empty records stayed empty

The pipeline correctly assigned needs_review when the array was empty, but
accepted a null model review reason and wrote no explicit empty-result issue.
Those records skip normal failed-episode retries. The optional cleanup selector
also requires an actionable reason/cohort, and therefore the null explanation
does not initiate source verification. Green workflows verified persistence and
publication of the empty records, not successful recommendation recovery.

Version 0.5.31 records an explicit coverage/intent reason for every new empty
extraction in source summaries, durable state and attempt journals. It does not
approve absence, automatically retry semantic empties or expand provider budgets.

## Validation and bounded continuation

No model/prompt default, retry cap, cooldown, free-tier commitment or approval
policy changed. One FF539 force using the inspected retained transcript is
justified by the corrected evidence selection; keep targeted verification and
normal capacity limits. Inspect its actual output before any further calls.
BB650/652 remain separate inspected-recovery work; do not reset their caps.
BB651 requires source checking, not a speculative model retry.

Private transcripts and numeric replay evidence are protected locally under
`.tmp/zero-investigation/`; no full transcript is committed or published.

Local validation: all 284 tests pass (two Git persistence tests required
subprocess access outside the Windows sandbox); archive validation and all 45
existing evaluation assertions pass. The 47-transcript boundary replay is
read-only and does not certify audio accuracy or missing optional recommendations.
