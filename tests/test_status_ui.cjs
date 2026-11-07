const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const node = { addEventListener() {}, querySelector() { return node; }, classList: { toggle() {} } };
const context = vm.createContext({
  document: { querySelector: () => node },
  window: { location: { hash: '', href: 'https://example.test/' }, addEventListener() {} },
  fetch: () => new Promise(() => {}), URL, Intl, Date, console,
});
vm.runInContext(fs.readFileSync('web/app.js', 'utf8'), context);
const now = Date.parse('2026-10-31T12:00:00Z');
const retry = { category: 'repair_progress_saved', retryable: true, attempt: 2, max_attempts: 3,
  next_retry_at: '2026-10-31T13:00:00Z' };
function action(error) { context.error = error; context.now = now; return vm.runInContext('recoveryAction(error, now)', context); }

test('exhausted saved repairs cannot promise scheduled recovery even with stale retry flags', () => {
  assert.match(action({ ...retry, attempt: 3 }), /Automatic retry limit reached/);
  assert.doesNotMatch(action({ ...retry, attempt: 3 }), /later scheduled run/);
});
test('cooldown and due eligibility do not imply a queued job', () => {
  assert.match(action(retry), /Eligible after/);
  assert.match(action({ ...retry, next_retry_at: '2026-10-30T13:00:00Z' }), /does not mean a job is queued or running/);
});
test('quarantined and nonretryable failures require intervention', () => {
  for (const change of [{ quarantined: true }, { retryable: false }, { category: 'manual_intervention' }]) {
    assert.match(action({ ...retry, ...change }), /Manual intervention required/);
  }
});
test('unknown retry timing never invents eligibility', () => {
  for (const value of [null, '', 'invalid']) assert.match(action({ ...retry, next_retry_at: value }), /Retry timing is not recorded/);
  assert.equal(action(null), '');
});

test('provider refusal and local capacity budget have distinct explanations', () => {
  context.error = { category: 'capacity_deferred', message: 'Shared capacity stop: provider limit observed; no further requests permitted.' };
  assert.match(vm.runInContext('failureReason(error)', context), /provider refused/);
  context.error.message = 'Shared capacity stop: configured request budget reached.';
  assert.match(vm.runInContext('failureReason(error)', context), /configured request budget/);
  context.error = { category: 'transient_provider', message: '503 UNAVAILABLE' };
  assert.match(vm.runInContext('failureReason(error)', context), /temporarily unavailable/);
  assert.equal(vm.runInContext('deferredStatus(error)', context), 'temporary provider outage');
});

test('retry allowance and eligibility remain explicit for both incident episodes', () => {
  assert.match(action({ ...retry, attempt: 1 }), /2 automatic attempts remain/);
  assert.match(action(retry), /1 automatic attempt remains/);
  assert.match(action({ ...retry, next_retry_at: '2026-10-30T13:00:00Z' }), /Eligible since/);
  assert.doesNotMatch(action({ ...retry, attempt: 3 }), /attempt remains/);
  assert.doesNotMatch(action({ ...retry, attempt: undefined }), /automatic attempts remain/);
});
test('status view exposes the failed attempt, reason, next action and details safely', () => {
  context.episode = { title: '<img onerror=bad>', guid: 'test"guid', episode_number: 484,
    processing_status: 'failed', pick_count: 0, processed_at: '2026-10-30T23:46:10Z',
    published_at: '2025-07-11T23:21:48Z', error: { ...retry, attempt: 3, retryable: false } };
  const html = vm.runInContext('state.index = {episodes: [episode]}; renderStatus()', context);
  assert.match(html, /last attempt/);
  assert.match(html, /Transcript repair progress was saved/);
  assert.match(html, /Automatic retry limit reached/);
  assert.match(html, /View recovery details/);
  assert.match(html, /test&quot;guid/);
  assert.doesNotMatch(html, /<img/);
});
