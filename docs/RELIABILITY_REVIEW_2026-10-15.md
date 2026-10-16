# BB 666 and BB 667 investigation — October 15, 2026

## Confirmed production evidence

BB 666 failed twice today on version 0.5.6, runs 38756313025 and 38821207857. The first attempt made two primary 503 calls, opened the availability circuit, and transcribed all three original chunks through Flash Lite. Chunk 2 then failed timing checks. The targeted replacement's first half succeeded and was cached; the second half returned valid JSON but failed the timing/coverage check. The evening retry reused the retained transcript and the successful repair half, then failed the remaining half again. Neither attempt reached recommendation extraction. Valid JSON/STOP in provider telemetry was not a usable transcription result.

The original retained BB 666 transcript contains 219 zero-length segments collapsed at the 1,800-second boundary. These are evidence of damage to chunk 2's timestamps. Rejected replacement payloads were not retained, so the old evidence cannot establish the exact representation error inside that replacement half. This is an observability defect; the precise replacement failure must not be inferred from the original transcript.

BB 667 has no new attempt after October 14. Its published failure is the earlier manual-review gate, not a fresh failure of version 0.5.6. Its retained transcript has 34 collapsed segments at 900 seconds, 63 at 2,700 seconds, and 47 at 3,600 seconds. More seriously, chunk 2 contains only the 34 collapsed tail segments from chunk 1 and no usable timed speech. The detector grouped those boundary segments into chunk 2 and incorrectly treated them as coverage. The actual inspected repair set is chunks 1, 2, 3 and 4, not the previous set of 1, 3 and 4.

The previous deployment fixed repeated primary probes, multi-chunk truncation recovery and deterministic retry gates. It did not make the models produce reliable timestamps. The BB 666 circuit and checkpoint reuse worked as intended while the timing repair itself still failed. BB 667's guarded failure remained unresolved.

## Version 0.5.7 changes

- Exclude zero-length boundary tails from next-chunk coverage and recheck coverage after all repairs.
- Repair suspect audio in four shorter clips (normally 225 seconds), with integer-second schema fields and explicit per-clip clock reset instructions, rather than retrying the same 450-second shape that failed twice. This is a bounded recovery strategy requiring live validation, not a proven provider fix.
- Retain successful repair quarters with a separate fingerprint; preserve original transcription checkpoints. Keep the existing maximum of eight rescue calls per invocation.
- Record sanitized timing rejection metrics and retain rejected repair payloads in private transcript storage/artifacts, never in the public archive.
- Permit a manually selected four-chunk repair budget for inspected cases such as BB 667; the automatic default remains two.

## Follow-up with retained rejection evidence

The single inspected 0.5.7 BB 666 attempt (run 38840331812) failed on its first 225-second repair clip. The newly retained response proves the timing was invalid: 70 segments, 30 zero-length timestamps, and a segment running backward from 225 to 23. The sequence mixes second-like and clock-like values (65, 110, 123, then 225 and 23); valid JSON and numeric bounds did not make the time representation coherent. This evidence does not justify guessing a conversion for those numbers.

Version 0.5.8 therefore requests explicit MM:SS.mmm string timestamps for all new Gemini transcription calls, including split rescue and targeted repair, and parses them deterministically into the existing numeric-second archive contract. New transcription fingerprints change with the prompt; retained legacy transcripts remain available for targeted repair. Timing bounds, missing coverage, collapsed tails and large backward jumps are still rejected. This replaces the ambiguous numeric protocol rather than relaxing validation.

The source fix and each live episode recovery are verified separately. See the attempt journal for actual outcomes; deployment success alone is not episode recovery.

The 0.5.8 live validation (38841020667) successfully generated and cached two replacement quarters, then exposed an overly strict parser: an otherwise correctly structured clock `01:57.73000000000002` exceeded the three-fractional-digit regex. Version 0.5.9 accepts arbitrary fractional-second precision while retaining explicit MM:SS structure, range, coverage and backward-jump checks. The cached successful quarters remain compatible and reusable.

## Sources

- [BB 666 initial attempt](https://github.com/courtjester15/ManaIntel/blob/master/state/attempts/26c7749a34fe4c49b68980604ddff5b2.json)
- [BB 666 retry](https://github.com/courtjester15/ManaIntel/blob/master/state/attempts/1e2c6488b1b64ffc944333708ead4163.json)
- [Attempt journal](https://github.com/courtjester15/ManaIntel/blob/master/state/episode-attempts.md)
- Private retained transcript artifacts from BB 666 run 38756313025 and BB 667 run 38485922136; inspected locally without publishing transcript text.
