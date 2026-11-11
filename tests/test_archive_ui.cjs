const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function harness(hash = '') {
  const nodes = new Map();
  function node(selector) {
    if (!nodes.has(selector)) nodes.set(selector, {
      innerHTML: '', textContent: '', dataset: {}, listeners: {}, attrs: {},
      addEventListener(type, callback) { this.listeners[type] = callback; },
      querySelector() { return node('heading'); }, querySelectorAll() { return []; },
      classList: { toggle() {} }, setAttribute(k, v) { this.attrs[k] = v; },
      removeAttribute(k) { delete this.attrs[k]; }, insertAdjacentHTML() {},
      focus() { this.focused = true; },
      showModal() { this.open = true; }, close() { this.open = false; },
    });
    return nodes.get(selector);
  }
  const c = vm.createContext({
    document: { querySelector: node, querySelectorAll: () => [] },
    window: { location: { hash, href: 'https://example.test/' }, addEventListener() {} },
    fetch: () => new Promise(() => {}), URL, URLSearchParams, Intl, Date, console,
  });
  vm.runInContext(fs.readFileSync('web/table.js', 'utf8'), c);
  vm.runInContext(fs.readFileSync('web/app.js', 'utf8'), c);
  return { c, node, run: (code) => vm.runInContext(code, c) };
}
function pick(id, oracle, extra = {}) {
  return { id, card: "Akroma's Will", printing: 'showcase', recommendation: 'buy',
    reasoning: ['Useful in the deck.'], hosts: [], review_status: 'approved', human_reviewed: false,
    timestamp: '00:30:00', start_seconds: 1800,
    card_resolution: { status: 'verified', oracle_id: oracle },
    episode: { guid: id + '-episode', source_name: 'Brainstorm Brewery', source_id: 'brainstorm-brewery',
      episode_number: 725, published_at: '2026-11-06T06:00:00Z' }, ...extra };
}

test('history uses verified oracle identity across shows and preserves variants and multiplicity', () => {
  const h = harness();
  h.c.picks = [pick('new', 'card-a'), pick('variant', 'card-a', { printing: 'foil version' }),
    pick('old', 'card-a', { card: 'Raw spelling', episode: {guid: 'old', source_name: 'MTG Fast Finance', published_at: '2025-01-01'} }),
    pick('suggested', 'card-a', {card_resolution: {status: 'suggested', oracle_id: 'card-a'}}), pick('other', 'card-b')];
  const result = h.run('state.cards = picks; recordedHistory(picks[0]).map(p => p.id).join(",")');
  assert.equal(result, 'new,variant,old');
  assert.equal(h.run('recordedHistory(picks[3]).length'), 1);
  h.c.picks[0].card_resolution.oracle_id = null;
  assert.equal(h.run('recordedHistory(picks[0]).length'), 1);
});

test('history separates mentioned price from target, escapes source text and states coverage', () => {
  const h = harness();
  h.c.p = pick('selected', 'a', { mentioned_price: '$150', entry_target: { raw: 'under $100' },
    reasoning: ['<script>bad()</script>'], printing: 'different <printing>' });
  h.run('state.cards = [p]; state.index = { episodes: [] }');
  const html = h.run('renderCardHistory(p)');
  assert.match(html, /Mentioned price<\/dt><dd>\$150/);
  assert.match(html, /Entry target<\/dt><dd>under \$100/);
  assert.match(html, /incomplete coverage/);
  assert.match(html, /machine checked/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(h.run('p.card_resolution.status="suggested"; renderCardHistory(p)'), /Only this recommendation/);
  assert.match(h.run('p.human_reviewed=true; renderCardHistory(p)'), /human reviewed/);
  assert.equal(h.run('episodeReviewLabel({review_state:"approved",human_reviewed:true})'), 'human reviewed');
});

test('dashboard metrics are destinations and source filters reset when following navigation', () => {
  const h = harness('#episodes?status=failed');
  h.run('state.index={episodes:[]}; state.episodeSource="brainstorm-brewery"; setRoute()');
  assert.equal(h.run('state.status'), 'failed');
  assert.equal(h.run('state.episodeSource'), 'all');
  assert.match(h.run('metric("Unfinished", 2, "view recovery", "#episodes?status=failed")'), /href="#episodes\?status=failed"/);
  h.run('window.location.hash="#picks?q=Akroma%27s&source=brainstorm-brewery"; setRoute()');
  assert.equal(h.run('state.query'), "Akroma's");
  assert.equal(h.run('state.pickSource'), 'brainstorm-brewery');
});

test('long error messages have a readable ellipsis and stay escaped exactly once', () => {
  const h = harness();
  h.c.error = { message: "can't <load> " + 'a'.repeat(240) };
  const html = h.run('failureReason(error)');
  assert.ok(html.endsWith('…'));
  assert.match(html, /can&#039;t &lt;load&gt;/);
  assert.doesNotMatch(html, /â|&amp;#039/);
});

test('a direct history link opens the selected pick and back control has a matching symbol', () => {
  const h = harness('#picks?pick=selected');
  h.c.p = pick('selected', 'a');
  h.run('state.cards=[p]; state.index={episodes:[]}; setRoute()');
  assert.equal(h.run('dialogState.pickId'), 'selected');
  assert.match(h.node('#dialog-content').innerHTML, /Pick history/);
  h.run('setDialogCloseAction(true)');
  assert.equal(h.node('.dialog-close').textContent, '←');
  assert.equal(h.node('.dialog-close').attrs['aria-label'], 'Back to episode picks');
});

test('clipboard denial exposes and selects the exact copyable value', async () => {
  const c = vm.createContext({ window: {}, navigator: { clipboard: { writeText: async () => { throw Error('denied'); } } } });
  vm.runInContext(fs.readFileSync('web/ui.js', 'utf8'), c);
  const button = {};
  const fallback = { hidden: true, focus() { this.focused = true; }, select() { this.selected = true; } };
  await c.window.ManaUI.copyText(button, 'exact-guid', 'Copied', fallback);
  assert.equal(fallback.value, 'exact-guid');
  assert.equal(fallback.hidden, false);
  assert.ok(fallback.focused && fallback.selected);
  assert.equal(button.textContent, 'Select and copy below');
});

test('missing URLs never become relative null or undefined destinations', () => {
  const h = harness();
  for (const value of [null, undefined, '', '   ', 'javascript:bad()']) {
    h.c.value = value;
    assert.equal(h.run('safeUrl(value)'), '#');
    assert.equal(h.run('rawSafeUrl(value)'), '#');
    assert.equal(h.run('tableSafeUrl(value)'), '#');
  }
});

test('legacy missing source metadata stays unknown instead of inventing show attribution', () => {
  const h = harness();
  assert.equal(h.run('sourceName({episode:{}})'), 'Source not recorded');
  assert.equal(h.run('sourceAbbreviation({episode:{}})'), 'Unknown');
});

test('unavailable audio disables dead buttons and preserves a real source fallback', () => {
  const c = vm.createContext({window:{location:{href:'https://example.test/'}},document:{},URL});
  vm.runInContext(fs.readFileSync('web/audio-player.js', 'utf8'),c);
  const container = {};
  const attrs={};
  const button={tagName:'BUTTON', setAttribute(k,v){attrs[k]=v},removeAttribute(){}};
  const link={tagName:'A'};
  let click;
  c.window.AudioPlayback.mount({container,audioUrl:null,sourceUrl:'https://podcast.test/episode'});
  c.window.AudioPlayback.bind({querySelectorAll(){return [button,link]},addEventListener(type,fn){click=fn}});
  assert.equal(button.disabled,true);
  assert.equal(attrs['aria-disabled'],'true');
  assert.equal(link.href,'https://podcast.test/episode');
  let prevented=false;
  click({target:{closest(){return {dataset:{listenSeconds:'10'}}}},preventDefault(){prevented=true}});
  assert.equal(prevented,false);
});
