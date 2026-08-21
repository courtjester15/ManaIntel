from __future__ import annotations

import json
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .models import utc_now
from .utils import atomic_write_json, load_json


RESOLUTION_SCHEMA_VERSION = "1.0.0"
SCRYFALL_RESOLVER_VERSION = "scryfall-named-v1"


class CardResolutionUnavailable(RuntimeError):
    """Raised when the catalog cannot be reached, rather than when a name is absent."""


def normalize_card_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.translate(str.maketrans({
        "\u2018": "'", "\u2019": "'", "\u02bc": "'", "`": "'",
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    }))
    return " ".join(normalized.split()).strip().casefold()


def _query_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.translate(str.maketrans({
        "\u2018": "'", "\u2019": "'", "\u02bc": "'", "`": "'",
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    }))
    return " ".join(normalized.split()).strip()


class ScryfallCardResolver:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        min_request_interval_seconds: float = 0.12,
        ca_bundle: Path | None = None,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.min_request_interval_seconds = min_request_interval_seconds
        self.opener = opener or urllib.request.urlopen
        self.ssl_context: ssl.SSLContext | None = None
        if ca_bundle is not None:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.load_verify_locations(cafile=str(ca_bundle))
        self.sleep = sleep
        self.clock = clock
        self._last_request_at: float | None = None

    @property
    def version(self) -> str:
        return SCRYFALL_RESOLVER_VERSION

    def _request(self, parameter: str, card_name: str) -> dict[str, Any] | None:
        if self._last_request_at is not None:
            remaining = self.min_request_interval_seconds - (self.clock() - self._last_request_at)
            if remaining > 0:
                self.sleep(remaining)
        query = urllib.parse.urlencode({parameter: card_name})
        request = urllib.request.Request(
            f"https://api.scryfall.com/cards/named?{query}",
            headers={
                "User-Agent": "ManaIntel/0.5 (https://github.com/courtjester15/ManaIntel)",
                "Accept": "application/json;q=0.9,*/*;q=0.8",
            },
        )
        try:
            request_options: dict[str, Any] = {"timeout": self.timeout_seconds}
            if self.ssl_context is not None:
                request_options["context"] = self.ssl_context
            with self.opener(request, **request_options) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code == 404:
                return None
            raise CardResolutionUnavailable(f"Scryfall returned HTTP {exc.code}.") from exc
        except (OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CardResolutionUnavailable(f"Scryfall lookup failed: {type(exc).__name__}: {exc}") from exc
        finally:
            self._last_request_at = self.clock()
        if not isinstance(payload, dict) or not payload.get("name"):
            raise CardResolutionUnavailable("Scryfall returned an invalid card payload.")
        return payload

    def resolve(self, raw_name: str) -> dict[str, Any]:
        query_name = _query_name(raw_name)
        if not query_name:
            return self._record(raw_name, status="not_found", method="exact")
        exact = self._request("exact", query_name)
        if exact is not None:
            method = "exact" if exact["name"].strip().casefold() == raw_name.strip().casefold() else "normalized"
            return self._record(raw_name, status="verified", method=method, card=exact)
        fuzzy = self._request("fuzzy", query_name)
        if fuzzy is None:
            return self._record(raw_name, status="not_found", method="fuzzy")
        if normalize_card_name(fuzzy["name"]) == normalize_card_name(raw_name):
            return self._record(raw_name, status="verified", method="normalized", card=fuzzy)
        return self._record(raw_name, status="suggested", method="fuzzy", card=fuzzy)

    def _record(
        self,
        raw_name: str,
        *,
        status: str,
        method: str,
        card: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        card = card or {}
        image_uris = card.get("image_uris") if isinstance(card.get("image_uris"), dict) else {}
        card_face_images = []
        for face in card.get("card_faces") or []:
            if not isinstance(face, dict):
                continue
            face_image_uris = face.get("image_uris") if isinstance(face.get("image_uris"), dict) else {}
            image_uri = face_image_uris.get("normal")
            if image_uri:
                card_face_images.append({"name": face.get("name"), "image_uri": image_uri})
        return {
            "raw_name": raw_name,
            "normalized_name": normalize_card_name(raw_name),
            "status": status,
            "canonical_name": card.get("name"),
            "scryfall_id": card.get("id"),
            "oracle_id": card.get("oracle_id"),
            "scryfall_uri": card.get("scryfall_uri"),
            "image_uri": image_uris.get("normal"),
            "card_face_images": card_face_images,
            "method": method,
            "resolver_version": self.version,
            "resolved_at": utc_now(),
        }


@dataclass
class ResolutionReport:
    scanned: int = 0
    cached: int = 0
    looked_up: int = 0
    verified: int = 0
    suggested: int = 0
    not_found: int = 0
    unavailable: int = 0
    changed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _is_current_resolution(record: dict[str, Any], resolver_version: str) -> bool:
    return (
        record.get("resolver_version") == resolver_version
        and bool(record.get("normalized_name"))
        and {"scryfall_uri", "image_uri", "card_face_images"}.issubset(record)
    )


def load_resolution_store(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"schema_version": RESOLUTION_SCHEMA_VERSION, "updated_at": None, "resolutions": {}}
    payload = load_json(path, {})
    if not isinstance(payload, dict) or not isinstance(payload.get("resolutions", {}), dict):
        return {"schema_version": RESOLUTION_SCHEMA_VERSION, "updated_at": None, "resolutions": {}}
    payload.setdefault("schema_version", RESOLUTION_SCHEMA_VERSION)
    payload.setdefault("updated_at", None)
    payload.setdefault("resolutions", {})
    return payload


def resolve_archive_card_names(
    archive_dir: Path,
    store_path: Path,
    resolver: ScryfallCardResolver,
    *,
    limit: int = 25,
    refresh: bool = False,
    production: bool = False,
) -> ResolutionReport:
    if limit < 1:
        raise ValueError("Card resolution limit must be positive.")
    store = load_resolution_store(store_path)
    resolutions: dict[str, dict[str, Any]] = store["resolutions"]
    reusable: dict[str, dict[str, Any]] = {}
    if not refresh:
        for record in resolutions.values():
            if _is_current_resolution(record, resolver.version):
                reusable[record["normalized_name"]] = record

    report = ResolutionReport()
    for summary_path in sorted((archive_dir / "episodes").glob("*/summary.json")):
        if production:
            metadata = load_json(summary_path.parent / "metadata.json", {})
            if metadata.get("synthetic") is True:
                continue
        summary = load_json(summary_path, {})
        for pick in summary.get("recommendations", []):
            pick_id = pick.get("id")
            raw_name = str(pick.get("card") or "").strip()
            if not pick_id or not raw_name:
                continue
            report.scanned += 1
            existing = resolutions.get(pick_id)
            if (
                not refresh
                and existing
                and existing.get("raw_name") == raw_name
                and _is_current_resolution(existing, resolver.version)
            ):
                report.cached += 1
                continue
            normalized = normalize_card_name(raw_name)
            if not refresh and normalized in reusable:
                record = {**reusable[normalized], "raw_name": raw_name, "resolved_at": utc_now()}
                resolutions[pick_id] = record
                report.cached += 1
                report.changed = True
                continue
            if report.looked_up >= limit:
                continue
            try:
                record = resolver.resolve(raw_name)
            except CardResolutionUnavailable:
                report.unavailable += 1
                continue
            report.looked_up += 1
            resolutions[pick_id] = record
            reusable[normalized] = record
            report.changed = True
            status = record["status"]
            if status == "verified":
                report.verified += 1
            elif status == "suggested":
                report.suggested += 1
            else:
                report.not_found += 1

    if report.changed:
        store["schema_version"] = RESOLUTION_SCHEMA_VERSION
        store["updated_at"] = utc_now()
        atomic_write_json(store_path, store)
    return report


def apply_card_resolution(pick: dict[str, Any], resolutions: dict[str, Any]) -> dict[str, Any]:
    projected = dict(pick)
    record = resolutions.get(pick.get("id"))
    if not isinstance(record, dict) or record.get("raw_name") != pick.get("card"):
        return projected
    projected["card_resolution"] = dict(record)
    if record.get("status") == "verified" and record.get("canonical_name"):
        projected["resolved_card"] = record["canonical_name"]
        projected["oracle_id"] = record.get("oracle_id")
    return projected
