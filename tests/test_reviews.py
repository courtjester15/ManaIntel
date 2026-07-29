from __future__ import annotations

import unittest
import uuid
from copy import deepcopy
from pathlib import Path

from ffw.archive import rebuild_catalog
from ffw.rendering import render_episode_markdown
from ffw.reviews import (
    REVIEW_SCHEMA_VERSION,
    apply_review,
    normalize_review,
    persist_review,
    review_expectation,
    review_file_path,
)
from ffw.utils import atomic_write_json, atomic_write_text, load_json, stable_pick_id
from ffw.validation import validate_archive


def pick(guid: str, card: str, start: int, printing: str | None = None) -> dict:
    return {
        "id": stable_pick_id(guid, card, start, printing),
        "card": card,
        "printing": printing,
        "printing_certainty": "confirmed" if printing else None,
        "foil": None,
        "hosts": ["Host One"],
        "recommendation": "buy",
        "mentioned_price": None,
        "entry_target": None,
        "hold": None,
        "exit_target": None,
        "reasoning": ["Supply is low."],
        "caveats": [],
        "confidence": "high",
        "start_seconds": start,
        "end_seconds": start + 30,
        "timestamp": f"00:{start // 60:02d}:{start % 60:02d}",
        "evidence_excerpt": f"{card} is the pick.",
        "review_status": "approved",
        "review_reason": None,
        "listen_url": f"https://audio.example/episode.mp3#t={start}",
    }


def summary() -> dict:
    guid = "source:episode-42"
    return {
        "schema_version": "1.1.0",
        "synthetic": False,
        "notice": "Automated extraction.",
        "episode": {
            "guid": guid,
            "episode_number": 42,
            "title": "Review fixture",
            "published_at": "2026-01-01T00:00:00Z",
            "audio_url": "https://audio.example/episode.mp3",
            "episode_url": "https://example.test/42",
            "duration_seconds": 3600,
            "hosts": ["Host One"],
            "description": "Fixture",
            "source_id": "mtg-fast-finance",
            "source_name": "MTG Fast Finance",
            "source_url": "https://example.test",
            "extraction_profile": "cards_to_watch",
        },
        "processing": {
            "status": "needs_review",
            "review_state": "needs_review",
            "review_reason": "Section ending was ambiguous.",
            "pipeline_version": "test",
            "schema_version": "1.1.0",
            "transcription_model": "test",
            "extraction_model": "test",
            "prompt_version": "test",
            "processed_at": "2026-01-02T00:00:00Z",
            "history": [],
            "error": None,
        },
        "section": {
            "located": True,
            "start_seconds": 600,
            "end_seconds": 900,
            "label": "Cards to Watch",
            "confidence": "medium",
            "review_reason": "Section ending was ambiguous.",
        },
        "recommendations": [
            pick(guid, "Wrong Card", 620),
            pick(guid, "Keep Card", 700, "Regular"),
        ],
    }


def payload(source: dict) -> dict:
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "source_id": "mtg-fast-finance",
        "episode_guid": source["episode"]["guid"],
        "expected": review_expectation(source),
        "decision": "approve",
        "note": "Verified against audio.",
        "operations": [
            {"action": "exclude", "pick_id": source["recommendations"][0]["id"]},
            {
                "action": "update",
                "pick_id": source["recommendations"][1]["id"],
                "changes": {
                    "card": "Corrected Card",
                    "printing": "Showcase",
                    "hosts": ["Host One", "Host Two"],
                    "recommendation": "buy under $5",
                    "start_seconds": 705,
                    "end_seconds": 735,
                    "evidence_excerpt": "Corrected Card is a buy under five dollars.",
                },
            },
            {
                "action": "add",
                "pick": {
                    "card": "Missing Card",
                    "printing": "",
                    "hosts": ["Host Two"],
                    "recommendation": "watch",
                    "start_seconds": 800,
                    "end_seconds": 830,
                    "evidence_excerpt": "Missing Card is worth watching.",
                },
            },
        ],
    }


class ReviewOverrideTests(unittest.TestCase):
    def test_review_applies_exclude_update_add_without_mutating_original(self) -> None:
        original = summary()
        untouched = deepcopy(original)
        review = normalize_review(
            original,
            payload(original),
            actor="reviewer",
            reviewed_at="2026-01-03T00:00:00Z",
        )
        effective = apply_review(original, review)

        self.assertEqual(untouched, original)
        self.assertEqual(["Corrected Card", "Missing Card"], [item["card"] for item in effective["recommendations"]])
        self.assertTrue(all(item["review_status"] == "approved" for item in effective["recommendations"]))
        self.assertEqual("complete", effective["processing"]["status"])
        self.assertEqual("approved", effective["processing"]["review_state"])
        self.assertIsNone(effective["processing"]["review_reason"])
        self.assertEqual("reviewer", effective["processing"]["human_review"]["reviewed_by"])
        corrected = effective["recommendations"][0]
        self.assertEqual(
            stable_pick_id(original["episode"]["guid"], "Corrected Card", 705, "Showcase"),
            corrected["id"],
        )
        self.assertEqual("00:11:45", corrected["timestamp"])

    def test_stale_review_is_rejected(self) -> None:
        original = summary()
        request = payload(original)
        original["processing"]["processed_at"] = "2026-01-04T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "stale"):
            normalize_review(original, request, actor="reviewer")

    def test_persisted_review_builds_effective_catalog_and_validates(self) -> None:
        root = Path.cwd() / ".test-work" / str(uuid.uuid4())
        root.mkdir(parents=True, exist_ok=True)
        archive = root / "archive"
        episode_dir = archive / "episodes" / "0042-review-fixture"
        reviews = root / "data" / "reviews"
        source = summary()
        metadata = {
                "schema_version": "1.1.0",
                "synthetic": False,
                "episode": source["episode"],
                "processing": source["processing"],
                "outputs": {
                    "summary_json": "episodes/0042-review-fixture/summary.json",
                    "summary_markdown": "episodes/0042-review-fixture/summary.md",
                },
        }
        atomic_write_json(episode_dir / "metadata.json", metadata)
        atomic_write_json(episode_dir / "summary.json", source)
        atomic_write_text(episode_dir / "summary.md", render_episode_markdown(source))
        atomic_write_json(root / "state" / "episodes.json", {
            "schema_version": "1.1.0",
            "pipeline_version": "test",
            "updated_at": "2026-01-02T00:00:00Z",
            "episodes": {source["episode"]["guid"]: {"status": "needs_review"}},
        })
        rebuild_catalog(archive, production=True, reviews_dir=reviews)

        path = persist_review(
            archive,
            reviews,
            payload(source),
            actor="github-user",
            reviewed_at="2026-01-03T00:00:00Z",
        )
        rebuild_catalog(archive, production=True, reviews_dir=reviews)

        self.assertEqual(
            review_file_path(reviews, "mtg-fast-finance", source["episode"]["guid"]),
            path,
        )
        self.assertTrue((episode_dir / "effective.json").exists())
        self.assertTrue((episode_dir / "effective.md").exists())
        index = load_json(archive / "index.json")
        self.assertEqual("complete", index["episodes"][0]["processing_status"])
        self.assertTrue(index["episodes"][0]["human_reviewed"])
        self.assertEqual(2, index["counts"]["picks"])
        cards = load_json(archive / "cards.json")["cards"]
        self.assertEqual(["Missing Card", "Corrected Card"], [item["card"] for item in cards])
        issues = validate_archive(
            archive,
            root / "state" / "episodes.json",
            Path(__file__).parents[1] / "schemas" / "cards-to-watch.schema.json",
            expected_production=True,
            reviews_dir=reviews,
        )
        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
