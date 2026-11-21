"""Bounded eligibility renewal for explicit provider outages, never counter resets."""
from datetime import datetime, timedelta
import re


def renew_provider_outage(error, last_attempt_at, *, attempt=None, maximum=None):
    if not error:
        return error
    result = dict(error)
    attempt = result.get("attempt", 0) if attempt is None else attempt
    maximum = result.get("max_attempts", 3) if maximum is None else maximum
    message = str(result.get("message", "")).lower()
    if (result.get("synthetic") or result.get("category") != "transient_provider"
            or any(s in message for s in ("manual review", "quota", "429", "401", "403", "404"))
            or not re.search(r"\b(?:500|502|503|504)\b|timed out|timeout|connection reset|peer closed", message)
            or not isinstance(attempt, int) or not isinstance(maximum, int)
            or maximum < 1 or attempt < maximum):
        return result
    try:
        stamp = datetime.fromisoformat(str(last_attempt_at).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return result
    except ValueError:
        return result
    hours = 48 if attempt < maximum + 3 else 168
    result.update(retryable=True, quarantined=False, recovery_mode="periodic_provider",
                  recovery_interval_hours=hours, attempt=attempt, max_attempts=maximum,
                  next_retry_at=(stamp + timedelta(hours=hours)).isoformat(timespec="seconds").replace("+00:00", "Z"))
    return result
