package uz.ketoshop.app

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.net.http.SslError
import android.os.Build
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

/** Flutter side: AndroidView(viewType: ShopWebViewFactory.TYPE). */
class ShopWebViewFactory(
    private val activity: MainActivity,
    private val messenger: BinaryMessenger,
) : PlatformViewFactory(StandardMessageCodec.INSTANCE) {
    override fun create(context: Context, viewId: Int, args: Any?): PlatformView {
        val params = args as? Map<*, *> ?: emptyMap<Any, Any>()
        return ShopWebView(
            activity, messenger, viewId,
            url = params["url"] as? String ?: "",
            host = params["host"] as? String ?: "",
            bot = params["bot"] as? String ?: "",
            initData = params["initData"] as? String ?: "",
        )
    }

    companion object {
        const val TYPE = "uz.ketoshop/webview"
    }
}

/**
 * The shop — the Mini App page itself — inside the app.
 *
 * Guard rails:
 *  - only https://<host> is ever shown; any other link opens outside;
 *  - the page's request for Telegram's script gets ks_telegram_shim.js with
 *    initData minted for this app session (short-lived, revocable);
 *  - the page talks to the app through prompt('__ks__'), answered only when
 *    it comes from https://<host>;
 *  - no file:// access, no mixed content, no third-party cookies, Safe
 *    Browsing on, TLS errors never bypassed.
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
) : PlatformView {
    private val webView = WebView(activity)
    private val channel = MethodChannel(messenger, "uz.ketoshop/webview_$viewId")
    private val shim: String by lazy {
        activity.assets.open("ks_telegram_shim.js").bufferedReader().use { it.readText() }
    }

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

    /** A message from the page (ks_telegram_shim.js `send`). */
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
            "location_settings" -> runCatching {
                activity.startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS))
            }
            "location" -> {
                val id = msg.optInt("id")
                activity.requestLocation { fix ->
                    val value = if (fix == null) "null" else JSONObject().apply {
                        put("latitude", fix.latitude)
                        put("longitude", fix.longitude)
                        put("horizontal_accuracy", fix.accuracy.toDouble())
                    }.toString()
                    webView.evaluateJavascript("window.__ksResolve && window.__ksResolve($id, $value)", null)
                }
            }
        }
        return ""
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
                val js = shim.replace("/*KS_INIT_DATA*/\"\"", JSONObject.quote(initData))
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
        ): Boolean = activity.pickFileForWeb(callback, params.acceptTypes)

        override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
            if (!isOurs(Uri.parse(origin))) return callback.invoke(origin, false, false)
            activity.withLocationPermission { granted -> callback.invoke(origin, granted, false) }
        }
    }
}
