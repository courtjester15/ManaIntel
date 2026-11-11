# November 10: archive interactions, card history and reliability review

Release: 0.5.25. This pass keeps the two-show static archive and existing free-tier processing policy.

## Interface findings and changes

| Observed problem | Result |
| --- | --- |
| Feed descriptions display literal entities such as `&#8217;` and `&#160;`. Long errors include a corrupted ellipsis. | Decode feed entities for display, then escape the result; original records remain unchanged. Fix the corrupted error suffix. |
| Dashboard totals look like useful destinations but are inert. Latest episode has no show context. | Make totals navigate to episodes, picks, review and unfinished filters. Add FF/BB labels; unknown source metadata stays unknown. |
| A primary card click unexpectedly opens Scryfall. | Card titles and rows open local details. External research has an explicit Scryfall label and arrow. Episode cells open episode details. |
| No way to follow the same card across recorded recommendations. | Pick history inside card details groups only verified Oracle identities, across both shows. Preserve raw names, printing/finish variants, individual picks, dates, known speakers, reasoning, review states and timestamped source links. Unresolved/suggested matches stay separate. |
| A mentioned price can look like an entry target. | Display mentioned price separately from entry target in details and history. No published extraction fields change. |
| Back-to-episode action is drawn as a close symbol. | Show a back arrow with the matching accessible label; restore episode position when returning. |
| Machine approval can look like human verification. | Label machine checks explicitly; preserve genuine human-review labels. Review preparation no longer claims verification before approval. |
| Search has no result count or obvious reset; URLs do not retain filters. | Add counts, reset controls and shareable search/source/status URLs. Navigation starts with the filters in its destination. |
| Clipboard restrictions fail silently. | Expose/select the exact retry GUID or review payload for manual copying when clipboard access fails. |
| Editing a review can leave an old prepared payload available. | Invalidate prepared output after field/action/note edits and adding/removing picks. |
| Missing audio can leave dead buttons or relative `null`/`undefined` links. | Disable unavailable playback controls, retain real source fallbacks, and reject blank URLs. Optional card-resolution fetch failure cannot hide an episode summary. |
| Dense tables, tiny labels, crowded narrow layouts and ambiguous status colors. | Increase row/control targets and reading sizes; restore amber review cues; contain table scrolling, wrap actions/status badges, align summary headings, provide mobile table hints, visible keyboard focus and a skip link. Catalog art explicitly warns about printing/identity limits. |

## Verification and limits

- Full Python suite: 250 passing, including deployment-asset coverage. First local run exposed missing `tzdata` and sandbox restrictions in isolated Git/temp tests; the complete rerun with the declared dependency and normal Git permissions passed.
- Sixteen dependency-free Node behavior checks cover recovery states, verified-history grouping/multiplicity, escaping, deep links, source uncertainty, machine/human distinction, clipboard denial, missing URLs and unavailable-audio controls.
- Separate local jsdom checks exercise the real 539-pick archive: dashboard filters, table clicks/keyboard activation, episode/pick/back navigation, cross-show Sol Ring history (four records), entity decoding without executing decoded markup, optional-resolution failure, and review preparation/invalidation/copy fallback. DOM checks do not establish pixel layout, audio-host playback or actual clipboard permissions.
- Both the production and local-preview in-app browser attempts timed out. No external browser or desktop control was used. **Visual browser QA remains unverified**, including exact mobile wrapping, native dialog focus restoration and remote audio playback. Responsive CSS was reviewed without claiming a human visual sign-off.
- Shared `ui.js` is included in both Pages publishing paths; entrypoint asset versions are updated. No new production dependency, account or inference request is introduced.

## Production health and evaluation

Read-only seven-day report as of November 10 at 23:01 EST (November 11 04:01 UTC): initial attempts 0/5 validated usable; retries 3/9; forced work 0/7 new usable results with seven prior publications preserved. The three usable results have observed persistence and Pages success. Recorded provider calls: 121, with 109 successful responses, 12 failures and 11 timing rejections. These are historical telemetry, not calls made by this batch or an accuracy score. GitHub evidence: 31 bounded job reads, zero errors; no observed no-op Pages churn.

Current catalog: 139 episodes, 539 picks, 60 episodes needing review, two failed and two explicitly human-reviewed. BB725 now has two published picks following its normal retry ([42452796069](https://github.com/courtjester15/ManaIntel/actions/runs/42452796069)). BB653 exhausted attempt 3/3 after provider refusal; no automatic retry is promised. BB652 attempt 2/3 saved progress but failed on a provider 503; ordinary eligibility is November 11 at 01:42 EST. Its [latest workflow](https://github.com/courtjester15/ManaIntel/actions/runs/42932993879) failed for the episode while validation, durable persistence and Pages succeeded. No forced recovery or cooldown bypass was dispatched tonight. The 0.6 reliability gate remains unmet.

R2: all 45 existing scoped assertions pass. Downloaded FF538 source and prepared a private 1515–1550-second context clip for the previously uncovered 1527–1538 sentence. Full source SHA-256: `7a5b2b51273569507d92528ce6bc7b06b3db4281e6f0ee7f498d7a6941f122bc`. The separate ASR model's two required text files repeatedly returned HTTP 403; stopped after bounded attempts. **No new ASR reading or source-accuracy certification was obtained.** Expectations, published picks, review overrides, prompts and provider defaults remain unchanged. Private diagnostic evidence is retained locally; temporary media/model/runtime files are removed after verification.

Next: independently check FF538's uncovered sentence when a working source-reading method is available; visually verify desktop/mobile journeys in the in-app browser when it responds. Pick history is the foundation for later Mentioned again/watchlist work, which is not part of this release.

Implementation `a0b17bc`; [production run 42957724939](https://github.com/courtjester15/ManaIntel/actions/runs/42957724939) passed tests, archive validation, artifact publication and Pages deployment. The served catalog reports 0.5.25 with the expected 139 episodes/539 picks and BB725/653/652 outcomes. All ten published assets match the release; only an exact unrelated network-viewer style prefix was excluded from the HTML comparisons. JavaScript and CSS comparisons are byte-for-byte. Deploy-only processing/media/provider steps were skipped, as intended. This confirms publication and served code, not visual layout or extraction correctness.
