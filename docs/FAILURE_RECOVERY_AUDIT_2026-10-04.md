# Failure and recovery audit — 2026-10-04

## Bottom line

This is not one recurring episode bug. There are several failure families that have been getting discussed under the same label: provider availability/quota, model output truncation, transcript/section extraction mistakes, recovery orchestration, and validation/persistence failures. Most episodes eventually recover, but our records do not reliably explain which intervention helped. MTGFF 520 and 535 expose weaknesses in recovery rather than evidence that the whole pipeline needs replacing.

Recommendation: add a small durable attempt ledger, close two concrete recovery gaps, and introduce a bounded rescue for the individual chunk that hits MAX_TOKENS. Keep the free-only architecture; do not broadly redesign transcription or add a paid provider on this evidence.

## Scope and confidence

Read-only inspection covered GitHub workflow inventory and current production state/code, representative failed-run logs, local Git history and historical state snapshots, project documentation, and 28 primary project chats in local Codex session files. Approval/guardian mirrors were excluded as independent conversations. Chat recollections were checked against logs/code where available. No production runs, fixes, commits, or pushes were performed. This report is the only new project file.

The local checkout is dirty and its remote-tracking branch is stale; GitHub production state was consulted rather than treating local state as current. Existing user edits were preserved. Historical logs/artifacts are not a complete record: transcript artifacts expire, latest state overwrites errors, and some successful processing never reached a committed state. Therefore counts below are lower bounds or workflow counts, not a complete incident census.

## What the current records actually say

GitHub episode state updated at 2026-10-04 00:48:27 UTC contains 101 real episode records, excluding synthetic fixtures:

- 66 complete, 33 needs_review, and 2 failed: MTGFF 520 and 535.
- 35 records have at least one failed history transition; 33 of those are now non-failed.
- 56 failed transitions survive in current history. This is not the total number of failed requests or historical attempts.

The 99 non-failed records should not be described as 99 clean, verified successes: needs_review is a separate quality outcome. Likewise, a zero-pick episode can be genuinely recommendation-free, incorrectly extracted, or failed before extraction.

The available workflow inventory has 231 primary archive runs: 146 success, 77 failure, 8 cancelled. Those include push/render runs and cannot be converted into an episode success rate. Recovery workflows have 29 runs, 28 green and one red; a green recovery run can mean nothing was selected. The current queue ledger was reset during its policy change, so it cannot reconstruct all 29 outcomes.

## Failure families and evidence

| Family | Observed evidence | What actually helped / what remains |
| --- | --- | --- |
| Provider failures | Repeated 503, 504, disconnects and quota errors across both shows; BB 711, 720, MTGFF 501, 503, 506 and others | Backoff, bounded retries and later reruns often work. A later success is not proof of a content-specific repair. |
| Output truncation | MAX_TOKENS on MTGFF 509, 520, 535 and BB 675, 678, 683, 703, 719 | Lite is not a reliable rescue for every chunk. Targeted chunk splitting was discussed earlier but is not implemented. |
| Wrong section / extraction | MTGFF 530/532 agenda markers mistaken for the real segment; BB 695 agenda/boundary mistake | Marker ranking, structural ordering and show-specific recommendation-block handling produced real recoveries. These were distinct bugs, not provider outages. |
| Recovery orchestration | Empty green queue runs; invalid GitHub gate fields; missing recovery checkpoint cache | Gate fixes landed, but the recovery workflow still lacks main-workflow checkpoint/artifact parity. |
| Validation/persistence | BB 708 and 704 extracted recommendations but the workflow failed on unrelated archive validation | Successful processing is not necessarily saved. Validate existing archive before spending provider calls. |
| State bookkeeping | Failed reruns replace latest error/status/count; old transcript metadata remains; history stores only status/time | Keep best published result independent of latest attempt; append attempt evidence instead of overwriting it. |
| Legitimate no recommendations / review | MTGFF 500/508 retrospectives; BB 703; fictional/ambiguous cards and speaker disagreement | Preserve explicit disposition and review reasons. Do not force every episode to four picks or repeatedly transcribe genuine no-recommendation episodes. |

### 520: more than one failure mechanism

The September 30 recovery hit Flash 503 twice, then Lite MAX_TOKENS on chunk 2/5. On October 1 it encountered a different error: “peer closed connection … incomplete chunked read.” The current transient-error matcher uses message substrings and does not recognize that wording or classify the transport exception by type. Consequently that attempt bypassed the normal retry/fallback path.

The later forced Lite run again hit MAX_TOKENS twice on chunk 2/5. It used Lite as both primary and fallback, which deduplicates to one model; it was not a two-model rescue. Changing the model pair also changes the checkpoint fingerprint and invalidates prior chunks. That intervention was therefore poorly matched to this failure.

State retains older five-chunk transcription metadata, but that does not prove the latest attempt finished transcription. Its current failure is at transcription.

Evidence: [September 30 recovery](https://github.com/courtjester15/ManaIntel/actions/runs/36785148032), [October 1 transport failure](https://github.com/courtjester15/ManaIntel/actions/runs/36943073407), [forced Lite failure](https://github.com/courtjester15/ManaIntel/actions/runs/37088285587).

### 535: provider failures followed by repeated output limits

The attempts failed at different chunks as work progressed: first chunk 1, then chunk 3, then chunk 4. The September 30 run reused checkpoints for chunks 1–3, then got two Flash disconnects and Lite MAX_TOKENS on chunk 4/5. Checkpointing demonstrably helped this episode, but it does not solve the remaining output limit.

It is not reasonable to call 535 uniquely unlucky or its exact content deterministically broken. Similar failure combinations preceded it, and longer MTGFF 534 processed six chunks. We do not have the failed partial response/usage needed to distinguish transcript verbosity, repetition, output allowance, or another model-specific cause.

Evidence: [checkpointed 535 failure](https://github.com/courtjester15/ManaIntel/actions/runs/36660238963), [BB 683: 504 plus MAX_TOKENS](https://github.com/courtjester15/ManaIntel/actions/runs/33642194307), [BB 719: same recurring combination](https://github.com/courtjester15/ManaIntel/actions/runs/36152819125).

### Successful work can be discarded downstream

BB 708 extracted nine recommendations in a September 22 run, but archive validation failed; a subsequent run persisted seven. BB 704 extracted two and reported complete on September 25, but the workflow failed because BB 703 was classified successful without its expected output files. Current production still carries the earlier one-pick result for 704. The explicit validator error was `completed_without_outputs`, not a Gemini error.

The metadata-only no-recommendations validator fix subsequently landed. This specific issue is fixed; its general lesson remains: unrelated archive validation can waste a successful provider run and hide its result.

Evidence: [BB 708 processing/validation failure](https://github.com/courtjester15/ManaIntel/actions/runs/35677583300), [BB 704 success followed by validation failure](https://github.com/courtjester15/ManaIntel/actions/runs/36085599456).

## Repairs already made: avoid rediscovering them

| Period | Actual change | Assessment |
| --- | --- | --- |
| July 16–20 | Valid Gemini model selection, positive batch cap, provider-wide stop, state-aware selection, cooldown/attempt limits | Early bulk 404 incidents were configuration/selection failures. Do not mix them with today's chunk failures. |
| July 24–31 | Lite fallback, malformed-JSON retry, longer backoff | Useful recovery mechanics, not a guarantee against output truncation. |
| August 13–21 | Recent-episode selection; private retained transcripts; improved section boundaries and extraction; zero-result overwrite guard; stable rerun paths and episode-number migration | Real content/identity bugs fixed. Some recoveries were transcript-only re-extraction, not retranscription. |
| August 30–September 3 | Request/job timeouts; checkpoint cache; quota shortcut; fewer retries; extraction retry/fallback | Reduced long hangs and restarted-work amplification. Extraction had previously been an unprotected single point of failure. |
| September 16–25 | Recovery queue, two GitHub gate repairs, explicit no-recommendations disposition, validator support | Gate used invalid `status=success`, then nonexistent `completed_at`; both were repaired. Green no-op runs had concealed this. |

Relevant Git commits: `03bcf2c`, `c6663a2`, `d398e17`, `3bcedc6`, `8621017`, `eee7fd1`, `8e7ca1b`, `c309747`, `3b6c855`, `e5f5ecc`, `5b8fb1f`, `7f3bf32`, `6efc858`.

Examples of observed recovery: MTGFF 530 and 532 reached four picks after boundary/extraction repairs; BB 695 went from zero to three; BB 702 restored four; MTGFF 510 used a retained transcript plus Lite extraction to reach two; BB 711 later reached five; MTGFF 525 reached four with mixed transcription models; BB 720 later reached three after all-503 failure. These are different recovery types and should not be lumped together.

## Gaps in the current implementation

1. **No durable incident ledger.** `state.py` history records status and timestamp, not the historical error, model, chunk, run, code revision, or intervention. Later attempts erase context. Chat history helps, but contains hypotheses, corrections and claims that were not always verified.
2. **Recovery lacks checkpoint parity.** `reprocess-queue.yml` neither restores/saves the transcription checkpoint cache nor offers the main workflow's retained-transcript reuse. Re-running through that route can redo expensive completed work.
3. **Transport matching is brittle.** `production.py` recognizes several error strings but misses the actual incomplete-body disconnect seen on 520. Composite errors can also obscure provider-wide outages: malformed output takes precedence in failure classification even when earlier calls returned 503.
4. **Insufficient failed-output diagnostics.** The transcription schema asks for full transcript text and segment text, repeating the speech in structured output. Failed MAX_TOKENS responses do not retain enough usage/partial-output evidence to diagnose why they reached the limit. Current generation configuration does not explicitly set an output-token budget.
5. **Checkpoint identity is configuration-sensitive.** Fingerprints include the model pair, audio and prompt/configuration. Changing models can silently lose reuse even when previous chunks were valid. Private transcript artifacts are retained for only 14 days; old recovery plans cannot assume they still exist.
6. **Latest attempt and best result are conflated.** A failed forced redo can leave a published summary beside failed state and zero pick count. BB 703 now has a no-recommendations disposition but still carries a historical error. Metadata needs an explicit attempt/result distinction.
7. **Queue outcome is underexplained.** A two-episode daily cap is not a Gemini request budget. Complete/blocked queue entries are excluded on later runs even when still below four picks; ranking can select old episodes outside the main pipeline's recent-episode policy. These policies need explicit reasons and eligibility, not another retry button.

Code to change if approved: `src/ffw/production.py`, `src/ffw/pipeline.py`, `src/ffw/state.py`, `.github/workflows/ffw.yml`, `.github/workflows/reprocess-queue.yml`.

## Proposed next steps, in order

### Small reliability pass

- Preflight the existing archive before making paid-in-quota provider calls. Persist attempt failures even if later archive validation fails.
- Handle typed transient transport exceptions, including incomplete chunked reads; test the exact 520 case. Record each model-call outcome rather than flattening the fallback chain into one string.
- Give recovery runs the same checkpoint restore/save and retained-transcript mechanisms as the main workflow. Show how many chunks will be reused before dispatch and warn when model changes invalidate reuse.
- Add a bounded MAX_TOKENS rescue: split only the failed chunk once, retain successful subchunks, and correctly offset timestamps. Do not globally shrink every chunk or repeatedly rerun the whole episode. Include a strict additional-call cap. Capture finish reason, available usage and partial-response length first; avoid publishing transcript excerpts.

### Minimal failure ledger, not a dashboard project

Use an append-only metadata record for every episode attempt, including success, failure, no-op and recovery:

`episode GUID/source/number; attempt ID; workflow/run URL; Git SHA; timestamps; stage; model/config fingerprint; chunk/subchunk; reused checkpoints; exception class; HTTP/provider code; finish reason; available usage; request count; validation/persistence outcome; prior attempt; intervention; resulting disposition/pick count`.

Retain successful summaries separately from last-attempt status. An intervention entry should distinguish “changed extraction rules,” “reused transcript,” “split chunk,” “changed model,” and “retried later.” Mark a fix confirmed only when the resulting artifact was persisted and checked. Keep audio, full transcripts, keys and sensitive response bodies out of the public ledger.

Backfill what we can from Git state, Actions and these chats, labeling source confidence. Do not pretend every historical incident is recoverable. Initially a simple file plus a human-readable summary is enough; account for concurrent writers when choosing its storage/merge mechanism.

### Focused regression coverage

Tests should cover the actual transport exception; Flash outage plus Lite malformed output; checkpoint reuse/configuration changes; MAX_TOKENS subchunk timestamps/call caps; successful extraction followed by unrelated validation failure; preserving best output after failed redo; queue gates using real GitHub payload fields; and known agenda-versus-real-segment fixtures.

## What I would not do

Do not add paid OpenAI fallback to solve this without a separate decision. No paid key was configured historically, so removing dormant fallback was not the cause of a lost working safety net. Do not call checkpoint recovery universally proven by MTGFF 509: its successful run started fresh. Do not infer live quota headroom from prior successes or green Actions badges. Do not treat needs_review, genuine no-recommendations, and provider failures as one metric.

The next practical move is the small reliability pass and ledger together. That would make 520/535 cheaper to rescue and make the next failure explainable, without rebuilding a pipeline that has successfully processed most episodes.
