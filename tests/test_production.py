from __future__ import annotations

import gzip
import hashlib
import io
import os
import json
import shutil
import subprocess
import sys
import types as stdlib_types
import unittest
import uuid
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, call, patch

from ffw.archive import rebuild_catalog
from ffw.detection import locate_cards_to_watch, locate_recommendation_section
from ffw.models import EpisodeCandidate, PipelineResult
from ffw.config import Settings
from ffw.pipeline import Pipeline, classify_failure, compare_episode_summaries
from ffw.production import CombinedFeedSource, GeminiExtractor, GeminiMalformedJSONError, GeminiTranscriber, OpenAIExtractor, OpenAITranscriber, ProviderFallbackTranscriber, StreamingDownloader, _gemini_generate_json, parse_episode_number, parse_rss, production_adapters
from ffw.state import JsonStateStore
from ffw.utils import atomic_write_json, load_json
from ffw.verification import GeminiPickVerifier


def workspace_temp() -> Path:
    path = Path.cwd() / ".test-work" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, *, content_type: str = "audio/mpeg", url: str = "https://cdn.example.test/audio.mp3", length: int | None = None):
        super().__init__(body)
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def episode(url: str = "https://cdn.example.test/audio.mp3") -> EpisodeCandidate:
    return EpisodeCandidate("guid", 42, "Episode 42", "2026-01-01T00:00:00Z", url, "https://example.test/42", [])


class RssTests(unittest.TestCase):
    def test_saved_feed_identity_fallback_order_and_number(self) -> None:
        payload = (Path(__file__).parent / "fixtures/feed.xml").read_bytes()
        items = parse_rss(payload)
        self.assertEqual([1001, 1002, 1003], [item.episode_number for item in items])
        self.assertEqual("real-guid-1001", items[0].guid)
        expected = hashlib.sha256(b"https://cdn.example.test/1002.mp3").hexdigest()
        self.assertEqual(f"enclosure-sha256:{expected}", items[1].guid)
        self.assertEqual(3930, items[2].duration_seconds)
        self.assertEqual(["Host One", "Host Two"], items[2].hosts)

    def test_episode_number_variants(self) -> None:
        self.assertEqual(87, parse_episode_number("Episode #87 — Cards"))
        self.assertEqual(91, parse_episode_number("MTGFF Ep. 91"))
        self.assertEqual(0, parse_episode_number("No number"))

    def test_duplicate_guids_are_collapsed(self) -> None:
        xml = (Path(__file__).parent / "fixtures/feed.xml").read_text(encoding="utf-8")
        duplicate = xml.replace("</channel>", xml[xml.index("<item>"):xml.index("</item>") + 7] + "</channel>")
        self.assertEqual(3, len(parse_rss(duplicate.encode())))

    def test_brainstorm_feed_namespaces_identity_and_source(self) -> None:
        payload = b"""<rss><channel><item><title>Brainstorm Brewery #705</title>
        <guid>libsyn-705</guid><pubDate>Fri, 24 Jul 2026 06:00:00 +0000</pubDate>
        <link>https://brainstormbrewery.com/705</link>
        <enclosure url="https://traffic.libsyn.com/example/705.mp3" type="audio/mpeg" />
        </item></channel></rss>"""
        item = parse_rss(
            payload, source_id="brainstorm-brewery", source_name="Brainstorm Brewery",
            source_url="https://brainstormbrewery.com/", extraction_profile="brainstorm_brewery",
            namespace_guid=True,
        )[0]
        self.assertEqual("brainstorm-brewery:libsyn-705", item.guid)
        self.assertEqual(("brainstorm-brewery", "Brainstorm Brewery", "brainstorm_brewery"), (item.source_id, item.source_name, item.extraction_profile))

    def test_source_specific_discovery_does_not_hide_requested_feed_failure(self) -> None:
        class Source:
            def __init__(self, source_id: str, fails: bool = False) -> None:
                self.source_id = source_id
                self.source_name = source_id
                self.fails = fails

            def episodes(self):
                if self.fails:
                    raise RuntimeError("feed unavailable")
                return [episode()]

        combined = CombinedFeedSource([Source("mtg-fast-finance"), Source("brainstorm-brewery", fails=True)])
        with self.assertRaisesRegex(RuntimeError, "feed unavailable"):
            combined.episodes_for("brainstorm-brewery")


class DownloadTests(unittest.TestCase):
    def test_streams_and_renames_part_file(self) -> None:
        root = workspace_temp()
        downloader = StreamingDownloader(100, 5, opener=lambda *a, **k: FakeResponse(b"audio-data"))
        result = downloader.download(episode(), root / "source-audio")
        self.assertEqual(b"audio-data", result.read_bytes())
        self.assertFalse((root / "source-audio.mp3.part").exists())

    def test_rejects_unsafe_url(self) -> None:
        downloader = StreamingDownloader(100, 5)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            downloader.download(episode("http://example.test/a.mp3"), Path("unused"))

    def test_rejects_mime_and_cleans_part(self) -> None:
        root = workspace_temp()
        downloader = StreamingDownloader(100, 5, opener=lambda *a, **k: FakeResponse(b"html", content_type="text/html"))
        with self.assertRaisesRegex(ValueError, "content type"):
            downloader.download(episode(), root / "source-audio")
        self.assertFalse((root / "source-audio.mp3.part").exists())

    def test_rejects_declared_or_streamed_oversize(self) -> None:
        for response in (FakeResponse(b"x", length=101), FakeResponse(b"x" * 101)):
            with self.subTest(length=response.headers.get("Content-Length")):
                root = workspace_temp()
                downloader = StreamingDownloader(100, 5, opener=lambda *a, response=response, **k: response)
                with self.assertRaisesRegex(ValueError, "maximum size"):
                    downloader.download(episode(), root / "source-audio")


class DetectionAndStateTests(unittest.TestCase):
    def test_section_detection_orders_segments_and_finds_boundaries(self) -> None:
        result = locate_cards_to_watch([
            {"start": 30, "end": 40, "text": "That wraps up our picks."},
            {"start": 20, "end": 30, "text": "The card is Example Card"},
            {"start": 10, "end": 20, "text": "Cards to Watch"},
        ])
        self.assertTrue(result["located"])
        self.assertEqual((10, 40, "high"), (result["start_seconds"], result["end_seconds"], result["confidence"]))

    def test_missing_section_never_invents_picks(self) -> None:
        result = locate_cards_to_watch([{"start": 0, "end": 10, "text": "General discussion"}])
        self.assertFalse(result["located"])
        self.assertEqual([], result["segments"])

    def test_ff_outline_is_ignored_when_implicit_picks_and_weekly_topic_bound_section(self) -> None:
        result = locate_cards_to_watch([
            {"start": 100, "end": 120, "text": "Today we have meta updates, Cards to Watch, and a deep dive into Goblin decks."},
            {"start": 500, "end": 520, "text": "Prices moved a little this week."},
            {"start": 600, "end": 620, "text": "What do you have for your first pick this week?"},
            {"start": 620, "end": 700, "text": "My pick is Example Card at five dollars."},
            {"start": 780, "end": 850, "text": "My other pick is Second Card."},
            {"start": 900, "end": 930, "text": "Now let's move on to our main topic and break down the Goblin decks."},
            {"start": 930, "end": 1000, "text": "The Goblin deck sale was a mess."},
            {"start": 1400, "end": 1420, "text": "Thanks for listening."},
        ], title="MTG Fast Finance Ep 1: Goblin Decks Got Gone")
        self.assertTrue(result["located"])
        self.assertEqual((600, 850), (result["start_seconds"], result["end_seconds"]))
        self.assertEqual("recommendation_language", result["start_signal"])
        self.assertEqual("advertised_topic_transition", result["end_signal"])
        self.assertEqual("medium", result["confidence"])
        self.assertIsNone(result["review_reason"])

    def test_ff_later_explicit_marker_wins_over_early_show_outline(self) -> None:
        result = locate_cards_to_watch([
            {"start": 90, "end": 110, "text": "This week: price updates, Cards to Watch, and Marvel previews."},
            {"start": 600, "end": 620, "text": "Now it is time for Cards to Watch."},
            {"start": 620, "end": 800, "text": "My first pick is Example Card."},
            {"start": 900, "end": 930, "text": "Moving on to our main topic, the Marvel previews."},
        ], title="MTG Fast Finance Ep 2: Marvel Previews")
        self.assertEqual((600, 800, "high"), (
            result["start_seconds"], result["end_seconds"], result["confidence"],
        ))
        self.assertIsNone(result["review_reason"])

    def test_ff_530_real_agenda_does_not_beat_later_cards_to_watch_marker(self) -> None:
        result = locate_cards_to_watch([
            {"sequence": 0, "start": 124, "end": 146.5, "text": (
                "We have a lot going on. We've got to talk about Modern events. Then we've got our top movers "
                "in paper. And then you and I have our cards to watch. And then we need to talk about the Cats."
            )},
            {"sequence": 1, "start": 147, "end": 239.5, "text": "Taking a look at the metagame week in review."},
            {"sequence": 2, "start": 900, "end": 900, "text": (
                "We're going to get into this Secret Lair drop later. For now, finish these top paper movers."
            )},
            {"sequence": 3, "start": 972, "end": 1003, "text": "All right, looking at cards to watch."},
            {"sequence": 4, "start": 1228, "end": 1315, "text": "My first pick this week is Example Card."},
            {"sequence": 5, "start": 1707, "end": 1760, "text": "My last pick is Final Card."},
            {"sequence": 6, "start": 1800, "end": 1840, "text": (
                "Now let's move on to our main topic and discuss the Cats Secret Lair Superdrop."
            )},
        ], title="MTG Fast Finance Ep 530: Secret Lair Cats Superdrop Results")

        self.assertEqual((972, 1760), (result["start_seconds"], result["end_seconds"]))
        self.assertEqual("explicit_section_marker", result["start_signal"])
        self.assertEqual("advertised_topic_transition", result["end_signal"])

    def test_ff_532_late_agenda_and_chunk_boundary_do_not_hide_real_section(self) -> None:
        result = locate_cards_to_watch([
            {"sequence": 0, "start": 341.9, "end": 416.7, "text": (
                "Our usual four segments. First is the metagame review. Then segment two is top movers. "
                "Then segment three, our cards to watch. And finally we wrap with Marvel Superheroes."
            )},
            {"sequence": 1, "start": 900, "end": 900, "text": (
                "Marvel Superheroes cards gained this week; take profits and move on to the next thing."
            )},
            {"sequence": 2, "start": 1301.7, "end": 1315, "text": (
                "Let's go to our cards to watch. Do you want to lead off?"
            )},
            {"sequence": 3, "start": 1514, "end": 1600, "text": "My first pick this week is Force of Vigor."},
            {"sequence": 4, "start": 1800, "end": 1800, "text": "My second pick is Roaming Throne."},
            {"sequence": 5, "start": 1900, "end": 1940, "text": "My other pick is Final Card."},
            {"sequence": 6, "start": 2100, "end": 2100, "text": (
                "Now let's move on to our main topic and discuss Marvel Superheroes pricing."
            )},
        ], title="MTG Fast Finance Ep 532: Early Marvel Price Action")

        self.assertEqual((1301, 1940), (result["start_seconds"], result["end_seconds"]))
        self.assertEqual("explicit_section_marker", result["start_signal"])
        self.assertEqual("advertised_topic_transition", result["end_signal"])

    def test_ff_split_intro_outline_does_not_beat_later_pick_language(self) -> None:
        result = locate_cards_to_watch([
            {"start": 80, "end": 90, "text": "Today we have price updates,"},
            {"start": 90, "end": 100, "text": "Cards to Watch,"},
            {"start": 100, "end": 110, "text": "and a deep dive into Goblin decks."},
            {"start": 600, "end": 620, "text": "My first pick this week is Example Card."},
            {"start": 800, "end": 820, "text": "Moving on to our main topic, Goblin decks."},
        ], title="MTG Fast Finance Ep 5: Goblin Decks Got Gone")
        self.assertEqual(600, result["start_seconds"])
        self.assertEqual("recommendation_language", result["start_signal"])
        self.assertIsNone(result["review_reason"])

    def test_ff_topic_word_inside_pick_discussion_is_not_a_structural_end(self) -> None:
        result = locate_cards_to_watch([
            {"start": 500, "end": 520, "text": "My first pick this week is a Marvel card."},
            {"start": 700, "end": 730, "text": "Now let's talk about the Marvel printing and its price."},
            {"start": 850, "end": 880, "text": "My other pick is Second Card."},
            {"start": 1400, "end": 1420, "text": "Thanks for listening."},
        ], title="MTG Fast Finance Ep 6: Much More Marvel")
        self.assertIsNone(result["end_signal"])
        self.assertIn("no explicit ending", result["review_reason"])

    def test_ff_description_supplies_topic_hint_when_title_is_generic(self) -> None:
        result = locate_cards_to_watch([
            {"start": 500, "end": 520, "text": "My first pick this week is Example Card."},
            {"start": 700, "end": 760, "text": "My other pick is Second Card."},
            {"start": 900, "end": 930, "text": "We're going to break down the Chaos Vault experiment now."},
        ], title="MTG Fast Finance Ep 7", description=(
            "Price updates, cards to watch and a breakdown of the Secret Lair Chaos Vault experiment."
        ))
        self.assertEqual("advertised_topic_transition", result["end_signal"])
        self.assertEqual(760, result["end_seconds"])
        self.assertIsNone(result["review_reason"])

    def test_ff_implicit_start_without_independent_end_still_needs_review(self) -> None:
        result = locate_cards_to_watch([
            {"start": 400, "end": 420, "text": "What do you have for your first pick this week?"},
            {"start": 420, "end": 500, "text": "My pick is Example Card."},
            {"start": 500, "end": 600, "text": "We keep discussing prices."},
            {"start": 1700, "end": 1750, "text": "Unrelated closing discussion."},
        ], title="MTG Fast Finance Ep 3: Special Topic")
        self.assertTrue(result["located"])
        self.assertEqual("recommendation_language", result["start_signal"])
        self.assertIsNone(result["end_signal"])
        self.assertEqual(600, result["end_seconds"])
        self.assertIn("no explicit ending", result["review_reason"])

    def test_ff_outline_and_topic_end_without_positive_start_remain_reviewable(self) -> None:
        result = locate_cards_to_watch([
            {"start": 100, "end": 120, "text": "Today: meta updates, Cards to Watch, and a deep dive into SOS."},
            {"start": 700, "end": 800, "text": "Several cards changed price."},
            {"start": 900, "end": 930, "text": "Now let's get into our main topic and discuss SOS."},
        ], title="MTG Fast Finance Ep 4: SOS Brick Targets")
        self.assertEqual("show_outline_fallback", result["start_signal"])
        self.assertIsNone(result["end_signal"])
        self.assertEqual("low", result["confidence"])
        self.assertIn("show-outline", result["review_reason"])

    def test_brainstorm_recommendation_profile_finds_breaking_bulk(self) -> None:
        result = locate_recommendation_section([
            {"start": 100, "end": 110, "text": "Breaking Bulk"},
            {"start": 110, "end": 140, "text": "My pick is Example Card at a dollar."},
            {"start": 140, "end": 150, "text": "Thanks for listening"},
        ], "brainstorm_brewery")
        self.assertTrue(result["located"])
        self.assertEqual(("Breaking Bulk / Pick of the Week", "high"), (result["label"], result["confidence"]))

    def test_discovery_is_idempotent_and_failed_attempt_is_retryable(self) -> None:
        store = JsonStateStore(workspace_temp() / "state.json")
        candidate = episode()
        self.assertTrue(store.discover(candidate))
        self.assertFalse(store.discover(candidate))
        before = len(store.get(candidate.guid)["history"])
        store.transition(candidate.guid, "downloading")
        store.transition(candidate.guid, "failed", error={"stage": "downloading", "message": "boom", "retryable": True})
        self.assertEqual(1, store.get(candidate.guid)["attempt_count"])
        self.assertEqual(before + 2, len(store.get(candidate.guid)["history"]))

    def test_production_catalog_excludes_fixtures_and_reports_health(self) -> None:
        archive = workspace_temp() / "archive"
        for name, synthetic in (("fixture", True), ("real", False)):
            directory = archive / "episodes" / name
            metadata = {
                    "synthetic": synthetic,
                    "episode": {"guid": name, "episode_number": 1, "title": name, "published_at": "2026-01-01T00:00:00Z", "audio_url": "https://example.test/a", "episode_url": "https://example.test/e", "duration_seconds": 1, "hosts": [], "description": None},
                    "processing": {"status": "complete", "processed_at": "2026-01-02T00:00:00Z", "review_state": "approved", "review_reason": None, "error": None},
                    "outputs": {},
            }
            atomic_write_json(directory / "metadata.json", metadata)
            atomic_write_json(directory / "summary.json", {"recommendations": []})
        index, _ = rebuild_catalog(archive, production=True)
        self.assertFalse(index["synthetic"])
        self.assertEqual(["real"], [item["guid"] for item in index["episodes"]])
        self.assertEqual(1, index["metadata"]["real_episode_count"])
        self.assertIn("generated_at", index["metadata"])


    def test_catalog_merges_mixed_source_urls(self) -> None:
        archive = workspace_temp() / "archive"
        for name, source_url in (("legacy", None), ("current", "https://soundcloud.com/example")):
            directory = archive / "episodes" / name
            atomic_write_json(directory / "metadata.json", {
                "synthetic": False,
                "episode": {
                    "guid": name,
                    "episode_number": 1,
                    "title": name,
                    "published_at": "2026-01-01T00:00:00Z",
                    "audio_url": "https://example.test/audio",
                    "episode_url": "https://example.test/episode",
                    "duration_seconds": 1,
                    "hosts": [],
                    "description": None,
                    "source_id": "mtg-fast-finance",
                    "source_name": "MTG Fast Finance",
                    "source_url": source_url,
                },
                "processing": {
                    "status": "complete",
                    "processed_at": "2026-01-02T00:00:00Z",
                    "review_state": "approved",
                    "review_reason": None,
                    "error": None,
                },
                "outputs": {},
            })
            atomic_write_json(directory / "summary.json", {"recommendations": []})

        index, _ = rebuild_catalog(archive, production=True)

        self.assertEqual(2, index["metadata"]["real_episode_count"])
        self.assertEqual([{
            "id": "mtg-fast-finance",
            "name": "MTG Fast Finance",
            "url": "https://soundcloud.com/example",
        }], index["metadata"]["sources"])

class FrontendContractTests(unittest.TestCase):
    def test_pages_paths_and_failure_copy(self) -> None:
        root = Path(__file__).parents[1]
        app = (root / "web/app.js").read_text(encoding="utf-8")
        workflow = (root / ".github/workflows/ffw.yml").read_text(encoding="utf-8")
        self.assertIn("fetch(`archive/index.json", app)
        self.assertNotIn("../archive", app)
        self.assertIn("automated pipeline may be updating", app)
        self.assertNotIn("python -m ffw", app)
        self.assertIn("data-episode-guid", app)
        self.assertIn("web/table.js", workflow)
        self.assertIn("web/review.html", workflow)
        self.assertIn("web/review.js", workflow)
        self.assertIn("web/audio-player.js", workflow)
        self.assertIn("function showEpisode", app)
        self.assertIn("View failure details", app)
        self.assertIn("data-copy-guid", app)
        self.assertIn("Open retry workflow", app)
        self.assertIn("Review episode", app)
        self.assertIn("episodeReviewUrl", app)
        self.assertIn("function closeDialogOrBack", app)
        self.assertIn('showEpisode(dialogState.episodeGuid, { returning: true, focusPickId: dialogState.pickId })', app)
        self.assertIn('dialog.addEventListener("cancel",', app)
        self.assertIn('"Back to episode picks"', app)
        self.assertIn('episodeSort: { key: "processed_at", direction: "desc" }', app)
        self.assertIn('data-episode-sort', app)
        self.assertIn('Added within the last 72 hours', app)
        self.assertIn("<h2>Recently added</h2>", app)
        self.assertIn("state.index.episodes.filter(isSuccessfulEpisode)", app)
        self.assertIn('return isSuccessfulEpisode(episode) ? "Added" : "Attempted"', app)
        self.assertIn('id="episode-source"', app)
        self.assertIn('id="pick-source"', app)
        self.assertIn('function sourceFilterOptions', app)
        self.assertIn('sourceId(episode) === state.episodeSource', app)
        self.assertIn('sourceId(pick) === state.pickSource', app)
        table = (root / "web/table.js").read_text(encoding="utf-8")
        self.assertIn("data-ms-sort", table)
        self.assertIn("aria-sort", table)
        self.assertNotIn("Unavailable", app)
        review_page = (root / "web/review.html").read_text(encoding="utf-8")
        review_app = (root / "web/review.js").read_text(encoding="utf-8")
        review_workflow = (root / ".github/workflows/review.yml").read_text(encoding="utf-8")
        self.assertIn("Human review", review_page)
        self.assertIn("Prepare review payload", review_app)
        self.assertIn('action: "exclude"', review_app)
        self.assertIn('action: "update"', review_app)
        self.assertIn('action: "add"', review_app)
        self.assertIn("review_payload", review_workflow)
        self.assertIn("apply-review", review_workflow)
        self.assertIn("git add data/reviews archive", review_workflow)

    def test_timestamp_playback_helpers_and_entry_points(self) -> None:
        root = Path(__file__).parents[1]
        player = root / "web/audio-player.js"
        if shutil.which("node") is None:
            self.skipTest("Node is required for the frontend helper contract test")
        script = (
            f"const p=require({json.dumps(str(player))});"
            "console.log(JSON.stringify({"
            "seconds:p.parseTime('01:02:03'),short:p.parseTime('12:34'),"
            "invalid:p.parseTime('12:99'),clamped:p.clampTime(120,90),"
            "unbounded:p.clampTime(120,NaN),formatted:p.formatTime(3723)}));"
        )
        completed = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True,
        )
        self.assertEqual(
            {
                "seconds": 3723,
                "short": 754,
                "invalid": None,
                "clamped": 89.75,
                "unbounded": 120,
                "formatted": "01:02:03",
            },
            json.loads(completed.stdout),
        )
        summary = (root / "web/summary.js").read_text(encoding="utf-8")
        review = (root / "web/review.js").read_text(encoding="utf-8")
        app = (root / "web/app.js").read_text(encoding="utf-8")
        self.assertIn('params.get("t")', summary)
        self.assertIn('params.get("pick")', summary)
        self.assertIn("data-listen-seconds", summary)
        self.assertIn("data-review-listen", review)
        self.assertIn("pickSummaryUrl", app)
        self.assertIn("episodeListenUrl", app)
        self.assertIn("function scryfallUrl", summary)
        self.assertIn("function scryfallUrl", review)
        self.assertIn("function scryfallUrl", app)
        self.assertIn("cardPreview(pick)", review)
        self.assertIn("cardPreview(pick)", app)

    def test_workflow_defaults_and_limit_guard_are_safe(self) -> None:
        workflow = (Path(__file__).parents[1] / ".github/workflows/ffw.yml").read_text(encoding="utf-8")
        self.assertIn("default: next", workflow)
        self.assertIn('default: "1"', workflow)
        self.assertIn("batch_size must be a positive integer", workflow)
        self.assertIn("exceeds the safety cap", workflow)
        self.assertIn("gemini-3.5-flash", workflow)
        self.assertIn("gemini-3.5-flash-lite", workflow)
        self.assertIn("ai_model:", workflow)
        self.assertIn("inputs.ai_model || 'gemini-3.5-flash'", workflow)
        self.assertIn('FFW_GEMINI_TRANSIENT_RETRIES: "2"', workflow)
        self.assertIn('FFW_GEMINI_RETRY_DELAY_SECONDS: "30"', workflow)
        self.assertIn("FFW_TRANSCRIPTION_PROVIDER_FALLBACK: openai", workflow)
        self.assertIn("Decide Pages publication", workflow)
        self.assertIn("needs.publish.outputs.pages_ready == 'true'", workflow)
        self.assertIn("DURABLE_CHANGED", workflow)
        self.assertIn('FFW_AUDIO_CHUNK_SECONDS: "900"', workflow)
        self.assertIn('cron: "17 20 * * *"', workflow)
        self.assertIn('INPUT_MODE="evening"', workflow)
        self.assertIn('FFW_MAX_EPISODE_ATTEMPTS: "3"', workflow)
        self.assertIn("deploy_only", workflow)
        self.assertIn("retry_failed", workflow)
        self.assertIn("evening-run --live", workflow)
        self.assertIn("Selected mode", workflow)
        self.assertIn('- "src/**"', workflow)
        self.assertIn('- "tests/**"', workflow)
        self.assertIn('- "schemas/**"', workflow)
        self.assertIn('- "pyproject.toml"', workflow)
        self.assertIn("brainstorm-brewery", workflow)
        self.assertIn('FFW_ENABLED_SOURCES: "mtg-fast-finance,brainstorm-brewery"', workflow)
        self.assertIn("process-next --live", workflow)
        self.assertIn("Deploy-only mode selected", workflow)
        self.assertIn("validation and durable-state persistence will continue", workflow)
        self.assertIn("Report pipeline failure", workflow)
        self.assertIn("Publish deployment summary", workflow)
        self.assertNotIn("0 means all", workflow)


class ProductionPipelineTests(unittest.TestCase):
    def test_live_provider_selection_is_swappable(self) -> None:
        root = workspace_temp()
        base = {
            "root": root,
            "archive_dir": root / "archive",
            "state_file": root / "state/episodes.json",
            "work_dir": root / ".ffw-work",
            "mode": "live",
        }
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}, clear=False):
            settings = Settings(
                **base,
                ai_provider="gemini",
                transcription_model="gemini-t",
                transcription_fallback_model="gemini-t-fallback",
                extraction_model="gemini-e",
            )
            _, _, _, transcriber, extractor = production_adapters(settings)
            self.assertIsInstance(transcriber, GeminiTranscriber)
            self.assertIsInstance(extractor, GeminiExtractor)
            self.assertEqual(("gemini-t", "gemini-e"), (transcriber.model_name, extractor.model_name))
            self.assertEqual("gemini-t-fallback", transcriber.fallback_model_name)
        settings = Settings(**base, ai_provider="openai", transcription_model="openai-t", extraction_model="openai-e")
        _, _, _, transcriber, extractor = production_adapters(settings)
        self.assertIsInstance(transcriber, OpenAITranscriber)
        self.assertIsInstance(extractor, OpenAIExtractor)

    def test_gemini_transcription_retries_then_uses_configured_fallback(self) -> None:
        transcriber = GeminiTranscriber(
            "gemini-primary",
            1200,
            fallback_model_name="gemini-fallback",
            transient_retries=1,
            retry_delay_seconds=0,
        )
        success = {"text": "Cards to Watch", "segments": [], "_usage": None}
        with patch(
            "ffw.production._gemini_generate_json",
            side_effect=[RuntimeError("503 UNAVAILABLE"), RuntimeError("503 UNAVAILABLE"), success],
        ) as generate:
            payload, model = transcriber._transcribe_chunk(object(), object(), ["audio"])

        self.assertEqual(success, payload)
        self.assertEqual("gemini-fallback", model)
        self.assertEqual(
            ["gemini-primary", "gemini-primary", "gemini-fallback"],
            [item.kwargs["model"] for item in generate.call_args_list],
        )

    def test_gemini_transcription_uses_exponential_backoff(self) -> None:
        transcriber = GeminiTranscriber(
            "gemini-primary", 900, transient_retries=2, retry_delay_seconds=30,
        )
        success = {"text": "Cards to Watch", "segments": [], "_usage": None}
        with (
            patch("ffw.production._gemini_generate_json", side_effect=[RuntimeError("503"), RuntimeError("429"), success]),
            patch("ffw.production.time.sleep") as sleep,
        ):
            payload, model = transcriber._transcribe_chunk(object(), object(), ["audio"])
        self.assertEqual(success, payload)
        self.assertEqual("gemini-primary", model)
        self.assertEqual([call(30), call(60)], sleep.call_args_list)

    def test_transient_gemini_failure_uses_openai_in_same_episode_attempt(self) -> None:
        class Primary:
            def transcribe(self, episode, audio_files):
                raise RuntimeError("503 UNAVAILABLE")

        class Fallback:
            def transcribe(self, episode, audio_files):
                return {"provider": "OpenAI", "text": "recovered", "segments": []}

        transcript = ProviderFallbackTranscriber(Primary(), Fallback()).transcribe(episode(), [])
        self.assertEqual("OpenAI", transcript["provider"])
        self.assertTrue(transcript["provider_fallback"]["used"])
        self.assertIn("503 UNAVAILABLE", transcript["provider_fallback"]["primary_error"])

    def test_permanent_gemini_failure_does_not_cross_provider_boundary(self) -> None:
        fallback = Mock()
        primary = Mock()
        primary.transcribe.side_effect = RuntimeError("404 NOT_FOUND model unavailable")
        with self.assertRaisesRegex(RuntimeError, "404 NOT_FOUND"):
            ProviderFallbackTranscriber(primary, fallback).transcribe(episode(), [])
        fallback.transcribe.assert_not_called()

    def test_gemini_adapter_enables_openai_fallback_when_secret_is_available(self) -> None:
        root = workspace_temp()
        settings = Settings(
            root, root / "archive", root / "state/episodes.json", root / ".ffw-work",
            mode="live", ai_provider="gemini", transcription_model="gemini-primary",
            transcription_provider_fallback="openai", openai_transcription_model="openai-transcribe",
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini", "OPENAI_API_KEY": "openai"}, clear=False):
            _, _, _, transcriber, _ = production_adapters(settings)
        self.assertIsInstance(transcriber, ProviderFallbackTranscriber)
        self.assertIsInstance(transcriber.primary, GeminiTranscriber)
        self.assertIsInstance(transcriber.fallback, OpenAITranscriber)
        self.assertEqual("openai-transcribe", transcriber.fallback.model_name)

    def test_gemini_transcription_retries_malformed_json_then_uses_fallback(self) -> None:
        transcriber = GeminiTranscriber(
            "gemini-primary",
            900,
            fallback_model_name="gemini-fallback",
            transient_retries=1,
            retry_delay_seconds=0,
        )
        malformed = GeminiMalformedJSONError("Gemini returned malformed JSON (unterminated string).")
        success = {"text": "Breaking Bulk", "segments": [], "_usage": None}
        with patch(
            "ffw.production._gemini_generate_json",
            side_effect=[malformed, malformed, success],
        ) as generate:
            payload, model = transcriber._transcribe_chunk(object(), object(), ["audio"])

        self.assertEqual(success, payload)
        self.assertEqual("gemini-fallback", model)
        self.assertEqual(
            ["gemini-primary", "gemini-primary", "gemini-fallback"],
            [item.kwargs["model"] for item in generate.call_args_list],
        )

    def test_gemini_malformed_json_reports_finish_reason_without_schema_downgrade(self) -> None:
        class Reason:
            value = "MAX_TOKENS"

        class Response:
            text = '{"text":"unfinished'
            candidates = [type("Candidate", (), {"finish_reason": Reason()})()]
            usage_metadata = None

        class Models:
            def __init__(self): self.calls = 0
            def generate_content(self, **kwargs):
                self.calls += 1
                return Response()

        class Client:
            models = Models()

        class Types:
            class GenerateContentConfig:
                def __init__(self, **kwargs): self.kwargs = kwargs

        client = Client()
        with self.assertRaisesRegex(GeminiMalformedJSONError, "MAX_TOKENS"):
            _gemini_generate_json(client, Types, model="gemini", contents=["audio"], schema={"type": "object"})
        self.assertEqual(1, client.models.calls)

    def test_malformed_json_failure_is_retryable_without_stopping_other_sources(self) -> None:
        self.assertEqual(
            ("transient_model_output", True, False),
            classify_failure("Gemini returned malformed JSON (unterminated string)."),
        )

    def test_gemini_transcription_does_not_hide_permanent_primary_failure(self) -> None:
        transcriber = GeminiTranscriber(
            "gemini-primary",
            1200,
            fallback_model_name="gemini-fallback",
            retry_delay_seconds=0,
        )
        with patch(
            "ffw.production._gemini_generate_json",
            side_effect=RuntimeError("404 NOT_FOUND model unavailable"),
        ) as generate:
            with self.assertRaisesRegex(RuntimeError, "404 NOT_FOUND"):
                transcriber._transcribe_chunk(object(), object(), ["audio"])
        self.assertEqual(1, generate.call_count)

    def test_gemini_transcription_exhaustion_remains_retryable(self) -> None:
        transcriber = GeminiTranscriber(
            "gemini-primary",
            1200,
            fallback_model_name="gemini-fallback",
            transient_retries=0,
            retry_delay_seconds=0,
        )
        with patch(
            "ffw.production._gemini_generate_json",
            side_effect=[RuntimeError("503 UNAVAILABLE"), RuntimeError("503 UNAVAILABLE")],
        ):
            with self.assertRaisesRegex(RuntimeError, "models exhausted") as raised:
                transcriber._transcribe_chunk(object(), object(), ["audio"])
        self.assertEqual(("transient_provider", True, True), classify_failure(str(raised.exception)))

    def test_live_run_requires_positive_limit(self) -> None:
        root = workspace_temp()
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work", mode="live")

        class Feed:
            def episodes(self): return [episode()]

        pipeline = Pipeline(settings, Feed(), object(), object(), object(), object(), JsonStateStore(settings.state_file))
        with self.assertRaisesRegex(ValueError, "positive --limit"):
            pipeline.run()
        with self.assertRaisesRegex(ValueError, "at least 1"):
            pipeline.run(limit=0)
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            pipeline.run(limit=settings.max_live_batch + 1)

    def test_provider_wide_failure_stops_live_batch(self) -> None:
        root = workspace_temp()
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work", mode="live")
        candidates = [
            EpisodeCandidate(f"guid-{index}", 50 + index, f"Episode {index}", f"2026-01-0{index}T00:00:00Z", "https://cdn.example.test/audio.mp3", "https://example.test/e", [])
            for index in range(1, 4)
        ]

        class Feed:
            def episodes(self): return candidates

        class Downloader:
            def download(self, item, destination):
                path = destination.with_suffix(".mp3")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"temporary audio")
                return path

        class Audio:
            def prepare(self, source, destination): return [source]

        class Transcriber:
            model_name = "bad-model"
            def transcribe(self, item, files):
                raise RuntimeError("404 NOT_FOUND. model is not available")

        class Extractor:
            model_name = "unused"

        pipeline = Pipeline(settings, Feed(), Downloader(), Audio(), Transcriber(), Extractor(), JsonStateStore(settings.state_file))
        results = pipeline.run(limit=3, selection_policy="backfill")
        self.assertEqual(1, len(results))
        self.assertEqual("failed", results[0].status)
        records = pipeline.state.all()
        self.assertEqual(["guid-3"], sorted(records))
        self.assertFalse(records["guid-3"]["error"]["retryable"])

    def test_episode_specific_failure_does_not_stop_limited_batch(self) -> None:
        root = workspace_temp()
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work", mode="live")
        candidates = [
            EpisodeCandidate("guid-1", 1, "Episode 1", "2026-01-01T00:00:00Z", "https://cdn.example.test/1.mp3", "https://example.test/1", []),
            EpisodeCandidate("guid-2", 2, "Episode 2", "2026-01-02T00:00:00Z", "https://cdn.example.test/2.mp3", "https://example.test/2", []),
        ]

        class Feed:
            def episodes(self): return candidates

        class Downloader:
            def download(self, item, destination):
                if item.guid == "guid-1":
                    raise ValueError("Audio exceeds configured maximum size.")
                path = destination.with_suffix(".mp3")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"temporary audio")
                return path

        class Audio:
            def prepare(self, source, destination): return [source]

        class Transcriber:
            model_name = "test-transcriber"
            def transcribe(self, item, files): return {"provider": "test", "segments": [], "chunk_count": 1}

        class Extractor:
            model_name = "test-extractor"
            def extract(self, item, transcript):
                return {"section": {"located": True, "start_seconds": 600, "end_seconds": 630, "label": "Cards to Watch", "confidence": "high", "review_reason": None}, "recommendations": [{
                    "card": "Real Card", "printing": None, "printing_certainty": None,
                    "foil": None, "hosts": [], "recommendation": "Watch for an entry.",
                    "mentioned_price": None, "entry_target": None, "hold": None, "exit_target": None,
                    "reasoning": ["Supply was discussed."], "caveats": [], "confidence": None,
                    "start_seconds": 600, "end_seconds": 630, "evidence_excerpt": "Short evidence.",
                    "review_status": "approved", "review_reason": None,
                }], "review_reason": None}

        pipeline = Pipeline(settings, Feed(), Downloader(), Audio(), Transcriber(), Extractor(), JsonStateStore(settings.state_file))
        results = pipeline.run(limit=2, selection_policy="backfill")
        self.assertEqual(["complete", "failed"], [item.status for item in results])
        error = pipeline.state.get("guid-1")["error"]
        self.assertFalse(error["retryable"])
        self.assertEqual("episode_input", error["category"])
        self.assertTrue(error["quarantined"])

    def test_targeted_second_listen_accepts_only_catalog_verified_card_name(self) -> None:
        root = workspace_temp()
        audio = root / "chunk-000.mp3"
        audio.write_bytes(b"audio")

        class Resolver:
            def resolve(self, name):
                if name == "Old Name":
                    return {"status": "suggested", "canonical_name": "Correct Name"}
                if name == "Correct Name":
                    return {"status": "verified", "canonical_name": "Correct Name"}
                return {"status": "not_found", "canonical_name": None}

        fake_genai = stdlib_types.ModuleType("google.genai")
        fake_genai.Client = lambda **kwargs: object()
        fake_genai.types = stdlib_types.SimpleNamespace(
            Part=stdlib_types.SimpleNamespace(from_bytes=lambda **kwargs: kwargs),
        )
        fake_google = stdlib_types.ModuleType("google")
        fake_google.genai = fake_genai
        extraction = {
            "review_reason": "Likely transcription error in a card name.",
            "recommendations": [{
                "card": "Old Name", "start_seconds": 30, "review_status": "needs_review",
                "review_reason": "Possible transcription error in card name.",
            }],
        }
        verifier = GeminiPickVerifier("verify-model", 900, Resolver())

        def create_clip(source, destination, relative_seconds):
            destination.write_bytes(b"clip")
            return destination

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch.dict(sys.modules, {"google": fake_google, "google.genai": fake_genai}),
            patch.object(verifier, "_clip", side_effect=create_clip),
            patch("ffw.verification._gemini_generate_json", return_value={
                "decision": "corrected", "card": "Correct Name", "explanation": "Clearly spoken.",
                "_usage": None,
            }),
        ):
            result = verifier.verify(episode(), extraction, [audio])

        pick = result["recommendations"][0]
        self.assertEqual("Correct Name", pick["card"])
        self.assertEqual("approved", pick["review_status"])
        self.assertTrue(pick["automated_verification"]["accepted"])
        self.assertIsNone(result["review_reason"])
    def test_reprocessing_comparison_reports_material_pick_changes(self) -> None:
        before = {
            "episode": {"guid": "episode-guid"},
            "processing": {"status": "needs_review"},
            "recommendations": [
                {"card": "Old Name", "review_status": "needs_review", "start_seconds": 10},
                {"card": "Stable Card", "review_status": "approved", "start_seconds": 20},
            ],
        }
        after = {
            "episode": {"guid": "episode-guid"},
            "processing": {"status": "complete"},
            "recommendations": [
                {"card": "Correct Name", "review_status": "approved", "start_seconds": 10},
                {"card": "Stable Card", "review_status": "approved", "start_seconds": 25},
            ],
        }

        report = compare_episode_summaries(before, after)

        self.assertEqual(["Correct Name"], report["added_cards"])
        self.assertEqual(["Old Name"], report["removed_cards"])
        self.assertEqual([{"card": "Stable Card", "fields": ["start_seconds"]}], report["changed_picks"])
        self.assertEqual(("needs_review", "complete"), (report["before_status"], report["after_status"]))

    def test_forced_zero_pick_reprocess_preserves_nonzero_published_summary(self) -> None:
        root = workspace_temp()
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work", mode="live")
        candidate = episode()

        class Feed:
            def episodes(self): return [candidate]

        class Downloader:
            def download(self, item, destination):
                path = destination.with_suffix(".mp3")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"temporary audio")
                return path

        class Audio:
            def prepare(self, source, destination): return [source]

        class Transcriber:
            model_name = "test-transcriber"
            def transcribe(self, item, files): return {"provider": "test", "segments": [], "chunk_count": 1}

        class Extractor:
            model_name = "test-extractor"
            empty = False

            def extract(self, item, transcript):
                section = {
                    "located": True, "start_seconds": 600, "end_seconds": 700,
                    "label": "Cards to Watch", "confidence": "high", "review_reason": None,
                }
                if self.empty:
                    return {"section": section, "recommendations": [], "review_reason": "No picks found."}
                return {"section": section, "recommendations": [{
                    "card": "Preserved Card", "printing": None, "printing_certainty": None,
                    "foil": None, "hosts": [], "recommendation": "Watch for an entry.",
                    "mentioned_price": None, "entry_target": None, "hold": None, "exit_target": None,
                    "reasoning": ["Supply was discussed."], "caveats": [], "confidence": None,
                    "start_seconds": 620, "end_seconds": 650, "evidence_excerpt": "Short evidence.",
                    "review_status": "approved", "review_reason": None,
                }], "review_reason": None}

        extractor = Extractor()
        pipeline = Pipeline(
            settings, Feed(), Downloader(), Audio(), Transcriber(), extractor,
            JsonStateStore(settings.state_file),
        )
        first = pipeline.process_episode(candidate)
        extractor.empty = True
        second = pipeline.process_episode(candidate, force=True)

        summary = load_json(settings.archive_dir / first.output_directory / "summary.json")
        report = load_json(settings.work_dir / "reprocess-reports" / "0042-episode-42.json")
        state = pipeline.state.get(candidate.guid)
        self.assertEqual(("complete", 1), (first.status, first.pick_count))
        self.assertEqual(("needs_review", 1), (second.status, second.pick_count))
        self.assertEqual(["Preserved Card"], [pick["card"] for pick in summary["recommendations"]])
        self.assertIn("previous recommendations were retained", summary["processing"]["review_reason"])
        self.assertEqual((1, False, True), (
            state["pick_count"], report["published"], report["preserved_previous"],
        ))
    def test_real_five_pick_publication_cleanup_and_idempotent_skip(self) -> None:
        root = workspace_temp()
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work", mode="live", retain_transcripts=True)
        candidate = episode()

        class Feed:
            def episodes(self): return [candidate]

        class Downloader:
            def download(self, item, destination):
                path = destination.with_suffix(".mp3")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"temporary audio")
                return path

        class Audio:
            def prepare(self, source, destination): return [source]

        class Transcriber:
            model_name = "test-transcriber"
            def transcribe(self, item, files): return {"provider": "test", "segments": [], "chunk_count": 1}

        class Extractor:
            model_name = "test-extractor"
            calls = 0
            def extract(self, item, transcript):
                self.calls += 1
                picks = []
                for index in range(5):
                    picks.append({
                        "card": f"Real Card {index + 1}", "printing": None, "printing_certainty": None,
                        "foil": None, "hosts": [], "recommendation": "Watch for an entry.",
                        "mentioned_price": None, "entry_target": None, "hold": None, "exit_target": None,
                        "reasoning": ["Supply was discussed."], "caveats": [], "confidence": None,
                        "start_seconds": 600 + index * 60, "end_seconds": 630 + index * 60,
                        "evidence_excerpt": f"Short evidence for card {index + 1}.", "review_status": "approved",
                        "review_reason": None,
                    })
                return {"section": {"located": True, "start_seconds": 600, "end_seconds": 930, "label": "Cards to Watch", "confidence": "medium", "review_reason": "No explicit section ending was detected."}, "recommendations": picks, "review_reason": None}

        extractor = Extractor()
        pipeline = Pipeline(settings, Feed(), Downloader(), Audio(), Transcriber(), extractor, JsonStateStore(settings.state_file))
        result = pipeline.run(limit=1)[0]
        self.assertEqual(("complete", 5), (result.status, result.pick_count), result.message)
        summary = load_json(settings.archive_dir / result.output_directory / "summary.json")
        self.assertFalse(summary["synthetic"])
        self.assertEqual(5, len(summary["recommendations"]))
        transcript_paths = list((settings.work_dir / "transcripts").glob("*.json.gz"))
        self.assertEqual(1, len(transcript_paths))
        with gzip.open(transcript_paths[0], "rt", encoding="utf-8") as source:
            retained = json.load(source)
        self.assertEqual(candidate.guid, retained["episode"]["guid"])
        self.assertEqual("test", retained["transcript"]["provider"])
        second = pipeline.run(limit=1)
        self.assertEqual([], second)
        self.assertEqual(1, pipeline.last_selection.completed_skipped)
        self.assertEqual(1, extractor.calls)


class StateAwareSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = workspace_temp()
        self.settings = Settings(
            self.root,
            self.root / "archive",
            self.root / "state/episodes.json",
            self.root / ".ffw-work",
            mode="live",
        )
        self.state = JsonStateStore(self.settings.state_file)
        self.pipeline = Pipeline(self.settings, object(), object(), object(), object(), object(), self.state)

    @staticmethod
    def candidates() -> list[EpisodeCandidate]:
        return [
            EpisodeCandidate(f"guid-{index}", index, f"Episode {index}", f"2026-01-0{index}T00:00:00Z", f"https://cdn.example.test/{index}.mp3", f"https://example.test/{index}", [])
            for index in range(1, 7)
        ]

    def set_status(self, candidate: EpisodeCandidate, status: str) -> None:
        self.state.discover(candidate)
        updates = {"error": {"retryable": True, "next_retry_at": None}} if status == "failed" else {}
        self.state.transition(candidate.guid, status, **updates)

    def test_next_selects_newest_unseen_after_completed_and_failed(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[5], "complete")
        self.set_status(candidates[4], "needs_review")
        self.set_status(candidates[3], "failed")
        report = self.pipeline.select_candidates(candidates, policy="next")
        self.assertEqual(["guid-3"], [item.guid for item in report.selected])
        self.assertEqual((2, 1, 1, 4), (
            report.completed_skipped,
            report.failed_skipped,
            report.eligible_found,
            report.feed_entries_scanned,
        ))

    def test_source_filter_selects_newest_from_requested_podcast(self) -> None:
        self.settings = Settings(**{**self.settings.__dict__, "enabled_sources": ("mtg-fast-finance", "brainstorm-brewery")})
        self.pipeline.settings = self.settings
        ffw = EpisodeCandidate("ffw", 1, "FFW", "2026-01-06T00:00:00Z", "https://cdn.example.test/f.mp3", "https://example.test/f", [])
        bb = EpisodeCandidate(
            "brainstorm-brewery:bb", 700, "BB", "2026-01-05T00:00:00Z",
            "https://cdn.example.test/b.mp3", "https://example.test/b", [],
            source_id="brainstorm-brewery", source_name="Brainstorm Brewery", extraction_profile="brainstorm_brewery",
        )
        report = self.pipeline.select_candidates([ffw, bb], policy="next", source_id="brainstorm-brewery")
        self.assertEqual([bb], report.selected)

    def test_backfill_limit_counts_eligible_not_feed_positions(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[5], "complete")
        self.set_status(candidates[4], "needs_review")
        self.set_status(candidates[3], "failed")
        report = self.pipeline.select_candidates(candidates, policy="backfill", limit=2)
        self.assertEqual(["guid-3", "guid-2"], [item.guid for item in report.selected])
        self.assertEqual(2, len(report.selected))

    def test_failed_only_never_selects_unseen_and_respects_limit(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[4], "failed")
        self.set_status(candidates[1], "failed")
        report = self.pipeline.select_candidates(candidates, policy="failed_only", limit=1)
        self.assertEqual(["guid-5"], [item.guid for item in report.selected])
        self.assertEqual(1, report.eligible_found)
        self.assertEqual(2, report.feed_entries_scanned)

    def test_evening_prefers_one_due_retry_over_newer_unseen_episode(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[4], "failed")

        report = self.pipeline.select_candidates(candidates, policy="retry_then_next")

        self.assertEqual(["guid-5"], [item.guid for item in report.selected])
        self.assertEqual("retry_failed", report.selected_mode)
        self.assertEqual(1, len(report.selected))

    def test_evening_falls_back_to_one_untouched_episode_when_no_retry_is_due(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[5], "complete")
        self.set_status(candidates[4], "failed")
        self.state.transition(candidates[4].guid, "failed", error={
            "retryable": True,
            "next_retry_at": "2999-01-01T00:00:00Z",
        })

        report = self.pipeline.select_candidates(candidates, policy="retry_then_next")

        self.assertEqual(["guid-4"], [item.guid for item in report.selected])
        self.assertEqual("next_fallback", report.selected_mode)
        self.assertEqual(1, report.retry_deferred)
        self.assertEqual(1, len(report.selected))

    def test_evening_noops_when_neither_retry_nor_untouched_episode_exists(self) -> None:
        candidates = self.candidates()
        for candidate in candidates:
            self.set_status(candidate, "complete")

        report = self.pipeline.select_candidates(candidates, policy="retry_then_next")

        self.assertEqual([], report.selected)
        self.assertIsNone(report.selected_mode)
        self.assertEqual(0, report.eligible_found)

    def test_evening_run_processes_only_the_retry_candidate(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[4], "failed")

        class Feed:
            def episodes(self): return candidates

        pipeline = Pipeline(self.settings, Feed(), object(), object(), object(), object(), self.state)
        result = PipelineResult("guid-5", "complete", pick_count=1)
        with patch.object(pipeline, "process_episode", return_value=result) as process, patch("ffw.pipeline.rebuild_catalog"):
            results = pipeline.run(selection_policy="retry_then_next")

        self.assertEqual([result], results)
        process.assert_called_once()
        self.assertEqual("guid-5", process.call_args.args[0].guid)
        self.assertTrue(process.call_args.kwargs["retry_failed"])

    def test_evening_run_processes_only_the_newest_untouched_fallback(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[5], "complete")

        class Feed:
            def episodes(self): return candidates

        pipeline = Pipeline(self.settings, Feed(), object(), object(), object(), object(), self.state)
        result = PipelineResult("guid-5", "complete", pick_count=1)
        with patch.object(pipeline, "process_episode", return_value=result) as process, patch("ffw.pipeline.rebuild_catalog"):
            results = pipeline.run(selection_policy="retry_then_next")

        self.assertEqual([result], results)
        process.assert_called_once()
        self.assertEqual("guid-5", process.call_args.args[0].guid)
        self.assertFalse(process.call_args.kwargs["retry_failed"])

    def test_exact_guid_searches_full_feed_and_bypasses_position_limit(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[0], "complete")
        report = self.pipeline.select_candidates(candidates, policy="exact_guid", limit=1, force_guid="guid-1")
        self.assertEqual(6, report.feed_entries_scanned)
        self.assertEqual(["guid-1"], [item.guid for item in report.selected])

    def test_automatic_selection_skips_very_old_episodes_but_exact_guid_can_override(self) -> None:
        recent = self.candidates()[-1]
        old = EpisodeCandidate(
            "guid-old", 36, "Episode 36", "2016-10-09T00:00:00Z",
            "https://cdn.example.test/old.mp3", "https://example.test/old", [],
        )

        progressive = self.pipeline.select_candidates([old, recent], policy="next")
        automatic = self.pipeline.select_candidates([old], policy="next")
        explicit = self.pipeline.select_candidates(
            [old, recent], policy="exact_guid", force_guid="guid-old",
        )

        self.assertEqual([recent], progressive.selected)
        self.assertEqual([], automatic.selected)
        self.assertEqual(1, automatic.age_skipped)
        self.assertEqual([old], explicit.selected)
    def test_reordered_feed_and_new_release_keep_guid_identity(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[5], "complete")
        reordered = [candidates[1], candidates[5], candidates[0], candidates[4], candidates[2], candidates[3]]
        first = self.pipeline.select_candidates(reordered, policy="next")
        self.assertEqual("guid-5", first.selected[0].guid)
        self.set_status(candidates[4], "complete")
        new_release = EpisodeCandidate("guid-7", 7, "Episode 7", "2026-01-07T00:00:00Z", "https://cdn.example.test/7.mp3", "https://example.test/7", [])
        second = self.pipeline.select_candidates(reordered + [new_release], policy="next")
        self.assertEqual("guid-7", second.selected[0].guid)
        self.set_status(new_release, "complete")
        resumed = self.pipeline.select_candidates(reordered + [new_release], policy="next")
        self.assertEqual("guid-4", resumed.selected[0].guid)

    def test_duplicate_guid_does_not_consume_eligible_batch_limit(self) -> None:
        candidates = self.candidates()
        duplicate = EpisodeCandidate("guid-6", 6, "Duplicate Episode 6", "2026-01-06T00:00:00Z", "https://cdn.example.test/duplicate.mp3", "https://example.test/duplicate", [])
        report = self.pipeline.select_candidates([duplicate, *candidates], policy="backfill", limit=2)
        self.assertEqual(2, report.feed_entries_scanned)
        self.assertEqual(["guid-6", "guid-5"], [item.guid for item in report.selected])

    def test_failed_only_defers_cooldown_and_quarantines_exhausted_attempts(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[5], "failed")
        self.state.transition(candidates[5].guid, "failed", error={
            "retryable": True,
            "next_retry_at": "2999-01-01T00:00:00Z",
        })
        self.set_status(candidates[4], "failed")
        for _ in range(self.settings.max_episode_attempts):
            self.state.transition(candidates[4].guid, "downloading")
            self.state.transition(candidates[4].guid, "failed", error={"retryable": True, "next_retry_at": None})
        self.set_status(candidates[3], "failed")

        report = self.pipeline.select_candidates(candidates, policy="failed_only", limit=1)

        self.assertEqual(["guid-4"], [item.guid for item in report.selected])
        self.assertEqual(1, report.retry_deferred)
        self.assertEqual(1, report.retry_exhausted)

    def test_noop_does_not_call_expensive_adapters_or_rebuild_catalog(self) -> None:
        candidate = self.candidates()[-1]
        self.set_status(candidate, "complete")
        self.settings.archive_dir.mkdir(parents=True)
        index = self.settings.archive_dir / "index.json"
        index.write_text('{"sentinel": true}\n', encoding="utf-8")
        before_state = self.settings.state_file.read_text(encoding="utf-8")

        class Feed:
            def episodes(self): return [candidate]

        class MustNotRun:
            def __getattr__(self, name):
                raise AssertionError(f"expensive adapter called: {name}")

        pipeline = Pipeline(self.settings, Feed(), MustNotRun(), MustNotRun(), MustNotRun(), MustNotRun(), self.state)
        self.assertEqual([], pipeline.run(selection_policy="next"))
        self.assertEqual([], pipeline.run(selection_policy="retry_then_next"))
        self.assertEqual('{"sentinel": true}\n', index.read_text(encoding="utf-8"))
        self.assertEqual(before_state, self.settings.state_file.read_text(encoding="utf-8"))

    def test_live_batch_limits_reject_zero_negative_and_over_cap(self) -> None:
        for invalid in (0, -1, self.settings.max_live_batch + 1):
            with self.subTest(limit=invalid), self.assertRaises(ValueError):
                self.pipeline.run(selection_policy="backfill", limit=invalid)


class FailureClassificationTests(unittest.TestCase):
    def test_quota_and_disconnect_are_retryable_provider_failures(self) -> None:
        self.assertEqual(("transient_provider", True, True), classify_failure("429 RESOURCE_EXHAUSTED"))
        self.assertEqual(("transient_provider", True, True), classify_failure("Server disconnected without sending a response."))

    def test_configuration_and_bad_audio_are_not_retried(self) -> None:
        self.assertEqual(("provider_configuration", False, True), classify_failure("403 PERMISSION_DENIED invalid API key"))
        self.assertEqual(("episode_input", False, False), classify_failure("Downloaded audio was empty."))


if __name__ == "__main__":
    unittest.main()
