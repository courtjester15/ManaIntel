from __future__ import annotations

import re
from typing import Any

START_PATTERNS = (
    r"cards?\s+to\s+watch",
    r"picks?\s+of\s+the\s+week",
    r"watch\s*list",
)
END_PATTERNS = (
    r"(that(?:'s| is) all|wrap(?:s|ping)? up).{0,40}(cards?|picks?)",
    r"(thanks for listening|until next week|patreon|listener questions)",
)

BRAINSTORM_START_PATTERNS = (
    r"breaking\s+bulk",
    r"bulk\s+to\s+binder",
    r"picks?\s+of\s+the\s+week",
)


def locate_cards_to_watch(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Locate the recurring section without performing recommendation extraction."""
    ordered = sorted(segments, key=lambda item: float(item.get("start", 0)))
    start_index = None
    for index, segment in enumerate(ordered):
        text = str(segment.get("text", ""))
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in START_PATTERNS):
            start_index = index
            break
    if start_index is None:
        return {
            "located": False,
            "start_seconds": None,
            "end_seconds": None,
            "label": "Cards to Watch",
            "confidence": "low",
            "review_reason": "No credible Cards to Watch section marker was found.",
            "segments": [],
        }
    end_index = len(ordered)
    explicit_end = False
    for index in range(start_index + 1, len(ordered)):
        text = str(ordered[index].get("text", ""))
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in END_PATTERNS):
            end_index = index + 1
            explicit_end = True
            break
    selected = ordered[start_index:end_index]
    return {
        "located": True,
        "start_seconds": int(float(selected[0].get("start", 0))),
        "end_seconds": int(float(selected[-1].get("end", selected[-1].get("start", 0)))),
        "label": "Cards to Watch",
        "confidence": "high" if explicit_end else "medium",
        "review_reason": None if explicit_end else "Section start found, but no explicit end marker was detected.",
        "segments": selected,
    }


def locate_recommendation_section(segments: list[dict[str, Any]], profile: str) -> dict[str, Any]:
    """Locate the source's explicit recommendation segment without extracting picks."""
    if profile != "brainstorm_brewery":
        return locate_cards_to_watch(segments)
    ordered = sorted(segments, key=lambda item: float(item.get("start", 0)))
    marker_indexes = [
        index for index, segment in enumerate(ordered)
        if any(re.search(pattern, str(segment.get("text", "")), re.IGNORECASE) for pattern in BRAINSTORM_START_PATTERNS)
    ]
    if not marker_indexes:
        return {
            "located": False, "start_seconds": None, "end_seconds": None,
            "label": "Breaking Bulk / Pick of the Week", "confidence": "low",
            "review_reason": "No credible Brainstorm Brewery recommendation segment marker was found.",
            "segments": [],
        }
    start_index = marker_indexes[0]
    start_seconds = float(ordered[start_index].get("start", 0))
    end_index = len(ordered)
    explicit_end = False
    for index in range(start_index + 1, len(ordered)):
        text = str(ordered[index].get("text", ""))
        elapsed = float(ordered[index].get("start", 0)) - start_seconds
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in END_PATTERNS) or elapsed > 1200:
            end_index = index + (1 if elapsed <= 1200 else 0)
            explicit_end = elapsed <= 1200
            break
    selected = ordered[start_index:end_index]
    return {
        "located": True,
        "start_seconds": int(float(selected[0].get("start", 0))),
        "end_seconds": int(float(selected[-1].get("end", selected[-1].get("start", 0)))),
        "label": "Breaking Bulk / Pick of the Week",
        "confidence": "high" if explicit_end else "medium",
        "review_reason": None if explicit_end else "Recommendation segment found without an explicit ending; review the bounded extraction.",
        "segments": selected,
    }
