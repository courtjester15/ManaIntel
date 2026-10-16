# ManaIntel Product Vision

> **Active scope (2026-10-15):** Improve the shipped MTG Fast Finance and Brainstorm Brewery archive through the [0.6–1.0 roadmap](ROADMAP.md), using the [hands-off working agreement](WORKING_AGREEMENT.md). This supersedes the July maintenance-only/five-hour restriction. Broader cross-media expansion remains historical product thinking.

## Product definition

ManaIntel is a lightweight archive organizing source-attributed Magic: The Gathering recommendations. The shipped product supports two podcasts. Its next improvements focus on reliability, correction, memory and small inspectable archive observations.

Its primary job is to answer:

> Who recommended what, when, and why?

ManaIntel is an information aggregator. It is not a price tracker, portfolio manager, recommendation engine, or AI analyst. It preserves and organizes source claims; the user decides what matters.

## Product promise

A user should be able to quickly answer:

- What cards were recommended this week?
- Which source recommended this card?
- When was it first mentioned?
- What entry or target price was suggested?
- What exactly was said, and where can I verify it?

If these questions are easy to answer, ManaIntel has accomplished its mission.

## Historical broader MVP concept

For every recommendation, capture and display:

- Source and contributor.
- Source item: episode, video, article, newsletter, or discussion.
- Publication date.
- Card name and printing when explicitly identified.
- Faithful recommendation summary.
- Mentioned prices.
- Suggested entry and exit targets when available.
- Timestamp, section, paragraph, or other source reference.
- Short supporting evidence where permitted.
- Confidence and review status.

The MVP is a clean searchable archive over those records. It does not require analytics, live prices, accounts, portfolios, alerts, or automated investment judgments.

## Historical source-expansion ideas

The earlier broader vision proposed adapters for the following. Additional adapters are not an active commitment:

- Podcasts, beginning with MTG Fast Finance and potentially other finance shows.
- Videos from trusted MTG finance creators.
- Articles, blogs, and newsletters where access and reuse are permitted.
- Public community discussions and curated summaries.

Adding a source must not require source-specific behavior in the archive UI. Each adapter discovers a source item, obtains permitted content, extracts recommendations, attaches evidence, and publishes the common contract.

Source support is not the same as permission to ingest. Paywalled, private, licensed, or community content must be handled according to its access terms and should store only the minimum evidence needed for verification.

## Archive observations and deferred analytics

Roadmap 0.9 permits simple observations over recorded recommendations, with evidence links, coverage limitations and reproducible counts. Earlier broader ideas included:

- Repeated mentions and first/most-recent mention dates.
- Independent-source agreement or disagreement.
- Recommendation history for a card.
- Average stated entry and exit targets.
- Mention frequency.
- Carefully defined source reliability measures.

These are projections rather than ingestion concerns. Only the limited observations named in the active roadmap are authorized; financial-performance/reliability scoring and external-price analysis remain deferred. An opaque AI score is not a substitute for evidence.

## Relationship with ManaSpec

ManaIntel gathers and exposes structured source information. ManaSpec may later consume that information for watchlists, positions, and speculation workflows.

```text
ManaIntel recommendations -> versioned export/API -> ManaSpec decision workflow
```

ManaSpec should not duplicate ManaIntel's collection pipeline, and ManaIntel should not absorb ManaSpec's portfolio or decision-making responsibilities.

## Implementation direction

Keep the existing `ffw` package, two podcast adapters, durable episode identities, versioned JSON/Markdown, review overrides and static Pages frontend. Extend rebuildable views and focused workflows as the roadmap earns them.

The product does not need a generic source-item migration, new backend or framework rewrite to reach 1.0. Future expansion requires a separate concrete product decision.
