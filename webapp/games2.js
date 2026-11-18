/* 🎮 O'yinlar markazi — seven new games and the games page's daily layer
   (owner, 2026-11-17: "hamma taklif qilingan o'yinlarni qur ... yuqori
   strategiya va inson psixologiyasini ham hisobga olib qur bog'liqlik bo'lsin").

   Loaded before the page's main script; everything it calls on the page
   (gx, escapeHtml, setGameScreen, api, quickAddToCart, launchConfetti, …)
   is only touched when a game runs. Content: games2_content.js (G2C).
   Server: games.py — Keto (daily cap), streak, story/map progress, the
   week's board. The page keeps working if the server is down: the games
   play, only Keto and the board wait.

   The habit loop, kept honest: one daily puzzle for everyone + a streak
   (one missed day a week forgiven), three small daily tasks with a bonus,
   one story chapter and one map station a day ending on what comes next,
   the week's board and "N people solved it today". No paid boosts, no
   countdown pressure, no fake scarcity. */
(function () {
  'use strict';
  const C = new Proxy({}, { get: (_, k) => (window.G2C || {})[k] });   // games2_content.js is deferred
  const G2 = window.G2 = {};
  let state = null;              // GET /api/games/state
  let products = null;           // the shop's products, loaded once for «Savatga»
  let run = null;                // the running new game

  const T = (uz, ru) => gx(uz, ru);
  const L = pair => gx(pair[0], pair[1]);
  const E = s => escapeHtml(String(s == null ? '' : s));
  const shuffle = a => gameShuffle(a);
  const pick = (a, n) => shuffle(a).slice(0, n);

  // ── tiles ──────────────────────────────────────────────────────────
  G2.tiles = [
    { id: 'clue', title: ['3 ta ishora', '3 подсказки'], sub: ['Kunlik jumboq — hamma uchun bitta', 'Загадка дня — одна для всех'] },
    { id: 'story', title: ["Keto yo'li: 30 kun", 'Путь кето: 30 дней'], sub: ['Har kuni yangi bob', 'Каждый день новая глава'] },
    { id: 'map', title: ['Ketoland xaritasi', 'Карта Кетоландии'], sub: ['10 bekat, kuniga bittadan', '10 станций, по одной в день'] },
    { id: 'swap', title: ['Almashtir!', 'Замени!'], sub: ['Taomni keto qiling', 'Сделайте блюдо кето'] },
    { id: 'label', title: ['Yorliq detektivi', 'Детектив этикеток'], sub: ['Yashirin shakarni toping', 'Найдите скрытый сахар'] },
    { id: 'myth', title: ['Afsona yoki haqiqat?', 'Миф или правда?'], sub: ['10 ta gap — siz hakamsiz', '10 утверждений — вы судья'] },
    { id: 'bazaar', title: ['Bozor sarguzashti', 'Приключение на базаре'], sub: ["Retsept uchun savat yig'ing", 'Соберите корзину для рецепта'] },
  ];
  const svg = d => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>';
  G2.icons = {
    clue: svg('<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/><path d="M11 8.5v3l2 1.2"/>'),
    story: svg('<path d="M4 5.5A2.5 2.5 0 016.5 3H20v15H6.5A2.5 2.5 0 004 20.5z"/><path d="M4 20.5A2.5 2.5 0 016.5 18H20v3H6.5"/>'),
    map: svg('<path d="M9 4L3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5z"/><path d="M9 4v13M15 6.5v13"/>'),
    swap: svg('<path d="M7 7h11l-3-3M17 17H6l3 3"/>'),
    label: svg('<path d="M4 4h9l7 7-9 9-7-7z"/><circle cx="8.5" cy="8.5" r="1.4"/>'),
    myth: svg('<path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.3 6-5.4-3.1-5.4 3.1 1.3-6L3.4 9.3l6-.7z"/>'),
    bazaar: svg('<path d="M3 9l1.5-5h15L21 9"/><path d="M4 9v11h16V9"/><path d="M3 9h18M9 20v-6h6v6"/>'),
  };

  // The tile's small line: streak, chapter, station — or «Yangi».
  G2.tileLabel = function (id) {
    if (!G2.starters[id]) return null;
    const s = state;
    if (id === 'clue' && s) return s.clue_solved ? T('✓ Bugun yechildi', '✓ Решено сегодня') : (s.streak ? '🔥 ' + s.streak + ' ' + T('kun', 'дн.') : T('✨ Yangi jumboq', '✨ Новая загадка'));
    if (id === 'story' && s) return s.story.done >= 30 ? '👑 30/30' : T('Bob ', 'Глава ') + Math.min(30, s.story.done + 1) + '/30';
    if (id === 'map' && s) return s.map.done >= 10 ? '👑 10/10' : T('Bekat ', 'Станция ') + Math.min(10, s.map.done + 1) + '/10';
    return T('✨ Yangi', '✨ Новое');
  };

  // ── server ─────────────────────────────────────────────────────────
  G2.refresh = async function () {
    setTimeout(() => loadProducts(), 1500);          // «Savatga» under results — ready before it is needed
    try { state = await api('/api/games/state'); } catch (_) { return; }
    const dash = document.getElementById('g2-dash');
    if (dash) dash.outerHTML = G2.dashHtml();
    document.querySelectorAll('.game-tile[data-game]').forEach(tile => {
      const id = tile.dataset.game, label = G2.tileLabel(id);
      if (label === null) return;
      let el = tile.querySelector('.game-tile-best');
      if (!el) { el = document.createElement('span'); el.className = 'game-tile-best'; tile.appendChild(el); }
      el.textContent = label;
    });
  };

  async function report(id, body) {
    try {
      const res = await api('/api/games/finish', { method: 'POST', body: JSON.stringify(Object.assign({ game: id }, body)) });
      if (res && res.ok !== false) state = res;
      return res;
    } catch (_) { return null; }
  }

  // The four old games report here from finishGame (index.html).
  G2.report = function (id, value, total) {
    let points = value;
    if (id === 'memory') points = Math.max(1, 10 - Math.max(0, value - total));
    report(id, { points, total: id === 'memory' ? 10 : total }).then(res => showReward(res));
  };

  // «+N Keto» under a result, plus a streak / tasks note.
  function showReward(res) {
    const slot = document.getElementById('g2-reward');
    if (!slot || !res) return;
    const parts = [];
    if (res.paid > 0) parts.push('<div class="g2-keto">+' + res.paid + ' Keto 🎉</div>');
    (res.notes || []).forEach(n => {
      if (n.kind === 'streak') parts.push('<div class="g2-note">🔥 ' + E(T(n.streak + ' kun ketma-ket! Bonus +' + n.keto + ' Keto', n.streak + ' дней подряд! Бонус +' + n.keto + ' Keto')) + '</div>');
      if (n.kind === 'tasks') parts.push('<div class="g2-note">✅ ' + E(T('Bugungi 3 topshiriq bajarildi! +' + n.keto + ' Keto', 'Все 3 задания дня выполнены! +' + n.keto + ' Keto')) + '</div>');
    });
    if (!res.paid && res.earning && res.keto_today >= res.keto_cap)
      parts.push('<div class="g2-note">' + E(T("Bugungi Keto chegarasi to'ldi — ochkolar reytingga yozilyapti", 'Дневной лимит Keto набран — очки идут в рейтинг')) + '</div>');
    if (res.board && res.board.me)
      parts.push('<div class="g2-note">🏆 ' + E(T('Haftalik reytingda ' + res.board.me.rank + '-o\'rindasiz', 'Вы на ' + res.board.me.rank + '-м месте недели')) + '</div>');
    slot.innerHTML = parts.join('');
    if (res.paid > 0) { try { tg.HapticFeedback.notificationOccurred('success'); } catch (_) {} }
  }

  // ── shop ───────────────────────────────────────────────────────────
  const KW_RU = {
    'bodom uni': 'миндальн', 'ghee': 'гхи', 'alluloza': 'аллюлоз', 'yashil grechka': 'зелён', 'zaytun': 'оливк',
    'kokos uni': 'кокосов', 'eritritol': 'эритрит', 'nibs': 'нибс', "zig'ir uni": 'льнян', 'olma sirkasi': 'уксус',
    'stevia': 'стеви', 'chia': 'чиа', 'kokos chips': 'кокосовые чипсы', 'kunjut': 'кунжут', 'qovoq urug': 'тыкв',
    'psillium': 'псиллиум', 'himalay': 'гималай', "no'xat uni": 'нут', 'javdar': 'ржан', 'devzira': 'девзир',
    'polba': 'полб', 'kepak': 'отруб', 'pista': 'фисташ', 'sedana': 'тмин', 'lasos': 'лосос', 'shokolad': 'шоколад',
    "zig'ir urug": 'лён', 'yeryong': 'арахис', 'ksantan': 'ксантан', 'kokos': 'кокос',
  };
  const norm = s => String(s || '').toLowerCase().replace(/[ʻʼ’`‘]/g, "'");
  async function loadProducts() {
    if (products) return products;
    try {
      const list = typeof fetchCatalogList === 'function' ? await fetchCatalogList('all')
        : await api('/api/products?page=0&per_page=200');
      products = (list && list.products) || [];
    } catch (_) { return []; }        // not kept: the next result asks again
    return products;
  }
  function findProduct(kw) {
    if (!kw || !products) return null;
    const keys = [norm(kw), norm(typeof latToCyr === 'function' ? latToCyr(kw) : kw), KW_RU[kw]].filter(Boolean);
    const hits = products.filter(p => !p.is_set && keys.some(k => norm(p.name).includes(k)));
    // In stock first, then the smallest pack (the cheapest way to try it).
    hits.sort((a, b) => ((a.out_of_stock ? 1 : 0) - (b.out_of_stock ? 1 : 0)) || ((a.price || 0) - (b.price || 0)));
    return hits[0] || null;
  }
  function shopRowHtml(kw, label) {
    const p = findProduct(kw);
    if (!p) return '';
    const inStock = !p.out_of_stock && !p.held_out;
    return '<div class="g2-shop-row">' +
      '<button type="button" class="g2-shop-name" onclick="G2.openProduct(' + p.id + ')">' + E(label || p.name) + ' →</button>' +
      (inStock ? '<button type="button" class="g2-add" data-pid="' + p.id + '" onclick="G2.add(this)">' + E(T('+ Savatga', '+ В корзину')) + '</button>' : '') +
    '</div>';
  }
  G2.openProduct = id => { try { openDetail(id); } catch (_) {} };
  G2.add = btn => { try { quickAddToCart({ id: +btn.dataset.pid, is_set: false }, btn, 'game_' + (run ? run.id : '')); } catch (_) {} };
  G2.addAll = async btn => {
    btn.disabled = true;
    const ids = [...document.querySelectorAll('.g2-add[data-pid]')].map(b => +b.dataset.pid);
    let n = 0;
    for (const id of [...new Set(ids)]) {
      try { await api('/api/cart/add', { method: 'POST', body: JSON.stringify({ product_id: id, quantity: 1 }) }); n++; } catch (_) {}
    }
    try { await loadCart(); } catch (_) {}
    try { trk(() => Trk.ev('cart_add', 'game_all', run ? run.id : '', String(n))); } catch (_) {}
    showToast(T(n + ' ta mahsulot savatga qo\'shildi', 'Добавлено в корзину: ' + n));
    btn.textContent = T('✓ Savatda', '✓ В корзине');
  };
  function shopRowsHtml(kws, title) {
    const rows = [...new Set(kws.filter(Boolean))].map(k => shopRowHtml(k)).filter(Boolean);
    if (!rows.length) return '';
    return '<div class="g2-shop"><div class="g2-shop-title">' + E(title) + '</div>' + rows.join('') +
      (rows.length > 1 ? '<button type="button" class="game-next g2-all" onclick="G2.addAll(this)">🛒 ' + E(T('Hammasini savatga', 'Всё в корзину')) + '</button>' : '') + '</div>';
  }
  // The result shows at once (2026-11-18: the right answer looked dead while
  // the product list loaded); the products slide in when they are there.
  let shopSeq = 0;
  function shopBlockHtml(kws, title) {
    if (products) return shopRowsHtml(kws, title);
    const id = 'g2-shop-' + (++shopSeq);
    loadProducts().then(() => {
      const el = document.getElementById(id);
      if (el) el.outerHTML = shopRowsHtml(kws, title);
    });
    return '<div id="' + id + '"></div>';
  }

  // ── share ──────────────────────────────────────────────────────────
  const shares = [];
  G2.share = function (k) {
    const text = shares[k] || '';
    const url = (state && state.share_url) || 'https://t.me/ketoshopbot/shop?startapp=oyin';
    const link = 'https://t.me/share/url?url=' + encodeURIComponent(url) + '&text=' + encodeURIComponent(text);
    try { trk(() => Trk.ev('game', 'share', run ? run.id : '')); } catch (_) {}
    try { tg.openTelegramLink(link); } catch (_) { window.open(link, '_blank'); }
  };
  const shareBtn = text => '<button type="button" class="game-other" onclick="G2.share(' + (shares.push(text) - 1) + ')">📤 ' + E(T("Do'stga yuborish", 'Отправить другу')) + '</button>';

  // ── shared result screen ───────────────────────────────────────────
  function resultHtml(id, big, msg, sub, extra, again) {
    return '<div class="game-result" id="game-result">' +
        '<div class="game-result-big">' + E(big) + '</div>' +
        '<div class="game-result-msg">' + E(msg) + '</div>' +
        (sub ? '<div class="game-result-sub">' + E(sub) + '</div>' : '') +
        '<div id="g2-reward" class="g2-reward"></div>' +
        '<div class="game-actions">' +
          (again === false ? '' : '<button type="button" class="game-again" onclick="openGame(\'' + id + '\')">' + E(T("Qayta o'ynash", 'Сыграть ещё')) + '</button>') +
          '<button type="button" class="game-other" onclick="renderGamesPage()">' + E(T("Boshqa o'yin", 'Другая игра')) + '</button>' +
        '</div>' +
      '</div>' + (extra || '');
  }
  function begin(id, data) {
    run = Object.assign({ id }, data || {});
    gameState = { id, g2: true };   // the page's own flag: other sheets wait while a game runs
    try { trk(() => Trk.open('game', id)); } catch (_) {}
  }
  function finished(id) {
    if (gameState && gameState.id === id) gameState.finished = true;
    try { trk(() => Trk.ev('game', 'game', id)); } catch (_) {}
  }
  const live = id => !!(run && run.id === id && gameState && gameState.id === id);

  // ═════════════ 1. «3 ta ishora» — the daily puzzle ═════════════
  function clueToday() {
    const list = C.clue || [];
    const seed = state ? state.clue_seed : Math.floor((Date.now() + 5 * 3600e3) / 864e5) + 719163;
    return list[(seed * 7 + 3) % list.length];
  }
  function startClue() {
    const item = clueToday();
    begin('clue', { item, shown: 1, tried: [], opts: shuffle([item.a].concat(item.wrong)), done: false });
    if (state && state.clue_solved) return clueDone(true);
    renderClue();
    if (!state) {
      api('/api/games/state').then(s => {
        state = s;
        if (!live('clue') || run.done || run.tried.length) return;
        if (s.clue_solved) { run.done = true; clueDone(true); } else renderClue();   // streak, social proof
      }).catch(() => {});
    }
  }
  function renderClue() {
    const r = run, it = r.item;
    const hints = it.hints.slice(0, r.shown).map((h, i) => '<div class="g2-hint"><b>' + (i + 1) + '</b><span>' + E(L(h)) + '</span></div>').join('');
    const social = state && state.solvers_today ? '<div class="g2-social">👥 ' + E(T('Bugun ' + state.solvers_today + ' kishi yechdi', 'Сегодня отгадали: ' + state.solvers_today)) + '</div>' : '';
    setGameScreen('clue', '🔥 ' + ((state && state.streak) || 0),
      '<div class="g2-lead">' + E(T('Men kimman? Har noto\'g\'ri javob yana bitta ishora ochadi. Kamroq ishora — ko\'proq Keto.', 'Кто я? Каждый неверный ответ открывает ещё одну подсказку. Меньше подсказок — больше Keto.')) + '</div>' +
      '<div class="g2-hints">' + hints + '</div>' +
      '<div class="quiz-opts" id="quiz-opts">' + r.opts.map((o, i) =>
        '<button type="button" class="quiz-opt' + (r.tried.includes(i) ? ' wrong' : '') + '" ' + (r.tried.includes(i) ? 'disabled' : '') + ' onclick="G2.answerClue(' + i + ')"><b>' + 'ABCD'[i] + '</b><span>' + E(L(o)) + '</span></button>').join('') + '</div>' +
      social + '<div id="game-reveal-slot"></div>');
  }
  G2.answerClue = function (i) {
    const r = run;
    if (!live('clue') || r.done) return;
    const ok = r.opts[i] === r.item.a;
    gameHaptic(ok);
    if (ok) {
      r.done = true; r.points = 4 - r.shown;
      document.querySelectorAll('#quiz-opts .quiz-opt').forEach((b, k) => { b.disabled = true; if (k === i) b.classList.add('right'); });
      return clueDone(false);
    }
    r.tried.push(i);
    if (r.shown < 3) { r.shown++; renderClue(); return; }
    r.done = true; r.points = 0; clueDone(false);
  };
  async function clueDone(already) {
    const r = run, it = r.item;
    finished('clue');
    let points = r.points;
    if (already) points = state && state.clue_hints ? 4 - state.clue_hints : 0;
    const big = points ? '⭐'.repeat(points) : '🙂';
    const msg = points === 3 ? T('Birinchi ishoradayoq! Daho!', 'С первой подсказки! Гениально!')
      : points === 2 ? T('Zo\'r! Ikki ishorada topdingiz', 'Отлично! Со второй подсказки')
      : points === 1 ? T('Topdingiz!', 'Отгадали!')
      : T('Bugun chiqmadi — ertaga yangi jumboq', 'Сегодня не вышло — завтра новая загадка');
    const answer = '<div class="g2-answer">' + E(T('Javob: ', 'Ответ: ')) + '<b>' + E(L(it.a)) + '</b></div>';
    const tomorrow = '<div class="g2-note">🌅 ' + E(T('Ertangi jumboq yarim tunda ochiladi. Ketma-ketlikni uzmang!', 'Завтрашняя загадка откроется в полночь. Не прерывайте серию!')) + '</div>';
    const shop = shopBlockHtml([it.kw], T("Bugungi qahramon do'konimizda", 'Сегодняшний герой — в нашем магазине'));
    const share = points ? '<div class="game-actions">' + shareBtn(T('Bugungi keto jumboqni ' + (4 - points) + ' ta ishorada topdim! Siz-chi? 🧩',
      'Я отгадал(а) кето-загадку дня с ' + (4 - points) + '-й подсказки! А вы? 🧩')) + '</div>' : '';
    setGameScreen('clue', '', resultHtml('clue', big, msg, '', answer + share + tomorrow + shop, false));
    if (already) { showReward({ paid: 0, notes: [], board: state && state.board, earning: false }); return; }
    if (points) launchConfetti(document.getElementById('game-result'));
    const res = await report('clue', { points });
    showReward(res);
  }

  // ═════════════ 2. «Almashtir!» ═════════════
  function startSwap() {
    const dishes = pick(C.swap || [], 3);
    const steps = [];
    dishes.forEach(d => d.steps.forEach(st => steps.push({ dish: d, st, order: shuffle([0, 1, 2]) })));
    begin('swap', { steps, i: 0, score: 0, marks: [], answered: false, kws: [] });
    renderSwap();
  }
  function renderSwap() {
    const r = run, cur = r.steps[r.i];
    setGameScreen('swap', r.score + '/' + r.steps.length,
      gameProgressHtml(r.marks, r.steps.length) +
      '<div class="g2-dish">' + cur.dish.icon + ' ' + E(L(cur.dish.dish)) + '</div>' +
      '<div class="quiz-q">' + E(T('Nima bilan almashtiramiz: ', 'Чем заменим: ')) + '<b>' + E(L(cur.st.from)) + '</b>?</div>' +
      '<div class="quiz-opts" id="quiz-opts">' + cur.order.map((oi, pos) =>
        '<button type="button" class="quiz-opt" data-pos="' + pos + '" onclick="G2.answerSwap(' + pos + ')"><b>' + 'ABC'[pos] + '</b><span>' + E(L(cur.st.opts[oi])) + '</span></button>').join('') + '</div>' +
      '<div id="game-reveal-slot"></div>');
  }
  G2.answerSwap = function (pos) {
    const r = run;
    if (!live('swap') || r.answered) return;
    r.answered = true;
    const cur = r.steps[r.i], ok = cur.order[pos] === 0;
    if (ok) { r.score++; r.kws.push(cur.st.kw); }
    r.marks.push(ok);
    gameHaptic(ok);
    document.querySelectorAll('#quiz-opts .quiz-opt').forEach(b => {
      b.disabled = true;
      const p = +b.dataset.pos;
      if (cur.order[p] === 0) b.classList.add('right'); else if (p === pos) b.classList.add('wrong');
    });
    document.getElementById('game-score').textContent = r.score + '/' + r.steps.length;
    showGameReveal(gameRevealHtml(ok, ok ? T("To'g'ri almashtirdingiz!", 'Верная замена!') : T('Boshqa variant yaxshiroq', 'Есть вариант лучше'),
      '<div class="game-fact">' + E(L(cur.st.why)) + '</div>', null, gameNextLabel(r.i === r.steps.length - 1), 'G2.nextSwap()'));
  };
  G2.nextSwap = async function () {
    const r = run;
    if (!live('swap')) return;
    if (r.i < r.steps.length - 1) { r.i++; r.answered = false; renderSwap(); return; }
    finished('swap');
    const great = r.score >= r.steps.length * 0.8;
    const all = r.steps.map(x => x.st.kw);
    const shop = shopBlockHtml(all, T('Keto masalliqlar — bir bosishda savatga', 'Кето-ингредиенты — в корзину в одно касание'));
    setGameScreen('swap', '', resultHtml('swap', r.score + '/' + r.steps.length,
      great ? T('Siz haqiqiy keto oshpazsiz!', 'Вы настоящий кето-повар!') : T("Yaxshi! Har bir almashtirish — sog'liq uchun qadam", 'Хорошо! Каждая замена — шаг к здоровью'),
      T('Retseptlar saytimizda: «Retseptlar» bo\'limi', 'Рецепты — на нашем сайте в разделе «Рецепты»'), shop));
    if (great) launchConfetti(document.getElementById('game-result'));
    showReward(await report('swap', { points: r.score, total: r.steps.length }));
  };

  // ═════════════ 3. «Yorliq detektivi» ═════════════
  function startLabel() {
    begin('label', { labels: pick(C.label || [], 5), i: 0, score: 0, marks: [], picked: new Set(), checked: false });
    renderLabel();
  }
  function renderLabel() {
    const r = run, lb = r.labels[r.i];
    setGameScreen('label', r.score + '/' + (r.labels.length * 3),
      gameProgressHtml(r.marks, r.labels.length) +
      '<div class="g2-lead">' + E(T("Tarkibdagi hamma shakarni bosing. Shakar yo'q bo'lsa — hech narsani bosmang.", 'Нажмите на весь сахар в составе. Если сахара нет — ничего не нажимайте.')) + '</div>' +
      '<div class="g2-label"><div class="g2-label-name">🏷 ' + E(L(lb.name)) + '</div>' +
        '<div class="g2-label-sub">' + E(T('Tarkibi:', 'Состав:')) + '</div>' +
        '<div class="g2-chips" id="g2-chips">' + lb.items.map((it, k) =>
          '<button type="button" class="g2-chip' + (r.picked.has(k) ? ' on' : '') + '" data-k="' + k + '" onclick="G2.toggleLabel(' + k + ')">' + E(gx(it[0], it[1])) + '</button>').join('') + '</div></div>' +
      '<div class="game-actions"><button type="button" class="game-next" id="g2-check" onclick="G2.checkLabel()">🔍 ' + E(T('Tekshirish', 'Проверить')) + '</button></div>' +
      '<div id="game-reveal-slot"></div>');
  }
  G2.toggleLabel = function (k) {
    const r = run;
    if (!live('label') || r.checked) return;
    r.picked.has(k) ? r.picked.delete(k) : r.picked.add(k);
    const el = document.querySelector('.g2-chip[data-k="' + k + '"]');
    if (el) el.classList.toggle('on', r.picked.has(k));
    try { tg.HapticFeedback.selectionChanged(); } catch (_) {}
  };
  G2.checkLabel = function () {
    const r = run;
    if (!live('label') || r.checked) return;
    r.checked = true;
    const lb = r.labels[r.i];
    const sugars = lb.items.map((it, k) => it[2] ? k : -1).filter(k => k >= 0);
    const hit = sugars.filter(k => r.picked.has(k)).length;
    const wrong = [...r.picked].filter(k => !lb.items[k][2]).length;
    let pts;
    if (!sugars.length) pts = wrong === 0 ? 3 : wrong === 1 ? 1 : 0;
    else if (hit === sugars.length && wrong === 0) pts = 3;
    else if (hit * 2 >= sugars.length && wrong <= 1) pts = 2;
    else pts = hit > 0 ? 1 : 0;
    r.score += pts;
    r.marks.push(pts >= 2);
    gameHaptic(pts >= 2);
    document.querySelectorAll('#g2-chips .g2-chip').forEach(b => {
      b.disabled = true;
      const k = +b.dataset.k;
      if (lb.items[k][2]) b.classList.add(r.picked.has(k) ? 'hit' : 'missed');
      else if (r.picked.has(k)) b.classList.add('false');
    });
    const btn = document.getElementById('g2-check');
    if (btn) btn.remove();
    document.getElementById('game-score').textContent = r.score + '/' + (r.labels.length * 3);
    const verdict = pts === 3 ? T('Detektiv darajasi! +3', 'Уровень детектива! +3') : pts === 2 ? T('Yaxshi! +2', 'Хорошо! +2') : pts === 1 ? T('Qisman +1', 'Частично +1') : T("Bu safar yashirindi", 'В этот раз спрятался');
    showGameReveal(gameRevealHtml(pts >= 2, verdict, '<div class="game-fact">' + E(L(lb.why)) + '</div>', null,
      gameNextLabel(r.i === r.labels.length - 1), 'G2.nextLabel()'));
  };
  G2.nextLabel = function () {
    const r = run;
    if (!live('label')) return;
    if (r.i < r.labels.length - 1) { r.i++; r.picked = new Set(); r.checked = false; renderLabel(); return; }
    finished('label');
    const total = r.labels.length * 3, great = r.score >= total * 0.8;
    setGameScreen('label', '', resultHtml('label', r.score + '/' + total,
      great ? T("Sizni yorliq aldab bo'lmaydi!", 'Вас этикеткой не обмануть!') : T("Endi do'konda tarkibni boshqacha o'qiysiz", 'Теперь вы будете читать состав по-другому'),
      T('Maslahat: tarkib kamayish tartibida yoziladi — birinchisi eng ko\'p.', 'Совет: состав пишут по убыванию — первое больше всего.'),
      '<div class="game-actions">' + shareBtn(T('Yorliq detektivida ' + r.score + '/' + total + ' oldim! Yashirin shakarni siz topa olasizmi? 🔍', 'В «Детективе этикеток» набрал(а) ' + r.score + '/' + total + '! А вы найдёте скрытый сахар? 🔍')) + '</div>'));
    if (great) launchConfetti(document.getElementById('game-result'));
    report('label', { points: r.score, total }).then(showReward);
  };

  // ═════════════ 4. «Afsona yoki haqiqat?» ═════════════
  function startMyth() {
    const items = pick(C.myth || [], 10);
    begin('myth', { items, i: 0, score: 0, marks: [], answered: false, golden: Math.floor(Math.random() * items.length) });
    renderMyth();
  }
  function renderMyth() {
    const r = run, m = r.items[r.i], gold = r.i === r.golden;
    setGameScreen('myth', r.score + '/' + r.items.length,
      gameProgressHtml(r.marks, r.items.length) +
      (gold ? '<div class="g2-gold">✨ ' + E(T('Oltin savol — ikki ochko!', 'Золотой вопрос — два очка!')) + '</div>' : '') +
      '<div class="quiz-q g2-statement">«' + E(gx(m[0], m[1])) + '»</div>' +
      '<div class="g2-two">' +
        '<button type="button" class="game-btn no" id="g2-myth-0" onclick="G2.answerMyth(0)">❌ ' + E(T('Afsona', 'Миф')) + '</button>' +
        '<button type="button" class="game-btn yes" id="g2-myth-1" onclick="G2.answerMyth(1)">✅ ' + E(T('Haqiqat', 'Правда')) + '</button>' +
      '</div><div id="game-reveal-slot"></div>');
  }
  G2.answerMyth = function (v) {
    const r = run;
    if (!live('myth') || r.answered) return;
    r.answered = true;
    const m = r.items[r.i], ok = (v === 1) === !!m[2];
    if (ok) r.score += r.i === r.golden ? 2 : 1;
    r.marks.push(ok);
    gameHaptic(ok);
    ['g2-myth-0', 'g2-myth-1'].forEach(id => { const b = document.getElementById(id); if (b) b.disabled = true; });
    document.getElementById('game-score').textContent = r.score + '/' + r.items.length;
    showGameReveal(gameRevealHtml(ok, (m[2] ? T('Haqiqat', 'Правда') : T('Afsona', 'Миф')) + (ok ? ' — ' + T("to'g'ri!", 'верно!') : ''),
      '<div class="game-fact">' + E(gx(m[3], m[4])) + '</div>', null, gameNextLabel(r.i === r.items.length - 1), 'G2.nextMyth()'));
  };
  G2.nextMyth = function () {
    const r = run;
    if (!live('myth')) return;
    if (r.i < r.items.length - 1) { r.i++; r.answered = false; renderMyth(); return; }
    finished('myth');
    const great = r.score >= 8;
    setGameScreen('myth', '', resultHtml('myth', r.score + '/' + r.items.length,
      great ? T('Afsonalar sizni aldolmaydi!', 'Мифы вас не обманут!') : T("Endi bilasiz — boshqalarga ham ayting", 'Теперь вы знаете — расскажите другим'),
      '', '<div class="game-actions">' + shareBtn(T('«Afsona yoki haqiqat»da ' + r.score + ' ochko! Keto haqidagi afsonalarni siz ajrata olasizmi?', 'В «Миф или правда» ' + r.score + ' очков! А вы отличите кето-мифы?')) + '</div>'));
    if (great) launchConfetti(document.getElementById('game-result'));
    report('myth', { points: r.score, total: r.items.length }).then(showReward);
  };

  // ═════════════ 5. «Keto yo'li: 30 kun» ═════════════
  const STATS = [['energiya', '⚡', ['Energiya', 'Энергия']], ['natija', '🎯', ['Natija', 'Результат']], ['kayfiyat', '😊', ['Kayfiyat', 'Настроение']]];
  function statBars(stats) {
    return '<div class="g2-stats">' + STATS.map(([k, ic, name]) => {
      const v = Math.max(0, Math.min(100, stats && stats[k] != null ? stats[k] : 50));
      return '<div class="g2-stat"><span>' + ic + ' ' + E(L(name)) + '</span><i><b style="width:' + v + '%"></b></i><em>' + v + '</em></div>';
    }).join('') + '</div>';
  }
  function startStory() {
    begin('story', {});
    if (state) { renderStoryHome(); return; }
    setGameScreen('story', '', '<div class="g2-lead">' + E(T('Yuklanmoqda…', 'Загрузка…')) + '</div>');
    api('/api/games/state').then(s => { state = s; }).catch(() => {})
      .then(() => { if (live('story')) renderStoryHome(); });
  }
  function renderStoryHome() {
    const ch = C.story || [], s = state ? state.story : { done: 0, open: 1, stats: {} };
    const done = s.done, open = s.open;
    const pct = Math.round(100 * done / ch.length);
    let next;
    if (done >= ch.length) next = '<div class="g2-note">👑 ' + E(T("Malika opa bilan 30 kunlik yo'lni bosib o'tdingiz! Bob tanlab, qayta o'qishingiz mumkin.", 'Вы прошли 30-дневный путь с Маликой-опой! Можно перечитать любую главу.')) + '</div>';
    else if (open > done) next = '<button type="button" class="game-next g2-big" onclick="G2.playChapter(' + open + ')">📖 ' + E(T(open + '-bob: ', 'Глава ' + open + ': ') + L(ch[open - 1].t)) + '</button>';
    else next = '<div class="g2-locked">🔒 ' + E(T('Ertaga: ' + (done + 1) + '-bob — «' + L(ch[done].t) + '»', 'Завтра: глава ' + (done + 1) + ' — «' + L(ch[done].t) + '»')) + '<small>' + E(T('Har kuni bitta bob ochiladi — qiziq joyida to\'xtaymiz 😉', 'Каждый день открывается одна глава — останавливаемся на самом интересном 😉')) + '</small></div>';
    const list = ch.slice(0, Math.max(done, 0)).map((c, i) => '<button type="button" class="g2-ch done" onclick="G2.playChapter(' + (i + 1) + ', true)">' + (i + 1) + '. ' + E(L(c.t)) + ' ✓</button>').reverse().join('');
    setGameScreen('story', done + '/' + ch.length,
      '<div class="g2-lead">' + E(T("Malika opa ketoni boshladi. Uning har bir kunini siz hal qilasiz: har tanlov energiya, natija va kayfiyatga ta'sir qiladi.", 'Малика-опа начала кето. Каждый её день решаете вы: выбор влияет на энергию, результат и настроение.')) + '</div>' +
      '<div class="g2-bar"><b style="width:' + pct + '%"></b></div>' + statBars(s.stats) + next +
      (list ? '<div class="g2-chs"><div class="g2-shop-title">' + E(T("O'qilgan boblar", 'Прочитанные главы')) + '</div>' + list + '</div>' : ''));
  }
  G2.playChapter = function (n, replay) {
    if (!live('story')) begin('story', {});
    const c = (C.story || [])[n - 1];
    if (!c) return;
    run.chapter = n; run.replay = !!replay; run.answered = false;
    setGameScreen('story', n + '/30',
      '<div class="g2-dish">📖 ' + E(T(n + '-bob · ', 'Глава ' + n + ' · ') + L(c.t)) + '</div>' +
      '<div class="g2-scene">' + E(L(c.s)) + '</div>' +
      '<div class="quiz-opts" id="quiz-opts">' + c.c.map((o, i) =>
        '<button type="button" class="quiz-opt" data-pos="' + i + '" onclick="G2.chooseStory(' + i + ')"><b>' + 'ABC'[i] + '</b><span>' + E(L(o[0])) + '</span></button>').join('') + '</div>' +
      '<div id="game-reveal-slot"></div>');
  };
  G2.chooseStory = async function (i) {
    const r = run;
    if (!live('story') || r.answered) return;
    r.answered = true;
    const n = r.chapter, c = C.story[n - 1], o = c.c[i], d = o[2] || {};
    const best = Math.max(...c.c.map(x => Object.values(x[2] || {}).reduce((a, b) => a + b, 0)));
    const mine = Object.values(d).reduce((a, b) => a + b, 0);
    gameHaptic(mine >= 0);
    document.querySelectorAll('#quiz-opts .quiz-opt').forEach(b => {
      b.disabled = true;
      if (+b.dataset.pos === i) b.classList.add(mine >= 0 ? 'right' : 'wrong');
    });
    const deltas = STATS.filter(([k]) => d[k]).map(([k, ic, name]) => '<span class="g2-delta ' + (d[k] > 0 ? 'up' : 'down') + '">' + ic + ' ' + E(L(name)) + ' ' + (d[k] > 0 ? '+' : '') + d[k] + '</span>').join('');
    const nextC = C.story[n];
    const teaser = nextC && !r.replay ? '<div class="g2-teaser">🔮 ' + E(T('Ertaga: «' + L(nextC.t) + '»', 'Завтра: «' + L(nextC.t) + '»')) + '</div>' : '';
    const tip = mine < best ? '<div class="g2-note">' + E(T("Maslahat: boshqa tanlov ko'proq foyda berardi — qayta o'qib ko'ring.", 'Совет: другой выбор дал бы больше — можно перечитать.')) + '</div>' : '';
    showGameReveal('<div class="game-reveal"><div class="game-fact">' + E(L(o[1])) + '</div><div class="g2-deltas">' + deltas + '</div>' + tip + teaser +
      '<div id="g2-reward" class="g2-reward"></div><div class="game-actions"><button type="button" class="game-next" onclick="G2.storyHome()">' + E(T("Yo'lga qaytish", 'Вернуться к пути')) + '</button></div></div>');
    if (!r.replay) {
      finished('story');
      const res = await report('story', { chapter: n, points: Math.max(0, 5 + mine), stats: d });
      showReward(res);
      if (res && res.paid) launchConfetti(document.querySelector('.game-reveal'));
    }
  };
  G2.storyHome = () => { if (gameState) gameState.finished = false; renderStoryHome(); };

  // ═════════════ 6. «Bozor sarguzashti» ═════════════
  function startBazaar() {
    begin('bazaar', {});
    const list = (C.bazaar || []).map((m, i) =>
      '<button type="button" class="g2-mission" onclick="G2.playMission(' + i + ')"><span class="g2-mi">' + m.icon + '</span><span>' + E(L(m.goal)) + '<small>' + E(T('5 rasta · 3 ta jon', '5 рядов · 3 жизни')) + '</small></span></button>').join('');
    setGameScreen('bazaar', '',
      '<div class="g2-lead">' + E(T("Bozorga keldingiz! Retseptni tanlang va rasta-rasta yurib to'g'ri masalliqlarni yig'ing. Tuzoqqa tushsangiz — jon ketadi.", 'Вы на базаре! Выберите рецепт и пройдите ряды, собирая правильные продукты. Попадёте в ловушку — потеряете жизнь.')) + '</div>' +
      '<div class="g2-missions">' + list + '</div>');
  }
  G2.playMission = function (i) {
    const m = C.bazaar[i];
    run = { id: 'bazaar', m, i: 0, hearts: 3, right: 0, basket: [], answered: false, orders: m.stalls.map(() => shuffle([0, 1, 2])) };
    renderStall();
  };
  function renderStall() {
    const r = run, st = r.m.stalls[r.i];
    setGameScreen('bazaar', '❤️'.repeat(r.hearts) + '🤍'.repeat(3 - r.hearts),
      '<div class="g2-dish">' + r.m.icon + ' ' + E(L(r.m.goal)) + ' · ' + (r.i + 1) + '/5</div>' +
      '<div class="g2-stall">🏪 ' + E(L(st.name)) + '</div>' +
      '<div class="g2-basket">🧺 ' + (r.basket.length ? r.basket.map(b => E(b)).join(' · ') : E(T("Savat bo'sh", 'Корзина пуста'))) + '</div>' +
      '<div class="quiz-opts" id="quiz-opts">' + r.orders[r.i].map((gi, pos) =>
        '<button type="button" class="quiz-opt" data-pos="' + pos + '" onclick="G2.pickGood(' + pos + ')"><b>' + 'ABC'[pos] + '</b><span>' + E(gx(st.goods[gi][0], st.goods[gi][1])) + '</span></button>').join('') + '</div>' +
      '<div id="game-reveal-slot"></div>');
  }
  G2.pickGood = function (pos) {
    const r = run;
    if (!r || r.id !== 'bazaar' || r.answered) return;
    r.answered = true;
    const st = r.m.stalls[r.i], gi = r.orders[r.i][pos], good = st.goods[gi], kind = good[2];
    let verdict, body = '';
    if (kind === 1) { r.right++; r.basket.push(gx(good[0], good[1])); verdict = T("Savatga! Aynan shu kerak edi", 'В корзину! Именно это нужно'); }
    else if (kind === -1) { r.hearts--; verdict = T('Tuzoq! −1 jon', 'Ловушка! −1 жизнь'); body = '<div class="game-fact">' + E(L(st.why)) + '</div>'; }
    else { verdict = T('Yomon emas, lekin bu retseptga kerak emas', 'Неплохо, но этому рецепту не нужно'); }
    gameHaptic(kind === 1);
    document.querySelectorAll('#quiz-opts .quiz-opt').forEach(b => {
      b.disabled = true;
      const g = st.goods[r.orders[r.i][+b.dataset.pos]];
      if (g[2] === 1) b.classList.add('right'); else if (+b.dataset.pos === pos) b.classList.add('wrong');
    });
    const last = r.i === r.m.stalls.length - 1 || r.hearts <= 0;
    showGameReveal(gameRevealHtml(kind === 1, verdict, body, null, last ? T('Natija', 'Итог') : T('Keyingi rasta →', 'Следующий ряд →'), 'G2.nextStall()'));
  };
  G2.nextStall = async function () {
    const r = run;
    if (!r || r.id !== 'bazaar') return;
    if (r.hearts > 0 && r.i < r.m.stalls.length - 1) { r.i++; r.answered = false; renderStall(); return; }
    finished('bazaar');
    const points = r.right * 10 + Math.max(0, r.hearts) * 3;
    const won = r.right >= 4 && r.hearts > 0;
    const kws = r.m.stalls.map(st => (st.goods.find(g => g[2] === 1) || [])[3]);
    const shop = shopBlockHtml(kws, T("Bu masalliqlar Keto shop'da bor", 'Эти продукты есть в Keto shop'));
    setGameScreen('bazaar', '', resultHtml('bazaar', r.right + '/5',
      won ? T(L(r.m.goal) + ' uchun savat tayyor! 🎉', 'Корзина для «' + L(r.m.goal) + '» готова! 🎉') : r.hearts <= 0 ? T('Joningiz tugadi — tuzoqlar ayyor edi', 'Жизни кончились — ловушки были хитрыми') : T("Yaxshi urinish! Yana bir bor yuring", 'Хорошая попытка! Пройдите ещё раз'),
      '🧺 ' + (r.basket.join(' · ') || '—'), shop));
    if (won) launchConfetti(document.getElementById('game-result'));
    showReward(await report('bazaar', { points, total: 59 }));
  };

  // ═════════════ 7. «Ketoland xaritasi» ═════════════
  function startMap() {
    begin('map', {});
    if (state) { renderMap(); return; }
    setGameScreen('map', '', '<div class="g2-lead">' + E(T('Yuklanmoqda…', 'Загрузка…')) + '</div>');
    api('/api/games/state').then(s => { state = s; }).catch(() => {})
      .then(() => { if (live('map')) renderMap(); });
  }
  function renderMap() {
    const st = C.map || [], m = state ? state.map : { done: 0, open: 1 };
    const nodes = st.map((s, i) => {
      const n = i + 1, done = n <= m.done, open = n === m.open && m.open > m.done;
      const cls = done ? 'done' : open ? 'open' : 'locked';
      const sub = done ? '✓' : open ? T('Ochiq — kiring', 'Открыта — входите') : n === m.done + 1 ? T('Ertaga ochiladi', 'Откроется завтра') : '🔒';
      return '<button type="button" class="g2-node ' + cls + '" ' + (open || done ? 'onclick="G2.playStation(' + n + ')"' : 'disabled') + '>' +
        '<span class="g2-node-ic">' + s.icon + '</span><span class="g2-node-t">' + n + '. ' + E(L(s.name)) + '<small>' + E(sub) + '</small></span></button>';
    }).join('<i class="g2-path"></i>');
    setGameScreen('map', m.done + '/' + st.length,
      '<div class="g2-lead">' + E(T("Ketoland bo'ylab sayohat: har bekatda 3 ta savol. 2 tasiga to'g'ri javob bersangiz, bekat sizniki. Kuniga bitta yangi bekat.", 'Путешествие по Кетоландии: на каждой станции 3 вопроса. Ответьте верно на 2 — станция ваша. Одна новая станция в день.')) + '</div>' +
      (m.done >= st.length ? '<div class="g2-note">👑 ' + E(T('Siz Ketoland fuqarosisiz!', 'Вы — гражданин Кетоландии!')) + '</div>' : '') +
      '<div class="g2-map">' + nodes + '</div>');
  }
  G2.playStation = function (n) {
    const s = (C.map || [])[n - 1];
    if (!s) return;
    if (!live('map')) begin('map', {});
    run.station = n; run.qs = s.qs.map(q => ({ q, order: shuffle([0, 1, 2, 3]) })); run.i = 0; run.score = 0; run.marks = []; run.answered = false;
    run.replay = state && n <= state.map.done;
    setGameScreen('map', s.icon,
      '<div class="g2-dish">' + s.icon + ' ' + E(L(s.name)) + '</div><div class="g2-scene">' + E(L(s.intro)) + '</div>' +
      '<div class="game-actions"><button type="button" class="game-next" onclick="G2.stationQ()">' + E(T('Boshladik!', 'Начнём!')) + '</button></div>');
  };
  G2.stationQ = function () {
    const r = run, cur = r.qs[r.i];
    setGameScreen('map', r.score + '/3',
      gameProgressHtml(r.marks, 3) + '<div class="quiz-q">' + E(L(cur.q[0])) + '</div>' +
      '<div class="quiz-opts" id="quiz-opts">' + cur.order.map((ai, pos) =>
        '<button type="button" class="quiz-opt" data-pos="' + pos + '" onclick="G2.answerStation(' + pos + ')"><b>' + 'ABCD'[pos] + '</b><span>' + E(L(cur.q[1][ai])) + '</span></button>').join('') + '</div>' +
      '<div id="game-reveal-slot"></div>');
  };
  G2.answerStation = function (pos) {
    const r = run;
    if (!live('map') || r.answered) return;
    r.answered = true;
    const cur = r.qs[r.i], ok = cur.order[pos] === 0;
    if (ok) r.score++;
    r.marks.push(ok);
    gameHaptic(ok);
    document.querySelectorAll('#quiz-opts .quiz-opt').forEach(b => {
      b.disabled = true;
      const p = +b.dataset.pos;
      if (cur.order[p] === 0) b.classList.add('right'); else if (p === pos) b.classList.add('wrong');
    });
    showGameReveal(gameRevealHtml(ok, ok ? T("To'g'ri!", 'Верно!') : T("Noto'g'ri", 'Неверно'), '<div class="game-fact">' + E(L(cur.q[2])) + '</div>', null,
      gameNextLabel(r.i === 2), 'G2.nextStation()'));
  };
  G2.nextStation = async function () {
    const r = run;
    if (!live('map')) return;
    if (r.i < 2) { r.i++; r.answered = false; G2.stationQ(); return; }
    finished('map');
    const passed = r.score >= 2, s = C.map[r.station - 1], next = C.map[r.station];
    const msg = passed ? T('«' + L(s.name) + '» bekati sizniki!', 'Станция «' + L(s.name) + '» ваша!') : T('Bu safar 2 ta to\'g\'ri javob kerak edi — yana urinib ko\'ring', 'Нужно 2 верных ответа — попробуйте ещё раз');
    const teaser = passed && next && !r.replay ? '<div class="g2-teaser">🔮 ' + E(T('Ertaga: «' + L(next.name) + '» ' + next.icon, 'Завтра: «' + L(next.name) + '» ' + next.icon)) + '</div>' : '';
    setGameScreen('map', '', resultHtml('map', r.score + '/3', msg, '', teaser +
      '<div class="game-actions"><button type="button" class="game-next" onclick="G2.mapHome()">🗺 ' + E(T('Xaritaga qaytish', 'К карте')) + '</button></div>', !passed));
    if (passed && !r.replay) {
      launchConfetti(document.getElementById('game-result'));
      showReward(await report('map', { station: r.station, points: r.score, total: 3 }));
    }
  };
  G2.mapHome = () => { if (gameState) gameState.finished = false; renderMap(); };

  G2.starters = { clue: startClue, swap: startSwap, label: startLabel, myth: startMyth, story: startStory, bazaar: startBazaar, map: startMap };

  // ── the games page's daily layer ───────────────────────────────────
  G2.dashHtml = function () {
    const s = state;
    if (!s) return '<div id="g2-dash" class="g2-dash g2-dash-wait"></div>';
    const t = s.tasks || {};
    const journey = s.story && s.story.done < 30
      ? { id: 'story', text: T("Keto yo'li — " + Math.min(30, s.story.done + 1) + '-bob', 'Путь кето — глава ' + Math.min(30, s.story.done + 1)) }
      : { id: 'map', text: T('Ketoland — yangi bekat', 'Кетоландия — новая станция') };
    const row = (done, ic, text, id) => '<button type="button" class="g2-task' + (done ? ' done' : '') + '" onclick="openGame(\'' + id + '\')"><span class="g2-check">' + (done ? '✓' : '') + '</span><span>' + ic + ' ' + E(text) + '</span><span class="g2-go">' + (done ? '' : '→') + '</span></button>';
    const other = ['swap', 'label', 'myth', 'bazaar'][new Date().getDay() % 4];
    const ring = Math.round(100 * (t.done || 0) / 3);
    const keto = s.earning ? '<span class="g2-pill">⭐ ' + E(T('Bugun: ' + s.keto_today + '/' + s.keto_cap + ' Keto', 'Сегодня: ' + s.keto_today + '/' + s.keto_cap + ' Keto')) + '</span>' : '';
    const streak = '<span class="g2-pill g2-fire">🔥 ' + E(T(s.streak + ' kun ketma-ket', s.streak + ' дн. подряд')) + '</span>' + (s.best_streak > s.streak ? '<span class="g2-pill">' + E(T('Rekord: ' + s.best_streak, 'Рекорд: ' + s.best_streak)) + '</span>' : '');
    const b = s.board || {};
    const top = (b.top || []).slice(0, 5).map(x => '<li class="' + (x.me ? 'me' : '') + '"><span>' + (x.rank <= 3 ? ['🥇', '🥈', '🥉'][x.rank - 1] : x.rank + '.') + '</span><b>' + E(x.name) + (x.me ? ' (' + T('siz', 'вы') + ')' : '') + '</b><em>' + x.points + '</em></li>').join('');
    const me = b.me && !(b.top || []).slice(0, 5).some(x => x.me) ? '<div class="g2-me">' + E(T('Siz: ' + b.me.rank + "-o'rin · " + b.me.points + ' ochko', 'Вы: ' + b.me.rank + '-е место · ' + b.me.points + ' очков')) + '</div>' : '';
    return '<div id="g2-dash" class="g2-dash">' +
      '<div class="g2-pills">' + streak + keto + '</div>' +
      '<div class="g2-card"><div class="g2-card-h"><div class="g2-ring" style="--p:' + ring + '"><span>' + (t.done || 0) + '/3</span></div><div><b>' + E(T('Bugungi topshiriqlar', 'Задания дня')) + '</b><small>' +
        E(t.bonus_paid ? T('Bajarildi — ertaga yangilari 🌅', 'Выполнено — завтра новые 🌅') : T('Uchalasini bajaring — bonus +10 Keto', 'Выполните все три — бонус +10 Keto')) + '</small></div></div>' +
        row(t.clue, '🧩', T('Kunlik jumboq', 'Загадка дня'), 'clue') +
        row(t.journey, journey.id === 'story' ? '📖' : '🗺', journey.text, journey.id) +
        row(t.game, '🎮', T('Yana bitta o\'yin', 'Ещё одна игра'), other) +
        (s.solvers_today ? '<div class="g2-social">👥 ' + E(T('Bugun ' + s.solvers_today + ' kishi jumboqni yechdi', 'Сегодня загадку отгадали: ' + s.solvers_today)) + '</div>' : '') +
      '</div>' +
      (top ? '<div class="g2-card"><b>🏆 ' + E(T('Haftaning eng zo\'rlari', 'Лучшие недели')) + '</b><ol class="g2-board">' + top + '</ol>' + me +
        '<small class="g2-board-note">' + E(T("Har o'yinning kunlik eng yaxshi natijasi sanaladi · dushanba yangilanadi", 'Считается лучший результат каждой игры за день · обновляется в понедельник')) + '</small></div>' : '') +
    '</div>';
  };

  // ── styles (light and dark come from the page's tokens) ────────────
  const css = `
  .g2-dash { padding: 0 14px 12px; display: grid; gap: 10px; }
  .g2-dash-wait { min-height: 8px; }
  .g2-pills { display: flex; flex-wrap: wrap; gap: 6px; }
  .g2-pill { padding: 6px 11px; border-radius: 999px; background: var(--surface); border: 1px solid var(--hairline); font: 700 12.5px var(--font-body); color: var(--text); }
  .g2-fire { background: var(--pop); color: var(--on-pop); border-color: transparent; }
  .g2-card { padding: 14px; border-radius: 22px 26px 20px 28px / 24px 20px 26px 22px; background: var(--surface); border: 1px solid var(--hairline); box-shadow: var(--shadow-1); display: grid; gap: 8px; }
  .g2-card > b { font: 800 15px var(--font-display); }
  .g2-card-h { display: flex; align-items: center; gap: 12px; }
  .g2-card-h b { display: block; font: 800 15px var(--font-display); }
  .g2-card-h small { color: var(--hint); font-size: 12.5px; }
  .g2-ring { --p: 0; flex-shrink: 0; width: 48px; height: 48px; border-radius: 50%; display: grid; place-items: center;
    background: conic-gradient(var(--leaf) calc(var(--p) * 1%), var(--surface-hi) 0); }
  .g2-ring span { width: 38px; height: 38px; border-radius: 50%; background: var(--surface); display: grid; place-items: center; font: 800 12.5px var(--font-display); }
  .g2-task { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 12px; border-radius: 14px; border: 1px solid var(--hairline); background: var(--bg); color: var(--text); font: 600 14px var(--font-body); text-align: left; cursor: pointer; }
  .g2-task span:nth-child(2) { flex: 1; min-width: 0; }
  .g2-task.done { opacity: .7; }
  .g2-task.done span:nth-child(2) { text-decoration: line-through; }
  .g2-check { width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--hairline); display: grid; place-items: center; font-size: 12px; font-weight: 800; color: #fff; flex-shrink: 0; }
  .g2-task.done .g2-check { background: var(--leaf); border-color: var(--leaf); }
  .g2-go { color: var(--hint); font-weight: 800; }
  .g2-social { color: var(--hint); font-size: 12.5px; text-align: center; padding-top: 2px; }
  .g2-board { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; }
  .g2-board li { display: flex; align-items: center; gap: 10px; padding: 6px 8px; border-radius: 10px; font-size: 14px; }
  .g2-board li.me { background: var(--leaf-soft); }
  .g2-board li span { width: 26px; text-align: center; font-weight: 800; }
  .g2-board li b { flex: 1; min-width: 0; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .g2-board li em { font-style: normal; font-weight: 800; }
  .g2-me { font-size: 13px; font-weight: 700; padding: 0 8px; }
  .g2-board-note { color: var(--hint); font-size: 11.5px; }
  .g2-lead { color: var(--hint); font-size: 13.5px; line-height: 1.5; margin-bottom: 12px; }
  .g2-hints { display: grid; gap: 8px; margin-bottom: 14px; }
  .g2-hint { display: flex; gap: 10px; align-items: flex-start; padding: 12px; border-radius: 16px; background: var(--surface); border: 1px solid var(--hairline); animation: popIn .4s var(--ease-spring); font-size: 14.5px; line-height: 1.45; }
  .g2-hint b { flex-shrink: 0; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: var(--pop); color: var(--on-pop); font: 800 13px var(--font-display); }
  .g2-answer { margin-top: 12px; text-align: center; font-size: 15px; }
  .g2-note { margin-top: 10px; padding: 10px 12px; border-radius: 14px; background: var(--leaf-soft); font-size: 13.5px; line-height: 1.45; }
  .g2-teaser { margin-top: 10px; padding: 10px 12px; border-radius: 14px; background: var(--surface-hi); font: 700 13.5px/1.45 var(--font-body); }
  .g2-reward { display: grid; gap: 6px; justify-items: center; margin-top: 12px; }
  .g2-keto { padding: 8px 16px; border-radius: 999px; background: var(--pop); color: var(--on-pop); font: 800 16px var(--font-display); animation: popIn .5s var(--ease-spring); }
  .g2-reward .g2-note { margin: 0; text-align: center; }
  .g2-dish { font: 800 16px var(--font-display); margin-bottom: 8px; }
  .g2-scene { font-size: 15px; line-height: 1.55; margin-bottom: 14px; }
  .g2-label { padding: 14px; border-radius: 18px; background: var(--surface); border: 1.5px dashed var(--hairline); margin-bottom: 12px; }
  .g2-label-name { font: 800 16px var(--font-display); }
  .g2-label-sub { margin: 8px 0 6px; color: var(--hint); font-size: 12.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
  .g2-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .g2-chip { padding: 8px 12px; border-radius: 999px; border: 1.5px solid var(--hairline); background: var(--bg); color: var(--text); font: 600 13.5px var(--font-body); cursor: pointer; }
  .g2-chip.on { border-color: var(--berry); background: var(--berry-soft); }
  .g2-chip.hit { border-color: var(--leaf); background: var(--leaf-soft); }
  .g2-chip.missed { border-color: var(--berry); background: var(--berry-soft); text-decoration: underline wavy; }
  .g2-chip.false { opacity: .55; text-decoration: line-through; }
  .g2-gold { margin-bottom: 10px; padding: 8px 12px; border-radius: 12px; background: var(--pop); color: var(--on-pop); font-weight: 800; text-align: center; animation: popIn .4s var(--ease-spring); }
  .g2-statement { font-size: 17px; line-height: 1.45; }
  .g2-two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
  .g2-two .game-btn { width: 100%; }
  .g2-bar { height: 10px; border-radius: 6px; background: var(--surface-hi); overflow: hidden; margin-bottom: 12px; }
  .g2-bar b { display: block; height: 100%; background: var(--leaf); border-radius: 6px; }
  .g2-stats { display: grid; gap: 6px; margin-bottom: 14px; }
  .g2-stat { display: grid; grid-template-columns: 110px 1fr 30px; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; }
  .g2-stat i { height: 8px; border-radius: 5px; background: var(--surface-hi); overflow: hidden; }
  .g2-stat i b { display: block; height: 100%; background: var(--pop); }
  .g2-stat em { font-style: normal; text-align: right; color: var(--hint); }
  .g2-big { width: 100%; }
  .g2-locked { padding: 14px; border-radius: 16px; background: var(--surface); border: 1px dashed var(--hairline); font-weight: 700; line-height: 1.45; }
  .g2-locked small { display: block; margin-top: 4px; color: var(--hint); font-weight: 600; }
  .g2-chs { display: grid; gap: 6px; margin-top: 16px; }
  .g2-ch { padding: 10px 12px; border-radius: 12px; border: 1px solid var(--hairline); background: var(--surface); color: var(--text); text-align: left; font: 600 13.5px var(--font-body); cursor: pointer; }
  .g2-deltas { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .g2-delta { padding: 4px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 800; }
  .g2-delta.up { background: var(--leaf-soft); color: var(--leaf-deep); }
  .g2-delta.down { background: var(--berry-soft); color: var(--berry); }
  .g2-missions { display: grid; gap: 8px; }
  .g2-mission { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 18px; border: 1px solid var(--hairline); background: var(--surface); color: var(--text); text-align: left; font: 700 15px var(--font-body); cursor: pointer; }
  .g2-mission small { display: block; color: var(--hint); font-size: 12px; font-weight: 600; }
  .g2-mi { font-size: 28px; }
  .g2-stall { font: 800 15px var(--font-display); margin: 4px 0 8px; }
  .g2-basket { padding: 8px 12px; border-radius: 12px; background: var(--surface-hi); font-size: 13px; margin-bottom: 12px; }
  .g2-map { display: grid; justify-items: center; }
  .g2-node { width: 100%; display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 18px; border: 1.5px solid var(--hairline); background: var(--surface); color: var(--text); text-align: left; font: 700 14.5px var(--font-body); cursor: pointer; }
  .g2-node small { display: block; color: var(--hint); font-size: 12px; font-weight: 600; }
  .g2-node-ic { font-size: 26px; }
  .g2-node.done { border-color: var(--leaf); background: var(--leaf-soft); }
  .g2-node.open { border-color: var(--pop); box-shadow: 0 0 0 4px var(--t-sun); animation: popIn .5s var(--ease-spring); }
  .g2-node.locked { opacity: .5; cursor: default; }
  .g2-path { width: 3px; height: 14px; background: var(--hairline); border-radius: 2px; }
  .g2-shop { margin-top: 14px; padding: 14px; border-radius: 18px; background: var(--surface); border: 1px solid var(--hairline); display: grid; gap: 8px; }
  .g2-shop-title { font: 800 14px var(--font-display); }
  .g2-shop-row { display: flex; align-items: center; gap: 8px; }
  .g2-shop-name { flex: 1; min-width: 0; padding: 8px 0; border: 0; background: none; color: var(--link, var(--text)); text-align: left; font: 600 14px var(--font-body); cursor: pointer; }
  .g2-add { flex-shrink: 0; padding: 8px 12px; border-radius: 999px; border: 0; background: var(--pop); color: var(--on-pop); font: 800 12.5px var(--font-body); cursor: pointer; }
  .g2-add.done { background: var(--leaf); color: #fff; }
  .g2-all { width: 100%; }
  @media (prefers-reduced-motion: reduce) { .g2-hint, .g2-keto, .g2-gold, .g2-node.open { animation: none; } }
  `;
  try {
    const el = document.createElement('style');
    el.id = 'g2-css';
    el.textContent = css;
    document.head.appendChild(el);
  } catch (_) {}
})();
