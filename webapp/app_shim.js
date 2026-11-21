/*
 * Ketoshop Android app ⇄ shop page bridge («Telegram.WebApp» for the app).
 *
 * The shop page (webapp/index.html) loads https://telegram.org/js/telegram-web-app.js.
 * Inside the Android app that request is answered with THIS file, served by
 * our server at /app/v1/shim.js — so the bridge changes without a new APK
 * (owner: "apkni yangilashga deyarli 99.99% zarurat bo'lmasin"). The APK
 * carries a copy only as a fallback for when the server can't be reached.
 *
 * The app puts window.__KS_BOOT before this file:
 *   { initData, native: <bridge version>, version, build, startParam, lang }
 *
 * Talking to the app: window.prompt('__ks__', json) → the app answers only
 * prompts coming from the shop's own origin (ShopWebView.kt onJsPrompt).
 * Native message types (bridge version 2): haptic, open, close, back_visible,
 * header_color, settings, location_state, location, location_settings,
 * share, copy, download, push_state, push_permission, app_info, reload.
 */
(function () {
  'use strict';
  var boot = window.__KS_BOOT || {};
  var initData = boot.initData || '';
  var NATIVE = Number(boot.native || 1);

  function parse(query) {
    var out = {};
    query.split('&').forEach(function (pair) {
      if (!pair) return;
      var i = pair.indexOf('=');
      if (i < 0) return;
      out[decodeURIComponent(pair.slice(0, i))] = decodeURIComponent(pair.slice(i + 1));
    });
    return out;
  }

  var raw = parse(initData);
  var user = {};
  try { user = JSON.parse(raw.user || '{}'); } catch (e) { user = {}; }

  function send(message) {
    try { return window.prompt('__ks__', JSON.stringify(message)); } catch (e) { return null; }
  }
  function has(minNative) { return NATIVE >= minNative; }

  var pending = {};
  var seq = 0;
  function call(message, cb) {
    var id = ++seq;
    pending[id] = cb || function () {};
    message.id = id;
    send(message);
  }
  window.__ksResolve = function (id, value) {
    var cb = pending[id];
    delete pending[id];
    if (cb) { try { cb(value); } catch (e) { /* the page's own error */ } }
  };

  var backHandlers = [];
  /* The app calls this on the Android back key while the page shows its back button. */
  window.__ksBack = function () {
    if (!WebApp.BackButton.isVisible || !backHandlers.length) return false;
    backHandlers.slice().forEach(function (h) { try { h(); } catch (e) { /* page error */ } });
    return true;
  };

  var events = {};
  function emit(name, data) {
    (events[name] || []).slice().forEach(function (h) { try { h(data); } catch (e) { /* page error */ } });
  }
  /* The app calls this, e.g. when a push is tapped while the shop is open. */
  window.__ksEvent = function (name, data) { emit(name, data); };

  function versionAtLeast(have, want) {
    var a = String(have).split('.'), b = String(want).split('.');
    for (var i = 0; i < Math.max(a.length, b.length); i++) {
      var x = parseInt(a[i] || '0', 10), y = parseInt(b[i] || '0', 10);
      if (x !== y) return x > y;
    }
    return true;
  }

  function haptic(kind) {
    return function (style) { send({ type: 'haptic', kind: kind, style: String(style || '') }); };
  }
  function pageLang() {
    /* global `lang` is the shop page's own language setting */
    return typeof lang === 'string' ? lang : (boot.lang || 'uz');
  }

  var noop = function () {};
  var WebApp = {
    initData: initData,
    initDataUnsafe: {
      user: user,
      auth_date: Number(raw.auth_date) || 0,
      hash: raw.hash,
      start_param: boot.startParam || undefined
    },
    version: '8.0',
    platform: 'android',
    colorScheme: 'light',
    themeParams: {},
    isExpanded: true,
    isFullscreen: false,
    viewportHeight: window.innerHeight,
    viewportStableHeight: window.innerHeight,
    safeAreaInset: { top: 0, bottom: 0, left: 0, right: 0 },
    contentSafeAreaInset: { top: 0, bottom: 0, left: 0, right: 0 },
    isVersionAtLeast: function (v) { return versionAtLeast('8.0', v); },
    ready: noop,
    expand: noop,
    requestFullscreen: noop,
    exitFullscreen: noop,
    lockOrientation: noop,
    unlockOrientation: noop,
    onEvent: function (name, cb) { (events[name] = events[name] || []).push(cb); },
    offEvent: function (name, cb) { events[name] = (events[name] || []).filter(function (h) { return h !== cb; }); },
    sendData: noop,
    switchInlineQuery: noop,
    enableClosingConfirmation: noop,
    disableClosingConfirmation: noop,
    enableVerticalSwipes: noop,
    disableVerticalSwipes: noop,
    setHeaderColor: function (color) { send({ type: 'header_color', color: String(color) }); },
    setBackgroundColor: noop,
    setBottomBarColor: noop,
    openLink: function (url) { send({ type: 'open', url: String(url) }); },
    openTelegramLink: function (url) { send({ type: 'open', url: String(url) }); },
    /* In Telegram this returns to the chat; the app opens the bot. */
    close: function () { send({ type: 'close' }); },
    showAlert: function (message, cb) { window.alert(message); if (cb) cb(); },
    showConfirm: function (message, cb) { var ok = window.confirm(message); if (cb) cb(ok); },
    showPopup: function (params, cb) {
      var ok = window.confirm((params && (params.title ? params.title + '\n' : '') + (params.message || '')) || '');
      var buttons = (params && params.buttons) || [];
      var pick = ok ? (buttons[0] && buttons[0].id) : (buttons[1] && buttons[1].id);
      if (cb) cb(pick || null);
    },
    /* The bot already writes to whoever logged in through it. */
    requestWriteAccess: function (cb) { if (cb) setTimeout(function () { cb(true); }, 0); },
    requestContact: function (cb) { if (cb) setTimeout(function () { cb(false); }, 0); },
    /* Android share sheet: text and/or a link. */
    shareMessage: function (msg, cb) { if (cb) setTimeout(function () { cb(false); }, 0); },
    shareToStory: noop,
    readTextFromClipboard: function (cb) { if (cb) setTimeout(function () { cb(null); }, 0); },
    downloadFile: function (params, cb) {
      if (has(2) && params && params.url) {
        call({ type: 'download', url: String(params.url), name: String(params.file_name || '') },
             function (ok) { if (cb) cb(!!ok); });
      } else if (cb) { cb(false); }
    },
    HapticFeedback: {
      impactOccurred: haptic('impact'),
      notificationOccurred: haptic('notification'),
      selectionChanged: function () { send({ type: 'haptic', kind: 'selection', style: '' }); }
    },
    BackButton: {
      isVisible: false,
      show: function () { this.isVisible = true; send({ type: 'back_visible', value: true }); },
      hide: function () { this.isVisible = false; send({ type: 'back_visible', value: false }); },
      onClick: function (cb) { if (backHandlers.indexOf(cb) < 0) backHandlers.push(cb); },
      offClick: function (cb) { backHandlers = backHandlers.filter(function (h) { return h !== cb; }); }
    },
    MainButton: {
      isVisible: false, text: '',
      show: noop, hide: noop, enable: noop, disable: noop, setText: noop, setParams: noop,
      onClick: noop, offClick: noop, showProgress: noop, hideProgress: noop
    },
    SecondaryButton: {
      isVisible: false, text: '',
      show: noop, hide: noop, enable: noop, disable: noop, setText: noop, setParams: noop,
      onClick: noop, offClick: noop, showProgress: noop, hideProgress: noop
    },
    SettingsButton: { isVisible: false, show: noop, hide: noop, onClick: noop, offClick: noop },
    /* Location from the phone itself. The app asks for the permission and,
       if location is switched off, to switch it on. isAccessGranted is live:
       false means a prompt will show, so the page waits longer. */
    LocationManager: {
      isInited: true,
      isLocationAvailable: true,
      isAccessRequested: true,
      get isAccessGranted() { return send({ type: 'location_state' }) === 'ready'; },
      init: function (cb) { if (cb) setTimeout(cb, 0); },
      getLocation: function (cb) {
        var id = ++seq;
        pending[id] = cb;
        send({ type: 'location', id: id, lang: pageLang() });
      },
      openSettings: function () { send({ type: 'location_settings' }); }
    }
  };

  function viewport() {
    var h = window.innerHeight + 'px';
    var s = document.documentElement.style;
    s.setProperty('--tg-viewport-height', h);
    s.setProperty('--tg-viewport-stable-height', h);
    s.setProperty('--tg-safe-area-inset-bottom', '0px');
    s.setProperty('--tg-content-safe-area-inset-bottom', '0px');
    WebApp.viewportHeight = window.innerHeight;
    WebApp.viewportStableHeight = window.innerHeight;
  }
  viewport();
  window.addEventListener('resize', function () { viewport(); emit('viewportChanged', { isStateStable: true }); });

  window.Telegram = {
    WebApp: WebApp,
    Utils: {},
    WebView: { initParams: {}, isIframe: false, postEvent: noop, receiveEvent: noop, onEvent: noop, offEvent: noop }
  };

  /* What only the app can do — the page uses these when `window.KsApp` exists. */
  window.KsApp = Object.freeze({
    native: NATIVE,
    version: boot.version || '',
    build: Number(boot.build || 0),
    openSettings: function () { send({ type: 'settings' }); },
    /* Android share sheet. */
    share: function (text, url) {
      if (!has(2)) return false;
      send({ type: 'share', text: String(text || ''), url: String(url || '') });
      return true;
    },
    copy: function (text) {
      if (!has(2)) return false;
      send({ type: 'copy', text: String(text || '') });
      return true;
    },
    /* A file from our site (a receipt, a price list) into the phone's Downloads. */
    download: function (url, name, cb) {
      if (!has(2)) { if (cb) cb(false); return; }
      call({ type: 'download', url: String(url), name: String(name || '') }, function (ok) { if (cb) cb(!!ok); });
    },
    /* Notifications: 'on' | 'off' | 'ask' (Android 13+ has not asked yet). */
    pushState: function () { return has(2) ? (send({ type: 'push_state' }) || 'off') : 'off'; },
    askPush: function (cb) {
      if (!has(2)) { if (cb) cb('off'); return; }
      call({ type: 'push_permission' }, function (state) { if (cb) cb(state); });
    },
    reload: function () { send({ type: 'reload' }); },
    on: function (name, cb) { WebApp.onEvent(name, cb); }
  });
})();
