from __future__ import annotations

import hashlib
import io
import os
import unittest
import uuid
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from ffw.archive import rebuild_catalog
from ffw.detection import locate_cards_to_watch
from ffw.models import EpisodeCandidate
from ffw.config import Settings
from ffw.pipeline import Pipeline, classify_failure
from ffw.production import GeminiExtractor, GeminiTranscriber, OpenAIExtractor, OpenAITranscriber, StreamingDownloader, parse_episode_number, parse_rss, production_adapters
from ffw.state import JsonStateStore
from ffw.utils import atomic_write_json, load_json


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
            {"start": 30, "end": 40, "text": "Thanks for listening"},
            {"start": 20, "end": 30, "text": "The card is Example Card"},
            {"start": 10, "end": 20, "text": "Cards to Watch"},
        ])
        self.assertTrue(result["located"])
        self.assertEqual((10, 40, "high"), (result["start_seconds"], result["end_seconds"], result["confidence"]))

    def test_missing_section_never_invents_picks(self) -> None:
        result = locate_cards_to_watch([{"start": 0, "end": 10, "text": "General discussion"}])
        self.assertFalse(result["located"])
        self.assertEqual([], result["segments"])

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
        self.assertIn("function showEpisode", app)
        self.assertIn("View failure details", app)
        self.assertNotIn("Unavailable", app)

    def test_workflow_defaults_and_limit_guard_are_safe(self) -> None:
        workflow = (Path(__file__).parents[1] / ".github/workflows/ffw.yml").read_text(encoding="utf-8")
        self.assertIn("default: next", workflow)
        self.assertIn('default: "1"', workflow)
        self.assertIn("batch_size must be a positive integer", workflow)
        self.assertIn("exceeds the safety cap", workflow)
        self.assertIn("gemini-3.5-flash", workflow)
        self.assertIn("gemini-3.5-flash-lite", workflow)
        self.assertIn('FFW_GEMINI_TRANSIENT_RETRIES: "1"', workflow)
        self.assertIn('cron: "17 20 * * *"', workflow)
        self.assertIn('INPUT_MODE="retry_failed"', workflow)
        self.assertIn('FFW_MAX_EPISODE_ATTEMPTS: "3"', workflow)
        self.assertIn("deploy_only", workflow)
        self.assertIn("retry_failed", workflow)
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

    def test_real_five_pick_publication_cleanup_and_idempotent_skip(self) -> None:
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
                return {"section": {"located": True, "start_seconds": 600, "end_seconds": 930, "label": "Cards to Watch", "confidence": "high", "review_reason": None}, "recommendations": picks, "review_reason": None}

        extractor = Extractor()
        pipeline = Pipeline(settings, Feed(), Downloader(), Audio(), Transcriber(), extractor, JsonStateStore(settings.state_file))
        result = pipeline.run(limit=1)[0]
        self.assertEqual(("complete", 5), (result.status, result.pick_count))
        summary = load_json(settings.archive_dir / result.output_directory / "summary.json")
        self.assertFalse(summary["synthetic"])
        self.assertEqual(5, len(summary["recommendations"]))
        self.assertFalse(any(settings.work_dir.glob("*")))
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

    def test_exact_guid_searches_full_feed_and_bypasses_position_limit(self) -> None:
        candidates = self.candidates()
        self.set_status(candidates[0], "complete")
        report = self.pipeline.select_candidates(candidates, policy="exact_guid", limit=1, force_guid="guid-1")
        self.assertEqual(6, report.feed_entries_scanned)
        self.assertEqual(["guid-1"], [item.guid for item in report.selected])

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
