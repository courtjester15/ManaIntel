from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from ffw.cli import main
from ffw.config import Settings
from ffw.health import build_health_report, fetch_github_evidence, render_health_markdown, workflow_evidence_projection
from ffw.utils import atomic_write_json
from tests.workspace import workspace_temp

NOW = datetime(2026, 10, 16, 3, tzinfo=timezone.utc)


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.root = workspace_temp(self)
        self.state = self.root / "state"
        self.archive = self.root / "archive"
        self.settings = Settings(self.root, self.archive, self.state / "episodes.json", self.root / ".ffw-work")

    def attempt(self, identity, *, kind="initial", outcome="complete", picks=3, version="0.5.10", **extra):
        context = {"force": kind == "forced", "retry_failed": kind == "retry", "prior_attempt_count": int(kind != "initial"),
                   "transcription_model": "primary", "extraction_model": "primary"}
        record = {"attempt_id": identity, "episode": {"guid": identity, "source": "brainstorm-brewery", "number": 667},
                  "pipeline_version": version, "started_at": "2026-10-15T20:00:00Z", "finished_at": "2026-10-15T20:01:00Z",
                  "context": context, "outcome": outcome, "pick_count": picks, "workflow_validation": "success",
                  "run_id": identity, "run_attempt": "1", "events": [], **extra}
        atomic_write_json(self.state / "attempts" / f"{identity}.json", record)
        return record

    def build(self, **kwargs):
        return build_health_report(self.state, self.archive, as_of=NOW, **kwargs)

    @staticmethod
    def observation(identity, *, attempt="1", conclusion="success", deploy="success", persist="success", **extra):
        return {"run_id": identity, "run_attempt": attempt, "created_at": "2026-10-15T20:00:00Z",
                "updated_at": "2026-10-15T20:02:00Z", "status": "completed", "conclusion": conclusion,
                "path": ".github/workflows/ffw.yml", "event": "schedule", "jobs_observed": True,
                "jobs": [{"name": "publish", "conclusion": conclusion,
                          "steps": [{"name": "Persist durable state and archive", "conclusion": persist}]},
                         {"name": "deploy", "conclusion": deploy}], **extra}

    def test_forced_recovery_cannot_improve_initial_rate_or_erase_failure(self):
        self.attempt("initial", outcome="failed", picks=0)
        for identity in ("recovery1", "recovery2", "recovery3"):
            self.attempt(identity, kind="forced")
        report = self.build()
        self.assertEqual((1, 0, 1), tuple(report["kinds"]["initial"][key] for key in ("finished", "validated_usable", "failed")))
        self.assertEqual(3, report["kinds"]["forced"]["validated_usable"])
        self.assertIn("0/1 (0%)", render_health_markdown(report))

    def test_empty_preserved_unvalidated_and_skipped_results_are_not_new_usable_work(self):
        self.attempt("empty", picks=0)
        self.attempt("confirmed", picks=0, zero_pick_disposition="confirmed_no_recommendations")
        self.attempt("preserved", preserved_previous=True)
        self.attempt("unvalidated", workflow_validation=None)
        self.attempt("invalid", workflow_validation="failure")
        self.attempt("skip", outcome="skipped")
        self.attempt("review", outcome="needs_review")
        r = self.build()["totals"]
        self.assertEqual(2, r["validated_usable"])
        self.assertEqual(6, r["finished"])
        self.assertEqual(1, r["skipped"])
        self.assertEqual(1, r["empty_unconfirmed"])
        self.assertEqual(1, r["preserved_previous"])
        self.assertEqual(1, r["validation_unknown"])

    def test_synthetic_invalid_dates_outside_window_and_future_results_are_excluded(self):
        self.attempt("fixture", episode={"guid": "ffw-synthetic-test"})
        self.attempt("bad-date", started_at="not a timestamp")
        self.attempt("naive", started_at="2026-10-15T20:00:00")
        self.attempt("old", started_at="2026-09-01T00:00:00Z")
        self.attempt("future", started_at="2026-10-17T00:00:00Z")
        self.attempt("finishes-later", finished_at="2026-10-17T00:00:00Z")
        r = self.build()
        self.assertEqual(1, r["totals"]["records"])
        self.assertEqual(1, r["totals"]["running"])
        self.assertEqual(0, r["totals"]["validated_usable"])
        self.assertEqual(2, r["journal_coverage"]["excluded_invalid_dates"])

    def test_boundary_time_is_included_and_retries_models_and_versions_stay_separate(self):
        self.attempt("start", started_at="2026-10-02T03:00:00Z")
        self.attempt("retry", kind="retry")
        self.attempt("old-version", version="0.5.5")
        other = self.attempt("other-model")
        other["context"]["transcription_model"] = "fallback"
        atomic_write_json(self.state / "attempts/other-model.json", other)
        report = self.build()
        self.assertEqual(4, len(report["cohorts"]))
        self.assertEqual(1, report["kinds"]["retry"]["finished"])

    def test_publication_requires_exact_run_attempt_persistence_and_pages_evidence(self):
        for identity in ("ok", "failed-workflow", "no-pages", "no-persist", "rerun", "pending", "no-observation"):
            self.attempt(identity)
        evidence = {"status": "available", "runs": [
            self.observation("ok"), self.observation("failed-workflow", conclusion="failure"),
            self.observation("no-pages", deploy="skipped"), self.observation("no-persist", persist="failure"),
            self.observation("rerun", attempt="2"), self.observation("pending", status="in_progress"),
        ]}
        r = self.build(github=evidence)["totals"]
        self.assertEqual(2, r["publication_verified"])
        self.assertEqual(2, r["publication_not_observed"])
        self.assertEqual(3, r["publication_unknown"])

    def test_workflow_types_do_not_treat_every_run_without_an_attempt_as_a_noop(self):
        journal = {"run_attempt": "1", "timestamp": "2026-10-15T20:02:00Z", "validation": "success"}
        atomic_write_json(self.state / "runs/empty.json", {**journal, "run_id": "empty", "selection": {"selected_count": 0}})
        atomic_write_json(self.state / "runs/gated.json", {**journal, "run_id": "gated", "note": "Primary gate=false; queue="})
        evidence = {"status": "available", "runs": [
            self.observation("push", event="push"), self.observation("manual", event="workflow_dispatch"),
        ]}
        r = self.build(github=evidence)
        self.assertEqual({"no_op": 1, "gated_skip": 1, "deploy_only_push": 1, "unclassified": 1}, r["workflow_kinds"])

    def test_provider_success_and_semantic_rejection_are_different_and_private_text_is_not_published(self):
        self.attempt("failed", outcome="failed", picks=0, intervention="PRIVATE TRANSCRIPT IN NOTE", events=[
            {"event": "model_call", "model": "primary", "outcome": "failed", "message": "PRIVATE TRANSCRIPT IN EXCEPTION"},
            {"event": "model_call", "model": "fallback", "outcome": "success"},
            {"event": "repair_timing_rejected", "model": "fallback", "text": "PRIVATE TRANSCRIPT"},
            {"event": "checkpoint_reused"}, {"event": "transcript_reused"}, {"event": "model_circuit_skipped"},
            {"event": "failure", "message": "Timing repair failed after primary 503; PRIVATE TRANSCRIPT"},
        ])
        r = self.build()
        self.assertEqual((2, 1, 1, 1, 1), tuple(r["totals"][key] for key in ("model_calls", "failed_model_calls", "timing_rejections", "checkpoint_reuses", "transcript_reuses")))
        self.assertEqual({"transcript_timing_or_coverage": 1}, r["failure_categories"])
        self.assertNotIn("PRIVATE TRANSCRIPT", json.dumps(r))
        self.assertNotIn("PRIVATE TRANSCRIPT", render_health_markdown(r))

    def test_current_backlog_is_not_reconstructed_from_old_attempt_results_or_machine_approval(self):
        self.attempt("formerly-failed", outcome="failed", picks=0)
        atomic_write_json(self.archive / "index.json", {"metadata": {"generated_at": "2026-10-16T02:57:00Z"}, "episodes": [
            {"guid": "formerly-failed", "source_id": "brainstorm-brewery", "processing_status": "complete", "review_state": "approved", "pick_count": 3},
            {"guid": "review", "source_id": "mtg-fast-finance", "processing_status": "needs_review", "pick_count": 2, "review_reason": "Uncertain section ending; fewer than four picks."},
            {"guid": "human", "source_id": "mtg-fast-finance", "processing_status": "complete", "pick_count": 4, "human_reviewed": True},
            {"guid": "fixture", "synthetic": True, "processing_status": "failed"},
        ]})
        r = self.build()
        self.assertEqual(1, r["totals"]["failed"])
        self.assertEqual((3, 9, 1, 0, 1), tuple(r["backlog"][key] for key in ("episodes", "picks", "needs_review", "failed", "human_reviewed")))
        self.assertEqual({"low_pick_count": 1, "section_or_boundary": 1}, r["backlog"]["review_reasons"])

    def test_missing_data_and_unavailable_github_remain_unknown(self):
        r = self.build(github={"status": "unavailable", "runs": []})
        self.assertFalse(r["backlog"]["available"])
        self.assertIsNone(r["journal_coverage"]["first_recorded"])
        self.assertIn("unknown", render_health_markdown(r))
        self.assertTrue(r["notes"])

    def test_future_github_evidence_cannot_certify_past_publication(self):
        self.attempt("past")
        r = self.build(github={"status": "available", "runs": [self.observation("past", updated_at="2026-10-17T00:00:00Z")]})
        self.assertEqual(0, r["totals"]["publication_verified"])

    def test_noop_publication_churn_is_separate_from_episode_results(self):
        atomic_write_json(self.state / "runs/noop.json", {"run_id": "noop", "run_attempt": "1",
                          "timestamp": "2026-10-15T20:01:00Z", "selection": {"selected_count": 0}})
        r = self.build(github={"status": "available", "runs": [self.observation("noop")]})
        self.assertEqual(0, r["totals"]["finished"])
        self.assertEqual(1, r["no_op_pages_publications"])

    def test_malformed_input_fails_instead_of_becoming_an_empty_healthy_report(self):
        atomic_write_json(self.state / "attempts/bad.json", [])
        with self.assertRaisesRegex(ValueError, "JSON object"):
            self.build()

    def test_offline_workflow_evidence_cannot_smuggle_raw_logs_into_saved_report(self):
        observation = self.observation("1")
        observation["private"] = "PRIVATE TRANSCRIPT"
        observation["jobs"][0]["steps"].append({"name": "Download PRIVATE TRANSCRIPT"})
        evidence = workflow_evidence_projection({"status": "available", "error": "PRIVATE TRANSCRIPT", "runs": [observation]})
        self.assertNotIn("PRIVATE TRANSCRIPT", json.dumps(evidence))

    def test_cli_is_read_only_deterministic_and_can_reuse_evidence_offline(self):
        self.attempt("123")
        before = {p: p.read_bytes() for p in self.state.rglob("*.json")}
        output = self.root / "health.json"
        markdown = self.root / "health.md"
        evidence = {"status": "available", "runs": [self.observation("123")]}
        with patch("ffw.cli.Settings.load", return_value=self.settings), patch("ffw.cli.fetch_github_evidence", return_value=evidence), redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["health-report", "--github", "--as-of", NOW.isoformat(), "--output-json", str(output), "--output-markdown", str(markdown)]))
        first = markdown.read_bytes()
        with patch("ffw.cli.Settings.load", return_value=self.settings), patch("ffw.cli.fetch_github_evidence", side_effect=AssertionError("must stay offline")), redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["health-report", "--workflow-evidence", str(output), "--as-of", NOW.isoformat(), "--output-markdown", str(markdown)]))
        self.assertEqual(first, markdown.read_bytes())
        self.assertEqual(before, {p: p.read_bytes() for p in self.state.rglob("*.json")})

    def test_cli_github_failure_still_writes_honest_report_and_invalid_window_fails(self):
        with patch("ffw.cli.Settings.load", return_value=self.settings), patch("ffw.cli.fetch_github_evidence", side_effect=RuntimeError("secret failure")), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, main(["health-report", "--github"]))
            self.assertIn("unknown", out.getvalue())
            self.assertNotIn("secret failure", out.getvalue())
            self.assertEqual(2, main(["health-report", "--days", "0"]))
            self.assertEqual(2, main(["health-report", "--as-of", "2026-10-15"]))

    def test_collector_is_bounded_read_only_and_drops_logs_messages_and_unrelated_fields(self):
        def command(args, **kwargs):
            self.assertEqual(["gh", "api", "--method", "GET"], args[:4])
            if args[4].endswith("/actions/runs"):
                data = {"workflow_runs": [
                    {"id": 1, "run_attempt": 2, "path": ".github/workflows/ffw.yml", "created_at": "2026-10-15T20:00:00Z", "logs_url": "PRIVATE LOGS"},
                    {"id": 2, "path": ".github/workflows/ffw.yml", "created_at": "2026-10-14T20:00:00Z"},
                ]}
            else:
                self.assertIn("/attempts/2/jobs", args[4])
                data = {"jobs": [{"name": "publish", "conclusion": "success", "logs_url": "PRIVATE LOGS", "steps": [
                    {"name": "Persist durable state and archive", "conclusion": "success", "secret": "PRIVATE LOGS"},
                    {"name": "Unrelated step with private content"},
                ]}]}
            return types.SimpleNamespace(returncode=0, stdout=json.dumps(data))
        with patch("ffw.health.subprocess.run", side_effect=command) as run:
            evidence = fetch_github_evidence("owner/repo", as_of=NOW, max_job_requests=1)
        self.assertEqual(2, run.call_count)
        self.assertEqual(1, evidence["job_requests"])
        self.assertTrue(evidence["truncated"])
        self.assertNotIn("PRIVATE LOGS", json.dumps(evidence))
        self.assertNotIn("Unrelated step", json.dumps(evidence))

    def test_collector_prioritizes_attempt_linked_runs_within_job_budget(self):
        runs = [{"id": i, "path": ".github/workflows/ffw.yml", "created_at": f"2026-10-{i + 10}T20:00:00Z"} for i in (1, 2)]
        def command(args, **kwargs):
            if args[4].endswith("/actions/runs"):
                return types.SimpleNamespace(returncode=0, stdout=json.dumps({"workflow_runs": runs}))
            self.assertIn("/runs/1/attempts/1/jobs", args[4])
            return types.SimpleNamespace(returncode=0, stdout='{"jobs": []}')
        with patch("ffw.health.subprocess.run", side_effect=command):
            evidence = fetch_github_evidence("owner/repo", as_of=NOW, max_job_requests=1, priority_runs={"1"})
        self.assertTrue(evidence["runs"][0]["jobs_observed"])
        self.assertEqual("1", evidence["runs"][0]["run_id"])

    def test_collector_stops_job_reads_after_repeated_outage(self):
        runs = [{"id": i, "path": ".github/workflows/ffw.yml", "created_at": "2026-10-15T20:00:00Z"} for i in range(10)]
        responses = [types.SimpleNamespace(returncode=0, stdout=json.dumps({"workflow_runs": runs}))]
        responses += [types.SimpleNamespace(returncode=1, stdout="", stderr="private error")] * 3
        with patch("ffw.health.subprocess.run", side_effect=responses) as run:
            evidence = fetch_github_evidence("owner/repo", as_of=NOW)
        self.assertEqual(4, run.call_count)
        self.assertEqual(3, evidence["job_errors"])
        self.assertTrue(evidence["truncated"])
        self.assertFalse(any(r["jobs_observed"] for r in evidence["runs"]))


if __name__ == "__main__":
    unittest.main()
