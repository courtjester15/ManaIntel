# MTGStocks Cheap Pickups: runner pilot and integration decision

November 13, 2026, America/New_York. This replaces the initial architecture
proposal with the owner-approved pilot scope and actual GitHub runner result.

## Decision: NO-GO for unattended ingestion through the tested route

The known public Atom feed works on GitHub Actions, but its newest article is
behind an AWS WAF challenge. The runner received HTTP 202, not usable article
content. Following the explicit stop condition, no older article requests,
alternate endpoint probing, browser challenges, proxy workarounds or bulk
discovery were attempted after that result.

This is an acquisition failure, not a successful empty import. No pickup rows
were extracted or accepted. This does not establish that the source can never be
integrated; a supported, publisher-permitted way to obtain the section would be
needed before another pilot.

Evidence:

- [GitHub Actions run 43543988228](https://github.com/courtjester15/ManaIntel/actions/runs/43543988228)
- Probe commit: `52f6a79`, isolated branch `codex/mtgstocks-ingestion-pilot`.
- Hosted runner: Linux, Ubuntu 26.04.1, image `ubuntu-26.04`, Azure eastus.
- Check started November 13 at 9:01:57 p.m. EST (`2026-11-14T02:01:57Z`).
- [Retained compact runner result](MTGSTOCKS_PILOT_2026-11-13.json) contains
  request URLs, statuses, selected response headers, byte counts, response hashes,
  discovered article identities and the explicit no-go. Teasers were removed.
- The temporary Actions artifact contains the original compact JSON, expires
  after three days, and contains no article body. The committed result preserves
  the useful evidence independently of artifact retention.

| Runner request | Observed result | Meaning |
| --- | --- | --- |
| `https://api.mtgstocks.com/news/feed` | HTTP 200; Atom XML; 43,661 bytes | Discovery works |
| Latest feed-discovered public article, news/25943 | HTTP 202; 2,455 bytes; CloudFront; `X-Amzn-Waf-Action: challenge` | Article acquisition blocked; stop |

The workflow is green because it successfully ran and recorded the negative
experiment. Its data verdict is explicitly `no-go`; workflow success does not
mean import success. There were exactly two source requests on the runner,
without retry. The probe has read-only repository permissions, no checkout,
model calls, secrets, schedule, repository writes or Pages deployment. Its push
trigger is restricted to its own workflow path and isolated pilot branch. The
probe workflow is not merged into production.

## Discovery and history: separate answers

The live feed held 15 total articles, of which five were Weekly Winners:

| Issue | Published date | Real link returned by feed |
| --- | --- | --- |
| 2026 - 46 | November 13, 2026 | [25943](https://www.mtgstocks.com/news/25943-weekly-winners-2026---46) |
| 2026 - 45 | November 6, 2026 | [25844](https://www.mtgstocks.com/news/25844-weekly-winners-2026---45) |
| 2026 - 44 | October 30, 2026 | [25745](https://www.mtgstocks.com/news/25745-weekly-winners-2026---44) |
| 2026 - 43 | October 23, 2026 | [25613](https://www.mtgstocks.com/news/25613-weekly-winners-2026---43) |
| 2026 - 42 | October 16, 2026 | [25514](https://www.mtgstocks.com/news/25514-weekly-winners-2026---42) |

Entries contain stable publisher IDs, published/updated timestamps, author,
article links and taxonomy. Both `content` and `summary` are teasers. Card tags
cover the whole article, so neither teasers nor tags establish section membership.
No ETag/Last-Modified was observed in the earlier direct feed inspection; do not
require conditional-request support. Some older entries have an updated time
earlier than publication; do not assume their ordering validates revisions.

**How far real links can be discovered:** this runner confirmed the current feed
window back to October 16, 2026. Prior reconnaissance found an indexed real link
to [Weekly Winners (51)](https://www.mtgstocks.com/news/56-weekly-winners-51),
described by the search index as approximately twelve years old. This supports
the series existing around 2014; it does not prove its earliest date or a complete,
automatically traversable archive. No guessed URLs or pagination sweep was used.

**Where the section is confirmed:** no article section was confirmed on this
runner. The earlier search reader exposed full Cheap Pickups sections in
[December 5, 2025's article](https://www.mtgstocks.com/news/20267-weekly-winners-2025---49)
and [March 6, 2026's article](https://www.mtgstocks.com/news/21752-weekly-winners-2026---10).
The old indexed article also mentions a differently worded cheap-pickup heading,
but that snippet does not establish equivalence to the modern section or parser
compatibility. The earliest consistent section and attainable historical depth
remain unknown. Prior cached/search-reader observations are not runner validation
and are not a proposed ingestion route.

## Source sample validation

**Accepted sample rows: none.** Latest-article retrieval failed before extraction.
The requested latest-plus-different-years semantic checks and focused parser
tests were therefore not pursued. There is no claim that older examples pass a
parser. A missing section, parser failure, blocked request or empty/challenge
response must remain a distinct unsuccessful result, never a complete empty issue.

Earlier readable examples show editorial pickup headings with prices and
movement labels, separate merchant offer prices and repeated purchase blocks.
Some entries have no individual rationale. These observations inform a future
parser but are not successful pilot rows. Do not fill the missing current sample
from feed tags or old cached data.

## Public reuse remains unresolved

The previously inspected [Terms of Use](https://www.mtgstocks.com/docs/terms-of-use)
limit access/use to personal, non-commercial purposes and prohibit unauthorized
reproduction/distribution. No public reuse permission was obtained, and a public
Atom feed is not by itself a license to republish its linked article content.
The WAF response is an observed access boundary, not a legal determination.

Before enablement, identify a supported permitted content route and clarify
publication of the compact card/date/price/movement facts with attribution. No
publisher contact was sent. Full article mirroring, copying editorial prose or
reproducing premium analysis is outside this proposal. This is a recorded reuse
uncertainty rather than a legal conclusion.

## Agreed next slice, only after a passing pilot

The owner narrowed v1 after the first recon. The following replaces earlier
suggestions for watchlists, dashboard panels, printing resolution and podcast
cross-links:

- One compact **Collection Pickups** tab, separate from **Podcast Picks**.
- Only Weekly Winners articles, and only their Cheap Pickups section.
- Card-level facts: card name, article date, quoted editorial price/currency,
  movement label when present, article URL and stable article/card identity.
- Preserve source spelling as evidence. Do not infer printings or finish, use
  merchant prices, invent a rationale, turn article prices into buy targets, or
  relabel entries as all-time lows. The inspected source caveat uses seven years
  for its record-low comparison.
- Keep appearances of the same card in different weeks. Deduplication is scoped
  to a source article, not to the entire collection history. IDs exclude price,
  movement and array order.
- Check daily. Prioritize the newest issue, and backfill at most one older real
  article per run. Do not manufacture an issue for every calendar week; discover
  actual links and record gaps/unknowns honestly. Article acquisition and history
  discovery must be proven before a recurring job is enabled.
- No watchlist, dashboard integration or podcast cross-links in v1.

## Minimal implementation fit, deferred

The existing podcast pipeline and `cards-to-watch.schema.json` require episode
and audio concepts. Articles should use a separate small contract and importer,
not fake episodes or a generalized source-schema migration.

```text
Atom discovery -> newest/pending Weekly Winners + bounded older-link discovery
  -> permitted public article content -> deterministic Cheap Pickups parser
  -> validated compact card-level records -> collection JSON projection
  -> static Collection Pickups tab
```

Proposed durable records are `data/collection-pickups/mtgstocks/<article-id>.json`,
with independent operational state in `state/collection-pickups.json` and a
generated `archive/collection-pickups.json`. Keep this projection separate from
podcast counts, episode health and audio/review controls. Existing atomic writes,
static styles and Pages packaging can be reused. A browser collection-load error
must not break podcast browsing. No backend, database or model calls are required.

Validate section boundaries and heading prices against source samples. Exclude
article-wide mentions, tags, charts, store offers and related article blocks.
Unknown movement stays absent. Stop on access refusal or unrecognized layout;
preserve previous good records, and do not silently replace them with an empty
list. Stage candidates before replacing validated durable output. Repeated
imports/rebuilds must preserve IDs and avoid duplicate rows or no-op deployments.

Any later production workflow must share the existing writer serialization,
preserve state across remote synchronization, publish directly through the Pages
mechanism, and leave podcast inference capacity independent. None is enabled by
this pilot.

## Completion and next action

The requested runner acquisition experiment is complete with a no-go. Do not
build the Collection Pickups tab or start backfill on the strength of the feed.
Reopen only with a supported permitted route or a material access change, then
test latest and a small different-year sample before making a go decision.

Production UI, schedules, podcast pipeline and published archive are unchanged.
Only pilot documentation/evidence is intended for master; no version bump or
Pages deployment is needed. R2 remains the active roadmap priority.
