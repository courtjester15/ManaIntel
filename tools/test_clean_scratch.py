import os
from pathlib import Path
import tempfile
import unittest

from clean_scratch import inventory


class ScratchTests(unittest.TestCase):
    def test_only_old_opted_in_unpinned_non_git_folders(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / ".tmp") as tmp:
            root = Path(tmp)
            for name in ("eligible", "recent", "pinned", "active", "worktree", "unmarked"):
                folder = root / ".tmp" / name
                folder.mkdir(parents=True)
                (folder / "data").write_text("test")
                if name != "unmarked":
                    (folder / ".disposable").touch()
                extra = {"pinned": ".keep", "active": ".active", "worktree": ".git"}.get(name)
                if extra:
                    (folder / extra).touch()
                for item in folder.iterdir():
                    os.utime(item, (1, 1))
                os.utime(folder, (1, 1))
            os.utime(root / ".tmp/recent/data", (2000000, 2000000))
            self.assertEqual([p.name for p, _ in inventory(root, now=2000000)], ["eligible"])
            # Recovery evidence is excluded even if someone adds a marker.
            evidence = root / ".ffw-work/transcripts"
            evidence.mkdir(parents=True)
            (evidence / ".disposable").touch()
            self.assertEqual([p.name for p, _ in inventory(root, now=2000000)], ["eligible"])


if __name__ == "__main__":
    unittest.main()
