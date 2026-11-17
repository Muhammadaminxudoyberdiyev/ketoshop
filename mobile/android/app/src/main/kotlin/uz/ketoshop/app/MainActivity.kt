package uz.ketoshop.app

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import android.webkit.ValueCallback
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executors
import uz.ketoshop.app.security.DeviceKey
import uz.ketoshop.app.security.Integrity
import uz.ketoshop.app.security.SecureBox

/**
 * The app's native side:
 *  - the "uz.ketoshop/secure" channel for Dart (Keystore key, encrypted box,
 *    integrity checks, FLAG_SECURE, opening links);
 *  - the shop WebView (ShopWebView.kt) and what it needs from the activity:
 *    location with its permission, the file picker for the cheque.
 * Keystore and disk work runs off the main thread (Flutter's UI runs on it).
 */
class MainActivity : FlutterActivity() {
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newFixedThreadPool(2)
    private val box by lazy { SecureBox(applicationContext) }
    private val locationFetcher by lazy { LocationFetcher(applicationContext) }

    private val permissionWaiters = mutableListOf<(Boolean) -> Unit>()
    private val locationWaiters = mutableListOf<(Location?) -> Unit>()
    private var webFileCallback: ValueCallback<Array<Uri>>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Until Dart says otherwise the window is secure (login shows a code).
        // Debug builds (never given to customers) stay screenshot-able for testing.
        if (!BuildConfig.DEBUG) window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        // Tapjacking: ignore touches while another app draws over this one.
        window.decorView.filterTouchesWhenObscured = true
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger
        MethodChannel(messenger, "uz.ketoshop/secure").setMethodCallHandler(::onCall)
        flutterEngine.platformViewsController.registry
            .registerViewFactory(ShopWebViewFactory.TYPE, ShopWebViewFactory(this, messenger))
    }

    private fun onCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "key.public" -> background(result) { DeviceKey.publicKey() }
            "key.sign" -> {
                val prefix = call.argument<String>("prefix")
                val body = call.argument<ByteArray>("body")
                if (prefix == null || body == null) return result.error("bad_args", null, null)
                background(result) { DeviceKey.sign(prefix, body) }
            }
            "key.reset" -> background(result) { DeviceKey.reset(); null }
            "box.put" -> {
                val name = call.argument<String>("key") ?: return result.error("bad_args", null, null)
                val value = call.argument<String>("value")
                background(result) { box.put(name, value); null }
            }
            "box.get" -> {
                val name = call.argument<String>("key") ?: return result.error("bad_args", null, null)
                background(result) { box.get(name) }
            }
            "box.clear" -> background(result) { box.clear(); null }
            "env.check" -> background(result) { Integrity.check(applicationContext) }
            "ui.secure" -> {
                if (call.argument<Boolean>("on") == true && !BuildConfig.DEBUG) window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
                else window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
                result.success(null)
            }
            "open.url" -> result.success(openExternal(call.argument<String>("url")))
            else -> result.notImplemented()
        }
    }

    private fun background(result: MethodChannel.Result, work: () -> Any?) {
        worker.execute {
            try {
                val value = work()
                main.post { result.success(value) }
            } catch (e: Exception) {
                // Never the message: it can carry key or file details.
                main.post { result.error("native_error", e.javaClass.simpleName, null) }
            }
        }
    }

    /** https:// and tg:// only — never intent:, file:, content:, javascript:. */
    fun openExternal(url: String?): Boolean {
        val uri = runCatching { Uri.parse(url ?: return false) }.getOrNull() ?: return false
        if (uri.scheme != "https" && uri.scheme != "tg") return false
        if (uri.scheme == "https" && uri.host.isNullOrEmpty()) return false
        val intent = Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE)
        return try {
            startActivity(intent)
            true
        } catch (e: ActivityNotFoundException) {
            false
        }
    }

    // ── location ──

    fun withLocationPermission(done: (Boolean) -> Unit) {
        val granted = listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            .any { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }
        if (granted) return done(true)
        permissionWaiters += done
        if (permissionWaiters.size == 1) {
            requestPermissions(
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
                REQUEST_LOCATION,
            )
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_LOCATION) return
        val granted = grantResults.any { it == PackageManager.PERMISSION_GRANTED }
        val waiters = permissionWaiters.toList()
        permissionWaiters.clear()
        waiters.forEach { it(granted) }
    }

    /** "ready" (permission + location on), "off" (location switched off) or
     *  "no_permission" — the shop page uses it to know a prompt will show. */
    fun locationState(): String {
        val granted = listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            .any { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }
        return when {
            !granted -> "no_permission"
            !locationFetcher.enabled() -> "off"
            else -> "ready"
        }
    }

    /** One position for the shop page, or null (it then offers the map).
     *  Asks for the permission, and to switch location on if it is off. */
    fun requestLocation(lang: String, done: (Location?) -> Unit) {
        withLocationPermission { granted ->
            when {
                !granted -> done(null)
                locationFetcher.enabled() -> fetchLocation(done)
                else -> askToEnableLocation(lang) { on -> if (on) fetchLocation(done) else done(null) }
            }
        }
    }

    private fun fetchLocation(done: (Location?) -> Unit) {
        locationWaiters += done
        if (locationWaiters.size > 1) return
        locationFetcher.current { fix ->
            val waiters = locationWaiters.toList()
            locationWaiters.clear()
            waiters.forEach { it(fix) }
        }
    }

    private var enableWaiter: ((Boolean) -> Unit)? = null

    /** Location is switched off: say so and open the system switch; the
     *  answer comes when the buyer is back (onResume). */
    private fun askToEnableLocation(lang: String, done: (Boolean) -> Unit) {
        val text = when (lang) {
            "ru" -> arrayOf("Геолокация выключена", "Включите геолокацию (GPS) на телефоне, чтобы определить адрес доставки.", "Включить", "Отмена")
            "uz_cyr" -> arrayOf("Жойлашув ўчирилган", "Етказиш манзилини аниқлаш учун телефонингизда жойлашувни (GPS) ёқинг.", "Ёқиш", "Бекор қилиш")
            else -> arrayOf("Joylashuv o'chirilgan", "Yetkazish manzilini aniqlash uchun telefoningizda joylashuvni (GPS) yoqing.", "Yoqish", "Bekor qilish")
        }
        var answered = false
        android.app.AlertDialog.Builder(this)
            .setTitle(text[0])
            .setMessage(text[1])
            .setPositiveButton(text[2]) { _, _ ->
                answered = true
                try {
                    enableWaiter = done
                    startActivity(Intent(android.provider.Settings.ACTION_LOCATION_SOURCE_SETTINGS))
                } catch (e: ActivityNotFoundException) {
                    enableWaiter = null
                    done(false)
                }
            }
            .setNegativeButton(text[3]) { _, _ -> answered = true; done(false) }
            .setOnDismissListener { if (!answered) done(false) }
            .show()
    }

    override fun onResume() {
        super.onResume()
        val waiter = enableWaiter ?: return
        enableWaiter = null
        waiter(locationFetcher.enabled())
    }

    // ── the cheque photo / PDF for the shop page ──

    fun pickFileForWeb(callback: ValueCallback<Array<Uri>>, acceptTypes: Array<String>?): Boolean {
        webFileCallback?.onReceiveValue(null)
        webFileCallback = callback
        val types = acceptTypes?.filter { it.isNotBlank() }?.flatMap { it.split(",") }?.map { it.trim() }
            ?.filter { it.startsWith("image/") || it == "application/pdf" }
            .orEmpty().ifEmpty { listOf("image/*", "application/pdf") }
        val intent = Intent(Intent.ACTION_GET_CONTENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType("*/*")
            .putExtra(Intent.EXTRA_MIME_TYPES, types.toTypedArray())
        return try {
            @Suppress("DEPRECATION")
            startActivityForResult(intent, REQUEST_WEB_FILE)
            true
        } catch (e: ActivityNotFoundException) {
            webFileCallback = null
            false
        }
    }

    fun forgetWebFileCallback() {
        webFileCallback?.onReceiveValue(null)
        webFileCallback = null
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_WEB_FILE) return
        val callback = webFileCallback ?: return
        webFileCallback = null
        val uri = data?.data
        callback.onReceiveValue(if (resultCode == RESULT_OK && uri != null) arrayOf(uri) else null)
    }

    override fun onDestroy() {
        worker.shutdown()
        super.onDestroy()
    }

    private companion object {
        const val REQUEST_LOCATION = 41
        const val REQUEST_WEB_FILE = 43
    }
}
