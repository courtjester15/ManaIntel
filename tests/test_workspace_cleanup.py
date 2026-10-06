from __future__ import annotations

import os
import time
import unittest

from tests.workspace import _remove_stale_workspaces, workspace_temp


class WorkspaceCleanupTests(unittest.TestCase):
    def test_only_old_owned_run_directories_are_removed(self) -> None:
        root = workspace_temp(self)
        old = root / ("run-" + "a" * 32)
        fresh = root / ("run-" + "b" * 32)
        foreign = root / "keep-my-debug-data"
        for folder in (old, fresh, foreign):
            folder.mkdir()
            (folder / "evidence.txt").write_text("keep", encoding="utf-8")
        earlier = time.time() - 172800
        for folder in (old, foreign):
            os.utime(folder, (earlier, earlier))
        _remove_stale_workspaces(root)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())
        self.assertTrue((foreign / "evidence.txt").exists())
