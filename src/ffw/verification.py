from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .card_resolution import CardResolutionUnavailable, ScryfallCardResolver
from .models import EpisodeCandidate
from .production import _gemini_generate_json


VERIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "card", "explanation"],
    "properties": {
        "decision": {"type": "string", "enum": ["confirmed", "corrected", "ambiguous"]},
        "card": {"type": ["string", "null"]},
        "explanation": {"type": "string"},
    },
}


class GeminiPickVerifier:
    """Second-listen verifier for a small number of transcription-level card ambiguities."""

    def __init__(
        self,
        model_name: str,
        chunk_seconds: int,
        resolver: ScryfallCardResolver,
        *,
        max_picks: int = 2,
        clip_lead_seconds: int = 20,
        clip_duration_seconds: int = 55,
    ) -> None:
        self.model_name = model_name
        self.chunk_seconds = chunk_seconds
        self.resolver = resolver
        self.max_picks = max(0, max_picks)
        self.clip_lead_seconds = max(0, clip_lead_seconds)
        self.clip_duration_seconds = max(10, clip_duration_seconds)

    @staticmethod
    def _is_card_name_ambiguity(pick: dict[str, Any]) -> bool:
        if pick.get("review_status") == "approved":
            return False
        reason = str(pick.get("review_reason") or "").casefold()
        return any(token in reason for token in ("card name", "transcription", "likely refer", "may refer"))

    def _clip(self, source: Path, destination: Path, relative_seconds: float) -> Path:
        start = max(0.0, relative_seconds - self.clip_lead_seconds)
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-t", str(self.clip_duration_seconds),
            "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
            str(destination),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if completed.returncode or not destination.exists():
            raise RuntimeError(f"Focused verification clip failed: {completed.stderr[-300:]}")
        return destination

    def verify(
        self,
        episode: EpisodeCandidate,
        extraction: dict[str, Any],
        audio_files: list[Path],
    ) -> dict[str, Any]:
        if not audio_files or self.max_picks == 0:
            return extraction
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return extraction
        client = genai.Client(api_key=api_key)
        checked = 0
        accepted_count = 0
        for pick_index, pick in enumerate(extraction.get("recommendations", [])):
            if checked >= self.max_picks or not self._is_card_name_ambiguity(pick):
                continue
            checked += 1
            start_seconds = float(pick.get("start_seconds") or 0)
            chunk_index = min(max(int(start_seconds // self.chunk_seconds), 0), len(audio_files) - 1)
            relative_seconds = start_seconds - chunk_index * self.chunk_seconds
            clip_path = audio_files[chunk_index].parent / f"verify-{pick_index:02d}.mp3"
            original_name = str(pick.get("card") or "")
            suggestion = None
            try:
                initial_resolution = self.resolver.resolve(original_name)
                if initial_resolution.get("status") in {"verified", "suggested"}:
                    suggestion = initial_resolution.get("canonical_name")
                self._clip(audio_files[chunk_index], clip_path, relative_seconds)
                prompt = (
                    f"Listen to this short excerpt from {episode.source_name}, episode {episode.title!r}. "
                    f"The first extraction heard the Magic card name as {original_name!r}. "
                    f"A Scryfall spelling candidate is {suggestion!r}. "
                    "Identify only the exact card name audibly discussed. Do not infer a card from strategy context. "
                    "Return ambiguous when the audio does not clearly support an exact name."
                )
                result = _gemini_generate_json(
                    client,
                    types,
                    model=self.model_name,
                    contents=[prompt, types.Part.from_bytes(data=clip_path.read_bytes(), mime_type="audio/mpeg")],
                    schema=VERIFICATION_SCHEMA,
                )
                result.pop("_usage", None)
                verdict_name = str(result.get("card") or "").strip()
                verified_resolution = self.resolver.resolve(verdict_name) if verdict_name else None
                accepted = bool(
                    result.get("decision") in {"confirmed", "corrected"}
                    and verified_resolution
                    and verified_resolution.get("status") == "verified"
                    and verified_resolution.get("canonical_name")
                )
                pick["automated_verification"] = {
                    "method": "focused_audio_scryfall",
                    "model": self.model_name,
                    "original_card": original_name,
                    "candidate_card": verdict_name or None,
                    "decision": result.get("decision"),
                    "accepted": accepted,
                    "explanation": str(result.get("explanation") or "")[:500],
                }
                if accepted:
                    accepted_count += 1
                    pick["card"] = verified_resolution["canonical_name"]
                    pick["review_status"] = "approved"
                    pick["review_reason"] = None
            except (CardResolutionUnavailable, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                pick["automated_verification"] = {
                    "method": "focused_audio_scryfall",
                    "model": self.model_name,
                    "original_card": original_name,
                    "candidate_card": suggestion,
                    "decision": "unavailable",
                    "accepted": False,
                    "explanation": f"{type(exc).__name__}: {exc}"[:500],
                }
            finally:
                clip_path.unlink(missing_ok=True)
        overall_reason = str(extraction.get("review_reason") or "").casefold()
        if (
            accepted_count
            and extraction.get("recommendations")
            and all(pick.get("review_status") == "approved" for pick in extraction["recommendations"])
            and any(token in overall_reason for token in ("card", "transcription", "ambiguous"))
        ):
            extraction["review_reason"] = None
        return extraction