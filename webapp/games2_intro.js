/* 🎮 Har o'yinga qisqa tushuntirish va o'z muhiti (owner, 2026-11-18/21:
   "o'yinlarni vizual chiroyli va tasavvur uchun qulay muhit dizaynda qil",
   "o'yin haqida qisqacha tushuntirish ham berib ket").
   - The first time a game is opened: a «Qanday o'ynaladi» card — three short
     rules, the reward, «▶️ Boshlash». Later the «?» button in the game's top
     bar brings it back.
   - Every game plays on its own scene (CSS only, no images to load).
   Loaded after games2.js; index.html's openGame()/setGameScreen() call it. */
(function () {
  'use strict';
  const G2 = window.G2 = window.G2 || {};
  const E = s => escapeHtml(String(s == null ? '' : s));
  const KEY = 'ketoshop_game_intro_';

  // id → [icon, [rules uz], [rules ru], reward uz, reward ru]
  const INTRO = {
    clue: ['🧩',
      ["Har kuni hamma uchun bitta yangi jumboq: «Men kimman?»", "Har noto'g'ri javob yana bitta ishora ochadi — jami 3 ta",
       "Har kuni yechsangiz, 🔥 seriya o'sadi (haftada bitta kun kechiriladi)"],
      ['Каждый день одна новая загадка для всех: «Кто я?»', 'Каждый неверный ответ открывает ещё подсказку — всего 3',
       'Отгадываете каждый день — 🔥 серия растёт (один пропуск в неделю прощается)'],
      "1-ishorada — 15 Keto, 2-da — 10, 3-da — 5; seriya uchun bonus", 'С 1-й подсказки — 15 Keto, со 2-й — 10, с 3-й — 5; бонус за серию'],
    story: ['📖',
      ["Malika opa ketoni boshladi — uning 30 kunini siz hal qilasiz", "Har bobda 3 ta tanlov: energiya, natija va kayfiyatga ta'sir qiladi",
       "Har kuni bitta yangi bob ochiladi; o'qilganlarini qayta o'qish mumkin"],
      ['Малика-опа начала кето — её 30 дней решаете вы', 'В каждой главе 3 выбора: они влияют на энергию, результат и настроение',
       'Каждый день открывается новая глава; прочитанные можно перечитать'],
      "Har yangi bob — 5 Keto", 'Каждая новая глава — 5 Keto'],
    map: ['🗺',
      ["Ketoland bo'ylab 10 bekatli sayohat", "Har bekatda 3 ta savol — 2 tasiga to'g'ri javob bersangiz, bekat sizniki",
       "Kuniga bitta yangi bekat ochiladi"],
      ['Путешествие по Кетоландии — 10 станций', 'На каждой станции 3 вопроса — 2 верных ответа, и станция ваша',
       'Каждый день открывается одна новая станция'],
      "Har bekat — 10 Keto", 'Каждая станция — 10 Keto'],
    swap: ['🔁',
      ["Somsa, chak-chak, palov… taomdagi masalliq beriladi", "3 ta variantdan keto yoki PP o'rinbosarini tanlang",
       "Har javobdan keyin — nima uchun shunday ekani"],
      ['Даётся ингредиент блюда: самса, чак-чак, плов…', 'Выберите из 3 вариантов кето- или ПП-замену',
       'После каждого ответа — почему именно так'],
      "Yarmidan ko'pi to'g'ri — 5 Keto; oxirida masalliqlar bir bosishda savatga", 'Больше половины верно — 5 Keto; в конце — ингредиенты в корзину в одно касание'],
    label: ['🏷',
      ["Mahsulot tarkibi beriladi", "Undagi hamma yashirin shakarni bosing (shakar yo'q bo'lsa — hech narsani)",
       "«Tekshirish» — qaysi biri shakar ekani va nima uchun"],
      ['Даётся состав продукта', 'Нажмите на весь скрытый сахар (если сахара нет — ничего)',
       '«Проверить» — что из этого сахар и почему'],
      "Yarmidan ko'pi to'g'ri — 5 Keto", 'Больше половины верно — 5 Keto'],
    myth: ['⭐',
      ["Keto haqida 10 ta gap", "Har biri — afsonami yoki haqiqatmi, siz hal qilasiz",
       "Bittasi «oltin savol» — ikki ochko"],
      ['10 утверждений о кето', 'Решите, миф это или правда',
       'Один из них — «золотой вопрос», два очка'],
      "Yarmidan ko'pi to'g'ri — 5 Keto", 'Больше половины верно — 5 Keto'],
    bazaar: ['🧺',
      ["Retseptni tanlang va bozor rastalarini aylaning", "Har rastada retseptga keraklisini oling — tuzoq mahsulot jonni oladi",
       "3 ta jon, 5 ta rasta"],
      ['Выберите рецепт и пройдите ряды базара', 'В каждом ряду возьмите нужное — продукт-ловушка отнимает жизнь',
       '3 жизни, 5 рядов'],
      "Savat yig'ilsa — 8 Keto; masalliqlar bir bosishda savatga", 'Собрали корзину — 8 Keto; ингредиенты в корзину в одно касание'],
    keto: ['✅',
      ["10 ta mahsulot ketma-ket chiqadi", "Har biri keto uchun mosmi yoki yo'qmi — tez javob bering",
       "Har javobdan keyin 100 g dagi uglevod va qisqa izoh"],
      ['По очереди 10 продуктов', 'Быстро отвечайте: подходит для кето или нет',
       'После ответа — углеводы на 100 г и короткое пояснение'],
      "Yarmidan ko'pi to'g'ri — 5 Keto", 'Больше половины верно — 5 Keto'],
    duel: ['⚖️',
      ["Ikki mahsulot yonma-yon", "Qaysi birida uglevod kamroq — o'shani bosing",
       "Xato qilguncha davom etadi — seriyani uzmang"],
      ['Два продукта рядом', 'Нажмите тот, где углеводов меньше',
       'Игра идёт до первой ошибки — не прерывайте серию'],
      "Kunning birinchi o'yini — 5 Keto", 'Первая игра дня — 5 Keto'],
    quiz: ['❓',
      ["10 ta savol, har birida 4 ta javob", "To'g'risini tanlang", "Har savoldan keyin qisqa izoh — bilim qoladi"],
      ['10 вопросов, в каждом 4 ответа', 'Выберите верный', 'После каждого вопроса — короткое пояснение'],
      "Yarmidan ko'pi to'g'ri — 5 Keto", 'Больше половины верно — 5 Keto'],
    memory: ['🃏',
      ["Kartalar yopiq turadi", "Mahsulotni uning foydasi bilan juftlang", "Qancha kam urinish — shuncha yaxshi"],
      ['Карточки перевёрнуты', 'Соедините продукт с его пользой', 'Чем меньше попыток — тем лучше'],
      "Kunning birinchi o'yini — 5 Keto", 'Первая игра дня — 5 Keto'],
  };
  G2.INTRO = INTRO;

  function seen(id) { try { return localStorage.getItem(KEY + id) === '1'; } catch (_) { return true; } }
  function markSeen(id) { try { localStorage.setItem(KEY + id, '1'); } catch (_) {} }

  function cardHtml(id, withStart) {
    const it = INTRO[id];
    const rules = gx(it[1].join('\n'), it[2].join('\n')).split('\n');
    return '<div class="g2-intro g2-theme-card-' + id + '">' +
        '<div class="g2-intro-icon" aria-hidden="true">' + it[0] + '</div>' +
        '<div class="g2-intro-title">' + E(gameTitle(id)) + '</div>' +
        '<div class="g2-intro-sub">' + E(gx('Qanday o\'ynaladi', 'Как играть')) + '</div>' +
        '<ol class="g2-intro-rules">' + rules.map(r => '<li>' + E(r) + '</li>').join('') + '</ol>' +
        '<div class="g2-intro-reward">🪙 ' + E(gx(it[3], it[4])) + '</div>' +
        (withStart
          ? '<button type="button" class="game-next g2-intro-go" onclick="G2.go(\'' + id + '\')">▶️ ' + E(gx('Boshlash', 'Начать')) + '</button>' +
            '<div class="g2-intro-note">' + E(gx('Qoidalarni yana ko\'rish — o\'yin ichidagi «?» tugmasi', 'Посмотреть правила снова — кнопка «?» в игре')) + '</div>'
          : '') +
      '</div>';
  }

  // openGame() asks: show the intro first? true = shown, the game waits for «Boshlash».
  const waiting = {};
  G2.intro = function (id, start) {
    if (!INTRO[id] || seen(id)) return false;
    waiting[id] = start;
    setGameScreen(id, '', cardHtml(id, true));
    return true;
  };
  G2.go = function (id) {
    markSeen(id);
    const start = waiting[id];
    delete waiting[id];
    if (start) start();
    window.scrollTo(0, 0);
  };
  G2.help = function (id) {
    if (!INTRO[id]) return;
    let box = document.getElementById('g2-help');
    if (box) box.remove();
    box = document.createElement('div');
    box.id = 'g2-help';
    box.className = 'g2-help';
    box.setAttribute('role', 'dialog');
    box.innerHTML = '<div class="g2-help-card">' + cardHtml(id, false) +
      '<button type="button" class="game-next" onclick="document.getElementById(\'g2-help\').remove()">' + E(gx('Tushunarli', 'Понятно')) + '</button></div>';
    box.onclick = e => { if (e.target === box) box.remove(); };
    document.body.appendChild(box);
  };
  G2.hasHelp = id => !!INTRO[id];

  const css = `
  .game-help { flex-shrink: 0; width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--hairline);
    background: var(--surface); color: var(--text); font: 800 15px var(--font-display); cursor: pointer; }
  .g2-intro { text-align: center; padding: 22px 18px 18px; border-radius: 28px 34px 26px 36px / 32px 26px 34px 28px;
    background: var(--surface); border: 1px solid var(--hairline); box-shadow: var(--shadow-1); animation: popIn .45s var(--ease-spring); }
  .g2-intro-icon { width: 84px; height: 84px; margin: 0 auto 10px; border-radius: 50%; display: grid; place-items: center;
    font-size: 44px; background: var(--pop); box-shadow: 0 14px 28px -16px rgba(0,0,0,.45); }
  .g2-intro-title { font: 800 20px/1.2 var(--font-display); letter-spacing: -.02em; }
  .g2-intro-sub { margin-top: 4px; color: var(--hint); font-size: 12.5px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; }
  .g2-intro-rules { margin: 14px 0 0; padding: 0; list-style: none; counter-reset: r; text-align: left; display: grid; gap: 8px; }
  .g2-intro-rules li { counter-increment: r; display: flex; gap: 10px; align-items: flex-start; font-size: 14.5px; line-height: 1.45; }
  .g2-intro-rules li::before { content: counter(r); flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
    display: grid; place-items: center; background: var(--leaf-soft); color: var(--leaf-deep); font: 800 12.5px var(--font-display); }
  .g2-intro-reward { margin-top: 14px; padding: 10px 12px; border-radius: 14px; background: var(--surface-hi); font-size: 13.5px; font-weight: 700; }
  .g2-intro-go { width: 100%; margin-top: 16px; }
  .g2-intro-note { margin-top: 10px; color: var(--hint); font-size: 12px; }
  .g2-help { position: fixed; inset: 0; z-index: 10050; display: flex; align-items: flex-end; justify-content: center;
    padding: 16px; background: rgba(20,14,8,.45); }
  .g2-help-card { width: 100%; max-width: 460px; display: grid; gap: 10px; animation: popIn .35s var(--ease-spring); }

  /* ── Each game's scene (2026-11-21): soft, CSS-only, alpha colours so the
     night and organic themes keep them. ── */
  .game-shell.g2-scene { position: relative; margin: 6px 8px 0; border-radius: 30px; min-height: 70vh; }
  .game-shell.g2-scene > * { position: relative; }
  .g2-scene-clue {      /* a starry night of riddles */
    background:
      radial-gradient(circle at 12% 8%, rgba(255,214,120,.55) 1.4px, transparent 2.2px) 0 0 / 90px 90px,
      radial-gradient(circle at 60% 30%, rgba(255,214,120,.35) 1px, transparent 1.8px) 0 0 / 130px 110px,
      linear-gradient(170deg, rgba(70,60,140,.16), rgba(70,60,140,.03) 55%, transparent); }
  .g2-scene-story {     /* the pages of a diary */
    background:
      repeating-linear-gradient(180deg, transparent 0 33px, rgba(150,110,60,.09) 33px 34px),
      linear-gradient(90deg, rgba(200,80,80,.18) 0 2px, transparent 2px 100%) 34px 0 / 100% 100% no-repeat,
      linear-gradient(180deg, rgba(240,200,140,.16), transparent 70%); }
  .g2-scene-map {       /* sand, grass and a dotted trail */
    background:
      radial-gradient(circle, rgba(120,90,50,.22) 1.6px, transparent 2.2px) 0 0 / 22px 22px,
      radial-gradient(ellipse at 15% 85%, rgba(110,160,100,.2), transparent 45%),
      radial-gradient(ellipse at 90% 15%, rgba(110,160,100,.16), transparent 40%),
      linear-gradient(180deg, rgba(230,200,140,.18), rgba(230,200,140,.04)); }
  .g2-scene-swap {      /* kitchen tiles */
    background:
      conic-gradient(rgba(120,170,160,.10) 25%, transparent 0 50%, rgba(120,170,160,.10) 0 75%, transparent 0) 0 0 / 44px 44px,
      linear-gradient(180deg, rgba(255,255,255,.0), rgba(120,170,160,.06)); }
  .g2-scene-label {     /* a paper label under a magnifier */
    background:
      repeating-linear-gradient(135deg, rgba(150,120,80,.06) 0 10px, transparent 10px 20px),
      radial-gradient(circle at 85% 12%, rgba(120,160,220,.18), transparent 28%); }
  .g2-scene-myth {      /* lilac sparkle */
    background:
      radial-gradient(circle at 20% 20%, rgba(190,150,230,.22), transparent 35%),
      radial-gradient(circle at 80% 70%, rgba(250,200,120,.18), transparent 35%),
      radial-gradient(circle, rgba(190,150,230,.25) 1px, transparent 1.6px) 0 0 / 34px 34px; }
  .g2-scene-bazaar {    /* the market's striped awnings */
    background:
      linear-gradient(180deg, transparent 0 18px, rgba(240,200,120,.12) 18px, transparent 60%),
      repeating-linear-gradient(90deg, rgba(210,90,70,.5) 0 22px, rgba(255,250,240,.7) 22px 44px) 0 0 / 100% 16px no-repeat; }
  .g2-scene-bazaar { padding-top: 26px; }
  .g2-scene-keto { background: radial-gradient(circle at 85% 10%, rgba(110,160,100,.22), transparent 40%),
      linear-gradient(180deg, rgba(110,160,100,.08), transparent 60%); }
  .g2-scene-duel { background: linear-gradient(90deg, rgba(240,170,120,.12) 50%, rgba(120,170,220,.12) 50%); }
  .g2-scene-quiz { background: radial-gradient(circle at 15% 15%, rgba(230,150,160,.2), transparent 40%),
      radial-gradient(circle, rgba(230,150,160,.22) 1px, transparent 1.6px) 0 0 / 28px 28px; }
  .g2-scene-memory { background: radial-gradient(circle at 80% 20%, rgba(170,150,220,.22), transparent 40%),
      linear-gradient(180deg, rgba(170,150,220,.08), transparent 70%); }
  @media (prefers-reduced-motion: reduce) { .g2-intro, .g2-help-card { animation: none; } }
  `;
  try {
    const el = document.createElement('style');
    el.textContent = css;
    document.head.appendChild(el);
  } catch (_) {}
})();
