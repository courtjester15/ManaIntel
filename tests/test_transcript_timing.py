import unittest

from ffw.transcript_timing import suspect_timing_chunks


class TranscriptTimingTests(unittest.TestCase):
    def test_compressed_clock_is_flagged_but_normal_seconds_are_not(self):
        segments = [{"start": i / 2, "end": i / 2 + 0.1, "text": "word " * 70} for i in range(50)]
        self.assertEqual([0], suspect_timing_chunks({"segments": segments}))
        normal = [{**s, "start": i * 17, "end": i * 17 + 16} for i, s in enumerate(segments)]
        self.assertEqual([], suspect_timing_chunks({"segments": normal}))

    def test_sparse_short_final_chunk_is_not_flagged(self):
        segments = [{"start": 900 + i, "end": 901 + i, "text": "yes"} for i in range(25)]
        self.assertEqual([], suspect_timing_chunks({"segments": segments}))
