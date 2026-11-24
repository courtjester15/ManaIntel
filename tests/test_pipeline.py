from __future__ import annotations

import json
import unittest

from ffw.config import Settings
from ffw.pipeline import Pipeline
from ffw.rendering import render_episode_markdown
from ffw.utils import load_json, stable_pick_id
from ffw.validation import validate_archive
from tests.workspace import workspace_temp


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        root = workspace_temp(self)
        self.settings = Settings(
            root=root,
            archive_dir=root / "archive",
            state_file=root / "state/episodes.json",
            work_dir=root / ".ffw-work",
        )

    def test_mock_pipeline_builds_required_fixture_mix(self) -> None:
        results = Pipeline.mock(self.settings).run()
        self.assertEqual(5, len(results))
        self.assertEqual(["complete", "failed", "needs_review", "complete", "complete"], [item.status for item in results])
        index = load_json(self.settings.archive_dir / "index.json")
        self.assertEqual(5, index["counts"]["episodes"])
        self.assertEqual(15, index["counts"]["picks"])
        self.assertEqual(3, index["counts"]["completed"])
        self.assertEqual(1, index["counts"]["needs_review"])
        self.assertEqual(1, index["counts"]["failed"])

    def test_second_run_is_idempotent(self) -> None:
        pipeline = Pipeline.mock(self.settings)
        pipeline.run()
        before = self.settings.state_file.read_text(encoding="utf-8")
        before_index = (self.settings.archive_dir / "index.json").read_text(encoding="utf-8")
        results = pipeline.run()
        after = self.settings.state_file.read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual(before_index, (self.settings.archive_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([], results)
        self.assertEqual(4, pipeline.last_selection.completed_skipped)
        self.assertEqual(1, pipeline.last_selection.failed_skipped)

    def test_generated_archive_validates(self) -> None:
        Pipeline.mock(self.settings).run()
        self.assertEqual([], validate_archive(self.settings.archive_dir, self.settings.state_file))

    def test_unexplained_empty_live_extraction_records_review_reason_everywhere(self) -> None:
        from ffw.models import EpisodeCandidate
        from unittest.mock import Mock
        pipeline = Pipeline.mock(self.settings)
        pipeline.transcriber.transcribe = Mock(return_value={"segments": [
            {"start": 0, "end": 200, "text": "An episode discussion.", "speaker": None},
        ], "chunk_count": 1})
        pipeline.extractor.extract = Mock(return_value={
            "section": {"located": True, "start_seconds": 100, "end_seconds": 200,
                        "label": "Cards to Watch", "confidence": "high", "review_reason": None},
            "recommendations": [], "review_reason": None,
        })
        candidate = EpisodeCandidate("empty-live", 539, "Empty extraction", "2026-11-11T00:00:00Z",
                                     "https://example.test/audio.mp3", "https://example.test/episode", [])
        result = pipeline.process_episode(candidate)
        self.assertEqual(("needs_review", 0), (result.status, result.pick_count), result.message)
        summary = load_json(self.settings.archive_dir / result.output_directory / "summary.json")
        state = pipeline.state.get(candidate.guid)
        attempt = load_json(next((self.settings.state_file.parent / "attempts").glob("*.json")))
        for record in (summary["processing"], state, attempt):
            self.assertIn("zero picks", record["review_reason"])
            self.assertIn("not a confirmed no-recommendations", record["review_reason"])
        self.assertEqual({"coverage", "intent"}, {i["code"] for i in state["review_issues"]})
        self.assertEqual(1, pipeline.extractor.extract.call_count)

    def test_markdown_is_derived_from_json(self) -> None:
        Pipeline.mock(self.settings).run()
        summary_path = next((self.settings.archive_dir / "episodes").glob("*/summary.json"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        markdown = summary_path.with_suffix(".md").read_text(encoding="utf-8")
        self.assertEqual(render_episode_markdown(summary), markdown)

    def test_pick_id_is_stable_and_input_sensitive(self) -> None:
        first = stable_pick_id("guid", "Bloodstained Mire", 100, "Regular")
        repeat = stable_pick_id("guid", "Bloodstained Mire", 100, "Regular")
        changed = stable_pick_id("guid", "Bloodstained Mire", 101, "Regular")
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, changed)

    def test_duplicate_candidate_is_retained_and_cannot_publish_or_erase_baseline(self):
        from copy import deepcopy
        from unittest.mock import patch
        for forced in (False, True):
            with self.subTest(forced=forced):
                pipeline = Pipeline.mock(self.settings)
                candidate = pipeline.feed.episodes()[0]
                if forced:
                    pipeline.process_episode(candidate, force=True)
                directory = self.settings.archive_dir / (pipeline.state.get(candidate.guid) or {}).get("output_directory", "absent")
                before = (directory / "summary.json").read_bytes() if forced else None
                original = pipeline.extractor.extract
                def duplicate(item, transcript):
                    result = deepcopy(original(item, transcript))
                    result["recommendations"].append(deepcopy(result["recommendations"][0]))
                    return result
                with patch.object(pipeline.extractor, "extract", side_effect=duplicate):
                    result = pipeline.process_episode(candidate, force=True)
                self.assertEqual("failed", result.status)
                self.assertIn("Duplicate recommendation identity", result.message)
                rejected = list((self.settings.work_dir / "reprocess-reports").glob("*.rejected.json"))
                self.assertTrue(rejected)
                payload = load_json(rejected[0])
                self.assertGreater(len(payload["recommendations"]), len({p["id"] for p in payload["recommendations"]}))
                if forced:
                    self.assertEqual(before, (directory / "summary.json").read_bytes())
                from ffw.archive import rebuild_catalog
                rebuild_catalog(self.settings.archive_dir)
                self.assertEqual([], validate_archive(self.settings.archive_dir, self.settings.state_file))


if __name__ == "__main__":
    unittest.main()
