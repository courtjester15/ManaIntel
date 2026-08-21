from __future__ import annotations

import re


EPISODE_NUMBER_PATTERNS = (
    r"\b(?:ep(?:isode)?\.?\s*#?)(\d{1,5})\b",
    r"\bbrainstorm\s+brewery\s*#\s*(\d{1,5})\b",
)


def parse_episode_number(title: str, description: str = "") -> int:
    for text in (title, description):
        for pattern in EPISODE_NUMBER_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
    return 0
