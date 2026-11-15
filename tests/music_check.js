// Runs the Mini App's Birdsong module (synthesised birds + real recordings
// for the music, webapp/index.html) against a fake DOM, <audio> element, Web
// Audio API and clock, drives it through a scenario and prints what it did as
// JSON. Driven by tests/test_site_music.py. Nothing makes a sound.
//
// Three phones: one that lets sound play before any touch, one that waits for
// the first touch, and an iPhone (media volume is read-only there, so the
// music goes through a Web Audio gain).
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'webapp', 'index.html'), 'utf8');
const start = html.indexOf('const Birdsong = (() => {');
const end = html.indexOf('})();', html.indexOf('return { start, sync, sing', start)) + 5;
if (start < 0 || end < 5) throw new Error('Birdsong module not found');
const PLAYLIST = [
  { id: 'moonlight', src: '/music/moonlight.mp3', remote: 'https://upload.wikimedia.org/x/moonlight.mp3', uz: 'Betxoven — «Oy nuri» sonatasi', ru: 'Бетховен' },
  { id: 'clair-de-lune', src: '/music/clair-de-lune.mp3', remote: 'https://upload.wikimedia.org/x/clair-de-lune.mp3', uz: 'Debyussi — «Oy nuri» (Clair de lune)', ru: 'Дебюсси' },
  { id: 'bach-prelude', src: '/music/bach-prelude.mp3', remote: 'https://upload.wikimedia.org/x/bach-prelude.mp3', uz: 'Bax — Prelyudiya do-major', ru: 'Бах' },
];

function phone({ autoplay, ios }) {
  let now = 0;                                         // ms
  const timers = [];
  let nextId = 1;
  const addTimer = (fn, ms, repeat) => { const id = nextId++; timers.push({ id, fn, ms: Math.max(1, ms || 0), at: now + Math.max(1, ms || 0), repeat }); return id; };
  const clearTimer = id => { const i = timers.findIndex(t => t.id === id); if (i >= 0) timers.splice(i, 1); };
  const advance = ms => {
    const until = now + ms;
    for (;;) {
      const due = timers.filter(t => t.at <= until).sort((a, b) => a.at - b.at)[0];
      if (!due) break;
      now = due.at;
      if (due.repeat) due.at += due.ms; else clearTimer(due.id);
      due.fn();
    }
    now = until;
  };

  let gestured = false;
  const audioEls = [];
  const elListeners = {};
  function makeAudio() {
    let vol = 1;
    const el = {
      paused: true, srcAttr: null, plays: 0, attrs: {},
      get volume() { return vol; },
      set volume(v) { if (!ios) vol = v; },             // iOS: read-only
      set src(v) { this.srcAttr = v; },
      get src() { return this.srcAttr || ''; },
      getAttribute(k) { return k === 'src' ? this.srcAttr : this.attrs[k]; },
      setAttribute(k, v) { this.attrs[k] = v; },
      addEventListener(type, fn) { (elListeners[type] = elListeners[type] || []).push(fn); },
      play() {
        if (!autoplay && !gestured) return Promise.reject(new Error('NotAllowedError'));
        this.paused = false; this.plays++;
        (elListeners.playing || []).forEach(fn => fn());
        return Promise.resolve();
      },
      pause() { this.paused = true; },
    };
    audioEls.push(el);
    return el;
  }

  const param = () => ({ value: 0, setValueAtTime() {}, linearRampToValueAtTime(v) { this.value = v; },
                         exponentialRampToValueAtTime() {}, cancelScheduledValues() {} });
  const node = extra => Object.assign({ connect() {}, disconnect() {} }, extra);
  let routedSources = 0;
  class FakeAudioContext {
    constructor() { this.state = gestured ? 'running' : 'suspended'; this.sampleRate = 8000; this.destination = node(); }
    get currentTime() { return now / 1000; }
    resume() { if (gestured) this.state = 'running'; return Promise.resolve(); }
    suspend() { this.state = 'suspended'; return Promise.resolve(); }
    createGain() { return node({ gain: param() }); }
    createBiquadFilter() { return node({ type: '', frequency: param() }); }
    createDelay() { return node({ delayTime: param() }); }
    createConvolver() { return node({ buffer: null }); }
    createStereoPanner() { return node({ pan: param() }); }
    createBuffer(ch, len) { return { getChannelData: () => new Float32Array(len) }; }
    createOscillator() { return node({ type: 'sine', frequency: param(), start() {}, stop() {} }); }
    createMediaElementSource() { routedSources++; return node(); }
  }

  const store = {};
  const toasts = [];
  const listeners = {};
  const btn = { style: {}, classList: { toggle() {} }, setAttribute() {} };
  const ctx = {
    window: { AudioContext: FakeAudioContext },
    document: {
      hidden: false,
      createElement: tag => (tag === 'audio' ? makeAudio() : btn),
      getElementById: id => (id === 'music-playlist' ? { textContent: JSON.stringify(PLAYLIST) } : null),
      body: { appendChild() {} },
      addEventListener: (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); },
      removeEventListener() {},
      querySelector: () => null,
    },
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } },
    activePage: 'home', t: { birdsOn: 'ON', birdsOff: 'OFF' },
    showToast: msg => toasts.push(msg), gx: uz => uz,
    setTimeout: (fn, ms) => addTimer(fn, ms, false), clearTimeout: clearTimer,
    setInterval: (fn, ms) => addTimer(fn, ms, true), clearInterval: clearTimer,
    Math, Date, Object, Promise, parseInt, String, Float32Array, JSON,
  };
  vm.createContext(ctx);
  vm.runInContext(html.slice(start, end) + '\nglobalThis.Birdsong = Birdsong;', ctx);
  const tap = () => { gestured = true; (listeners.click || []).forEach(fn => fn()); };
  const flush = () => new Promise(r => setImmediate(r));
  // audioEls[0] is the module's own volume probe; the player is the last one made.
  const player = () => audioEls[audioEls.length - 1];
  return { B: ctx.Birdsong, ctx, store, toasts, advance, tap, flush, btn, audioEls, elListeners, player,
           routed: () => routedSources };
}

(async () => {
  const out = {};

  // 1) A phone that allows sound before a touch: music at once, no tap.
  let p = phone({ autoplay: true, ios: false });
  p.B.admin();                                   // no night rule — the test must not depend on the clock
  p.B.start();
  await p.flush();
  p.advance(2000);
  const el = p.player();
  out.playsWithoutTap = !!el && !el.paused;
  out.firstPiece = p.store.ketoshop_music_piece;
  out.firstSrc = el && el.src;
  out.fadedIn = el && el.volume > 0.2 && el.volume <= 0.36;

  p.ctx.activePage = 'checkout';
  p.advance(1500);
  out.silentAtCheckout = el.paused;
  p.ctx.activePage = 'catalog';
  p.advance(1000);
  await p.flush();
  out.backAfterCheckout = !el.paused;

  p.btn.onclick();                               // off
  p.advance(1000);
  out.silentWhenOff = el.paused;
  out.offToast = p.toasts[p.toasts.length - 1];
  p.btn.onclick();                               // on again → the next piece
  await p.flush();
  p.advance(500);
  out.pieceAfterToggle = p.store.ketoshop_music_piece;
  out.onToast = p.toasts[p.toasts.length - 1];
  out.playingAfterToggle = !el.paused;

  const before = p.store.ketoshop_music_piece;
  (p.elListeners.ended || []).forEach(fn => fn());   // the piece ends → the next one
  await p.flush();
  out.autoAdvanced = p.store.ketoshop_music_piece !== before;
  out.srcAfterEnd = el.src;
  (p.elListeners.error || []).forEach(fn => fn());   // our server has no copy → Wikimedia
  await p.flush();
  out.srcAfterError = el.src;

  // 2) A phone that wants a touch first: tries at once, starts on the first tap.
  p = phone({ autoplay: false, ios: false });
  p.B.admin();
  p.B.start();
  await p.flush();
  p.advance(3000);
  await p.flush();
  out.waitsForTap = p.player().paused;
  out.triesBeforeTap = p.player().plays === 0;
  p.tap();
  await p.flush();
  p.advance(1000);
  out.playsAfterTap = !p.player().paused;

  // 3) iPhone: media volume is read-only — the music goes through Web Audio.
  p = phone({ autoplay: false, ios: true });
  p.B.admin();
  p.B.start();
  await p.flush();
  p.tap();
  await p.flush();
  p.advance(1000);
  out.iosRouted = p.routed() === 1;
  out.iosPlays = !p.player().paused;

  process.stdout.write(JSON.stringify(out));
})();
