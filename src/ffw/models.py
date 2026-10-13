from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


TERMINAL_STATES = {"complete", "needs_review"}
PROCESSING_STATES = {
    "detected",
    "queued",
    "downloading",
    "downloaded",
    "preparing",
    "transcribing",
    "transcribed",
    "extracting",
    "extracted",
    "validating",
    "publishing",
    "needs_review",
    "complete",
    "failed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EpisodeCandidate:
    guid: str
    episode_number: int
    title: str
    published_at: str
    audio_url: str
    episode_url: str
    hosts: list[str]
    description: str | None = None
    duration_seconds: int | None = None
    feed_metadata: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    fixture: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    source_id: str = "mtg-fast-finance"
    source_name: str = "MTG Fast Finance"
    source_url: str = "https://www.mtgfastfinance.com/"
    extraction_profile: str = "cards_to_watch"

    @property
    def synthetic(self) -> bool:
        return bool(self.fixture)


@dataclass
class PipelineResult:
    guid: str
    status: str
    output_directory: str | None = None
    pick_count: int = 0
    message: str = ""


@dataclass
class SelectionReport:
    policy: str
    selected_mode: str | None = None
    feed_entries_scanned: int = 0
    completed_skipped: int = 0
    failed_skipped: int = 0
    retry_deferred: int = 0
    retry_exhausted: int = 0
    eligible_found: int = 0
    selected: list[EpisodeCandidate] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        selected = [
            {
                "guid": episode.guid,
                "episode_number": episode.episode_number,
                "title": episode.title,
                "published_at": episode.published_at,
                "source_id": episode.source_id,
                "source_name": episode.source_name,
            }
            for episode in self.selected
        ]
        return {
            "policy": self.policy,
            "selected_mode": self.selected_mode,
            "feed_entries_scanned": self.feed_entries_scanned,
            "completed_skipped": self.completed_skipped,
            "failed_skipped": self.failed_skipped,
            "retry_deferred": self.retry_deferred,
            "retry_exhausted": self.retry_exhausted,
            "eligible_found": self.eligible_found,
            "selected_count": len(selected),
            "selected": selected,
            "newest_selected": selected[0] if selected else None,
            "oldest_selected": selected[-1] if selected else None,
        }
