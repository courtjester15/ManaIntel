"""Persist a workflow commit without losing a concurrent journal/code update."""
import argparse
from pathlib import Path
import subprocess
from .audit import render_attempt_log


def _git(root, *args, check=True):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr[-1200:]}")
    return result


def push_commit(root: Path, branch: str, max_attempts: int = 3):
    for _ in range(max_attempts):
        _git(root, "fetch", "origin", branch)
        current = _git(root, "merge-base", "--is-ancestor", f"origin/{branch}", "HEAD", check=False)
        if current.returncode:
            # Only the derived Markdown index is discarded and regenerated.
            # Actual JSON/archive conflicts stop rebase rather than pick a side.
            _git(root, "restore", "--source=HEAD^", "--staged", "--worktree", "state/episode-attempts.md")
            _git(root, "commit", "--amend", "--no-edit", "--allow-empty")
            _git(root, "rebase", f"origin/{branch}")
            render_attempt_log(root / "state")
            _git(root, "add", "state/episode-attempts.md")
            _git(root, "commit", "--amend", "--no-edit", "--allow-empty")
        result = _git(root, "push", "origin", f"HEAD:{branch}", check=False)
        if result.returncode == 0:
            return
    raise RuntimeError("Production branch advanced repeatedly; retained artifacts require inspected persistence recovery.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    args = parser.parse_args()
    push_commit(Path.cwd(), args.branch)
