# ManaIntel Product Specification

## Purpose

ManaIntel is a small, readable, correctable archive of explicit recommendation segments from MTG Fast Finance and Brainstorm Brewery. The canonical user question is:

> Who recommended what, when, and why?

The existing two-podcast FFW pipeline and static archive are the supported product boundary. Earlier cross-media/source-agnostic concepts remain research; additional source expansion is outside the active roadmap.

## Active development scope

The October 15, 2026 [roadmap](ROADMAP.md) supersedes the maintenance-only/five-hour final-pass restriction. Improve reliability first (0.6), then review (0.7), card history/search (0.8), small evidence-linked archive observations (0.9), and overall readiness (1.0). These are incremental capabilities over the existing product, with acceptance evidence and no fixed release dates. The [working agreement](WORKING_AGREEMENT.md) defines bounded agent-led sessions and routine deployment; it creates no recurring development automation.

## Current supported workflow

1. A morning scheduled run selects the next untouched feed episode using durable state before applying its limit; a later bounded run retries at most one due transient failure.
2. Successful episodes publish readable summaries; failed episodes publish understandable status without fabricated picks.
3. Jason reviews an episode in the static UI and copies or downloads a correction JSON file.
4. The correction file is stored as durable source data and applied over, never written into, the original extraction.
5. A pick timestamp opens remote RSS audio and seeks near the referenced moment.
6. Failed or exact episodes can be retried deliberately without processing unrelated work.

### User-visible episode states

The UI communicates `Unseen`, `Processing`, `Completed`, `Completed — Needs Review`, `Reviewed`, `Manually Corrected`, `Failed`, `Skipped`, and `Excluded`. These display states may be derived from simpler processing and review fields.

### Review and correction

The Review action supports editing, adding, confirming, and excluding picks; marking an episode reviewed; cancelling; and producing a JSON override for `data/reviews/<episode-id>.json`. Browser edits do not directly commit to GitHub. Rebuilds preserve the original extraction, the manual override, and the effective displayed result.

### Timestamp playback

Timestamp links carry a seconds value in the page URL and control an in-page HTML audio player using the RSS enclosure URL. The player seeks only after metadata loads, handles autoplay denial and media-host failures, and always offers the original episode page as a fallback. Podcast audio is not stored or proxied.

### Backfill and retry expectations

- Scheduled `next` runs prioritize new releases, then continue historical progress one eligible episode at a time.
- `backfill` processes a bounded eligible batch in deterministic order and resumes from durable state.
- `retry-failed` selects only due retryable failed records, respects cooldown, and stops selecting an episode after three total attempts.
- Exact-GUID processing selects only the requested feed episode.
- A no-op does not rewrite projections, create a commit, or deploy an unchanged site.

## Historical source-agnostic product surfaces (deferred)

### Source ingestion

Every source adapter implements the same conceptual flow:

```text
discover source item -> acquire permitted content -> locate relevant material
  -> extract recommendations -> validate evidence -> publish common records
```

Source-specific work ends at normalization. Podcast transcription, video captions, HTML parsing, and community import are adapter concerns and must not leak into the archive or frontend.

### Recommendation archive

The MVP archive provides:

- A chronological view of recent recommendations.
- Search by card, source, contributor, source-item title, and recommendation text.
- Filters for publication date, source, source type, and review status.
- Recommendation detail with mentioned prices, targets, reasoning, confidence, and evidence.
- A link or reference back to the exact location in the source when possible.
- Visible processing and review status; uncertain records are never silently presented as approved.

## Historical source-agnostic requirements (deferred)

1. Each source, source item, and recommendation has a stable identity.
2. Reprocessing a source item does not create duplicate recommendations.
3. Every recommendation identifies its source item, publication date, card, and faithful recommendation summary.
4. Mentioned market prices remain distinct from suggested entry and exit targets.
5. Unknown values remain `null`; extraction must not invent missing context.
6. Every published recommendation has a timestamp or source reference and short supporting evidence where permitted.
7. Confidence and review status are stored as data and exposed in the UI.
8. Failed ingestion remains auditable without publishing a fabricated or empty successful result.
9. The frontend consumes only the common archive contract and contains no source-specific parsing or presentation logic.
10. Generated or extracted text is clearly attributable to its source and can be verified against the source reference.
11. The archive supports deterministic rebuilds of derived catalogs and views.
12. Export boundaries are versioned so future consumers such as ManaSpec do not import pipeline internals.

## Historical source-agnostic entities (deferred)

```text
Source -> Source item -> Recommendation -> Archive projections
```

- A **source** is a publisher, show, channel, publication, or community feed.
- A **source item** is an episode, video, article, newsletter issue, post, or curated discussion summary.
- A **recommendation** is a source-attributed claim about a card, with supporting context and evidence.
- An **archive projection** is a rebuildable search or display representation of canonical records.

See [Data Model](DATA_MODEL.md) for the target contract and the mapping from the current episode schema.

## Trust and content requirements

- Preserve source wording for prices and targets alongside any parsed numeric values.
- Keep evidence excerpts compact and store only content that is permitted and necessary.
- Distinguish source confidence from extraction confidence and editorial review status.
- Do not infer financial advice, sentiment, targets, speakers, printings, or currencies without support.
- Treat all imported content and extracted output as untrusted input.
- Clearly identify synthetic fixtures so they cannot be mistaken for real recommendations.

## Explicit non-goals

- Live card-price tracking or market data.
- Price prediction, automated picks, or AI investment analysis.
- Portfolio, position, or transaction management.
- Performance scoring or source leaderboards.
- Recommendation alerts or trading automation.
- Social features or user-generated investment advice.
- Direct ManaSpec workflow integration.
- Additional sources or a source-agnostic schema migration.
- Authenticated editing from the static site.
- A hosted backend or database.
- Broad visual redesign or framework conversion.
- Market trends, financial-performance/reliability scoring, or inferred source opinions. The limited source-backed archive observations in roadmap 0.9 are in scope.

## Current archive acceptance criteria

The current implementation retains these acceptance criteria without requiring a generic source-contract migration:

- RSS GUID is the stable episode identity.
- Terminal episodes are skipped on ordinary reruns.
- Successful episodes publish `metadata.json`, `summary.json`, and deterministic `summary.md`.
- Failed episodes publish metadata without a false summary.
- `archive/index.json` and `archive/cards.json` are rebuildable frontend projections.
- Every recommendation has a deterministic ID, timestamp, evidence excerpt, and review state.
- The synthetic fixture set exercises repeats, missing values, ambiguous speech, multiple hosts, and failure handling.

## Final success measures

- Jason can identify the episode, pick, recommendation, source time, processing status, and review status without inspecting raw pipeline data.
- No duplicate source item or recommendation is published during normal reprocessing.
- Card names, source attribution, prices, and references meet thresholds defined on representative evaluation fixtures.
- Unsupported values are absent rather than inferred.
- Ambiguous records route to review with an actionable reason.
- A failed run can retry without corrupting or duplicating published data.
- Manual corrections survive deterministic rebuilds without changing original extraction.
- Remote audio seeks near the selected timestamp or provides a clear source fallback.
- Empty scheduled runs do not create archive, commit, or deployment churn.
