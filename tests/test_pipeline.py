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


if __name__ == "__main__":
    unittest.main()
