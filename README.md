# FFW — ManaIntel Proof of Concept

FFW automatically checks MTG Fast Finance and Brainstorm Brewery, extracts their explicit recommendation segments, and publishes them to a static archive.

FFW is the working implementation of **ManaIntel**, a deliberately small podcast recommendation archive. ManaIntel's goal is to show who recommended what, when, and why; it is not a price tracker, portfolio manager, or automated financial analyst.

The implementation supports two podcast adapters and is composed of two decoupled parts:

1. A Python automation pipeline that turns podcast episodes into validated, versioned JSON and Markdown.
2. A static vanilla JavaScript archive that reads only the generated JSON.

Version 0.2 retains a fully runnable credential-free mock mode and adds live RSS, temporary audio preparation, swappable AI transcription/extraction, daily GitHub Actions processing, and GitHub Pages publication.

## Normal user workflow

Open <https://courtjester15.github.io/mtgff-cards-to-watch/>. Every day at 10:17 UTC, the archive processes the newest eligible untouched episode across both podcasts. A new release takes priority automatically; otherwise the workflow continues backward through combined history. At 20:17 UTC, a separate bounded run retries at most one due transient failure; when no retry is due, it advances the same newest-to-oldest untouched cursor. Automatic selection ignores episodes older than `FFW_AUTOMATIC_MAX_EPISODE_AGE_DAYS` (365 by default); an explicit GUID can override the age limit.

For an episode marked **needs review**, open its details and choose **Review episode**. Keep, exclude, or correct extracted picks, add any missing picks, then prepare and copy the review payload. Paste that payload into **Actions -> Review one episode -> Run workflow**. The authenticated workflow validates and stores the review, rebuilds the effective archive, commits it, and deploys Pages while retaining the original AI extraction unchanged.

The repository starts with synthetic fixtures. The deployed production catalog excludes those fixtures and shows only live records after the first successful backfill.

> All recommendations, quotations, prices, episode numbers, people, and processing outcomes currently in `archive/` are synthetic fixtures. They are not real podcast commentary or financial advice.

## Developer quick start

Python 3.11 or newer is required. Mock processing needs no credentials or external media tools. Live processing additionally requires `ffmpeg`, network access, and either `GEMINI_API_KEY` or `OPENAI_API_KEY` depending on `FFW_AI_PROVIDER`.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m ffw run
python -m ffw validate
python -m ffw serve
```

Open <http://127.0.0.1:8765/web/>. Stop the server with `Ctrl+C`.

On macOS or Linux, activate with `source .venv/bin/activate`; the remaining commands are identical.

For development without installing the package, set `PYTHONPATH=src` before invoking `python -m ffw`.

## Commands

| Command | Purpose |
|---|---|
| `python -m ffw run` | Process unprocessed mock episodes and skip terminal records idempotently. |
| `python -m ffw process-next --live` | Process the newest eligible live episode, at most one. |
| `python -m ffw process-next --live --source brainstorm-brewery` | Process only the newest eligible Brainstorm Brewery episode. |
| `python -m ffw backfill --live --limit N` | Process the newest N eligible unprocessed live episodes. |
| `python -m ffw retry-failed --live --limit N` | Retry only the newest N failed live episodes. |
| `python -m ffw run --live --force-guid GUID` | Force one exact feed GUID regardless of feed position or terminal state. |
| `python -m ffw resolve-cards --limit N` | Verify up to N uncached extracted card names against Scryfall and rebuild canonical display projections. |
| `python -m ffw backfill` | Force-regenerate every synthetic fixture. |
| `python -m ffw process-latest` | Process only the newest eligible synthetic fixture. |
| `python -m ffw validate` | Validate identity, states, evidence, outputs, catalogs, and deterministic Markdown. |
| `python -m ffw render` | Re-render Markdown from JSON and rebuild `index.json` and `cards.json`. |
| `python -m ffw serve` | Serve the repository and local archive on port 8765. |

Live batch and failed-only runs require a positive limit no greater than 20. Limits count eligible selected episodes, not RSS entries inspected. `complete` and `needs_review` records are skipped before download or provider calls; failed records are selected only by `retry-failed` or an exact GUID override. Gemini transcription uses exponential in-run backoff, its configured same-key fallback, and then an optional OpenAI provider fallback before consuming an episode attempt. Automatic episode retries use a six-hour cooldown and stop after three total attempts. A no-op does not rewrite catalogs, state, or Pages; a changed validated failure record is published so operational status stays current.

Targeted verification is bounded and cost-conscious. For at most `FFW_TARGETED_VERIFICATION_MAX_PICKS` transcription-level card-name ambiguities per episode, ManaIntel cuts a short audio excerpt, performs a focused second listen, and accepts a correction only when the returned name independently resolves as an exact Scryfall card. Printing and foil uncertainty remains reviewable.

Card-name resolution is additive and auditable. Original extracted names and stable pick IDs remain unchanged in episode summaries. Exact or punctuation-normalized Scryfall matches receive a canonical display name and Oracle ID in `state/card-resolutions.json`; fuzzy matches are published only as review suggestions. Successful live runs resolve a bounded batch of historical names automatically, and `resolve-cards` can run an explicit backfill. `archive/resolutions.json`, `archive/cards.json`, and the web UI are rebuildable projections of that state.

For local networks that inspect HTTPS, set `FFW_CA_BUNDLE` to the trusted PEM/CRT file. ManaIntel also honors an existing `NODE_EXTRA_CA_CERTS` value for the Scryfall resolver, so a shared local Node/browser development certificate does not need to be configured twice. This only adds the specified CA to normal TLS verification; certificate checks remain enabled, and deployed environments without either variable retain the default trust behavior.

Run the tests with:

```powershell
python -m unittest discover -s tests -v
```

## Generated archive

```text
archive/
├── index.json                 # frontend master catalog
├── cards.json                 # flattened searchable recommendations
└── episodes/
    └── 0901-fetchland-signals/
        ├── metadata.json      # identity, audit metadata, state history
        ├── summary.json       # canonical Cards to Watch data
        └── summary.md         # deterministic rendering of summary.json
```

A deliberately failed fixture receives `metadata.json` but no summary files. Successful and needs-review episodes always receive all three outputs.

## Trust rules

- Unknown means `null`; it is never silently inferred.
- An entry or exit target must preserve the source wording in `raw`.
- Every pick requires a timestamp and evidence excerpt.
- Ambiguity is surfaced through certainty and review state.
- Markdown is generated from JSON, never independently.
- Pick identifiers are deterministic and insensitive to list ordering.
- Raw audio is temporary and is never part of the archive contract.

Structural validation can prove that evidence exists; it cannot prove that an AI interpreted speech faithfully. Production readiness therefore requires representative extraction evaluations and explicit review thresholds.

## Production operation

The feeds are MTG Fast Finance's SoundCloud RSS and Brainstorm Brewery's public FeedBurner RSS. The processing workflow is [`.github/workflows/ffw.yml`](.github/workflows/ffw.yml), supports `next`, `backfill`, `retry_failed`, and `deploy_only` manual modes plus an optional source selector, serializes writers, commits only `archive/` and `state/`, and deploys a clean Pages artifact. [`.github/workflows/review.yml`](.github/workflows/review.yml) applies authenticated human-review payloads under `data/reviews/`, rebuilds effective projections, and deploys them through the same writer concurrency group. Audio and chunks remain inside ignored/disposable `.ffw-work/` storage. Production runs retain full timestamped transcripts only as private GitHub Actions artifacts for 14 days; they are never committed or published to Pages.

Required repository setup and recovery procedures are documented in [Production Runbook](docs/RUNBOOK.md).

## Current boundary and product direction

Implemented foundation:

- Package, CLI, state model, pipeline orchestration, rendering, catalogs, validation, tests, and local UI.
- Protocols for feed, downloader, audio, transcription, extraction, and state adapters.
- Idempotent terminal-state handling and auditable processing histories.
- Versioned JSON Schema and pipeline metadata.
- Opt-in live RSS, guarded audio download, `ffmpeg` preparation, Gemini/OpenAI transcription and extraction adapters, and a scheduled GitHub Actions/Pages workflow.

Still intentionally outside the product:

- Additional source types beyond the two podcast adapters, generic source-item records, notifications, databases, price tracking, analytics, and ManaSpec integration.

ManaIntel is entering maintenance mode after one bounded final functional pass of approximately five hours. That pass is limited to durable review overrides, in-page timestamp playback, clearer status/failure presentation, a copyable exact-episode retry path, and a deployment-level no-op guard. Multi-source normalization and expansion are deferred indefinitely. Afterward, portfolio attention moves to ManaSpec adoption and GalleyFlow; ManaIntel reopens only for production-breaking defects or very small maintenance fixes.

See [ManaIntel Vision](docs/VISION.md), [Product Spec](docs/PRODUCT_SPEC.md), [Architecture](docs/ARCHITECTURE.md), [Data Model](docs/DATA_MODEL.md), [Roadmap](docs/ROADMAP.md), [Decisions](docs/DECISIONS.md), and [Production Runbook](docs/RUNBOOK.md).
