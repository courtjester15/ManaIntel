import json
from pathlib import Path
import shutil
import subprocess
import unittest
from ffw.audit import render_attempt_log
from ffw.persistence import push_commit
from tests.workspace import workspace_temp


@unittest.skipUnless(shutil.which("git"), "git required")
class PersistenceTests(unittest.TestCase):
    def git(self, root, *args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def setup_repos(self):
        root = workspace_temp(self)
        origin, local, other = root / "origin.git", root / "local", root / "other"
        self.git(root, "init", "--bare", "--initial-branch=master", str(origin))
        self.git(root, "clone", str(origin), str(local))
        self.git(local, "config", "user.email", "test@example.test")
        self.git(local, "config", "user.name", "Test")
        self.git(local, "checkout", "-b", "master")
        (local / "state/runs").mkdir(parents=True)
        (local / "state/attempts").mkdir()
        render_attempt_log(local / "state")
        (local / "archive.json").write_text('{"picks": 3}')
        self.git(local, "add", ".")
        self.git(local, "commit", "-m", "baseline")
        self.git(local, "push", "origin", "master")
        self.git(root, "clone", str(origin), str(other))
        self.git(other, "config", "user.email", "test@example.test")
        self.git(other, "config", "user.name", "Test")
        return origin, local, other

    def test_concurrent_journal_commit_preserves_both_runs_and_archive(self):
        origin, local, other = self.setup_repos()
        for repo, run in ((local, "live"), (other, "cancelled")):
            (repo / "state/runs").mkdir(exist_ok=True)
            (repo / "state/runs" / (run + "-1.json")).write_text(json.dumps({"run_id": run, "run_attempt": "1"}))
            render_attempt_log(repo / "state")
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", run)
        self.git(other, "push", "origin", "master")
        push_commit(local, "master")
        self.git(other, "pull", "--ff-only")
        log = (other / "state/episode-attempts.md").read_text()
        self.assertIn("run live/1", log)
        self.assertIn("run cancelled/1", log)
        self.assertEqual('{"picks": 3}', (other / "archive.json").read_text())

    def test_conflicting_archive_updates_stop_without_overwriting_remote(self):
        origin, local, other = self.setup_repos()
        for repo, picks in ((local, 4), (other, 5)):
            (repo / "archive.json").write_text(json.dumps({"picks": picks}))
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", str(picks))
        self.git(other, "push", "origin", "master")
        with self.assertRaises(RuntimeError):
            push_commit(local, "master")
        self.assertEqual('{"picks": 5}', self.git(other, "show", "origin/master:archive.json"))
