# FFW — ManaIntel Proof of Concept

FFW automatically checks the MTG Fast Finance podcast, extracts Cards to Watch recommendations, and publishes them to a static archive.

FFW is the working implementation of **ManaIntel**, a deliberately small archive for MTG Fast Finance Cards to Watch recommendations. ManaIntel's goal is to show who recommended what, when, and why; it is not a price tracker, portfolio manager, automated financial analyst, or active multi-source platform effort.

The current implementation remains deliberately scoped to MTG Fast Finance and is composed of two decoupled parts:

1. A Python automation pipeline that turns podcast episodes into validated, versioned JSON and Markdown.
2. A static vanilla JavaScript archive that reads only the generated JSON.

Version 0.2 retains a fully runnable credential-free mock mode and adds live RSS, temporary audio preparation, swappable AI transcription/extraction, daily GitHub Actions processing, and GitHub Pages publication.

## Normal user workflow

Open <https://courtjester15.github.io/mtgff-cards-to-watch/>. Every day at 10:17 UTC, the archive processes the newest eligible untouched episode. A new release takes priority automatically; otherwise the workflow continues backward through historical episodes one per day. At 20:17 UTC, a separate bounded run retries at most one due transient failure without consuming the next day's fresh-backfill slot.

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
| `python -m ffw backfill --live --limit N` | Process the newest N eligible unprocessed live episodes. |
| `python -m ffw retry-failed --live --limit N` | Retry only the newest N failed live episodes. |
| `python -m ffw run --live --force-guid GUID` | Force one exact feed GUID regardless of feed position or terminal state. |
| `python -m ffw backfill` | Force-regenerate every synthetic fixture. |
| `python -m ffw process-latest` | Process only the newest eligible synthetic fixture. |
| `python -m ffw validate` | Validate identity, states, evidence, outputs, catalogs, and deterministic Markdown. |
| `python -m ffw render` | Re-render Markdown from JSON and rebuild `index.json` and `cards.json`. |
| `python -m ffw serve` | Serve the repository and local archive on port 8765. |

Live batch and failed-only runs require a positive limit no greater than 20. Limits count eligible selected episodes, not RSS entries inspected. `complete` and `needs_review` records are skipped before download or provider calls; failed records are selected only by `retry-failed` or an exact GUID override. Gemini transcription transiently retries the primary model once, then uses the configured same-key fallback before consuming an episode attempt. Automatic episode retries use a six-hour cooldown and stop after three total attempts. A no-op does not rewrite catalogs or state.

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

The official feed is `https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss`. The workflow is [`.github/workflows/ffw.yml`](.github/workflows/ffw.yml), supports `next`, `backfill`, `retry_failed`, and `deploy_only` manual modes, serializes writers, commits only `archive/` and `state/`, and deploys a clean Pages artifact. Audio, chunks, and full transcripts remain inside ignored/disposable `.ffw-work/` storage.

Required repository setup and recovery procedures are documented in [Production Runbook](docs/RUNBOOK.md).

## Current boundary and product direction

Implemented foundation:

- Package, CLI, state model, pipeline orchestration, rendering, catalogs, validation, tests, and local UI.
- Protocols for feed, downloader, audio, transcription, extraction, and state adapters.
- Idempotent terminal-state handling and auditable processing histories.
- Versioned JSON Schema and pipeline metadata.
- Opt-in live RSS, guarded audio download, `ffmpeg` preparation, Gemini/OpenAI transcription and extraction adapters, and a scheduled GitHub Actions/Pages workflow.

Still intentionally outside the product:

- Additional sources, generic source-item records, cross-source search, notifications, databases, price tracking, analytics, and ManaSpec integration.

ManaIntel is entering maintenance mode after one bounded final functional pass of approximately five hours. That pass is limited to durable review overrides, in-page timestamp playback, clearer status/failure presentation, a copyable exact-episode retry path, and a deployment-level no-op guard. Multi-source normalization and expansion are deferred indefinitely. Afterward, portfolio attention moves to ManaSpec adoption and GalleyFlow; ManaIntel reopens only for production-breaking defects or very small maintenance fixes.

See [ManaIntel Vision](docs/VISION.md), [Product Spec](docs/PRODUCT_SPEC.md), [Architecture](docs/ARCHITECTURE.md), [Data Model](docs/DATA_MODEL.md), [Roadmap](docs/ROADMAP.md), [Decisions](docs/DECISIONS.md), and [Production Runbook](docs/RUNBOOK.md).
