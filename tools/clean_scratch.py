"""Preview or remove explicitly disposable local scratch; never production evidence."""
from __future__ import annotations

import argparse
import stat
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]


def linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def inventory(root: Path, days: int = 14, now: float | None = None):
    cutoff = (time.time() if now is None else now) - days * 86400
    for name in (".tmp", ".test-work"):
        base = root / name
        if not base.is_dir() or linked(base):
            continue
        for folder in sorted(base.iterdir()):
            if not folder.is_dir() or linked(folder):
                continue
            entries = [folder]
            # Do not traverse links, junctions, or nested repositories.
            pending = [folder]
            unsafe = False
            while pending and not unsafe:
                for item in pending.pop().iterdir():
                    if linked(item) or item.name in (".git", ".keep", ".active"):
                        unsafe = True
                        break
                    entries.append(item)
                    if item.is_dir():
                        pending.append(item)
            if unsafe or not (folder / ".disposable").is_file():
                continue
            if max(item.stat().st_mtime for item in entries) > cutoff:
                continue
            yield folder, sum(item.stat().st_size for item in entries if item.is_file())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete eligible folders (default: preview)")
    parser.add_argument("--days", type=int, default=14, help="Minimum inactivity in days (default: 14)")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be at least 1")
    total = 0
    for folder, size in inventory(ROOT, args.days):
        # Resolve immediately before deletion and constrain to the intended scratch parent.
        if folder.resolve().parent not in (ROOT / ".tmp", ROOT / ".test-work"):
            raise RuntimeError(f"Scratch path escaped its parent: {folder}")
        print(f"{'Remove' if args.apply else 'Would remove'} {folder.relative_to(ROOT)} ({size / 1048576:.2f} MiB)")
        if args.apply:
            shutil.rmtree(folder)
        total += size
    print(f"{'Removed' if args.apply else 'Reclaimable'}: {total / 1048576:.2f} MiB")


if __name__ == "__main__":
    main()
