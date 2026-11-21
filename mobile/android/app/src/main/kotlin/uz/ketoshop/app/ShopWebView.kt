package uz.ketoshop.app

import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.net.http.SslError
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.view.HapticFeedbackConstants
import android.view.View
import android.webkit.CookieManager
import android.webkit.GeolocationPermissions
import android.webkit.JsPromptResult
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.StandardMessageCodec
import io.flutter.plugin.platform.PlatformView
import io.flutter.plugin.platform.PlatformViewFactory
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Flutter side: AndroidView(viewType: ShopWebViewFactory.TYPE). */
class ShopWebViewFactory(
    private val activity: MainActivity,
    private val messenger: BinaryMessenger,
) : PlatformViewFactory(StandardMessageCodec.INSTANCE) {
    override fun create(context: Context, viewId: Int, args: Any?): PlatformView {
        val p = args as? Map<*, *> ?: emptyMap<Any, Any>()
        return ShopWebView(
            activity, messenger, viewId,
            url = p["url"] as? String ?: "",
            host = p["host"] as? String ?: Ks.HOST,
            bot = p["bot"] as? String ?: "",
            initData = p["initData"] as? String ?: "",
            shimPath = Ks.cleanPath(p["shimPath"] as? String) ?: "/app/v1/shim.js",
            appVersion = p["appVersion"] as? String ?: "",
            appBuild = (p["appBuild"] as? Int) ?: 0,
        )
    }

    companion object {
        const val TYPE = "uz.ketoshop/webview"
    }
}

/**
 * The shop — the Mini App page itself — inside the app.
 *
 * The page asks for Telegram's script; it gets window.__KS_BOOT (this
 * session's initData, the bridge version) followed by the bridge
 * webapp/app_shim.js, fetched from our server so it changes without an APK
 * (the copy in assets is the fallback). The native side below offers fixed,
 * general abilities; which ones the shop uses is the server's choice.
 *
 * Guard rails: only https://<host> is shown, other links open outside;
 * prompt('__ks__') is answered only for our origin; no file://, no mixed
 * content, no third-party cookies, Safe Browsing on, TLS errors never bypassed.
 */
@SuppressLint("SetJavaScriptEnabled")
class ShopWebView(
    private val activity: MainActivity,
    messenger: BinaryMessenger,
    viewId: Int,
    url: String,
    private val host: String,
    private val bot: String,
    @Volatile private var initData: String,
    private val shimPath: String,
    private val appVersion: String,
    private val appBuild: Int,
) : PlatformView {
    private val webView = WebView(activity)
    private val channel = MethodChannel(messenger, "uz.ketoshop/webview_$viewId")
    private val bundledShim: String by lazy {
        activity.assets.open("ks_telegram_shim.js").bufferedReader().use { it.readText() }
    }
    private val shimCache = File(activity.filesDir, "app_shim.js")

    init {
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            mediaPlaybackRequiresUserGesture = true
            setGeolocationEnabled(true)
            if (Build.VERSION.SDK_INT >= 26) safeBrowsingEnabled = true
            userAgentString = "$userAgentString KetoshopApp/${BuildConfig.VERSION_NAME}"
        }
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false)
        webView.webViewClient = Client()
        webView.webChromeClient = Chrome()
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "back" -> back { handled -> result.success(handled) }
                "reload" -> {
                    call.argument<String>("initData")?.let { initData = it }
                    webView.reload()
                    result.success(null)
                }
                "load" -> {
                    // A tapped push while the shop is open: go to its page.
                    val target = call.argument<String>("url")?.let { Uri.parse(it) }
                    if (Ks.isOurs(target) && target?.host == host) webView.loadUrl(target.toString())
                    result.success(null)
                }
                "event" -> {
                    val name = JSONObject.quote(call.argument<String>("name") ?: "")
                    val data = call.argument<String>("data") ?: "null"
                    webView.evaluateJavascript("window.__ksEvent && window.__ksEvent($name, $data)", null)
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        if (isOurs(Uri.parse(url))) webView.loadUrl(url)
    }

    override fun getView(): View = webView

    override fun dispose() {
        channel.setMethodCallHandler(null)
        activity.forgetWebFileCallback()
        webView.stopLoading()
        webView.destroy()
    }

    private fun isOurs(uri: Uri): Boolean = uri.scheme == "https" && uri.host == host

    /** Android back: the page's own back button first, then history. */
    private fun back(done: (Boolean) -> Unit) {
        webView.evaluateJavascript("(window.__ksBack && window.__ksBack()) === true") { value ->
            when {
                value == "true" -> done(true)
                webView.canGoBack() -> { webView.goBack(); done(true) }
                else -> done(false)
            }
        }
    }

    private fun event(name: String, value: Any? = null) {
        activity.runOnUiThread { channel.invokeMethod(name, value) }
    }

    private fun resolve(id: Int, jsonValue: String) {
        activity.runOnUiThread {
            webView.evaluateJavascript("window.__ksResolve && window.__ksResolve($id, $jsonValue)", null)
        }
    }

    /** The bridge script: from our server (cached), else the bundled copy. */
    private fun shim(): String {
        val fresh = runCatching {
            val conn = URL("https://$host$shimPath").openConnection() as HttpURLConnection
            conn.connectTimeout = 4000
            conn.readTimeout = 4000
            conn.instanceFollowRedirects = false
            try {
                if (conn.responseCode == 200) conn.inputStream.bufferedReader().use { it.readText() } else null
            } finally {
                conn.disconnect()
            }
        }.getOrNull()?.takeIf { it.contains("__KS_BOOT") && it.length < 512 * 1024 }
        if (fresh != null) {
            runCatching { shimCache.writeText(fresh) }
            return fresh
        }
        return runCatching { shimCache.readText() }.getOrNull()?.takeIf { it.contains("__KS_BOOT") } ?: bundledShim
    }

    private fun boot(): String = JSONObject().apply {
        put("initData", initData)
        put("native", BuildConfig.BRIDGE_VERSION)
        put("version", appVersion)
        put("build", appBuild)
        put("platform", "android")
    }.toString()

    /** A message from the page (app_shim.js `send`). */
    private fun onBridge(json: String): String {
        val msg = runCatching { JSONObject(json) }.getOrNull() ?: return ""
        when (msg.optString("type")) {
            "haptic" -> webView.performHapticFeedback(
                if (msg.optString("kind") == "notification") HapticFeedbackConstants.LONG_PRESS
                else HapticFeedbackConstants.VIRTUAL_KEY,
            )
            "open" -> activity.openExternal(msg.optString("url"))
            "close" -> if (bot.isNotEmpty()) activity.openExternal("https://t.me/$bot")
            "back_visible" -> event("back_visible", msg.optBoolean("value"))
            "header_color" -> event("header_color", msg.optString("color"))
            "settings" -> event("settings")
            "reload" -> event("reload_session")
            "app_info" -> return JSONObject().apply {
                put("version", appVersion); put("build", appBuild); put("native", BuildConfig.BRIDGE_VERSION)
                put("android", Build.VERSION.SDK_INT)
            }.toString()
            "location_state" -> return activity.locationState()
            "location_settings" -> runCatching {
                activity.startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS))
            }
            "location" -> {
                val id = msg.optInt("id")
                activity.requestLocation(msg.optString("lang", "uz")) { fix ->
                    resolve(id, if (fix == null) "null" else JSONObject().apply {
                        put("latitude", fix.latitude)
                        put("longitude", fix.longitude)
                        put("horizontal_accuracy", fix.accuracy.toDouble())
                    }.toString())
                }
            }
            "share" -> {
                val text = listOf(msg.optString("text"), msg.optString("url"))
                    .filter { it.isNotBlank() }.joinToString("\n").take(4000)
                if (text.isNotEmpty()) runCatching {
                    activity.startActivity(Intent.createChooser(
                        Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text), null))
                }
            }
            "copy" -> runCatching {
                val cm = activity.getSystemService(ClipboardManager::class.java)
                cm?.setPrimaryClip(ClipData.newPlainText("Ketoshop", msg.optString("text").take(4000)))
            }
            "download" -> resolve(msg.optInt("id"), download(msg.optString("url"), msg.optString("name")).toString())
            "push_state" -> return activity.pushState()
            "push_permission" -> {
                val id = msg.optInt("id")
                activity.requestPushPermission { state -> resolve(id, JSONObject.quote(state)) }
            }
        }
        return ""
    }

    /** A file from our own site into the phone's Downloads (the session's
     *  initData goes along: the shop API needs it). */
    private fun download(url: String, name: String): Boolean {
        val uri = runCatching { Uri.parse(url) }.getOrNull() ?: return false
        if (!isOurs(uri)) return false
        val safeName = name.replace(Regex("[^A-Za-z0-9._ -]"), "_").take(80).ifBlank { "ketoshop-file" }
        return runCatching {
            val req = DownloadManager.Request(uri)
                .setTitle(safeName)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .addRequestHeader("Authorization", "tma $initData")
            if (Build.VERSION.SDK_INT >= 29) req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, safeName)
            activity.getSystemService(DownloadManager::class.java).enqueue(req)
            true
        }.getOrDefault(false)
    }

    private inner class Client : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            if (isOurs(request.url)) return false
            if (request.isForMainFrame) activity.openExternal(request.url.toString())
            return true
        }

        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
            val u = request.url
            if (u.scheme == "https" && u.host == "telegram.org" && u.path == "/js/telegram-web-app.js") {
                val js = "window.__KS_BOOT=${boot()};\n" + shim()
                return WebResourceResponse(
                    "application/javascript", "utf-8", 200, "OK",
                    mapOf("Cache-Control" to "no-store"), js.byteInputStream(),
                )
            }
            return null
        }

        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
            // Belt and braces: a page that is not ours never stays on screen.
            if (url != null && !isOurs(Uri.parse(url))) view.stopLoading()
            event("loading", true)
        }

        override fun onPageFinished(view: WebView, url: String?) = event("loading", false)

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame) event("error", error.errorCode)
        }

        @SuppressLint("WebViewClientOnReceivedSslError")
        override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
            handler.cancel()
            event("error", -11)
        }

        override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
            event("crashed")
            return true
        }
    }

    private inner class Chrome : WebChromeClient() {
        override fun onJsPrompt(
            view: WebView, url: String?, message: String?, defaultValue: String?, result: JsPromptResult,
        ): Boolean {
            if (message != "__ks__") return false
            if (url == null || !isOurs(Uri.parse(url))) {
                result.cancel()
                return true
            }
            result.confirm(onBridge(defaultValue ?: ""))
            return true
        }

        override fun onProgressChanged(view: WebView, newProgress: Int) = event("progress", newProgress)

        override fun onShowFileChooser(
            view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams,
        ): Boolean = activity.pickFileForWeb(callback, params.acceptTypes, params.isCaptureEnabled)

        override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
            if (!isOurs(Uri.parse(origin))) return callback.invoke(origin, false, false)
            activity.withLocationPermission { granted -> callback.invoke(origin, granted, false) }
        }
    }
}
