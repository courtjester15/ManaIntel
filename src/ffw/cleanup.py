"""Select a small, inspectable cleanup cohort; never infer approval from counts."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

from .utils import atomic_write_json, load_json


def select(root=Path("."), now=None):
    now = now or datetime.now(timezone.utc)
    records = load_json(root / "state/episodes.json", {}).get("episodes", {})
    ledger_path = root / "state/reprocess-queue.json"
    ledger = load_json(ledger_path, {"entries": []})
    from zoneinfo import ZoneInfo
    day = now.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
    capacity = load_json(root / "state/request-capacity.json", {}).get("days", {}).get(day, {})
    model = os.getenv("FFW_TRANSCRIPTION_MODEL", "gemini-3.5-flash-lite")
    bucket = capacity.get(model, {})
    optional_limit = int(os.getenv("FFW_REQUEST_DAILY_BUDGET", "48")) - int(os.getenv("FFW_PRIMARY_REQUEST_RESERVE", "16"))
    if bucket.get("requests", 0) >= optional_limit or bucket.get("daily_exhausted") or (
        bucket.get("blocked_until") and datetime.fromisoformat(bucket["blocked_until"]) > now
    ):
        return "", "shared request capacity unavailable"
    if ledger.get("daily_date") != day:
        ledger.update(daily_date=day, daily_runs=0)
    # Each episode gets one automatic cohort trial. Incomplete repairs are
    # allowed to resume only when the journal proves a new repaired chunk.
    candidates = []
    enabled = set(filter(None, os.getenv("FFW_CLEANUP_ISSUES", "").split(",")))
    for guid, record in records.items():
        pilot = ledger.get("inspected_pilots", {}).get(guid, {})
        inspected = pilot.get("status") in {"ready", "deferred"} and bool(pilot.get("evidence"))
        if record.get("source_id") not in {"mtg-fast-finance", "brainstorm-brewery"} or guid.startswith("ffw-synthetic-"):
            continue
        if not inspected and (record.get("status") != "needs_review" or record.get("error")):
            continue
        from .reviews import review_file_path
        if review_file_path(root / "data/reviews", record["source_id"], guid).exists():
            continue
        try:
            updated = datetime.fromisoformat(record["updated_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError):
            continue
        prior = [e for e in ledger.get("entries", []) if e.get("guid") == guid]
        last_error = record.get("last_attempt_error") or {}
        if last_error and not inspected and not (prior and prior[-1].get("status") == "deferred"):
            # A preserved publication can conceal a failed forced attempt.
            # Respect its intervention gate as well as the current error field.
            continue
        if prior:
            last = prior[-1]
            if len(prior) >= min(3, int(pilot.get("max_attempts", 3))) or last.get("status") != "deferred":
                continue
            if datetime.fromisoformat(last["finished_at"]) > now - timedelta(hours=6):
                continue
        elif not inspected and updated > now - timedelta(days=14):
            continue
        reason = str(record.get("review_reason", "")).lower()
        issue = "timing" if inspected or any(s in reason for s in ("timing", "timestamp", "coverage", "missing from timed")) else "boundary"
        if issue not in enabled:
            continue
        if issue == "boundary" and not any(s in reason for s in ("section", "boundary", "ending")):
            continue
        retained = (root / ".ffw-work/transcripts" / (Path(record.get("output_directory", "")).name + ".json.gz")).exists()
        candidates.append((-2 if inspected and pilot.get("repair_mode") == "coverage" and record.get("status") == "failed"
                           else -1 if inspected else 0 if retained else 1, updated, guid, record, issue))
    guid, reason = "", "no eligible validated repair cohort"
    if ledger.get("daily_runs", 0) >= 2:
        reason = "daily cleanup episode cap reached"
    elif candidates:
        _, _, guid, record, issue = min(candidates)
        pilot = ledger.get("inspected_pilots", {}).get(guid, {})
        inspected = bool(pilot.get("evidence")) and pilot.get("status") in {"ready", "deferred"}
        ledger.setdefault("entries", []).append({"guid": guid, "title": record.get("title"),
            "episode_number": record.get("episode_number"), "status": "running", "issue": issue,
            "inspected_pilot": inspected, "repair_mode": pilot.get("repair_mode", "review") if inspected else "review",
            "started_at": now.isoformat(), "before_status": record["status"], "before_pick_count": record.get("pick_count", 0)})
        if inspected:
            pilot["status"] = "running"
        ledger["daily_runs"] = ledger.get("daily_runs", 0) + 1
        reason = "inspected bounded pilot" if inspected else "older than fourteen days; bounded repair cohort"
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
    attempts = [a for a in attempts if a.get("episode", {}).get("guid") == guid and a.get("started_at")
                and datetime.fromisoformat(a["started_at"].replace("Z", "+00:00")) >= datetime.fromisoformat(entry["started_at"])]
    events = [e for a in attempts for e in a.get("events", [])]
    progress = sum(e.get("event") == "transcript_timing_repaired" for e in events)
    cleared = os.environ.get("OUTCOME") == "success" and state.get("status") == "complete"
    publication_recovered = entry.get("inspected_pilot") and entry.get("repair_mode") == "coverage" and (
        os.environ.get("OUTCOME") == "success" and state.get("status") in {"complete", "needs_review"} and state.get("pick_count", 0) > 0)
    saved_clips = sum(e.get("event") == "transcription_checkpoint_saved" for e in events)
    deferred = not cleared and (progress > 0 or saved_clips > 0) and any(
        e.get("event") == "timing_repair_incomplete" or (e.get("event") == "failure" and any(
            phrase in e.get("message", "").lower() for phrase in ("call budget exhausted", "shared capacity stop")))
        for e in events)
    limit = min(3, int(ledger.get("inspected_pilots", {}).get(guid, {}).get("max_attempts", 3)))
    if len([e for e in ledger["entries"] if e.get("guid") == guid]) >= limit:
        deferred = False
    entry.update(finished_at=now.isoformat(), result_status=state.get("status"),
        result_pick_count=state.get("pick_count", 0), repaired_chunks=progress, saved_clips=saved_clips,
        status="complete" if cleared or publication_recovered else "deferred" if deferred else "blocked",
        note="Review cleared" if cleared else "Publication recovered; remaining review is separate" if publication_recovered else "Saved new repair progress; bounded continuation" if deferred else "Inspect retained evidence before further automatic calls")
    if entry.get("inspected_pilot"):
        ledger["inspected_pilots"][guid]["status"] = entry["status"]
    atomic_write_json(path, ledger)
    return entry


def selected_mode(root=Path(".")):
    entries = load_json(root / "state/reprocess-queue.json", {}).get("entries", [])
    return entries[-1].get("repair_mode", "review") if entries else "review"


if __name__ == "__main__":
    guid, reason = select()
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"guid={guid}\nreason={reason}\n")
