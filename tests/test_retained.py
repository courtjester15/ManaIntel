import gzip
import json
import unittest
from ffw.retained import restore_episode
from tests.workspace import workspace_temp


class RetainedRecoveryTests(unittest.TestCase):
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
