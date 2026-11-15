from copy import deepcopy
import unittest

from ffw.archive import rebuild_catalog
from ffw.reviews import apply_review, normalize_review, persist_review, review_revision
from ffw.utils import atomic_write_json, load_json
from tests.test_reviews import summary, payload
from tests.workspace import workspace_temp


class ReviewWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.source = summary()
        self.request = payload(self.source)
        self.request["operations"] = []
        self.root = workspace_temp(self)
        self.archive = self.root / "archive"
        self.reviews = self.root / "data/reviews"
        self.directory = self.archive / "episodes/review-fixture"
        atomic_write_json(self.directory / "summary.json", self.source)
        atomic_write_json(self.directory / "metadata.json", {
            "episode": self.source["episode"], "processing": self.source["processing"],
            "outputs": {"summary_json": "episodes/review-fixture/summary.json"},
        })

    def update(self, changes):
        self.request["operations"] = [{"action": "update", "pick_id": self.source["recommendations"][0]["id"],
                                       "changes": changes}]

    def persist(self):
        return persist_review(self.archive, self.reviews, self.request, actor="reviewer",
                              reviewed_at="2026-11-14T23:00:00Z")

    def test_price_context_targets_hold_and_unknown_speaker_survive_repeated_rebuilds(self):
        untouched = deepcopy(self.source)
        target = {"raw": "under five dollars", "currency": "USD", "minimum": None, "maximum": 5}
        self.update({"mentioned_price": "Previously ten dollars", "entry_target": target,
                     "exit_target": None, "hold": "Six months", "hosts": [],
                     "reasoning": ["Low supply", "  New demand  "], "caveats": ["May be reprinted"]})
        self.persist()
        for _ in range(2):
            index, cards = rebuild_catalog(self.archive, production=True, reviews_dir=self.reviews)
            corrected = next(pick for pick in cards if pick["card"] == "Wrong Card")
            self.assertEqual([], corrected["hosts"])
            self.assertEqual(target, corrected["entry_target"])
            self.assertEqual("Previously ten dollars", corrected["mentioned_price"])
            self.assertEqual("Six months", corrected["hold"])
            self.assertEqual(["Low supply", "New demand"], corrected["reasoning"])
            self.assertEqual(["May be reprinted"], corrected["caveats"])
            self.assertTrue(index["episodes"][0]["human_reviewed"])
            self.assertEqual(index["episodes"][0]["review_revision"],
                             load_json(self.directory / "effective.json")["processing"]["review_revision"])
        self.assertEqual(untouched, load_json(self.directory / "summary.json"))

    def test_new_pick_can_keep_unknown_attribution_and_explicit_target(self):
        operation = payload(self.source)["operations"][-1]
        operation["pick"].update(hosts=[], entry_target={"raw": "five dollars", "currency": None,
                                                       "minimum": 5, "maximum": 5}, hold="one year")
        self.request["operations"] = [operation]
        effective = apply_review(self.source, normalize_review(self.source, self.request, actor="reviewer"))
        self.assertEqual([], effective["recommendations"][-1]["hosts"])
        self.assertEqual("one year", effective["recommendations"][-1]["hold"])
        self.assertEqual(5, effective["recommendations"][-1]["entry_target"]["minimum"])

    def test_stale_review_cannot_overwrite_a_newer_review_even_when_extraction_is_unchanged(self):
        self.request.update(decision="correct_without_approval", note="Checked printing only; other uncertainty remains.")
        self.update({"printing": "Full art", "entry_target": None})
        path = self.persist()
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "saved review changed"):
            self.persist()
        self.assertEqual(before, path.read_bytes())
        self.request["expected_review_revision"] = review_revision(load_json(path))
        self.request["decision"] = "approve"
        self.persist()
        effective = apply_review(self.source, load_json(path))
        self.assertEqual("Full art", effective["recommendations"][0]["printing"])
        self.assertEqual("complete", effective["processing"]["status"])
        self.assertEqual(self.source, load_json(self.directory / "summary.json"))

    def test_legacy_payloads_remain_readable_but_cannot_replace_a_saved_override(self):
        self.request["schema_version"] = "1.0.0"
        self.request.pop("expected_review_revision")
        path = self.persist()
        self.assertEqual("complete", apply_review(self.source, load_json(path))["processing"]["status"])
        with self.assertRaisesRegex(ValueError, "legacy payload cannot replace"):
            self.persist()

    def test_limited_correction_cannot_replace_a_durable_human_review_on_raw_extraction(self):
        path = self.persist()
        before = path.read_bytes()
        self.request["expected_review_revision"] = review_revision(load_json(path))
        self.request["decision"] = "correct_without_approval"
        self.update({"printing": "Unapproved replacement"})
        with self.assertRaisesRegex(ValueError, "cannot replace a human review"):
            self.persist()
        self.assertEqual(before, path.read_bytes())

    def test_invalid_targets_never_replace_an_existing_review(self):
        path = self.persist()
        before = path.read_bytes()
        self.request["expected_review_revision"] = review_revision(load_json(path))
        target = {"raw": "under five", "currency": "USD", "minimum": None, "maximum": 5}
        for invalid in ({}, {**target, "raw": ""}, {**target, "maximum": True},
                        {**target, "raw": {"guess": "five"}}, {**target, "currency": ["USD"]},
                        {**target, "minimum": 10}, {**target, "maximum": -1},
                        {**target, "maximum": float("nan")}, {**target, "maximum": float("inf")},
                        {**target, "maximum": "5"}):
            with self.subTest(target=invalid):
                self.update({"entry_target": invalid})
                with self.assertRaises(ValueError):
                    self.persist()
                self.assertEqual(before, path.read_bytes())

    def test_invalid_clocks_and_duplicates_fail_before_any_override_is_written(self):
        for changes in ({"start_seconds": 3601}, {"end_seconds": 600}, {"start_seconds": None},
                        {"start_seconds": 620.5}, {"start_seconds": True},
                        {"card": "Keep Card", "printing": "Regular", "start_seconds": 700}):
            with self.subTest(changes=changes):
                self.update(changes)
                with self.assertRaises(ValueError):
                    self.persist()
                self.assertFalse(self.reviews.exists())

    def test_schema_requires_explicit_revision_and_limited_correction_requires_changes(self):
        del self.request["expected_review_revision"]
        with self.assertRaisesRegex(ValueError, "expected_review_revision"):
            self.persist()
        self.request["expected_review_revision"] = None
        self.request["decision"] = "correct_without_approval"
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.persist()


if __name__ == "__main__":
    unittest.main()
