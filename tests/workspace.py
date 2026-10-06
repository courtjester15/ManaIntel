from __future__ import annotations

import atexit
import shutil
import tempfile
import re
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4


_WORKSPACE_RETENTION = timedelta(days=1)
_test_root = Path.cwd() / ".test-work"
_run_root: Path | None = None


def _remove_stale_workspaces(test_root: Path) -> None:
    """Remove abandoned workspaces after a short retention window.

    A run that is interrupted may not reach its atexit cleanup. Keeping such
    workspaces for one day leaves a brief debugging window without letting the
    ignored directory grow indefinitely.
    """
    cutoff = datetime.now(UTC) - _WORKSPACE_RETENTION
    for workspace in test_root.iterdir():
        if (
            not re.fullmatch(r"run-[0-9a-f]{32}", workspace.name)
            or not workspace.is_dir()
            or workspace.is_symlink()
            or getattr(workspace, "is_junction", lambda: False)()
            or workspace.resolve().parent != test_root.resolve()
            or workspace.stat().st_mtime > cutoff.timestamp()
        ):
            continue
        shutil.rmtree(workspace, ignore_errors=True)


def _cleanup_run_workspace() -> None:
    if _run_root is None:
        return
    if _run_root.resolve().parent != _test_root.resolve() or _run_root.is_symlink() or getattr(_run_root, "is_junction", lambda: False)():
        return
    shutil.rmtree(_run_root, ignore_errors=True)
    try:
        _test_root.rmdir()
    except OSError:
        # Another test process may still be using the shared parent directory.
        pass


def _run_workspace() -> Path:
    global _run_root
    if _run_root is None:
        _test_root.mkdir(parents=True, exist_ok=True)
        _remove_stale_workspaces(_test_root)
        _run_root = _test_root / f"run-{uuid4().hex}"
        _run_root.mkdir()
        atexit.register(_cleanup_run_workspace)
    return _run_root


def workspace_temp(test_case: unittest.TestCase) -> Path:
    """Create a per-test workspace and remove it during test cleanup."""
    temporary = tempfile.TemporaryDirectory(
        dir=_run_workspace(),
        prefix="test-",
        ignore_cleanup_errors=True,
    )
    test_case.addCleanup(temporary.cleanup)
    return Path(temporary.name)
