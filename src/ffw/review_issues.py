"""Conservative review issue classification; a resolved name is not a resolved episode."""
from __future__ import annotations

import re
from typing import Any

_PATTERNS = {
    "coverage": r"section|segment|ending|boundary|completeness|omitted|retained|zero picks|fewer than|missing\s+(?:chunks?|recommendation|content|coverage)",
    "timing": r"timestamp|timing|clock|cluster|audio bound",
    "printing": r"printing|foil|version|price point|price target",
    "intent": r"disagree|debate|ambiguous recommendation|recommendation intent|direct endorsement|skeptic|risk|whether to buy|unsupported recommendation",
    "scope": r"non-magic|non-mtg|another game|joke|april fools|tcg|slay the spire",
    "identity": r"card name|transcription|misheard|likely refer|may refer|not a known|not standard|database entries",
}


def reason_codes(reason: str) -> list[str]:
    """Keep mixed reasons mixed; unknown prose never becomes automatic approval."""
    return [code for code, pattern in _PATTERNS.items() if re.search(pattern, reason, re.I)] or ["unspecified"]


def name_only_reason(reason: str | None) -> bool:
    return bool(reason) and reason_codes(reason) == ["identity"]


def resolve_verified_name(pick: dict[str, Any], canonical_name: str) -> None:
    original_reason = pick.get("review_reason")
    pick["card"] = canonical_name
    if name_only_reason(original_reason):
        pick["review_status"] = "approved"
        pick["review_reason"] = None
    # Mixed/unknown reasons stay reviewable even after audible identity resolves.
    pick["name_verification_resolution"] = {
        "method": "focused_audio_scryfall", "original_review_reason": original_reason,
        "identity_resolved": True, "other_review_required": pick.get("review_status") != "approved",
    }


def collect_review_issues(extraction: dict[str, Any], duration_seconds: float | None = None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def add(path: str, reason: str, codes: list[str] | None = None) -> None:
        for code in codes or reason_codes(reason):
            issues.append({"code": code, "path": path, "reason": reason, "state": "unresolved"})

    for path, reason in (("extraction", extraction.get("review_reason")),
                         ("section", extraction.get("section", {}).get("review_reason"))):
        if reason:
            add(path, str(reason))
    section = extraction.get("section", {})
    for index, pick in enumerate(extraction.get("recommendations", [])):
        path = f"recommendations/{index}"
        if pick.get("review_status") != "approved":
            add(path, str(pick.get("review_reason") or "Unresolved pick without a recorded reason."))
        start, end = pick.get("start_seconds"), pick.get("end_seconds")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            if start < 0 or end < start or (duration_seconds and end > duration_seconds):
                add(path, "Pick timestamps fall outside the stated audio bounds; verify audio duration and alignment.", ["timing"])
        if isinstance(start, (int, float)) and section.get("start_seconds") is not None and section.get("end_seconds") is not None:
            if not section["start_seconds"] <= start <= section["end_seconds"]:
                add(path, "Pick starts outside the selected recommendation section; verify coverage and alignment.", ["coverage", "timing"])
    return issues


def published_version_regression(baseline: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Do not replace a known published variant with a different/unknown one.

    A deliberate correction belongs in an evidence-backed override. Case-only
    spelling differences are harmless; each candidate can account for one pick.
    """
    remaining = list(candidate.get("recommendations", []))
    previous = sorted(baseline.get("recommendations", []),
                      key=lambda p: (bool(p.get("printing")), p.get("foil") is not None), reverse=True)
    for old in previous:
        same_card = [p for p in remaining if str(p.get("card", "")).strip().casefold() == str(old.get("card", "")).strip().casefold()]
        matches = [p for p in same_card
                   if (not old.get("printing") or str(p.get("printing") or "").strip().casefold() == str(old["printing"]).strip().casefold())
                   and (old.get("foil") is None or p.get("foil") == old["foil"])]
        if not matches:
            return True
        remaining.remove(matches[0])
    return False
