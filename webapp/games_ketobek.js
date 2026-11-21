/* 🚚 «Ketobek / Ketoxonim» — a top-down city driving game (the player picks the
   hero before the shift — owner, 2026-11-21: "O'yin nomi Keto kuryer emas,
   Ketoxonim yoki Ketobek bo'lishi kerak, o'zlari tanlashlari kerak o'yin
   boshlashdan avval"). Earlier brief (owner, 2026-11-21: "o'yinlarni
   yanada kengaytir boshqarib o'ynaydigan ... Keto shop stilida ... sensitive
   content bo'lmasin ... oddiy neytral stillar va o'yinlar va vazifalar").
   Our own game: a small neutral town, the Ketoshop van, orders to pick up and
   deliver, ingredients to collect, other cars to steer around (a bump only
   costs seconds). Canvas, no images, no libraries; a joystick on phones and the
   arrow keys on a computer. The score goes to the week's board and Keto
   (games.py, game "kuryer"). Loaded before the page's main script. */
(function () {
  'use strict';
  const G2 = window.G2 = window.G2 || {};
  const T = (uz, ru) => gx(uz, ru);
  const E = s => escapeHtml(String(s == null ? '' : s));

  const TILE = 90, N = 15, W = TILE * N;          // a 15×15 town
  const ROAD = i => i % 3 === 0;                    // every third row and column is a road
  const GAME_SECONDS = 120, DELIVERY_BONUS_S = 15, BUMP_S = 2;
  const PICKUPS = ['🥚', '🧀', '🥦', '🌰', '🍓', '🥥', '🫒', '🥜'];

  G2.tiles = G2.tiles || [];
  G2.tiles.unshift({ id: 'kuryer', title: ['Ketobek · Ketoxonim', 'Кетобек · Кетохоним'], sub: ["Qahramonni tanlang va shaharda buyurtma yetkazing", 'Выберите героя и развозите заказы по городу'] });
  const HEROES = {
    bek: { name: ['Ketobek', 'Кетобек'], icon: '🙋‍♂️', van: '#6E9A6A' },
    xonim: { name: ['Ketoxonim', 'Кетохоним'], icon: '🙋‍♀️', van: '#B86F7E' },
  };
  const HERO_KEY = 'ketoshop_ketobek_hero';
  const heroName = () => (S && S.hero ? T(HEROES[S.hero].name[0], HEROES[S.hero].name[1]) : '');
  G2.icons = G2.icons || {};
  G2.icons.kuryer = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/></svg>';
  G2.starters = G2.starters || {};
  if (G2.INTRO) {
    G2.INTRO.kuryer = ['🚚',
      ["Ketobek yoki Ketoxonimni tanlang va joystik (yoki strelkalar) bilan furgonni boshqaring", "Do'kondan buyurtmani oling va ko'rsatkich bo'yicha mijozga yetkazing",
       "Yo'ldagi masalliqlarni tering, mashinalarga urilmang — urilsangiz 2 soniya ketadi"],
      ['Выберите Кетобека или Кетохоним и управляйте фургоном джойстиком (или стрелками)', 'Заберите заказ в магазине и доставьте клиенту по стрелке',
       'Собирайте продукты по пути и объезжайте машины — столкновение отнимает 2 секунды'],
      "Har yetkazish +15 soniya; kunning birinchi o'yini — 8 Keto", 'Каждая доставка +15 секунд; первая игра дня — 8 Keto'];
  }

  // ── the town (drawn once into an off-screen canvas) ──
  let rnd = 1;
  const rand = () => ((rnd = (rnd * 16807) % 2147483647) - 1) / 2147483646;
  function buildTown() {
    rnd = 7;
    const houses = [];                       // {x, y, door: {x, y}, color}
    const blocks = [];
    for (let by = 0; by < N - 1; by += 3) {
      for (let bx = 0; bx < N - 1; bx += 3) {
        const x = (bx + 1) * TILE, y = (by + 1) * TILE, s = 2 * TILE;
        const kind = (bx === 6 && by === 6) ? 'shop' : (bx === 3 && by === 9) || (bx === 9 && by === 3) ? 'park' : 'homes';
        blocks.push({ x, y, s, kind });
        if (kind === 'homes') {
          [[0, 0], [1, 0], [0, 1], [1, 1]].forEach(([i, j]) => {
            const hx = x + i * TILE + 14, hy = y + j * TILE + 14;
            const door = { x: x + i * TILE + TILE / 2, y: j ? y + s + TILE / 2 - 8 : y - TILE / 2 + 8 };
            houses.push({ x: hx, y: hy, w: TILE - 28, h: TILE - 28, door,
              roof: ['#C98B6B', '#8FB48A', '#D9B45F', '#9CB6D6', '#C7A0C9', '#E0A07D'][Math.floor(rand() * 6)] });
          });
        }
      }
    }
    return { houses, blocks, shop: { x: 7 * TILE + TILE / 2, y: 6 * TILE + TILE / 2 + 4 } };
  }

  function paintTown(town) {
    const c = document.createElement('canvas');
    c.width = W; c.height = W;
    const g = c.getContext('2d');
    g.fillStyle = '#CFE3C3'; g.fillRect(0, 0, W, W);                       // grass
    for (let i = 0; i < N; i++) {
      if (!ROAD(i)) continue;
      g.fillStyle = '#7C7F86';
      g.fillRect(0, i * TILE, W, TILE); g.fillRect(i * TILE, 0, TILE, W);
    }
    g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 3; g.setLineDash([16, 16]);
    for (let i = 0; i < N; i++) {
      if (!ROAD(i)) continue;
      g.beginPath(); g.moveTo(0, i * TILE + TILE / 2); g.lineTo(W, i * TILE + TILE / 2); g.stroke();
      g.beginPath(); g.moveTo(i * TILE + TILE / 2, 0); g.lineTo(i * TILE + TILE / 2, W); g.stroke();
    }
    g.setLineDash([]);
    town.blocks.forEach(b => {
      g.fillStyle = b.kind === 'park' ? '#A9D39A' : '#E9E1D2';
      roundRect(g, b.x + 6, b.y + 6, b.s - 12, b.s - 12, 16); g.fill();
      if (b.kind === 'park') {
        for (let k = 0; k < 9; k++) tree(g, b.x + 30 + (k % 3) * 60, b.y + 30 + Math.floor(k / 3) * 60);
        g.fillStyle = '#8EC4E0'; g.beginPath(); g.ellipse(b.x + b.s / 2, b.y + b.s / 2, 30, 20, 0, 0, Math.PI * 2); g.fill();
      }
      if (b.kind === 'shop') {
        g.fillStyle = '#6E9A6A'; roundRect(g, b.x + 22, b.y + 22, b.s - 44, b.s - 44, 18); g.fill();
        g.fillStyle = '#FFF8EC'; g.font = '800 26px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText('Keto', b.x + b.s / 2, b.y + b.s / 2 - 14); g.fillText('shop', b.x + b.s / 2, b.y + b.s / 2 + 16);
      }
    });
    town.houses.forEach(h => {
      g.fillStyle = 'rgba(0,0,0,.12)'; roundRect(g, h.x + 4, h.y + 5, h.w, h.h, 8); g.fill();
      g.fillStyle = h.roof; roundRect(g, h.x, h.y, h.w, h.h, 8); g.fill();
      g.strokeStyle = 'rgba(255,255,255,.45)'; g.lineWidth = 2;
      g.beginPath(); g.moveTo(h.x + 6, h.y + h.h / 2); g.lineTo(h.x + h.w - 6, h.y + h.h / 2); g.stroke();
    });
    for (let k = 0; k < 60; k++) {                                         // trees along the blocks
      const b = town.blocks[Math.floor(rand() * town.blocks.length)];
      if (b.kind === 'homes') tree(g, b.x + 8 + rand() * (b.s - 16), b.y + (rand() < .5 ? 8 : b.s - 8));
    }
    return c;
  }
  function tree(g, x, y) {
    g.fillStyle = 'rgba(0,0,0,.12)'; g.beginPath(); g.arc(x + 3, y + 4, 11, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#6FA866'; g.beginPath(); g.arc(x, y, 11, 0, Math.PI * 2); g.fill();
  }
  function roundRect(g, x, y, w, h, r) {
    g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
  }
  const onRoad = (x, y) => x > 4 && y > 4 && x < W - 4 && y < W - 4 &&
    (ROAD(Math.floor(y / TILE)) || ROAD(Math.floor(x / TILE)));

  // ── a run ──
  let S = null;
  function start() {
    let last = null;
    try { last = localStorage.getItem(HERO_KEY); } catch (_) {}
    gameState = { id: 'kuryer', g2: true };
    const card = (k) => '<button type="button" class="ky-hero' + (k === last ? ' last' : '') + '" onclick="G2.pickHero(\'' + k + '\')">' +
      '<span class="ky-hero-ic">' + HEROES[k].icon + '</span><b>' + E(T(HEROES[k].name[0], HEROES[k].name[1])) + '</b>' +
      '<small>' + E(k === 'bek' ? T('Yashil furgon', 'Зелёный фургон') : T('Gulrang furgon', 'Розовый фургон')) + '</small></button>';
    setGameScreen('kuryer', '',
      '<div class="ky-pick-title">' + E(T('Bugun kim smenada?', 'Кто сегодня на смене?')) + '</div>' +
      '<div class="ky-heroes">' + card('bek') + card('xonim') + '</div>' +
      '<div class="ky-help">' + E(T("Tanlovingiz eslab qolinadi — keyingi smenada o'zgartirish mumkin", 'Выбор запомнится — в следующую смену можно сменить')) + '</div>');
  }
  G2.pickHero = function (hero) {
    if (!HEROES[hero]) return;
    try { localStorage.setItem(HERO_KEY, hero); } catch (_) {}
    play(hero);
  };
  function play(hero) {
    const town = buildTown();
    S = {
      hero,
      town, map: paintTown(town),
      car: { x: 7 * TILE + TILE / 2, y: 9 * TILE + TILE / 2, a: -Math.PI / 2, v: 0 },
      npcs: [], items: [], phase: 'pickup', target: town.shop, house: null,
      left: GAME_SECONDS, delivered: 0, points: 0, bumpUntil: 0, msg: '', msgUntil: 0,
      joy: { x: 0, y: 0, on: false }, keys: {}, last: 0, over: false,
    };
    for (let k = 0; k < 9; k++) {                                          // other cars on their lanes
      const line = 3 * Math.floor(rand() * 5);
      const horiz = k % 2 === 0;
      const pos = TILE / 2 + line * TILE;
      S.npcs.push({ horiz, x: horiz ? rand() * W : pos + 14, y: horiz ? pos - 14 : rand() * W,
        v: (rand() < .5 ? -1 : 1) * (60 + rand() * 50), color: ['#E07A5F', '#5B8DBE', '#E0B84F', '#8E7CC3'][k % 4] });
    }
    for (let k = 0; k < 14; k++) spawnItem();
    gameState = { id: 'kuryer', g2: true };
    setGameScreen('kuryer', '',
      '<div class="ky-hud" id="ky-hud"></div>' +
      '<div class="ky-wrap"><canvas id="ky-canvas"></canvas>' +
        '<div class="ky-joy" id="ky-joy"><div class="ky-knob" id="ky-knob"></div></div>' +
        '<div class="ky-msg" id="ky-msg"></div></div>' +
      '<div class="ky-help">' + E(T("Joystikni barmoq bilan suring — furgon o'sha tomonga yuradi", 'Ведите джойстик пальцем — фургон едет в ту сторону')) + '</div>');
    bindControls();
    say(heroName() + ', ' + T("do'kondan buyurtmani oling 🏪", 'заберите заказ в магазине 🏪'));
    try { trk(() => Trk.open('game', 'kuryer')); } catch (_) {}
    S.last = performance.now();
    requestAnimationFrame(frame);
  }
  function spawnItem() {
    for (let tries = 0; tries < 30; tries++) {
      const line = 3 * Math.floor(rand() * 5), horiz = rand() < .5, along = TILE + rand() * (W - 2 * TILE);
      const x = horiz ? along : line * TILE + TILE / 2, y = horiz ? line * TILE + TILE / 2 : along;
      if (onRoad(x, y)) { S.items.push({ x, y, e: PICKUPS[Math.floor(rand() * PICKUPS.length)] }); return; }
    }
  }
  function say(text) { S.msg = text; S.msgUntil = performance.now() + 2600; }

  function bindControls() {
    const joy = document.getElementById('ky-joy'), knob = document.getElementById('ky-knob');
    const R = 46;
    const move = e => {
      const r = joy.getBoundingClientRect();
      let dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
      const d = Math.hypot(dx, dy);
      if (d > R) { dx *= R / d; dy *= R / d; }
      S.joy = { x: dx / R, y: dy / R, on: true };
      knob.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
    };
    const end = () => { S.joy = { x: 0, y: 0, on: false }; knob.style.transform = ''; };
    joy.addEventListener('pointerdown', e => { joy.setPointerCapture(e.pointerId); move(e); e.preventDefault(); });
    joy.addEventListener('pointermove', e => { if (S.joy.on) move(e); });
    joy.addEventListener('pointerup', end);
    joy.addEventListener('pointercancel', end);
    S.onKey = e => {
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      S.keys[e.key] = e.type === 'keydown';
      e.preventDefault();
    };
    window.addEventListener('keydown', S.onKey);
    window.addEventListener('keyup', S.onKey);
  }

  function alive() {
    return S && !S.over && document.getElementById('ky-canvas') && gameState && gameState.id === 'kuryer';
  }
  function stop() {
    if (S && S.onKey) { window.removeEventListener('keydown', S.onKey); window.removeEventListener('keyup', S.onKey); }
  }

  function frame(now) {
    if (!alive()) { stop(); return; }
    const dt = Math.min(0.05, (now - S.last) / 1000);
    S.last = now;
    step(dt, now);
    draw(now);
    if (S.left <= 0) { finish(); return; }
    requestAnimationFrame(frame);
  }

  function step(dt, now) {
    const c = S.car;
    S.left -= dt;
    const bumped = now < S.bumpUntil;
    let want = 0;
    if (S.joy.on && Math.hypot(S.joy.x, S.joy.y) > 0.15) {
      const target = Math.atan2(S.joy.y, S.joy.x);
      let d = target - c.a;
      while (d > Math.PI) d -= 2 * Math.PI;
      while (d < -Math.PI) d += 2 * Math.PI;
      c.a += Math.max(-4 * dt, Math.min(4 * dt, d));
      want = 230 * Math.min(1, Math.hypot(S.joy.x, S.joy.y));
    } else {
      if (S.keys.ArrowLeft) c.a -= 3 * dt;
      if (S.keys.ArrowRight) c.a += 3 * dt;
      want = S.keys.ArrowUp ? 230 : S.keys.ArrowDown ? -90 : 0;
    }
    if (bumped) want = 0;
    c.v += (want - c.v) * Math.min(1, 3 * dt);
    const nx = c.x + Math.cos(c.a) * c.v * dt, ny = c.y + Math.sin(c.a) * c.v * dt;
    if (onRoad(nx, ny)) { c.x = nx; c.y = ny; }
    else if (onRoad(nx, c.y)) { c.x = nx; c.v *= 0.7; }
    else if (onRoad(c.x, ny)) { c.y = ny; c.v *= 0.7; }
    else c.v *= 0.3;

    S.npcs.forEach(n => {
      if (n.horiz) { n.x += n.v * dt; if (n.x < 0 || n.x > W) n.v *= -1; }
      else { n.y += n.v * dt; if (n.y < 0 || n.y > W) n.v *= -1; }
      if (!bumped && Math.hypot(n.x - c.x, n.y - c.y) < 30) {
        S.bumpUntil = now + BUMP_S * 1000;
        S.left -= BUMP_S;
        c.v = 0;
        say(T("Ehtiyot bo'ling! −2 soniya", 'Осторожно! −2 секунды'));
        try { tg.HapticFeedback.notificationOccurred('warning'); } catch (_) {}
      }
    });
    S.items = S.items.filter(it => {
      if (Math.hypot(it.x - c.x, it.y - c.y) < 30) {
        S.points += 1;
        try { tg.HapticFeedback.impactOccurred('light'); } catch (_) {}
        setTimeout(spawnItem, 1500);
        return false;
      }
      return true;
    });
    if (Math.hypot(S.target.x - c.x, S.target.y - c.y) < 42) {
      if (S.phase === 'pickup') {
        S.phase = 'deliver';
        S.house = S.town.houses[Math.floor(rand() * S.town.houses.length)];
        S.target = S.house.door;
        say(T('Buyurtma olindi! Mijozga yetkazing 📦', 'Заказ у вас! Везите клиенту 📦'));
      } else {
        S.delivered += 1;
        S.points += 10;
        S.left += DELIVERY_BONUS_S;
        S.phase = 'pickup';
        S.target = S.town.shop;
        say(T('Yetkazildi! +15 soniya ✅', 'Доставлено! +15 секунд ✅'));
        try { tg.HapticFeedback.notificationOccurred('success'); } catch (_) {}
      }
    }
  }

  function draw(now) {
    const cv = document.getElementById('ky-canvas');
    const wrap = cv.parentElement;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = wrap.clientWidth, h = wrap.clientHeight;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      cv.style.width = w + 'px'; cv.style.height = h + 'px';
    }
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const c = S.car;
    const camX = Math.max(0, Math.min(W - w, c.x - w / 2)), camY = Math.max(0, Math.min(W - h, c.y - h / 2));
    g.fillStyle = '#CFE3C3'; g.fillRect(0, 0, w, h);
    g.drawImage(S.map, camX, camY, w, h, 0, 0, w, h);
    g.save(); g.translate(-camX, -camY);
    // the target: a soft pulsing ring
    const pulse = 26 + 6 * Math.sin(now / 200);
    g.strokeStyle = S.phase === 'pickup' ? 'rgba(110,154,106,.95)' : 'rgba(224,122,95,.95)';
    g.lineWidth = 5; g.beginPath(); g.arc(S.target.x, S.target.y, pulse, 0, Math.PI * 2); g.stroke();
    g.font = '24px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText(S.phase === 'pickup' ? '🏪' : '📦', S.target.x, S.target.y);
    S.items.forEach(it => { g.font = '22px sans-serif'; g.fillText(it.e, it.x, it.y); });
    S.npcs.forEach(n => vehicle(g, n.x, n.y, n.horiz ? (n.v > 0 ? 0 : Math.PI) : (n.v > 0 ? Math.PI / 2 : -Math.PI / 2), n.color, false));
    vehicle(g, c.x, c.y, c.a, now < S.bumpUntil && Math.floor(now / 150) % 2 ? '#F3C9BE' : HEROES[S.hero].van, true);
    g.restore();
    // pointer to the target when it is off screen
    const tx = S.target.x - camX, ty = S.target.y - camY;
    if (tx < 0 || ty < 0 || tx > w || ty > h) {
      const ang = Math.atan2(ty - h / 2, tx - w / 2);
      const px = w / 2 + Math.cos(ang) * (w / 2 - 28), py = h / 2 + Math.sin(ang) * (h / 2 - 28);
      g.save(); g.translate(px, py); g.rotate(ang);
      g.fillStyle = S.phase === 'pickup' ? '#6E9A6A' : '#E07A5F';
      g.beginPath(); g.moveTo(16, 0); g.lineTo(-10, -11); g.lineTo(-10, 11); g.closePath(); g.fill();
      g.restore();
    }
    const dist = Math.round(Math.hypot(S.target.x - c.x, S.target.y - c.y) / 3);
    document.getElementById('ky-hud').innerHTML =
      '<span>' + HEROES[S.hero].icon + ' ' + E(heroName()) + '</span>' +
      '<span>⏱ ' + Math.max(0, Math.ceil(S.left)) + '</span>' +
      '<span>📦 ' + S.delivered + '</span>' +
      '<span>⭐ ' + S.points + '</span>' +
      '<span class="ky-goal">' + (S.phase === 'pickup' ? '🏪 ' + E(T("Do'kon", 'Магазин')) : '🏠 ' + E(T('Mijoz', 'Клиент'))) + ' · ' + dist + ' m</span>';
    const m = document.getElementById('ky-msg');
    m.textContent = now < S.msgUntil ? S.msg : '';
    m.classList.toggle('show', now < S.msgUntil);
  }
  function vehicle(g, x, y, a, color, mine) {
    g.save(); g.translate(x, y); g.rotate(a);
    g.fillStyle = 'rgba(0,0,0,.18)'; roundRect(g, -17, -10, 38, 24, 6); g.fill();
    g.fillStyle = color; roundRect(g, -19, -12, 38, 24, 6); g.fill();
    g.fillStyle = 'rgba(255,255,255,.75)'; roundRect(g, 6, -9, 9, 18, 3); g.fill();          // windscreen
    if (mine) { g.fillStyle = '#FFF8EC'; g.font = '800 9px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('K', -6, 0); }
    g.restore();
  }

  async function finish() {
    S.over = true;
    stop();
    const pts = S.points;
    gameState = { id: 'kuryer', g2: true, finished: true };
    setGameScreen('kuryer', '',
      '<div class="game-result" id="game-result">' +
        '<div class="game-result-big">📦 ' + S.delivered + '</div>' +
        '<div class="game-result-msg">' + E(heroName() + ': ') + E(S.delivered >= 5 ? T("zo'r smena! Mijozlar mamnun 🎉", 'отличная смена! Клиенты довольны 🎉')
          : S.delivered >= 2 ? T('yaxshi smena!', 'хорошая смена!') : T("yana bir smena — tezroq bo'ladi", 'ещё смена — будет быстрее')) + '</div>' +
        '<div class="game-result-sub">⭐ ' + pts + ' ' + E(T('ochko', 'очков')) + '</div>' +
        '<div id="g2-reward" class="g2-reward"></div>' +
        '<div class="game-actions">' +
          '<button type="button" class="game-again" onclick="openGame(\'kuryer\')">' + E(T("Yana smena", 'Ещё смена')) + '</button>' +
          '<button type="button" class="game-other" onclick="renderGamesPage()">' + E(T("Boshqa o'yin", 'Другая игра')) + '</button>' +
        '</div></div>');
    if (S.delivered >= 3) { try { launchConfetti(document.getElementById('game-result')); } catch (_) {} }
    try {
      const res = await api('/api/games/finish', { method: 'POST', body: JSON.stringify({ game: 'kuryer', points: pts, total: pts }) });
      const slot = document.getElementById('g2-reward');
      if (slot && res && res.paid > 0) slot.innerHTML = '<div class="g2-keto">+' + res.paid + ' Keto 🎉</div>';
    } catch (_) {}
  }
  G2.starters.kuryer = start;
  G2.kuryerState = () => S;          // tests

  const css = `
  .ky-hud { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
  .ky-hud span { padding: 5px 10px; border-radius: 999px; background: var(--surface); border: 1px solid var(--hairline);
    font: 800 13px var(--font-display); }
  .ky-hud .ky-goal { margin-left: auto; }
  .ky-wrap { position: relative; height: 60vh; min-height: 320px; border-radius: 22px; overflow: hidden;
    border: 1px solid var(--hairline); touch-action: none; user-select: none; -webkit-user-select: none; }
  .ky-wrap canvas { display: block; width: 100%; height: 100%; }
  .ky-joy { position: absolute; left: 18px; bottom: 18px; width: 112px; height: 112px; border-radius: 50%;
    background: rgba(255,255,255,.35); border: 2px solid rgba(255,255,255,.7); touch-action: none; }
  .ky-knob { position: absolute; left: 31px; top: 31px; width: 50px; height: 50px; border-radius: 50%;
    background: rgba(110,154,106,.9); box-shadow: 0 6px 14px -6px rgba(0,0,0,.5); pointer-events: none; }
  .ky-msg { position: absolute; top: 12px; left: 50%; transform: translate(-50%, -6px); padding: 7px 14px; border-radius: 999px;
    background: rgba(40,32,24,.78); color: #fff; font: 800 13.5px var(--font-body); opacity: 0; transition: opacity .3s, transform .3s;
    pointer-events: none; white-space: nowrap; }
  .ky-msg.show { opacity: 1; transform: translate(-50%, 0); }
  .ky-help { margin-top: 8px; color: var(--hint); font-size: 12.5px; text-align: center; }
  .ky-pick-title { font: 800 18px var(--font-display); text-align: center; margin: 6px 0 14px; }
  .ky-heroes { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .ky-hero { display: grid; justify-items: center; gap: 6px; padding: 18px 10px; border-radius: 24px;
    border: 2px solid var(--hairline); background: var(--surface); color: var(--text); cursor: pointer;
    font: 800 16px var(--font-display); animation: popIn .4s var(--ease-spring); }
  .ky-hero.last { border-color: var(--pop); }
  .ky-hero small { color: var(--hint); font: 600 12px var(--font-body); }
  .ky-hero-ic { font-size: 54px; line-height: 1; }
  .ky-hero:active { transform: scale(.97); }
  .g2-scene-kuryer { background: linear-gradient(180deg, rgba(110,154,106,.10), transparent 60%); }
  `;
  try { const el = document.createElement('style'); el.textContent = css; document.head.appendChild(el); } catch (_) {}
})();
