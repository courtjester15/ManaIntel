from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import utc_now
from .utils import atomic_write_json, load_json, seconds_to_timestamp, stable_pick_id

REVIEW_SCHEMA_VERSION = "1.0.0"
REVIEW_ACTIONS = {"exclude", "update", "add"}
EDITABLE_PICK_FIELDS = {
    "card",
    "printing",
    "hosts",
    "recommendation",
    "start_seconds",
    "end_seconds",
    "evidence_excerpt",
}


def review_file_path(reviews_dir: Path, source_id: str, episode_guid: str) -> Path:
    digest = hashlib.sha256(episode_guid.encode("utf-8")).hexdigest()[:16]
    return reviews_dir / source_id / f"{digest}.json"


def review_expectation(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "processed_at": summary.get("processing", {}).get("processed_at"),
        "pick_ids": [pick.get("id") for pick in summary.get("recommendations", [])],
    }


def _source_id(summary: dict[str, Any]) -> str:
    return summary.get("episode", {}).get("source_id") or "mtg-fast-finance"


def _parse_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return deepcopy(payload)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Review payload is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Review payload must be a JSON object.")
    return parsed


def _require_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Review pick field {field!r} is required.")
    return text


def _normalize_seconds(value: Any, field: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"Review pick field {field!r} must be seconds.")
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Review pick field {field!r} must be seconds.") from exc
    if seconds < 0:
        raise ValueError(f"Review pick field {field!r} cannot be negative.")
    return seconds


def _normalize_hosts(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Review pick field 'hosts' must be a list.")
    hosts = [str(host).strip() for host in value if str(host).strip()]
    if not hosts:
        raise ValueError("Review pick field 'hosts' requires at least one speaker.")
    return hosts


def _normalize_changes(changes: Any) -> dict[str, Any]:
    if not isinstance(changes, dict) or not changes:
        raise ValueError("An update operation requires non-empty changes.")
    unexpected = set(changes) - EDITABLE_PICK_FIELDS
    if unexpected:
        raise ValueError(f"Unsupported review changes: {sorted(unexpected)}")
    normalized = deepcopy(changes)
    if "card" in normalized:
        normalized["card"] = _require_text(normalized["card"], "card")
    if "printing" in normalized:
        normalized["printing"] = str(normalized["printing"]).strip() or None
    if "hosts" in normalized:
        normalized["hosts"] = _normalize_hosts(normalized["hosts"])
    if "recommendation" in normalized:
        normalized["recommendation"] = _require_text(normalized["recommendation"], "recommendation")
    if "evidence_excerpt" in normalized:
        normalized["evidence_excerpt"] = _require_text(normalized["evidence_excerpt"], "evidence_excerpt")
    for field in ("start_seconds", "end_seconds"):
        if field in normalized:
            normalized[field] = _normalize_seconds(normalized[field], field)
    return normalized


def _new_pick(summary: dict[str, Any], values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("An add operation requires a pick object.")
    unexpected = set(values) - EDITABLE_PICK_FIELDS
    if unexpected:
        raise ValueError(f"Unsupported added-pick fields: {sorted(unexpected)}")
    episode = summary["episode"]
    start_seconds = _normalize_seconds(values.get("start_seconds"), "start_seconds")
    if start_seconds is None:
        raise ValueError("An added pick requires start_seconds.")
    end_seconds = _normalize_seconds(values.get("end_seconds"), "end_seconds")
    card = _require_text(values.get("card"), "card")
    printing = str(values.get("printing") or "").strip() or None
    hosts = _normalize_hosts(values.get("hosts"))
    recommendation = _require_text(values.get("recommendation"), "recommendation")
    evidence = _require_text(values.get("evidence_excerpt"), "evidence_excerpt")
    return {
        "id": stable_pick_id(episode["guid"], card, start_seconds, printing),
        "card": card,
        "printing": printing,
        "printing_certainty": None,
        "foil": None,
        "hosts": hosts,
        "recommendation": recommendation,
        "mentioned_price": None,
        "entry_target": None,
        "hold": None,
        "exit_target": None,
        "reasoning": [],
        "caveats": [],
        "confidence": None,
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "timestamp": seconds_to_timestamp(start_seconds),
        "evidence_excerpt": evidence,
        "review_status": "approved",
        "review_reason": None,
        "listen_url": f"{episode['audio_url']}#t={start_seconds}",
    }


def normalize_review(
    summary: dict[str, Any],
    payload: str | dict[str, Any],
    *,
    actor: str,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    review = _parse_payload(payload)
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise ValueError(f"Review schema_version must be {REVIEW_SCHEMA_VERSION}.")
    episode = summary["episode"]
    source_id = _source_id(summary)
    if review.get("episode_guid") != episode["guid"]:
        raise ValueError("Review episode_guid does not match the selected episode.")
    if review.get("source_id") != source_id:
        raise ValueError("Review source_id does not match the selected episode.")
    if review.get("decision") != "approve":
        raise ValueError("Review decision must be 'approve'.")
    if review.get("expected") != review_expectation(summary):
        raise ValueError("Review payload is stale because the extracted episode changed.")

    existing_ids = {pick["id"] for pick in summary.get("recommendations", [])}
    targeted: set[str] = set()
    operations: list[dict[str, Any]] = []
    for operation in review.get("operations", []):
        if not isinstance(operation, dict) or operation.get("action") not in REVIEW_ACTIONS:
            raise ValueError("Each review operation needs a supported action.")
        action = operation["action"]
        if action == "add":
            pick = _new_pick(summary, operation.get("pick"))
            operations.append({"action": "add", "pick": {
                field: pick[field] for field in EDITABLE_PICK_FIELDS
            }})
            continue
        pick_id = operation.get("pick_id")
        if pick_id not in existing_ids:
            raise ValueError(f"Review operation targets unknown pick_id: {pick_id}")
        if pick_id in targeted:
            raise ValueError(f"Review payload targets pick_id more than once: {pick_id}")
        targeted.add(pick_id)
        if action == "exclude":
            operations.append({"action": "exclude", "pick_id": pick_id})
        else:
            operations.append({
                "action": "update",
                "pick_id": pick_id,
                "changes": _normalize_changes(operation.get("changes")),
            })

    note = str(review.get("note") or "").strip() or None
    reviewer = str(actor or "").strip()
    if not reviewer:
        raise ValueError("A review actor is required.")
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "source_id": source_id,
        "episode_guid": episode["guid"],
        "expected": review_expectation(summary),
        "decision": "approve",
        "note": note,
        "operations": operations,
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at or utc_now(),
    }


def apply_review(summary: dict[str, Any], review: dict[str, Any] | None) -> dict[str, Any]:
    effective = deepcopy(summary)
    if not review:
        return effective
    if review.get("expected") != review_expectation(summary):
        raise ValueError("Stored review is stale because the extracted episode changed.")
    if review.get("episode_guid") != summary.get("episode", {}).get("guid"):
        raise ValueError("Stored review targets a different episode.")

    picks = {pick["id"]: deepcopy(pick) for pick in summary.get("recommendations", [])}
    order = [pick["id"] for pick in summary.get("recommendations", [])]
    for operation in review.get("operations", []):
        action = operation["action"]
        if action == "exclude":
            picks.pop(operation["pick_id"], None)
            order = [pick_id for pick_id in order if pick_id != operation["pick_id"]]
        elif action == "update":
            original_id = operation["pick_id"]
            pick = picks.pop(original_id)
            pick.update(deepcopy(operation["changes"]))
            pick["id"] = stable_pick_id(
                summary["episode"]["guid"],
                pick["card"],
                pick.get("start_seconds"),
                pick.get("printing"),
            )
            pick["timestamp"] = seconds_to_timestamp(pick.get("start_seconds"))
            pick["listen_url"] = (
                f"{summary['episode']['audio_url']}#t={pick['start_seconds']}"
                if pick.get("start_seconds") is not None else summary["episode"]["audio_url"]
            )
            if pick["id"] in picks:
                raise ValueError(f"Review update creates a duplicate pick: {pick['card']}")
            picks[pick["id"]] = pick
            order = [pick["id"] if pick_id == original_id else pick_id for pick_id in order]
        elif action == "add":
            pick = _new_pick(summary, operation["pick"])
            if pick["id"] in picks:
                raise ValueError(f"Review adds a duplicate pick: {pick['card']}")
            picks[pick["id"]] = pick
            order.append(pick["id"])

    effective_picks = [picks[pick_id] for pick_id in order]
    for pick in effective_picks:
        pick["review_status"] = "approved"
        pick["review_reason"] = None
    effective["recommendations"] = effective_picks
    processing = effective["processing"]
    processing["original_status"] = processing.get("status")
    processing["original_processed_at"] = processing.get("processed_at")
    processing["status"] = "complete"
    processing["review_state"] = "approved"
    processing["review_reason"] = None
    processing["processed_at"] = review["reviewed_at"]
    processing["human_review"] = {
        "reviewed_by": review["reviewed_by"],
        "reviewed_at": review["reviewed_at"],
        "note": review.get("note"),
        "operation_count": len(review.get("operations", [])),
    }
    return effective


def load_episode_review(
    reviews_dir: Path | None,
    summary: dict[str, Any],
) -> dict[str, Any] | None:
    if reviews_dir is None:
        return None
    path = review_file_path(reviews_dir, _source_id(summary), summary["episode"]["guid"])
    review = load_json(path)
    return review or None


def find_episode_summary(archive_dir: Path, episode_guid: str) -> tuple[Path, dict[str, Any]]:
    for summary_path in (archive_dir / "episodes").glob("*/summary.json"):
        summary = load_json(summary_path)
        if summary and summary.get("episode", {}).get("guid") == episode_guid:
            return summary_path, summary
    raise ValueError(f"No published episode matches GUID: {episode_guid}")


def persist_review(
    archive_dir: Path,
    reviews_dir: Path,
    payload: str | dict[str, Any],
    *,
    actor: str,
    reviewed_at: str | None = None,
) -> Path:
    parsed = _parse_payload(payload)
    episode_guid = str(parsed.get("episode_guid") or "")
    _, summary = find_episode_summary(archive_dir, episode_guid)
    review = normalize_review(summary, parsed, actor=actor, reviewed_at=reviewed_at)
    path = review_file_path(reviews_dir, review["source_id"], review["episode_guid"])
    atomic_write_json(path, review)
    return path
