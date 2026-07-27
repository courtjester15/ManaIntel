from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import PIPELINE_VERSION, SCHEMA_VERSION
from .models import PROCESSING_STATES, utc_now
from .utils import atomic_write_json, load_json


class JsonStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, Any]:
        return load_json(
            self.path,
            {
                "schema_version": SCHEMA_VERSION,
                "pipeline_version": PIPELINE_VERSION,
                "updated_at": None,
                "episodes": {},
            },
        )

    def get(self, guid: str) -> dict[str, Any] | None:
        return self._load()["episodes"].get(guid)

    def all(self) -> dict[str, dict[str, Any]]:
        return self._load()["episodes"]

    def transition(self, guid: str, status: str, **updates: Any) -> None:
        if status not in PROCESSING_STATES:
            raise ValueError(f"Unsupported processing state: {status}")
        state = self._load()
        timestamp = utc_now()
        record = state["episodes"].setdefault(guid, {"guid": guid, "history": []})
        if status == "downloading" and record.get("status") != "downloading":
            record["attempt_count"] = int(record.get("attempt_count", 0)) + 1
        record.update(updates)
        record["status"] = status
        record["updated_at"] = timestamp
        record.setdefault("history", []).append({"status": status, "timestamp": timestamp})
        state["updated_at"] = timestamp
        state["pipeline_version"] = PIPELINE_VERSION
        atomic_write_json(self.path, state)

    def discover(self, episode: Any) -> bool:
        if self.get(episode.guid):
            return False
        self.transition(
            episode.guid,
            "detected",
            title=episode.title,
            episode_number=episode.episode_number,
            published_at=episode.published_at,
            source_id=episode.source_id,
            source_name=episode.source_name,
            attempt_count=0,
            pick_count=0,
            error=None,
        )
        self.transition(episode.guid, "queued")
        return True
