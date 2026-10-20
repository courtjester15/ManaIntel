"""Conservative local request budgets, not a provider remaining-quota meter.

Production writers share a GitHub concurrency group. Reserve before sending so
failed responses count too. A runner crash can lose uncommitted reservations.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import os

from .utils import atomic_write_json, load_json


class CapacityStopped(RuntimeError):
    pass


def nightly_window_open(now):
    if os.getenv("FFW_NIGHTLY_WINDOW", "").lower() != "true":
        return True
    eastern = now.astimezone(ZoneInfo("America/New_York"))
    return eastern.hour in (23, 0, 1, 2) and not (eastern.hour == 2 and eastern.minute >= 50)


def reserve(model: str, now=None):
    configured = os.getenv("FFW_CAPACITY_PATH")
    if not configured:
        return None
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
    path = Path(configured)
    ledger = load_json(path, {"schema_version": 1, "days": {}})
    models = ledger["days"].setdefault(day, {})
    if model not in models:
        # Bootstrap from retained observations, including calls made earlier on
        # the rollout day. Subsequent reservations are the authoritative count.
        count, daily_exhausted = 0, False
        for attempt in (path.parent / "attempts").glob("*.json"):
            for event in load_json(attempt, {}).get("events", []):
                if event.get("event") != "model_call" or event.get("model") != model:
                    continue
                stamp = event.get("timestamp")
                if not stamp or datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat() != day:
                    continue
                count += 1
                message = event.get("message", "").lower()
                daily_exhausted |= any(s in message for s in ("requestsperday", "per_day", "daily quota"))
        models[model] = {"requests": count, "daily_exhausted": daily_exhausted}
    bucket = models[model]
    optional = os.getenv("FFW_OPTIONAL_WORK", "").lower() == "true"
    if optional and not nightly_window_open(now):
        raise CapacityStopped("Shared capacity stop: outside nightly cleanup window.")
    limit = int(os.getenv("FFW_REQUEST_DAILY_BUDGET", "48"))
    reserve_count = int(os.getenv("FFW_PRIMARY_REQUEST_RESERVE", "16")) if optional else 0
    if limit <= 0 or reserve_count < 0:
        raise ValueError("Invalid request budget configuration")
    until = bucket.get("blocked_until")
    if bucket.get("daily_exhausted") or (until and datetime.fromisoformat(until) > now):
        raise CapacityStopped("Shared capacity stop: provider limit observed; no further requests permitted.")
    if bucket["requests"] >= max(0, limit - reserve_count):
        raise CapacityStopped("Shared capacity stop: configured request budget reached.")
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    run = bucket.setdefault("runs", {}).setdefault(run_id, {"requests": 0})
    if optional and run["requests"] >= int(os.getenv("FFW_OPTIONAL_RUN_REQUEST_BUDGET", "16")):
        raise CapacityStopped("Shared capacity stop: optional run request budget reached.")
    bucket["requests"] += 1
    run["requests"] += 1
    atomic_write_json(path, ledger)
    return path, day, model


def record_failure(ticket, exc, now=None):
    if ticket is None:
        return
    path, day, model = ticket
    ledger = load_json(path, {})
    bucket = ledger["days"][day][model]
    text = str(exc).lower()
    # A generic 429 can mean minute-level pressure. Do not call it daily
    # exhaustion without evidence; still stop all workflows for a cooldown.
    if any(word in text for word in ("requestsperday", "per_day", "per day", "daily quota")) and any(
        word in text for word in ("429", "exhausted", "quota")
    ):
        bucket["daily_exhausted"] = True
    elif any(word in text for word in ("429", "resource_exhausted", "503", "unavailable")):
        bucket["blocked_until"] = ((now or datetime.now(timezone.utc)) + timedelta(minutes=30)).isoformat()
    atomic_write_json(path, ledger)
