"""Read-only health projections over recorded evidence, never provider calls."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from .config import PIPELINE_VERSION

SOURCES = {"mtg-fast-finance": "MTG Fast Finance", "brainstorm-brewery": "Brainstorm Brewery"}
KINDS = ("initial", "retry", "forced", "other", "skipped")
FINISHED = {"complete", "needs_review", "failed", "interrupted"}
COUNTERS = ("records", "finished", "complete", "needs_review", "failed", "interrupted", "running", "skipped",
            "validated_usable", "empty_unconfirmed", "preserved_previous", "validation_unknown",
            "publication_verified", "publication_not_observed", "publication_unknown",
            "model_calls", "failed_model_calls", "timing_rejections", "checkpoint_reuses", "transcript_reuses", "circuit_skips")


def timestamp(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(result, dict):
            raise ValueError(f"Health input {path.name} must be a JSON object.")
        return result
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read health input {path.name}; expected valid JSON.") from exc


def attempt_kind(record: dict) -> str:
    context = record.get("context") or {}
    if record.get("outcome") == "skipped":
        return "skipped"
    if context.get("force") is True:
        return "forced"
    if context.get("retry_failed") is True:
        return "retry"
    if context.get("force") is False and context.get("retry_failed") is False and context.get("prior_attempt_count") == 0:
        return "initial"
    return "other"


def failure_category(message: str) -> str:
    text = message.lower()
    for category, patterns in (
        ("application_capacity", ("shared capacity stop",)),
        ("transcript_timing_or_coverage", ("timing", "compressed", "missing segments", "coverage")),
        ("provider_quota", ("429", "quota", "resource_exhausted")),
        ("truncated_model_output", ("max_tokens", "truncated")),
        ("malformed_model_output", ("malformed json", "jsondecodeerror", "clock format")),
        ("provider_configuration", ("api key", "401", "403", "404", "unsupported", "response_schema", "response_json_schema")),
        ("provider_availability", ("503", "502", "504", "500", "timeout", "timed out", "connection", "peer closed", "unavailable")),
        ("input_or_media", ("ffmpeg", "ffprobe", "audio exceeds", "empty audio", "content type", "download")),
        ("archive_validation", ("validation", "schema", "evidence excerpt")),
    ):
        if any(pattern in text for pattern in patterns):
            return category
    return "unknown"


def _run_key(record: dict) -> tuple[str, str]:
    return str(record.get("run_id", "")), str(record.get("run_attempt") or "1")


def workflow_evidence_projection(evidence: dict) -> dict:
    """Whitelist metadata even when an offline evidence file has extra fields."""
    result = {key: evidence.get(key) for key in ("status", "observed_at", "runs_listed", "job_requests", "job_errors", "truncated")}
    result["runs"] = []
    for run in evidence.get("runs", []):
        row = {key: run.get(key) for key in ("run_id", "run_attempt", "created_at", "updated_at", "path", "event", "status", "conclusion", "jobs_observed")}
        row["jobs"] = [{"name": job.get("name"), "status": job.get("status"), "conclusion": job.get("conclusion"),
                        "steps": [{"name": step.get("name"), "conclusion": step.get("conclusion")}
                                  for step in job.get("steps", []) if str(step.get("name", "")).startswith("Persist ")]}
                       for job in run.get("jobs", [])]
        result["runs"].append(row)
    return result


def _bucket() -> dict:
    return {name: 0 for name in COUNTERS}


def _publication(record: dict, observations: dict) -> str:
    observed = observations.get(_run_key(record))
    if not observed or observed.get("status") != "completed" or not observed.get("jobs_observed"):
        return "unknown"
    # The overall workflow can fail after it successfully publishes failure
    # metadata. Inspect persistence and Pages independently of that conclusion.
    jobs = observed.get("jobs", [])
    persisted = any(step.get("name", "").startswith("Persist ") and step.get("conclusion") == "success"
                    for job in jobs for step in job.get("steps", []))
    deployed = any(job.get("name") == "deploy" and job.get("conclusion") == "success" for job in jobs)
    return "verified" if persisted and deployed else "not_observed"


def _workflow_kind(journal: dict | None, observed: dict | None, has_attempt: bool) -> str:
    if has_attempt:
        return "processing"
    if journal:
        selection = journal.get("selection")
        if isinstance(selection, dict) and selection.get("selected_mode") == "capacity_deferred":
            return "gated_skip"
        if isinstance(selection, dict) and selection.get("selected_count") == 0:
            return "no_op"
        note = str(journal.get("note", "")).lower()
        if "primary gate=false" in note:
            return "gated_skip"
        if "queue=no eligible" in note or "queue=daily cap" in note:
            return "queue_no_op"
        if journal.get("preflight") == "failure":
            return "preflight_failure"
    if observed and str(observed.get("path") or "").endswith("/ffw.yml") and observed.get("event") == "push":
        return "deploy_only_push"
    if observed and str(observed.get("path") or "").endswith("/review.yml"):
        return "review"
    # Dispatch inputs are not in run metadata. No attempt does not prove that
    # a manual dispatch was deploy-only, an empty selection, or a setup failure.
    return "unclassified"


def build_health_report(state_dir: Path, archive_dir: Path, *, as_of: datetime | None = None,
                        days: int = 14, github: dict | None = None) -> dict:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or not 1 <= days <= 365:
        raise ValueError("Health reports require a timezone-aware as-of time and 1–365 days.")
    now = now.astimezone(timezone.utc)
    since = now - timedelta(days=days)
    notes: list[str] = []
    all_attempts = []
    seen = set()
    invalid_times = 0
    for path in sorted((state_dir / "attempts").glob("*.json")):
        record = read_json(path, {})
        episode = record.get("episode") or {}
        if episode.get("synthetic") or str(episode.get("guid", "")).startswith("ffw-synthetic-"):
            continue
        identity = record.get("attempt_id") or path.name
        if identity in seen:
            notes.append("Duplicate attempt ID excluded.")
            continue
        seen.add(identity)
        started = timestamp(record.get("started_at"))
        if not started:
            invalid_times += 1
            continue
        if started <= now:
            all_attempts.append((started, record))
    records = [(started, record) for started, record in all_attempts if since <= started]
    records.sort(key=lambda pair: (pair[0], str(pair[1].get("attempt_id", ""))))
    github = workflow_evidence_projection(github or {"status": "not_requested", "runs": []})
    observations = {}
    for run in github.get("runs", []):
        updated = timestamp(run.get("updated_at"))
        if updated and updated <= now:
            observations[_run_key(run)] = run
    totals, kinds = _bucket(), {kind: _bucket() for kind in KINDS}
    cohorts: dict[tuple, dict] = defaultdict(_bucket)
    models: dict[str, Counter] = defaultdict(Counter)
    failure_counts: Counter = Counter()
    recent = []
    attempt_runs = set()
    for started, original in records:
        record = dict(original)
        finished_at = timestamp(record.get("finished_at"))
        if finished_at and finished_at > now:
            record.update(outcome="running", pick_count=0, workflow_validation=None)
        episode, context = record.get("episode") or {}, record.get("context") or {}
        source = episode.get("source") if episode.get("source") in SOURCES else "unknown"
        version = str(record.get("pipeline_version") or "unknown")
        kind, outcome = attempt_kind(record), record.get("outcome", "unknown")
        primary = str(context.get("transcription_model") or "unknown")
        extraction = str(context.get("extraction_model") or "unknown")
        bucket = _bucket()
        bucket["records"] = 1
        if outcome in bucket:
            bucket[outcome] += 1
        bucket["finished"] = int(outcome in FINISHED)
        preserved = bool(record.get("preserved_previous"))
        picks = record.get("pick_count")
        positive = isinstance(picks, int) and not isinstance(picks, bool) and picks > 0
        qualified = positive or record.get("zero_pick_disposition") == "confirmed_no_recommendations"
        successful = outcome in {"complete", "needs_review"}
        usable = successful and qualified and not preserved and record.get("workflow_validation") == "success"
        bucket["validated_usable"] = int(usable)
        bucket["empty_unconfirmed"] = int(successful and not qualified)
        bucket["preserved_previous"] = int(preserved)
        bucket["validation_unknown"] = int(successful and record.get("workflow_validation") not in {"success", "failure"})
        publication = _publication(record, observations) if usable else None
        if publication:
            bucket[f"publication_{publication}"] += 1
        events = [event for event in record.get("events", [])
                  if not timestamp(event.get("timestamp")) or timestamp(event["timestamp"]) <= now]
        failures = []
        for event in events:
            name = event.get("event")
            if name == "model_call":
                bucket["model_calls"] += 1
                failed = event.get("outcome") == "failed"
                bucket["failed_model_calls"] += int(failed)
                model = str(event.get("model") or "unknown")
                models[model]["calls"] += 1
                models[model]["failed"] += int(failed)
                models[model]["successful_response"] += int(event.get("outcome") == "success")
            elif name == "repair_timing_rejected":
                bucket["timing_rejections"] += 1
                models[str(event.get("model") or "unknown")]["timing_rejections"] += 1
            elif name == "checkpoint_reused":
                bucket["checkpoint_reuses"] += 1
            elif name == "transcript_reused":
                bucket["transcript_reuses"] += 1
            elif name == "model_circuit_skipped":
                bucket["circuit_skips"] += 1
            elif name == "failure":
                failures.append(str(event.get("message", "")))
        reason = failure_category(failures[-1]) if outcome in {"failed", "interrupted"} and failures else "unknown"
        if outcome in {"failed", "interrupted"}:
            failure_counts[reason] += 1
        for target in (totals, kinds[kind], cohorts[(source, version, kind, primary, extraction)]):
            for metric, count in bucket.items():
                target[metric] += count
        if outcome != "skipped":
            attempt_runs.add(_run_key(record))
        recent.append({"started_at": iso(started), "attempt_id": record.get("attempt_id"), "source": source,
                       "episode_number": episode.get("number"), "pipeline_version": version, "kind": kind,
                       "outcome": outcome, "picks": picks if outcome != "running" else None,
                       "validated_usable": bool(usable), "publication": publication,
                       "preserved_previous": preserved, "failure_category": reason if outcome in {"failed", "interrupted"} else None,
                       "run_id": record.get("run_id"), "run_attempt": record.get("run_attempt")})
    workflow_records = {}
    for path in sorted((state_dir / "runs").glob("*.json")):
        record = read_json(path, {})
        at = timestamp(record.get("timestamp"))
        if at and since <= at <= now:
            workflow_records[_run_key(record)] = {"journal": record}
    for key, run in observations.items():
        created = timestamp(run.get("created_at"))
        if created and since <= created <= now:
            workflow_records.setdefault(key, {})["observed"] = run
    workflows = []
    for key, item in sorted(workflow_records.items()):
        journal, observed = item.get("journal"), item.get("observed")
        jobs = (observed or {}).get("jobs", [])
        workflows.append({"run_id": key[0], "run_attempt": key[1],
                          "kind": _workflow_kind(journal, observed, key in attempt_runs),
                          "workflow_conclusion": (observed or {}).get("conclusion") or "unknown",
                          "workflow_status": (observed or {}).get("status") or "unknown",
                          "journal_validation": (journal or {}).get("validation") or "unknown",
                          "journal_pipeline_exit": (journal or {}).get("pipeline_exit_code"),
                          "persistence": next((step.get("conclusion") for job in jobs for step in job.get("steps", [])
                                               if step.get("name", "").startswith("Persist ")), "unknown"),
                          "pages": next((job.get("conclusion") or job.get("status") for job in jobs if job.get("name") == "deploy"),
                                        ("no_deploy_job" if (observed or {}).get("status") == "completed" else "not_yet_observed")
                                        if (observed or {}).get("jobs_observed") else "unknown")})
    catalog = read_json(archive_dir / "index.json", None)
    backlog = {"available": catalog is not None, "catalog_generated_at": (catalog or {}).get("metadata", {}).get("generated_at"),
               "episodes": 0, "picks": 0, "needs_review": 0, "failed": 0, "human_reviewed": 0, "sources": []}
    backlog_sources: dict[str, Counter] = defaultdict(Counter)
    review_reasons: Counter = Counter()
    for item in (catalog or {}).get("episodes", []):
        if item.get("synthetic") or str(item.get("guid", "")).startswith("ffw-synthetic-"):
            continue
        source = item.get("source_id") if item.get("source_id") in SOURCES else "unknown"
        measures = {"episodes": 1, "picks": int(item.get("pick_count") or 0),
                    "needs_review": int(item.get("processing_status") == "needs_review" or item.get("review_state") == "needs_review"),
                    "failed": int(item.get("processing_status") == "failed"), "human_reviewed": int(bool(item.get("human_reviewed")))}
        for name, count in measures.items():
            backlog[name] += count
            backlog_sources[source][name] += count
        if measures["needs_review"]:
            reason = str(item.get("review_reason") or "").lower()
            matched = False
            for category, patterns in (
                ("section_or_boundary", ("section", "ending", "block")),
                ("name_or_printing", ("card name", "printing", "foil", "ambiguous")),
                ("low_pick_count", ("fewer than", "missing pick", "low pick")),
                ("timing_or_coverage", ("timing", "timestamp", "missing from timed", "content missing")),
            ):
                if any(pattern in reason for pattern in patterns):
                    review_reasons[category] += 1
                    matched = True
            if not matched:
                review_reasons["other_or_unspecified"] += 1
    backlog["sources"] = [{"source": source, **dict(counts)} for source, counts in sorted(backlog_sources.items())]
    backlog["review_reasons"] = dict(sorted(review_reasons.items()))
    if invalid_times:
        notes.append(f"{invalid_times} attempt records with missing/invalid timezone-aware dates excluded.")
    if not all_attempts:
        notes.append("No dated live attempt journals available; zero records is not evidence of reliability.")
    if not catalog:
        notes.append("Archive catalog unavailable; current backlog is unknown.")
    if "unknown" in backlog_sources:
        notes.append(f"{backlog_sources['unknown']['episodes']} catalog entries lack an explicit supported source ID; grouped as Unknown rather than inferred.")
    if github.get("status") != "available":
        notes.append("GitHub workflow/job observations unavailable; publication and deployment are not inferred from validation.")
    return {"schema_version": 1, "report_generator_version": PIPELINE_VERSION,
            "as_of": iso(now), "window": {"start": iso(since), "end": iso(now), "days": days},
            "journal_coverage": {"first_recorded": iso(min(at for at, _ in all_attempts)) if all_attempts else None,
                                 "last_recorded": iso(max(at for at, _ in all_attempts)) if all_attempts else None,
                                 "dated_live_records": len(all_attempts), "excluded_invalid_dates": invalid_times},
            "totals": totals, "kinds": kinds,
            "cohorts": [{"source": key[0], "pipeline_version": key[1], "kind": key[2],
                         "transcription_model": key[3], "extraction_model": key[4], **counts}
                        for key, counts in sorted(cohorts.items())],
            "model_responses": [{"model": model, **dict(counts)} for model, counts in sorted(models.items())],
            "failure_categories": dict(sorted(failure_counts.items())), "recent_attempts": list(reversed(recent)),
            "workflows": workflows, "workflow_kinds": dict(Counter(row["kind"] for row in workflows)),
            "workflow_conclusions": dict(Counter(row["workflow_conclusion"] for row in workflows)),
            "pages_outcomes": dict(Counter(row["pages"] for row in workflows)),
            "no_op_pages_publications": sum(row["kind"] in {"no_op", "queue_no_op", "gated_skip"} and row["pages"] == "success" for row in workflows),
            "github_evidence": {name: github.get(name) for name in ("status", "observed_at", "runs_listed", "job_requests", "job_errors", "truncated", "error")},
            "backlog": backlog, "notes": notes}


def _cell(value: Any) -> str:
    return html.escape(str(value) if value is not None else "unknown").replace("|", "&#124;").replace("\n", " ").replace("\r", " ")


def render_health_markdown(report: dict, repository: str = "courtjester15/ManaIntel") -> str:
    def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
        return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                *["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows], ""]
    def rate(bucket: dict) -> str:
        n = bucket["finished"]
        return f"{bucket['validated_usable']}/{n} ({bucket['validated_usable'] / n:.0%})" if n else "No finished sample"
    lines = ["# ManaIntel processing health", "", f"As of **{report['as_of']}** · trailing {report['window']['days']} days · generator {report['report_generator_version']}", "",
             "This is a report of recorded evidence, not an uptime or extraction-accuracy score. Initial attempts, retries and forced recoveries have separate denominators.", "",
             "## Recorded episode outcomes", ""]
    lines += table(["Attempt kind", "Finished", "Validated usable result", "Complete", "Needs review", "Failed", "Interrupted", "Old result preserved"],
                   [[kind, b["finished"], rate(b), b["complete"], b["needs_review"], b["failed"], b["interrupted"], b["preserved_previous"]]
                    for kind, b in report["kinds"].items() if b["records"]])
    lines += ["A validated usable result means a new complete/needs-review extraction with picks (or an explicit confirmed-no-recommendations disposition) and successful archive validation. An unexplained empty result, preserved previous output, skip, or in-progress attempt is not a new usable result. Human/source correctness is not established by this measure.", "",
              f"Skipped records: {report['totals']['skipped']}; in progress: {report['totals']['running']}; unexplained empty results: {report['totals']['empty_unconfirmed']}.", "",
              f"Verified persistence + Pages for usable results: **{report['totals']['publication_verified']}**; completed runs without both observed: {report['totals']['publication_not_observed']}; unknown/in progress: {report['totals']['publication_unknown']}.", "",
              "## Source, version and configured-model cohorts", ""]
    lines += table(["Source", "Pipeline", "Kind", "Transcription / extraction model", "Finished", "Usable", "Failed", "Needs review", "Publication verified"],
                   [[SOURCES.get(b["source"], "Unknown"), b["pipeline_version"], b["kind"],
                     b["transcription_model"] if b["transcription_model"] == b["extraction_model"] else f"{b['transcription_model']} / {b['extraction_model']}",
                     b["finished"], b["validated_usable"], b["failed"], b["needs_review"], b["publication_verified"]] for b in report["cohorts"]])
    current = [b for b in report["cohorts"] if b["pipeline_version"] == report["report_generator_version"] and b["kind"] == "initial"]
    lines += [f"Initial-attempt sample on current generator/pipeline version: **{sum(b['finished'] for b in current)}**. A short recovery experiment does not establish sustained unattended reliability; this report alone does not satisfy the 0.6 release gate.", "", "## Observed model responses", ""]
    lines += table(["Model", "Calls", "Successful responses", "Failed responses", "Rejected timing responses"],
                   [[b["model"], b.get("calls", 0), b.get("successful_response", 0), b.get("failed", 0), b.get("timing_rejections", 0)] for b in report["model_responses"]])
    lines += [f"Checkpoint/clip reuse events: {report['totals']['checkpoint_reuses']}; retained-transcript reuse events: {report['totals']['transcript_reuses']}; unavailable-model skips: {report['totals']['circuit_skips']}.", "",
              "A successful provider response may still fail semantic timing checks. Rejection counts are additional quality signals, not extra provider calls. Missing older telemetry is not reconstructed.", "", "## Failed/interrupted attempt causes", ""]
    lines += table(["Cause category", "Attempts"], [[name, count] for name, count in report["failure_categories"].items()])
    lines += ["These are message-based terminal categories, not independently verified root-cause verdicts. Provider response counts separately expose outages hidden inside composite repair errors. Raw exceptions, transcript bodies and private recovery notes are not copied here.", "", "## Workflow and deployment evidence", ""]
    lines += table(["Workflow class", "Recorded/observed run attempts"], [[name, count] for name, count in sorted(report["workflow_kinds"].items())])
    lines += table(["Observed workflow conclusion", "Run attempts"], [[name, count] for name, count in sorted(report["workflow_conclusions"].items())])
    lines += table(["Pages job outcome", "Run attempts"], [[name, count] for name, count in sorted(report["pages_outcomes"].items())])
    lines += [f"Observed no-op/gated runs with a successful Pages job: **{report['no_op_pages_publications']}**. This exposes publication churn separately from useful processing.", ""]
    lines += ["Workflow results, validation, persistence and Pages are distinct. A failed workflow can deploy a valid failure record. Unknown is not success. Push runs of ffw.yml are deploy-only; unclassified manual dispatches are not guessed to be no-ops or deploy-only.", "",
              f"GitHub evidence: {_cell(report['github_evidence'].get('status'))}; job requests: {report['github_evidence'].get('job_requests') or 0}; failed job reads: {report['github_evidence'].get('job_errors') or 0}; bounded/truncated evidence: {bool(report['github_evidence'].get('truncated'))}. The current workflow may still be running when its summary is generated.", "", "## Current archive and review backlog", ""]
    b = report["backlog"]
    if b["available"]:
        lines += [f"Catalog snapshot: {b['catalog_generated_at'] or 'date unknown'}. **{b['episodes']} live episodes, {b['picks']} picks, {b['needs_review']} episodes needing review, {b['failed']} currently failed, {b['human_reviewed']} explicitly human-reviewed.**", ""]
        lines += table(["Source", "Episodes", "Picks", "Needs review", "Failed", "Human reviewed"],
                       [[SOURCES.get(row["source"], "Unknown"), *[row.get(key, 0) for key in ("episodes", "picks", "needs_review", "failed", "human_reviewed")]] for row in b["sources"]])
        lines += table(["Review reason (may overlap)", "Episodes"], [[name, count] for name, count in b["review_reasons"].items()])
    else:
        lines += ["Current archive/backlog unknown: no catalog snapshot is available.", ""]
    lines += ["This snapshot is separate from historical attempt outcomes; a later recovery does not erase earlier failures. Machine-approved is not the same as human-reviewed. These are recorded archive counts, not total feed coverage.", "", "## Recent episode attempts", ""]
    lines += table(["UTC start", "Source / episode", "Version", "Kind", "Outcome", "Picks", "Publication evidence", "Run"],
                   [[row["started_at"], f"{SOURCES.get(row['source'], 'Unknown')} {row['episode_number']}", row["pipeline_version"], row["kind"], row["outcome"], row["picks"], row["publication"] or "not a usable new result",
                     f"[{row['run_id']}](https://github.com/{repository}/actions/runs/{row['run_id']})" if str(row.get("run_id", "")).isdigit() else "not recorded"] for row in report["recent_attempts"][:15]])
    coverage = report["journal_coverage"]
    lines += ["## Coverage and limits", "", f"Live attempt journals first recorded: {coverage['first_recorded'] or 'unknown'}; latest recorded: {coverage['last_recorded'] or 'unknown'}. No historical attempt backfill is implied.", "",
              "The window uses UTC attempt start times and includes only dated live records. Synthetic fixtures are excluded. Source/model/version cohorts can have very different sample sizes and forced-recovery selection bias. No financial-performance or source-accuracy claims are made.", ""]
    lines += [f"- {_cell(note)}" for note in report["notes"]]
    return "\n".join(lines).rstrip() + "\n"


def fetch_github_evidence(repository: str, *, as_of: datetime, days: int = 14, max_job_requests: int = 60,
                          priority_runs: set[str] | None = None) -> dict:
    """At most three run-list requests and a bounded set of metadata-only job reads."""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("GitHub repository must be owner/name.")
    deadline = time.monotonic() + 90
    def api(endpoint: str, *fields: str) -> dict:
        command = ["gh", "api", "--method", "GET", endpoint]
        for field in fields:
            command.extend(["-f", field])
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("GitHub metadata observation time budget exhausted.")
        result = subprocess.run(command, capture_output=True, text=True, timeout=min(15, remaining))
        if result.returncode:
            raise RuntimeError("GitHub metadata read failed; workflow/deployment evidence remains unknown.")
        return json.loads(result.stdout)
    runs = []
    truncated = False
    for page in range(1, 4):
        data = api(f"repos/{repository}/actions/runs", "per_page=100", f"page={page}",
                   f"created=>={iso(as_of - timedelta(days=days))}")
        batch = data.get("workflow_runs", [])
        runs.extend(batch)
        if len(batch) < 100:
            break
        if page == 3:
            truncated = True
    result = {"status": "available", "observed_at": iso(as_of), "runs_listed": len(runs),
              "job_requests": 0, "job_errors": 0, "truncated": truncated, "runs": []}
    consecutive_errors = 0
    for run in sorted(runs, key=lambda row: (str(row.get("id")) in (priority_runs or set()), row.get("created_at", "")), reverse=True):
        row = {"run_id": str(run["id"]), "run_attempt": str(run.get("run_attempt") or 1),
               **{name: run.get(name) for name in ("created_at", "updated_at", "path", "event", "status", "conclusion")},
               "jobs_observed": False, "jobs": []}
        if str(row.get("path") or "").endswith(("/ffw.yml", "/review.yml", "/reprocess-queue.yml")):
            if result["job_requests"] < max_job_requests and time.monotonic() < deadline and consecutive_errors < 3:
                try:
                    jobs = api(f"repos/{repository}/actions/runs/{row['run_id']}/attempts/{row['run_attempt']}/jobs", "per_page=100")
                    row["jobs"] = [{"name": job.get("name"), "conclusion": job.get("conclusion"), "status": job.get("status"),
                                    "steps": [{"name": step.get("name"), "conclusion": step.get("conclusion")} for step in job.get("steps", [])
                                              if str(step.get("name", "")).startswith("Persist ")]} for job in jobs.get("jobs", [])]
                    row["jobs_observed"] = True
                    consecutive_errors = 0
                    if jobs.get("total_count", len(row["jobs"])) > len(row["jobs"]):
                        result["truncated"] = True
                except (OSError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired):
                    row["jobs_error"] = True
                    result["job_errors"] += 1
                    consecutive_errors += 1
                result["job_requests"] += 1
            else:
                result["truncated"] = True
        result["runs"].append(row)
    return result
