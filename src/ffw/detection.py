from __future__ import annotations

import re
from typing import Any

START_PATTERNS = (
    r"cards?\s+to\s+watch",
    r"picks?\s+of\s+the\s+week",
    r"watch\s*list",
)
SECTION_END_PATTERNS = (
    r"(that(?:'s| is) all|wrap(?:s|ping)? up).{0,40}(cards?|picks?)",
)
EPISODE_END_PATTERNS = (
    r"(thanks for listening|until next week|patreon|listener questions)",
)
END_PATTERNS = SECTION_END_PATTERNS + EPISODE_END_PATTERNS

# MTG Fast Finance commonly names Cards to Watch while previewing the whole show.
# That outline mention is not a reliable section boundary by itself.
OUTLINE_PATTERNS = (
    r"\b(?:today|this week|on (?:today'?s|this) (?:show|episode)|coming up)\b.{0,500}\bcards?\s+to\s+watch\b",
    r"\b(?:including|we(?:'ll| will)|going to)\b.{0,500}\bcards?\s+to\s+watch\b.{0,300}\b(?:and|plus|before)\b",
    r"\b(?:meta|price) updates?\b.{0,500}\bcards?\s+to\s+watch\b",
    r"\b(?:agenda|usual\s+(?:three|four|five|\d+)\s+segments?|have a lot going on|we(?:'ve| have) got to talk)\b.{0,700}\bcards?\s+to\s+watch\b",
    r"\b(?:first|then|finally)\b.{0,700}\bcards?\s+to\s+watch\b.{0,300}\b(?:and then|then|finally|after|wrap)\b",
)
PICK_CUE_PATTERNS = (
    r"\bmy\s+(?:(?:first|second|next|other|last)\s+)?(?:card|pick)\b",
    r"\b(?:first|second|next|other|last)\s+(?:card|pick)(?:\s+this week)?\b",
    r"\b(?:my|our|the)\s+pick\s+(?:this week|is)\b",
    r"\bwhat\s+(?:do|have)\s+you\s+(?:have|got)(?:\s+this week)?\b",
    r"\b(?:let(?:'s| us)|time to)\s+(?:get into|do|talk about)\s+(?:our\s+)?(?:cards?|picks?)\b",
    r"\bi(?:'m| am)\s+(?:going|gonna)\s+with\b",
)
TOPIC_TRANSITION_PATTERNS = (
    r"\b(?:move|moving)\s+on\s+to\b",
    r"\b(?:main|weekly|featured?)\s+(?:topic|discussion|segment)\b",
    r"\b(?:time to|we(?:'re| are) going to)\b.{0,60}\b(?:discuss|talk|break down|dive|get into)\b",
)

BRAINSTORM_START_PATTERNS = (
    r"breaking\s+bulk",
    r"bulk\s+to\s+binder",
    r"picks?\s+of\s+the\s+week",
)
BRAINSTORM_OUTLINE_PATTERNS = (
    r"\b(?:today|this week|on (?:today'?s|this) (?:show|episode)|coming up|later(?:\s+in\s+the\s+show)?)\b.{0,500}\b(?:breaking\s+bulk|bulk\s+to\s+binder|picks?\s+of\s+the\s+week)\b",
    r"\b(?:we(?:'ll| will)|going to|before|after)\b.{0,500}\b(?:breaking\s+bulk|bulk\s+to\s+binder|picks?\s+of\s+the\s+week)\b.{0,300}\b(?:and|plus|before|after|then)\b",
    r"\b(?:agenda|first|then|finally|segments?|show)\b.{0,700}\b(?:breaking\s+bulk|bulk\s+to\s+binder|picks?\s+of\s+the\s+week)\b.{0,300}\b(?:and|then|finally|after|wrap)\b",
)
BRAINSTORM_PICK_CUE_PATTERNS = PICK_CUE_PATTERNS + (
    r"\bmy\s+(?:breaking\s+bulk|bulk\s+pick)\b",
    r"\bfor\s+(?:my|our)\s+(?:breaking\s+bulk|pick\s+of\s+the\s+week)\b",
    r"\b(?:breaking\s+bulk|pick\s+of\s+the\s+week)\s+(?:is|has to be|goes to)\b",
)

MIN_TOPIC_TRANSITION_SECONDS = 120
MAX_UNBOUNDED_SECTION_SECONDS = 1200
OUTLINE_CONTEXT_SECONDS = 120
TOPIC_STOPWORDS = {
    "and", "best", "card", "cards", "episode", "ep", "fast", "finance", "for", "from",
    "got", "magic", "main", "more", "mtg", "much", "of", "on", "results", "set", "the",
    "their", "this", "top", "with", "x", "action", "down", "how", "look", "low", "out",
    "played", "take",
}


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _window_text(segments: list[dict[str, Any]], index: int, width: int = 3) -> str:
    return " ".join(str(item.get("text", "")) for item in segments[index:index + width])


def _is_outline_mention(
    segments: list[dict[str, Any]], index: int, *, patterns: tuple[str, ...] = OUTLINE_PATTERNS,
) -> bool:
    segment_text = str(segments[index].get("text", ""))
    if _matches(patterns, segment_text):
        return True
    candidate_start = float(segments[index].get("start", 0))
    context = " ".join(
        str(item.get("text", ""))
        for item in segments[max(0, index - 2):index + 3]
        if abs(float(item.get("start", 0)) - candidate_start) <= OUTLINE_CONTEXT_SECONDS
    )
    return _matches(patterns, context)


def _ordered_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer provider sequence over timestamps when every segment supplies it."""
    if segments and all(item.get("sequence") is not None for item in segments):
        return sorted(segments, key=lambda item: int(item["sequence"]))
    return sorted(segments, key=lambda item: float(item.get("start", 0)))


def _has_duration(segment: dict[str, Any]) -> bool:
    return float(segment.get("end", segment.get("start", 0))) > float(segment.get("start", 0))


def _best_explicit_start(explicit_indexes: list[int], implicit_indexes: list[int]) -> int:
    """Choose the explicit marker most closely followed by recommendation language."""
    ranked: list[tuple[int, int]] = []
    for explicit_index in explicit_indexes:
        following = [index for index in implicit_indexes if index >= explicit_index]
        if following:
            ranked.append((following[0] - explicit_index, explicit_index))
    if ranked:
        return min(ranked)[1]
    return explicit_indexes[0]


def _topic_terms(title: str, description: str) -> set[str]:
    title_topic = title.split(":", 1)[-1] if ":" in title else title
    description_topic = ""
    match = re.search(r"cards?\s+to\s+watch\s+and\s+(.+?)(?:\.|$)", description, re.IGNORECASE)
    if match:
        description_topic = match.group(1)
    words = re.findall(r"[a-z0-9]{3,}", f"{title_topic} {description_topic}".lower())
    return {word for word in words if word not in TOPIC_STOPWORDS and not word.isdigit()}


def _topic_transition_index(
    ordered: list[dict[str, Any]], start_index: int, *, title: str, description: str,
    first_pick_index: int | None = None,
) -> int | None:
    terms = _topic_terms(title, description)
    start_seconds = float(ordered[start_index].get("start", 0))
    for index in range(start_index + 1, len(ordered)):
        if first_pick_index is None or index <= first_pick_index:
            continue
        elapsed = float(ordered[index].get("start", 0)) - start_seconds
        if elapsed < MIN_TOPIC_TRANSITION_SECONDS:
            continue
        transition_text = str(ordered[index].get("text", ""))
        if not _has_duration(ordered[index]) and ordered[index].get("sequence") is None:
            continue
        transition_match = next(
            (
                match
                for pattern in TOPIC_TRANSITION_PATTERNS
                if (match := re.search(pattern, transition_text, re.IGNORECASE))
            ),
            None,
        )
        if transition_match is None:
            continue
        next_text = str(ordered[index + 1].get("text", "")) if index + 1 < len(ordered) else ""
        context = f"{transition_text[transition_match.start():transition_match.end() + 200]} {next_text[:200]}"
        lowered = context.lower()
        # A strong generic label is sufficient. Otherwise require the transition
        # to agree with the advertised feature topic from the title/show notes.
        generic_label = re.search(
            r"\b(?:main|weekly|featured?)\s+(?:topic|discussion|segment)\b",
            transition_text, re.IGNORECASE,
        )
        if generic_label or any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms):
            return index
    return None


def locate_cards_to_watch(
    segments: list[dict[str, Any]], *, title: str = "", description: str = "",
) -> dict[str, Any]:
    """Locate the recommendation block using independent start and end evidence."""
    ordered = _ordered_segments(segments)
    outline_indexes: list[int] = []
    explicit_indexes: list[int] = []
    implicit_indexes: list[int] = []
    for index, segment in enumerate(ordered):
        text = str(segment.get("text", ""))
        if _matches(START_PATTERNS, text):
            if _is_outline_mention(ordered, index):
                outline_indexes.append(index)
            else:
                explicit_indexes.append(index)
        if _matches(PICK_CUE_PATTERNS, text) and not _is_outline_mention(ordered, index):
            implicit_indexes.append(index)

    if explicit_indexes:
        start_index = _best_explicit_start(explicit_indexes, implicit_indexes)
        start_signal = "explicit_section_marker"
    elif implicit_indexes:
        start_index = implicit_indexes[0]
        start_signal = "recommendation_language"
    elif outline_indexes:
        # Preserve the broad extraction fallback, but do not approve it as a
        # trustworthy boundary. The model can still recover useful picks.
        start_index = outline_indexes[0]
        start_signal = "show_outline_fallback"
    else:
        return {
            "located": False,
            "start_seconds": None,
            "end_seconds": None,
            "label": "Cards to Watch",
            "confidence": "low",
            "review_reason": "No credible Cards to Watch marker or recommendation-language cluster was found.",
            "start_signal": None,
            "end_signal": None,
            "segments": [],
        }

    explicit_end_index: int | None = None
    for index in range(start_index + 1, len(ordered)):
        if _matches(SECTION_END_PATTERNS, str(ordered[index].get("text", ""))):
            explicit_end_index = index
            break
    first_pick_index = next((index for index in implicit_indexes if index >= start_index), None)
    topic_index = _topic_transition_index(
        ordered, start_index, title=title, description=description,
        first_pick_index=first_pick_index,
    )
    if topic_index is not None and (explicit_end_index is None or topic_index < explicit_end_index):
        end_index = topic_index
        end_signal: str | None = "advertised_topic_transition"
    elif explicit_end_index is not None:
        end_index = explicit_end_index + 1
        end_signal = "explicit_section_end"
    else:
        end_index = len(ordered)
        start_seconds = float(ordered[start_index].get("start", 0))
        for index in range(start_index + 1, len(ordered)):
            if float(ordered[index].get("start", 0)) - start_seconds > MAX_UNBOUNDED_SECTION_SECONDS:
                end_index = index
                break
        end_signal = None

    selected = ordered[start_index:end_index]
    strong_start = start_signal != "show_outline_fallback"
    bounded = end_signal is not None
    if not strong_start:
        review_reason = "Only the early show-outline mention of Cards to Watch was found; verify where the recommendation block begins."
    elif not bounded:
        review_reason = "Recommendation block start found, but no explicit ending or advertised weekly-topic transition was detected."
    else:
        review_reason = None
    confidence = "high" if start_signal == "explicit_section_marker" and bounded else (
        "medium" if strong_start else "low"
    )
    return {
        "located": True,
        "start_seconds": int(float(selected[0].get("start", 0))),
        "end_seconds": int(float(selected[-1].get("end", selected[-1].get("start", 0)))),
        "label": "Cards to Watch",
        "confidence": confidence,
        "review_reason": review_reason,
        "start_signal": start_signal,
        "end_signal": end_signal,
        "segments": selected,
    }


def locate_recommendation_section(
    segments: list[dict[str, Any]], profile: str, *, title: str = "", description: str = "",
) -> dict[str, Any]:
    """Locate a source's recommendation segment without extracting picks."""
    if profile != "brainstorm_brewery":
        return locate_cards_to_watch(segments, title=title, description=description)
    ordered = _ordered_segments(segments)
    outline_indexes: list[int] = []
    explicit_indexes: list[int] = []
    implicit_indexes: list[int] = []
    for index, segment in enumerate(ordered):
        text = str(segment.get("text", ""))
        has_pick_cue = _matches(BRAINSTORM_PICK_CUE_PATTERNS, text)
        is_outline = _is_outline_mention(ordered, index, patterns=BRAINSTORM_OUTLINE_PATTERNS)
        if _matches(BRAINSTORM_START_PATTERNS, text):
            if is_outline and not has_pick_cue:
                outline_indexes.append(index)
            else:
                explicit_indexes.append(index)
        if has_pick_cue:
            implicit_indexes.append(index)

    if explicit_indexes:
        # Brainstorm may contain both Breaking Bulk and Pick of the Week with a
        # long topic discussion between them. Preserve the first credible
        # section instead of collapsing to the marker closest to the last pick.
        start_index = explicit_indexes[0]
        start_signal = "explicit_section_marker"
    elif implicit_indexes:
        start_index = implicit_indexes[0]
        start_signal = "recommendation_language"
    elif outline_indexes:
        start_index = outline_indexes[0]
        start_signal = "show_outline_fallback"
    else:
        return {
            "located": False, "start_seconds": None, "end_seconds": None,
            "label": "Breaking Bulk / Pick of the Week", "confidence": "low",
            "review_reason": "No credible Brainstorm Brewery recommendation segment marker was found.",
            "start_signal": None, "end_signal": None,
            "segments": [],
        }

    start_seconds = float(ordered[start_index].get("start", 0))
    end_index = len(ordered)
    end_signal: str | None = None
    recommendation_indexes = [
        index for index in explicit_indexes + implicit_indexes if index >= start_index
    ]
    last_recommendation_index = max(recommendation_indexes, default=start_index)
    cap_anchor_seconds = float(ordered[last_recommendation_index].get("start", start_seconds))
    for index in range(start_index + 1, len(ordered)):
        text = str(ordered[index].get("text", ""))
        segment_start = float(ordered[index].get("start", 0))
        if index > last_recommendation_index and _matches(END_PATTERNS, text):
            end_index = index + 1
            end_signal = "explicit_section_end"
            break
        if segment_start - cap_anchor_seconds > MAX_UNBOUNDED_SECTION_SECONDS:
            end_index = index
            break
    selected = ordered[start_index:end_index]
    strong_start = start_signal != "show_outline_fallback"
    if not strong_start:
        review_reason = "Only a show-outline mention of the Brainstorm Brewery recommendation segment was found; verify where the picks begin."
    elif end_signal is None:
        review_reason = "Recommendation segment found without an explicit ending; review the bounded extraction."
    else:
        review_reason = None
    confidence = "high" if start_signal == "explicit_section_marker" and end_signal else (
        "medium" if strong_start else "low"
    )
    return {
        "located": True,
        "start_seconds": int(float(selected[0].get("start", 0))),
        "end_seconds": int(float(selected[-1].get("end", selected[-1].get("start", 0)))),
        "label": "Breaking Bulk / Pick of the Week",
        "confidence": confidence,
        "review_reason": review_reason,
        "start_signal": start_signal,
        "end_signal": end_signal,
        "segments": selected,
    }
