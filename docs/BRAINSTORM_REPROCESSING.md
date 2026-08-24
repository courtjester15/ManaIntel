# Brainstorm Brewery Reprocessing

This note records the bounded procedure for revisiting Brainstorm Brewery episodes whose published recommendation counts look incomplete or unreliable.

## Candidate priority

Prioritize episodes in this order:

1. Zero-pick episodes produced by an older pipeline version or blocked by a transient transcription failure.
2. One-pick episodes whose detected section is unusually short or predates the hardened Brainstorm boundary detector.
3. Two-pick episodes with medium/low section confidence, a missing end marker, or an older pipeline version.
4. Higher-count episodes only when the review reason identifies likely transcription errors, jokes, or non-card names.

Do not rerun an episode merely because it has a naturally low count. Recent high-confidence results and intentionally non-Magic joke episodes should remain out of the queue unless manual listening finds a concrete problem.

## Cost and scheduling guardrails

- Wait for the scheduled production run to finish before starting a manual rerun.
- Run at most one long full-audio Brainstorm episode per quota day.
- Prefer a retained transcript whenever the matching private Actions artifact is still inside its 14-day retention window.
- A retained-transcript rerun should reuse the exact prior Actions run ID and still force the episode by canonical GUID.
- Stop for the day after a free-tier `429 RESOURCE_EXHAUSTED` response. Do not immediately cycle models or repeat the same full transcription.
- Do not queue several forced reruns behind one another; inspect each result and its before/after artifact first.

## Workflow inputs

Use the `FFW automated archive` workflow with:

- `mode`: `next`
- `batch_size`: `1`
- `source`: `brainstorm-brewery`
- `force_guid`: the exact canonical RSS GUID
- `ai_model`: `gemini-3.5-flash`
- `reuse_transcript_run_id`: the matching prior run ID when its transcript artifact is available; otherwise blank
- `deploy`: enabled

Before dispatching, verify that no production writer is active. After completion, confirm the extracted pick count, archive validation, durable commit, and Pages deployment. Inspect the private reprocessing comparison whenever a previous summary existed.

## Publication safety

Forced reruns preserve the episode's existing durable output directory. If a rerun falls from one or more published picks to zero, the zero-pick publication guard retains the previous picks and marks the episode for review. A nonzero replacement can still change individual picks, so review the before/after artifact for additions, removals, timestamp changes, and suspicious card names.

## Current queue

The queue is intentionally re-evaluated after every run:

1. Episode 697, `brainstorm-brewery:https://brainstormbrewery.com/?p=18925` — two picks, old detector, medium confidence; prefer retained transcript.
2. Episode 711, `brainstorm-brewery:https://brainstormbrewery.com/?p=29150` — zero picks, old detector, medium confidence.
3. Episode 704, `brainstorm-brewery:https://brainstormbrewery.com/?p=24803` — one pick from a long old-detector section.
4. Episode 709, `brainstorm-brewery:https://brainstormbrewery.com/?p=26773` — one pick from a suspiciously short old-detector section.
5. Episode 710, `brainstorm-brewery:https://brainstormbrewery.com/?p=28574` — transcription failed before extraction; use a new full run only when daily quota is clear.

Lower-priority follow-ups are episodes 708 and 703 (long full transcriptions with prior provider/quota failures), then old-detector three-pick episodes whose section windows suggest that only one recommendation block may have been captured.
