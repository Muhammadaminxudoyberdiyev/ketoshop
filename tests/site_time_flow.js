// Runs the Mini App's «saytda faol vaqt» block (webapp/index.html, from
// "// ===== SAYTDA FAOL VAQT UCHUN KETO" to "// ===== AKSIYA / BONUS =====")
// against a fake DOM, clock and api(), for one scenario in argv[2]:
//   beats     — which minutes are reported, with what count and gaps
//   presence  — the «Davom etyapsizmi?» card ignores early and scripted taps
//   durations — the time texts
// Prints what happened as JSON. Driven by tests/test_site_time.py.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'webapp', 'index.html'), 'utf8');
const start = html.indexOf('// ===== SAYTDA FAOL VAQT UCHUN KETO');
const end = html.indexOf('// ===== AKSIYA / BONUS =====', start);
if (start < 0 || end < 0) throw new Error('site time block not found');
const scenario = process.argv[2] || 'beats';

let now = 5000;                               // ms, the fake performance.now()
const calls = [];
const body = { children: [], appendChild(e) { this.children.push(e); }, append(...e) { this.children.push(...e); } };
const docListeners = {};
const winListeners = {};
const intervals = [];
const el = tag => {
  const listeners = {};
  const e = {
    tagName: tag, style: {}, dataset: {}, className: '', innerHTML: '', textContent: '', _stops: [],
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    setAttribute() {}, getAttribute: () => null, focus() {},
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    fire(type, ev) { (listeners[type] || []).forEach(fn => fn(ev)); },
    remove() { const i = body.children.indexOf(e); if (i >= 0) body.children.splice(i, 1); },
    querySelector: () => null, querySelectorAll: () => [],
  };
  return e;
};
let responses = [];
const ctx = {
  lang: 'uz',
  document: {
    visibilityState: 'visible',
    body,
    createElement: el,
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener(type, fn) { (docListeners[type] = docListeners[type] || []).push(fn); },
    removeEventListener() {},
  },
  window: {
    innerWidth: 390, innerHeight: 760,
    addEventListener(type, fn) { (winListeners[type] = winListeners[type] || []).push(fn); },
    matchMedia: () => ({ matches: false }),
  },
  performance: { now: () => now },
  setInterval: (fn, ms) => { intervals.push(fn); return intervals.length; },
  clearInterval() {},
  setTimeout: () => 0,
  clearTimeout() {},
  requestAnimationFrame: () => 0,
  localStorage: { getItem: () => null, setItem() {} },
  api: (url, opts) => {
    const sent = opts && opts.body ? JSON.parse(opts.body) : null;
    calls.push([url, sent, now / 1000]);
    const r = responses.shift() || { ok: true, enabled: true, active: 0, awards: [], next: null, check: null };
    return Promise.resolve(r);
  },
  escapeHtml: s => String(s),
  formatPrice: n => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '),
  launchFireworks: () => () => {}, hmsLeft: () => '0:00:00', showWelcomeParty() {},
  tg: {}, t: {}, activePage: 'catalog', gameState: null,
  Date, JSON, Math, Promise, String, Number, Array, Object,
};
ctx.gx = (uz, ru) => (ctx.lang === 'ru' ? ru : uz);
vm.createContext(ctx);
vm.runInContext(html.slice(start, end), ctx);
// Watch the celebration's queue without drawing it.
const partyAdds = [];
let helloDone = 0;
ctx.__seen = { add: a => partyAdds.push(a), hello: () => { helloDone++; } };
vm.runInContext('KetoParty.add = (awards) => __seen.add(awards); KetoParty.helloDone = () => __seen.hello();', ctx);

const settle = async () => { for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r)); };
const fire = (type, isTrusted) => (docListeners[type] || []).forEach(fn => fn({ isTrusted, target: {} }));
const tick = () => { now += 1000; intervals.forEach(fn => fn()); };
const INFO = { ladder: [{ seconds: 0, amount: 5 }, { seconds: 60, amount: 10 }], levels: [], every_hour_after: 500, daily_cap: 28800 };

(async () => {
  const out = {};
  if (scenario === 'beats') {
    responses = [
      { ok: true, enabled: true, active: 0, credited: 0, awards: [{ seconds: 0, amount: 5 }], balance: 5,
        next: { seconds: 60, amount: 10, left: 60 }, check: null, info: INFO },
      { ok: true, enabled: true, active: 60, credited: 60, awards: [{ seconds: 60, amount: 10 }], balance: 15,
        next: { seconds: 600, amount: 50, left: 540 }, check: null, info: INFO },
      { ok: true, enabled: true, active: 120, credited: 60, awards: [], balance: 15,
        next: { seconds: 600, amount: 50, left: 480 }, check: null },
    ];
    vm.runInContext('SiteTime.start()', ctx);
    await settle();
    const beatAt = [];
    let seen = calls.length;
    for (let sec = 1; sec <= 215; sec++) {
      if (sec === 5) fire('pointerdown', false);           // a script's click — not a person
      if (sec === 10) fire('pointerdown', true);
      if (sec === 11) { now += 500; fire('touchmove', true); now -= 500; }   // 1.5 s after the first
      if (sec === 12) { now -= 400; fire('wheel', true); now += 400; }       // 100 ms after — the same swipe
      if (sec === 70) ctx.document.visibilityState = 'hidden';
      if (sec === 100) ctx.document.visibilityState = 'visible';
      if (sec === 120) fire('keydown', true);
      tick();
      await settle();
      if (calls.length > seen) { beatAt.push(sec); seen = calls.length; }
    }
    out.calls = calls.map(c => [c[0], c[1]]);
    out.beatAtSec = beatAt;
    out.partyAdds = partyAdds;
    out.helloDone = helloDone;
  } else if (scenario === 'presence') {
    responses = [{ ok: true, enabled: true, active: 1200, awards: [], balance: 0, next: null, check: 'tok1' },
                 { ok: true, check: null }];
    vm.runInContext('SiteTime.start()', ctx);
    await settle();
    const card = body.children.find(e => e.className === 'st-check');
    out.cardShown = !!card;
    now += 100;
    card.fire('click', { isTrusted: true });                 // too fast to be a person
    now += 400;
    card.fire('click', { isTrusted: false });                // scripted
    await settle();
    now += 100;
    card.fire('click', { isTrusted: true });
    await settle();
    out.herePosts = calls.filter(c => c[0] === '/api/site-time/here').length;
    out.hereBody = (calls.find(c => c[0] === '/api/site-time/here') || [])[1];
    out.cardAfter = body.children.includes(card);
  } else if (scenario === 'durations') {
    const run = code => vm.runInContext(code, ctx);
    out.uz = run('[stDur(60), stDur(540), stDur(3600), stDur(5400), stDur(0, true), stDur(36000)]');
    ctx.lang = 'ru';
    out.ru = run('[stDur(60), stDur(540), stDur(3600), stDur(5400)]');
    out.ruLong = run('[stDur(60, true, true), stDur(600, true, true), stDur(3600, true, true), stDur(7200, true, true), stDur(1320, true, true)]');
    ctx.lang = 'uz';
    out.next = run('stNextText({ seconds: 600, amount: 50, left: 540 })');
  }
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
