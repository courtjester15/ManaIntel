"""Select a small, inspectable cleanup cohort; never infer approval from counts."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os

from .utils import atomic_write_json, load_json


def select(root=Path("."), now=None):
    now = now or datetime.now(timezone.utc)
    records = load_json(root / "state/episodes.json", {}).get("episodes", {})
    ledger_path = root / "state/reprocess-queue.json"
    ledger = load_json(ledger_path, {"entries": []})
    from zoneinfo import ZoneInfo
    day = now.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
    if ledger.get("daily_date") != day:
        ledger.update(daily_date=day, daily_runs=0)
    # Each episode gets one automatic cohort trial. Incomplete repairs are
    # allowed to resume only when the journal proves a new repaired chunk.
    candidates = []
    enabled = set(filter(None, os.getenv("FFW_CLEANUP_ISSUES", "").split(",")))
    for guid, record in records.items():
        if record.get("source_id") not in {"mtg-fast-finance", "brainstorm-brewery"} or guid.startswith("ffw-synthetic-"):
            continue
        if record.get("status") != "needs_review" or record.get("error"):
            continue
        try:
            updated = datetime.fromisoformat(record["updated_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError):
            continue
        prior = [e for e in ledger.get("entries", []) if e.get("guid") == guid]
        if prior:
            last = prior[-1]
            if len(prior) >= 3 or last.get("status") != "deferred":
                continue
            if datetime.fromisoformat(last["finished_at"]) > now - timedelta(hours=6):
                continue
        elif updated > now - timedelta(days=14):
            continue
        reason = str(record.get("review_reason", "")).lower()
        issue = "timing" if any(s in reason for s in ("timing", "timestamp", "coverage", "missing from timed")) else "boundary"
        if issue not in enabled:
            continue
        if issue == "boundary" and not any(s in reason for s in ("section", "boundary", "ending")):
            continue
        candidates.append((updated, guid, record, issue))
    guid, reason = "", "no eligible validated repair cohort"
    if ledger.get("daily_runs", 0) >= 2:
        reason = "daily cleanup episode cap reached"
    elif candidates:
        _, guid, record, issue = min(candidates)
        ledger.setdefault("entries", []).append({"guid": guid, "title": record.get("title"),
            "episode_number": record.get("episode_number"), "status": "running", "issue": issue,
            "started_at": now.isoformat(), "before_status": record["status"], "before_pick_count": record.get("pick_count", 0)})
        ledger["daily_runs"] = ledger.get("daily_runs", 0) + 1
        reason = "older than fourteen days; pilot-validated repair cohort"
    atomic_write_json(ledger_path, ledger)
    return guid, reason


def record(root=Path("."), now=None):
    now = now or datetime.now(timezone.utc)
    path = root / "state/reprocess-queue.json"
    ledger = load_json(path, {})
    guid = os.environ["GUID"]
    entry = next(e for e in reversed(ledger["entries"]) if e["guid"] == guid and e["status"] == "running")
    state = load_json(root / "state/episodes.json", {})["episodes"][guid]
    attempts = [load_json(p, {}) for p in (root / "state/attempts").glob("*.json")]
    attempts = [a for a in attempts if a.get("episode", {}).get("guid") == guid and a.get("started_at", "") >= entry["started_at"]]
    events = [e for a in attempts for e in a.get("events", [])]
    progress = sum(e.get("event") == "transcript_timing_repaired" for e in events)
    cleared = os.environ.get("OUTCOME") == "success" and state.get("status") == "complete"
    deferred = not cleared and progress > 0 and any(
        e.get("event") == "timing_repair_incomplete" for e in events)
    entry.update(finished_at=now.isoformat(), result_status=state.get("status"),
        result_pick_count=state.get("pick_count", 0), repaired_chunks=progress,
        status="complete" if cleared else "deferred" if deferred else "blocked",
        note="Review cleared" if cleared else "Saved new repair progress; bounded continuation" if deferred else "Inspect retained evidence before further automatic calls")
    atomic_write_json(path, ledger)


if __name__ == "__main__":
    guid, reason = select()
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"guid={guid}\nreason={reason}\n")
