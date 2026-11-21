import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from ffw.models import EpisodeCandidate
from ffw.pipeline import Pipeline
from ffw.recovery import renew_provider_outage
from ffw.config import Settings
from tests.workspace import workspace_temp
from unittest.mock import Mock


class PeriodicRecoveryTests(unittest.TestCase):
    def error(self, **changes):
        return {"category": "transient_provider", "message": "Timing repair failed: 503 UNAVAILABLE",
                "attempt": 3, "max_attempts": 3, "retryable": False, "quarantined": True,
                "synthetic": False, **changes}

    def test_renewal_keeps_history_and_advances_backoff(self):
        for count, hours in ((3, 48), (4, 48), (5, 48), (6, 168), (25, 168)):
            error = self.error(attempt=count)
            original = copy.deepcopy(error)
            result = renew_provider_outage(error, "2026-11-20T00:00:00Z")
            self.assertEqual(original, error)
            self.assertEqual(count, result["attempt"])
            self.assertEqual(hours, result["recovery_interval_hours"])
            self.assertEqual(datetime(2026, 11, 20, tzinfo=timezone.utc) + timedelta(hours=hours),
                             datetime.fromisoformat(result["next_retry_at"].replace("Z", "+00:00")))
            self.assertTrue(result["retryable"])
            self.assertFalse(result["quarantined"])

    def test_ambiguous_quota_configuration_manual_and_semantic_failures_stay_gated(self):
        for changes in ({"category": "capacity_deferred"}, {"category": "manual_intervention"},
                        {"message": "503; manual review required"}, {"message": "429 daily quota"},
                        {"message": "403 provider denied"}, {"message": "MAX_TOKENS"},
                        {"category": "repair_progress_saved"}, {"synthetic": True}, {"attempt": 2}):
            error = self.error(**changes)
            self.assertEqual(error, renew_provider_outage(error, "2026-11-20T00:00:00Z"))
        for date in (None, "invalid", "2026-11-20"):
            self.assertEqual(self.error(), renew_provider_outage(self.error(), date))

    def pipeline(self, hours_ago, count=3):
        now = datetime.now(timezone.utc)
        episode = EpisodeCandidate("outage", 650, "Old episode", "2025-01-01T00:00:00Z", "audio", "episode", [])
        record = {"status": "failed", "attempt_count": count,
                  "updated_at": (now - timedelta(hours=hours_ago)).isoformat(), "error": self.error(attempt=count)}
        pipeline = object.__new__(Pipeline)
        pipeline.settings = SimpleNamespace(max_episode_attempts=3, enabled_sources=("mtg-fast-finance",))
        pipeline.state = SimpleNamespace(all=lambda: {episode.guid: record})
        return pipeline, episode, record

    def test_both_retry_selectors_renew_legacy_outage_without_mutating_state(self):
        for policy in ("failed_only", "retry_then_next"):
            pipeline, episode, record = self.pipeline(49)
            original = copy.deepcopy(record)
            result = pipeline.select_candidates([episode], policy=policy, limit=1)
            self.assertEqual([episode], result.selected)
            self.assertEqual(original, record)

    def test_cooldown_and_weekly_backoff_are_enforced(self):
        for hours, count in ((47, 3), (49, 6)):
            pipeline, episode, _ = self.pipeline(hours, count)
            result = pipeline.select_candidates([episode], policy="retry_then_next")
            self.assertEqual([], result.selected)
            self.assertEqual(1, result.retry_deferred)

    def test_new_release_precedes_periodic_recovery(self):
        pipeline, episode, _ = self.pipeline(200)
        fresh = EpisodeCandidate("fresh", 540, "New release", datetime.now(timezone.utc).isoformat(), "audio", "episode", [])
        result = pipeline.select_candidates([episode, fresh], policy="retry_then_next")
        self.assertEqual([fresh], result.selected)
        self.assertEqual("new_release", result.selected_mode)

    def test_third_outage_writes_renewed_failure_and_keeps_lifetime_count(self):
        root = workspace_temp(self)
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work")
        pipeline = Pipeline.mock(settings)
        _, episode, _ = self.pipeline(49)
        pipeline.state.discover(episode)
        pipeline.state.transition(episode.guid, "failed", attempt_count=2, error=self.error(attempt=2))
        pipeline.downloader.download = Mock(side_effect=RuntimeError("503 UNAVAILABLE"))
        result = pipeline.process_episode(episode, retry_failed=True)
        record = pipeline.state.get(episode.guid)
        self.assertEqual("failed", result.status)
        self.assertEqual(3, record["attempt_count"])
        self.assertEqual("periodic_provider", record["error"]["recovery_mode"])
        self.assertTrue(record["error"]["retryable"])
        self.assertFalse(record["error"]["quarantined"])
