const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function harness() {
  const nodes = new Map();
  const editors = [];
  function node(selector) {
    if (!nodes.has(selector)) nodes.set(selector, { value: '', hidden: false, innerHTML: '',
      textContent: '', addEventListener() {}, scrollIntoView() {} });
    return nodes.get(selector);
  }
  const c = vm.createContext({
    document: { querySelector: node, querySelectorAll: (selector) => selector === ".review-pick[data-new='false']" ? editors : [] },
    window: { location: { search: '?episode=fixture', href: 'https://example.test/review.html?episode=fixture' } },
    fetch: () => new Promise(() => {}), URL, URLSearchParams, console,
  });
  vm.runInContext(fs.readFileSync('web/review.js', 'utf8'), c);
  c.fixture = { episode: { guid: 'fixture', source_id: 'mtg-fast-finance', hosts: ['Show Host'], duration_seconds: 3600 },
    processing: { processed_at: '2026-11-14T00:00:00Z', status: 'needs_review' },
    recommendations: [{ id: 'pick-fixture', card: 'Example Card', printing: 'Regular', foil: false, hosts: [],
      recommendation: 'buy', start_seconds: 100, end_seconds: 130, evidence_excerpt: 'Source evidence',
      entry_target: { raw: 'historical five', currency: 'USD', minimum: 5, maximum: 5 },
      mentioned_price: null, exit_target: null, hold: null, reasoning: ['Low supply'], caveats: [] }] };
  const run = (code) => vm.runInContext(code, c);
  run('originalSummary = JSON.parse(JSON.stringify(fixture)); sourceSummary = JSON.parse(JSON.stringify(fixture));');
  return { c, run, node, editors };
}

test('review editor and added picks never fill unknown pick speakers from show hosts', () => {
  const h = harness();
  const html = h.run('pickEditor(sourceSummary.recommendations[0], 0)');
  assert.match(html, /name="hosts" value=""/);
  assert.doesNotMatch(html, /value="Show Host"/);
  assert.match(html, /name="entry_target_raw"/);
  assert.match(html, /name="end_timestamp"/);
  assert.match(html, /name="reasoning"/);
  assert.match(html, /name="caveats"/);
});

test('target fields preserve source text and unknown bounds without inferring a price', () => {
  const h = harness();
  h.c.fields = { entry_target_raw: 'under five', entry_target_currency: '', entry_target_minimum: '', entry_target_maximum: '5' };
  const result = JSON.parse(h.run('JSON.stringify(readTarget(name => fields[name], "entry_target"))'));
  assert.deepEqual(result, { raw: 'under five', currency: null, minimum: null, maximum: 5 });
  for (const changes of [{ entry_target_raw: '' }, { entry_target_minimum: '6' },
    { entry_target_maximum: '-1' }, { entry_target_maximum: 'Infinity' }, { entry_target_maximum: '$5' }]) {
    h.c.fields = { entry_target_raw: 'under five', entry_target_currency: '', entry_target_minimum: '', entry_target_maximum: '5', ...changes };
    assert.throws(() => h.run('readTarget(name => fields[name], "entry_target")'));
  }
});

test('target object key order cannot manufacture an edit and unknown speakers remain valid', () => {
  const h = harness();
  assert.equal(h.run('sameValue({raw:"five",minimum:null,maximum:5,currency:"USD"}, {currency:"USD",maximum:5,minimum:null,raw:"five"})'), true);
  assert.equal(h.run('Object.keys(changedFields(sourceSummary.recommendations[0], editableValues(sourceSummary.recommendations[0]))).length'), 0);
  h.run('validatePickValues(editableValues(sourceSummary.recommendations[0]))');
  assert.throws(() => h.run('validatePickValues({...editableValues(sourceSummary.recommendations[0]), end_seconds: 99})'), /precede/);
  assert.throws(() => h.run('validatePickValues({...editableValues(sourceSummary.recommendations[0]), end_seconds: 3601})'), /duration/);
});

test('limited correction outcome keeps its narrow scope and requires an evidence note', () => {
  const h = harness();
  h.run('validateOutcome("correct_without_approval", [{action:"update",changes:{printing:"full art",entry_target:null}}], "Checked printing")');
  h.run('validateOutcome("correct_without_approval", [{action:"update",changes:{hosts:[]}}, {action:"add",pick:{card:"Recovered",hosts:[]}}], "Checked source; attribution unknown")');
  for (const operation of [{ action: 'exclude' }, { action: 'add' },
    { action: 'update', changes: { hosts: ['Guessed'] } },
    { action: 'update', changes: { entry_target: { raw: 'five' } } }]) {
    h.c.operation = operation;
    assert.throws(() => h.run('validateOutcome("correct_without_approval", [operation], "Checked")'), /Limited corrections/);
  }
  assert.throws(() => h.run('validateOutcome("correct_without_approval", [], "")'), /evidence note/);
  assert.throws(() => h.run('validateOutcome("approve-later", [], "")'), /Choose a review outcome/);
});

test('Keep preserves a saved correction in the cumulative payload and binds its revision', () => {
  const h = harness();
  h.run('sourceSummary.recommendations[0].printing = "Full art"; sourceSummary.recommendations[0].entry_target = null; expectedReviewRevision = "a".repeat(64)');
  h.editors.push({ dataset: { originalId: 'pick-fixture' }, querySelector: () => ({ value: 'keep' }) });
  h.node('[name="decision"]').value = 'approve';
  h.run('preparePayload()');
  const payload = JSON.parse(h.node('#review-payload').value);
  assert.deepEqual(payload.operations, [{ action: 'update', pick_id: 'pick-fixture', changes: { printing: 'Full art', entry_target: null } }]);
  assert.equal(payload.expected_review_revision, 'a'.repeat(64));
  assert.equal(payload.expected.processed_at, h.c.fixture.processing.processed_at);
  assert.equal(h.node('#review-output').hidden, false);
  assert.match(h.node('#review-preview').innerHTML, /Previously saved corrections/);
  h.run('invalidatePayload()');
  assert.equal(h.node('#review-output').hidden, true);
  assert.equal(h.node('#review-payload').value, '');
  assert.equal(h.node('#review-preview').innerHTML, '');
});

test('preview escapes source and edited text while preserving false finish and unknown attribution', () => {
  const h = harness();
  h.run('sourceSummary.recommendations[0].hosts = ["Known speaker"]; sourceSummary.recommendations[0].foil = true');
  h.c.payload = { decision: 'approve', note: '<script>bad()</script>', operations: [
    { action: 'update', pick_id: 'pick-fixture', changes: { card: '<img onerror="bad()">', hosts: [], foil: false } },
  ] };
  const html = h.run('renderChangePreview(payload)');
  assert.match(html, /&lt;img/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /Unknown speaker/);
  assert.match(html, /Nonfoil/);
  assert.doesNotMatch(html, /<script>|<img/);
});

test('preview shows reverting an existing correction even when no cumulative operation remains', () => {
  const h = harness();
  h.run('sourceSummary.recommendations[0].printing = "Full art"');
  h.c.payload = { decision: 'approve', note: '', operations: [] };
  const html = h.run('renderChangePreview(payload)');
  assert.match(html, /Full art/);
  assert.match(html, /Regular/);
  assert.doesNotMatch(html, /No pick field changes/);
});

test('failed preparation clears a previously copied payload and cannot imply approval', () => {
  const h = harness();
  h.node('#review-payload').value = 'old-payload';
  h.run('preparePayload()');
  assert.equal(h.node('#review-output').hidden, true);
  assert.equal(h.node('#review-payload').value, '');
  assert.equal(h.node('#review-error').hidden, false);
  assert.match(h.node('#review-error').textContent, /Choose a review outcome/);
});

test('complete machine output can be reviewed even when optional card lookup is offline', async () => {
  const h = harness();
  h.c.fixture.processing.status = 'complete';
  h.c.index = { metadata: { review_workflow_url: 'https://example.test/actions' },
    episodes: [{ guid: 'fixture', processing_status: 'complete', human_reviewed: false, review_revision: null }] };
  h.c.fetch = async (url) => {
    if (url.startsWith('archive/resolutions')) throw new Error('Optional lookup offline');
    return { ok: true, json: async () => url.startsWith('archive/index') ? h.c.index : h.c.fixture };
  };
  h.run('renderReview = () => { globalThis.rendered = true; }');
  await h.run('loadReview()');
  assert.equal(h.c.rendered, true);
});

test('saved correction mismatch and already human-reviewed output cannot open an editable draft', async () => {
  for (const human_reviewed of [true, false]) {
    const h = harness();
    h.c.index = { metadata: { review_workflow_url: 'https://example.test/actions' }, episodes: [
      { guid: 'fixture', processing_status: 'needs_review', human_reviewed, review_revision: 'a'.repeat(64) },
    ] };
    h.c.fetch = async (url) => ({ ok: true, json: async () => url.startsWith('archive/index') ? h.c.index : h.c.fixture });
    h.run('renderReview = () => { globalThis.rendered = true; }');
    await h.run('loadReview()');
    assert.notEqual(h.c.rendered, true);
    assert.match(h.node('#review-app').innerHTML, human_reviewed ? /already been human reviewed/ : /Saved corrections changed/);
  }
});
