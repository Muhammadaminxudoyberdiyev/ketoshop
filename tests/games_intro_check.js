// Every game has a «Qanday o'ynaladi» card in uz and ru (games2_intro.js, 2026-11-21).
const fs = require('node:fs');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const ctx = { window: {}, escapeHtml: s => String(s), gx: (u, r) => u, gameTitle: id => id,
  document: { createElement: () => ({}), head: { appendChild() {} } }, localStorage: { getItem: () => null, setItem() {} } };
ctx.window = ctx;
ctx.scrollTo = () => {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('webapp/games2_intro.js', 'utf8'), ctx);
const intro = ctx.G2.INTRO;
const ids = ['clue', 'story', 'map', 'swap', 'label', 'myth', 'bazaar', 'keto', 'duel', 'quiz', 'memory'];
ids.forEach(id => {
  const it = intro[id];
  assert.ok(it, id);
  assert.equal(it[1].length, 3, id + ' uz rules');
  assert.equal(it[2].length, 3, id + ' ru rules');
  assert.ok(it[3] && it[4], id + ' reward');
});
const shown = [];
ctx.setGameScreen = (id, s, html) => shown.push(html);
let started = 0;
assert.equal(ctx.G2.intro('clue', () => started++), true);
assert.match(shown[0], /G2\.go\('clue'\)/);
ctx.G2.go('clue');
assert.equal(started, 1);
console.log('games intro: 11 games explained in uz and ru, intro → start passed');
