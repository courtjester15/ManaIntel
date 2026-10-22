import json
import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from ffw.capacity import reserve, record_failure, CapacityStopped
from ffw.transcript_timing import align_published_quotes, suspect_timing_chunks
from ffw.cleanup import select, record
from ffw.utils import atomic_write_json, load_json
from tests.workspace import workspace_temp


class CapacityCleanupTests(unittest.TestCase):
    def setUp(self):
        self.root = workspace_temp(self)
        self.env = patch.dict(os.environ, {"FFW_CAPACITY_PATH": str(self.root / "capacity.json"),
            "FFW_REQUEST_DAILY_BUDGET": "3", "FFW_PRIMARY_REQUEST_RESERVE": "1",
            "FFW_OPTIONAL_WORK": "true", "FFW_NIGHTLY_WINDOW": "false", "FFW_CLEANUP_ISSUES": "", "GITHUB_RUN_ID": "test"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.now = datetime(2026, 10, 20, 6, 59, tzinfo=timezone.utc)

    def test_capacity_preflight_is_read_only_and_still_enforces_limits(self):
        reserve("lite", self.now, check_only=True)
        self.assertFalse((self.root / "capacity.json").exists())
        reserve("lite", self.now)
        before = (self.root / "capacity.json").read_bytes()
        reserve("lite", self.now, check_only=True)
        self.assertEqual(before, (self.root / "capacity.json").read_bytes())
        reserve("lite", self.now)
        with self.assertRaises(CapacityStopped):
            reserve("lite", self.now, check_only=True)

    def test_optional_reserves_primary_and_rolls_at_pacific_midnight(self):
        reserve("lite", self.now)
        reserve("lite", self.now)
        with self.assertRaises(CapacityStopped):
            reserve("lite", self.now)
        with patch.dict(os.environ, {"FFW_OPTIONAL_WORK": "false"}):
            reserve("lite", self.now)
        reserve("lite", self.now + timedelta(minutes=2))
        ledger = json.loads((self.root / "capacity.json").read_text())
        self.assertEqual({"2026-10-19", "2026-10-20"}, set(ledger["days"]))

    def test_minute_pressure_cools_down_and_explicit_daily_quota_stops_day(self):
        ticket = reserve("lite", self.now)
        record_failure(ticket, RuntimeError("429 RESOURCE_EXHAUSTED"), self.now)
        with self.assertRaises(CapacityStopped):
            reserve("lite", self.now)
        # Test cooldown within the same Pacific day.
        earlier = self.now - timedelta(hours=2)
        with patch.dict(os.environ, {"FFW_REQUEST_DAILY_BUDGET": "20"}):
            ticket = reserve("other", earlier)
            record_failure(ticket, RuntimeError("429 rate limit"), earlier)
            reserve("other", earlier + timedelta(minutes=31))
            record_failure(ticket, RuntimeError("429 requestsPerDay quota exceeded"), earlier)
            with self.assertRaises(CapacityStopped):
                reserve("other", earlier + timedelta(minutes=40))

    def test_delayed_cleanup_can_select_and_reserve_with_existing_limits(self):
        atomic_write_json(self.root / "state/episodes.json", {"episodes": {"pilot": {
            "source_id": "mtg-fast-finance", "status": "failed", "updated_at": self.now.isoformat()}}})
        atomic_write_json(self.root / "state/reprocess-queue.json", {"inspected_pilots": {
            "pilot": {"status": "ready", "evidence": "inspected saved progress"}}})
        with patch.dict(os.environ, {"FFW_NIGHTLY_WINDOW": "true", "FFW_CLEANUP_ISSUES": "timing"}):
            guid, reason = select(self.root, self.now)
            self.assertEqual("pilot", guid)
            reserve("lite", self.now)
            reserve("lite", self.now)
            with self.assertRaises(CapacityStopped):
                reserve("lite", self.now)

    def test_repairs_clear_only_current_affected_chunks(self):
        from ffw.transcript_timing import unresolved_timing_chunks
        transcript = {"timing_adjustments": 7, "timing_adjustment_chunks": [1, 3]}
        self.assertEqual([1, 3], unresolved_timing_chunks(transcript, 5))
        transcript["timing_repairs"] = [{"chunk": 2, "validated_audio": True, "timing_adjustments": 0}]
        self.assertEqual([3], unresolved_timing_chunks(transcript, 5))
        transcript["timing_repairs"].append({"chunk": 4, "validated_audio": True, "timing_adjustments": 0})
        self.assertEqual([], unresolved_timing_chunks(transcript, 5))
        transcript["timing_repairs"].append({"chunk": 2, "validated_audio": True, "timing_adjustments": 1})
        self.assertEqual([1], unresolved_timing_chunks(transcript, 5))
        del transcript["timing_adjustment_chunks"]
        self.assertEqual([0, 1, 2, 4], unresolved_timing_chunks(transcript, 5))

    def test_exact_quote_alignment_preserves_printings_and_abstains_on_repetition(self):
        quote = "this specific printing is cheap and you should buy a copy"
        picks = [{"card": "Invented card", "printing": "Rainbow Foil", "id": "stable", "evidence_excerpt": quote}]
        segment = {"text": quote, "start": 123, "end": 139}
        result = align_published_quotes(picks, {"segments": [segment]})
        self.assertEqual((123, "Rainbow Foil", "stable"),
                         (result[0]["start_seconds"], result[0]["printing"], result[0]["id"]))
        self.assertIsNone(align_published_quotes(picks, {"segments": [segment, segment]}))
        self.assertIsNone(align_published_quotes(picks, {"segments": [{**segment, "text": "something else"}]}))

    def test_ellipsis_alignment_requires_each_unique_fragment_in_order(self):
        pick = {"evidence_excerpt": "this particular printing is cheap ... you should buy a copy", "start_seconds": 5}
        transcript = {"segments": [{"start": 40, "end": 50,
            "text": "this particular printing is cheap because supply is high and you should buy a copy"}]}
        self.assertEqual(40, align_published_quotes([pick], transcript)[0]["start_seconds"])
        transcript["segments"][0]["text"] = "you should buy a copy and this particular printing is cheap"
        self.assertIsNone(align_published_quotes([pick], transcript))

    def test_last_chunk_past_audio_end_is_suspect(self):
        transcript = {"duration_seconds": 2507, "chunk_count": 3, "segments": [
            {"start": 0, "end": 10}, {"start": 900, "end": 910}, {"start": 2660, "end": 2673}]}
        self.assertEqual([2], suspect_timing_chunks(transcript))

    def test_cleanup_older_validated_cohort_and_progress_only_resume(self):
        records = {"old": {"status": "needs_review", "source_id": "mtg-fast-finance",
            "review_reason": "Verify timing", "updated_at": "2026-09-01T00:00:00Z", "pick_count": 4},
            "new": {"status": "needs_review", "source_id": "brainstorm-brewery",
            "review_reason": "Verify timing", "updated_at": self.now.isoformat()}}
        atomic_write_json(self.root / "state/episodes.json", {"episodes": records})
        self.assertEqual("", select(self.root, self.now)[0])
        with patch.dict(os.environ, {"FFW_CLEANUP_ISSUES": "timing", "GUID": "old", "OUTCOME": "failure"}):
            self.assertEqual("old", select(self.root, self.now)[0])
            atomic_write_json(self.root / "state/attempts/progress.json", {
                "episode": {"guid": "old"}, "started_at": (self.now + timedelta(seconds=1)).isoformat(),
                "events": [{"event": "transcript_timing_repaired"}, {"event": "timing_repair_incomplete"}]})
            record(self.root, self.now + timedelta(minutes=1))
            self.assertEqual("deferred", load_json(self.root / "state/reprocess-queue.json")["entries"][-1]["status"])
            self.assertEqual("", select(self.root, self.now + timedelta(hours=1))[0])
            self.assertEqual("old", select(self.root, self.now + timedelta(hours=7))[0])
            # No new progress in the later attempt: quarantine the unchanged case.
            record(self.root, self.now + timedelta(hours=7, minutes=1))
            self.assertEqual("blocked", load_json(self.root / "state/reprocess-queue.json")["entries"][-1]["status"])

    def test_exact_inspected_pilot_does_not_open_other_failed_records(self):
        records = {guid: {"status": "failed", "source_id": "mtg-fast-finance",
            "error": {"category": "manual_intervention"}, "updated_at": self.now.isoformat()}
            for guid in ("inspected", "other")}
        atomic_write_json(self.root / "state/episodes.json", {"episodes": records})
        atomic_write_json(self.root / "state/reprocess-queue.json", {"entries": [], "inspected_pilots": {
            "inspected": {"status": "ready", "evidence": "inspected saved progress", "repair_mode": "coverage", "max_attempts": 1}}})
        with patch.dict(os.environ, {"FFW_CLEANUP_ISSUES": "timing", "GUID": "inspected", "OUTCOME": "failure"}):
            self.assertEqual("inspected", select(self.root, self.now)[0])
            atomic_write_json(self.root / "state/attempts/progress.json", {
                "episode": {"guid": "inspected"}, "started_at": (self.now + timedelta(seconds=1)).isoformat(),
                "events": [{"event": "transcription_checkpoint_saved"},
                           {"event": "failure", "message": "Shared capacity stop"}]})
            record(self.root, self.now + timedelta(minutes=1))
            ledger = load_json(self.root / "state/reprocess-queue.json")
            self.assertEqual("blocked", ledger["inspected_pilots"]["inspected"]["status"])
            self.assertEqual("", select(self.root, self.now + timedelta(days=1))[0])
