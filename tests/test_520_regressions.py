import unittest

from ffw.detection import locate_cards_to_watch
from ffw.transcript_timing import missing_recommendation_content


class Recovery520Tests(unittest.TestCase):
    def test_agenda_and_topic_of_week_bound_real_recommendations(self):
        result = locate_cards_to_watch([
            {"start": 118, "end": 146, "text": "Lots to do. Segment two is top movers. Segment three is online. Then we've got cards to watch and the preview stream."},
            {"start": 600, "end": 700, "text": "These are the online movers."},
            {"start": 780, "end": 900, "text": "I've got a good pick here. Displacer Kitten blacklight foils look like forty to eighty."},
            {"start": 914, "end": 1033, "text": "My first pick is Torment of Hailfire."},
            {"start": 1256, "end": 1425, "text": "My last pick is Victimize."},
            {"start": 1436, "end": 1601, "text": "Let's move on over to the topic of the week. Secrets of Strixhaven reveals."},
        ], title="MTG Fast Finance Ep 520: SOS Previews In Focus")
        self.assertEqual(780, result["start_seconds"])
        self.assertEqual(1425, result["end_seconds"])
        self.assertEqual("recommendation_language", result["start_signal"])
        self.assertEqual("advertised_topic_transition", result["end_signal"])
        self.assertIsNone(result["review_reason"])

    def test_dropped_pick_is_flagged_without_inventing_timing(self):
        text = ("I've got a good pick here. Displacer Kitten blacklight foils have scarce listings, "
                "Commander demand, strong liquidity, unusual artwork, premium finish, healthy supply, "
                "longterm potential and attractive pricing.")
        transcript = {"text": text, "segments": [{"start": 600, "end": 650, "text": "Online movers are changing prices."}]}
        self.assertEqual(1, missing_recommendation_content(transcript))
        self.assertEqual(text, transcript["text"])
        self.assertEqual(1, len(transcript["segments"]))
        transcript["segments"][0]["text"] = text
        self.assertEqual(0, missing_recommendation_content(transcript))

    def test_no_full_text_does_not_create_false_gap(self):
        self.assertEqual(0, missing_recommendation_content({"segments": []}))
