# Production reliability review — October 14, 2026

## Conclusion

The recent model migration is not functioning as a useful primary path in the observed production sample. Provider unavailability forces processing onto Flash Lite, whose truncated output and suspect timing expose existing recovery limits. Automatic retry classification then wastes a retry on a deterministic manual-review gate. This is a combination of external failures and internal recovery design, not an extraction or deployment failure.

Evidence comes from the current remote attempt journal and five remote attempt JSON files, checked against the local source at 589ad4f. The local checkout does not contain the latest generated production state. No live inference or recovery was triggered for this review. Full retained transcript contents were not inspected; timing defects below are detector findings, not independently verified audio errors.

## Observed outcomes since migration

Five recorded episode attempts across three distinct episodes: four failed, one published needs_review, none complete. That is an 80% attempt failure rate in this small sample; it is not a historical all-time rate. The three initial attempts yielded one publication and two failures. No-op and deploy-only runs are excluded.

Across these attempts, all 30 observed gemini-3.6-flash calls failed with 503 UNAVAILABLE. Flash Lite made 18 calls: 14 successful responses and four MAX_TOKENS failures. Successful provider responses do not establish usable transcript timing or faithful extraction.

| Episode / attempt | Start, Eastern | Evidence and result |
|---|---|---|
| FF 495 initial | Oct 12, 10:52 p.m. | 16 calls. All ten primary calls failed; Lite supplied transcription, timing repair and extraction. Published four picks as needs_review because the recommendation block ending was not found. |
| BB 667 initial | Oct 13, 1:36 p.m. | Both primary calls and the Lite fallback returned 503 on chunk 1/5. Failed before extraction. |
| BB 667 retry | Oct 13, 7:43 p.m. | 19 calls. Twelve primary 503s; Lite completed six responses after one truncated chunk was split. Timing detector flagged chunks 1, 3 and 4 against a repair budget of two. No repair or extraction was attempted. |
| FF 494 initial | Oct 14, 11:06 a.m. | Ten calls. Six primary 503s. Lite truncated chunk 1; its two halves succeeded. Lite then truncated chunk 2/3. Episode-wide split allowance was already consumed, so processing stopped. |
| BB 667 final automatic retry | Oct 14, 7:13 p.m. | Automatically reused retained transcript; identical suspect chunks [1,3,4], identical budget two. Zero model calls. Failed and consumed the third total attempt. |

## Findings

1. **Primary model migration has no observed successful calls.** Commit 589ad4f changed both transcription and extraction defaults from 3.5 Flash to 3.6 Flash, including the low-pick queue. The returned errors explicitly report high demand. The evidence does not distinguish provider-wide capacity from account/model routing issues, and does not prove the prior model would work today. It does establish that the new primary added failed calls and delays throughout this sample.

2. **The fallback is doing the production work but is not reliably producing usable 15-minute transcripts.** Four Lite responses hit MAX_TOKENS. BB's eventual transcript exceeded the timing repair budget. FF 495 also required timing repair. These are separate failure modes from 503 availability. A valid JSON response is insufficient evidence of a usable transcript.

3. **Split recovery is capped per episode, rather than per failed chunk.** `production.py` initializes `rescue_used` before the audio loop. FF 494 successfully rescued chunk 1, then refused to split chunk 2 when it also truncated. This is a deliberate bound on calls, but it prevents recovery from multiple truncated chunks in one pass. Increasing an output-token cap alone is not a demonstrated remedy: Lite already reached approximately 65k candidate tokens on BB's truncated response.

4. **A deterministic manual-review stop is incorrectly scheduled for automatic retry.** `classify_failure` has no timing-budget category; its default is `unknown, retryable=True`. A direct local reproduction returns exactly that for BB's error. Automatic transcript reuse then reloads the unchanged failed transcript, reaches the same gate, and spends an episode attempt without changing any inputs. BB's final attempt is direct production evidence of this loop.

5. **Repeated primary failures do not suppress that model for subsequent chunks.** The same model is retried on every chunk and split half even after repeated 503s. Quota handling skips repeats within a chunk, but there is no corresponding episode-level availability circuit breaker. BB's second attempt contains twelve failed primary calls.

6. **Recent fixes improved evidence and bounded damage, but did not establish reliable unattended completion.** Earlier changes added timing detection, transcript retention, incremental repairs, missing-coverage detection and split rescue. These prevent suspect evidence from silently passing and preserve recovery progress. They also expose failures that previously could have looked successful. The two-chunk timing limit and one-split limit are now operational stopping points. Raising limits without inspecting evidence would weaken the spending controls without resolving model reliability.

7. **The apparent health of workflow steps overstates useful throughput.** Archive validation succeeded for every failed attempt: it validates stored failure records too. The shell processing step deliberately captures the nonzero CLI exit and continues persistence, so `pipeline=success` in the workflow journal is not episode success. The final reporting step correctly fails the run. The low-pick queue's successful-primary gate was false on Oct 13–14, so those recovery runs skipped work; they were not additional successful processing outcomes.

## What changed, and causal limits

The October 12 change simultaneously switched the primary model and removed the 365-day selection cutoff. Removing the cutoff restored historical work that previously produced no-op runs. That explains why old episodes are being attempted and why the workflow is encountering more real processing failures. It does not explain 503s or malformed output. Comparing green workflow counts before and after this change would mix no-ops with actual attempts.

Timing and truncation trouble predates this model switch: the journal records earlier FF 520 and 510 failures and inspected recoveries. The migration therefore did not create every underlying weakness. It placed a consistently unavailable primary in front of an already fragile fallback path in the observed sample.

## Recommended repair order

1. Add an explicit non-retryable/manual-intervention classification for timing-budget exhaustion and incompatible retained transcript recovery. Prevent identical retained-input failures from consuming automatic retry slots. Add a regression for the exact BB sequence.
2. Validate a primary model on a bounded representative sample before making it the default again. Add an episode-level circuit breaker so repeated 503s stop repeatedly probing a failing model. Do not assume reverting to the previous name proves availability.
3. Replace the single episode-wide split boolean with an explicit total rescue-call budget plus per-chunk recovery state, preserving completed halves. Add a regression covering two truncated original chunks, as seen in FF 494. Evaluate shorter initial chunks against real transcript quality and call volume before changing the global default.
4. Recover BB 667 only after inspecting its retained timing evidence. The existing manually selected three-chunk budget matches the detector count, but is not proof those repairs will succeed or preserve content. Retain the current transcript and repair only inspected chunks. Its three automatic attempts are now consumed.
5. Recover FF 494 using saved chunk/half checkpoints and a bounded plan for the remaining truncated chunks. A retry may progress with the existing code because completed chunk 1 can be reused, but success is not assured.
6. Report attempted episodes, usable publications, needs_review, failures, no-ops, primary availability and recovery call counts separately. Preserve the distinction between persisted valid state and successful episode processing.

## Evidence links

Implementation follow-up: local version 0.5.6 adds manual-intervention classification and legacy-record selection guards, a shared per-attempt availability circuit, an eight-call split-rescue budget that supports multiple original chunks and resumes saved halves, and failed-call/circuit-skip counts in the attempt log. The low-pick queue also respects manual-intervention failures. Provider model names and timing repair limits remain unchanged. Deployment, a live provider evaluation and inspected recovery of the two production episodes remain operational follow-up work; local fixes do not establish that those episodes have recovered.

- [Remote attempt journal](https://github.com/courtjester15/ManaIntel/blob/master/state/episode-attempts.md)
- [FF 495 attempt](https://github.com/courtjester15/ManaIntel/blob/master/state/attempts/64b026cbeca041adba41156f2261dba5.json)
- [BB 667 initial failure](https://github.com/courtjester15/ManaIntel/blob/master/state/attempts/cb52a2711c3b4c48b3cf5c4d95649e6e.json)
- [BB 667 timing failure](https://github.com/courtjester15/ManaIntel/blob/master/state/attempts/1301bb48dd0c419f8ff00ddec98b34ce.json)
- [FF 494 failure](https://github.com/courtjester15/ManaIntel/blob/master/state/attempts/f940e36fe2fe4ff49084d04b27ead0ef.json)
- [BB 667 unchanged-input retry](https://github.com/courtjester15/ManaIntel/blob/master/state/attempts/2353a0c645a64af48f5f38f2d6264049.json)
- [Model and selection migration](https://github.com/courtjester15/ManaIntel/commit/589ad4f5dd666fed04421959b34286d8977cf030)
