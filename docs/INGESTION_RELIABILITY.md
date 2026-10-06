# Ingestion reliability and attempt history

## Changes

- Transient transport exceptions, including incomplete chunked reads, use retry/fallback.
- An output-limit response skips repeating the identical model/chunk. If model fallback is exhausted with MAX_TOKENS, one chunk per episode attempt may be split into two halves. Each half has one model call, no schema downgrade/fallback retries, and its own private checkpoint. There is no recursive splitting. Subsequent runs resume an existing split plan without first requesting the failing parent again.
- Gemini SDK HTTP retries are disabled; the application's bounded retries own recovery. HttpRetryOptions.attempts=1 disables SDK retries, as documented in [the SDK's type definitions](https://github.com/googleapis/python-genai/blob/v1.50.0/google/genai/types.py). The minimum supported SDK version is now 1.50.
- Both ingestion workflows share the existing checkpoint cache identity. Retained transcripts use a separate private cache; old checkpoint-cache compatibility is preserved.
- Matching retained transcripts can be reused automatically when their episode GUID, audio URL and prompt version match. They still require audio preparation for targeted verification. This is not an audio-content-hash guarantee; use fresh transcription when the source audio has changed at the same URL.
- Preflight archive validation runs before provider work. A live CLI run also preflights an existing catalog when it has selected episodes. An empty new archive may bootstrap; workflows expect an existing valid production archive.
- Failed forced reruns restore the previous summary, Markdown and metadata, including failures partway through publication. Published state remains successful while last_attempt_error records the unsuccessful redo. The command still returns a failed attempt.
- Attempt evidence is uploaded and committed even if archive validation fails. Invalid episode/catalog changes are not committed or deployed. Inspect the workflow for the actual commit/deployment result; a local output write is not proof of publication.
- The deployed queue gate/low-pick policy and confirmed-no-recommendations validator compatibility fix were carried into this older local checkout to avoid regressing them.
- Atomic file replacement retries brief Windows scanner locks for at most 0.3 seconds. Other permission errors still fail immediately.

## Where to look

- state/episode-attempts.md: generated short bullets for episodes and workflow outcomes.
- state/attempts/<attempt-id>.json: detailed metadata-only record, one unique file per attempt.
- state/runs/<run-id>-<run-attempt>.json: workflow preflight, selection/no-op, pipeline exit and archive-validation outcome.
- GitHub run links and attempts-<run>-<attempt> artifacts: evidence when Git persistence itself fails.

Each attempt includes episode identity, timestamps, prior status/attempt count, model configuration, code SHA, prompt/pipeline version, stages, observed model calls, available usage/finish reason/response length, checkpoint reuse/invalidation, extraction counts/review metadata, recovery action and outcome. Successful retries and ordinary passes are both retained. Unknown values remain null rather than invented. Existing history is not silently interpreted as complete attempt history.

The journal has no audio, full transcripts or raw model response bodies. Error messages are bounded and known credential patterns/environment values are redacted. Treat operator notes as public repository metadata: never enter credentials or private transcript excerpts.

Records are updated during their attempt, then finalized. Earlier attempt files are not overwritten by subsequent attempts; workflow finalization adds validation context to the matching run/attempt only. GitHub ingestion workflows use the same writer concurrency group. Concurrent local writers against one state/archive remain unsupported; unique journal filenames do not make the underlying shared state store multiwriter-safe.

## Recovery controls

Manual main-workflow dispatch adds:

- attempt_note: a short reason for an intervention, e.g. “Fresh transcription after source audio correction.”
- fresh_transcript: bypass automatic retained-transcript reuse. Existing explicitly requested reuse_transcript_run_id remains authoritative; leave it empty for fresh transcription.

Local equivalents are FFW_ATTEMPT_NOTE and FFW_AUTO_REUSE_TRANSCRIPTS=true.
Private Actions transcript artifacts retain the existing 14-day setting; caches have Actions' separate eviction policy and are not guaranteed permanent storage. Model/prompt/audio fingerprint changes invalidate chunk checkpoints and are recorded. MAX_TOKENS rescue is a bounded opportunity, not a promise of recovery.

## How to use the evidence

Separate provider failures, output-limit/JSON failures, section/extraction quality, validation failures and persistence/deployment failures. Compare ordinary passes against recovered episodes. A later retry succeeding is not automatically a verified code fix. Review the artifact and intervention before attributing cause.

Recommendation quality still needs spot-checks against source audio/transcripts; a green run or a larger pick count alone is not an accuracy metric. No paid-provider change or global chunk-size reduction is included.

## Verification and rollout

Install the test extra with python -m pip install -e ".[test]" and run
python -m unittest discover -s tests -v. Tests cover the actual transport wording,
typed transport errors, composite failures, split limits/timestamps/checkpoint resume,
failed-redo rollback, pass/skip journaling, redaction, validation evidence, preflight,
Windows locks, YAML parsing and embedded workflow Python syntax.

The deployment patch was reconciled in an isolated checkout of current production,
without including unrelated local review/UI edits. All 115 network-free tests and
production archive validation passed before publication. Inspect the first ordinary
run's journal, cache steps, validation and Git persistence. No historical failed
episode was dispatched as part of implementing this patch.
