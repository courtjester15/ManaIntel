# Hands-off development working agreement

Updated October 15, 2026. Jason usually browses cards and reports something odd, or asks what would improve the app. The agent owns investigation, technical choices, implementation, verification and routine deployment. Jason does not need to supply a ticket, a GUID, a technical diagnosis or a detailed feature specification.

## Starting a work session

| Owner message | Agent response |
| --- | --- |
| An episode/card/screenshot looks wrong | Find the record, inspect production/source evidence, diagnose it and fix the demonstrated problem. |
| “What should we improve?” | Recommend the best next improvement from current evidence and the roadmap. A request for ideas alone does not authorize shipping an unrelated feature. |
| “Improve it,” “pick something,” or approval to run with a recommendation | Choose one useful roadmap batch and carry it through deployment and verification. |
| “Keep going” | Reassess health and the queue, then choose the next bounded batch. |

This is standing guidance for authorized sessions. It does not create a recurring development automation or change episode-processing schedules. A future scheduled maintenance worker needs its own concrete scope, cadence and budget.

## Choosing the work

Read `AGENTS.md`, the roadmap queue, relevant incidents, Git status and current production evidence. Check what is already implemented before proposing a new feature.

Prioritize:

1. Lost/corrupted data, broken publication or evidence falsely presented as certain.
2. Recurring processing failures and wrong/missing recommendations.
3. Confusing status, review, playback or card-reading friction.
4. The next small capability in the active milestone.

Choose a concrete visible or operational result with a way to verify it. Finish one cohesive improvement per pass, or a few closely related fixes. Do not turn “improve it” into an unbounded march through the roadmap. Avoid infrastructure or abstraction the problem does not need.

State the chosen problem, why it has priority and what success looks like. Routine technical/UI choices belong to the agent and do not require a requirements interview.

## Investigating before spending calls

- Separate episode outcome, workflow outcome, archive validation and Pages deployment.
- Compare source versions and attempts; distinguish an old displayed failure from a new regression.
- Inspect retained transcripts/checkpoints, numeric diagnostics and source evidence where available. Valid JSON and green tests do not establish accurate transcription.
- Prefer offline reproduction and retained evidence. Use a small representative live check when provider-dependent behavior changes.
- Run one bounded recovery at a time and inspect its result. Further attempts need changed inputs, a demonstrated correction or newly useful saved progress; do not repeat an unchanged deterministic failure.
- Keep cooldown, quota and repair limits. Stop after free-tier quota exhaustion. Inspect evidence before overriding manual-review gates and record the reason for the selected budget.
- Preserve successful repairs and previously published picks through later failures. Do not rerun historical queues merely because a new version exists or a count looks low.

The [runbook](RUNBOOK.md) and [Brainstorm recovery notes](BRAINSTORM_REPROCESSING.md) provide operational detail. Current checked-in workflow defaults take precedence over stale model names in historical incident notes.

## Shipping end to end

1. Synchronize the remote without discarding production archive/state or unrelated local work.
2. Implement the smallest coherent improvement. Preserve source evidence, identities, links and human overrides.
3. Run appropriate checks: meaningful regressions for demonstrated behavior, archive validation for data changes, and browser/visual checks for UI behavior/readability. Avoid tests that merely restate trivial implementation details.
4. For model/prompt changes, evaluate bounded representative evidence before making a broad reliability claim. Keep transcripts/rejections private; commit only appropriate sanitized fixtures and compact evidence.
5. Update release metadata when behavior changes, and update the queue/runbook where relevant.
6. Before pushing, inspect active production writers. Do not race a workflow's durable-state commit; synchronize again after it finishes.
7. Commit and push the authorized change. Routine production deployment is part of the work, without another approval round.
8. Verify production checks and Pages publication for site/pipeline changes. A documentation-only commit does not need a redundant Pages run when its paths are not published.
9. For recovery, check actual episode/pick/review outcomes as well as the workflow.

Leave the checkout synchronized and explain any remaining local work. Failed deployment means the task remains open for investigation, not “done locally.”

## Keeping Jason's input small

Resolve routine implementation, naming, layout, tests and deployment choices independently. Preserve ambiguous source claims as needs_review rather than asking Jason to validate every pick or silently approving them.

Bring a decision to Jason when it materially changes the agreed product: new recurring spending/accounts, supported sources, public/private retention scope, a destructive/incompatible migration or a substantial architecture/scope change. Prepare evidence and a recommended concrete option first, and explain why his decision is needed. This roadmap does not authorize those expansions.

## Reporting results

Keep the report short: what changed and why, what was checked, actual deployment outcome/link, unresolved limitations/review state, and a useful next action. Show visual results when helpful. For incidents, explain the actual cause and episode outcomes. Avoid an implementation diary or a claim that deployed means every extraction is correct.

## Versions and progress

Versioning began at 0.1.0 on July 14, 2026. It lets an episode be traced to the code that processed it.

- Patch: a shipped fix/small improvement within a milestone; package and pipeline versions stay aligned.
- Minor: a roadmap capability whose acceptance evidence is satisfied.
- 1.0: a dependable, understandable small product with the documented operating history and recovery procedures.
- Schema: the data contract; change it for contract changes, not merely an app milestone.
- Prompt/cache identity: distinguish extraction-policy and transcription behavior that could invalidate reused output.

Documentation-only edits, generated backfill and time passing do not earn version bumps. A short live validation does not establish sustained reliability; record the sample and limitations honestly.

## Durable handoff

After a pass, update the roadmap with item/state, result and evidence/commit, remaining uncertainty and next action. Mark milestones complete only when their gates are met. When progress depends on naturally accumulating evidence, record that dependency and choose independent useful work; do not manufacture live runs to satisfy a release checklist.
