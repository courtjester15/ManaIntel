from copy import deepcopy
import unittest

from ffw.reviews import normalize_review, apply_review, review_expectation
from pathlib import Path
from ffw.archive import rebuild_catalog
from ffw.reviews import persist_review
from ffw.rendering import render_episode_markdown
from ffw.utils import atomic_write_json, atomic_write_text, load_json
from ffw.validation import validate_archive
from tests.workspace import workspace_temp
from tests.test_reviews import summary


class UnapprovedCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.summary = summary()
        self.pick = self.summary["recommendations"][0]
        self.payload = {"schema_version": "1.0.0", "source_id": "mtg-fast-finance",
                        "episode_guid": self.summary["episode"]["guid"], "expected": review_expectation(self.summary),
                        "decision": "correct_without_approval", "note": "Independent local ASR corroborates two fields; not human reviewed.",
                        "operations": [{"action": "update", "pick_id": self.pick["id"],
                                        "changes": {"printing": "full art", "entry_target": None}}]}

    def test_machine_correction_preserves_original_identity_other_picks_and_uncertainty(self):
        original = deepcopy(self.summary)
        review = normalize_review(self.summary, self.payload, actor="Codex local audio check")
        effective = apply_review(self.summary, review)
        self.assertEqual(original, self.summary)
        self.assertEqual(self.pick["id"], effective["recommendations"][0]["id"])
        self.assertEqual("full art", effective["recommendations"][0]["printing"])
        self.assertEqual(original["recommendations"][1:], effective["recommendations"][1:])
        self.assertEqual("needs_review", effective["processing"]["status"])
        self.assertNotIn("human_review", effective["processing"])
        self.assertIn("machine_correction", effective["processing"])

    def test_machine_correction_cannot_approve_add_remove_invent_prices_or_override_human(self):
        for op in ({"action": "exclude", "pick_id": self.pick["id"]},
                   {"action": "update", "pick_id": self.pick["id"], "changes": {"hosts": ["Guessed"]}},
                   {"action": "update", "pick_id": self.pick["id"], "changes": {"entry_target": {"raw": "new"}}}):
            with self.subTest(op=op), self.assertRaises(ValueError):
                normalize_review(self.summary, {**self.payload, "operations": [op]}, actor="Codex")
        self.summary["processing"]["human_review"] = {"reviewed_by": "Owner"}
        self.payload["expected"] = review_expectation(self.summary)
        with self.assertRaisesRegex(ValueError, "cannot replace a human"):
            normalize_review(self.summary, self.payload, actor="Codex")

    def test_durable_correction_rebuild_preserves_extraction_and_never_claims_human_review(self):
        root = workspace_temp(self)
        archive, reviews = root / "archive", root / "data/reviews"
        directory = archive / "episodes/fixture"
        atomic_write_json(directory / "summary.json", self.summary)
        before = (directory / "summary.json").read_bytes()
        atomic_write_text(directory / "summary.md", render_episode_markdown(self.summary))
        atomic_write_json(directory / "metadata.json", {"synthetic": False, "episode": self.summary["episode"],
                          "processing": self.summary["processing"], "outputs": {"summary_json": "episodes/fixture/summary.json",
                          "summary_markdown": "episodes/fixture/summary.md"}})
        atomic_write_json(root / "state/episodes.json", {"episodes": {self.summary["episode"]["guid"]: {"status": "complete"}}})
        persist_review(archive, reviews, self.payload, actor="Codex", reviewed_at="2026-11-01T20:00:00Z")
        for _ in range(2):
            index, _ = rebuild_catalog(archive, production=True, reviews_dir=reviews)
            self.assertFalse(index["episodes"][0]["human_reviewed"])
            self.assertEqual("needs_review", index["episodes"][0]["processing_status"])
            self.assertEqual(before, (directory / "summary.json").read_bytes())
            self.assertEqual([], validate_archive(archive, root / "state/episodes.json", reviews_dir=reviews))
