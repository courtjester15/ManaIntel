import gzip
import json
import unittest
from ffw.retained import restore_episode, restore_checkpoints
from ffw.production import GeminiTranscriber
from tests.test_reliability import candidate
from dataclasses import replace
from tests.workspace import workspace_temp


class RetainedRecoveryTests(unittest.TestCase):
    def test_partial_original_and_repair_recovery_preserves_other_progress_and_fingerprints(self):
        root = workspace_temp(self)
        source, target = root / "source", root / "target"
        writer = GeminiTranscriber("model", 900, checkpoint_root=source)
        episode = candidate()
        repair = replace(episode, guid=episode.guid + ":timing-repair-1")
        other = replace(episode, guid="other")
        for selected, count in ((episode, 2), (repair, 1), (other, 2)):
            writer._save_chunk_checkpoint(selected, 0, count, "matching", {"segments": []}, "model", 1)
        reader = GeminiTranscriber("model", 900, checkpoint_root=target)
        reader._save_chunk_checkpoint(other, 0, 2, "newer", {"segments": []}, "model", 2)
        restored = restore_checkpoints(source, target, episode.guid)
        self.assertEqual(2, len(restored))
        self.assertIsNotNone(reader._load_chunk_checkpoint(episode, 0, 2, "matching"))
        self.assertIsNotNone(reader._load_chunk_checkpoint(repair, 0, 1, "matching"))
        self.assertIsNotNone(reader._load_chunk_checkpoint(other, 0, 2, "newer"))
        self.assertIsNone(reader._load_chunk_checkpoint(episode, 0, 2, "changed-audio"))
        for guid in ("", "missing"):
            with self.assertRaises(ValueError):
                restore_checkpoints(source, target, guid)

    def test_historical_artifact_does_not_overwrite_other_episode_progress(self):
        root = workspace_temp(self)
        source, target = root / "source", root / "target"
        source.mkdir()
        target.mkdir()
        for guid in ("selected", "other"):
            with gzip.open(source / (guid + ".json.gz"), "wt") as stream:
                json.dump({"episode": {"guid": guid}, "transcript": {"text": "old"}}, stream)
        other = target / "other.json.gz"
        other.write_bytes(b"newer saved progress")
        restore_episode(source, target, "selected")
        self.assertEqual(b"newer saved progress", other.read_bytes())
        self.assertTrue((target / "selected.json.gz").exists())
        with self.assertRaises(ValueError):
            restore_episode(source, target, "missing")
        with self.assertRaises(ValueError):
            restore_episode(source, target, "")
