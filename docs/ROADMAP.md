# ManaIntel roadmap: 0.6 to 1.0

Updated October 15, 2026. This is the active roadmap, replacing the maintenance-only/five-hour final-pass plan. There are no release dates or obligation to finish every idea. The goal is a useful little archive that needs very little of Jason's attention.

**Current release: 0.5.12. Next milestone: 0.6 — dependable processing.**

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
| R5 | Next | Ready | Check backfill/recovery fairness and publication churn: R1 observed no-op runs deploying Pages. |
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

October 16 R2 first batch: added `tests/test_representative_evaluation.py` and [evaluation inventory](EVALUATION.md). Invented minimal cases cover separated BB recommendation windows, weak endings in both shows, and omitted content despite plausible timing. Existing timing/ambiguous-name/recovery tests are mapped explicitly; private transcripts remain private. No inference calls or runtime/default changes; no version bump. R2 remains in progress pending independently checked expected-pick cases. Deployment verification is recorded below after CI.
