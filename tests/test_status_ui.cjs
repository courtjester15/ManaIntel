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
  assert.match(action(retry), /Cooldown until/);
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
