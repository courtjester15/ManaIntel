"""Opt-in, bounded audio recovery of missing attribution on published picks."""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import re
import subprocess

from .capacity import reserve
from .config import PIPELINE_VERSION
from .models import utc_now
from .production import _gemini_generate_json
from .utils import atomic_write_json, load_json

HOST_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["participants", "picks"],
    "properties": {
        "participants": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["name", "anchor_quote"],
            "properties": {"name": {"type": "string"}, "anchor_quote": {"type": "string"}}}},
        "picks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["pick_id", "host", "decision", "quote", "explanation"],
            "properties": {
                "pick_id": {"type": "string"}, "host": {"type": ["string", "null"]},
                "decision": {"type": "string", "enum": ["confirmed", "ambiguous"]},
                "quote": {"type": "string"}, "explanation": {"type": "string"}}}},
    },
}


def words(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def quote_supported(quote, text, minimum=6):
    normalized = words(quote)
    return minimum <= len(normalized.split()) <= 30 and len(re.findall(r"(?<![a-z0-9])" + re.escape(normalized) + r"(?![a-z0-9])", words(text))) == 1


def pick_context(pick, segments):
    start, end = pick.get("start_seconds"), pick.get("end_seconds")
    if start is None:
        return ""
    return " ".join(s.get("text", "") for s in segments
                    if start - 40 <= float(s.get("start", 0)) <= (end or start) + 90)


def agreed_hosts(summary, transcript, readings, model):
    """Fill empty hosts only; every accepted assignment needs two grounded readings."""
    result = deepcopy(summary)
    if len(readings) != 2:
        raise ValueError("Host recovery requires exactly two audio readings")
    segments = transcript.get("segments", [])
    intro = " ".join(s.get("text", "") for s in segments if float(s.get("start", 0)) < 150)
    participants = []
    indexed = []
    for reading in readings:
        anchors = {}
        for participant in reading.get("participants", []):
            name = str(participant.get("name") or "").strip()
            quote = participant.get("anchor_quote", "")
            if len(name.split()) == 1 and words(name) in words(quote).split() and quote_supported(quote, intro, 3):
                anchors.setdefault(name.casefold(), []).append(participant)
        participants.append({name: values[0] for name, values in anchors.items() if len(values) == 1})
        records = {}
        for record in reading.get("picks", []):
            records.setdefault(record.get("pick_id"), []).append(record)
        indexed.append(records)
    accepted = []
    for pick in result["recommendations"]:
        if pick.get("hosts"):
            continue
        pair = [records.get(pick["id"], []) for records in indexed]
        if any(len(records) != 1 for records in pair):
            continue
        first, second = [records[0] for records in pair]
        host = str(first.get("host") or "").strip()
        key = host.casefold()
        if not host or key != str(second.get("host") or "").strip().casefold():
            continue
        context = pick_context(pick, segments)
        if not all(key in anchors for anchors in participants):
            continue
        if not all(record.get("decision") == "confirmed" and len(str(record.get("explanation") or "")) >= 20
                   and quote_supported(record.get("quote"), context) for record in (first, second)):
            continue
        pick["hosts"] = [participants[0][key]["name"].strip()]
        pick["host_attribution"] = {
            "method": "introduction_and_section_audio_two_readings", "model": model,
            "recovered_at": utc_now(), "audio_confirmed": True,
            "anchor_quote": participants[0][key]["anchor_quote"],
            "recommendation_quote": first["quote"],
            "confirmation_quote": second["quote"],
        }
        accepted.append(pick["id"])
    return result, accepted


def audio_clip(source: Path, destination: Path, start: float, duration: float):
    if start < 0 or not 0 < duration <= 960:
        raise ValueError("Metadata recovery clip exceeds its bounded audio scope")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
               "-t", str(duration), "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(destination)]
    process = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if process.returncode or not destination.exists():
        raise RuntimeError("Metadata audio clip preparation failed: " + process.stderr[-300:])
    return destination


def recover_hosts(episode, summary, transcript_path, source, work_dir, report_path, model, observer):
    if not transcript_path.exists():
        raise ValueError("Host recovery requires the existing retained transcript")
    with gzip.open(transcript_path, "rt", encoding="utf-8") as handle:
        retained = json.load(handle)
    if retained.get("episode", {}).get("guid") != episode.guid or retained.get("episode", {}).get("audio_url") != episode.audio_url:
        raise ValueError("Retained host-recovery evidence does not match the exact source episode")
    transcript = retained["transcript"]
    from .transcript_timing import suspect_timing_chunks, unresolved_timing_chunks
    if suspect_timing_chunks(transcript) or unresolved_timing_chunks(transcript, transcript.get("chunk_count", 1)):
        raise ValueError("Repair transcript timing before recovering host attribution")
    section = summary["section"]
    if not section.get("located") or section.get("start_seconds") is None or section.get("end_seconds") is None:
        raise ValueError("Host recovery requires an established recommendation section")
    start = max(0, section["start_seconds"] - 25)
    stop = min(episode.duration_seconds or section["end_seconds"] + 25, section["end_seconds"] + 25)
    if not 0 < stop - start <= 960 or len(summary["recommendations"]) > 8:
        raise ValueError("Host recovery exceeds the one-section audio/pick bound")
    reserve(model, check_only=True, minimum_requests=2)
    intro = audio_clip(source, work_dir / "host-introduction.mp3", 0, min(150, episode.duration_seconds or 150))
    discussion = audio_clip(source, work_dir / "host-discussion.mp3", start, stop - start)
    from google import genai
    from google.genai import types
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required for audio host recovery")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=300000, retry_options={"attempts": 1}))
    context = {
        "intro_transcript": [s for s in transcript["segments"] if float(s.get("start", 0)) < 150],
        "picks": [{"pick_id": p["id"], "card": p["card"], "start_seconds": p["start_seconds"],
                   "context": pick_context(p, transcript["segments"])} for p in summary["recommendations"] if not p.get("hosts")],
    }
    prompt = (
        "Identify the ORIGINATING RECOMMENDER for each existing pick by listening to BOTH audio clips. "
        "The first clip is the episode introduction at absolute 0 seconds. The second clip is the continuous "
        f"recommendation discussion at absolute {start} seconds. The supplied transcript uses absolute times. "
        "Use the intro's self-identification and named handoffs to anchor voices, then follow those same voices "
        "in the discussion. A co-host agreeing or discussing a pick is not its originator. Never infer alternating "
        "pick order, assign every host, or use old transcript speaker labels as proof. They may be missing or wrong. "
        "Return first names ONLY for hosts identified in the audio. For each participant, anchor_quote must be "
        "3 to 30 exact words from intro_transcript containing their name. For each pick, quote must be 6 to 30 "
        "exact words from that pick's supplied context, audibly spoken by the originating recommender. "
        "Explain the voice linkage and handoff in explanation. Return ambiguous and null host if either "
        "voice identity or recommendation ownership is unclear. Do not add picks or change any card/printing/timing."
    )
    readings = []
    for index in range(2):
        instruction = prompt + (" Independently identify ownership without assuming the listed order indicates the speaker."
                                if index == 0 else " Audit recommendation ownership carefully; distinguish the speaker who chose the card from the co-host commenting on it.")
        reading = _gemini_generate_json(client, types, model=model,
            contents=[instruction, json.dumps(context, ensure_ascii=False), "INTRODUCTION AUDIO", types.Part.from_bytes(data=intro.read_bytes(), mime_type="audio/mpeg"),
                      "RECOMMENDATION DISCUSSION AUDIO", types.Part.from_bytes(data=discussion.read_bytes(), mime_type="audio/mpeg")],
            schema=HOST_SCHEMA, observer=observer, allow_schema_fallback=False)
        readings.append(reading)
        atomic_write_json(report_path, {"episode_guid": episode.guid, "method": "audio_host_recovery_v1", "readings": readings})
    result, accepted = agreed_hosts(summary, transcript, readings, model)
    observer("host_recovery_checked", accepted_pick_ids=accepted, missing_remaining=sum(not p.get("hosts") for p in result["recommendations"]),
             method="introduction_and_section_audio_two_readings")
    if accepted:
        result["processing"]["metadata_recovery"] = {"pipeline_version": PIPELINE_VERSION, "method": "audio_host_recovery_v1",
            "recovered_at": utc_now(), "accepted_pick_ids": accepted, "model": model}
    return result, accepted
