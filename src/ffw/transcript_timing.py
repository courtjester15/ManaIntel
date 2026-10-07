"""Detect dense speech compressed into an implausibly short chunk clock."""


def suspect_timing_chunks(transcript: dict, chunk_seconds: int = 900) -> list[int]:
    groups: dict[int, list[dict]] = {}
    for segment in transcript.get("segments", []):
        groups.setdefault(int(float(segment.get("start", 0)) // chunk_seconds), []).append(segment)
    suspect = []
    for index, segments in groups.items():
        offset = index * chunk_seconds
        maximum = max(float(s.get("end", s.get("start", 0))) - offset for s in segments)
        words = sum(len(str(s.get("text", "")).split()) for s in segments)
        if len(segments) >= 20 and 0 < maximum <= chunk_seconds / 10 and words / maximum > 10:
            suspect.append(index)
    return suspect
