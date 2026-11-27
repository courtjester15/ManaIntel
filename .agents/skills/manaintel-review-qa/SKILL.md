---
name: manaintel-review-qa
description: Verify changes to ManaIntel review editing, listening controls, correction payloads or the review workbench.
---

Start with [review workbench checks](../../../docs/RUNBOOK.md#verify-the-review-workbench). Use synthetic inputs to exercise the same user action before and after the change. Check the timestamp and pick sent to the player, and the decision and revision in the payload. Use Codex's in-app browser for rendered checks. Record starting state, viewport, action and result where relevant. Record native playback separately from JavaScript event coverage.
