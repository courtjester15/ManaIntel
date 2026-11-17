from copy import deepcopy
import unittest

from ffw.archive import rebuild_catalog
from ffw.review_issues import review_triage
from ffw.utils import atomic_write_json
from tests.test_reviews import summary
from tests.workspace import workspace_temp


class ReviewTriageTests(unittest.TestCase):
    def test_mixed_reasons_and_effective_pick_navigation_without_mutation(self):
        source = summary()
        source["processing"]["review_reason"] = "Missing section ending; timestamps need checking."
        source["recommendations"][0].update(review_status="needs_review", review_reason="Card name and foil price target are ambiguous.")
        original = deepcopy(source)
        triage = review_triage(source)
        self.assertEqual(0, triage["priority"])
        self.assertTrue({"coverage", "timing", "identity", "printing"}.issubset(triage["codes"]))
        pick_issues = [i for i in triage["issues"] if i.get("pick_id")]
        self.assertEqual(source["recommendations"][0]["id"], pick_issues[0]["pick_id"])
        self.assertEqual(source["recommendations"][0]["start_seconds"], pick_issues[0]["start_seconds"])
        self.assertEqual(original, source)

    def test_unknown_and_empty_publications_remain_actionable(self):
        source = summary()
        source.pop("section", None)
        source["processing"]["review_reason"] = "Investigate this odd result."
        source["recommendations"] = []
        triage = review_triage(source)
        self.assertEqual({"coverage", "unspecified"}, set(triage["codes"]))
        source["recommendations"] = deepcopy(summary()["recommendations"])
        for pick in source["recommendations"]:
            pick.update(review_status="approved", review_reason=None)
        self.assertEqual(["unspecified"], review_triage(source)["codes"])

    def test_human_approval_and_failure_are_excluded_even_with_old_warnings(self):
        source = summary()
        source["processing"].update(human_review={"reviewed_by": "Reviewer"})
        self.assertIsNone(review_triage(source))
        source["processing"].pop("human_review")
        source["processing"]["status"] = "failed"
        self.assertIsNone(review_triage(source))
        self.assertIsNone(review_triage(None))

    def test_clean_machine_checked_episode_is_not_treated_as_human_reviewed_or_flagged(self):
        source = summary()
        source["processing"].update(status="complete", review_reason=None)
        source.pop("section", None)
        for pick in source["recommendations"]:
            pick.update(review_status="approved", review_reason=None)
        self.assertIsNone(review_triage(source))
        source["processing"]["status"] = "needs_review"
        self.assertEqual(["unspecified"], review_triage(source)["codes"])

    def test_catalog_projects_effective_correction_and_removes_approved_queue_entry(self):
        # Exercise durable overrides through the existing projection, not a mock.
        from ffw.reviews import review_file_path, normalize_review
        from tests.test_reviews import payload
        root = workspace_temp(self)
        source = summary()
        directory = root / "archive/episodes/fixture"
        atomic_write_json(directory / "summary.json", source)
        atomic_write_json(directory / "metadata.json", {"episode": source["episode"], "processing": source["processing"], "outputs": {}})
        reviews = root / "data/reviews"
        review = payload(source)
        review.update(decision="correct_without_approval", operations=[{
            "action": "update", "pick_id": source["recommendations"][0]["id"], "changes": {"printing": "full art"}}])
        path = review_file_path(reviews, source["episode"]["source_id"], source["episode"]["guid"])
        atomic_write_json(path, normalize_review(source, review, actor="Test reviewer"))
        index, _ = rebuild_catalog(root / "archive", reviews_dir=reviews, write=False)
        self.assertIsNotNone(index["episodes"][0]["review_triage"])
        atomic_write_json(path, normalize_review(source, payload(source), actor="Test reviewer"))
        index, _ = rebuild_catalog(root / "archive", reviews_dir=reviews, write=False)
        self.assertIsNone(index["episodes"][0]["review_triage"])
