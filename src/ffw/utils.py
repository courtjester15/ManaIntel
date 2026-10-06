from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError as exc:
            # Windows scanners can briefly hold the target between write and rename.
            # Do not mask genuine permissions errors or retry indefinitely.
            if getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 5:
                raise
            time.sleep(0.02 * (attempt + 1))


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def episode_slug(number: int, title: str, guid: str | None = None) -> str:
    clean_title = re.sub(r"^\[synthetic\]\s*", "", title, flags=re.IGNORECASE)
    clean_title = re.sub(r"^mtg fast finance\s+ep\s+\d+[:\s-]*", "", clean_title, flags=re.IGNORECASE)
    title_slug = slugify(clean_title)[:80].rstrip("-")
    suffix = ""
    if number == 0 and guid:
        suffix = "-" + hashlib.sha256(guid.encode("utf-8")).hexdigest()[:8]
    return f"{number:04d}-{title_slug}{suffix}"


def stable_pick_id(guid: str, card_name: str, start_seconds: int | None, printing: str | None) -> str:
    identity = "|".join(
        [guid.strip().lower(), card_name.strip().lower(), str(start_seconds), (printing or "").strip().lower()]
    )
    return "pick-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def seconds_to_timestamp(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
