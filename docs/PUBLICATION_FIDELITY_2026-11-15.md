# Publication fidelity and the encoding false alarm

Release 0.5.28 strengthens source-to-publication checks without changing published
recommendations, model/prompt defaults, supported sources or review decisions.

## Diagnosis: production punctuation was intact

The November 14 closeout incorrectly reported 29 projected records with damaged
punctuation. The comparison used `Path.read_text()` without an encoding in a
Windows scratch script. This Python environment defaults to CP1252; the archive
JSON is UTF-8. The same comparison used binary JSON decoding for the downloaded
Pages artifact, so it compared correctly decoded publication text with mojibake
in the local reference. CP1252 console bytes decoded as UTF-8 then made the good
text appear to contain replacement characters in tool output.

Reproduced all three facts against the retained artifact:

- Binary JSON and explicit UTF-8 source reads match the artifact exactly.
- The locale-default read differs; the artifact contains zero U+FFFD code points.
- The new public-site verifier passes all three catalog documents for the
  existing 0.5.27 deployment: 142 episodes and 546 picks, zero findings.

The artifact card-payload SHA-256 remains
`abafdb59dca82acfa5eb04130da5f0a32ccade84bc7a692483b2f5fb9c847aef`.
No text repair is justified. Retained the original reports/artifacts and a compact
corrected diagnosis; do not treat the earlier 29-record comparison as evidence of
publication corruption.

## Delivered checks

Previously, archive validation compared pick ID sets and counts, but could accept
changed evidence, price targets, hosts, review flags, duplicated flattened rows,
stale timestamps, or an episode removed from every catalog together. Validation
now reconstructs the expected catalogs from all retained episode metadata,
summaries, durable reviews and cached card resolutions, then compares field values.
This includes dashboard recent/latest records, episode context, counts, ordering
and resolution metadata. Both failed episodes and confirmed empty dispositions
remain represented. Production mode still excludes synthetic fixtures.

The projection is read-only: no directory creation, output rewriting, effective
file deletion, model requests or card lookups. A bad effective file remains bad
and fails validation. The guard does not fix records to make its own check pass.
Preflight accepts an older pipeline version while enforcing current field
fidelity, so routine releases do not require rewriting processing history.

Both Pages upload paths now verify their staged catalogs after copying `_site`
and before upload. A mismatch fails the job. Nightly cleanup uses the main
deploy-only workflow and therefore passes through the same guard.

```powershell
python -m ffw verify-publication --site-dir _site
python -m ffw verify-publication --url https://courtjester15.github.io/ManaIntel/ --output-json .tmp/publication-check.json
```

The command always checks the production projection. It reads exactly three
catalog JSON documents, with explicit UTF-8 decoding, a 16 MiB limit per document
and a 20-second timeout per remote request. It sends no credentials and makes no
provider calls. It does not retry. Output is ASCII-safe JSON with at most 30
field-path findings and no source values. Exit 0 means the catalogs match, 1 means
mismatch/unreadable publication, and 2 means invalid verification input.

Use the checkout corresponding to the intended deployment. The standalone
publication check verifies the pipeline version and all metadata except the
build-time value; the build time must still be timezone-aware and parseable.
It does not silently normalize punctuation or ignore source/evidence fields.

## Evidence and limits

Regression mutations cover changed fields with identical IDs/counts, duplicate
rows, coordinated catalog omissions, dashboard drift, cached matches, durable
reviews, genuine U+FFFD corruption, UTF-8/CP1252 differences, stale timestamps,
read-only behavior, invalid JSON and CLI exit status. Network tests use a fake
opener; workflow tests verify that the gate precedes both Pages uploads.

These checks establish catalog fidelity to retained records. They cannot establish
that the source transcript is accurate or the retained extraction is complete.
The three-document check does not certify visual layout, playback or all linked
assets. R2's independent FF538 source check and the 0.6 reliability gate remain
open. No episode retry, model call or actual review approval is part of this pass.

Local final verification: all 274 Python tests pass, including the 26 Node UI
checks. The existing production archive validates, an isolated 0.5.28 staged
projection verifies, and the 0.5.27 public-site baseline verified before the
version bump. All checks are read-only except isolated test fixtures/reports.


## Production closeout

Implementation `6139d43`; [release 43684808924](https://github.com/courtjester15/ManaIntel/actions/runs/43684808924)
passed all 274 production tests, archive validation, the new staged fidelity
check, publish and Pages deployment. The new verifier checked the served 0.5.28
release: three catalogs, 142 episodes, 546 picks, zero findings. It verifies the
release metadata as well as Unicode text, projected fields and resolution state.
All 293 original episode/metadata/review files, checked-in catalogs and durable
state are unchanged. No inference calls, episode retries or review approvals.

Scratch preview/apply found 0 MiB age-eligible. The new copied staged catalogs
were removed after verification; diagnosis, before/staged/served reports and test
logs are pinned under `.tmp/publication-fidelity/`. The earlier artifacts remain
pinned under `.tmp/review-workbench/`, with the false-alarm interpretation corrected
in the documentation. Next independent product task: review-queue prioritization;
R2 still needs an independent source check, and 0.6 is not declared complete.
