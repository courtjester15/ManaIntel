# 2026-07-20 — Bounded Retry and Backfill Reliability

## Why this pass happened

The scheduled run [29685070228](https://github.com/courtjester15/ManaIntel/actions/runs/29685070228) selected episode 527, downloaded and prepared its audio, then failed during Gemini transcription with `Server disconnected without sending a response.` The durable failure record was correctly committed, but Pages did not deploy because the pipeline failed.

The run summary also reported 500 feed entries scanned and 497 eligible. Only one episode was selected and attempted; the selector had classified the entire RSS window before slicing to one. The expensive audio/model work was already limited to one episode, but the summary made that fact unnecessarily hard to see.

## Diagnosis

- Episode 527 did not fail during RSS discovery, download, or ffmpeg preparation.
- The failure occurred inside Gemini transcription. The old diagnostic did not identify the failed audio chunk.
- A disconnect is a transient provider/transport failure, not evidence that the episode is permanently broken.
- Gemini quota failures should arrive as `429 RESOURCE_EXHAUSTED`. Exact project/model quotas are visible in Google AI Studio and cannot be inferred from a generic public free-tier number.
- The existing `next` policy deliberately skipped failed records, while `retry_failed` required manual dispatch. That allowed backfill to continue but provided no unattended recovery.

## Implemented policy

The pipeline is now version 0.3.0.

1. The 10:17 UTC schedule runs `next` and guarantees progress on one untouched episode. Failed records never consume this fresh-backfill slot.
2. The 20:17 UTC schedule runs `retry_failed` and attempts at most one due transient failure.
3. Retryable failures receive a six-hour cooldown and a maximum of three total episode attempts.
4. A third failed attempt becomes non-retryable/quarantined instead of running forever.
5. `429`, disconnect, timeout, `408`, and `5xx` failures are transient. They stop the current provider-wide batch but remain eligible for a later scheduled retry.
6. Invalid credentials, unavailable/unsupported models, and schema capability errors stop the provider batch and are not retried per episode.
7. Broken or oversized episode audio is quarantined as episode-specific input failure, allowing other work to continue.
8. Unknown failures receive bounded retries because model output failures can be intermittent; the attempt cap prevents an infinite loop.

This produces the intended sequence for episode 527: its existing failure counts as attempt one; the later retry can make attempt two; the next morning still advances to the next untouched episode; and the following later retry can make the final attempt if needed.

## Observability and cost controls

- `Feed entries scanned` now counts distinct entries actually examined before the requested selection is satisfied. Exact-GUID searches still inspect the full feed when necessary.
- Gemini transcription failures record the failed chunk number, total chunk count, exception type, and request duration.
- Successful chunks record audio seconds, request duration, and provider usage metadata.
- Workflow summaries report deferred retries and exhausted/quarantined records.
- The workflow pins `gemini-3.5-flash` instead of the moving `gemini-flash-latest` alias.
- `FFW_MAX_EPISODE_ATTEMPTS` and `FFW_RETRY_COOLDOWN_HOURS` remain configurable, with defaults of 3 and 6.

## Deliberately deferred

Cross-run chunk checkpointing was not added. Making it durable on disposable GitHub runners would require committing raw transcript fragments or adding external storage, which changes the existing transcript-retention policy. The review/correction UI also remains a separate pass.

## Verification

- 36 unit tests passed.
- Python compilation passed for the modified package modules.
- Production archive validation passed with no issues.
- `git diff --check` passed.

## Pete handoff

On the first live day after deployment, check both workflow summaries:

- The morning run should use selector policy `next` and attempt one fresh episode.
- The later run should use selector policy `failed_only` and either retry one due failure or make a clean no-op.
- A repeated episode 527 failure should now name the exact Gemini chunk and attempt count.
- A quota failure should be categorized as transient and scheduled later, not permanently discarded.
- After three total failures, the episode should remain visible as quarantined while morning historical backfill continues.

