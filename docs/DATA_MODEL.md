# ManaIntel Data Model

## Final-pass implemented boundary

The authoritative extraction contract remains `schemas/cards-to-watch.schema.json`. The final pass extends behavior with separate review files and derived display states; it does not require the deferred source-agnostic migration described later in this document.

### Review override

Review files live at `data/reviews/<episode-id>.json` and are durable manual input.

| Field | Type | Rule |
|---|---|---|
| `episode_id` | string | Required stable episode identity; must match the target extraction. |
| `reviewed_at` | date-time | Required timestamp for the review event. |
| `reviewed_by` | string | Required provenance; `manual` is sufficient for the single-user workflow. |
| `status` | enum | `reviewed` or `corrected`. |
| `pick_overrides` | array | Ordered update/add/exclude operations; may be empty for reviewed-without-changes. |

Each override contains `action: update | add | exclude`, an optional/required `source_pick_id` according to the action, and `fields` for update/add. Editable fields are card name, printing/set, finish, host/speaker, recommendation, current price, target price, summary, timestamp seconds, notes, and inclusion. Fields are optional and unknowns remain absent/null.

`update` and `exclude` require a valid original pick ID. `add` must receive a deterministic manual pick ID during application. The original extraction is never rewritten.

### Effective rendering

Projection generation loads the original episode summary, validates any matching review file, applies operations, and emits the effective picks. Review metadata is derived as:

- no review file + uncertainty: `Needs Review`
- no review file: `Unreviewed`
- `status: reviewed` with no material changes: `Reviewed — No Changes`
- `status: corrected` or material operations: `Manually Corrected`

Excluded picks remain auditable in original extraction and review history but do not appear in normal effective projections.

### Card-name resolution overlay

`state/card-resolutions.json` stores versioned catalog lookups keyed by the original stable pick ID. A resolution retains the raw extracted name, normalized lookup key, status, canonical Scryfall name, Oracle ID, lookup method, resolver version, and timestamp.

- `verified` means an exact, punctuation-normalized, or explicitly reviewed catalog-and-episode-context match and may supply the canonical display name. Reviewed matches retain a note and timestamp.
- `suggested` means Scryfall returned a fuzzy candidate; it is review assistance and must not silently replace the extraction.
- `automated_verification` records a bounded focused-audio second listen. A corrected name may replace the extracted card only when the verifier identifies it audibly and Scryfall independently verifies the exact catalog name; the original name and decision remain in the audit object.
- Matched records may retain the selected Scryfall printing ID, page URL, normal image URL, and per-face image URLs. These are display references only and do not change the canonical identity or original extraction.
- `not_found` records a completed lookup with no candidate.

Original summaries, `card`, and pick IDs remain unchanged. `archive/resolutions.json` and canonical fields in `archive/cards.json` are derived projections. A human review remains authoritative when it corrects a card name.

### Failure metadata

Operational failure data exposes `category`, `message`, `stage`, `attempt`, `max_attempts`, `retryable`, `provider_wide`, `next_retry_at`, and `quarantined`. Current categories are `transient_provider`, `provider_configuration`, `episode_input`, and `unknown`. The transition history supplies attempt timestamps. Transcription error messages also identify the failed chunk and request duration; raw provider/stack detail remains secondary.

### Display status derivation

Processing state, review state, correction presence, and exclusions combine into user-facing labels. Display labels do not need to expand the internal pipeline enum. In particular, `complete + needs_review` displays `Completed — Needs Review`, a valid review file displays `Reviewed` or `Manually Corrected`, and a durable exclusion displays `Excluded`.

## Deferred source-agnostic model boundary

ManaIntel normalizes every source into four concepts:

```text
Source -> Source item -> Recommendation -> Archive projection
```

The common contract described here is the target for a future ManaIntel schema. The implemented `schemas/cards-to-watch.schema.json` version 1.1.0 remains the authoritative FFW podcast contract until a new source-neutral schema and migration are added.

## Source

A source represents a publisher, show, channel, publication, or community feed.

| Field | Type | Rule |
|---|---|---|
| `id` | string | Stable internal identity; not derived only from mutable display name. |
| `name` | string | User-facing source name. |
| `source_type` | enum | `podcast`, `video`, `article`, `newsletter`, `community`, or a future versioned value. |
| `publisher` | string/null | Publisher or owning organization when distinct from the source name. |
| `url` | string/null | Canonical public source URL. |
| `adapter` | string | Adapter/configuration identity used for provenance. |

Policy and credentials belong in configuration or operational metadata, not public archive records.

## Source item

A source item is an episode, video, article, newsletter issue, post, or curated discussion summary.

| Field | Type | Rule |
|---|---|---|
| `id` | string | Stable ManaIntel identity scoped to its source. |
| `source_id` | string | Required reference to `source.id`. |
| `external_id` | string/null | Publisher-provided stable identity when available. |
| `item_type` | enum | `episode`, `video`, `article`, `newsletter_issue`, `post`, `discussion_summary`, or future versioned value. |
| `title` | string | Publisher-controlled display title. |
| `published_at` | date-time | Original publication time; preserves known timezone semantics. |
| `url` | string | Human-facing canonical item URL. |
| `contributors` | contributor[] | Hosts, authors, presenters, or explicitly identified participants. |
| `duration_seconds` | integer/null | Relevant for timed media; otherwise null. |
| `description` | string/null | Optional compact source description. |

Item identity must not depend only on title or publication date. Each adapter documents its preferred external ID and deterministic fallback.

## Recommendation

| Field | Type | Rule |
|---|---|---|
| `id` | string | Deterministic stable identity; never an array index. |
| `source_item_id` | string | Required provenance link. |
| `card` | string | Required source card name, normalized without losing source evidence. |
| `printing` | string/null | Exact printing only when supported. |
| `printing_certainty` | enum/null | `confirmed`, `likely`, `ambiguous`, or null. |
| `contributors` | contributor[] | People responsible for this recommendation when identifiable. |
| `summary` | string | Faithful action or stance; no added finance opinion. |
| `mentioned_prices` | price_mention[] | Prices discussed as context, distinct from targets. |
| `entry_target` | target/null | Suggested acquisition price or range when explicitly supported. |
| `exit_target` | target/null | Suggested sale price or range when explicitly supported. |
| `hold` | string/null | Duration or condition as expressed. |
| `reasoning` | string[] | Source reasoning only. |
| `caveats` | string[] | Source-stated risks and qualifications. |
| `source_confidence` | enum/null | Confidence stated or unmistakably expressed by the source. |
| `extraction_confidence` | enum/null | Pipeline confidence in the record, not investment confidence. |
| `reference` | source_reference | Timestamp, section, paragraph, message, or equivalent locator. |
| `evidence_excerpt` | string/null | Compact supporting excerpt when permitted. |
| `review_status` | enum | `pending`, `approved`, or `needs_review`. |
| `review_reason` | string/null | Actionable reason when review is required. |

### Contributor

At minimum, a contributor contains a display `name` and optional `role`. A future contributor registry may add stable IDs, but lack of a registry must not encourage guessed speaker attribution.

### Price mention and target

Price context and advice are semantically different and must remain separate.

```json
{
  "raw": "copies are around $11",
  "currency": "USD",
  "minimum": 11.0,
  "maximum": 11.0,
  "context": "current_market"
}
```

```json
{
  "raw": "buy these under $8",
  "currency": "USD",
  "minimum": null,
  "maximum": 8.0
}
```

`raw` preserves the source wording. Parsed currency and bounds are optional and must never be filled merely to make analytics easier. Foil status, printing, timeframe, and per-unit or lot context should be retained when the source makes them material.

### Source reference

A generic reference supports all source types without forcing fake timestamps:

| Field | Type | Examples |
|---|---|---|
| `kind` | enum | `timestamp`, `section`, `paragraph`, `page`, `message`, `url_fragment`. |
| `url` | string | Deep link where the source platform supports one. |
| `label` | string | `01:12:34`, `Budget Picks`, `paragraph 8`, or a message identifier. |
| `start_seconds` / `end_seconds` | integer/null | Timed media only. |
| `locator` | string/null | Adapter-specific opaque locator needed to verify the passage. |

The UI renders references generically based on available fields; it does not parse source-specific payloads.

## Confidence and review

Three concepts must not be collapsed:

- `source_confidence`: how strongly the source expressed the recommendation.
- `extraction_confidence`: how certain the pipeline is that it captured the source correctly.
- `review_status`: the editorial verification state of the record.

An enthusiastic source can still have a low-confidence extraction, and an approved extraction is not an endorsement by ManaIntel.

## Stable identifiers

The current FFW recommendation ID hashes normalized episode GUID, card name, start seconds, and printing. The common model retains that principle but scopes identity to a source item and generic reference:

```text
normalized source item ID | normalized card | normalized reference identity | normalized printing
```

The exact canonicalization must be specified in the future schema implementation and covered by fixtures before migration. Material corrections may create a new ID; an alias or supersession mechanism can later preserve external links when necessary.

## Processing metadata

Processing metadata is associated with an ingestion attempt or source item, rather than embedded as recommendation meaning. It includes:

- Adapter, pipeline, schema, extraction, and prompt versions.
- Processing timestamps and state history.
- Review summary and reasons.
- Structured retryable or terminal failures.
- Content acquisition and retention facts needed for audit.

The current FFW queue serializes `detected`, `queued`, `downloading`, `downloaded`, `preparing`, `transcribing`, `transcribed`, `extracting`, `extracted`, `validating`, `publishing`, `complete`, `needs_review`, and `failed`. Each record retains transition history, attempt count, a useful failure stage/message, and whether a live failure is retryable.

Feed selection treats `complete` and `needs_review` as successful terminal states and uses the GUID-keyed records as the historical cursor. Failed records remain durable but are eligible only for explicit failed-only retry; unseen and interrupted nonterminal records remain eligible for ordinary newest-first selection.

## Archive projections

Canonical records are the source of truth. Search indexes, flattened recommendation catalogs, Markdown summaries, dashboards, and future analytics are rebuildable projections.

A flattened recommendation may repeat source and item display fields for efficient static search. That denormalization is a projection convenience, not a second canonical record.

## FFW v1 mapping

| FFW v1 | ManaIntel target |
|---|---|
| Single configured feed name | `source` record. |
| `episode` | `source_item` with `item_type: episode`. |
| Episode `guid` | Preferred `external_id` and input to stable source-item ID. |
| Episode `hosts` | Source-item contributors. |
| Recommendation `hosts` | Recommendation contributors. |
| `recommendation` | `summary`. |
| `mentioned_price` | One or more `mentioned_prices` records after lossless migration. |
| `entry_target` / `exit_target` | Same semantic target fields. |
| `confidence` | `source_confidence` only when it describes the host's stance; otherwise migration requires review. |
| Timestamp fields and `listen_url` | `reference` with `kind: timestamp`. |
| `review_status` | Same editorial state. |
| Episode `processing` | Source-item ingestion-attempt metadata. |

No v1 file should be silently reinterpreted. Ambiguous confidence or price fields must remain null or route to review during migration.
