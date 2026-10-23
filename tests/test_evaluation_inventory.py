from copy import deepcopy
import json
import unittest

from tools.evaluate_picks import compare, DEFAULT_INVENTORY


class ExpectedPickEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.inventory = json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8"))
        self.case = self.inventory["cases"][1]
        self.summary = {"episode": {"guid": self.case["episode_guid"]}, "recommendations": [
            {"card": "Psychic Frog", "recommendation": "buy", "start_seconds": 3576},
            {"card": "Fire Crystal", "recommendation": "buy", "printing": "Final Fantasy full art",
             "entry_target": {"minimum": None, "maximum": None}, "start_seconds": 3683},
            {"card": "Suture Priest", "recommendation": "buy", "printing": "New Phyrexia",
             "start_seconds": 3786},
        ]}

    def test_missing_pick_cannot_be_hidden_by_matching_count_or_valid_structure(self):
        self.summary["recommendations"][0]["card"] = "Unrelated discussion card"
        result = compare(self.case, self.summary)
        self.assertEqual([{"card": "Psychic Frog", "field": "presence", "problem": "missing"}], result["findings"])

    def test_historical_price_as_target_and_lost_variant_are_separate_findings(self):
        self.summary["recommendations"][1].update(
            printing="Final Fantasy", entry_target={"minimum": 2.5, "maximum": 5})
        result = compare(self.case, self.summary)
        self.assertEqual({"entry_target", "printing"}, {item["field"] for item in result["findings"]})

    def test_unknown_attribution_is_unscored_and_comparison_is_read_only(self):
        original = deepcopy(self.summary)
        result = compare(self.case, self.summary)
        self.assertFalse(result["findings"])
        self.assertTrue(result["unscored"])
        self.assertEqual(original, self.summary)
        self.assertNotIn("accuracy", result)

    def test_bad_clock_is_detected_without_claiming_audio_alignment(self):
        for clock in (True, "3786", None, 180):
            with self.subTest(clock=clock):
                self.summary["recommendations"][2]["start_seconds"] = clock
                self.assertEqual("start_seconds", compare(self.case, self.summary)["findings"][0]["field"])

    def test_duplicate_variants_abstain_instead_of_selecting_convenient_match(self):
        self.summary["recommendations"].append(deepcopy(self.summary["recommendations"][0]))
        self.assertEqual("ambiguous multiplicity", compare(self.case, self.summary)["findings"][0]["problem"])

    def test_wrong_episode_is_rejected_even_with_matching_cards(self):
        self.summary["episode"]["guid"] = "different-episode"
        with self.assertRaisesRegex(ValueError, "GUID"):
            compare(self.case, self.summary)

    def test_malformed_candidate_is_rejected_instead_of_looking_like_empty_success(self):
        for value in (None, [], {"episode": None},
                      {"episode": self.summary["episode"], "recommendations": ["card"]}):
            with self.subTest(candidate=value), self.assertRaises(ValueError):
                compare(self.case, value)

    def test_inventory_has_both_shows_with_evidence_and_explicit_limits(self):
        self.assertEqual(2, len(self.inventory["cases"]))
        for case in self.inventory["cases"]:
            self.assertEqual(64, len(case["evidence"]["sha256"]))
            self.assertTrue(case["unscored"])
            self.assertIn("not_independent_audio", case["basis"])
            for pick in case["expected_picks"]:
                self.assertTrue(pick["rationale"])
                self.assertLess(pick["start_window"][0], pick["start_window"][1])


if __name__ == "__main__":
    unittest.main()
