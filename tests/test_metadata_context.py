import json
import unittest
from copy import deepcopy
from ffw.production import extraction_evidence
from ffw.review_issues import published_version_regression


class MetadataContextTests(unittest.TestCase):
    def test_introduction_and_boundary_context_do_not_become_recommendation_scope(self):
        intro = {"start": 10, "text": "I am Host A, with Host B.", "speaker": "Host A"}
        pick = {"start": 110, "text": "My pick is Card One.", "speaker": "Host B"}
        variant = {"start": 201, "text": "That is the bonus card from the Artist Drop."}
        unrelated = {"start": 300, "text": "My unrelated pick is Card Two."}
        section = {"start_seconds": 100, "end_seconds": 200, "segments": [pick]}
        result = json.loads(extraction_evidence({"segments": [intro, pick, variant, unrelated]}, section))
        self.assertEqual([pick], result["recommendation_segments"])
        self.assertEqual([intro], result["context_only"]["introduction"])
        self.assertEqual([variant], result["context_only"]["after_section"])
        self.assertNotIn("segments", section)

    def test_reprocessing_cannot_silently_erase_or_change_known_attribution(self):
        before = {"recommendations": [{"card": "Card One", "hosts": ["Host A"]}]}
        for hosts in ([], ["Host B"], ["Host A", "Host B"]):
            after = deepcopy(before)
            after["recommendations"][0]["hosts"] = hosts
            self.assertTrue(published_version_regression(before, after))
        self.assertFalse(published_version_regression(before, before))
        after = deepcopy(before)
        after["recommendations"][0]["hosts"] = ["HOST A"]
        self.assertFalse(published_version_regression(before, after))

    def test_inspected_printing_correction_keeps_original_pick_identity(self):
        from ffw.pipeline import Pipeline
        from ffw.utils import stable_pick_id
        from ffw.models import EpisodeCandidate
        from unittest.mock import patch
        from types import SimpleNamespace
        item = EpisodeCandidate("guid", 1, "Episode 1", "2026-01-01T00:00:00Z", "https://example.test/audio", "https://example.test", [])
        original = stable_pick_id(item.guid, "Card One", 20, None)
        pipeline = object.__new__(Pipeline)
        extraction = {"section": {}, "recommendations": [{"card": "Card One", "start_seconds": 20,
            "printing": "Artist bonus card", "identity_printing": None}]}
        with patch.object(Pipeline, "_processing_metadata", return_value={}):
            result = pipeline._build_summary(item, extraction, "complete")
        self.assertEqual(original, result["recommendations"][0]["id"])
        self.assertEqual("Artist bonus card", result["recommendations"][0]["printing"])

    def test_timing_repair_retains_unique_exact_speaker_and_abstains_on_repetition(self):
        from ffw.transcript_timing import retain_exact_speakers
        quote = "This is my first recommendation for this particular week."
        old = [{"text": quote, "speaker": "Host A", "start": 900}]
        new = [{"text": quote, "speaker": None, "start": 780}]
        self.assertEqual(1, retain_exact_speakers(old, new))
        self.assertEqual("Host A", new[0]["speaker"])
        new[0]["speaker"] = None
        self.assertEqual(0, retain_exact_speakers(old + old, new))
        self.assertIsNone(new[0]["speaker"])
        new[0]["speaker"] = "Host B"
        self.assertEqual(0, retain_exact_speakers(old, new))
        self.assertEqual("Host B", new[0]["speaker"])
