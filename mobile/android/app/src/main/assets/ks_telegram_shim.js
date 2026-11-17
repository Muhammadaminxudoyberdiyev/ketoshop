/*
 * Ketoshop Android app: the shop page (webapp/index.html) runs inside the
 * app's WebView instead of Telegram. The page loads
 * https://telegram.org/js/telegram-web-app.js; the app answers that request
 * with this file (ShopWebView.kt), so the page finds the window.Telegram.WebApp
 * it expects. Only the parts the page uses are here.
 *
 * initData was minted by the server for this app session (app_auth.py):
 * short-lived, revocable, accepted only by the shop's own /api/*.
 *
 * Talking to the app: window.prompt('__ks__', json). The app answers only
 * prompts coming from the shop's own origin (ShopWebView.kt onJsPrompt).
 */
(function () {
  'use strict';
  var initData = /*KS_INIT_DATA*/"";

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

  var pending = {};
  var seq = 0;
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

  var noop = function () {};
  var WebApp = {
    initData: initData,
    initDataUnsafe: { user: user, auth_date: Number(raw.auth_date) || 0, hash: raw.hash },
    version: '8.0',
    platform: 'android',
    colorScheme: 'light',
    themeParams: {},
    isExpanded: true,
    viewportHeight: window.innerHeight,
    viewportStableHeight: window.innerHeight,
    isVersionAtLeast: function (v) { return versionAtLeast('8.0', v); },
    ready: noop,
    expand: noop,
    onEvent: noop,
    offEvent: noop,
    sendData: noop,
    enableClosingConfirmation: noop,
    disableClosingConfirmation: noop,
    enableVerticalSwipes: noop,
    disableVerticalSwipes: noop,
    setHeaderColor: function (color) { send({ type: 'header_color', color: String(color) }); },
    setBackgroundColor: noop,
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
    /* Location from the phone itself (the app asks for the permission). */
    LocationManager: {
      isInited: true,
      isLocationAvailable: true,
      isAccessRequested: true,
      isAccessGranted: true,
      init: function (cb) { if (cb) setTimeout(cb, 0); },
      getLocation: function (cb) {
        var id = ++seq;
        pending[id] = cb;
        send({ type: 'location', id: id });
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
  window.addEventListener('resize', viewport);

  window.Telegram = {
    WebApp: WebApp,
    Utils: {},
    WebView: { initParams: {}, isIframe: false, postEvent: noop, receiveEvent: noop, onEvent: noop, offEvent: noop }
  };
  /* Lets the page show app-only items (the profile's «Ilova va xavfsizlik»). */
  window.KsApp = Object.freeze({
    native: true,
    openSettings: function () { send({ type: 'settings' }); }
  });
})();
