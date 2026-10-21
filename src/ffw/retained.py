"""Restore only an explicitly selected episode from a historical artifact."""
import argparse
import gzip
import json
from pathlib import Path
import shutil


def restore_episode(source: Path, target: Path, guid: str) -> Path:
    if not guid:
        raise ValueError("Historical transcript recovery requires an exact episode GUID.")
    matches = []
    for path in source.rglob("*.json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
        if payload.get("episode", {}).get("guid") == guid and isinstance(payload.get("transcript"), dict):
            matches.append(path)
    if len(matches) != 1:
        raise ValueError(f"Expected one retained transcript for selected episode; found {len(matches)}.")
    target.mkdir(parents=True, exist_ok=True)
    destination = target / matches[0].name
    shutil.copy2(matches[0], destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--guid", required=True)
    args = parser.parse_args()
    restore_episode(args.source, args.target, args.guid)
