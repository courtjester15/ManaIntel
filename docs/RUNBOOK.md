# FFW Production Runbook

## Automated service

GitHub Actions runs `.github/workflows/ffw.yml` at 10:17 UTC for fresh backfill and at 20:17 UTC for bounded failed recovery. It reads both public podcast feeds:

`https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss`

`https://feeds.feedburner.com/brainstormbrewerypodcast`

The production stages are feed discovery, eligibility-first selection, durable queueing, streamed temporary download, ffmpeg normalization/splitting, provider transcription, Cards to Watch boundary detection, schema-constrained extraction, validation, bot commit, and Pages deployment. The checked-in workflow selects Gemini `gemini-3.5-flash` for transcription and extraction. Transcription retries transient primary-model failures after 30 and 60 seconds, then uses `gemini-3.5-flash-lite`, then uses OpenAI `gpt-4o-transcribe-diarize` when `OPENAI_API_KEY` is available. All provider fallbacks happen inside one durable episode attempt.

Before publication, `FFW_TARGETED_VERIFICATION_ENABLED=true` permits up to `FFW_TARGETED_VERIFICATION_MAX_PICKS` focused second-listen checks for card-name/transcription ambiguities. Each check sends only a short excerpt around the pick timestamp. A correction is accepted only when the second listen supplies a name that Scryfall verifies exactly; unavailable verification remains non-fatal and the pick stays in review. Printing and foil ambiguity is not auto-approved.

After a successful episode attempt, ManaIntel checks up to `FFW_CARD_RESOLUTION_BATCH_SIZE` uncached card names against Scryfall. Exact matches are projected as canonical names; fuzzy matches are only review suggestions. Resolution failures do not fail podcast ingestion. Run `python -m ffw resolve-cards --limit N` for an explicit historical sweep or add `--refresh` after a resolver-version change.

MTG Fast Finance boundary detection is bidirectional. Show-outline mentions of Cards to Watch do not count as a section start, regardless of when the agenda occurs; when multiple markers remain, the marker most closely followed by recommendation language wins. A separate pick-wrap phrase or structural transition into the weekly feature named by the episode title/show notes supplies end evidence only after pick language has occurred. Independent ending evidence improves section confidence; without it, extraction is conservatively capped at 20 minutes after the trusted start and remains a diagnostic warning when extraction still yields approved picks. Transcript sequence, not provider timestamps, owns structural ordering because malformed chunk timestamps can collapse at a chunk boundary. A weak start, missing section, empty extraction, or pick-level ambiguity remains `needs_review`, and a generic topic word inside a pick discussion is not sufficient to close the section.

One concurrency group serializes all writers. The 10:17 UTC `next` run scans newest to oldest and processes at most one untouched eligible episode. `complete`, `needs_review`, and `failed` records skip before download or provider calls, so new releases take priority. The 20:17 UTC `retry_then_next` run selects at most one episode: the newest due retry first, otherwise the newest untouched episode across both feeds. Both automatic runs therefore advance the same newest-to-oldest cursor and exclude episodes older than `FFW_AUTOMATIC_MAX_EPISODE_AGE_DAYS` (365 by default). It never attempts both. Retryable errors cool down for six hours and stop after three total episode attempts. A runner crash after an external API response but before the next durable Git commit can cause a repeated API call; file-backed Git state cannot guarantee exactly-once external billing.

## One-time GitHub setup

1. Open the repository, then **Settings -> Secrets and variables -> Actions -> New repository secret**. For the temporary Gemini validation provider, name it exactly `GEMINI_API_KEY` and paste a valid Google AI Studio API key. For the OpenAI provider, name it exactly `OPENAI_API_KEY` and paste a valid OpenAI API key.
2. Open **Settings → Actions → General → Workflow permissions**. Select **Read and write permissions**, then save.
3. Open **Settings → Pages → Build and deployment → Source**. Select **GitHub Actions**.
4. If GitHub pauses the first deployment, open **Actions → FFW automated archive → the waiting run → Review deployments**, approve `github-pages`, and continue.

## Controlled live validation

Manual live runs are intentionally capped. For one Brainstorm Brewery episode, use `next`, `source=brainstorm-brewery`, `batch_size=1`, leave `force_guid` blank, and set `deploy=true`. The workflow rejects zero, blank, negative, and over-cap batch sizes so a manual run cannot accidentally process the full RSS feed. The limit counts eligible episodes after durable-state filtering, not the newest feed positions.

The first Gemini validation attempt used `gemini-2.5-flash`, which returned `404 NOT_FOUND` for this key because that model was not available to new users. That run also demonstrated why provider-wide failures must stop the batch: the old `episode_limit=0` default meant "all episodes" and published roughly 500 failed live records. The archive/state cleanup commit removes those generated failure records and keeps the synthetic fixture archive only.

Provider-wide failures include missing or invalid keys, unavailable models, quota exhaustion, transient provider capacity, and provider schema capability errors. They stop the current batch so one outage does not burn through multiple episodes. Missing credentials, unsupported models, and incompatible schemas are non-retryable configuration failures. During transcription, quota (`429`), disconnect, timeout, and `5xx` errors receive one short retry on the primary model and one request on the configured fallback model. If both models fail, the episode remains retryable after the normal cooldown. Episode-specific bad input, such as oversized or empty audio, is quarantined and does not stop unrelated work.

The fallback uses the existing `GEMINI_API_KEY`; it requires no second account or repository secret. `FFW_TRANSCRIPTION_FALLBACK_MODEL` disables fallback when blank. `FFW_GEMINI_TRANSIENT_RETRIES` and `FFW_GEMINI_RETRY_DELAY_SECONDS` control primary-model retries and delay. Successful state records retain the actual model for every chunk, including mixed-model transcripts.

Never put the API key in `.env.example`, state, archive output, workflow inputs, issue text, or logs.

## Controlled historical backfill

Open **Actions → FFW automated archive → Run workflow** and choose:

- mode: `backfill`
- batch_size: `3`
- force_guid: blank
- deploy: enabled

The job attempts all three sequentially, validates the production-only catalog, commits durable changes with `chore(ffw): publish automated episode updates`, and deploys the site. A partial episode failure remains visible in processing status and the run summary.

## Recovery

- Process one next eligible episode: dispatch `next` with `batch_size=1`.
- Process one source only: dispatch `next`, choose `mtg-fast-finance` or `brainstorm-brewery` in `source`, and keep `batch_size=1`.
- Process a controlled eligible batch: dispatch `backfill` with `batch_size` from 1 through 20.
- Use the bounded evening slot manually: dispatch `evening`; it retries one due failure or, if none is due, processes the newest untouched episode inside the automatic age window. It never does both.
- Retry failed episodes only: manually dispatch `retry_failed` with a `batch_size` from 1 through 20. Cooldowns and the three-attempt cap still apply.
- Force one episode: choose any processing mode and provide its exact RSS GUID in `force_guid`; the override searches the full fetched feed and bypasses batch position limits.
- Validate locally: set `FFW_MODE=live`, then run `python -m ffw validate`.
- Rebuild production projections locally: set `FFW_MODE=live`, then run `python -m ffw render`.
- Inspect workflow health: open **Actions → FFW automated archive**. The publish summary reports selector counts, attempts, outcomes, and whether durable outputs changed. Deployment outcome is reported separately by the deployment job.

## Verify a no-op run

1. Confirm the next candidate is already terminal or there are no eligible feed records for the chosen policy.
2. Dispatch `next` with `batch_size=1` and leave `force_guid` blank.
3. In the run summary, verify `Selected: 0`, `Attempted: 0`, and `Durable outputs changed: false`.
4. Verify `git status` remains clean after pulling the workflow result.
5. Confirm the **Decide Pages publication** step reports `ready=false` and that Pages upload/deployment are skipped. A changed, validated failure record should instead report `ready=true` and deploy the current failure status even though the publish job ultimately reports the pipeline failure.

## Human review workflow

The static site intentionally contains no repository credential. It prepares a compact payload for the authenticated review workflow:

1. Open a needs-review episode and select **Review episode**.
2. Leave valid picks on **Keep**, or choose **Exclude** or **Correct**. Add any omitted picks under **Missing picks**.
3. Optionally add a review note, then choose **Prepare review payload** and **Copy payload**.
4. Choose **Open review workflow**, select **Run workflow**, paste the payload into `review_payload`, and leave deployment enabled.
5. The workflow records the GitHub actor, rejects stale or malformed payloads, runs the test and validation suites, writes the durable file under `data/reviews/<source-id>/`, rebuilds effective projections, commits both, and deploys Pages.
6. Confirm the episode now shows **human reviewed** and that its effective summary contains the intended picks.

For local maintenance, run `python -m ffw apply-review --payload '<json>' --actor '<name>'`. This performs the same durable write and projection rebuild; validate before committing.

The original `summary.json` and `summary.md` are immutable machine output. Reviewed output is written to `effective.json` and `effective.md`; normal catalog and summary views prefer those effective files. Malformed or stale reviews must stop validation with a readable error. Never work around validation by editing `archive/index.json`, `archive/cards.json`, or generated Markdown directly.

## Timestamp playback and review listening

- Use **Listen to Cards to Watch** from an episode, or **Listen** on a specific pick. Episode links choose the earliest extracted pick; pick links preserve both `t=<seconds>` and `pick=<id>`.
- The summary and review pages share the same player. In review, each extracted or newly added pick can seek using the timestamp currently entered in its editor.
- Open the episode URL with `t=<seconds>` and optionally `pick=<id>` to share or verify specific context.
- If it does not seek immediately, wait for media metadata; seeking before `loadedmetadata` is not reliable.
- If autoplay is blocked, press Play once. This is expected browser behavior.
- If the enclosure host rejects seeking or byte ranges, use the displayed original episode link.
- If the enclosure URL is missing, expired, or redirected unsuccessfully, verify the current RSS entry before changing archive data.
- Do not download, commit, proxy, or mirror the podcast audio as a workaround.

## Retry one exact episode

The exact-episode backend is already available:

```bash
python -m ffw run --live --force-guid <rss-guid>
```

In GitHub Actions, choose a normal processing mode, enter the exact canonical GUID in `force_guid`, keep `batch_size=1`, and dispatch. Exact GUID selection searches the full fetched feed and processes only that episode, even when it is quarantined. Manual dispatches can select `gemini-3.5-flash-lite` in `ai_model` when the primary model's per-model quota is exhausted; scheduled runs retain `gemini-3.5-flash` as the default. To retry extraction without paying to transcribe again, enter the prior Actions run ID in `reuse_transcript_run_id`; the workflow downloads that run's private transcript artifact, verifies its episode GUID, and fails closed if it is missing or mismatched. Failed episode details in the static UI provide **Copy retry GUID** and **Open retry workflow** buttons. The UI intentionally contains no GitHub token and cannot dispatch an authenticated run itself.

## Retention and cost

Raw MP3s and normalized chunks remain disposable in `.ffw-work/`. When `FFW_RETAIN_TRANSCRIPTS=true`, the pipeline writes compressed full timestamped transcripts under `.ffw-work/transcripts/`; the production workflow uploads them as private Actions artifacts with 14-day retention. Transcripts are never committed or copied to Pages. Forced episode reruns also retain the previous summary and a compact before/after comparison as private 14-day workflow artifacts, allowing the replacement to be evaluated without manual transcription diffing. A forced rerun that falls from one or more published picks to zero cannot erase the previous recommendations: the prior picks remain published, the episode returns to `needs_review`, and the rejected comparison records the publication guard. Published records retain only source metadata, timestamps, short evidence excerpts, model/version audit data, JSON, and Markdown.

A missing recommendation-section ending remains visible in section metadata but does not by itself require editorial review when all extracted picks are approved. Missing sections, empty extraction, and pick-level ambiguity still produce `needs_review`. Gemini segment timestamps are bounded to their source chunk and the count of timing corrections is retained in transcription metadata.

The OpenAI API may return token usage for extraction, but transcription usage availability varies by response. The pipeline records provider/model/chunk/duration metadata when available and does not fabricate a cost estimate. Monitor actual spend in the OpenAI API usage dashboard.
