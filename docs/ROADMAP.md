# ManaIntel Roadmap

ManaIntel is entering maintenance mode. After the final functional pass below, active product work moves to putting ManaSpec in users' hands and then to GalleyFlow. ManaIntel should receive further development only when a real production failure prevents its basic utility.

## Current state

The unattended production foundation is in place:

- Daily GitHub Actions processing and GitHub Pages publication.
- Durable GUID-keyed state and eligibility-first selection.
- Incremental historical backfill with limits applied after filtering.
- Failed-only retry and exact-GUID processing.
- Deterministic archive projections and a compact static UI.
- Focused tests for selection, retry, and no-op pipeline behavior.

This is enough foundation. The remaining work is a bounded usability and correction pass, not a platform expansion.

## Final functional pass — maximum approximately five development hours

Work in this order and stop when the budget is exhausted:

1. **Manual review overrides (complete):** preserve extraction output, apply validated files from `data/reviews/`, and use a focused editor plus authenticated workflow for approve/update/add/exclude decisions.
2. **Timestamp playback:** add an in-page remote RSS audio player that seeks after metadata loads and supports a `t` URL parameter.
3. **Readable status and failure detail:** expose attempts, last attempt, retryability, review state, and a small failure taxonomy without leading with raw exceptions.
4. **Single-episode recovery:** retain exact-GUID backend processing and expose a copyable workflow input or command in the episode UI.
5. **No-op publication guard:** ensure an empty scheduled selection does not commit generated churn or deploy an unchanged Pages artifact.
6. **Small readability fixes:** omit empty pick fields, keep evidence/debug content collapsed, and make the card name, recommendation, and timestamp the scanning hierarchy.

Focused tests should cover override update/add/exclude behavior, override survival across rebuilds, invalid override rejection, timestamp parsing/seeking fallbacks, readable rendering, and the deployment-level no-op guard.

## Definition of done

ManaIntel is done when:

- Scheduled processing keeps advancing through eligible historical episodes.
- Failed-only and exact-episode retry are deliberate and bounded.
- Empty runs leave durable/generated files unchanged and do not redeploy.
- Failed episodes are understandable from the site.
- Picks are readable without inspecting extraction internals.
- Manual corrections are separate, validated, and rebuild-safe.
- Timestamp links seek remote podcast audio near the saved moment.
- The runbook explains the normal, backfill, retry, review, and playback workflows.

## Deferred indefinitely

- Additional podcasts, video, written, or community sources.
- A source-agnostic schema migration or cross-source UI.
- Accounts, hosted databases, authenticated browser writes, or complex GitHub auth.
- Analytics, price tracking, scoring, alerts, portfolio features, and ManaSpec integration.
- Large UI redesigns, framework migrations, and broad test refactors.

The earlier source-agnostic design remains useful research, but it is not an active delivery commitment.

## Portfolio sequence after ManaIntel

1. Complete only the bounded ManaIntel final pass.
2. Put ManaSpec in users' hands and continue its adoption roadmap.
3. Shift primary build attention to GalleyFlow.
4. Return to ManaIntel only for production-breaking defects or very small maintenance fixes.
