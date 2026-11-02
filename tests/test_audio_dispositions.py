import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ffw.audio_dispositions import apply_non_speech_tail
from ffw.transcript_timing import suspect_timing_chunks, unresolved_timing_chunks
from tests.workspace import workspace_temp


class AudioDispositionTests(unittest.TestCase):
    def setUp(self):
        self.root = workspace_temp(self)
        self.episode = SimpleNamespace(guid="inspected", audio_url="https://example.test/audio", duration_seconds=1100)
        self.source = self.root / "source.mp3"
        self.source.write_bytes(b"exact inspected bytes")
        self.prepared = [self.root / "first.mp3", self.root / "last.mp3"]
        self.transcript = {"chunk_count": 2, "segments": [{"start": 0, "end": 20, "text": "speech"}]}
        self.record = {"episode_guid": "inspected", "audio_url": self.episode.audio_url,
                       "source_sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
                       "chunk_index": 1, "start_seconds": 900, "end_seconds": 1100,
                       "method": "inspected_local_asr_and_vad_v1", "evidence_note": "Both readings found no speech.",
                       "inspected_at": "2026-11-01"}
        self.path = self.root / "data/audio-dispositions" / (hashlib.sha256(b"inspected").hexdigest()[:24] + ".json")

    def apply(self, record=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(record or self.record))
        with patch("ffw.audio_dispositions.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="200")):
            return apply_non_speech_tail(self.root, self.episode, self.source, self.prepared, self.transcript, 900)

    def test_exact_source_bound_tail_is_explicit_not_missing_coverage(self):
        self.assertEqual([1], suspect_timing_chunks(self.transcript))
        self.apply()
        self.assertEqual([], suspect_timing_chunks(self.transcript))
        self.transcript.update(timing_adjustments=1, timing_adjustment_chunks=[1])
        self.assertEqual([], unresolved_timing_chunks(self.transcript, 2))
        self.assertEqual([self.record], self.transcript["audio_dispositions"])

    def test_retained_claim_cannot_authorize_itself(self):
        self.transcript["source_bound_non_speech_chunks"] = [1]
        apply_non_speech_tail(self.root, self.episode, self.source, self.prepared, self.transcript, 900)
        self.assertEqual([1], suspect_timing_chunks(self.transcript))

    def test_changed_source_existing_speech_and_wrong_physical_interval_fail_closed(self):
        for mutation in ({"source_sha256": "wrong"}, {"chunk_index": 0}, {"end_seconds": 1200},
                         {"end_seconds": float("nan")}, {"episode_guid": "other"}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.apply({**self.record, **mutation})
        self.transcript["segments"].append({"start": 895, "end": 905, "text": "crossing speech"})
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.apply()
