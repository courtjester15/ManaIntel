from pathlib import Path
import shutil
import subprocess
import unittest


class RecoveryStatusUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is required for browser rendering checks")
    def test_recovery_status_behavior(self):
        result = subprocess.run(
            ["node", "--test", "tests/test_status_ui.cjs"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
