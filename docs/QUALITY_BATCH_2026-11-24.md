# November 24 source and extraction quality batch

Release 0.5.34. This is a bounded machine source check, not human approval or a statistical accuracy claim.

## What the comparisons established

[Source comparison](https://github.com/courtjester15/ManaIntel/actions/runs/45541555316): four fixed audio clips, independent faster-whisper tiny.en ASR plus separate Gemini transcription. FF539 1360–1585, FF504 1350–1800, BB678 1350–1800, FF507 720–945 seconds. All four Lite calls succeeded with no recorded clock adjustments or detected compressed clocks. The alternative gemini-3.6-flash timed out on its first audio clip after about 180 seconds; its audio test stopped. Five actual Gemini requests. An earlier harness run failed in the local audio decoder before any Gemini request; the corrected run supplies decoded PCM directly to ASR.

[Extraction comparison](https://github.com/courtjester15/ManaIntel/actions/runs/45542633716): retained identical source transcripts for FF539, FF537, BB667 and FF538; ten actual requests, five per model. FF539 has baseline and candidate policy; the other three test the candidate policy. All requests returned JSON. Lite took 3–5 seconds per response; alternative Flash took 28–52 seconds. Lite omitted the final FF539 pick with both policies. Alternative Flash included it with both, but the candidate also added an uncertified sealed-product recommendation. Other cases still had identity, printing, price or listening-window discrepancies against scoped expectations. Raw responses also differ from publication normalization, so this is not an end-to-end accuracy ranking. Neither the prompt rewrite nor a broad model switch is justified by this sample. Both remain unchanged in production.

The source and extraction workflows serialize with production writers, reserve actual provider calls in the existing durable ledger, retain only compact metadata in Git and keep transcript evidence in existing private 14-day artifacts. Source cap eight; extraction cap ten; no hidden schema/split calls outside these caps. No queue-wide reprocessing or new spending.

## Product repairs

* FF539: add the omitted SOLDIER Military Program positive recommendation, including the spoken surge-foil version and $1-entry/$5-resale thesis, with cohost disagreement preserved. Independent machine ASR and the separate Lite clip agree. Scryfall exact lookup establishes card identity only, not the thesis or exact printing. Remove unsupported full host names from all four existing picks; preserve the existing unresolved Dawnsire name warning.
* FF504: repair Narset’s Reversal and Avatar Kyoshi listening starts to 1682 and 1768 seconds.
* BB678: repair Witty Roastmaster and Bringer of the Last Gift starts to 1528 and 1762 seconds. Uninspected later picks, including an existing feed-duration discrepancy, remain untouched.
* FF507: repair Sol Ring’s listening start from 754 to 789 seconds. Other picks are not certified.

Unverified end clocks are cleared, rather than guessed. Durable `correct_without_approval` overrides preserve original extraction JSON/metadata/Markdown and all existing pick IDs. The limited-correction path now supports unattributed additions, clearing unsupported speakers and repairing listening times; it cannot assign guessed names, approve the episode or replace a human approval. Changed/new clocks must validate; unrelated old clock defects cannot prevent a limited repair or become implicitly approved. Whole-episode approval still validates every clock.

Effective archive: 149 episodes, 562 picks, 75 complete, 69 needs_review, five failed. Three historical complete labels become needs_review through explicit limited corrections. This is an honest consequence of finding defects, not a processing regression. No historical queue is automatically cleared.

## Future-processing safeguards

A deterministic handoff inventory flags explicit FF first/other/final-pick handoffs with no nearby extracted pick, including final handoffs beyond a section cap when no independent ending exists. It catches the new Lite FF539 omission despite four plausible picks. It is a conservative omission alarm, not a guarantee: wrong cards at plausible times, weak handoffs and BB coverage still require source checking.

Per-pick speaker names require a named source label on recommendation speech or an exact named handoff. Introduction participant lists, questioners and numbered voices do not establish attribution. Unsupported names become unknown, with the proposed attribution retained in a diagnostic. The checks run again after verification/alignment so retained metadata cannot restore unsupported names.

Only either exact known missing-ending warning becomes nonblocking when the section has a trusted explicit/recommendation-language start. Mixed warnings, untrusted outline starts, missing picks, bad clocks, identity and printing issues remain blocking. Diagnostics remain recorded and visible. Historical states are not mass-reclassified. Extraction policy identity advances to v5; transcription identity stays unchanged so source caches remain reusable.

## Validation and next action

The archive validates. The existing 45 scoped assertions and six new final-pick assertions pass; these assertions cover explicit fields, not every source claim. Regression coverage includes limited corrections, identity preservation, source attribution, missing final handoffs and actual live status selection for diagnostic-only versus mixed warnings. All 303 Python tests pass across the full suite’s 301 non-Git tests and a separate successful two-test Git persistence run; the desktop full-run environment omits GIT_CONFIG_VALUE_0 for child Git processes. Ten Node review journeys pass. A retained-publication path also now preserves candidate/source warnings instead of replacing them with only its generic retention warning. Local three-catalog publication fidelity passes with zero findings.

Next: monitor ordinary releases/recoveries under the existing bounded provider renewal policy. Investigate coverage alarms using a focused source window, rather than unchanged retries. Expand independent checks before choosing a separate extraction model or changing the 900-second transcription default. Four successful short clips do not establish full-episode reliability or justify multiplying routine call demand. R2 remains open pending broader independent evidence and a sustained healthy operating window.
