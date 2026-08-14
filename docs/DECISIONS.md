# ManaIntel and FFW Architecture Decisions

## ADR-001 — Python package is `ffw`

**Decision:** Use `ffw` and expose `python -m ffw`.

**Reason:** This matches the internal project identity and keeps the CLI concise. The longer repository name remains useful externally.

## ADR-002 — JSON is the integration boundary

**Decision:** The pipeline and frontend share versioned generated JSON and nothing else.

**Reason:** The archive can remain static, future Pages publication is simple, and ManaSpec can consume data without importing pipeline internals.

## ADR-003 — Standard library first

**Decision:** Revision 1 used no downloaded runtime packages. The UI continues to use native JavaScript, `Intl`, tables, and `<dialog>`. Version 0.2 adds the official OpenAI Python dependency for opt-in live adapters while mock mode remains credential-free.

**Reason:** The workspace contained no approved local copies of Tabulator, Fuse.js, Day.js, Micromodal, or Tippy.js. Native frontend implementations are sufficient for the current archive. The live model API is a separate integration need and does not justify unrelated UI dependencies.

**Future recommendation:** Evaluate Fuse.js when fuzzy search is needed and Tabulator when sorting, column controls, or thousands of rows justify the dependency. Keep library files vendored or pinned rather than CDN-dependent.

## ADR-004 — Stable pick IDs use content identity, not array index

**Decision:** Hash GUID, card, timestamp, and printing.

**Reason:** Array indexes change when extraction order changes. The selected identity remains stable during unrelated additions and supports repeated cards.

## ADR-005 — Failed episodes publish metadata only

**Decision:** A failed folder contains `metadata.json`; summary outputs are null and absent.

**Reason:** Empty or fabricated summaries would look successful. The catalog still needs the failure for status reporting.

## ADR-006 — Full transcripts are not durable archive output

**Decision:** Keep only short evidence excerpts and timestamps in the published contract.

**Reason:** This limits repository growth and copyright exposure while retaining an audit trail. Production debugging may use short-lived protected artifacts.

## ADR-007 — Git JSON state is sufficient for v1

**Decision:** Store episode state in one atomic JSON manifest keyed by GUID.

**Reason:** The expected cadence and concurrency are tiny. A database would add operational burden without improving the local experiment. GitHub Actions must later serialize runs with a concurrency group.

## ADR-008 — Review is data, not an exception

**Decision:** `needs_review` is a successful extraction outcome with complete outputs; infrastructure or stage errors are `failed`.

**Reason:** Ambiguity is expected in speech. Preserving uncertain results for review is different from pretending the pipeline could not run.

## ADR-009 — Current fixture corpus stays conspicuously synthetic

**Decision:** Every fixture title, evidence quote, catalog, summary, and screen carries a synthetic marker.

**Reason:** Test recommendations must never be confused with host statements or actionable financial advice.

## ADR-010 — ManaIntel is the product; FFW is the first adapter

**Decision:** Treat the existing `ffw` package and episode contract as the MTG Fast Finance proof of concept and first source adapter, not as the final product boundary.

**Reason:** The implemented pipeline is valuable and testable, but podcast-specific concepts cannot represent video, written, and community sources without leaking special cases throughout the system.

## ADR-011 — Normalize to source, source item, and recommendation

**Decision:** Future adapters publish a common hierarchy of `source -> source_item -> recommendation`. The frontend consumes only common archive projections.

**Reason:** Source acquisition varies substantially, while the user-facing questions and recommendation fields remain consistent. Normalization keeps source-specific complexity at the ingestion edge.

## ADR-012 — Provenance is required and source-type neutral

**Decision:** Every published recommendation requires a generic source reference and compact evidence where permitted. References support timestamps, sections, paragraphs, pages, messages, and deep links.

**Reason:** A timestamp-only contract excludes written and community sources. A generic locator preserves verification without inventing a media-specific field.

## ADR-013 — Separate price context, targets, and confidence types

**Decision:** Mentioned prices are modeled separately from entry and exit targets. Source-stated confidence, extraction confidence, and review status are also distinct.

**Reason:** Collapsing these concepts changes source meaning. A market price is not automatically an entry recommendation, and pipeline certainty is not investment conviction.

## ADR-014 — Analytics and ManaSpec integration are projections, not ingestion concerns

**Decision:** Defer trends, reliability, portfolio features, and ManaSpec workflows. Future analytics and integrations consume versioned canonical recommendations or rebuildable projections.

**Reason:** ManaIntel's first responsibility is a trustworthy archive. Keeping downstream analysis outside ingestion prevents speculative product features from distorting captured source data.

## ADR-015 — Migrate additively through an FFW normalizer

**Decision:** Introduce the common contract beside v1 and map existing FFW summaries into it before replacing v1 paths or adding multiple adapters.

**Reason:** An additive compatibility layer preserves the working proof of concept, makes migration testable, and proves the common model against real implementation constraints.

## ADR-016 — GitHub Actions is the Revision 2 production host

**Decision:** Run one serialized daily workflow at 10:17 UTC, commit durable JSON state and generated outputs with the Actions bot, and deploy a clean GitHub Pages artifact.

**Reason:** The podcast cadence and sequential workload fit hosted runners, repository JSON remains auditable, Pages serves the existing static contract, and Jason's laptop can remain off. Audio and transcripts are disposable runner data. A database or long-running host becomes appropriate only if runner limits, concurrency, archive scale, or review workflows outgrow this model.

## ADR-017 — OpenAI diarized transcription plus structured extraction

**Decision:** Split normalized mono audio below provider upload limits, transcribe with configurable `gpt-4o-transcribe-diarize`, detect Cards to Watch boundaries separately, and extract with configurable schema-constrained Responses API output. The initial extraction default is `gpt-5.6-luna` for cost-sensitive structured work.

**Reason:** Diarized segments provide the timestamps and speaker hints required for evidence, while a separate structured pass prevents whole-episode summarization and enforces null handling. Model names remain environment-configurable as availability and cost change.

## ADR-018 — Durable state is the historical backfill cursor

**Decision:** Select feed items newest to oldest using one state-aware selector. `complete` and `needs_review` are ineligible, failed records are eligible only under the failed-only policy, and live limits count selected eligible episodes rather than feed positions. Scheduled runs use `next` with an effective maximum of one. Exact GUID overrides search the full fetched feed.

**Reason:** Feed positions change as episodes are published or reordered. Durable GUID-keyed outcomes already identify completed work, prioritize new releases naturally, and let historical backfill resume without a fragile numeric cursor. Filtering before acquisition prevents duplicate provider cost, while an empty selection avoids meaningless generated timestamp changes and commits.

## ADR-019 — ManaIntel enters maintenance mode after a bounded final pass

**Decision:** Limit remaining feature development to approximately five hours focused on correction, playback, status clarity, exact recovery, and no-op behavior. Then stop unless a production failure prevents the utility from doing its basic job. This supersedes the active expansion implied by ADR-010 and ADR-015; their source-agnostic design remains historical context only.

**Reason:** The single-source archive already proves the useful workflow. Additional abstraction and sources have lower portfolio value than getting ManaSpec into users' hands and moving primary development to GalleyFlow.

## ADR-020 — Manual corrections are durable overrides

**Decision:** Preserve original machine extraction and store reviews separately under `data/reviews/`. Generated views apply validated update/add/exclude operations to produce an effective result.

**Reason:** Directly editing generated summaries destroys provenance and is vulnerable to rebuilds. A small override layer is auditable, reversible, compatible with static hosting, and sufficient for one reviewer.

## ADR-021 — GitHub Pages remains static

**Decision:** The review editor copies or downloads correction JSON. Do not add a hosted backend, user accounts, embedded GitHub token, or complex authenticated write flow.

**Reason:** Static Pages is operationally cheap and already deployed. A manual repository step is acceptable for the expected correction volume and fits the final-pass time constraint.

## ADR-022 — Podcast audio remains remote

**Decision:** Play the RSS enclosure URL through an in-page HTML audio element and seek after metadata loads. Keep the original episode URL as fallback; do not store, proxy, or mirror audio.

**Reason:** Remote playback enables useful timestamp verification without repository growth, copyright/retention expansion, or a new media service.

## ADR-023 — No-op means no publish churn

**Decision:** An empty selection must leave state and projections unchanged, create no commit, and skip an unchanged Pages deployment.

**Reason:** Run timestamps and deployment churn are not product output. A true no-op makes scheduled behavior auditable and avoids misleading activity.

## ADR-024 — Production provider is configurable; workflow default is Gemini

**Decision:** Retain both Gemini and OpenAI adapters. The checked-in GitHub workflow pins `gemini-3.5-flash` for transcription and extraction. Transient transcription failures receive one short primary retry and then one same-key request to `gemini-3.5-flash-lite`; model/provider values remain environment configuration rather than product architecture.

**Reason:** Provider availability and cost change. A bounded same-provider fallback prevents temporary capacity trouble from consuming a full episode attempt while avoiding new credentials or an unbounded provider carousel. Operational documentation must describe the checked-in default without coupling the archive contract to it.

## ADR-025 — Fresh backfill and failed recovery use separate bounded schedules

**Decision:** Run `next` at 10:17 UTC and `retry_then_next` at 20:17 UTC. The fresh run always selects the newest untouched episode and skips failed records. The evening run selects at most one episode: the newest due retryable failure after a six-hour cooldown, otherwise the newest untouched episode across both feeds. Automatic selectors ignore episodes older than the configured age window; only an explicit GUID can bypass it. Each episode receives at most three total attempts before quarantine. Transient provider failures remain retryable even when they stop the current batch; permanent provider configuration failures and episode-specific bad input do not loop.

**Reason:** A broken episode must not stall historical progress, but transient network, capacity, and quota failures should recover without manual dispatch. Separate schedules preserve a guaranteed fresh-work slot, spread free-tier requests across the day, and cap wasted provider calls when an episode is genuinely bad.

## ADR-026 — Add Brainstorm Brewery through a compatibility-first podcast adapter

**Decision:** Enable Brainstorm Brewery beside MTG Fast Finance, preserve every existing FFW GUID, namespace new Brainstorm Brewery GUIDs, and merge candidates newest-first. Normal schedules choose the newest eligible episode across enabled sources; manual runs may filter to one source. Each source owns its recommendation-section profile, while archive projections remain backward compatible.

**Reason:** The second source adds useful coverage without requiring a disruptive schema rewrite. Namespaced new identities prevent cross-feed collisions, source-specific section detection limits false picks, and source filtering makes controlled testing and backfill possible.

## ADR-027 — Exact retries remain token-free on static Pages

**Decision:** Failed episode details copy the canonical GUID and link to the workflow dispatch page. The operator pastes that GUID into `force_guid`; exact selection bypasses cooldown and quarantine. Pages does not store a GitHub token or dispatch authenticated workflow writes.

**Reason:** This removes GUID hunting while preserving the static site's security boundary. A true one-click retry would require an authenticated backend or GitHub App and is not justified for the current volume.

## Known risks

- The manual validator implements project invariants but does not execute the full JSON Schema vocabulary because no JSON Schema package was downloaded.
- Semantic fabrication cannot be detected by structural validation alone; production needs evaluation fixtures and review thresholds.
- A single JSON state file assumes serialized writers.
- Timestamp URL fragments are not supported uniformly by podcast hosts.
- Native table rendering is intentionally simple and may need virtualization for a large historical archive.
- Corrected card names, printings, or timestamps can change deterministic IDs; future imports may require an alias map.
