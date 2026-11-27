"""Manual, bounded source/quality experiment. Never publishes episode output."""
import argparse
from contextlib import contextmanager
from dataclasses import fields, replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

from ffw.models import EpisodeCandidate, utc_now
from ffw.production import GeminiExtractor, GeminiTranscriber
from ffw.utils import atomic_write_json, load_json
from ffw.audit import safe_message
from ffw.capacity import reserve
from ffw.extraction_quality import assess_extraction_quality, QUALITY_INSTRUCTIONS


@contextmanager
def request_cap(limit):
    """Include SDK/schema/split recovery calls in the aggregate experiment cap."""
    from ffw import capacity
    original = capacity.reserve
    reserved = []
    def bounded(model, *args, **kwargs):
        if not kwargs.get("check_only"):
            if len(reserved) >= limit:
                raise capacity.CapacityStopped("Evaluation aggregate call cap reached")
            ticket = original(model, *args, **kwargs)
            reserved.append(model)
            return ticket
        return original(model, *args, **kwargs)
    capacity.reserve = bounded
    try:
        yield reserved
    finally:
        capacity.reserve = original

MODELS = ("gemini-3.5-flash-lite", "gemini-3.6-flash")
FF = "mtg-fast-finance"
BB = "brainstorm-brewery"
SOURCE_CLIPS = ((FF, 539, 1360, 225), (FF, 504, 1350, 450),
                (BB, 678, 1350, 450), (FF, 507, 720, 225))
INDEPENDENT_CLIPS = ((FF, 538, 1495, 95), (BB, 678, 3040, 390),
                     (FF, 539, 890, 490), (BB, 651, 1510, 240))
CASES = (("mtg-fast-finance", 539), ("mtg-fast-finance", 537),
         ("brainstorm-brewery", 667), ("mtg-fast-finance", 538))
CANDIDATE_INSTRUCTIONS = QUALITY_INSTRUCTIONS


def candidate(episode):
    allowed = {f.name for f in fields(EpisodeCandidate)}
    return EpisodeCandidate(**{k: v for k, v in episode.items() if k in allowed})


class CandidateExtractor(GeminiExtractor):
    def _generate(self, client, types, contents):
        return super()._generate(client, types, [contents[0] + CANDIDATE_INSTRUCTIONS, *contents[1:]])

    def extract(self, episode, transcript):
        return assess_extraction_quality(episode, transcript, super().extract(episode, transcript))


def retained(root, source, number):
    matches = []
    for path in root.rglob("*.json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            record = json.load(stream)
        e = record.get("episode", {})
        if e.get("source_id") == source and e.get("episode_number") == number:
            matches.append(record)
    if len(matches) != 1:
        raise ValueError(f"Expected one retained transcript for {source}/{number}; found {len(matches)}")
    return matches[0]


def source_clip(asr, model_name, episode, output, start, duration):
    import numpy as np

    number = episode["episode_number"]
    audio = output.parent / f"clip-{number}.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
        "-i", episode["audio_url"], "-t", str(duration), "-vn", "-ac", "1", "-ar", "16000",
        "-b:a", "32k", str(audio)], check=True, timeout=180)
    # Pass PCM directly to avoid PyAV decoder version coupling.
    pcm = subprocess.check_output(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(audio),
        "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"], timeout=90)
    samples = np.frombuffer(pcm, dtype="<f4")
    if samples.size == 0:
        raise ValueError(f"Episode {number} returned an empty source window")
    segments, info = asr.transcribe(samples, beam_size=5, vad_filter=True)
    atomic_write_json(output / f"source-{number}-independent.json", {
        "model": f"faster-whisper/{model_name}",
        "episode": number, "episode_guid": episode["guid"], "source_id": episode["source_id"],
        "clip_start": start, "clip_duration": duration, "decoded_duration": samples.size / 16000,
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in segments],
        "language_probability": info.language_probability,
    })
    return audio


def independent(output):
    """Read fixed source windows without accessing credentials or durable state."""
    from faster_whisper import WhisperModel

    output.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("small.en", device="cpu", compute_type="int8", download_root=".ffw-work/asr-models")
    episodes = load_json(Path("archive/index.json"))["episodes"]
    for source, number, start, duration in INDEPENDENT_CLIPS:
        episode = next(e for e in episodes if e.get("episode_number") == number and e.get("source_id") == source)
        source_clip(model, "small.en", episode, output, start, duration)


def run(phase, root, output):
    output.mkdir(parents=True, exist_ok=True)
    journal = {"kind": "bounded_quality_evaluation", "phase": phase, "started_at": utc_now(),
               "run_id": os.getenv("GITHUB_RUN_ID", "local"), "calls": [], "results": [],
               "notice": "Machine source checks and scoped comparisons; not human approval or full-episode certification."}
    cap = 8 if phase == "source" else 10
    def observe(event, **details):
        if event == "model_call":
            journal["calls"].append({k: details.get(k) for k in
                ("model", "outcome", "request_seconds", "finish_reason")})
    def save():
        journal["finished_at"] = utc_now()
        atomic_write_json(output / "journal.json", journal)
        atomic_write_json(Path("state/quality-runs") / f"{journal['run_id']}.json", journal)
    try:
        # Hard stop independent of model-specific daily capacity buckets.
        def before(model):
            if len(journal["calls"]) >= cap:
                raise RuntimeError("Evaluation aggregate call cap reached")
            reserve(model, check_only=True)
        if phase == "source":
            from faster_whisper import WhisperModel
            asr = WhisperModel("tiny.en", device="cpu", compute_type="int8", download_root=".ffw-work/asr-models")
            index = load_json(Path("archive/index.json"))
            clips = []
            for source, number, start, duration in SOURCE_CLIPS:
                ep = next(e for e in index["episodes"] if e.get("episode_number") == number and e.get("source_id") == source)
                audio = source_clip(asr, "tiny.en", ep, output, start, duration)
                clips.append((number, start, duration, replace(candidate(ep), duration_seconds=duration), audio))
            for model in MODELS:
                for number, start, duration, ep, audio in clips:
                    try:
                        before(model)
                        transcriber = GeminiTranscriber(model, duration, transient_retries=0,
                                                        request_timeout_seconds=180)
                        transcriber.audit_callback = observe
                        result = transcriber.transcribe(ep, [audio])
                        atomic_write_json(output / f"source-{number}-{model}.json", result)
                        journal["results"].append({"episode": number, "model": model, "kind": "source_clip",
                            "clip_start": start, "clip_duration": duration, "outcome": "response"})
                    except Exception as exc:
                        journal["results"].append({"episode": number, "model": model, "kind": "source_clip",
                                                  "outcome": "stopped", "error": safe_message(exc)})
                        break  # No repeated probe of an unavailable model in this run.
        else:
            for model in MODELS:
                cases = CASES
                stop = False
                for source, number in cases:
                    record = retained(root, source, number)
                    ep = candidate(record["episode"])
                    policies = (("baseline", GeminiExtractor), ("candidate", CandidateExtractor)) if number == 539 else (("candidate", CandidateExtractor),)
                    for policy, cls in policies:
                        try:
                            before(model)
                            extractor = cls(model, transient_retries=0, request_timeout_seconds=180, quality_policy=False)
                            extractor.audit_callback = observe
                            result = extractor.extract(ep, record["transcript"])
                            atomic_write_json(output / f"extract-{number}-{model}-{policy}.json", {
                                "episode": record["episode"], "recommendations": result["recommendations"],
                                "section": result["section"], "review_reason": result.get("review_reason")})
                            journal["results"].append({"episode": number, "model": model, "policy": policy,
                                "outcome": "response", "pick_count": len(result["recommendations"])})
                        except Exception as exc:
                            journal["results"].append({"episode": number, "model": model, "policy": policy,
                                                      "outcome": "stopped", "error": safe_message(exc)})
                            stop = True
                            break
                    if stop:
                        break
        journal["status"] = "finished"
    except Exception as exc:
        journal.update(status="failed", error=safe_message(exc))
        raise
    finally:
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("source", "extraction", "independent"), required=True)
    parser.add_argument("--retained", type=Path, default=Path(".ffw-work/quality-retained"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase == "independent":
        independent(args.output or Path(".ffw-work/quality-independent/reports"))
    else:
        with request_cap(8 if args.phase == "source" else 10):
            run(args.phase, args.retained, args.output or Path(".ffw-work/quality/reports"))
