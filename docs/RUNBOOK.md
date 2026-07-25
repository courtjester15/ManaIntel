# FFW Production Runbook

## Automated service

GitHub Actions runs `.github/workflows/ffw.yml` at 10:17 UTC for fresh backfill and at 20:17 UTC for bounded failed recovery. It reads the official MTG Fast Finance feed:

`https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss`

The production stages are feed discovery, eligibility-first selection, durable queueing, streamed temporary download, ffmpeg normalization/splitting, provider transcription, Cards to Watch boundary detection, schema-constrained extraction, validation, bot commit, and Pages deployment. The checked-in workflow selects Gemini `gemini-3.5-flash` for transcription and extraction. Transcription retries one transient primary-model failure after two seconds, then uses `gemini-3.5-flash-lite` as a same-key fallback. OpenAI remains an environment-selectable adapter.

One concurrency group serializes all writers. The 10:17 UTC `next` run scans newest to oldest and processes at most one untouched eligible episode. `complete`, `needs_review`, and `failed` records skip before download or provider calls, so new releases take priority and historical backfill resumes automatically. The 20:17 UTC `failed_only` run retries at most one due transient failure. Retryable errors cool down for six hours and stop after three total episode attempts. A runner crash after an external API response but before the next durable Git commit can cause a repeated API call; file-backed Git state cannot guarantee exactly-once external billing.

## One-time GitHub setup

1. Open the repository, then **Settings -> Secrets and variables -> Actions -> New repository secret**. For the temporary Gemini validation provider, name it exactly `GEMINI_API_KEY` and paste a valid Google AI Studio API key. For the OpenAI provider, name it exactly `OPENAI_API_KEY` and paste a valid OpenAI API key.
2. Open **Settings → Actions → General → Workflow permissions**. Select **Read and write permissions**, then save.
3. Open **Settings → Pages → Build and deployment → Source**. Select **GitHub Actions**.
4. If GitHub pauses the first deployment, open **Actions → FFW automated archive → the waiting run → Review deployments**, approve `github-pages`, and continue.

## Controlled live validation

Manual live runs are intentionally capped. For the first historical episode, use `backfill`, `batch_size=1`, leave `force_guid` blank, and set `deploy=true`. The workflow rejects zero, blank, negative, and over-cap batch sizes so a manual run cannot accidentally process the full RSS feed. The limit counts eligible episodes after durable-state filtering, not the newest feed positions.

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
- Process a controlled eligible batch: dispatch `backfill` with `batch_size` from 1 through 20.
- Retry failed episodes only: the later daily schedule automatically attempts one due failure, or manually dispatch `retry_failed` with a `batch_size` from 1 through 20. Cooldowns and the three-attempt cap still apply.
- Force one episode: choose any processing mode and provide its exact RSS GUID in `force_guid`; the override searches the full fetched feed and bypasses batch position limits.
- Validate locally: set `FFW_MODE=live`, then run `python -m ffw validate`.
- Rebuild production projections locally: set `FFW_MODE=live`, then run `python -m ffw render`.
- Inspect workflow health: open **Actions → FFW automated archive**. The publish summary reports selector counts, attempts, outcomes, and whether durable outputs changed. Deployment outcome is reported separately by the deployment job.

## Verify a no-op run

1. Confirm the next candidate is already terminal or there are no eligible feed records for the chosen policy.
2. Dispatch `next` with `batch_size=1` and leave `force_guid` blank.
3. In the run summary, verify `Selected: 0`, `Attempted: 0`, and `Durable outputs changed: false`.
4. Verify `git status` remains clean after pulling the workflow result.
5. Before declaring the final pass complete, also verify that the workflow skips Pages upload/deployment when nothing changed. The pipeline currently avoids catalog rewrites, but the checked-in workflow still needs this deployment-level guard.

## Final-pass review workflow (pending implementation)

The static site cannot write to the repository. When the Review editor is implemented:

1. Open the episode and select **Review**.
2. Update, add, or exclude picks and mark the episode reviewed.
3. Choose **Copy Correction JSON** or **Download Correction JSON**.
4. Save the payload as `data/reviews/<episode-id>.json`; do not place it under generated `archive/` paths.
5. Run `python -m ffw validate` and `python -m ffw render`.
6. Confirm the effective archive reflects the correction and the original episode extraction is unchanged.
7. Commit the review file and regenerated projections together.

Malformed review files must stop validation with a readable error. Never work around validation by editing `archive/index.json`, `archive/cards.json`, or generated Markdown directly.

## Final-pass timestamp playback troubleshooting (pending implementation)

- Open the episode URL with `t=<seconds>` and confirm the selected timestamp appears in the player.
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

In GitHub Actions, choose a normal processing mode, enter the exact RSS GUID in `force_guid`, keep `batch_size=1`, and dispatch. Exact GUID selection searches the full fetched feed and processes only that episode. The final-pass UI may add a copy button for this command/input, but it must not contain a token or trigger an authenticated write from Pages.

## Retention and cost

Raw MP3s, normalized chunks, and full transcripts remain in `.ffw-work/`, which is ignored and disposable on GitHub-hosted runners. Published records retain only source metadata, timestamps, short evidence excerpts, model/version audit data, JSON, and Markdown.

The OpenAI API may return token usage for extraction, but transcription usage availability varies by response. The pipeline records provider/model/chunk/duration metadata when available and does not fabricate a cost estimate. Monitor actual spend in the OpenAI API usage dashboard.
