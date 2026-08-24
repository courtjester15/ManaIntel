from __future__ import annotations

import unittest

from ffw.config import Settings
from ffw.pipeline import Pipeline
from ffw.utils import atomic_write_json, load_json
from ffw.validation import validate_archive
from tests.workspace import workspace_temp


class ValidationTests(unittest.TestCase):
    def test_detects_cards_catalog_drift(self) -> None:
        root = workspace_temp(self)
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work")
        Pipeline.mock(settings).run()
        cards_path = settings.archive_dir / "cards.json"
        cards = load_json(cards_path)
        cards["cards"].pop()
        atomic_write_json(cards_path, cards)
        codes = {issue.code for issue in validate_archive(settings.archive_dir, settings.state_file)}
        self.assertIn("cards_catalog_drift", codes)

    def test_live_validation_refuses_fixture_catalog(self) -> None:
        root = workspace_temp(self)
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work")
        Pipeline.mock(settings).run()
        codes = {issue.code for issue in validate_archive(settings.archive_dir, settings.state_file, expected_production=True)}
        self.assertIn("fixture_catalog_in_live_mode", codes)


if __name__ == "__main__":
    unittest.main()
