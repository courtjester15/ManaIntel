import unittest

from ffw.transcript_timing import normalize_integer_clock, suspect_timing_chunks
from ffw.detection import locate_recommendation_section


class TranscriptTimingTests(unittest.TestCase):
    def test_opening_marker_beats_fourth_pick_and_split_topic_transition(self):
        segments = [{"start": 636, "end": 650, "text": "Taking a look at our first cards to watch."}]
        segments += [{"start": 651 + i, "end": 652 + i, "text": "Discussion of collecting."} for i in range(10)]
        segments += [
            {"start": 680, "end": 850, "text": "My first pick is Mox Amber."},
            {"start": 932, "end": 1100, "text": "My first pick this week is Bag End Banquet."},
            {"start": 1203, "end": 1900, "text": "I like Hobbit Collector Booster Boxes."},
            {"start": 1947, "end": 2200, "text": "My other card to watch is Extinction Event."},
            {"start": 2201, "end": 2210, "text": "Let's move on to what you don't think is positive EV."},
            {"start": 2210, "end": 2211, "text": "No."},
            {"start": 2211, "end": 2240, "text": "Tell the folks about the Zeta Secret Lair."},
        ]
        section = locate_recommendation_section(segments, "cards_to_watch", title="The Zeta Drop Fiasco")
        self.assertEqual(636, section["start_seconds"])
        self.assertEqual(2200, section["end_seconds"])
        self.assertEqual("advertised_topic_transition", section["end_signal"])

    def test_mmss_is_repaired_only_when_entire_chunk_proves_encoding(self):
        segments = [{"start": i * 100, "end": i * 100 + 30, "text": "speech"} for i in range(15) for _ in range(2)]
        repaired = normalize_integer_clock({"segments": segments}, 900)
        self.assertEqual(870, repaired["segments"][-1]["end"])
        self.assertEqual(1430, segments[-1]["end"])
        segments[0]["end"] = 99
        self.assertNotIn("clock_encoding_repaired", normalize_integer_clock({"segments": segments}, 900))

    def test_compressed_clock_is_flagged_but_normal_seconds_are_not(self):
        segments = [{"start": i / 2, "end": i / 2 + 0.1, "text": "word " * 70} for i in range(50)]
        self.assertEqual([0], suspect_timing_chunks({"segments": segments}))
        normal = [{**s, "start": i * 17, "end": i * 17 + 16} for i, s in enumerate(segments)]
        self.assertEqual([], suspect_timing_chunks({"segments": normal}))

    def test_sparse_short_final_chunk_is_not_flagged(self):
        segments = [{"start": 900 + i, "end": 901 + i, "text": "yes"} for i in range(25)]
        self.assertEqual([], suspect_timing_chunks({"segments": segments}))

    def test_clamped_chunk_end_is_flagged_as_previous_chunk(self):
        segments = [{"start": 900, "end": 900, "text": "speech"} for _ in range(8)]
        self.assertEqual([0], suspect_timing_chunks({"segments": segments}))
