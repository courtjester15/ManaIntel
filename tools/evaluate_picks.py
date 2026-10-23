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
    checked = 0
    for expected in case["expected_picks"]:
        label = expected["cards"][0]
        aliases = {normalized(name) for name in expected["cards"]}
        matches = [pick for pick in picks if normalized(pick.get("card")) in aliases]
        checked += 1
        if len(matches) != 1:
            findings.append({"card": label, "field": "presence",
                             "problem": "missing" if not matches else "ambiguous multiplicity"})
            continue
        pick = matches[0]
        for field, wanted in expected.get("equals", {}).items():
            checked += 1
            actual = pick.get(field)
            # A target with null bounds is the archive's empty-target representation.
            if field.endswith("_target") and isinstance(actual, dict) and wanted is None:
                actual = None if all(actual.get(key) is None for key in ("minimum", "maximum")) else actual
            if actual != wanted:
                findings.append({"card": label, "field": field, "expected": wanted, "actual": actual})
        for term in expected.get("printing_contains", []):
            checked += 1
            if normalized(term) not in normalized(pick.get("printing")):
                findings.append({"card": label, "field": "printing", "missing_term": term})
        if "start_window" in expected:
            checked += 1
            start = pick.get("start_seconds")
            low, high = expected["start_window"]
            if isinstance(start, bool) or not isinstance(start, (int, float)) or not low <= start <= high:
                findings.append({"card": label, "field": "start_seconds", "expected_window": [low, high], "actual": start})
    return {"case": case["id"], "basis": case["basis"], "scope": case["scope"],
            "checked_assertions": checked, "findings": findings, "unscored": case["unscored"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--archive", type=Path, default=ROOT / "archive")
    parser.add_argument("--case", help="Evaluate one named case")
    parser.add_argument("--candidate", type=Path, help="Candidate summary JSON; requires --case")
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    cases = [case for case in inventory["cases"] if not args.case or case["id"] == args.case]
    if not cases or (args.candidate and not args.case):
        parser.error("Select a valid --case; --candidate requires --case")
    results = []
    try:
        for case in cases:
            path = args.candidate or args.archive / case["summary_path"]
            results.append(compare(case, json.loads(path.read_text(encoding="utf-8"))))
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps({"notice": inventory["notice"], "results": results}, indent=2))
    return int(any(result["findings"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
