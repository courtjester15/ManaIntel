"""Detect dense speech compressed into an implausibly short chunk clock."""
from copy import deepcopy
import re


def missing_recommendation_content(transcript: dict) -> int:
    """Flag recommendation windows lost between full text and timed segments.

    This is a conservative review signal, never a source of invented timestamps.
    Keep the original full text as recovery evidence rather than replacing it.
    """
    from .detection import PICK_CUE_PATTERNS
    text = str(transcript.get("text", ""))
    timed_words = set(re.findall(r"[a-z0-9]+", " ".join(
        str(segment.get("text", "")) for segment in transcript.get("segments", [])
    ).lower()))
    missing = 0
    for match in re.finditer("|".join(PICK_CUE_PATTERNS), text, re.IGNORECASE):
        words = re.findall(r"[a-z0-9]+", text[match.start():].lower())[:100]
        distinctive = {word for word in words if len(word) >= 4}
        if len(distinctive) >= 10 and len(distinctive & timed_words) / len(distinctive) < .7:
            missing += 1
    return missing


def normalize_integer_clock(payload: dict, duration: int) -> dict:
    """Repair MMSS only when the entire dense chunk proves that encoding."""
    segments = payload.get("segments", [])
    values = [float(s.get(field, s.get("start", 0))) for s in segments for field in ("start", "end")]
    if len(segments) < 20 or not values or max(values) <= duration:
        return payload
    if any(v < 0 or not v.is_integer() or int(v) % 100 >= 60 for v in values):
        return payload
    converted = [int(v) // 100 * 60 + int(v) % 100 for v in values]
    if not duration * .7 <= max(converted) <= duration:
        return payload
    result = deepcopy(payload)
    for i, segment in enumerate(result["segments"]):
        segment.update(start=converted[2 * i], end=converted[2 * i + 1])
    result["clock_encoding_repaired"] = "MMSS"
    return result


def suspect_timing_chunks(transcript: dict, chunk_seconds: int = 900) -> list[int]:
    groups: dict[int, list[dict]] = {}
    for segment in transcript.get("segments", []):
        groups.setdefault(int(float(segment.get("start", 0)) // chunk_seconds), []).append(segment)
    boundary_counts: dict[int, int] = {}
    for segment in transcript.get("segments", []):
        start = float(segment.get("start", 0))
        if start > 0 and start % chunk_seconds == 0 and float(segment.get("end", start)) == start:
            index = int(start // chunk_seconds) - 1
            boundary_counts[index] = boundary_counts.get(index, 0) + 1
    suspect = [index for index, count in boundary_counts.items() if count >= 5]
    for index, segments in groups.items():
        offset = index * chunk_seconds
        maximum = max(float(s.get("end", s.get("start", 0))) - offset for s in segments)
        words = sum(len(str(s.get("text", "")).split()) for s in segments)
        if len(segments) >= 20 and 0 < maximum <= chunk_seconds / 10 and words / maximum > 10:
            suspect.append(index)
        elif len(segments) >= 20 and sum(float(s.get("start", 0)) == offset + chunk_seconds for s in segments) >= 5:
            suspect.append(index)
    return sorted(set(suspect))
