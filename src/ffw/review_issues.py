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


def review_triage(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    """Read-only navigation hints from effective evidence, never an approval."""
    if not summary:
        return None
    processing = summary.get("processing", {})
    if processing.get("human_review") or processing.get("status") not in {"complete", "needs_review"}:
        return None
    picks = summary.get("recommendations", [])
    issues = collect_review_issues({
        "review_reason": processing.get("review_reason"),
        "section": summary.get("section", {}), "recommendations": picks,
    }, summary.get("episode", {}).get("duration_seconds"))
    if not picks:
        issues.append({"code": "coverage", "path": "extraction", "state": "unresolved",
                       "reason": "No published picks; verify whether recommendations were missed."})
    if not issues and processing.get("status") == "needs_review":
        issues.append({"code": "unspecified", "path": "extraction", "state": "unresolved",
                       "reason": "Episode needs review without a recorded reason."})
    if not issues:
        return None
    # Lower ranks are inspected first. Unknown prose is visible, never cleared.
    ranks = {"coverage": 0, "timing": 0, "intent": 1, "scope": 1, "identity": 2, "printing": 2}
    unique = {}
    for issue in issues:
        item = dict(issue)
        if item["path"].startswith("recommendations/"):
            pick = picks[int(item["path"].split("/")[1])]
            item.update(pick_id=pick.get("id"), card=pick.get("card"), start_seconds=pick.get("start_seconds"))
        unique[(item["code"], item["path"], item["reason"])] = item
    codes = sorted({item["code"] for item in unique.values()}, key=lambda code: (ranks.get(code, 3), code))
    return {"priority": min(ranks.get(code, 3) for code in codes), "codes": codes,
            "issues": list(unique.values())}


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
                   and (old.get("foil") is None or p.get("foil") == old["foil"])
                   and (not old.get("hosts") or {h.casefold() for h in p.get("hosts", [])} == {h.casefold() for h in old["hosts"]})]
        if not matches:
            return True
        remaining.remove(matches[0])
    return False
