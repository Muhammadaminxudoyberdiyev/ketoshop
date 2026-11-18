// 🎮 O'yinlar markazi (webapp/games2.js): every new game is played to the end
// against a tiny DOM stub and a fake /api, in all three languages; the
// content is checked for shape. No network, no Telegram.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const vm = require('node:vm');

const contentSrc = fs.readFileSync('webapp/games2_content.js', 'utf8');
const gamesSrc = fs.readFileSync('webapp/games2.js', 'utf8');

// ── content shape ────────────────────────────────────────────────────
const C = (() => { const w = {}; vm.runInNewContext(contentSrc, { window: w }); return w.G2C; })();
const pair = (p, where) => assert.ok(Array.isArray(p) && p.length >= 2 && p[0] && p[1], 'uz/ru pair: ' + where);
assert.equal(C.clue.length, 30); assert.equal(C.story.length, 30); assert.equal(C.map.length, 10);
assert.ok(C.swap.length >= 8 && C.label.length >= 10 && C.myth.length >= 20 && C.bazaar.length >= 5);
C.swap.forEach((d, i) => { pair(d.dish, 'swap ' + i); d.steps.forEach(st => { pair(st.from, 'swap from'); assert.equal(st.opts.length, 3); st.opts.forEach(o => pair(o, 'swap opt')); pair(st.why, 'swap why'); }); });
C.label.forEach((l, i) => { pair(l.name, 'label ' + i); pair(l.why, 'label why'); l.items.forEach(it => { assert.equal(it.length, 3); assert.ok([0, 1].includes(it[2])); }); });
C.clue.forEach((q, i) => { pair(q.a, 'clue ' + i); assert.equal(q.hints.length, 3); q.hints.forEach(h => pair(h, 'hint')); assert.equal(q.wrong.length, 3); q.wrong.forEach(w => { pair(w, 'wrong'); assert.notEqual(w[0], q.a[0]); }); });
C.myth.forEach((m, i) => { assert.equal(m.length, 5, 'myth ' + i); assert.ok([0, 1].includes(m[2])); });
C.story.forEach((c, i) => { pair(c.t, 'story ' + i); pair(c.s, 'scene'); assert.equal(c.c.length, 3); c.c.forEach(o => { pair(o[0], 'choice'); pair(o[1], 'outcome'); Object.keys(o[2]).forEach(k => assert.ok(['energiya', 'natija', 'kayfiyat'].includes(k), k)); }); });
C.bazaar.forEach((m, i) => { pair(m.goal, 'bazaar ' + i); assert.equal(m.stalls.length, 5); m.stalls.forEach(st => { assert.equal(st.goods.length, 3); assert.equal(JSON.stringify(Array.from(st.goods, g => g[2]).sort()), "[-1,0,1]"); pair(st.why, 'stall why'); }); });
C.map.forEach((s, i) => { pair(s.name, 'map ' + i); assert.equal(s.qs.length, 3); s.qs.forEach(q => { pair(q[0], 'map q'); assert.equal(q[1].length, 4); pair(q[2], 'map why'); }); });

// ── a page around the games ──────────────────────────────────────────
function page(lang, cfg = {}) {
  const screens = [];
  const posts = [];
  const els = {};
  const el = id => (els[id] = els[id] || { id, innerHTML: '', textContent: '', outerHTML: '', classList: { add() {}, remove() {}, toggle() {} }, remove() {}, scrollIntoView() {}, querySelector: () => null, appendChild() {}, dataset: {} });
  let state = { ok: true, clue_seed: 739000, clue_solved: false, streak: 2, best_streak: 5, story: { done: 3, open: 4, stats: { energiya: 60 } },
    map: { done: 1, open: 2 }, tasks: { clue: false, journey: false, game: false, done: 0 }, keto_today: 10, keto_cap: 60, earning: true,
    solvers_today: 12, board: { top: [{ name: 'Ali V.', points: 40, rank: 1, me: false }, { name: 'Siz', points: 10, rank: 2, me: true }], me: { name: 'Siz', points: 10, rank: 2, me: true } },
    share_url: 'https://t.me/ketoshopbot/shop?startapp=oyin' };
  const ctx = {
    window: {}, console, setTimeout, clearTimeout, Proxy,
    lang,
    gx: (uz, ru) => (lang === 'ru' ? ru : uz),
    escapeHtml: s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])),
    gameShuffle: a => a.slice(),        // no randomness: the right answer stays first
    gameHaptic() {}, launchConfetti() {}, showToast() {}, loadCart: async () => {}, openDetail() {},
    trk() {}, quickAddToCart() {},
    latToCyr: s => s,
    gameProgressHtml: () => '<progress>',
    gameRevealHtml: (ok, v, body, cat, next, fn) => '<reveal ' + fn + '>' + v + body,
    gameNextLabel: () => 'next',
    showGameReveal: html => screens.push({ reveal: html }),
    setGameScreen: (id, score, inner) => screens.push({ id, score, inner }),
    renderGamesPage() {},
    tg: { openTelegramLink: url => posts.push({ share: url }), HapticFeedback: { notificationOccurred() {}, selectionChanged() {} } },
    document: { getElementById: id => el(id), querySelectorAll: () => [], querySelector: () => null, createElement: () => el('x'), head: { appendChild() {} } },
    api: async (path, opts) => {
      if (path === '/api/games/state') return cfg.slowState ? new Promise(() => {}) : state;
      if (path.startsWith('/api/products') && cfg.slowProducts) return new Promise(() => {});   // never answers
      if (path.startsWith('/api/products')) return { products: [{ id: 7, name: 'Bodom uni 500gr', price: 90000, out_of_stock: false }, { id: 8, name: 'Eritritol 100gr', price: 30000 }, { id: 9, name: 'Tabiiy GHEE 1000ml', price: 120000 }] };
      if (path === '/api/games/finish') {
        const body = JSON.parse(opts.body);
        posts.push(body);
        return Object.assign({}, state, { paid: 5, notes: body.game === 'clue' ? [{ kind: 'streak', streak: 3, keto: 10 }] : [] });
      }
      throw new Error('unexpected ' + path);
    },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(contentSrc, ctx);
  vm.runInContext('let gameState = null;', ctx);
  vm.runInContext(gamesSrc, ctx);
  const G2 = ctx.G2;
  const last = () => screens[screens.length - 1];
  const tick = () => new Promise(r => setTimeout(r, 0));
  const gs = () => vm.runInContext('gameState', ctx);
  return { G2, ctx, screens, posts, last, tick, gs, setState: s => { state = Object.assign(state, s); } };
}

(async () => {
  // 2026-11-18: «Men kimman?» — the right answer must show the result at once,
  // even when the game state and the product list are slow or never come.
  {
    const P = page('uz', { slowProducts: true, slowState: true });
    P.G2.starters.clue();
    assert.equal(P.gs().id, 'clue');
    assert.match(P.last().inner, /quiz-opts/);               // the puzzle is on screen without the server
    P.G2.answerClue(0);
    await P.tick();
    assert.ok(P.last().inner.includes('game-result'), 'result shown without waiting for products');
    assert.ok(P.last().inner.includes('id="g2-shop-'), 'products come later into their place');
    P.G2.starters.swap();
    for (let i = 0; i < 20 && P.gs() && !P.gs().finished; i++) { P.G2.answerSwap(0); await P.G2.nextSwap(); }
    assert.ok(P.last().inner.includes('game-result'));
    P.G2.starters.story();
    assert.match(P.last().inner, /Yuklanmoqda|G2\.playChapter/);   // drawn at once — from the state or with a loading line
    const Q = page('ru', { slowState: true });
    Q.G2.starters.map();
    assert.match(Q.last().inner, /Загрузка/);                 // nothing known yet: a visible line, never a frozen tap
  }
  for (const lang of ['uz', 'ru', 'uz_cyr']) {
    const P = page(lang);
    const { G2, posts, last, tick } = P;
    assert.equal(G2.tiles.length, 7);
    Object.keys(G2.starters).forEach(id => assert.ok(G2.icons[id], 'icon ' + id));
    assert.equal(G2.tileLabel('keto'), null);           // the old games keep their own labels

    // daily puzzle: wrong, wrong, right → 1 point; the reward and a share button show
    await G2.starters.clue(); await tick();
    assert.equal(P.gs().id, 'clue');
    G2.answerClue(1); G2.answerClue(2);
    assert.match(last().inner, /<b>3<\/b>/);             // the third hint is open
    G2.answerClue(0); await tick(); await tick(); await tick();
    const clueRes = posts.find(p => p.game === 'clue');
    assert.deepEqual(clueRes, { game: 'clue', points: 1 });
    assert.ok(P.screens.some(s => s.inner && s.inner.includes('G2.share(0)')));

    // swap: all right → full score, shop block with «Hammasini savatga»
    G2.starters.swap();
    const swapSteps = P.screens.length;
    for (let i = 0; i < 20 && P.gs() && !P.gs().finished; i++) { G2.answerSwap(0); await G2.nextSwap(); }
    const sw = posts.find(p => p.game === 'swap');
    assert.ok(sw && sw.points === sw.total && sw.total >= 4, JSON.stringify(sw));
    assert.ok(P.screens.slice(swapSteps).some(s => s.inner && s.inner.includes('G2.addAll')));

    // label: tap exactly the sugars → 15/15
    G2.starters.label();
    for (let i = 0; i < 5; i++) {
      const lb = vm.runInContext('G2C', P.ctx).label;
      // the running label is the i-th of the (unshuffled) first five
      lb[i].items.forEach((it, k) => { if (it[2]) G2.toggleLabel(k); });
      G2.checkLabel(); G2.nextLabel();
    }
    await tick();
    assert.deepEqual(posts.find(p => p.game === 'label'), { game: 'label', points: 15, total: 15 });

    // myth: answer by the truth → 11 (the golden one counts twice)
    G2.starters.myth();
    for (let i = 0; i < 10; i++) { G2.answerMyth(P.ctx.G2C.myth[i][2]); G2.nextMyth(); }
    await tick();
    assert.equal(posts.find(p => p.game === 'myth').points, 11);

    // story: chapter 4 (open), the best-for-stats choice, then a replay that reports nothing
    await G2.starters.story();
    assert.ok(last().inner.includes('G2.playChapter(4)'));
    G2.playChapter(4); await G2.chooseStory(0);
    const st = posts.find(p => p.game === 'story');
    assert.equal(st.chapter, 4);
    const before = posts.length;
    G2.playChapter(1, true); await G2.chooseStory(0);
    assert.equal(posts.length, before);

    // bazaar: the right good at every stall → 5/5, 59 points
    await G2.starters.bazaar();
    G2.playMission(0);
    for (let i = 0; i < 5; i++) {
      const good = P.ctx.G2C.bazaar[0].stalls[i].goods.findIndex(g => g[2] === 1);
      G2.pickGood(good); await G2.nextStall();
    }
    assert.deepEqual(posts.find(p => p.game === 'bazaar'), { game: 'bazaar', points: 59, total: 59 });

    // map: station 2 is open → three right answers → reported
    await G2.starters.map();
    assert.ok(last().inner.includes('G2.playStation(2)'));
    assert.ok(!last().inner.includes('G2.playStation(3)'));          // tomorrow's stays shut
    G2.playStation(2); G2.stationQ();
    for (let i = 0; i < 3; i++) { G2.answerStation(0); await G2.nextStation(); }
    assert.deepEqual(posts.find(p => p.game === 'map'), { game: 'map', station: 2, points: 3, total: 3 });

    // the old games report through G2.report
    G2.report('memory', 8, 6); await tick();
    assert.deepEqual(posts.find(p => p.game === 'memory'), { game: 'memory', points: 8, total: 10 });

    // the daily layer: tasks, streak, Keto, board, social proof
    await G2.refresh();
    const dash = G2.dashHtml();
    assert.ok(dash.includes('g2-ring') && dash.includes('🔥') && dash.includes('10/60') && dash.includes('Ali V.'));
    assert.ok(dash.includes("openGame('clue')") && dash.includes("openGame('story')"));

    // share opens Telegram's share sheet with the tracked link
    G2.share(0);
    assert.ok(posts.some(p => p.share && p.share.includes(encodeURIComponent('startapp=oyin'))));
  }
  console.log('games2_check: content shape, seven games played in uz/ru/uz_cyr, daily layer and share passed');
})().catch(e => { console.error(e); process.exit(1); });
