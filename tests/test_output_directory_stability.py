from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ffw.config import Settings
from ffw.models import EpisodeCandidate
from ffw.pipeline import Pipeline
from ffw.state import JsonStateStore
from ffw.utils import atomic_write_json, load_json


class OutputDirectoryStabilityTests(unittest.TestCase):
    def test_forced_rerun_keeps_existing_directory_after_episode_number_repair(self) -> None:
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        settings = Settings(
            root,
            root / "archive",
            root / "state/episodes.json",
            root / ".ffw-work",
            mode="live",
        )
        guid = "brainstorm-brewery:https://example.test/?p=702"
        legacy_output = "episodes/0000-promo-pickle-deadbeef"
        candidate = EpisodeCandidate(
            guid,
            702,
            "Promo Pickle | Brainstorm Brewery #702 | Magic Finance",
            "2026-05-29T06:00:00Z",
            "https://cdn.example.test/702.mp3",
            "https://example.test/702",
            [],
            source_id="brainstorm-brewery",
            source_name="Brainstorm Brewery",
            extraction_profile="brainstorm_brewery",
        )
        state = JsonStateStore(settings.state_file)
        state.discover(candidate)
        state.transition(
            guid,
            "failed",
            output_directory=legacy_output,
            pick_count=0,
            error={"stage": "extracting", "message": "transient"},
        )
        atomic_write_json(settings.archive_dir / legacy_output / "metadata.json", {
            "episode": {"guid": guid, "episode_number": 702},
            "processing": {"status": "failed"},
        })

        class Downloader:
            def download(self, episode, destination):
                path = destination.with_suffix(".mp3")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"audio")
                return path

        class Audio:
            def prepare(self, source, destination):
                return [source]

        class Transcriber:
            model_name = "test-transcriber"

            def transcribe(self, episode, files):
                return {"provider": "test", "segments": [], "chunk_count": 1}

        class Extractor:
            model_name = "test-extractor"

            def extract(self, episode, transcript):
                return {
                    "section": {
                        "located": True,
                        "start_seconds": 10,
                        "end_seconds": 20,
                        "label": "Pick of the Week",
                        "confidence": "high",
                        "review_reason": None,
                    },
                    "recommendations": [{
                        "card": "Recovered Card",
                        "printing": None,
                        "printing_certainty": None,
                        "foil": None,
                        "hosts": [],
                        "recommendation": "Watch for an entry.",
                        "mentioned_price": None,
                        "entry_target": None,
                        "hold": None,
                        "exit_target": None,
                        "reasoning": ["Supply was discussed."],
                        "caveats": [],
                        "confidence": None,
                        "start_seconds": 10,
                        "end_seconds": 20,
                        "evidence_excerpt": "Short evidence.",
                        "review_status": "approved",
                        "review_reason": None,
                    }],
                    "review_reason": None,
                }

        pipeline = Pipeline(
            settings,
            object(),
            Downloader(),
            Audio(),
            Transcriber(),
            Extractor(),
            state,
        )

        result = pipeline.process_episode(candidate, force=True)

        self.assertEqual("complete", result.status, result.message)
        self.assertEqual(legacy_output, result.output_directory)
        self.assertTrue((settings.archive_dir / legacy_output / "summary.json").exists())
        self.assertFalse(any(
            path.name.startswith("0702-")
            for path in (settings.archive_dir / "episodes").iterdir()
        ))
        self.assertEqual(legacy_output, load_json(settings.state_file)["episodes"][guid]["output_directory"])


if __name__ == "__main__":
    unittest.main()
