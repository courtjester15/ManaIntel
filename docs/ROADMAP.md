# ManaIntel roadmap: 0.6 to 1.0

October 20 local housekeeping: added a preview-first, opt-in scratch cleanup tool and session-end/weekly-while-active working instructions. Fourteen-day inactivity, active/pinned evidence, repositories and filesystem-link guards keep recovery data outside automatic deletion. Reviewed the two clean September worktrees and confirmed their commits are retained before removal (about 10.6 MiB). No runtime/version or production retention change. Next: use marked scratch for disposable experiments; roadmap feature priorities remain unchanged.

Updated October 15, 2026. This is the active roadmap, replacing the maintenance-only/five-hour final-pass plan. There are no release dates or obligation to finish every idea. The goal is a useful little archive that needs very little of Jason's attention.

**Current release: 0.5.15. Next milestone: 0.6 — dependable processing.**

Keep answering: **Who recommended what, when, and why?** MTG Fast Finance and Brainstorm Brewery are the supported sources. Improve the existing Python pipeline, static archive, remote playback and durable overrides before adding infrastructure.

See [Working agreement](WORKING_AGREEMENT.md) for how work is selected and shipped, and [Runbook](RUNBOOK.md) for production operations.

## Existing foundation

Already built: two podcast adapters; bounded processing/backfill/retries; private transcripts/checkpoints; auditable attempts; explicit clock parsing; searchable episode/card views; source/status filters; card images and name resolution; timestamp playback; a review editor and durable overrides; validation/tests; automated persistence and Pages deployment.

These are foundations to improve, not features to rebuild. A successful workflow differs from a faithful extraction. Needs-review output is published uncertainty, not a human-approved result.

## Milestones

| Version | Theme | What Jason should notice |
| --- | --- | --- |
| 0.6 | It runs reliably | Fewer failed episodes; understandable failures and deliberate recovery. |
| 0.7 | Reviewing is easy | Check an odd pick against audio and correct it with little friction. |
| 0.8 | Useful memory | Follow a card's history and return to useful searches. |
| 0.9 | Interesting patterns | See repeat recommendations and overlaps with coverage stated clearly. |
| 1.0 | A dependable small product | Give someone the link and expect them to understand and use it. |

Version numbers follow delivered capability. Patch releases fix the current milestone; minor releases require the evidence below. Documentation edits and ordinary backfill do not earn version bumps. App/pipeline, schema and prompt versions remain separate audit concepts.

## 0.6 — Dependable processing

**Outcome:** Failures usually have an understandable cause and a bounded way forward, without Jason bringing every one to chat.

Work in this order:

1. **R1: Honest health baseline.** Summarize recent attempts by source and deployed version. Separate initial processing, retries, forced experiments, no-ops and deploy-only jobs. Show episode outcomes, review backlog, recurring failure reasons, model-call counts and checkpoint reuse. Start with existing journals; a report can precede a small status-page improvement.
2. **R2: Representative evaluation.** Build on existing tests with small sanitized cases for both shows: content omissions, weak boundaries, ambiguous names and bad clocks. Include lessons from FF 494 and BB 666/667 without committing full private transcripts. Structural correctness and source-content accuracy are separate checks.
3. **R3: Actionable failures.** Improve the existing status view with the last actual attempt, reason, retry/intervention state and next useful action. Distinguish an old displayed failure from a new regression. Preserve token-free static-site retry links.
4. **R4: Deliberate model/prompt changes.** Compare a bounded representative sample before changing defaults. Preserve evidence and known-good results. Use the responding free-tier configuration; avoid repeatedly probing a model already shown unavailable.
5. **R5: Predictable historical progress.** Check that new releases, backfill, retries and the low-pick queue share capacity sensibly. Explain processed coverage and remaining unknowns. An episode-number gap alone does not prove a feed item is missing.

Working release gate:

- Relevant regressions pass; there are no duplicate identities, lost published picks or silent acceptance of missing coverage.
- Report at least ten real non-noop episode attempts across both shows and at least seven days. Initial target: at least nine reach a usable publication. Include failures and show retries separately; do not generate calls just to fill the sample.
- Usable means evidence-backed picks or an explicitly verified no-recommendations disposition. An unexplained empty extraction does not count. Report needs-review publications and independently checked correctness separately.
- Representative source/evidence spot checks document remaining quality limits. Green schema validation alone does not establish accuracy.
- A user can understand a failure and recovery state from the app/runbook. Exact recovery, persistence and deployment have been exercised without damaging prior results.

These are working targets, not an uptime promise. Do not lower them merely to declare the milestone finished. Small clarity/review improvements can proceed while production evidence accumulates; stay on 0.5.x until the gate is met.

## 0.7 — Reviewing is easy

**Outcome:** Check an odd pick, listen nearby and correct it in one short visit.

- Improve the existing review queue by grouping actionable reasons and prioritizing consequential uncertainty.
- Keep audio context visible while checking a card, printing, recommendation or timestamp.
- Make the prepared correction and its before/after effect obvious; support small related batches where useful.
- Distinguish machine output, machine uncertainty and human correction. Preserve original extraction and overrides.
- Improve card/image readability where actual use exposes problems; retain the working static interface.

**Gate:** Demonstrate correct/exclude/add/approve flows; prove rebuild/reprocessing preserve overrides; exercise playback/error fallbacks; show a short before/after walkthrough. Keep the copied-payload/authenticated-workflow boundary unless Jason chooses a different architecture.

## 0.8 — Useful memory

**Outcome:** Understand a card's recommendation history without hunting through episodes.

- Build clearer card timelines over existing canonical resolution and original extracted names.
- Show first/most recent **recorded** recommendations, episode, known contributor, review state and evidence/audio links.
- Add useful filter combinations, shareable filtered URLs and browser-local saved searches.
- Compare the two shows and attributed contributors. A show-level host list does not establish who made a pick; unknown attribution stays unknown.

**Gate:** Representative questions work across both shows; verified name variants do not fragment histories; links retain context; incomplete coverage and missing attribution are labelled. Existing URLs and pick identities remain usable.

## 0.9 — Interesting patterns

**Outcome:** Discover something interesting and inspect exactly what supports it.

- Surface repeat recommendations, cards recommended on both shows and records worth revisiting.
- Compare explicitly attributed changes of position only where the source supports them; preserve both statements.
- Show processed date range, eligible-record count, review-state inclusion and coverage limitations beside each observation.
- Count distinct recommendations/episodes rather than duplicate transcript fragments; make results reproducible from archive data.

**Gate:** Every observation links to contributing records and explains its denominator. Check sparse coverage, uncertain attribution, overrides and duplicate mentions. These are archive observations, not financial-performance scores, investment predictions or source-reliability rankings.

## 1.0 — A dependable small product

**Outcome:** Send a friend the link; they can browse, verify a recommendation and understand uncertainty.

- Clear first-visit explanation, useful empty/error states and readable desktop/mobile browsing.
- An observed operating history with honest dispositions for recurring exceptions.
- Review, playback, search, history and small observation features work together clearly.
- Tested rebuild/export/restore preserves records, overrides, identities and links; private diagnostics retain their documented boundary.
- A concise maintenance guide explains normal operation, credentials, bounded recovery and known limitations.

**Gate:** A documented representative walkthrough, tested rebuild/restore, no unresolved data-loss/publication-corruption defect, and a recent thirty-day operating summary including failures/no-ops/reviews. Full historical coverage, accounts and a database are not prerequisites.

## Current work queue

One improvement batch is active at a time. Production defects interrupt this order.

| ID | Priority | State | Next concrete result |
| --- | --- | --- | --- |
| R1 | Shipped | Complete | Read-only health-report CLI, [baseline](HEALTH_REPORT.md), and reports in processing-workflow summaries/artifacts. Source/version/configuration cohorts, separate experiment/retry denominators, deployment evidence and backlog. |
| R2 | First | In progress | [Evaluation inventory](EVALUATION.md) and offline cross-show boundary/content regressions added. Next: independently checked expected-pick cases for both shows before model/prompt comparison. |
| R3 | Next | Ready | One clear status/recovery UI improvement guided by R1. |
| R4 | Next | Ready | Repeatable bounded model/prompt evaluation using retained evidence. |
| R5 | Active | Bounded rollout | Shared Pacific-day capacity ledger and nightly cleanup implemented in 0.5.15. Inspect queued FF 495/537 pilots and first older boundary cohort; preserve review uncertainty and primary reserve. No-op Pages churn remains separate. |
| 0.7 work | Later | Planned | Choose the next review-friction improvement from actual usage. |
| 0.8–1.0 | Later | Planned | Refine each milestone when earlier foundations support it. |

The October 15 incident fixes shipped in 0.5.10: BB 666 published three picks as needs_review; BB 667 published three as complete. The R1 report shipped in 0.5.11 and adds no inference calls or scheduled development. Its first fourteen-day window contains only five initial attempts (two usable) alongside many forced recoveries; current catalog failures are zero but forty episodes need review. GitHub job reads are bounded, and unobserved deployment outcomes remain unknown. This does not satisfy the sustained-reliability gate. Start the next authorized improvement pass with R2 unless new evidence changes the priority.

R1 follow-ups: inspect the observed no-op Pages churn under R5, and evaluate eight legacy catalog entries missing explicit source IDs without silently guessing attribution. Keep the current health snapshot separate from historical attempts and from independent source-accuracy evaluation. Implementation: `src/ffw/health.py`; validation: `tests/test_health.py`; baseline evidence: `state/health-baseline.json`.

R1 delivery evidence: implementation commit `87ab009`; [production run 38846756441](https://github.com/courtjester15/ManaIntel/actions/runs/38846756441) passed tests, archive validation, the health-summary step, report upload and Pages deployment. Downloaded and inspected `health-38846756441-1` (Markdown plus sanitized JSON; GitHub metadata available, bounded at 60 job reads with zero read errors). Locally, 168 tests ran successfully with three optional PyYAML skips; archive validation passed. No inference calls or episode retries were made for R1. Next authorized batch: R2's compact representative evaluation.

October 16 schedule experiment (0.5.12): shift main triggers to 20:17 / 00:17 UTC, aiming at evening processing after observed scheduler delays. Flash Lite recorded 39 successful and zero failed responses at 22:00–24:00 EDT across eight attempts on four dates; only five attempts produced usable results, and recovery/version selection bias prevents a causal claim. Preserve six-hour cooldown, three-attempt cap, optional-queue gates and free-tier defaults. No inference probes are needed for this change. Follow-up under R5: compare actual call times and episode outcomes after two weeks of ordinary work; UTC triggers shift an hour earlier locally in winter. R2 remains the next feature batch. Shipped as `fddfe7d`; [production verification](https://github.com/courtjester15/ManaIntel/actions/runs/38976982887) passed tests, archive validation, health reporting and Pages deployment. Local suite: 168 tests, three optional-dependency skips. No inference calls or episode recoveries were performed for this schedule-only release.

After a batch, update its state, result, evidence/commit and next action here. Blocked work needs a specific prerequisite; choose independent useful work rather than repeating the same failed attempt.

## Outside this roadmap

Additional sources, generic source-schema migration, live prices, portfolios, performance scoring, alerts, ManaSpec integration, accounts, a hosted database/backend, paid-provider commitments and a large framework/redesign project remain separate product decisions. Limited archive observations in 0.9 are in scope; general market analytics are not.

It is fine to stay on a minor version, skip an unhelpful idea or keep the project quiet between requests. This roadmap creates no scheduled feature-development runs; existing GitHub schedules continue processing episodes.

October 16 R2 first batch: added `tests/test_representative_evaluation.py` and [evaluation inventory](EVALUATION.md). Invented minimal cases cover separated BB recommendation windows, weak endings in both shows, and omitted content despite plausible timing. Existing timing/ambiguous-name/recovery tests are mapped explicitly; private transcripts remain private. No inference calls or runtime/default changes; no version bump. R2 remains in progress pending independently checked expected-pick cases. Delivered as `c2b6358`; [production run 38998021623](https://github.com/courtjester15/ManaIntel/actions/runs/38998021623) passed tests, archive validation, health reporting and Pages deployment. Local suite: 171 tests passed with three optional PyYAML skips; archive validation passed. No episode processing or inference calls were triggered.

October 16 review-automation batch (0.5.13): [40-episode audit](NEEDS_REVIEW_AUDIT.md) guided an independent issue ledger, mixed-reason-safe name verification, out-of-audio clip abstention, and extraction guidance separating source caveats from extraction uncertainty. Added conservative advertised-topic casual handoffs (two topic terms, no new-pick cue), including final-selection language. Transcription cache identity is now separate from extraction prompt identity so extraction-only changes reuse audio evidence. Twelve new semantic/integration regressions cover mixed warnings, valid name-only resolution, audio bounds, boundaries and source caveats. Offline replay resolves FF 495's boundary while four other available snapshots remain uncertain; no blanket status migration. R2/R4 remain in progress: independent source accuracy and broader multi-window/alignment recovery are not established. Next: inspect the bounded FF 495 retained-transcript pilot, then implement quote-to-audio alignment before expanding to old records. Initial implementation `f6fd301`, refinements `d1b5bff`/`86f032a`; [deployment 38999798337](https://github.com/courtjester15/ManaIntel/actions/runs/38999798337) passed. [Pilot 38999890733](https://github.com/courtjester15/ManaIntel/actions/runs/38999890733) reused the retained transcript, resolved FF 495 boundary, retained all four card names, and correctly left timing unresolved. Its less-specific printing output exposed a preservation gap; the 0.5.14 follow-up below fixes it.

Review pilot safety follow-up (0.5.14): forced reprocessing now preserves known printing/foil identities as well as card coverage, including distinct variants and pick multiplicity. Restored FF 495's four original recommendation records/IDs from its retained published baseline, kept the newly supported topic boundary, and recorded the restoration and unresolved timing explicitly. The rejected pilot candidate remains in its private reprocessing artifact. Local full suite: 186 passing with three optional-dependency skips, plus the new end-to-end printing-preservation test passing separately; production suite includes 187 tests. No additional inference attempt was made. Remaining 40-episode backlog has not been mass-approved. Next bounded task: quote/audio alignment and coverage repair using retained evidence, before cohort recovery or relaxing timing gates. Shipped as `de6de66`; [production run 39000225561](https://github.com/courtjester15/ManaIntel/actions/runs/39000225561) passed all 187 tests, archive validation, health reporting and Pages deployment. Verified served Pages JSON: four original FF 495 records, specific Rainbow Foil printing restored, advertised-topic end signal present, needs_review retained. Pilot journal records exactly one successful Flash-Lite extraction call and retained-transcript reuse. Checkout synchronized; no further recovery attempt or automatic approval performed.

October 19 reliability repair batch (0.5.15, validation in progress): inspected private retained FF 537 and BB 663 evidence. FF 537 has suspect chunks 1/2/4; BB 663 has 1/4. FF 495 also exposes a final-chunk overrun relative to stated audio duration missed by the prior detector. Added bounded incremental repair, bounded subdivision of rejected repair clips with durable child checkpoints, unique exact-quote alignment, and stable published identities across timestamp repairs. Original full text and rejected payloads remain private. Shared Pacific-day request reservations include failures, schema fallbacks, extraction and verification; the configured 48-request ceiling is a conservative application budget, not measured provider quota. Optional work reserves sixteen requests for primary work and is capped at sixteen requests/run and two episodes/night. Nightly opportunities move to 04:17/05:17 UTC; rollout remains gated until pilot evidence supports an issue cohort. No blanket review approval. Next: inspect three bounded pilots, enable only demonstrated cohorts, then measure new-review rate and historical backlog separately. Deployment and pilot results pending.

Pilot evidence so far: [release deployment 39358551114](https://github.com/courtjester15/ManaIntel/actions/runs/39358551114) passed production checks and Pages. [BB 663 pilot 39358654854](https://github.com/courtjester15/ManaIntel/actions/runs/39358654854) reused retained evidence, repaired chunks 1/4 and published three recommendations as needs_review; eight new model calls, archive validation and Pages passed. [FF 537 pilot 39359069116](https://github.com/courtjester15/ManaIntel/actions/runs/39359069116) saved a repaired first chunk, then stopped on MAX_TOKENS in a 112.5-second repair clip (nine calls). The changed-input follow-up permits one further subdivision, still under the same eight-call rescue cap, and resumes successful children. No unchanged blind retry, quota probe or blanket approval. Local suite: 198 tests pass, plus the saved-progress scheduling regression and workflow checks. Rollout variables remain disabled pending the next inspected results.

October 19 final bounded outcome: [refinement deployment 39359841739](https://github.com/courtjester15/ManaIntel/actions/runs/39359841739) passed checks and Pages. [FF 537 continuation 39359859403](https://github.com/courtjester15/ManaIntel/actions/runs/39359859403) reused saved work and saved more clips, then stopped on provider 503 after four requests; validation and Pages succeeded but the episode remains failed with no published picks. The shared ledger recorded 28 requests for the outgoing Pacific day (including seven preceding rollout) and a thirty-minute provider cooldown ending 03:09 UTC October 20. No new calls were made during that stop. BB 663's three picks were verified in served Pages JSON; timing remains unresolved. FF 495 was not live-attempted in this session because the provider stop applied first.

Final follow-up: cache-aware older-record selection with bounded fresh fallback (all 27 older-than-fourteen-day review records lack retained files), saved-checkpoint progress accounting, exact inspected-pilot dispositions and independent review/publication outcomes. Local full suite: 199 tests pass, archive validation passes. Offline production-state preview selects the FF 495 timing-review pilot first. The durable queue records that pilot (three cohort attempts maximum) and one additional FF 537 retained-progress recovery; the latter is an inspected exception after its exhausted ordinary attempts, not a reopened global retry gate. Each continuation still needs new saved progress. Enable the nightly timing/boundary trial and future scheduled incremental processing after final deployment verification. Next: inspect actual pilot/review outcomes and first older boundary cohort, then expand consumption only if verified useful throughput supports it. No under-10% review claim, source-accuracy claim, mass approval, paid-provider use or quota-cap increase was made.

Rollout verified: final implementation `6fe4823`; [production 39361221335](https://github.com/courtjester15/ManaIntel/actions/runs/39361221335) passed the 199-test suite, archive validation and Pages deployment. Repository variables now enable `FFW_CLEANUP_ENABLED=true`, `FFW_CLEANUP_ISSUES=timing,boundary` and future scheduled incremental repair. [Cleanup verification 39361222070](https://github.com/courtjester15/ManaIntel/actions/runs/39361222070) passed tests/preflight, honored the outside-nightly-window stop, made no episode attempt or inference request and left the shared count at 28. The preceding rollout check caught an inherited-cohort test-fixture leak before processing; fixture/workflow test environments were isolated and the corrected runtime check passed. Saved-progress budget deferrals are summarized explicitly rather than reported as blocked failures; attempt outcomes remain independently recorded. Public Pages JSON verified version 0.5.15, BB 663 three needs-review picks, FF 537 failed/zero picks, and FF 495's four existing needs-review picks retained. FF 495's apparent overrun is relative to the stated duration; its actual audio alignment remains to be checked by the queued pilot. Next action belongs to the bounded nightly queue, with no further live calls made during provider cooldown. Neither pending recovery nor review reduction is claimed complete.


October 20 owner-requested reliability fixes (0.5.16, verification in progress): removed the optional clock cutoff that discarded delayed cleanup run 39400708326 at 05:26 EDT. Per-request daily limits, primary reserve, cooldowns and two cleanup episodes/day remain. Fixed sticky timing debt: record affected original chunks, use the latest successful repair to clear that chunk, and distinguish <=one second validated final-endpoint rounding from material clock correction. Legacy unknown corrections remain conservative; ambiguous names, boundaries, missing content and identity preservation remain gated. Regression checks include delayed selection with capacity enforcement, latest-repair precedence, small endpoint rounding and clearing a repaired episode's historical warning. Next: deploy and inspect FF 537 saved-progress recovery and bounded cross-show review pilots; report actual dispositions separately from deployment.

Release deployment [39537516659](https://github.com/courtjester15/ManaIntel/actions/runs/39537516659) passed production checks and Pages. Local full suite: 203 tests pass, archive validation passes. [FF 537 recovery 39537535091](https://github.com/courtjester15/ManaIntel/actions/runs/39537535091) saved clean repairs of chunks 2/4 with nine calls; one suspect chunk remains. A concurrent owner housekeeping commit caused its state push to be rejected. Recovered its journal and charged requests from retained artifacts; private checkpoints/transcripts remain available for continuation. Follow-up rebuilds adjusted legacy repair parents from saved children, with no calls when all children are retained. Actual observed final endpoint rounding (0.360/0.398 seconds) motivates the one-second rounding bound; >one-second corrections remain reviewable. No existing review record is blanket-approved.
