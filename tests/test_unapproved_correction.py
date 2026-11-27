from copy import deepcopy
import unittest

from ffw.reviews import normalize_review, apply_review, review_expectation
from pathlib import Path
from ffw.archive import rebuild_catalog
from ffw.card_resolution import resolve_archive_card_names
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

    def test_missing_pick_and_unknown_speakers_can_be_corrected_without_approval(self):
        values = {k: deepcopy(self.pick.get(k)) for k in ("card", "printing", "foil", "hosts", "recommendation",
                  "start_seconds", "end_seconds", "evidence_excerpt")}
        values.update(card="Recovered Card", hosts=[], start_seconds=25, end_seconds=35)
        payload = {**self.payload, "operations": [
            {"action": "update", "pick_id": self.pick["id"], "changes": {"hosts": []}},
            {"action": "add", "pick": values}]}
        review = normalize_review(self.summary, payload, actor="Codex source check")
        result = apply_review(self.summary, review)
        self.assertEqual(self.pick["id"], result["recommendations"][0]["id"])
        self.assertEqual([], result["recommendations"][0]["hosts"])
        self.assertEqual("Recovered Card", result["recommendations"][-1]["card"])
        self.assertEqual("needs_review", result["recommendations"][-1]["review_status"])
        self.assertNotIn("human_review", result["processing"])
        self.assertEqual("needs_review", result["processing"]["status"])

    def test_listening_time_repair_keeps_identity_and_unresolved_reason(self):
        self.pick["review_reason"] = "Card name remains uncertain."
        payload = {**self.payload, "operations": [{"action": "update", "pick_id": self.pick["id"],
                  "changes": {"start_seconds": 25, "end_seconds": None}}]}
        review = normalize_review(self.summary, payload, actor="Codex source check")
        result = apply_review(self.summary, review)["recommendations"][0]
        self.assertEqual(self.pick["id"], result["id"])
        self.assertEqual(self.pick["start_seconds"], result["identity_start_seconds"])
        self.assertEqual(25, result["start_seconds"])
        self.assertIn("Card name remains uncertain", result["review_reason"])
        self.assertTrue(result["listen_url"].endswith("#t=25"))

    def test_limited_clock_validation_cannot_approve_unmodified_bad_clocks(self):
        from ffw.reviews import _validate_review_clocks
        self.summary["recommendations"][1]["end_seconds"] = 99999
        _validate_review_clocks(self.summary, {self.pick["id"]})
        with self.assertRaisesRegex(ValueError, "duration"):
            _validate_review_clocks(self.summary)
        self.pick["start_seconds"] = 99999
        self.pick["end_seconds"] = None
        with self.assertRaisesRegex(ValueError, "duration"):
            _validate_review_clocks(self.summary, {self.pick["id"]})

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
        other_pick = self.summary["recommendations"][1]
        duplicate = deepcopy(self.payload)
        duplicate["operations"][0]["changes"].update(
            card=other_pick["card"].upper(), printing=other_pick["printing"],
            start_seconds=other_pick["start_seconds"], end_seconds=None,
        )
        with self.assertRaisesRegex(ValueError, "duplicate recommendation"):
            persist_review(archive, reviews, duplicate, actor="Codex")
        self.assertFalse(reviews.exists())
        self.payload["operations"][0]["changes"]["card"] = "Corrected Card"
        persist_review(archive, reviews, self.payload, actor="Codex", reviewed_at="2026-11-01T20:00:00Z")
        store_path = root / "state/card-resolutions.json"

        class Resolver:
            version = "test-v1"

            def resolve(self, raw_name):
                return {"raw_name": raw_name, "normalized_name": raw_name.casefold(),
                        "canonical_name": raw_name, "status": "verified", "oracle_id": "oracle:" + raw_name,
                        "resolver_version": self.version}

        resolve_archive_card_names(archive, store_path, Resolver())
        self.assertEqual(self.pick["card"], load_json(store_path)["resolutions"][self.pick["id"]]["raw_name"])
        resolve_archive_card_names(archive, store_path, Resolver(), reviews_dir=reviews)
        self.assertEqual("Corrected Card", load_json(store_path)["resolutions"][self.pick["id"]]["raw_name"])
        for _ in range(2):
            index, cards = rebuild_catalog(archive, production=True, reviews_dir=reviews,
                                           resolutions_path=store_path)
            corrected = next(pick for pick in cards if pick["id"] == self.pick["id"])
            self.assertEqual("Corrected Card", corrected["resolved_card"])
            self.assertEqual(self.pick["card"], corrected["identity_card"])
            self.assertFalse(index["episodes"][0]["human_reviewed"])
            self.assertEqual("needs_review", index["episodes"][0]["processing_status"])
            self.assertEqual(before, (directory / "summary.json").read_bytes())
            self.assertEqual([], validate_archive(archive, root / "state/episodes.json", reviews_dir=reviews))
