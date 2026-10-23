"""Detect dense speech compressed into an implausibly short chunk clock."""
from copy import deepcopy
import re


def clock_string_segments(payload: dict) -> dict:
    """Convert explicit clip-local MM:SS clocks without guessing numeric units."""
    result = deepcopy(payload)
    for segment in result.get("segments", []):
        for field in ("start", "end"):
            value = segment.get(field)
            match = re.fullmatch(r"(\d{1,2}):([0-5]\d)(?:\.(\d+))?", value) if isinstance(value, str) else None
            if not match:
                raise ValueError("Repair timestamp must be an explicit MM:SS or MM:SS.mmm clock.")
            minutes, seconds, fraction = match.groups()
            segment[field] = int(minutes) * 60 + int(seconds) + float("0." + (fraction or "0"))
    return result


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
        start = float(segment.get("start", 0))
        # Clamped tails belong to the preceding chunk. They are evidence of
        # damaged timing there, never coverage of the following audio chunk.
        if start > 0 and start % chunk_seconds == 0 and float(segment.get("end", start)) == start:
            continue
        groups.setdefault(int(start // chunk_seconds), []).append(segment)
    boundary_counts: dict[int, int] = {}
    for segment in transcript.get("segments", []):
        start = float(segment.get("start", 0))
        if start > 0 and start % chunk_seconds == 0 and float(segment.get("end", start)) == start:
            index = int(start // chunk_seconds) - 1
            boundary_counts[index] = boundary_counts.get(index, 0) + 1
    suspect = [index for index, count in boundary_counts.items() if count >= 5]
    # A successful JSON response can contain full text but omit timed segments.
    # Use the original audio chunk count rather than only inspecting groups
    # that happen to exist in the provider response.
    suspect.extend(index for index in range(int(transcript.get("chunk_count", 0)))
                   if not groups.get(index))
    for index, segments in groups.items():
        offset = index * chunk_seconds
        maximum = max(float(s.get("end", s.get("start", 0))) - offset for s in segments)
        words = sum(len(str(s.get("text", "")).split()) for s in segments)
        if len(segments) >= 20 and 0 < maximum <= chunk_seconds / 10 and words / maximum > 10:
            suspect.append(index)
        elif len(segments) >= 20 and sum(float(s.get("start", 0)) == offset + chunk_seconds for s in segments) >= 5:
            suspect.append(index)
    duration = transcript.get("duration_seconds")
    if duration and duration > 0:
        for segment in transcript.get("segments", []):
            start = float(segment.get("start", 0))
            end = float(segment.get("end", 0))
            if end > duration + 3:
                index = int(start // chunk_seconds)
                # A clamped tail at the boundary belongs to the preceding
                # audio chunk, never a nonexistent next chunk.
                if start > 0 and start % chunk_seconds == 0 and end == start:
                    index -= 1
                suspect.append(index)
    return sorted(set(suspect))


def align_published_quotes(picks: list[dict], transcript: dict) -> list[dict] | None:
    """Locate exact, unique source excerpts in newly audio-validated segments.

    No fuzzy name matching, clock scaling, or invented source evidence. Require
    every normalized quote fragment (explicit ellipses permit gaps), and abstain
    on repeated/short excerpts.
    """
    words, spans = [], []
    for segment in transcript.get("segments", []):
        tokens = re.findall(r"[a-z0-9]+", str(segment.get("text", "")).lower())
        words.extend(tokens)
        spans.extend([(segment["start"], segment["end"])] * len(tokens))
    result = deepcopy(picks)
    for pick in result:
        fragments = [re.findall(r"[a-z0-9]+", part.lower()) for part in
                     re.split(r"\.{3,}|\u2026", str(pick.get("evidence_excerpt", "")))]
        fragments = [part for part in fragments if part]
        if sum(map(len, fragments)) < 8 or any(len(part) < 3 for part in fragments):
            return None
        positions = []
        for quote in fragments:
            matches = [i for i in range(len(words) - len(quote) + 1) if words[i:i+len(quote)] == quote]
            if len(matches) != 1:
                return None
            positions.append((matches[0], matches[0] + len(quote) - 1))
        if any(positions[i][0] <= positions[i-1][1] for i in range(1, len(positions))):
            return None
        start, end = spans[positions[0][0]][0], spans[positions[-1][1]][1]
        if end < start or end - start > 180:
            return None
        pick.setdefault("identity_start_seconds", pick.get("start_seconds"))
        pick.update(start_seconds=int(start), end_seconds=int(end))
    return result


def unresolved_timing_chunks(transcript: dict, chunk_count: int) -> list[int]:
    """Locate outstanding corrections; legacy aggregate counts stay conservative.

    Repair history is append-only. Only the latest repair of a chunk establishes
    its current timing, and unrelated clean chunks do not need retranscription.
    """
    if "timing_adjustment_chunks" in transcript:
        pending = set(transcript["timing_adjustment_chunks"])
    else:
        pending = set(range(chunk_count)) if transcript.get("timing_adjustments") else set()
    latest = {r["chunk"] - 1: r for r in transcript.get("timing_repairs", [])}
    for index, repair in latest.items():
        if repair.get("validated_audio"):
            if repair.get("timing_adjustments"):
                pending.add(index)
            else:
                pending.discard(index)
    return sorted(pending)


def retain_exact_speakers(previous: list[dict], replacement: list[dict]) -> int:
    """Retain labels only for a unique unchanged utterance, never by timestamp."""
    def key(segment):
        return tuple(re.findall(r"[a-z0-9]+", str(segment.get("text", "")).casefold()))
    old = {}
    new = {}
    for segment in previous:
        old.setdefault(key(segment), []).append(segment)
    for segment in replacement:
        new.setdefault(key(segment), []).append(segment)
    retained = 0
    for quote, matches in new.items():
        originals = old.get(quote, [])
        if len(quote) < 8 or len(matches) != 1 or len(originals) != 1:
            continue
        if not matches[0].get("speaker") and originals[0].get("speaker"):
            matches[0]["speaker"] = originals[0]["speaker"]
            retained += 1
    return retained
