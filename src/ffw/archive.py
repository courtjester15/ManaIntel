from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import PIPELINE_VERSION, SCHEMA_VERSION
from .card_resolution import apply_card_resolution, load_resolution_store
from .rendering import render_episode_markdown
from .reviews import apply_review, load_episode_review
from .utils import atomic_write_json, atomic_write_text, load_json
from .models import utc_now


SYNTHETIC_NOTICE = (
    "All archive content in this fixture build is synthetic test data. "
    "It is not real podcast commentary or financial advice."
)


def rebuild_catalog(
    archive_dir: Path, *, production: bool = False, feed_name: str = "MTG Fast Finance",
    repository_url: str = "https://github.com/courtjester15/mtgff-cards-to-watch",
    reviews_dir: Path | None = None,
    resolutions_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    episode_records: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    resolution_store = load_resolution_store(resolutions_path)
    resolutions = resolution_store["resolutions"]
    for metadata_path in sorted((archive_dir / "episodes").glob("*/metadata.json")):
        metadata = load_json(metadata_path)
        if not metadata:
            continue
        if production and metadata.get("synthetic", False):
            continue
        summary_path = metadata_path.parent / "summary.json"
        summary = load_json(summary_path)
        review = load_episode_review(reviews_dir, summary) if summary else None
        effective_summary = apply_review(summary, review) if summary else None
        effective_path = metadata_path.parent / "effective.json"
        effective_markdown_path = metadata_path.parent / "effective.md"
        if review and effective_summary:
            atomic_write_json(effective_path, effective_summary)
            atomic_write_text(effective_markdown_path, render_episode_markdown(effective_summary))
        else:
            effective_path.unlink(missing_ok=True)
            effective_markdown_path.unlink(missing_ok=True)
        processing = (
            effective_summary.get("processing", metadata["processing"])
            if effective_summary else metadata["processing"]
        )
        human_review = processing.get("human_review")
        outputs = {
            **metadata.get("outputs", {}),
            "effective_summary_json": (
                effective_path.relative_to(archive_dir).as_posix() if review else None
            ),
            "effective_summary_markdown": (
                effective_markdown_path.relative_to(archive_dir).as_posix() if review else None
            ),
        }
        episode_item = {
            **metadata["episode"],
            "processing_status": processing["status"],
            "review_state": processing.get("review_state"),
            "review_reason": processing.get("review_reason"),
            "pick_count": len(effective_summary["recommendations"]) if effective_summary else 0,
            "directory": metadata_path.parent.relative_to(archive_dir).as_posix(),
            "outputs": outputs,
            "processed_at": processing.get("processed_at"),
            "error": processing.get("error"),
            "human_reviewed": bool(human_review),
            "reviewed_at": human_review.get("reviewed_at") if human_review else None,
            "reviewed_by": human_review.get("reviewed_by") if human_review else None,
            "review_note": human_review.get("note") if human_review else None,
            "synthetic": metadata.get("synthetic", False),
        }
        episode_records.append(episode_item)
        if effective_summary:
            for pick in effective_summary["recommendations"]:
                projected_pick = apply_card_resolution(pick, resolutions)
                cards.append(
                    {
                        **projected_pick,
                        "episode": {
                            "guid": metadata["episode"]["guid"],
                            "episode_number": metadata["episode"]["episode_number"],
                            "title": metadata["episode"]["title"],
                            "published_at": metadata["episode"]["published_at"],
                            "episode_url": metadata["episode"]["episode_url"],
                            "audio_url": metadata["episode"]["audio_url"],
                            "source_id": metadata["episode"].get("source_id", "mtg-fast-finance"),
                            "source_name": metadata["episode"].get("source_name", feed_name),
                        },
                        "processing_status": processing["status"],
                        "human_reviewed": bool(human_review),
                    }
                )
    episode_records.sort(key=lambda item: item["published_at"], reverse=True)
    cards.sort(key=lambda item: (item["episode"]["published_at"], item["start_seconds"] or 0), reverse=True)
    status_counts: dict[str, int] = {}
    for episode in episode_records:
        status = episode["processing_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    counts = {
        "episodes": len(episode_records),
        "picks": len(cards),
        "needs_review": status_counts.get("needs_review", 0),
        "failed": status_counts.get("failed", 0),
        "completed": status_counts.get("complete", 0),
    }
    generated_at = utc_now()
    is_synthetic = not production
    successful = [episode for episode in episode_records if episode["processing_status"] in {"complete", "needs_review"}]
    sources = sorted({
        (episode.get("source_id", "mtg-fast-finance"), episode.get("source_name", feed_name), episode.get("source_url"))
        for episode in episode_records
    })
    index = {
        "schema_version": SCHEMA_VERSION,
        "synthetic": is_synthetic,
        "notice": SYNTHETIC_NOTICE if is_synthetic else "Automated transcription and extraction may contain errors. Verify against source audio.",
        "metadata": {
            "project": "FFW",
            "pipeline_version": PIPELINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "latest_successful_run_at": max((item.get("processed_at") or "" for item in successful), default=None),
            "generated_from": "synthetic-fixtures" if is_synthetic else "live-feed",
            "production_mode": production,
            "source": {"name": feed_name if len(sources) < 2 else "MTG Fast Finance + Brainstorm Brewery"},
            "sources": [{"id": item[0], "name": item[1], "url": item[2]} for item in sources],
            "real_episode_count": 0 if is_synthetic else len(episode_records),
            "real_pick_count": 0 if is_synthetic else len(cards),
            "last_discovered_episode_date": episode_records[0]["published_at"] if episode_records else None,
            "repository_url": repository_url,
            "workflow_url": f"{repository_url}/actions/workflows/ffw.yml",
            "review_workflow_url": f"{repository_url}/actions/workflows/review.yml",
        },
        "counts": counts,
        "status_counts": status_counts,
        "latest_episode": episode_records[0] if episode_records else None,
        "recent_picks": cards[:6],
        "episodes": episode_records,
    }
    atomic_write_json(archive_dir / "index.json", index)
    atomic_write_json(
        archive_dir / "cards.json",
        {
            "schema_version": SCHEMA_VERSION,
            "synthetic": is_synthetic,
            "notice": SYNTHETIC_NOTICE if is_synthetic else "Automated extraction; verify against source audio.",
            "count": len(cards),
            "cards": cards,
        },
    )
    published_ids = {pick.get("id") for pick in cards}
    atomic_write_json(
        archive_dir / "resolutions.json",
        {
            "schema_version": resolution_store["schema_version"],
            "resolver_updated_at": resolution_store.get("updated_at"),
            "resolutions": {
                pick_id: record
                for pick_id, record in resolutions.items()
                if pick_id in published_ids
            },
        },
    )
    return index, cards


def rerender_archive(
    archive_dir: Path, *, production: bool = False, reviews_dir: Path | None = None,
    repository_url: str = "https://github.com/courtjester15/mtgff-cards-to-watch",
    resolutions_path: Path | None = None,
) -> int:
    rendered = 0
    for summary_path in (archive_dir / "episodes").glob("*/summary.json"):
        summary = load_json(summary_path)
        atomic_write_text(summary_path.with_suffix(".md"), render_episode_markdown(summary))
        rendered += 1
    rebuild_catalog(
        archive_dir,
        production=production,
        reviews_dir=reviews_dir,
        repository_url=repository_url,
        resolutions_path=resolutions_path,
    )
    return rendered
