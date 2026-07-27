from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.4.0"
PIPELINE_VERSION = "0.4.0"
SCHEMA_VERSION = "1.1.0"
PROMPT_VERSION = "source-recommendations-v1"
MOCK_TRANSCRIPTION_MODEL = "mock-transcriber-v1"
MOCK_EXTRACTION_MODEL = "mock-extractor-v1"
MAX_LIVE_BATCH = 20
MAX_EPISODE_ATTEMPTS = 3
RETRY_COOLDOWN_HOURS = 6
GEMINI_TRANSIENT_RETRIES = 1
GEMINI_RETRY_DELAY_SECONDS = 2.0


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root: Path
    archive_dir: Path
    state_file: Path
    work_dir: Path
    mode: str = "mock"
    ai_provider: str = "openai"
    feed_url: str = "https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss"
    feed_name: str = "MTG Fast Finance"
    brainstorm_feed_url: str = "https://feeds.feedburner.com/brainstormbrewerypodcast"
    enabled_sources: tuple[str, ...] = ("mtg-fast-finance",)
    max_audio_bytes: int = 250_000_000
    download_timeout_seconds: int = 120
    audio_chunk_seconds: int = 1200
    transcription_model: str = "gpt-4o-transcribe-diarize"
    transcription_fallback_model: str | None = None
    extraction_model: str = "gpt-5.6-luna"
    max_live_batch: int = MAX_LIVE_BATCH
    max_episode_attempts: int = MAX_EPISODE_ATTEMPTS
    retry_cooldown_hours: int = RETRY_COOLDOWN_HOURS
    gemini_transient_retries: int = GEMINI_TRANSIENT_RETRIES
    gemini_retry_delay_seconds: float = GEMINI_RETRY_DELAY_SECONDS
    card_glossary: str = ""
    repository_url: str = "https://github.com/courtjester15/mtgff-cards-to-watch"

    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        root = (root or project_root()).resolve()
        archive = root / os.getenv("FFW_ARCHIVE_DIR", "archive")
        state = root / os.getenv("FFW_STATE_FILE", "state/episodes.json")
        return cls(
            root=root,
            archive_dir=archive,
            state_file=state,
            work_dir=root / ".ffw-work",
            mode=os.getenv("FFW_MODE", "mock"),
            ai_provider=os.getenv("FFW_AI_PROVIDER", "openai").lower(),
            feed_url=os.getenv("FFW_FEED_URL", "https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss"),
            feed_name=os.getenv("FFW_FEED_NAME", "MTG Fast Finance"),
            brainstorm_feed_url=os.getenv("FFW_BRAINSTORM_FEED_URL", "https://feeds.feedburner.com/brainstormbrewerypodcast"),
            enabled_sources=tuple(
                source.strip()
                for source in os.getenv("FFW_ENABLED_SOURCES", "mtg-fast-finance").split(",")
                if source.strip()
            ),
            max_audio_bytes=int(os.getenv("FFW_MAX_AUDIO_BYTES", "250000000")),
            download_timeout_seconds=int(os.getenv("FFW_DOWNLOAD_TIMEOUT_SECONDS", "120")),
            audio_chunk_seconds=int(os.getenv("FFW_AUDIO_CHUNK_SECONDS", "1200")),
            transcription_model=os.getenv("FFW_TRANSCRIPTION_MODEL", "gpt-4o-transcribe-diarize"),
            transcription_fallback_model=os.getenv("FFW_TRANSCRIPTION_FALLBACK_MODEL") or None,
            extraction_model=os.getenv("FFW_EXTRACTION_MODEL", "gpt-5.6-luna"),
            max_live_batch=int(os.getenv("FFW_MAX_LIVE_BATCH", str(MAX_LIVE_BATCH))),
            max_episode_attempts=int(os.getenv("FFW_MAX_EPISODE_ATTEMPTS", str(MAX_EPISODE_ATTEMPTS))),
            retry_cooldown_hours=int(os.getenv("FFW_RETRY_COOLDOWN_HOURS", str(RETRY_COOLDOWN_HOURS))),
            gemini_transient_retries=max(0, int(os.getenv("FFW_GEMINI_TRANSIENT_RETRIES", str(GEMINI_TRANSIENT_RETRIES)))),
            gemini_retry_delay_seconds=max(0.0, float(os.getenv("FFW_GEMINI_RETRY_DELAY_SECONDS", str(GEMINI_RETRY_DELAY_SECONDS)))),
            card_glossary=os.getenv("FFW_CARD_GLOSSARY", ""),
            repository_url=os.getenv("FFW_REPOSITORY_URL", "https://github.com/courtjester15/mtgff-cards-to-watch"),
        )
