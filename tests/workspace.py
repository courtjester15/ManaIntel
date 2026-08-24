from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


def workspace_temp(test_case: unittest.TestCase) -> Path:
    """Create a per-test workspace and remove it during test cleanup."""
    test_root = Path.cwd() / ".test-work"
    test_root.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(
        dir=test_root,
        prefix="test-",
        ignore_cleanup_errors=True,
    )
    test_case.addCleanup(temporary.cleanup)
    return Path(temporary.name)
