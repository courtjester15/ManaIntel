from copy import deepcopy
from io import BytesIO
import json
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

from ffw.archive import rebuild_catalog
from ffw.cli import main
from ffw.config import Settings
from ffw.publication import (catalog_findings, expected_publication, json_differences,
                             read_publication_json, verify_publication)
from ffw.rendering import render_episode_markdown
from ffw.reviews import persist_review
from ffw.utils import atomic_write_json, atomic_write_text, load_json
from ffw.validation import validate_archive
from tests.test_reviews import summary, payload, pick
from tests.workspace import workspace_temp


class PublicationFidelityTests(unittest.TestCase):
    def setUp(self):
        self.root = workspace_temp(self)
        self.archive = self.root / "archive"
        self.state = self.root / "state/episodes.json"
        self.reviews = self.root / "data/reviews"
        self.directory = self.archive / "episodes/review-fixture"
        self.source = summary()
        self.source["episode"]["title"] = "Invented review \u2014 speaker\u2019s notes\u2026"
        self.source["recommendations"][0] = pick(self.source["episode"]["guid"], "Invented J\u00f8rn", 620, "Art \u2014 foil")
        self.source["recommendations"][0]["evidence_excerpt"] = "Invented speaker\u2019s rationale: caf\u00e9 \U0001f9d9"
        atomic_write_json(self.directory / "summary.json", self.source)
        atomic_write_text(self.directory / "summary.md", render_episode_markdown(self.source))
        atomic_write_json(self.directory / "metadata.json", {"synthetic": False, "episode": self.source["episode"],
                          "processing": self.source["processing"], "outputs": {
                              "summary_json": "episodes/review-fixture/summary.json",
                              "summary_markdown": "episodes/review-fixture/summary.md"}})
        atomic_write_json(self.state, {"episodes": {self.source["episode"]["guid"]: {"status": "needs_review"}}})
        self.rebuild()

    def rebuild(self):
        return rebuild_catalog(self.archive, production=True, reviews_dir=self.reviews,
                               resolutions_path=self.state.parent / "card-resolutions.json")

    def expected(self):
        return expected_publication(self.archive, self.state, reviews_dir=self.reviews)

    def codes(self):
        return {issue.code for issue in validate_archive(self.archive, self.state, reviews_dir=self.reviews)}

    def test_utf8_values_round_trip_independent_of_locale_and_console(self):
        raw = (self.archive / "cards.json").read_bytes()
        expected = self.source["recommendations"][0]["evidence_excerpt"]
        card = next(p for p in read_publication_json(raw)["cards"] if p["start_seconds"] == 620)
        self.assertEqual(expected, card["evidence_excerpt"])
        self.assertNotEqual(json.loads(raw.decode("cp1252")), read_publication_json(raw))
        report = verify_publication(self.archive, self.state, site_dir=self.root, reviews_dir=self.reviews)
        self.assertTrue(report["verified"], report)
        self.assertFalse(self.codes())

    def test_field_drift_with_unchanged_ids_and_counts_is_rejected(self):
        original = load_json(self.archive / "cards.json")
        for field, value in (("evidence_excerpt", "Secret changed excerpt"), ("mentioned_price", "$100"),
                             ("entry_target", {"raw": "five", "currency": "USD", "minimum": 5, "maximum": 5}),
                             ("human_reviewed", True), ("hosts", ["Guessed Speaker"]),
                             ("printing", "Art \ufffd foil")):
            with self.subTest(field=field):
                cards = deepcopy(original)
                cards["cards"][0][field] = value
                atomic_write_json(self.archive / "cards.json", cards)
                issues = validate_archive(self.archive, self.state, reviews_dir=self.reviews)
                self.assertIn("catalog_field_drift", {issue.code for issue in issues})
                self.assertTrue(any(field in issue.path for issue in issues if issue.code == "catalog_field_drift"))
                self.assertNotIn("Secret changed excerpt", str(issues))

    def test_duplicate_catalog_row_cannot_hide_behind_a_set_of_ids(self):
        cards = load_json(self.archive / "cards.json")
        cards["cards"].append(deepcopy(cards["cards"][0]))
        cards["count"] += 1
        atomic_write_json(self.archive / "cards.json", cards)
        self.assertIn("catalog_field_drift", self.codes())

    def test_coordinated_removal_from_every_catalog_still_finds_retained_episode(self):
        index = load_json(self.archive / "index.json")
        index.update(episodes=[], recent_picks=[], latest_episode=None, status_counts={})
        index["counts"] = dict.fromkeys(index["counts"], 0)
        index["metadata"].update(real_episode_count=0, real_pick_count=0, sources=[],
                                 latest_successful_run_at=None, last_discovered_episode_date=None)
        atomic_write_json(self.archive / "index.json", index)
        cards = load_json(self.archive / "cards.json")
        cards.update(cards=[], count=0)
        atomic_write_json(self.archive / "cards.json", cards)
        self.assertIn("catalog_field_drift", self.codes())

    def test_dashboard_and_episode_context_are_compared_to_retained_metadata(self):
        original = load_json(self.archive / "index.json")
        for field in ("episodes", "recent_picks", "latest_episode", "counts", "status_counts"):
            with self.subTest(field=field):
                index = deepcopy(original)
                index[field] = [] if isinstance(index[field], list) else {}
                atomic_write_json(self.archive / "index.json", index)
                self.assertIn("catalog_field_drift", self.codes())

    def test_read_only_projection_and_validation_cannot_repair_bad_effective_files(self):
        persist_review(self.archive, self.reviews, payload(self.source), actor="Reviewer")
        self.rebuild()
        path = self.directory / "effective.json"
        value = load_json(path)
        value["recommendations"][0]["evidence_excerpt"] = "Changed in effective file"
        atomic_write_json(path, value)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        self.expected()
        self.assertIn("effective_summary_drift", self.codes())
        after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        missing = self.root / "never-created"
        rebuild_catalog(missing, write=False)
        self.assertFalse(missing.exists())

    def test_reviews_and_cached_resolutions_are_expected_not_discarded(self):
        request = payload(self.source)
        request["operations"] = [{"action": "update", "pick_id": self.source["recommendations"][0]["id"],
                                  "changes": {"mentioned_price": "historical five", "entry_target": None, "hosts": []}}]
        persist_review(self.archive, self.reviews, request, actor="Reviewer")
        pick_id = self.source["recommendations"][0]["id"]
        atomic_write_json(self.state.parent / "card-resolutions.json", {"schema_version": "1.0.0", "resolutions": {
            pick_id: {"raw_name": self.source["recommendations"][0]["card"], "normalized_name": "invented jorn",
                      "status": "verified", "canonical_name": "Invented J\u00f8rn", "oracle_id": "fixture-id",
                      "resolver_version": "test"}}})
        self.rebuild()
        self.assertFalse(self.codes())
        self.assertTrue(verify_publication(self.archive, self.state, site_dir=self.root, reviews_dir=self.reviews)["verified"])
        cards = load_json(self.archive / "cards.json")
        cards["cards"][0].pop("card_resolution", None)
        cards["cards"][0]["human_reviewed"] = False
        atomic_write_json(self.archive / "cards.json", cards)
        self.assertIn("catalog_field_drift", self.codes())

    def test_remote_check_is_three_bounded_reads_and_fails_closed_on_invalid_json(self):
        documents = self.expected()
        calls = []
        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            name = request.full_url.rsplit("/", 1)[1]
            return BytesIO(json.dumps(documents[name], ensure_ascii=False).encode("utf-8"))
        report = verify_publication(self.archive, self.state, url="https://example.test/site/", reviews_dir=self.reviews, opener=opener)
        self.assertTrue(report["verified"], report)
        self.assertEqual(3, len(calls))
        self.assertTrue(all(timeout == 20 for _, timeout in calls))
        bad = verify_publication(self.archive, self.state, url="https://example.test/", reviews_dir=self.reviews,
                                 opener=lambda *a, **k: BytesIO(b'not json'))
        self.assertFalse(bad["verified"])
        self.assertEqual(3, len(bad["findings"]))
        with self.assertRaises(ValueError):
            read_publication_json(b'{"title":"\x92"}')

    def test_only_build_time_value_is_ignored_and_diagnostics_are_bounded(self):
        expected = self.expected()
        actual = deepcopy(expected)
        actual["index.json"]["metadata"]["generated_at"] = "2026-02-02T02:02:02Z"
        self.assertFalse(catalog_findings(expected, actual))
        actual["index.json"]["metadata"]["pipeline_version"] = "wrong-release"
        self.assertTrue(catalog_findings(expected, actual))
        actual["index.json"]["metadata"]["generated_at"] = "not a date"
        self.assertTrue(any(row["problem"] == "invalid_build_time" for row in catalog_findings(expected, actual)))
        self.assertEqual(["/flag"], json_differences({"flag": False}, {"flag": 0}))
        self.assertEqual(5, len(json_differences(list(range(1000)), [-1] * 1000, limit=5)))

    def test_cli_exit_statuses_and_report_match_the_actual_publication(self):
        settings = Settings(self.root, self.archive, self.state, self.root / ".ffw-work")
        output = self.root / "report.json"
        with patch("ffw.cli.Settings.load", return_value=settings), redirect_stdout(StringIO()) as stdout:
            self.assertEqual(0, main(["verify-publication", "--site-dir", str(self.root), "--output-json", str(output)]))
            self.assertTrue(json.loads(stdout.getvalue())["verified"])
            self.assertTrue(load_json(output)["verified"])
            cards = load_json(self.archive / "cards.json")
            cards["cards"][0]["evidence_excerpt"] = "Changed excerpt"
            atomic_write_json(self.archive / "cards.json", cards)
            self.assertEqual(1, main(["verify-publication", "--site-dir", str(self.root)]))
            for url in ("file:///not-a-site", "", "https://example.test/?query=value"):
                self.assertEqual(2, main(["verify-publication", "--url", url]))

    def test_failed_and_confirmed_empty_episodes_are_not_lost_or_miscounted(self):
        for disposition in ("failed", "no_recommendations"):
            with self.subTest(disposition=disposition):
                metadata = load_json(self.directory / "metadata.json")
                metadata["episode"]["guid"] = "another:" + disposition
                metadata["processing"].update(status="failed" if disposition == "failed" else "complete",
                                              review_state=disposition, error={"message": "Provider unavailable"} if disposition == "failed" else None)
                directory = self.archive / "episodes" / disposition
                atomic_write_json(directory / "metadata.json", metadata)
                state = load_json(self.state)
                state["episodes"][metadata["episode"]["guid"]] = {"status": metadata["processing"]["status"]}
                atomic_write_json(self.state, state)
                self.rebuild()
                self.assertFalse(self.codes())
                self.assertTrue(verify_publication(self.archive, self.state, site_dir=self.root, reviews_dir=self.reviews)["verified"])


if __name__ == "__main__":
    unittest.main()
