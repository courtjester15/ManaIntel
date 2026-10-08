# Episode attempt log

Generated from `attempts/*.json`. Outcomes describe local processing; workflow validation is separate. Run links identify persistence/deployment outcomes. No historical backfill is implied.

- 2026-10-06T22:48:37Z — mtg-fast-finance 535: **complete**; forced rerun; 1 picks; 6 observed model calls; 0 checkpoints reused; archive validation=success; note: Automatic low-pick recovery. [Details](attempts/6a78849d6b6d497d92e2f1e8742fdfb4.json) · [Run](https://github.com/courtjester15/ManaIntel/actions/runs/37542157876)
- 2026-10-07T02:11:27Z — mtg-fast-finance 535: **needs_review**; forced rerun; retained transcript; 1 picks; 2 observed model calls; 0 checkpoints reused; archive validation=success; note: 535 targeted timing repair: reuse retained transcript, retranscribe suspect chunk only, preserve published recommendations. [Details](attempts/86e2c0d3d163418894182f30a883e578.json) · [Run](https://github.com/courtjester15/ManaIntel/actions/runs/37560646583)
- 2026-10-07T02:22:04Z — mtg-fast-finance 535: **complete**; forced rerun; retained transcript; 4 picks; 2 observed model calls; 1 checkpoints reused; archive validation=success; note: 535 bounded recovery: repair flagged clocks before clamping; fix opening and split topic transition; preserve published cards. [Details](attempts/61fc2fe13da5415cad0a6c68ec105fdc.json) · [Run](https://github.com/courtjester15/ManaIntel/actions/runs/37561434906)
- 2026-10-07T02:29:27Z — mtg-fast-finance 535: **needs_review**; forced rerun; retained transcript; 4 picks; 1 observed model calls; 0 checkpoints reused; previous published result retained; archive validation=success; Forced reprocessing omitted published recommendations; the previous recommendations were retained for review.; note: 535 extraction-only cleanup: remove stale clamped duplicates from repaired chunks; retain published recommendations on any removal. [Details](attempts/ab3c29c44b45448db0c2409a57f3ce56.json) · [Run](https://github.com/courtjester15/ManaIntel/actions/runs/37562072188)
- 2026-10-08T02:29:29Z — mtg-fast-finance 520: **failed**; forced rerun; 0 picks; 5 observed model calls; 0 checkpoints reused; archive validation=success; Multiple chunks have suspect timing; manual review required before spending more calls.; note: 520 single bounded recovery after review-aware preflight fix; prior overnight run stopped before Gemini calls. [Details](attempts/92bad154d27d43c993609a6577da10d4.json) · [Run](https://github.com/courtjester15/ManaIntel/actions/runs/37716700802)

## Workflow outcomes

- 2026-10-06T16:47:57Z — run 37498445368/1: preflight=success; pipeline=success; exit=0; validation=success; selected=0; . [Details](runs/37498445368-1.json)
- 2026-10-06T22:54:55Z — run 37542157876/1: preflight=success; pipeline=success; exit=None; validation=success; selected=see queue note; Primary gate=true; queue=selected. [Details](runs/37542157876-1.json)
- 2026-10-06T23:48:29Z — run 37548492901/1: preflight=success; pipeline=success; exit=0; validation=success; selected=0; . [Details](runs/37548492901-1.json)
- 2026-10-07T02:14:18Z — run 37560646583/1: preflight=success; pipeline=success; exit=0; validation=success; selected=1; . [Details](runs/37560646583-1.json)
- 2026-10-07T02:25:35Z — run 37561434906/1: preflight=success; pipeline=success; exit=0; validation=success; selected=1; . [Details](runs/37561434906-1.json)
- 2026-10-07T02:30:28Z — run 37562072188/1: preflight=success; pipeline=success; exit=0; validation=success; selected=1; . [Details](runs/37562072188-1.json)
- 2026-10-07T02:42:14Z — run 37563164804/1: preflight=success; pipeline=success; exit=2; validation=success; selected=see queue note; . [Details](runs/37563164804-1.json)
- 2026-10-07T17:25:43Z — run 37658844910/1: preflight=success; pipeline=success; exit=0; validation=success; selected=0; . [Details](runs/37658844910-1.json)
- 2026-10-07T23:11:05Z — run 37700693549/1: preflight=success; pipeline=skipped; exit=None; validation=skipped; selected=see queue note; Primary gate=true; queue=no eligible episode. [Details](runs/37700693549-1.json)
- 2026-10-08T00:12:06Z — run 37706421861/1: preflight=success; pipeline=success; exit=0; validation=success; selected=0; . [Details](runs/37706421861-1.json)
- 2026-10-08T02:38:17Z — run 37716700802/1: preflight=success; pipeline=success; exit=1; validation=success; selected=1; . [Details](runs/37716700802-1.json)
- 2026-10-08T17:24:19Z — run 37816154462/1: preflight=success; pipeline=success; exit=0; validation=success; selected=0; . [Details](runs/37816154462-1.json)
