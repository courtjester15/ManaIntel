from __future__ import annotations

import gzip
import json
import os
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from ffw.audit import AttemptJournal, main as finalize_audit
from ffw.config import PROMPT_VERSION, Settings
from ffw.models import EpisodeCandidate
from ffw.pipeline import Pipeline, classify_failure
from ffw.production import GeminiMalformedJSONError, GeminiTranscriber, _gemini_generate_json
from ffw.utils import atomic_write_text, load_json
from ffw.validation import validate_archive
from tests.workspace import workspace_temp


def candidate() -> EpisodeCandidate:
    return EpisodeCandidate("real-guid", 520, "MTGFF 520", "2026-10-01T00:00:00Z",
                            "https://example.test/audio.mp3", "https://example.test/520", [], duration_seconds=1800)


@contextmanager
def fake_sdk():
    genai = types.ModuleType("google.genai")
    genai.Client = lambda **kwargs: object()
    genai.types = types.SimpleNamespace(
        HttpOptions=lambda **kwargs: kwargs,
        Part=types.SimpleNamespace(from_bytes=lambda **kwargs: kwargs),
    )
    google = types.ModuleType("google")
    google.genai = genai
    with patch.dict(sys.modules, {"google": google, "google.genai": genai}), patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        yield genai.types


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.root = workspace_temp(self)
        self.settings = Settings(self.root, self.root / "archive", self.root / "state/episodes.json", self.root / ".ffw-work")

    @staticmethod
    def media(command, **kwargs):
        if command[0] == "ffprobe":
            return types.SimpleNamespace(returncode=0, stdout="100", stderr="")
        Path(command[-1]).write_bytes(b"fake audio")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def transcriber(self):
        return GeminiTranscriber("primary", 900, fallback_model_name="fallback", transient_retries=1,
                                 retry_delay_seconds=0, checkpoint_root=self.root / "checkpoints")

    def test_incomplete_body_retries_and_falls_back(self):
        error = RuntimeError("peer closed connection without sending complete message body (incomplete chunked read)")
        with patch("ffw.production._gemini_generate_json", side_effect=[error, error, {"text": "ok"}]) as generate:
            payload, model = self.transcriber()._transcribe_chunk(object(), object(), [])
        self.assertEqual("fallback", model)
        self.assertEqual(3, generate.call_count)
        self.assertEqual(("transient_provider", True, True), classify_failure(str(error)))

    def test_typed_transport_error_without_matching_message_retries(self):
        class TransportError(Exception):
            pass
        with patch.dict(sys.modules, {"httpx": types.SimpleNamespace(TransportError=TransportError)}), patch(
            "ffw.production._gemini_generate_json", side_effect=[TransportError("opaque"), {"text": "ok"}]
        ) as generate:
            self.transcriber()._transcribe_chunk(object(), object(), [])
        self.assertEqual(2, generate.call_count)

    def test_composite_provider_and_output_failure_stops_batch(self):
        self.assertEqual(("transient_provider", True, True),
                         classify_failure("primary: 503 UNAVAILABLE; fallback: malformed JSON MAX_TOKENS"))

    def test_max_tokens_skips_identical_primary_retry(self):
        with patch("ffw.production._gemini_generate_json",
                   side_effect=[GeminiMalformedJSONError("MAX_TOKENS"), {"text": "ok"}]) as generate:
            self.transcriber()._transcribe_chunk(object(), object(), [])
        self.assertEqual(["primary", "fallback"], [call.kwargs["model"] for call in generate.call_args_list])

    def test_failed_generation_records_usage_not_response_body(self):
        response = types.SimpleNamespace(text='{"private":"transcript text"}',
                                         candidates=[types.SimpleNamespace(finish_reason="MAX_TOKENS")],
                                         usage_metadata={"candidates_token_count": 8000})
        client = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=lambda **kwargs: response))
        config = types.SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs)
        events = []
        with self.assertRaises(GeminiMalformedJSONError):
            _gemini_generate_json(client, config, model="primary", contents=[], schema={},
                                  observer=lambda event, **details: events.append(details))
        self.assertEqual(8000, events[0]["provider_usage"]["candidates_token_count"])
        self.assertEqual("MAX_TOKENS", events[0]["finish_reason"])
        self.assertNotIn("transcript text", json.dumps(events))

    def test_rescue_offsets_and_resumes_successful_half(self):
        transcriber = self.transcriber()
        audio = self.root / "chunk.mp3"
        audio.write_bytes(b"parent")
        first = {"text": "first", "segments": [{"start": 1, "end": 2, "text": "first", "speaker": None}]}
        second = {"text": "second", "segments": [{"start": 3, "end": 4, "text": "second", "speaker": None}]}
        with fake_sdk() as sdk, patch("ffw.production.subprocess.run", side_effect=self.media), patch(
            "ffw.production._gemini_generate_json", side_effect=[first, RuntimeError("503")]
        ):
            with self.assertRaisesRegex(RuntimeError, "503"):
                transcriber._rescue_chunk(object(), sdk, candidate(), audio, 0, 2, "fingerprint", "prompt")
        with fake_sdk() as sdk, patch("ffw.production.subprocess.run", side_effect=self.media), patch(
            "ffw.production._gemini_generate_json", return_value=second
        ) as generate:
            payload, _ = transcriber._rescue_chunk(object(), sdk, candidate(), audio, 0, 2, "fingerprint", "prompt")
        self.assertEqual(1, generate.call_count)
        self.assertFalse(generate.call_args.kwargs["allow_schema_fallback"])
        self.assertEqual([1, 53], [segment["start"] for segment in payload["segments"]])
        self.assertFalse((self.root / "chunk-rescue").exists())

    def test_rescue_budget_is_two_extra_calls_for_entire_episode(self):
        transcriber = self.transcriber()
        files = [self.root / f"chunk-{index}.mp3" for index in range(2)]
        for path in files:
            path.write_bytes(b"parent")
        with fake_sdk(), patch("ffw.production.subprocess.run", side_effect=self.media), patch.object(
            transcriber, "_transcribe_chunk", side_effect=RuntimeError("MAX_TOKENS")
        ), patch("ffw.production._gemini_generate_json", return_value={"text": "ok", "segments": []}) as generate:
            with self.assertRaisesRegex(RuntimeError, "chunk 2/2"):
                transcriber.transcribe(candidate(), files)
        self.assertEqual(2, generate.call_count)

    def test_completed_split_parent_checkpoint_reused_on_next_attempt(self):
        transcriber = self.transcriber()
        audio = self.root / "chunk.mp3"
        audio.write_bytes(b"parent")
        with fake_sdk(), patch("ffw.production.subprocess.run", side_effect=self.media), patch.object(
            transcriber, "_transcribe_chunk", side_effect=RuntimeError("MAX_TOKENS")
        ), patch("ffw.production._gemini_generate_json", return_value={"text": "ok", "segments": []}):
            transcriber.transcribe(candidate(), [audio])
        with fake_sdk(), patch.object(transcriber, "_transcribe_chunk") as generate, patch.object(transcriber, "_rescue_chunk") as rescue:
            transcript = transcriber.transcribe(candidate(), [audio])
        generate.assert_not_called()
        rescue.assert_not_called()
        self.assertTrue(transcript["usage"][0]["checkpoint_reused"])

    def test_sdk_retries_disabled_so_application_owns_call_budget(self):
        transcriber = self.transcriber()
        audio = self.root / "chunk.mp3"
        audio.write_bytes(b"parent")
        with fake_sdk(), patch.object(sys.modules["google.genai"], "Client", return_value=object()) as client, patch.object(
            transcriber, "_transcribe_chunk", return_value=({"text": "ok", "segments": []}, "primary")
        ):
            transcriber.transcribe(candidate(), [audio])
        self.assertEqual({"attempts": 1}, client.call_args.kwargs["http_options"]["retry_options"])

    def published(self):
        pipeline = Pipeline.mock(self.settings)
        results = pipeline.run()
        result = next(item for item in results if item.status == "complete")
        item = next(item for item in pipeline.feed.episodes() if item.guid == result.guid)
        output = self.settings.archive_dir / result.output_directory
        return pipeline, item, output

    def test_failed_rerun_keeps_published_files_and_logs_failure(self):
        pipeline, item, output = self.published()
        before = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
        with patch.object(pipeline.transcriber, "transcribe", side_effect=RuntimeError("503 UNAVAILABLE")):
            result = pipeline.process_episode(item, force=True)
        self.assertEqual("failed", result.status)
        self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()})
        state = pipeline.state.get(item.guid)
        self.assertEqual("complete", state["status"])
        self.assertGreater(state["pick_count"], 0)
        self.assertEqual("transcribing", state["last_attempt_error"]["stage"])
        records = [load_json(path) for path in (self.root / "state/attempts").glob("*.json")]
        failed = [record for record in records if record["episode"]["guid"] == item.guid and record["outcome"] == "failed"]
        self.assertTrue(failed[0]["preserved_previous"])
        self.assertEqual([], validate_archive(self.settings.archive_dir, self.settings.state_file))

    def test_mid_publish_failure_rolls_back_previous_output(self):
        pipeline, item, output = self.published()
        before = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
        failed = False
        def write(path, contents):
            nonlocal failed
            if path.name == "summary.md" and not failed:
                failed = True
                raise OSError("simulated write failure")
            atomic_write_text(path, contents)
        with patch("ffw.pipeline.atomic_write_text", side_effect=write):
            result = pipeline.process_episode(item, force=True)
        self.assertEqual("failed", result.status)
        self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()})

    def test_passes_and_idempotent_skips_are_logged(self):
        pipeline, item, _ = self.published()
        before = self.settings.state_file.read_bytes()
        pipeline.process_episode(item)
        self.assertEqual(before, self.settings.state_file.read_bytes())
        records = [load_json(path) for path in (self.root / "state/attempts").glob("*.json")]
        self.assertIn("complete", [record["outcome"] for record in records])
        self.assertIn("skipped", [record["outcome"] for record in records])
        self.assertIn("**skipped**", (self.root / "state/episode-attempts.md").read_text(encoding="utf-8"))

    def test_preflight_prevents_expensive_calls_on_invalid_archive(self):
        settings = Settings(self.root, self.root / "archive", self.root / "state/episodes.json",
                            self.root / ".ffw-work", mode="live")
        settings.archive_dir.mkdir()
        (settings.archive_dir / "index.json").write_text('{"sentinel": true}', encoding="utf-8")
        pipeline = Pipeline.mock(settings)
        pipeline.feed = types.SimpleNamespace(episodes=lambda: [candidate()])
        pipeline.downloader = Mock()
        with self.assertRaisesRegex(ValueError, "preflight failed"):
            pipeline.run(force_guid=candidate().guid)
        pipeline.downloader.download.assert_not_called()

    def test_journal_secrets_redacted_and_validation_failure_survives(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "super-secret", "GITHUB_RUN_ID": "123",
                                     "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "abc"}):
            journal = AttemptJournal(self.settings.state_file, candidate())
            journal.record("failure", message="super-secret failed")
            journal.finish("failed", pick_count=0)
            with patch.object(sys, "argv", ["audit", "--state-dir", str(self.root / "state"), "--validation", "failure"]):
                finalize_audit()
        text = journal.path.read_text(encoding="utf-8")
        self.assertNotIn("super-secret", text)
        self.assertEqual("failure", load_json(journal.path)["workflow_validation"])
        self.assertFalse(load_json(journal.path)["publication_eligible"])
        self.assertTrue((self.root / "state/runs/123-1.json").exists())

    def test_auto_retained_transcript_avoids_transcriber_call(self):
        pipeline, item, _ = self.published()
        from ffw.utils import episode_slug
        slug = episode_slug(item.episode_number, item.title, item.guid)
        directory = self.settings.work_dir / "transcripts"
        directory.mkdir(parents=True, exist_ok=True)
        with gzip.open(directory / f"{slug}.json.gz", "wt", encoding="utf-8") as output:
            json.dump({"episode": {"guid": item.guid, "audio_url": item.audio_url},
                       "prompt_version": PROMPT_VERSION, "transcript": {"segments": []}}, output)
        with patch.dict(os.environ, {"FFW_AUTO_REUSE_TRANSCRIPTS": "true"}), patch.object(pipeline.transcriber, "transcribe") as transcribe:
            result = pipeline.process_episode(item, force=True)
        self.assertEqual("complete", result.status)
        transcribe.assert_not_called()

    def test_atomic_write_retries_brief_windows_lock(self):
        locked = PermissionError("scanner lock")
        locked.winerror = 32
        with patch.object(Path, "replace", side_effect=[locked, None]) as replace, patch("ffw.utils.time.sleep") as sleep:
            atomic_write_text(self.root / "output.json", "{}")
        self.assertEqual(2, replace.call_count)
        sleep.assert_called_once_with(0.02)

    def test_atomic_write_does_not_hide_real_permission_failure(self):
        with patch.object(Path, "replace", side_effect=PermissionError("not writable")) as replace, patch("ffw.utils.time.sleep") as sleep:
            with self.assertRaises(PermissionError):
                atomic_write_text(self.root / "output.json", "{}")
        self.assertEqual(1, replace.call_count)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
