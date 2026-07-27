from __future__ import annotations

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .archive import rerender_archive
from .config import Settings, VERSION
from .pipeline import Pipeline
from .validation import validate_archive
from .utils import atomic_write_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ffw", description="FFW pipeline and local archive")
    parser.add_argument("--version", action="version", version=f"FFW {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run the idempotent pipeline")
    run.add_argument("--force", action="store_true", help="Regenerate terminal fixture episodes")
    run.add_argument("--live", action="store_true", help="Use the live feed and configured production adapters")
    run.add_argument("--limit", type=int, help="Process the newest N eligible episodes (legacy backfill alias)")
    run.add_argument("--retry-failed", action="store_true", help="Select failed live episodes only")
    run.add_argument("--force-guid", help="Process only this episode GUID")
    run.add_argument("--source", choices=("mtg-fast-finance", "brainstorm-brewery"), help="Limit discovery to one podcast source")
    run.add_argument("--report-json", type=Path, help=argparse.SUPPRESS)
    subparsers.add_parser("validate", help="Validate state, episode outputs, and archive catalogs")
    subparsers.add_parser("render", help="Regenerate Markdown and archive catalogs from JSON")
    next_episode = subparsers.add_parser("process-next", help="Process the newest eligible unprocessed episode")
    next_episode.add_argument("--live", action="store_true", help="Use the live feed and configured production adapters")
    next_episode.add_argument("--report-json", type=Path, help=argparse.SUPPRESS)
    next_episode.add_argument("--source", choices=("mtg-fast-finance", "brainstorm-brewery"))
    backfill = subparsers.add_parser("backfill", help="Process the newest eligible unprocessed episodes")
    backfill.add_argument("--force", action="store_true", default=True, help=argparse.SUPPRESS)
    backfill.add_argument("--live", action="store_true", help="Backfill the live feed")
    backfill.add_argument("--limit", type=int, default=1, help="Eligible live episodes to attempt (1-20)")
    backfill.add_argument("--report-json", type=Path, help=argparse.SUPPRESS)
    backfill.add_argument("--source", choices=("mtg-fast-finance", "brainstorm-brewery"))
    retry = subparsers.add_parser("retry-failed", help="Retry failed live episodes")
    retry.add_argument("--live", action="store_true", help="Use the live feed and configured production adapters")
    retry.add_argument("--limit", type=int, default=1, help="Failed live episodes to retry (1-20)")
    retry.add_argument("--report-json", type=Path, help=argparse.SUPPRESS)
    retry.add_argument("--source", choices=("mtg-fast-finance", "brainstorm-brewery"))
    subparsers.add_parser("process-latest", help="Process only the latest synthetic fixture")
    serve = subparsers.add_parser("serve", help="Serve the repository for the local archive application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _print_results(results: list) -> None:
    for result in results:
        print(f"{result.status:12} {result.guid:28} picks={result.pick_count:2}  {result.message}")


def _run_pipeline(settings: Settings, *, report_json: Path | None = None, **options) -> tuple[list, int]:
    try:
        pipeline = Pipeline.from_settings(settings)
        results = pipeline.run(**options)
    except (RuntimeError, ValueError) as error:
        print(f"Configuration error: {error}")
        return [], 2
    selection = pipeline.last_selection
    print(f"Selection policy: {selection.policy}")
    print(f"Feed entries scanned: {selection.feed_entries_scanned}")
    print(f"Skipped completed: {selection.completed_skipped}")
    print(f"Skipped failed: {selection.failed_skipped}")
    print(f"Retry deferred: {selection.retry_deferred}")
    print(f"Retry exhausted/quarantined: {selection.retry_exhausted}")
    print(f"Eligible found: {selection.eligible_found}")
    if selection.selected:
        print(f"Selected newest eligible episode: {selection.selected[0].title}")
    _print_results(results)
    if not results:
        print("No eligible episodes remain; no archive or state changes were made.")
    if report_json:
        report = pipeline.last_selection.as_dict()
        report["attempted"] = len(results)
        report["completed"] = sum(item.status == "complete" for item in results)
        report["needs_review"] = sum(item.status == "needs_review" for item in results)
        report["failed"] = sum(item.status == "failed" for item in results)
        atomic_write_json(report_json, report)
    return results, 1 if any(item.status == "failed" for item in results) else 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings.load()
    requested_live = bool(getattr(args, "live", False) or args.command == "retry-failed")
    if requested_live and settings.mode != "live":
        settings = Settings.load()
        settings = Settings(**{**settings.__dict__, "mode": "live"})
    if args.command == "run":
        policy = "exact_guid" if args.force_guid else "failed_only" if args.retry_failed else "backfill" if args.limit is not None else "next" if args.live else "backfill"
        _, exit_code = _run_pipeline(settings, report_json=args.report_json, force=args.force or bool(args.force_guid), limit=args.limit, force_guid=args.force_guid, selection_policy=policy, source_id=args.source)
        return exit_code
    if args.command == "process-next":
        _, exit_code = _run_pipeline(settings, report_json=args.report_json, selection_policy="next", source_id=args.source)
        return exit_code
    if args.command == "backfill":
        _, exit_code = _run_pipeline(settings, report_json=args.report_json, force=not args.live, limit=args.limit if args.live else None, selection_policy="backfill", source_id=args.source)
        return exit_code
    if args.command == "retry-failed":
        _, exit_code = _run_pipeline(settings, report_json=args.report_json, limit=args.limit, selection_policy="failed_only", source_id=args.source)
        return exit_code
    if args.command == "process-latest":
        _, exit_code = _run_pipeline(settings, selection_policy="next")
        return exit_code
    if args.command == "render":
        count = rerender_archive(settings.archive_dir, production=settings.mode == "live")
        print(f"Rendered {count} episode Markdown files and rebuilt archive catalogs.")
        return 0
    if args.command == "validate":
        issues = validate_archive(
            settings.archive_dir,
            settings.state_file,
            settings.root / "schemas/cards-to-watch.schema.json",
            expected_production=settings.mode == "live",
        )
        if not issues:
            print("Validation passed with no issues.")
            return 0
        for issue in issues:
            print(f"{issue.severity.upper():7} {issue.code:28} {issue.path}: {issue.message}")
        return 1 if any(issue.severity == "error" for issue in issues) else 0
    if args.command == "serve":
        os.chdir(settings.root)
        handler = partial(SimpleHTTPRequestHandler, directory=str(settings.root))
        server = ThreadingHTTPServer((args.host, args.port), handler)
        print(f"FFW archive: http://{args.host}:{args.port}/web/")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
        finally:
            server.server_close()
        return 0
    return 2
