"""Read-only source-to-catalog fidelity checks, not source-accuracy approval."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import urllib.parse
import urllib.request

from .archive import rebuild_catalog
from .card_resolution import load_resolution_store
from .models import utc_now

MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
MAX_FINDINGS = 30


def json_differences(expected: Any, actual: Any, pointer: str = "", *, limit: int = MAX_FINDINGS) -> list[str]:
    """Return bounded JSON pointers only; never echo excerpts or field values."""
    differences: list[str] = []

    def visit(left: Any, right: Any, path: str) -> None:
        if len(differences) >= limit:
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                child = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
                if key not in left or key not in right:
                    differences.append(child)
                else:
                    visit(left[key], right[key], child)
                if len(differences) >= limit:
                    break
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                differences.append(path or "/")
            for index, (a, b) in enumerate(zip(left, right)):
                visit(a, b, path + "/" + str(index))
                if len(differences) >= limit:
                    break
        elif left != right or isinstance(left, bool) != isinstance(right, bool):
            differences.append(path or "/")

    visit(expected, actual, pointer)
    return differences


def expected_publication(archive_dir: Path, state_file: Path, *, reviews_dir: Path | None = None,
                         production: bool = True, feed_name: str = "MTG Fast Finance",
                         repository_url: str = "https://github.com/courtjester15/ManaIntel") -> dict[str, dict]:
    store = load_resolution_store(state_file.parent / "card-resolutions.json")
    index, cards = rebuild_catalog(archive_dir, production=production, feed_name=feed_name,
                                   repository_url=repository_url, reviews_dir=reviews_dir,
                                   resolutions_path=state_file.parent / "card-resolutions.json", write=False)
    ids = {pick["id"] for pick in cards}
    return {
        "index.json": index,
        "cards.json": {"schema_version": index["schema_version"], "synthetic": not production,
                       "notice": index["notice"] if not production else "Automated extraction; verify against source audio.",
                       "count": len(cards), "cards": cards},
        "resolutions.json": {"schema_version": store["schema_version"],
                             "resolver_updated_at": store.get("updated_at"),
                             "resolutions": {key: value for key, value in store["resolutions"].items() if key in ids}},
    }


def catalog_findings(expected: dict[str, dict], actual: dict[str, dict], *, full_metadata: bool = True) -> list[dict]:
    findings: list[dict] = []
    for name, wanted in expected.items():
        observed = actual.get(name)
        if name == "index.json" and isinstance(observed, dict) and isinstance(observed.get("metadata"), dict):
            wanted = {**wanted, "metadata": dict(wanted["metadata"])}
            observed = {**observed, "metadata": dict(observed["metadata"])}
            try:
                generated = datetime.fromisoformat(str(observed["metadata"].get("generated_at", "")).replace("Z", "+00:00"))
                if generated.tzinfo is None:
                    raise ValueError("Naive build time")
            except ValueError:
                findings.append({"file": name, "pointer": "/metadata/generated_at", "problem": "invalid_build_time"})
            # Build time is the only ignored field when verifying a deployment.
            wanted["metadata"].pop("generated_at", None)
            observed["metadata"].pop("generated_at", None)
            if not full_metadata:
                # Preflight validates older releases too, using the current code.
                for key in ("pipeline_version", "repository_url", "workflow_url", "review_workflow_url"):
                    wanted["metadata"].pop(key, None)
                    observed["metadata"].pop(key, None)
        for pointer in json_differences(wanted, observed, limit=MAX_FINDINGS - len(findings)):
            findings.append({"file": name, "pointer": pointer, "problem": "differs_from_source_projection"})
        if len(findings) >= MAX_FINDINGS:
            break
    return findings


def read_publication_json(payload: bytes) -> dict:
    """Decode explicitly, independent of Windows locale or console encoding."""
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise ValueError("Publication document exceeds the 16 MiB verification limit.")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Publication document must be a JSON object.")
    return value


def verify_publication(archive_dir: Path, state_file: Path, *, site_dir: Path | None = None,
                       url: str | None = None, reviews_dir: Path | None = None,
                       feed_name: str = "MTG Fast Finance",
                       repository_url: str = "https://github.com/courtjester15/ManaIntel",
                       opener: Callable = urllib.request.urlopen) -> dict:
    if (site_dir is None) == (url is None):
        raise ValueError("Select exactly one publication directory or URL.")
    if not archive_dir.is_dir() or not state_file.is_file():
        raise ValueError("Verification requires the retained archive and state file.")
    if url is not None and (urllib.parse.urlsplit(url).scheme not in {"http", "https"}
                or urllib.parse.urlsplit(url).query or urllib.parse.urlsplit(url).fragment):
        raise ValueError("Publication URL must be an HTTP(S) site root without query or fragment.")
    expected = expected_publication(archive_dir, state_file, reviews_dir=reviews_dir,
                                    feed_name=feed_name, repository_url=repository_url)
    actual: dict[str, dict] = {}
    findings: list[dict] = []
    for name in expected:
        try:
            if site_dir is not None:
                with (site_dir / "archive" / name).open("rb") as stream:
                    payload = stream.read(MAX_DOCUMENT_BYTES + 1)
            else:
                request = urllib.request.Request(url.rstrip("/") + "/archive/" + name,
                                                 headers={"Accept": "application/json", "Cache-Control": "no-cache"})
                with opener(request, timeout=20) as response:
                    payload = response.read(MAX_DOCUMENT_BYTES + 1)
            actual[name] = read_publication_json(payload)
        except (OSError, ValueError) as exc:
            findings.append({"file": name, "pointer": "/", "problem": "unreadable_publication",
                             "error_type": type(exc).__name__})
    if not findings:
        findings = catalog_findings(expected, actual)
    return {"observed_at": utc_now(), "verified": not findings, "files_checked": len(actual),
            "expected_episodes": len(expected["index.json"]["episodes"]),
            "expected_picks": len(expected["cards.json"]["cards"]), "findings": findings,
            "findings_limited": len(findings) >= MAX_FINDINGS,
            "notice": "Catalog fidelity to retained records and overrides; not independent audio accuracy or review approval."}
