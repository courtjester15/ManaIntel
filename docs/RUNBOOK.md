# ManaIntel Production Runbook

## Automated service

GitHub Actions runs `.github/workflows/ffw.yml` at 20:17 UTC for fresh backfill and at 00:17 UTC for bounded failed recovery. It reads both public podcast feeds:

`https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss`

`https://feeds.feedburner.com/brainstormbrewerypodcast`

The production stages are feed discovery, eligibility-first selection, durable queueing, streamed temporary download, ffmpeg normalization/splitting, provider transcription, Cards to Watch boundary detection, schema-constrained extraction, validation, bot commit, and Pages deployment. The checked-in workflow is intentionally free-tier-only: scheduled processing and the low-pick queue select the responding Gemini `gemini-3.5-flash-lite` model for transcription and extraction. The identical fallback setting is deduplicated, so the adapter does not call the same model twice as two providers. Manual dispatch retains `gemini-3.6-flash` as an explicit availability-test option, with Flash Lite fallback, but does not automatically probe the repeatedly unavailable model on every episode. It does not configure or use OpenAI. The OpenAI adapters remain dormant for a possible future explicit paid opt-in.

Before publication, `FFW_TARGETED_VERIFICATION_ENABLED=true` permits up to `FFW_TARGETED_VERIFICATION_MAX_PICKS` focused second-listen checks for card-name/transcription ambiguities. Each check sends only a short excerpt around the pick timestamp. A correction is accepted only when the second listen supplies a name that Scryfall verifies exactly; unavailable verification remains non-fatal and the pick stays in review. Printing and foil ambiguity is not auto-approved.

After a successful episode attempt, ManaIntel checks up to `FFW_CARD_RESOLUTION_BATCH_SIZE` uncached card names against Scryfall. Exact matches are projected as canonical names; fuzzy matches are only review suggestions. Resolution failures do not fail podcast ingestion. Run `manaintel resolve-cards --limit N` for an explicit historical sweep or add `--refresh` after a resolver-version change.

MTG Fast Finance boundary detection is bidirectional. Show-outline mentions of Cards to Watch do not count as a section start, regardless of when the agenda occurs; when multiple markers remain, the marker most closely followed by recommendation language wins. A separate pick-wrap phrase or structural transition into the weekly feature named by the episode title/show notes supplies end evidence only after pick language has occurred. Independent ending evidence improves section confidence; without it, extraction is conservatively capped at 20 minutes after the trusted start and remains a diagnostic warning when extraction still yields approved picks. Transcript sequence, not provider timestamps, owns structural ordering because malformed chunk timestamps can collapse at a chunk boundary. A weak start, missing section, empty extraction, or pick-level ambiguity remains `needs_review`, and a generic topic word inside a pick discussion is not sufficient to close the section.

Brainstorm Brewery applies the same start-evidence rules to Breaking Bulk, Bulk to Binder, and Pick of the Week. Intro/agenda mentions are excluded, the first credible recommendation marker starts the section, and recommendation language can supply the start when the host does not repeat a segment label. Because Breaking Bulk and Pick of the Week can be separated by a long topic discussion, the detector preserves both blocks and trusts an ending only after the last recommendation marker or cue; otherwise it caps the tail at 20 minutes and leaves the result reviewable.

One concurrency group serializes all writers. The 20:17 UTC `next` run scans newest to oldest and processes at most one untouched eligible episode. `complete`, `needs_review`, and `failed` records skip before download or provider calls, so new releases take priority. The 00:17 UTC `retry_then_next` run selects at most one episode: the newest due retry first, otherwise the newest untouched episode across both feeds. Both automatic runs therefore advance the same newest-to-oldest cursor without an episode-age cutoff. It never attempts both. Retryable errors cool down for six hours and stop after three total episode attempts. A runner crash after an external API response but before the next durable Git commit can cause a repeated API call; file-backed Git state cannot guarantee exactly-once external billing.

The October 16 schedule experiment targets evening provider availability: triggers at 4:17 p.m. / 8:17 p.m. EDT aim for actual starts around 6–8 p.m. / 10 p.m.–midnight if the observed 2–4-hour GitHub delay persists. Fixed UTC schedules shift to 3:17 p.m. / 7:17 p.m. EST in winter. Starts may be prompt, much later, or missed; do not treat lag as a guaranteed offset. The two triggers are four hours apart: a new failure may still be cooling down at the second run, which then considers an untouched episode instead. The existing low-pick queue times and successful-primary gate remain in place. Compare actual model-call times and usable episode outcomes after two weeks of ordinary processing; do not manufacture calls to fill the sample.

## One-time GitHub setup

1. Open the repository, then **Settings -> Secrets and variables -> Actions -> New repository secret**. Name the production secret exactly `GEMINI_API_KEY` and paste a valid Google AI Studio API key. Do not add an OpenAI key for the checked-in production workflow.
2. Open **Settings → Actions → General → Workflow permissions**. Select **Read and write permissions**, then save.
3. Open **Settings → Pages → Build and deployment → Source**. Select **GitHub Actions**.
4. If GitHub pauses the first deployment, open **Actions → ManaIntel automated archive → the waiting run → Review deployments**, approve `github-pages`, and continue.

## Controlled live validation

Manual live runs are intentionally capped. For one Brainstorm Brewery episode, use `next`, `source=brainstorm-brewery`, `batch_size=1`, leave `force_guid` blank, and set `deploy=true`. The workflow rejects zero, blank, negative, and over-cap batch sizes so a manual run cannot accidentally process the full RSS feed. The limit counts eligible episodes after durable-state filtering, not the newest feed positions.

The first Gemini validation attempt used `gemini-2.5-flash`, which returned `404 NOT_FOUND` for this key because that model was not available to new users. That run also demonstrated why provider-wide failures must stop the batch: the old `episode_limit=0` default meant "all episodes" and published roughly 500 failed live records. The archive/state cleanup commit removes those generated failure records and keeps the synthetic fixture archive only.

Provider-wide failures include missing or invalid keys, unavailable models, quota exhaustion, transient provider capacity, and provider schema capability errors. They stop the current batch so one outage does not burn through multiple episodes. Missing credentials, unsupported models, and incompatible schemas are non-retryable configuration failures. During transcription, quota (`429`), disconnect, timeout, and `5xx` errors receive the configured primary retries and one request on the same-key fallback model. If both models fail, the episode remains retryable after the normal cooldown. Episode-specific bad input, such as oversized or empty audio, is quarantined and does not stop unrelated work.

The fallback uses the existing `GEMINI_API_KEY`; it requires no second account or repository secret. `FFW_TRANSCRIPTION_FALLBACK_MODEL` disables fallback when blank. `FFW_GEMINI_TRANSIENT_RETRIES` and `FFW_GEMINI_RETRY_DELAY_SECONDS` control primary-model retries and delay. Successful state records retain the actual model for every chunk, including mixed-model transcripts.

### Free-tier retry caution

Each successful transcription chunk is written atomically under ignored `.ffw-work/chunk-checkpoints/`. GitHub Actions restores and saves that directory through its private cache, so a later scheduled attempt resumes at the first missing chunk. A fingerprint covers the episode GUID and audio URL, audio bytes, prompt, model pair, and chunk size; stale or corrupt checkpoints are ignored. Checkpoints are cleared after the episode publishes successfully, while extraction failures retain the completed transcription chunks. A `429 RESOURCE_EXHAUSTED` response skips further retries on that model and tries the same-key fallback at most once. Do not manually dispatch more runs after both Gemini models report quota exhaustion that day.

Never put the API key in `.env.example`, state, archive output, workflow inputs, issue text, or logs.

## Controlled historical backfill

Open **Actions → ManaIntel automated archive → Run workflow** and choose:

- mode: `backfill`
- batch_size: `3`
- force_guid: blank
- deploy: enabled

The job attempts all three sequentially, validates the production-only catalog, commits durable changes with `chore(ffw): publish automated episode updates`, and deploys the site. A partial episode failure remains visible in processing status and the run summary.

## Recovery

### Read the processing health report

The dated baseline is [HEALTH_REPORT.md](HEALTH_REPORT.md); its structured report and saved GitHub metadata are [state/health-baseline.json](../state/health-baseline.json). A fresh report appears in the primary and low-pick workflow job summaries and `health-<run-id>-<attempt>` artifacts (30 days). It is read-only, uses no transcription/extraction calls, and writes only temporary report files during workflows, so it does not itself create archive changes or publication churn. Reporting is non-blocking if GitHub metadata is unavailable; unknown evidence stays unknown. The baseline in Git is a dated snapshot, not a continuously rewritten dashboard.

```powershell
$env:PYTHONPATH = 'src'
python -m ffw health-report --days 14
python -m ffw health-report --days 14 --github --output-json .ffw-work/health/report.json --output-markdown .ffw-work/health/report.md
```

`--github` requires an authenticated `gh` CLI (Actions supplies its existing read-only Actions permission through `GH_TOKEN`). Collection makes at most three run-list reads and sixty job-metadata reads, prioritizing attempt-linked runs, with a ninety-second observation budget and a stop after three consecutive failed job reads. Truncation and failed reads are reported; no run logs or transcripts are fetched. Use `--workflow-evidence state/health-baseline.json --as-of <the-saved-as_of>` to reuse the saved observation payload offline. Exact regeneration also requires the same source version and journal/catalog inputs; later archive snapshots can legitimately change the backlog. The stored JSON keeps the original report inspectable without refetching mutable GitHub results.

Definitions:

- Initial, retry and forced attempts have separate denominators; skips/in-progress records are excluded from finished attempts. The window uses UTC attempt start time. The journals do not reconstruct earlier unjournaled history.
- A validated usable result is a new complete/needs-review extraction with picks, or an explicitly confirmed no-recommendations disposition, with successful validation. Preserved old output and unexplained empty results do not count. This measures processing, not independent transcription accuracy.
- Publication is verified only when the exact run attempt has observed successful persistence and a successful Pages job. Archive validation or an overall workflow conclusion alone is insufficient. A reporting workflow cannot yet certify its own future deployment.
- Current catalog/review counts are a separately dated snapshot. Machine approval is distinct from explicit human review. Legacy missing source IDs are reported as unknown rather than silently attributed.
- Model-response success and semantic timing rejection are separate counts. Terminal error categories are message-based summaries, not independent root-cause diagnoses.

The report exposes no-op/gated runs with successful Pages jobs so deployment churn is visible rather than counted as productive processing. Investigate that guard separately; R1 does not change selection/retry/publication behavior.

- Process one next eligible episode: dispatch `next` with `batch_size=1`.
- Process one source only: dispatch `next`, choose `mtg-fast-finance` or `brainstorm-brewery` in `source`, and keep `batch_size=1`.
- Process a controlled eligible batch: dispatch `backfill` with `batch_size` from 1 through 20.
- Use the bounded evening slot manually: dispatch `evening`; it retries one due failure or, if none is due, processes the newest untouched episode regardless of age. It never does both.
- Retry failed episodes only: manually dispatch `retry_failed` with a `batch_size` from 1 through 20. Cooldowns and the three-attempt cap still apply.
- Force one episode: choose any processing mode and provide its exact RSS GUID in `force_guid`; the override searches the full fetched feed and bypasses batch position limits.
- Validate locally: set `FFW_MODE=live`, then run `manaintel validate`.
- Rebuild production projections locally: set `FFW_MODE=live`, then run `manaintel render`.
- Inspect workflow health: open **Actions → ManaIntel automated archive**. The publish summary reports selector counts, attempts, outcomes, and whether durable outputs changed. Deployment outcome is reported separately by the deployment job.

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

For local maintenance, run `manaintel apply-review --payload '<json>' --actor '<name>'`. This performs the same durable write and projection rebuild; validate before committing.

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
manaintel run --live --force-guid <rss-guid>
```

In GitHub Actions, choose a normal processing mode, enter the exact canonical GUID in `force_guid`, keep `batch_size=1`, and dispatch. Exact GUID selection searches the full fetched feed and processes only that episode, even when it is quarantined. Flash Lite is the default in `ai_model`; use the optional 3.6 model only for an explicit bounded availability test. To retry extraction without paying to transcribe again, enter the prior Actions run ID in `reuse_transcript_run_id`; the workflow downloads that run's private transcript artifact, verifies its episode GUID, and fails closed if it is missing or mismatched. Failed episode details in the static UI provide **Copy retry GUID** and **Open retry workflow** buttons. The UI intentionally contains no GitHub token and cannot dispatch an authenticated run itself.

## Retention and cost

### Availability and bounded recovery

Version 0.5.6 shares a model availability circuit across transcription, timing repair and extraction within each episode attempt. With a configured fallback, two transient primary failures or one quota response suppress further calls to that primary during the attempt. Output truncation and malformed JSON do not open the availability circuit. The next attempt starts with fresh model availability state. Optional second-listen verification preserves unresolved ambiguity if its model's circuit is open.

Each original audio chunk can be split into two halves once for truncation recovery. A transcription invocation permits at most eight actual rescue calls, including failed calls and fallback calls. Cached parent chunks and clips are reused without spending that budget. If it is exhausted, a later bounded retry resumes the saved progress. Since 0.5.7, targeted timing repairs use four shorter clips with integer-second timestamps and a per-clip clock reset. Timing repair permits two original chunks by default (three or four only for an inspected manual dispatch); its separate single-chunk transcription invocations remain bounded too. Rejected timing payloads are retained privately as `rejected-*.json.gz` alongside transcript artifacts, with sanitized numeric metrics in the attempt journal.

Timing budget exhaustion, incompatible retained transcripts and unusable replacement timing are classified `manual_intervention`, with no automatic retry date. Both normal retry selectors and the low-pick queue exclude those errors. Legacy records with the same manual-review message are also excluded even if their stored retryable flag is true. Exact-GUID dispatch remains the explicit recovery path after inspecting evidence. Do not raise the global repair limit or delete retained evidence to bypass this gate.

The October 15 inspection found that BB 667 needs four original chunks repaired: chunks 1, 3 and 4 have collapsed tails, and those tails masked missing coverage in chunk 2. The corrected detector excludes zero-length boundary tails from following-chunk coverage. Use the four-chunk manual budget only for this inspected recovery. BB 666's targeted repair of original chunk 2 succeeded in run 38841659910 and published three picks as needs_review for section-boundary uncertainty. Scheduled processing uses the responding Flash Lite model; a circuit breaker remains available for explicitly selected model/fallback pairs, but cannot ensure provider availability.

Attempt-log entries now show failed model-call counts and unavailable-model skips. Judge useful throughput by episode outcome and pick count; archive validation can succeed while persisting a failed episode record.

Raw MP3s and normalized chunks remain disposable in `.ffw-work/`. When `FFW_RETAIN_TRANSCRIPTS=true`, the pipeline writes compressed full timestamped transcripts under `.ffw-work/transcripts/`; the production workflow uploads them as private Actions artifacts with 14-day retention. Transcripts are never committed or copied to Pages. Forced episode reruns also retain the previous summary and a compact before/after comparison as private 14-day workflow artifacts, allowing the replacement to be evaluated without manual transcription diffing. A forced rerun that falls from one or more published picks to zero cannot erase the previous recommendations: the prior picks remain published, the episode returns to `needs_review`, and the rejected comparison records the publication guard. Published records retain only source metadata, timestamps, short evidence excerpts, model/version audit data, JSON, and Markdown.

A missing recommendation-section ending remains visible in section metadata but does not by itself require editorial review when all extracted picks are approved. Missing sections, empty extraction, and pick-level ambiguity still produce `needs_review`. Gemini segment timestamps are bounded to their source chunk and the count of timing corrections is retained in transcription metadata.

The production pipeline records Gemini provider/model/chunk/duration metadata when available and does not fabricate a cost estimate. OpenAI cost monitoring is irrelevant unless the dormant adapter is explicitly enabled in a future deployment.

Since 0.5.8, every new Gemini transcription requests explicit `MM:SS.mmm` strings and converts them to elapsed seconds in code. This applies to original chunks, truncation rescue, and targeted timing repair. It avoids the numeric second/MMSS ambiguity observed in the retained BB 666 rejection from run 38840331812. The published transcript/summary contract remains numeric seconds; legacy retained transcripts and old successful episode outputs are preserved. New audio requests use the new prompt fingerprint.

Clock fractions accept full decimal precision. For targeted repair only, version 0.5.10 permits a final segment that starts inside the clip to end at most three seconds past its physical duration; its end is trimmed to the measured duration. The correction is journaled and counted, and the episode stays needs_review. Earlier out-of-bounds segments, starts outside the clip, larger overruns and backward clocks remain failures.

### Review automation (0.5.13)

New attempts persist `processing.review_issues` with independent codes, evidence reasons and extraction/section/pick paths. Unknown reasons remain unresolved. A catalog-backed audible name correction clears only identity-only reasons; mixed printing, intent, timing or coverage concerns remain reviewable. Out-of-audio picks skip name inference until alignment is repaired. Source disagreement and conditional prices belong in caveats/targets only when an explicit recommendation is supported; uncertain commentary remains reviewable. Existing records are not automatically approved.

Retained transcripts now record `transcription_prompt_version` separately from the extraction `prompt_version`. Legacy transcripts with the known unchanged transcription identity remain reusable. A change to actual transcription policy must advance the transcription identity; extraction-only prompt changes must not force fresh audio calls.

Run one bounded retained-transcript pilot before expanding a recovery cohort. Compare every prior pick and printing, inspect candidate/preservation reports and remaining issue codes, and retain old publication if coverage regresses. Name-only automated verification is not independent source-accuracy evidence. Large mixed transcript windows need alignment/coverage repair; do not relax gates merely to clear the queue.

0.5.14 additionally rejects automatic replacement of known printing/foil identities during forced reprocessing. Candidate evidence/comparison is retained privately; old recommendation records and stable IDs survive the regression. Use an explicit evidence-backed correction/override for deliberate variant corrections. A bounded FF 495 pilot motivated this guard; its original records were restored while preserving a supported new boundary and unresolved timing.

### Bounded cleanup rollout (0.5.15)

Exact-GUID dispatch accepts `timing_repair_limit=incremental` to repair at most two suspect original chunks and retain progress before stopping. `review` additionally revisits all original chunks behind legacy timing corrections. When the two-chunk cap leaves additional suspects after successful repairs, the saved-progress disposition is retryable after the existing cooldown and within the existing episode-attempt cap. Existing manual-intervention records remain excluded. Repository variable `FFW_INCREMENTAL_REPAIR=true` permits this mode for future scheduled processing after pilot validation. These inspected modes do not increase the per-chunk eight-call rescue cap. A rejected quarter may subdivide into two shorter clips, at most two levels deep; successful children and the subdivision plan persist so the parent rejection is not repeated on resume. Cleanup reuses matching retained evidence whenever available; older records without retained transcripts may take a fresh pass under the same sixteen-request run cap. Overruns relative to the stated audio duration now identify the affected final original chunk. Original timing-adjustment counters remain audit history; the timing warning clears only after every original chunk has validated audio repair with no current trimming. Other review reasons stay independent. Unique exact full-quote matches (at least eight normalized words, no repeated match) may align published picks to repaired audio text. `identity_start_seconds` preserves the prior pick ID while playback uses the corrected timestamp; explicit human edits retain the established review behavior.

Every Gemini request in the main and cleanup workflows reserves capacity in `state/request-capacity.json` before transmission, including schema fallback requests and failures. Counts are per model and America/Los_Angeles date, bootstrapped from retained attempt events on rollout. Application ceiling: 48 requests/model/day; optional work stops at 32 total to reserve sixteen for primary work, and uses at most sixteen/run. These are application limits, not provider entitlements or a remaining-quota meter. Explicit daily-limit responses stop that model until the Pacific day changes; generic 429 and overload stop all writers for thirty minutes. Runner termination before Git persistence can lose reservations, so exact-once accounting is not guaranteed.

The existing optional workflow now has nightly opportunities at 04:17 and 05:17 UTC (00:17/01:17 EDT; 23:17/00:17 EST). Actual starts may be delayed; there is no wall-clock cutoff. Shared per-request Pacific-day accounting, primary reserve, provider cooldown and the two-episode/day cap apply at the actual execution time, including across midnight. Repository variables `FFW_CLEANUP_ENABLED=true` and `FFW_CLEANUP_ISSUES=timing,boundary` enable only pilot-validated issue cohorts. With rollout disabled, scheduled optional processing skips; manual legacy low-pick dispatch remains available. Each enabled selection targets needs-review records last processed over fourteen days ago, preferring retained evidence and then oldest processing time. It excludes failed/manual-gated records and already attempted cases; at most two episode attempts/Pacific day. A continuation is allowed after six hours only if a previous incomplete attempt saved a newly repaired original chunk, or saved a new validated clip before hitting a request budget, with three cohort attempts maximum. Unchanged failures and remaining review reasons become blocked for inspection. Cleanup commits validated outputs then dispatches the existing deploy-only Pages workflow. The successful-primary gate is replaced by per-request capacity reservation. Enable only demonstrated cohorts after bounded FF 495/537 and BB 663 pilots; expand request budgets only after useful throughput is observed.


Exact inspected pilots can be recorded in `state/reprocess-queue.json` under `inspected_pilots`, with a reason/evidence reference, `ready` status, repair mode and at most three cohort attempts. They are explicit per-GUID exceptions after evidence inspection, never a general bypass for failed/manual-gated records. FF 495 is the full review pilot; FF 537 has only one additional retained-progress publication recovery after its inspected 503 stop. Human overrides remain excluded. A coverage pilot can finish with usable needs-review picks while a review pilot finishes only when the review actually clears; these dispositions are reported separately. New validated checkpoints before a request-budget stop permit a six-hour-delayed continuation; unchanged semantic failures stop the cohort. The nightly queue keeps its two-attempt/Pacific-day cap even for inspected pilots. The shared provider cooldown applies to all of them.


A request-budget stop with proved new saved progress is an expected `deferred` cleanup disposition: the workflow can finish successfully while its attempt journal still truthfully records a failed/incomplete episode attempt. The job summary states disposition, published status/picks, saved progress and next action. A blocked semantic failure or failed archive validation still fails the workflow. Workflow success alone never establishes a usable extraction or cleared review.


October 19 rollout variables are enabled for the bounded trial. Production and Pages verification: run 39361221335; safe outside-window cleanup verification: run 39361222070. Inspect `inspected_pilots` and the cleanup disposition summary before expanding budgets. FF 495's duration discrepancy is based on its stated duration, not an independent measurement of the original audio; the pilot must preserve that uncertainty if actual audio and metadata disagree.


0.5.16 timing diagnostics: new transcripts record zero-based `timing_adjustment_chunks` so clean chunks do not need retranscription to clear another chunk's warning. Latest successful audio repairs supersede historical adjustment counts for that chunk; legacy aggregate-only evidence remains conservative. Validated repair clips may trim at most one second of final endpoint rounding without a review flag; the segment must start inside the clip and all existing bounds/content checks still pass. Larger accepted trims remain reviewable, and larger invalid overruns remain rejected. Private checkpoints retain trim diagnostics. This does not approve existing review records or certify semantic accuracy.
