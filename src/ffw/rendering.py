from __future__ import annotations

from typing import Any


def _target(value: dict[str, Any] | None) -> str:
    return "Not stated" if value is None else value.get("raw") or "Not stated"


def _text(value: Any) -> str:
    return "Not stated" if value in (None, "", []) else str(value)


def render_episode_markdown(summary: dict[str, Any]) -> str:
    episode = summary["episode"]
    processing = summary["processing"]
    lines = [
        f"# Episode {episode['episode_number']}: {episode['title']}",
        "",
    ]
    if summary.get("synthetic"):
        lines.extend(["> **Synthetic fixture:** This document contains generated test data only. It does not represent real podcast commentary or financial advice.", ""])
    else:
        lines.extend(["> Automated transcription and extraction. Verify recommendations against the linked source audio.", ""])
    lines.extend([
        f"- Published: {episode['published_at']}",
        f"- Hosts: {', '.join(episode['hosts']) or 'Not identified'}",
        f"- Processing status: {processing['status'].replace('_', ' ').title()}",
        f"- Episode source: {episode['episode_url']}",
        "",
        f"## {summary.get('section', {}).get('label', 'Recommendations')}",
        "",
    ])
    if not summary["recommendations"]:
        lines.extend(["No recommendations were extracted.", ""])
    for pick in summary["recommendations"]:
        lines.extend(
            [
                f"### {pick['card']}",
                "",
                f"- Printing: {_text(pick['printing'])}",
                f"- Printing certainty: {_text(pick['printing_certainty'])}",
                f"- Host(s): {', '.join(pick['hosts'])}",
                f"- Recommendation: {pick['recommendation']}",
                f"- Entry: {_target(pick['entry_target'])}",
                f"- Hold: {_text(pick['hold'])}",
                f"- Exit: {_target(pick['exit_target'])}",
                f"- Confidence: {_text(pick['confidence'])}",
                f"- Timestamp: {_text(pick['timestamp'])}",
                f"- Review status: {pick['review_status'].replace('_', ' ').title()}",
                "",
                "**Reasoning**",
                "",
            ]
        )
        lines.extend([f"- {reason}" for reason in pick["reasoning"]] or ["- Not stated"])
        lines.extend(["", "**Caveats**", ""])
        lines.extend([f"- {caveat}" for caveat in pick["caveats"]] or ["- None stated"])
        lines.extend(["", f"> Evidence: {pick['evidence_excerpt']}", ""])
    lines.extend(
        [
            "---",
            "",
            f"Schema {summary['schema_version']} · Pipeline {processing['pipeline_version']} · Prompt {processing['prompt_version']}",
            "",
        ]
    )
    return "\n".join(lines)
