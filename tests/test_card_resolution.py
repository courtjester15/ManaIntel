from __future__ import annotations

import io
import json
import unittest
import urllib.error
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from ffw.card_resolution import (
    ScryfallCardResolver,
    apply_card_resolution,
    normalize_card_name,
    resolve_archive_card_names,
)
from ffw.utils import atomic_write_json, load_json
from ffw.config import Settings
from ffw.pipeline import Pipeline


class JsonResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class CardResolverTests(unittest.TestCase):
    def test_normalizes_typographic_punctuation_without_losing_words(self) -> None:
        self.assertEqual("urza's saga - showcase", normalize_card_name("  Urza’s   Saga — Showcase "))

    def test_exact_catalog_match_is_verified(self) -> None:
        requests = []

        def opener(request, **_kwargs):
            requests.append(request.full_url)
            return JsonResponse(json.dumps({
                "id": "printing-lightning-bolt",
                "name": "Lightning Bolt",
                "oracle_id": "oracle-lightning-bolt",
                "scryfall_uri": "https://scryfall.com/card/test/1/lightning-bolt",
                "image_uris": {"normal": "https://cards.scryfall.io/normal/test.jpg"},
            }).encode())

        resolver = ScryfallCardResolver(opener=opener, sleep=lambda _seconds: None)
        result = resolver.resolve("Lightning Bolt")
        self.assertEqual("verified", result["status"])
        self.assertEqual("Lightning Bolt", result["canonical_name"])
        self.assertEqual("oracle-lightning-bolt", result["oracle_id"])
        self.assertEqual("printing-lightning-bolt", result["scryfall_id"])
        self.assertEqual("https://scryfall.com/card/test/1/lightning-bolt", result["scryfall_uri"])
        self.assertEqual("https://cards.scryfall.io/normal/test.jpg", result["image_uri"])
        self.assertIn("exact=Lightning+Bolt", requests[0])

    def test_double_faced_catalog_match_retains_face_images(self) -> None:
        def opener(_request, **_kwargs):
            return JsonResponse(json.dumps({
                "id": "printing-delver",
                "name": "Delver of Secrets // Insectile Aberration",
                "oracle_id": "oracle-delver",
                "scryfall_uri": "https://scryfall.com/card/test/2/delver-of-secrets",
                "card_faces": [
                    {"name": "Delver of Secrets", "image_uris": {"normal": "https://cards.scryfall.io/normal/front.jpg"}},
                    {"name": "Insectile Aberration", "image_uris": {"normal": "https://cards.scryfall.io/normal/back.jpg"}},
                ],
            }).encode())

        result = ScryfallCardResolver(opener=opener, sleep=lambda _seconds: None).resolve(
            "Delver of Secrets // Insectile Aberration"
        )

        self.assertIsNone(result["image_uri"])
        self.assertEqual(
            ["https://cards.scryfall.io/normal/front.jpg", "https://cards.scryfall.io/normal/back.jpg"],
            [face["image_uri"] for face in result["card_face_images"]],
        )

    def test_fuzzy_catalog_match_remains_a_review_suggestion(self) -> None:
        calls = 0

        def opener(request, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, None)
            return JsonResponse(json.dumps({
                "name": "Talon Gates of Madara",
                "oracle_id": "oracle-talon-gates",
            }).encode())

        resolver = ScryfallCardResolver(opener=opener, sleep=lambda _seconds: None)
        result = resolver.resolve("Talongates of Madara")
        self.assertEqual("suggested", result["status"])
        self.assertEqual("fuzzy", result["method"])
        self.assertEqual("Talon Gates of Madara", result["canonical_name"])

    def test_configured_ca_bundle_is_added_to_tls_verification(self) -> None:
        context = Mock()
        response = JsonResponse(json.dumps({
            "name": "Black Lotus",
            "oracle_id": "oracle-black-lotus",
        }).encode())
        opener = Mock(return_value=response)

        with patch("ffw.card_resolution.ssl.create_default_context", return_value=context):
            resolver = ScryfallCardResolver(
                ca_bundle=Path("local-proxy-ca.crt"),
                opener=opener,
                sleep=lambda _seconds: None,
            )
            result = resolver.resolve("Black Lotus")

        context.load_verify_locations.assert_called_once_with(cafile="local-proxy-ca.crt")
        self.assertIs(opener.call_args.kwargs["context"], context)
        self.assertEqual("verified", result["status"])

    def test_archive_sweep_reuses_a_name_lookup_and_preserves_pick_ids(self) -> None:
        root = Path.cwd() / ".test-work" / str(uuid.uuid4())
        first = root / "archive/episodes/one/summary.json"
        second = root / "archive/episodes/two/summary.json"
        atomic_write_json(first, {"recommendations": [{"id": "pick-one", "card": "Sol Ring"}]})
        atomic_write_json(second, {"recommendations": [{"id": "pick-two", "card": "Sol Ring"}]})

        class Resolver:
            version = "test-v1"

            def __init__(self):
                self.calls = 0

            def resolve(self, raw_name):
                self.calls += 1
                return {
                    "raw_name": raw_name,
                    "normalized_name": normalize_card_name(raw_name),
                    "status": "verified",
                    "canonical_name": "Sol Ring",
                    "oracle_id": "oracle-sol-ring",
                    "method": "exact",
                    "resolver_version": self.version,
                    "resolved_at": "2026-08-07T00:00:00Z",
                }

        resolver = Resolver()
        store_path = root / "state/card-resolutions.json"
        report = resolve_archive_card_names(root / "archive", store_path, resolver, limit=10)
        store = load_json(store_path)
        self.assertEqual(1, resolver.calls)
        self.assertEqual(1, report.looked_up)
        self.assertEqual(1, report.cached)
        self.assertEqual({"pick-one", "pick-two"}, set(store["resolutions"]))

        projected = apply_card_resolution(
            {"id": "pick-one", "card": "Sol Ring"},
            store["resolutions"],
        )
        self.assertEqual("Sol Ring", projected["resolved_card"])
        self.assertEqual("oracle-sol-ring", projected["oracle_id"])
        self.assertEqual("Sol Ring", projected["card"])

    def test_archive_sweep_refreshes_legacy_records_without_visual_metadata(self) -> None:
        root = Path.cwd() / ".test-work" / str(uuid.uuid4())
        summary = root / "archive/episodes/one/summary.json"
        store_path = root / "state/card-resolutions.json"
        atomic_write_json(summary, {"recommendations": [{"id": "pick-one", "card": "Sol Ring"}]})
        atomic_write_json(store_path, {
            "schema_version": "1.0.0",
            "updated_at": "2026-08-07T00:00:00Z",
            "resolutions": {"pick-one": {
                "raw_name": "Sol Ring",
                "normalized_name": "sol ring",
                "status": "verified",
                "canonical_name": "Sol Ring",
                "oracle_id": "oracle-sol-ring",
                "method": "exact",
                "resolver_version": "test-v1",
                "resolved_at": "2026-08-07T00:00:00Z",
            }},
        })

        class Resolver:
            version = "test-v1"

            def resolve(self, raw_name):
                return {
                    "raw_name": raw_name,
                    "normalized_name": normalize_card_name(raw_name),
                    "status": "verified",
                    "canonical_name": "Sol Ring",
                    "scryfall_id": "printing-sol-ring",
                    "oracle_id": "oracle-sol-ring",
                    "scryfall_uri": "https://scryfall.com/card/test/1/sol-ring",
                    "image_uri": "https://cards.scryfall.io/normal/sol-ring.jpg",
                    "card_face_images": [],
                    "method": "exact",
                    "resolver_version": self.version,
                    "resolved_at": "2026-08-10T00:00:00Z",
                }

        report = resolve_archive_card_names(root / "archive", store_path, Resolver(), limit=10)
        refreshed = load_json(store_path)["resolutions"]["pick-one"]

        self.assertEqual(1, report.looked_up)
        self.assertEqual("https://cards.scryfall.io/normal/sol-ring.jpg", refreshed["image_uri"])

    def test_production_sweep_skips_synthetic_episode_summaries(self) -> None:
        root = Path.cwd() / ".test-work" / str(uuid.uuid4())
        synthetic = root / "archive/episodes/synthetic/summary.json"
        atomic_write_json(synthetic, {"recommendations": [{"id": "synthetic-pick", "card": "Sol Ring"}]})
        atomic_write_json(synthetic.parent / "metadata.json", {"synthetic": True})

        class Resolver:
            version = "test-v1"

            def resolve(self, _raw_name):
                raise AssertionError("Synthetic picks must not be resolved in production mode.")

        report = resolve_archive_card_names(
            root / "archive", root / "state/card-resolutions.json", Resolver(),
            limit=10, production=True,
        )

        self.assertEqual(0, report.scanned)

    def test_pipeline_publishes_resolved_projection_without_mutating_summary(self) -> None:
        root = Path.cwd() / ".test-work" / str(uuid.uuid4())
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work")

        class Resolver:
            version = "test-v1"

            def resolve(self, raw_name):
                return {
                    "raw_name": raw_name,
                    "normalized_name": normalize_card_name(raw_name),
                    "status": "verified",
                    "canonical_name": raw_name,
                    "oracle_id": f"oracle-{normalize_card_name(raw_name).replace(' ', '-')}",
                    "method": "exact",
                    "resolver_version": self.version,
                    "resolved_at": "2026-08-07T00:00:00Z",
                }

        pipeline = Pipeline.mock(settings)
        pipeline.card_resolver = Resolver()
        pipeline.run()

        cards = load_json(settings.archive_dir / "cards.json")["cards"]
        public_resolutions = load_json(settings.archive_dir / "resolutions.json")["resolutions"]
        first_summary_path = next((settings.archive_dir / "episodes").glob("*/summary.json"))
        original_pick = load_json(first_summary_path)["recommendations"][0]
        projected_pick = next(pick for pick in cards if pick["id"] == original_pick["id"])

        self.assertNotIn("card_resolution", original_pick)
        self.assertEqual(original_pick["card"], projected_pick["resolved_card"])
        self.assertEqual("verified", projected_pick["card_resolution"]["status"])
        self.assertIn(original_pick["id"], public_resolutions)


if __name__ == "__main__":
    unittest.main()
