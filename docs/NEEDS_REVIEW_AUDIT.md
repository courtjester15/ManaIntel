# Needs-review audit and proposed automation plan

Snapshot: October 16, 2026, production catalog generated 2026-10-17T00:35:11Z. Planning only: no picks, review statuses, prompts or defaults changed; no inference calls made.

## Scope and evidence

Inspected all 40 current needs-review effective summaries and all 168 contained picks: episode/section/pick reasons, boundaries, clocks, excerpts, versions, transcription diagnostics, recorded verification and cached card resolutions. Initial sample included BB 721/719/718/715/712 and FF 534; expanded to the entire set. Compared available attempt journals for FF 494/495/510 and BB 666/721, and replayed five locally retained transcript snapshots through today's boundary/timing/content checks. Saved snapshots are historical evidence, not guaranteed to match the latest repaired publication. Full audio was not independently listened to. No source-accuracy score or automatic approvals follow from this audit.

Eight legacy catalog entries lack explicit source IDs; they are labelled legacy below rather than silently assigned from episode numbers. 39 summaries carry a pipeline version older than 0.5.12; the one 0.5.12 record is a preservation outcome, not proof of a new extraction.

## Findings

- 33/40 episodes have a section boundary warning; 23/40 have all picks machine-approved. These are overlapping sets, not independent clearance estimates. All 23 also have boundary warnings, but FF 494/501 additionally preserve prior results after lossy reprocessing and FF 510 flags low count.
- 17 episodes contain 21 flagged picks, out of 168 total. Cached catalog results: 13 exact/normalized verified identities, five suggestions, three not found. All picks combined: 142 verified, 11 suggested, 15 not found. Catalog identity is not proof of audible identity or recommendation intent.
- 18 episodes record timestamp adjustments. Five picks end after the catalog's stated audio duration; eight episodes share pick-start timestamps; one current pick (BB 666 Atraxa) starts outside its published section. These are diagnostic discrepancies, not five proven audio failures: feed duration and generated clocks both need checking.
- Twelve warned sections span more than 50 minutes. Several begin at 20–125 seconds. This is consistent with agenda/whole-show selection, so removing ending-marker requirements alone would conceal coverage errors.
- Of 21 flagged picks, 16 have no recorded focused verification; four record ambiguous and one confirmed-but-not-accepted. Absence of telemetry does not establish why a check was skipped. Current eligibility relies on reason-string substrings and only checks two picks per episode.

## Representative evidence

BB 721: three machine-approved picks, boundary warning, section 180–3642. Saved transcript tail sounds like opening agenda material despite being at the end; current replay reproduces the warning while timing and omission heuristics report no issue. Suggests semantic clock/order or repeated content needs testing; not proof without audio.

FF 531 and legacy FF-range records 521–529: several very early starts and large extraction windows. FF 524 contains two Cyclonic Rift records; preserve both until printing/evidence comparison establishes whether they are distinct. A fixed pick count cannot certify completeness.

BB 718: Tormod has multiple versions/prices, not necessarily an uncertain card. FF 511 Regal Sliver and FF 496 Horde of Notions involve disagreement/risk; that is source content rather than automatically an extraction defect. FF 534 combines disagreement with clustered timestamps, so fixing caveat policy alone cannot clear it.

FF 528 Collective Inferno, BB 699 North Wind Avatar and FF 513 Exalted Sunborn: model warnings say unknown card while our cached catalog verifies the recorded name. The catalog contradicts the nonexistence rationale but cannot certify the transcript. FF 513's second listen heard unrelated discussion, making clock/clip selection a prerequisite to another name check.

BB 672: audio checker confirmed the short name Vivi, but catalog acceptance failed; its explanation asserted a different game's context. Do not use explanation prose as authoritative game classification. BB 715/687 similarly mix possible names, scope and model knowledge limitations.

BB 693: recorded output describes an April Fools Slay the Spire recommendation. Candidate for an evidence-backed out-of-scope/no-MTG-recommendations disposition, not a guessed MTG replacement or silent deletion.

FF 494/501: prior picks survived newer zero/omitting extractions. This guard is valuable. FF 494 latest attempt is 0.5.12, so upgrading/repeating the same pipeline is demonstrably insufficient.

Offline replay of available FF 494/495/510 and BB 666/721 snapshots reproduces all five boundary warnings. Timing/omission heuristics passed those snapshots; this does not establish faithful speech or complete audio coverage. BB 666 snapshot is older than its latest repairs and cannot explain every current discrepancy.

## Proposed work, in order

1. **Structured issue ledger and offline re-evaluation.** Record separate issue codes for boundary/coverage, audible identity, printing/price association, intent, scope and clock alignment. Store evidence and resolution method per issue. Clear only the resolved issue; derive episode state from unresolved issues. First audit old reason strings into proposed codes without changing status. Current global/free-text clearing can erase unrelated warnings and stale parent reasons can survive corrected picks.
2. **Coverage before cleanup.** Identify multiple recommendation windows (especially BB Breaking Bulk and Pick of the Week), not a single giant interval. Distinguish agendas, recommendation speech, topic transitions, ads and signoff. Use verified audio duration plus terminal speech/transition evidence as alternatives to one exact end phrase. Full-text vs timed coverage and a second independent recommendation-cue inventory should account for every candidate block. Never accept silence, N picks or model agreement alone as completeness evidence.
3. **Repair only the suspect audio.** Check duplicate starts, chunk-edge clustering, repeated intro/outro text, duration overrun and picks outside selected windows. Find distinctive quote anchors in retained text, then confirm short audio clips around those anchors. Use overlapping clip boundaries to avoid cutting a name. Replay saved repairs first, then at most two suspect windows per episode with a total call budget and checkpointed progress. A miss should widen or relocate once, not retry the same wrong 55-second clip.
4. **Catalog-assisted identity, without catalog hallucinations.** Supply exact current catalog candidates to the verifier before asking whether a name exists. Support spoken aliases/short names only when one catalog candidate plus the surrounding audible description uniquely identifies it. Fuzzy matches remain suggestions. Verify the spoken name and recommendation separately; preserve original spelling/evidence and correction history. Do not let mere name confirmation clear printing, scope or timing issues.
5. **Represent nuance rather than flag it.** An explicit recommendation with disagreement, reprint risk or a conditional entry price can be complete with attributed caveats and nullable targets. A generic 'check it out' or market commentary should not become an invented buy. Re-extract evidence with an explicit intent classification and resolve to recommendation/commentary/uncertain. Keep uncertain cases reviewable; preserve old records with auditable exclusion rather than silently dropping them.
6. **Printing/price evidence and scope dispositions.** Bind price to variant in the same supported speech window; split explicitly distinct variants or leave optional printing unknown when card-level intent is clear. Do not imply a price applies to every variant. Add a verified out-of-scope/no-recommendations disposition for confirmed joke/non-MTG material, preserving source/exclusion reasons. Sealed MTG products stay in scope and should not be rejected for failing a card-only catalog lookup.
7. **A bounded recovery queue.** Start with five pilots: BB 721 boundary, FF 495 timing/boundary, FF 513 identity plus wrong clip, BB 718 variant prices, FF 511 disagreement. Only after passing targeted expected-result tests, expand by issue cohort. Keep FF 494/501 protected until all prior picks are explicitly accounted for. Process one episode at a time, reuse transcripts, obey free-tier limits/circuits, save partial progress and stop deterministic failures. Schedule recovery capacity without starving new releases; do not blindly rerun all 40.

## Acceptance and realistic outcome

No blanket approval. For each cleared issue, require persisted evidence, unchanged known-good picks/IDs/overrides, valid audio bounds, supporting audible identity/intent and resolved coverage. Validate negative controls: jokes, uncertain aliases, missing chunks, conflicting variants and deliberate omissions must remain unresolved or receive an evidence-backed exclusion. Audit a small source-checked sample before broad rollout; an AI checking its own summary is not independent evidence.

The largest opportunity is the 33-episode boundary cohort, but it is not a promise to clear 33 episodes. The 23 with machine-approved picks are triage candidates, not established accurate records. Some can likely become unattended; ambiguous audio or unsupported intent may remain unknown. The goal is zero unnecessary human review, with safe automatic abstention when evidence cannot settle a claim.

## Episode inventory

Flags below overlap. B = section boundary; P = flagged picks; T = recorded timing adjustments; S = protected previous output after lossy reprocessing. Every row's full pick-level reasons were inspected. 'None' means no flagged pick, not independent accuracy approval.

| Episode | Source | Picks | Flags | Flagged picks / main extra issue |
| --- | --- | ---: | --- | --- |
| 721 | brainstorm-brewery | 3 | B, T | None |
| 719 | brainstorm-brewery | 5 | B, P, T | Shaman en-Kor |
| 718 | brainstorm-brewery | 5 | P, T | Tormod, the Desecrator |
| 534 | mtg-fast-finance | 5 | P, T | Depala, Pilot Exemplar |
| 715 | brainstorm-brewery | 6 | P, T | Summoner, Exalted Sanborn |
| 712 | brainstorm-brewery | 5 | B | None |
| 531 | mtg-fast-finance | 7 | B | None |
| 529 | legacy source ID missing | 4 | B, P | Undergrowth Stadium |
| 528 | legacy source ID missing | 4 | B, P | Uthro's Titanic God-Hood, Collective Inferno |
| 527 | legacy source ID missing | 6 | B | None |
| 704 | brainstorm-brewery | 4 | B | None |
| 526 | legacy source ID missing | 4 | B | None |
| 524 | legacy source ID missing | 5 | B | None |
| 523 | legacy source ID missing | 4 | B | None |
| 701 | brainstorm-brewery | 4 | B | None |
| 522 | legacy source ID missing | 4 | B | None |
| 699 | brainstorm-brewery | 4 | B, P | North Wind Avatar, flashback |
| 521 | legacy source ID missing | 5 | B | None |
| 693 | brainstorm-brewery | 1 | B, P | The Hunt |
| 689 | brainstorm-brewery | 5 | P, T | Cyberman Patrol |
| 688 | brainstorm-brewery | 6 | P, T | Fire Crystal |
| 687 | brainstorm-brewery | 4 | P, T | Earthbending Ascendancy, Vibrants |
| 513 | mtg-fast-finance | 4 | B, P, T | Exalted Sunborn |
| 511 | mtg-fast-finance | 4 | B, P, T | Regal Sliver |
| 510 | mtg-fast-finance | 2 | B, T | None; low-count completeness warning |
| 503 | mtg-fast-finance | 3 | B, P, T | Urza's Saga |
| 501 | mtg-fast-finance | 3 | B, T, S | None; preserved prior picks |
| 672 | brainstorm-brewery | 3 | B, P, T | Vivi |
| 496 | mtg-fast-finance | 4 | B, P, T | Horde of Notions |
| 668 | brainstorm-brewery | 3 | P, T | Three Steps Ahead |
| 495 | mtg-fast-finance | 4 | B, T | None |
| 494 | mtg-fast-finance | 3 | B, S | None; preserved prior picks |
| 666 | brainstorm-brewery | 3 | B, T | None |
| 42 | mtg-fast-finance | 5 | B | None |
| 41 | mtg-fast-finance | 5 | B | None |
| 40 | mtg-fast-finance | 5 | B | None |
| 39 | mtg-fast-finance | 3 | B | None |
| 38 | mtg-fast-finance | 5 | B | None |
| 37 | mtg-fast-finance | 4 | B | None |
| 36 | mtg-fast-finance | 5 | B | None |
