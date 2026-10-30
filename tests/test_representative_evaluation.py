import copy
import unittest

from ffw.detection import locate_recommendation_section
from ffw.transcript_timing import missing_recommendation_content, suspect_timing_chunks


class RepresentativeEvaluationTests(unittest.TestCase):
    """Invented minimal examples, not quotations or accuracy scores."""

    def test_ff_selection_handoff_keeps_all_four_recommendations(self):
        segments = [
            {"start": 90, "end": 100, "text": "Then cards to watch, and then previews."},
            {"start": 780, "end": 784, "text": "What is your first selection this week?"},
            {"start": 790, "end": 900, "text": "Example Alpha at seventeen could reach forty."},
            {"start": 950, "end": 1070, "text": "Example Beta foils are my next purchase."},
            {"start": 1080, "end": 1280, "text": "I am picking Example Gamma for demand."},
            {"start": 1290, "end": 1370, "text": "My pick is Example Delta, ten to twenty."},
            {"start": 1374, "end": 1380, "text": "All righty, let's move on over to the latest reveals from Example Expansion."},
        ]
        result = locate_recommendation_section(segments, "cards_to_watch", title="Example Expansion Deep Dive")
        self.assertEqual(780, result["start_seconds"])
        self.assertEqual(1370, result["end_seconds"])
        self.assertIsNone(result["review_reason"])
        self.assertEqual(segments[1:6], result["segments"])

    def test_brainstorm_keeps_bulk_and_late_pick_across_topic_gap(self):
        segments = [
            {"start": 600, "end": 630, "text": "Time for Breaking Bulk."},
            {"start": 640, "end": 700, "text": "My pick is Example Card Alpha."},
            {"start": 1500, "end": 1800, "text": "Discussion of the weekly topic."},
            {"start": 3000, "end": 3040, "text": "Pick of the week. My pick is Example Card Beta."},
        ]
        original = copy.deepcopy(segments)
        result = locate_recommendation_section(segments, "brainstorm_brewery")
        self.assertEqual(600, result["start_seconds"])
        self.assertEqual(3040, result["end_seconds"])
        self.assertIn(segments[1], result["segments"])
        self.assertIn(segments[3], result["segments"])
        self.assertIsNotNone(result["review_reason"])
        self.assertEqual(original, segments)

    def test_both_shows_preserve_uncertainty_without_explicit_end(self):
        for profile, marker in (("cards_to_watch", "Cards to watch."),
                                ("brainstorm_brewery", "Breaking Bulk.")):
            with self.subTest(profile=profile):
                result = locate_recommendation_section([
                    {"start": 600, "end": 610, "text": marker},
                    {"start": 620, "end": 660, "text": "My pick is Example Card Alpha."},
                ], profile)
                self.assertTrue(result["located"])
                self.assertIsNone(result["end_signal"])
                self.assertIsNotNone(result["review_reason"])
                self.assertNotEqual("high", result["confidence"])

    def test_content_omission_is_separate_from_valid_timing(self):
        missing = ("My first pick is Example Card Alpha with scarce listings, unusual artwork, "
                   "premium finish, Commander demand, strong liquidity, healthy supply, "
                   "longterm potential and attractive pricing.")
        transcript = {"chunk_count": 1, "text": missing, "segments": [
            {"start": 0, "end": 890, "text": "Discussion about weekly events."},
        ]}
        original = copy.deepcopy(transcript)
        self.assertEqual([], suspect_timing_chunks(transcript))
        self.assertGreater(missing_recommendation_content(transcript), 0)
        self.assertEqual(original, transcript)
        transcript["segments"][0]["text"] = missing
        self.assertEqual(0, missing_recommendation_content(transcript))

    def test_ff_advertised_topic_inside_next_pick_is_not_section_end(self):
        segments = [
            {"start": 790, "end": 800, "text": "Cards to watch."},
            {"start": 810, "end": 980, "text": "My first pick is Example Alpha."},
            {"start": 990, "end": 1257, "text": "Example Beta is our second choice."},
            {"start": 1258, "end": 1259, "text": "What about your next selection?"},
            {"start": 1260, "end": 1272, "text": "My other pick this week, so we are going to talk about the Sonic results."},
            {"start": 1280, "end": 1440, "text": "Example Gamma foils benefit from that demand."},
            {"start": 1450, "end": 1880, "text": "My final pick is Example Delta."},
            {"start": 1900, "end": 1910, "text": "Now moving on to the Sonic Secret Lair results."},
        ]
        result = locate_recommendation_section(segments, "cards_to_watch", title="Sonic Secret Lair Results")
        self.assertEqual(1880, result["end_seconds"])
        self.assertIn(segments[5], result["segments"])
        self.assertIn(segments[6], result["segments"])
