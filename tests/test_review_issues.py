import unittest
from copy import deepcopy
from ffw.review_issues import collect_review_issues, name_only_reason, resolve_verified_name


class ReviewIssueTests(unittest.TestCase):
    def test_name_confirmation_cannot_clear_price_intent_or_timing(self):
        for reason in (
            "Possible transcription error in card name; foil price point is ambiguous.",
            "Card name is uncertain; host disagreement and recommendation intent need checking.",
            "Card name is ambiguous and timestamps are clustered.",
            "Card name may belong to a non-Magic game.",
        ):
            with self.subTest(reason=reason):
                pick = {"card": "Old Name", "review_status": "needs_review", "review_reason": reason}
                resolve_verified_name(pick, "Correct Name")
                self.assertEqual("Correct Name", pick["card"])
                self.assertEqual("needs_review", pick["review_status"])
                self.assertEqual(reason, pick["review_reason"])
                self.assertTrue(pick["name_verification_resolution"]["other_review_required"])

    def test_name_only_confirmation_is_resolved_with_original_reason_retained(self):
        reason = "Possible transcription error in card name."
        pick = {"card": "Old Name", "review_status": "needs_review", "review_reason": reason}
        resolve_verified_name(pick, "Correct Name")
        self.assertEqual("approved", pick["review_status"])
        self.assertIsNone(pick["review_reason"])
        self.assertEqual(reason, pick["name_verification_resolution"]["original_review_reason"])

    def test_unknown_prose_is_never_name_only(self):
        for reason in (None, "Ambiguous.", "Card information is ambiguous.", "Check this recommendation."):
            self.assertFalse(name_only_reason(reason))

    def test_boundaries_and_printings_survive_resolved_identity(self):
        extraction = {"section": {"review_reason": "Missing section ending."}, "recommendations": [
            {"card": "Correct Name", "review_status": "needs_review", "review_reason": "Foil price point is ambiguous."},
        ]}
        original = deepcopy(extraction)
        issues = collect_review_issues(extraction)
        self.assertEqual({"coverage", "printing"}, {issue["code"] for issue in issues})
        self.assertEqual(original, extraction)
        self.assertTrue(all(i["state"] == "unresolved" for i in issues))

    def test_suspect_bounds_and_outside_section_are_explicit_issues(self):
        extraction = {"section": {"start_seconds": 10, "end_seconds": 20}, "recommendations": [
            {"card": "Example", "review_status": "approved", "start_seconds": 30, "end_seconds": 120},
        ]}
        issues = collect_review_issues(extraction, duration_seconds=100)
        self.assertEqual({"coverage", "timing"}, {i["code"] for i in issues})
        self.assertTrue(all(i["path"] == "recommendations/0" for i in issues))

    def test_clean_explicit_pick_does_not_need_review_for_source_caveats(self):
        extraction = {"section": {"start_seconds": 10, "end_seconds": 30}, "recommendations": [
            {"card": "Example", "review_status": "approved", "start_seconds": 12, "end_seconds": 20,
             "caveats": ["Other host disagrees; buy only below five dollars."]},
        ]}
        self.assertEqual([], collect_review_issues(extraction, duration_seconds=100))

class BoundaryEvidenceTests(unittest.TestCase):
    def test_advertised_topic_casual_handoff_bounds_final_selection(self):
        from ffw.detection import locate_cards_to_watch
        section = locate_cards_to_watch([
            {"start": 600, "end": 620, "text": "Cards to watch."},
            {"start": 630, "end": 700, "text": "My first pick is Example Alpha."},
            {"start": 900, "end": 1000, "text": "My final selection this week is Example Beta."},
            {"start": 1100, "end": 1150, "text": "All righty. So the Spider-Man Secret Lair dropped this morning."},
        ], title="Spider-Man Secret Lair launch")
        self.assertEqual(1000, section["end_seconds"])
        self.assertEqual("advertised_topic_transition", section["end_signal"])

    def test_casual_handoff_with_another_pick_cannot_end_section(self):
        from ffw.detection import locate_cards_to_watch
        section = locate_cards_to_watch([
            {"start": 600, "end": 620, "text": "Cards to watch."},
            {"start": 630, "end": 700, "text": "My first pick is Example Alpha."},
            {"start": 900, "end": 1000, "text": "All righty. So my next pick is a Spider-Man Secret Lair."},
        ], title="Spider-Man Secret Lair launch")
        self.assertEqual(1000, section["end_seconds"])
        self.assertIsNone(section["end_signal"])
        self.assertIsNotNone(section["review_reason"])

class VerificationIntegrationTests(unittest.TestCase):
    def test_confirmed_name_preserves_mixed_pick_and_episode_reason(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from tests.test_reliability import fake_sdk, candidate
        from tests.workspace import workspace_temp
        from ffw.verification import GeminiPickVerifier
        root = workspace_temp(self)
        audio = root / "audio.mp3"
        audio.write_bytes(b"audio")
        resolver = SimpleNamespace(resolve=lambda name: {"status": "verified", "canonical_name": "Correct Name"})
        verifier = GeminiPickVerifier("model", 900, resolver)
        reason = "Card name transcription is ambiguous; foil price point needs review."
        extraction = {"review_reason": "Ambiguous card name and missing section ending.", "recommendations": [
            {"card": "Old Name", "start_seconds": 20, "review_status": "needs_review", "review_reason": reason},
        ]}
        def clip(source, destination, seconds):
            destination.write_bytes(b"clip")
            return destination
        with fake_sdk(), patch.object(verifier, "_clip", side_effect=clip), patch(
            "ffw.verification._gemini_generate_json", return_value={"decision": "corrected", "card": "Correct Name"}
        ):
            verifier.verify(candidate(), extraction, [audio])
        self.assertEqual(reason, extraction["recommendations"][0]["review_reason"])
        self.assertEqual("needs_review", extraction["recommendations"][0]["review_status"])
        self.assertIn("missing section ending", extraction["review_reason"])

    def test_outside_audio_name_check_makes_no_model_request(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from tests.test_reliability import fake_sdk, candidate
        from ffw.verification import GeminiPickVerifier
        verifier = GeminiPickVerifier("model", 900, SimpleNamespace())
        extraction = {"recommendations": [{"card": "Old Name", "start_seconds": 1900,
            "review_status": "needs_review", "review_reason": "Card name transcription error."}]}
        with fake_sdk(), patch("ffw.verification._gemini_generate_json") as generate:
            verifier.verify(candidate(), extraction, [object()])
        generate.assert_not_called()
        self.assertFalse(extraction["recommendations"][0]["automated_verification"]["accepted"])


class VerificationEligibilityTests(unittest.TestCase):
    def test_unknown_name_reason_is_checked_but_source_risk_is_not(self):
        from ffw.verification import GeminiPickVerifier
        self.assertTrue(GeminiPickVerifier._is_card_name_ambiguity({
            "review_status": "needs_review", "review_reason": "This is not a known Magic card."}))
        self.assertFalse(GeminiPickVerifier._is_card_name_ambiguity({
            "review_status": "needs_review", "review_reason": "Hosts disagree about reprint risk."}))
