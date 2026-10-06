from __future__ import annotations

import re
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


@unittest.skipIf(yaml is None, "Install the test extra for YAML validation")
class WorkflowTests(unittest.TestCase):
    def workflows(self):
        root = Path(__file__).resolve().parents[1]
        return [yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
                for path in [root / ".github/workflows/ffw.yml", root / ".github/workflows/reprocess-queue.yml"]]

    def test_workflows_parse_and_step_references_exist(self):
        for workflow in self.workflows():
            self.assertIn("on", workflow)
            for job in workflow["jobs"].values():
                ids = [step["id"] for step in job["steps"] if "id" in step]
                self.assertEqual(len(ids), len(set(ids)))
                for step in job["steps"]:
                    for referenced in re.findall(r"steps\.([a-zA-Z_0-9]+)\.", str(step)):
                        self.assertIn(referenced, ids)

    def test_inline_python_compiles_without_running_providers(self):
        for workflow in self.workflows():
            for job in workflow["jobs"].values():
                for step in job["steps"]:
                    run = step.get("run", "")
                    for code in re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", run, re.S):
                        compile(code, step.get("name", "workflow"), "exec")

    def test_shared_cache_identity_and_failure_evidence(self):
        for workflow in self.workflows():
            steps = next(iter(workflow["jobs"].values()))["steps"]
            restores = [step for step in steps if step.get("uses") == "actions/cache/restore@v4"]
            self.assertTrue(any(step["with"]["path"] == ".ffw-work/chunk-checkpoints" for step in restores))
            self.assertTrue(any(step["with"]["path"] == ".ffw-work/transcripts" for step in restores))
            self.assertTrue(any(step.get("id") == "preflight" for step in steps))
            audit = next(step for step in steps if step.get("id") == "audit")
            self.assertIn("always()", audit["if"])
            persistence = next(step for step in steps if "git add state/episode-attempts.md" in step.get("run", ""))
            self.assertIn("always()", persistence["if"])
            self.assertIn('steps.validation.outcome', persistence["run"])


if __name__ == "__main__":
    unittest.main()
