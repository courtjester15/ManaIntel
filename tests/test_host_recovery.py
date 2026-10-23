from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ffw.metadata_recovery import agreed_hosts, quote_supported
from ffw.pipeline import Pipeline
from ffw.config import Settings
from ffw.models import EpisodeCandidate
from ffw.utils import atomic_write_json
from tests.workspace import workspace_temp


class AudioHostRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.quote = "My first choice this week is the Artist Card."
        self.summary = {"processing": {"status": "needs_review", "review_reason": "Retain timing review."},
                        "recommendations": [{"id": "pick-one", "card": "Artist Card", "hosts": [],
                            "printing": "Artist bonus", "foil": True, "start_seconds": 200, "end_seconds": 220}]}
        self.transcript = {"segments": [
            {"start": 0, "text": "I am your host Ada, and my cohost is Ben."},
            {"start": 200, "text": self.quote}]}
        self.reading = {"participants": [{"name": "Ada", "anchor_quote": "I am your host Ada"}],
                        "picks": [{"pick_id": "pick-one", "host": "Ada", "decision": "confirmed",
                                   "quote": self.quote, "explanation": "Same voice as the self-identified introductory speaker."}]}

    def test_two_grounded_readings_fill_hosts_without_changing_picks_timing_or_review(self):
        before = deepcopy(self.summary)
        result, accepted = agreed_hosts(before, self.transcript, [self.reading, self.reading], "model")
        self.assertEqual(["pick-one"], accepted)
        self.assertEqual(["Ada"], result["recommendations"][0]["hosts"])
        self.assertEqual(self.summary, before)
        pick = result["recommendations"][0]
        pick.pop("host_attribution")
        pick["hosts"] = []
        self.assertEqual(self.summary, result)

    def test_disagreement_ambiguity_bad_quote_and_duplicate_ids_abstain(self):
        for mutate in (
            lambda r: r["picks"][0].update(host="Ben"),
            lambda r: r["picks"][0].update(decision="ambiguous"),
            lambda r: r["picks"][0].update(quote="I did not actually say this in the source audio."),
            lambda r: r["picks"].append(deepcopy(r["picks"][0])),
            lambda r: r["participants"][0].update(anchor_quote="Ada was not mentioned here"),
        ):
            with self.subTest(mutate=mutate):
                second = deepcopy(self.reading)
                mutate(second)
                result, accepted = agreed_hosts(self.summary, self.transcript, [self.reading, second], "model")
                self.assertEqual([], accepted)
                self.assertEqual(self.summary, result)

    def test_known_hosts_are_never_replaced(self):
        self.summary["recommendations"][0]["hosts"] = ["Ben"]
        result, accepted = agreed_hosts(self.summary, self.transcript, [self.reading, self.reading], "model")
        self.assertEqual([], accepted)
        self.assertEqual(["Ben"], result["recommendations"][0]["hosts"])

    def test_repeated_or_short_quote_does_not_establish_identity(self):
        self.assertFalse(quote_supported(self.quote, self.quote + " " + self.quote))
        self.assertFalse(quote_supported("my choice", "my choice"))

    def pipeline_fixture(self):
        root = workspace_temp(self)
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work", mode="live")
        baseline = json.loads(Path("archive/episodes/0537-reality-fracture-deep-dive/summary.json").read_text(encoding="utf-8"))
        for pick in baseline["recommendations"]:
            pick["hosts"] = []
        ep = baseline["episode"]
        candidate = EpisodeCandidate(ep["guid"], ep["episode_number"], ep["title"], ep["published_at"], ep["audio_url"], ep["episode_url"], [])
        output = root / "archive/episodes/test"
        output.mkdir(parents=True)
        files = {"summary.json": json.dumps(baseline), "summary.md": "retained markdown", "metadata.json": json.dumps({"processing": baseline["processing"]})}
        for name, contents in files.items():
            (output / name).write_text(contents, encoding="utf-8")
        pipeline = object.__new__(Pipeline)
        pipeline.settings = settings
        pipeline.downloader = Mock()
        pipeline.downloader.download.return_value = root / "audio.mp3"
        pipeline.state = Mock()
        transcript = settings.work_dir / "transcripts/test.json.gz"
        transcript.parent.mkdir(parents=True)
        transcript.touch()
        return pipeline, candidate, baseline, files, output

    def test_metadata_recovery_failure_preserves_all_public_files_and_state(self):
        pipeline, ep, baseline, files, output = self.pipeline_fixture()
        with patch("ffw.metadata_recovery.recover_hosts", side_effect=RuntimeError("503 unavailable")), patch("ffw.capacity.reserve"):
            result = pipeline._recover_published_hosts(ep, baseline, files, output, "episodes/test", "test", Mock())
        self.assertEqual("failed", result.status)
        for name, contents in files.items():
            self.assertEqual(contents, (output / name).read_text(encoding="utf-8"))
        pipeline.state.transition.assert_not_called()

    def test_metadata_recovery_success_keeps_ids_printings_timestamps_and_status(self):
        pipeline, ep, baseline, files, output = self.pipeline_fixture()
        recovered = deepcopy(baseline)
        recovered["recommendations"][0]["hosts"] = ["Ada"]
        recovered["processing"]["metadata_recovery"] = {"method": "test"}
        with patch("ffw.metadata_recovery.recover_hosts", return_value=(recovered, [recovered["recommendations"][0]["id"]])), patch("ffw.capacity.reserve"):
            result = pipeline._recover_published_hosts(ep, baseline, files, output, "episodes/test", "test", Mock())
        self.assertEqual(baseline["processing"]["status"], result.status)
        self.assertEqual(recovered, json.loads((output / "summary.json").read_text(encoding="utf-8")))
        updates = pipeline.state.transition.call_args.kwargs
        self.assertEqual({"metadata_recovery": {"method": "test"}}, updates)

    def test_capacity_preflight_stops_before_download_or_model_calls(self):
        from ffw.capacity import CapacityStopped
        pipeline, ep, baseline, files, output = self.pipeline_fixture()
        with patch("ffw.capacity.reserve", side_effect=CapacityStopped("Shared capacity stop")):
            result = pipeline._recover_published_hosts(ep, baseline, files, output, "episodes/test", "test", Mock())
        self.assertEqual("failed", result.status)
        pipeline.downloader.download.assert_not_called()
        pipeline.state.transition.assert_not_called()

    def test_live_adapter_is_bounded_to_two_readings_and_keeps_private_evidence(self):
        import gzip
        import os
        import sys
        import types
        from ffw.metadata_recovery import recover_hosts
        root = workspace_temp(self)
        ep = EpisodeCandidate("guid", 1, "Episode 1", "2026-01-01T00:00:00Z", "https://example.test/audio", "https://example.test", [], duration_seconds=300)
        transcript_path = root / "transcript.json.gz"
        with gzip.open(transcript_path, "wt", encoding="utf-8") as handle:
            json.dump({"episode": {"guid": ep.guid, "audio_url": ep.audio_url}, "transcript": self.transcript}, handle)
        self.summary["section"] = {"located": True, "start_seconds": 190, "end_seconds": 230}
        clip = root / "clip.mp3"
        clip.write_bytes(b"test audio")
        google = types.ModuleType("google")
        genai = types.ModuleType("google.genai")
        sdk_types = types.ModuleType("google.genai.types")
        sdk_types.HttpOptions = Mock()
        sdk_types.Part = SimpleNamespace(from_bytes=Mock(return_value="audio part"))
        genai.Client = Mock()
        genai.types = sdk_types
        google.genai = genai
        report = root / "private/report.json"
        with patch.dict(sys.modules, {"google": google, "google.genai": genai, "google.genai.types": sdk_types}), patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch(
            "ffw.metadata_recovery.audio_clip", return_value=clip
        ), patch("ffw.metadata_recovery.reserve") as reserve, patch(
            "ffw.metadata_recovery._gemini_generate_json", side_effect=[deepcopy(self.reading), deepcopy(self.reading)]
        ) as generate:
            result, accepted = recover_hosts(ep, self.summary, transcript_path, clip, root, report, "model", Mock())
        self.assertEqual(["pick-one"], accepted)
        self.assertEqual(2, generate.call_count)
        self.assertTrue(all(not call.kwargs["allow_schema_fallback"] for call in generate.call_args_list))
        reserve.assert_called_once_with("model", check_only=True, minimum_requests=2)
        self.assertEqual(2, len(json.loads(report.read_text(encoding="utf-8"))["readings"]))
        self.assertEqual("audio_host_recovery_v1", result["processing"]["metadata_recovery"]["method"])
        sdk_types.HttpOptions.assert_called_once_with(timeout=300000, retry_options={"attempts": 1})
