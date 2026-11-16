"""Restore only an explicitly selected episode from a historical artifact."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


def restore_checkpoints(source: Path, target: Path, guid: str) -> list[Path]:
    """Restore selected original/repair chunks; consumers still verify fingerprints."""
    if not guid:
        raise ValueError("Checkpoint recovery requires an exact episode GUID.")
    def name(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    matches = [p for p in source.rglob(name(guid)) if p.is_dir()]
    if len(matches) != 1:
        raise ValueError(f"Expected one selected episode checkpoint directory; found {len(matches)}.")
    original = matches[0]
    counts = {json.loads(p.read_text(encoding="utf-8")).get("chunk_count")
              for p in original.glob("chunk-*.json") if p.stem.removeprefix("chunk-").isdigit()}
    if len(counts) != 1 or not all(type(n) is int and 1 <= n <= 1000 for n in counts):
        raise ValueError("Selected checkpoints have missing or inconsistent chunk counts.")
    directories = [original]
    for index in range(counts.pop()):
        repair = original.parent / name(guid + f":timing-repair-{index}")
        if repair.is_dir():
            directories.append(repair)
    # Merge only the exact episode and its repairs, preserving all other progress.
    restored = []
    for directory in directories:
        destination = target / directory.name
        destination.mkdir(parents=True, exist_ok=True)
        for path in directory.glob("chunk-*.json"):
            if path.is_symlink():
                raise ValueError("Checkpoint recovery does not accept symbolic links.")
            shutil.copy2(path, destination / path.name)
        restored.append(destination)
    return restored


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
    parser.add_argument("--kind", choices=("transcript", "checkpoints"), default="transcript")
    args = parser.parse_args()
    restore = restore_checkpoints if args.kind == "checkpoints" else restore_episode
    restore(args.source, args.target, args.guid)
