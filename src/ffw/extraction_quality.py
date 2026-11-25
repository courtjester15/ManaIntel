"""Conservative checks on supplied source evidence, not completeness certification."""
import re
from .detection import FF_OPENING_CUE_PATTERNS, FF_CONTINUATION_MARKER


def recommendation_anchors(episode, transcript, section):
    if episode.extraction_profile != "cards_to_watch" or not section.get("located"):
        return []
    start, end = section.get("start_seconds"), section.get("end_seconds")
    if start is None or end is None:
        return []
    anchors = []
    for segment in transcript.get("segments", []):
        stamp = float(segment.get("start", 0))
        text = str(segment.get("text", ""))
        if start <= stamp <= end and any(re.search(p, text, re.I) for p in (*FF_OPENING_CUE_PATTERNS, FF_CONTINUATION_MARKER)):
            if not anchors or stamp - anchors[-1] >= 60:
                anchors.append(stamp)
    return anchors


def assess_extraction_quality(episode, transcript, extraction):
    """Abstain on unsupported attribution; flag unrepresented strong handoffs."""
    segments = transcript.get("segments", [])
    for pick in extraction.get("recommendations", []):
        proposed = pick.get("hosts") or []
        if not proposed:
            continue
        start = pick.get("start_seconds")
        if start is None:
            continue  # Publication validation handles missing clocks.
        end = pick.get("end_seconds") or start + 60
        local = [s for s in segments if start - 30 <= float(s.get("start", 0)) <= end]
        quote = " ".join(re.findall(r"\w+", str(pick.get("evidence_excerpt") or "").casefold()))
        def recommendation_speech(segment):
            text = str(segment.get("text", ""))
            normalized = " ".join(re.findall(r"\w+", text.casefold()))
            exact_quote = len(quote.split()) >= 4 and quote in normalized
            opening = start - 3 <= float(segment.get("start", 0)) <= start + 15 and re.search(
                r"\bmy\s+(?:(?:first|other|final|next)\s+)?(?:pick|card)\b|\bi(?:'m| am)\s+(?:going|gonna)\s+with\b", text, re.I)
            return exact_quote or opening
        labels = {str(s.get("speaker") or "").casefold().strip() for s in local
                  if recommendation_speech(s)
                  and not re.fullmatch(r"speaker\s*\d+", str(s.get("speaker") or ""), re.I)}
        accepted = []
        for host in proposed:
            # An exact named handoff immediately before a pick can establish
            # attribution. A show introduction or alternating numbered voices cannot.
            handoff = any(start - 30 <= float(s.get("start", 0)) <= start
                and re.search(r"\b" + re.escape(host) + r"\s*[,;:]\s*(?:what|tell|give)\b.{0,60}\b(?:pick|card|selection)\b", str(s.get("text", "")), re.I)
                for s in local)
            if str(host).casefold().strip() in labels or handoff:
                accepted.append(host)
        if accepted != proposed:
            pick["hosts"] = accepted
            pick["attribution_check"] = {"method": "named_source_evidence", "proposed_hosts": proposed,
                                         "accepted_hosts": accepted, "unresolved": True}
    anchors = recommendation_anchors(episode, transcript, extraction.get("section", {}))
    missing = []
    for index, anchor in enumerate(anchors):
        stop = min(anchor + 180, anchors[index + 1] - 20 if index + 1 < len(anchors) else anchor + 180)
        if not any(p.get("start_seconds") is not None and anchor - 20 <= p["start_seconds"] <= stop
                   for p in extraction.get("recommendations", [])):
            missing.append(int(anchor))
    if missing:
        reason = "Recommendation handoff has no corresponding extracted pick near " + ", ".join(map(str, missing)) + " seconds; verify section coverage."
        extraction["review_reason"] = " ".join(filter(None, [extraction.get("review_reason"), reason]))
        extraction["coverage_check"] = {"method": "strong_handoff_inventory", "unrepresented_seconds": missing}
    return extraction
