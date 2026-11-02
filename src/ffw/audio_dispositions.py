"""Apply an inspected non-speech tail only to the exact source bytes reviewed."""
import hashlib
import math
import subprocess
from pathlib import Path

from .utils import load_json


def apply_non_speech_tail(root, episode, source, prepared, transcript, chunk_seconds):
    # Retained/model-supplied claims never authorize their own coverage exception.
    transcript.pop("source_bound_non_speech_chunks", None)
    transcript.pop("audio_dispositions", None)
    key = hashlib.sha256(episode.guid.encode()).hexdigest()[:24]
    record = load_json(Path(root) / "data/audio-dispositions" / f"{key}.json")
    if not record:
        return None
    index = record.get("chunk_index")
    if (record.get("episode_guid") != episode.guid or record.get("audio_url") != episode.audio_url
            or type(index) is not int or index != len(prepared) - 1 or index < 1
            or record.get("method") != "inspected_local_asr_and_vad_v1"
            or not record.get("evidence_note") or not record.get("inspected_at")):
        raise ValueError("Invalid inspected non-speech tail disposition.")
    if hashlib.sha256(Path(source).read_bytes()).hexdigest() != record.get("source_sha256"):
        raise ValueError("Non-speech disposition source hash mismatch; inspect changed audio.")
    start = index * chunk_seconds
    if any((float(s.get("start", 0)) >= start or float(s.get("end", 0)) > start)
           and str(s.get("text", "")).strip()
           for s in transcript.get("segments", [])):
        raise ValueError("Non-speech disposition conflicts with retained timed speech.")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", str(prepared[index])],
        capture_output=True, text=True, timeout=30,
    )
    duration = float(probe.stdout.strip()) if not probe.returncode else float("nan")
    end = record.get("end_seconds")
    if (not isinstance(end, (float, int)) or isinstance(end, bool)
            or not math.isfinite(end)
            or not math.isfinite(duration) or duration <= 0
            or record.get("start_seconds") != start or abs(start + duration - end) > 1
            or not episode.duration_seconds or abs(end - episode.duration_seconds) > 3):
        raise ValueError("Non-speech disposition does not match the physical final chunk.")
    transcript["source_bound_non_speech_chunks"] = [index]
    transcript["audio_dispositions"] = [record]
    return record
