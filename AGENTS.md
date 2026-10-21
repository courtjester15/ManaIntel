# Project working agreement

For routine ManaIntel fixes requested by the owner, carry the work through implementation, appropriate tests, commit, push to the production branch, and verification of the GitHub Actions/Pages deployment. Deployment is part of completing the fix; do not stop at local changes or ask again for approval already given for that work.

Preserve current production archive/state changes when synchronizing with the remote. Keep live recovery attempts bounded, inspect retained evidence before overriding manual-review gates, and report actual deployment and episode outcomes clearly.

## Local scratch housekeeping

At the end of each work session, run `python tools/clean_scratch.py`, review the preview, then run it with `--apply`. This also sweeps old scratch whenever the repository is used; no background scheduler is required. Use a direct child of `.tmp/` or `.test-work/` for disposable experiments and add `.disposable` only after confirming there is no unique evidence to preserve. The sweep requires fourteen days of inactivity. Remove newly created disposable work immediately after verification where practical. A `.keep` or `.active` file anywhere in a folder protects it; remove `.active` only when the work finishes. Never mark an active task disposable without also protecting it.

Never age-delete `.ffw-work/`, archive/state data, transcripts or checkpoints. Review incident evidence before removing it. Clean Git worktrees with `git worktree remove` only after checking for local changes and confirming their commits are retained. See `docs/LOCAL_CLEANUP.md`.

## Active roadmap and owner involvement

Read `docs/ROADMAP.md` and `docs/WORKING_AGREEMENT.md` before selecting improvements. The October 15, 2026 roadmap supersedes the old maintenance-only/five-hour final-pass restriction. Current focus: 0.6 reliability. R1 health reporting is shipped in 0.5.11; the next ready improvement is R2 unless production evidence changes the priority.

For an authorized open-ended improvement pass, choose one useful bounded task from evidence and the queue. Own routine technical/product choices, implementation, checks, commit, push and deployment verification. A request for suggestions alone calls for recommendations; do not start unrelated feature work or create recurring automations without authorization.

Protect the two-show static-archive scope and free-tier operation. New spending/accounts, sources, retention scope, destructive/incompatible migrations or major architecture changes need an owner decision with a concrete recommendation. Preserve uncertainty rather than inventing source claims or automatically approving ambiguous picks.

Check active production writers before pushing; do not race a workflow's archive/state commit. Finish by updating the roadmap queue with results and next action. Documentation-only edits need no version bump or redundant Pages deployment.
