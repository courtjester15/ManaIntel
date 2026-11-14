"""Read-only comparison against explicitly scoped, transcript-checked expectations.

This is not an audio accuracy score or an episode completeness certification.
"""
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "tests/fixtures/evaluation_inventory.json"


def normalized(value):
    return " ".join(str(value or "").casefold().split())


def compare(case, summary):
    """Match by explicit name aliases, never pick IDs or fuzzy catalog guesses."""
    if not isinstance(summary, dict) or not isinstance(summary.get("episode"), dict):
        raise ValueError("Candidate must be an episode summary object")
    if summary.get("episode", {}).get("guid") != case["episode_guid"]:
        raise ValueError("Candidate episode GUID does not match the evaluation case")
    picks = summary.get("recommendations", [])
    if not isinstance(picks, list) or any(not isinstance(pick, dict) for pick in picks):
        raise ValueError("Candidate recommendations must be a list of pick objects")
    findings = []
    assertions = []
    for expected in case["expected_picks"]:
        label = expected["cards"][0]
        aliases = {normalized(name) for name in expected["cards"]}
        matches = [pick for pick in picks if normalized(pick.get("card")) in aliases]
        rules = [("equals", field, wanted) for field, wanted in expected.get("equals", {}).items()]
        rules += [("printing_contains", "printing", term) for term in expected.get("printing_contains", [])]
        if "start_window" in expected:
            rules.append(("start_window", "start_seconds", expected["start_window"]))
        def record(rule, field, detail, status):
            assertions.append({"id": json.dumps([label, rule, field, detail], sort_keys=True),
                               "card": label, "field": field, "status": status})
        record("presence", "presence", None, "passed" if len(matches) == 1 else "failed")
        if len(matches) != 1:
            findings.append({"card": label, "field": "presence",
                             "problem": "missing" if not matches else "ambiguous multiplicity"})
            for rule, field, wanted in rules:
                record(rule, field, wanted, "blocked")
            continue
        pick = matches[0]
        for field, wanted in expected.get("equals", {}).items():
            actual = pick.get(field)
            # A target with null bounds is the archive's empty-target representation.
            if field.endswith("_target") and isinstance(actual, dict) and wanted is None:
                actual = None if all(actual.get(key) is None for key in ("minimum", "maximum")) else actual
            if actual != wanted:
                findings.append({"card": label, "field": field, "expected": wanted, "actual": actual})
            record("equals", field, wanted, "passed" if actual == wanted else "failed")
        for term in expected.get("printing_contains", []):
            passed = normalized(term) in normalized(pick.get("printing"))
            if not passed:
                findings.append({"card": label, "field": "printing", "missing_term": term})
            record("printing_contains", "printing", term, "passed" if passed else "failed")
        if "start_window" in expected:
            start = pick.get("start_seconds")
            low, high = expected["start_window"]
            passed = not isinstance(start, bool) and isinstance(start, (int, float)) and low <= start <= high
            if not passed:
                findings.append({"card": label, "field": "start_seconds", "expected_window": [low, high], "actual": start})
            record("start_window", "start_seconds", expected["start_window"], "passed" if passed else "failed")
    return {"case": case["id"], "basis": case["basis"], "scope": case["scope"],
            "expected_assertions": len(assertions),
            "checked_assertions": sum(item["status"] != "blocked" for item in assertions),
            "assertions": assertions, "findings": findings, "unscored": case["unscored"]}


def compare_change(case, baseline, candidate):
    """Compare the same scoped assertions; missing picks block their field checks."""
    before, after = compare(case, baseline), compare(case, candidate)
    previous = {item["id"]: item for item in before["assertions"]}
    changes = {"regressions": [], "resolved": [], "still_unresolved": []}
    for item in after["assertions"]:
        old = previous[item["id"]]["status"]
        new = item["status"]
        change = dict(item, before=old, after=new)
        if old == "passed" and new != "passed":
            changes["regressions"].append(change)
        elif old != "passed" and new == "passed":
            changes["resolved"].append(change)
        elif new != "passed":
            changes["still_unresolved"].append(change)
    return {"baseline": before, "candidate": after, **changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--archive", type=Path, default=ROOT / "archive")
    parser.add_argument("--case", help="Evaluate one named case")
    parser.add_argument("--candidate", type=Path, help="Candidate summary JSON; requires --case")
    baselines = parser.add_mutually_exclusive_group()
    baselines.add_argument("--baseline", type=Path, help="Baseline summary JSON; requires --case")
    baselines.add_argument("--baseline-archive", type=Path, help="Baseline archive root for the selected cases")
    args = parser.parse_args()
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    cases = [case for case in inventory["cases"] if not args.case or case["id"] == args.case]
    if not cases or ((args.candidate or args.baseline) and not args.case):
        parser.error("Select a valid --case; --candidate and --baseline require --case")
    results = []
    try:
        for case in cases:
            path = args.candidate or args.archive / case["summary_path"]
            candidate = json.loads(path.read_text(encoding="utf-8"))
            baseline_path = args.baseline or (args.baseline_archive / case["summary_path"] if args.baseline_archive else None)
            results.append(compare_change(case, json.loads(baseline_path.read_text(encoding="utf-8")), candidate)
                           if baseline_path else compare(case, candidate))
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps({"notice": inventory["notice"], "results": results}, indent=2))
    return int(any(result.get("candidate", result)["findings"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
