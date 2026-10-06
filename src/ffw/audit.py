"""Metadata-only journals: one atomic file per attempt, never transcript bodies."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import PIPELINE_VERSION, PROMPT_VERSION
from .models import utc_now
from .utils import atomic_write_json, atomic_write_text, load_json


def safe_message(value: Any) -> str:
    text = str(value)
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        secret = os.getenv(name)
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"\bAIza[\w-]+|\bsk-[\w-]+|(?i:Bearer)\s+\S+", "[redacted]", text)
    return text[:4000]


class AttemptJournal:
    def __init__(self, state_file: Path, episode: Any, **context: Any) -> None:
        self.root = state_file.parent
        self.data = {
            "schema_version": 1, "attempt_id": uuid4().hex,
            "episode": {"guid": episode.guid, "number": episode.episode_number,
                        "title": episode.title, "source": episode.source_id},
            "started_at": utc_now(), "pipeline_version": PIPELINE_VERSION,
            "prompt_version": PROMPT_VERSION,
            "run_id": os.getenv("GITHUB_RUN_ID"), "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "git_sha": os.getenv("GITHUB_SHA"), "intervention": safe_message(os.getenv("FFW_ATTEMPT_NOTE", "")),
            "context": context, "events": [], "outcome": "running",
        }
        repo, run = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_RUN_ID")
        if not self.data["git_sha"]:
            try:
                revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=state_file.parent.parent,
                                          capture_output=True, text=True, timeout=5)
                self.data["git_sha"] = revision.stdout.strip() if revision.returncode == 0 else None
                dirty = subprocess.run(["git", "diff", "--quiet"], cwd=state_file.parent.parent, timeout=5,
                                       capture_output=True)
                self.data["uncommitted_code_possible"] = dirty.returncode != 0
            except (OSError, subprocess.TimeoutExpired):
                self.data["uncommitted_code_possible"] = True
        self.data["run_url"] = f"https://github.com/{repo}/actions/runs/{run}" if repo and run else None
        self.path = self.root / "attempts" / f"{self.data['attempt_id']}.json"
        self.save()

    def save(self) -> None:
        atomic_write_json(self.path, self.data)

    def record(self, event: str, **details: Any) -> None:
        if "message" in details:
            details["message"] = safe_message(details["message"])
        self.data["events"].append({"timestamp": utc_now(), "event": event, **details})
        self.save()

    def finish(self, outcome: str, **details: Any) -> None:
        self.data.update(outcome=outcome, finished_at=utc_now(), **details)
        self.save()
        render_attempt_log(self.root)


def render_attempt_log(root: Path) -> None:
    records = [load_json(path, {}) for path in sorted((root / "attempts").glob("*.json"))]
    records.sort(key=lambda item: (item.get("started_at", ""), item.get("attempt_id", "")))
    lines = ["# Episode attempt log", "", "Generated from `attempts/*.json`. Outcomes describe local processing; workflow validation is separate. Run links identify persistence/deployment outcomes. No historical backfill is implied.", ""]
    for item in records:
        episode = item.get("episode", {})
        label = f"{episode.get('source', '?')} {episode.get('number', '?')}"
        failures = [event for event in item.get("events", []) if event.get("event") == "failure"]
        reason = safe_message(failures[-1].get("message", "")) if failures else item.get("note", "")
        context = item.get("context", {})
        action = "forced rerun" if context.get("force") else "retry" if context.get("retry_failed") else "initial processing"
        if context.get("reuse_transcript"):
            action += "; retained transcript"
        events = item.get("events", [])
        if any(event.get("event") == "transcript_reused" for event in events) and not context.get("reuse_transcript"):
            action += "; automatically retained transcript"
        if any(event.get("event") == "chunk_split" for event in events):
            action += "; bounded chunk split"
        calls = sum(event.get("event") == "model_call" for event in events)
        reused = sum(event.get("event") == "checkpoint_reused" for event in events)
        line = f"- {item.get('started_at')} — {label}: **{item.get('outcome')}**; {action}; {item.get('pick_count', 0)} picks; {calls} observed model calls; {reused} checkpoints reused"
        if item.get("preserved_previous"):
            line += "; previous published result retained"
        if item.get("workflow_validation"):
            line += f"; archive validation={item['workflow_validation']}"
        if reason:
            line += "; " + reason[:240]
        if item.get("intervention"):
            line += "; note: " + item["intervention"][:240]
        line = line.replace("\n", " ").replace("\r", " ")
        line += f". [Details](attempts/{item['attempt_id']}.json)"
        if item.get("run_url"):
            line += f" · [Run]({item['run_url']})"
        lines.append(line)
    lines.extend(["", "## Workflow outcomes", ""])
    runs = [load_json(path, {}) for path in (root / "runs").glob("*.json")]
    for run in sorted(runs, key=lambda item: (item.get("timestamp", ""), item.get("run_id", ""))):
        selection = run.get("selection") or {}
        note = safe_message(run.get("note", "")).replace("\n", " ").replace("\r", " ")
        lines.append(f"- {run.get('timestamp')} — run {run.get('run_id')}/{run.get('run_attempt')}: preflight={run.get('preflight')}; pipeline={run.get('pipeline')}; exit={run.get('pipeline_exit_code')}; validation={run.get('validation')}; selected={selection.get('selected_count', 'see queue note')}; {note}. [Details](runs/{run.get('run_id')}-{run.get('run_attempt') or '1'}.json)")
    atomic_write_text(root / "episode-attempts.md", "\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    parser.add_argument("--validation", required=True)
    parser.add_argument("--preflight", default="unknown")
    parser.add_argument("--pipeline", default="unknown")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    run = os.getenv("GITHUB_RUN_ID")
    if run:
        atomic_write_json(args.state_dir / "runs" / f"{run}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}.json", {
            "schema_version": 1, "run_id": run, "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "timestamp": utc_now(), "workflow": os.getenv("GITHUB_WORKFLOW"), "git_sha": os.getenv("GITHUB_SHA"),
            "preflight": args.preflight, "pipeline": args.pipeline, "validation": args.validation,
            "pipeline_exit_code": os.getenv("PIPELINE_EXIT"),
            "selection": load_json(Path(os.environ["FFW_REPORT_PATH"]), {}) if os.getenv("FFW_REPORT_PATH") else None,
            "note": safe_message(args.note),
        })
    for path in (args.state_dir / "attempts").glob("*.json"):
        data = load_json(path, {})
        if run and data.get("run_id") == run and data.get("run_attempt") == os.getenv("GITHUB_RUN_ATTEMPT"):
            data["workflow_validation"] = args.validation
            data["publication_eligible"] = args.validation == "success"
            if data.get("outcome") == "running":
                data.update(outcome="interrupted", finished_at=utc_now())
            atomic_write_json(path, data)
    render_attempt_log(args.state_dir)


if __name__ == "__main__":
    main()
