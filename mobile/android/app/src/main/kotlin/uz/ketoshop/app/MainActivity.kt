package uz.ketoshop.app

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executors
import uz.ketoshop.app.security.DeviceKey
import uz.ketoshop.app.security.Integrity
import uz.ketoshop.app.security.SecureBox

/**
 * The single native door for the Dart side ("uz.ketoshop/secure"). Keystore,
 * disk and file work runs off the main thread (in Flutter the UI runs on
 * it); every answer is posted back on the main thread.
 */
class MainActivity : FlutterActivity() {
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newFixedThreadPool(2)
    private val box by lazy { SecureBox(applicationContext) }
    private val location by lazy { LocationFetcher(applicationContext) }
    private var pendingPick: MethodChannel.Result? = null
    private var pendingLocation: MethodChannel.Result? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Until Dart says otherwise the window is secure (login shows a code).
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        // Tapjacking: ignore touches while another app draws over this one.
        window.decorView.filterTouchesWhenObscured = true
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "uz.ketoshop/secure")
            .setMethodCallHandler(::onCall)
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
                if (call.argument<Boolean>("on") == true) window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
                else window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
                result.success(null)
            }
            "open.url" -> result.success(openUrl(call.argument<String>("url")))
            "fs.cacheDir" -> result.success(cacheDir.absolutePath)
            "location.current" -> currentLocation(result)
            "file.pickCheque" -> pickCheque(result)
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
    private fun openUrl(url: String?): Boolean {
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

    private fun currentLocation(result: MethodChannel.Result) {
        if (pendingLocation != null) return result.error("busy", null, null)
        if (!location.enabled()) return result.error("disabled", null, null)
        pendingLocation = result
        val granted = listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            .any { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }
        if (granted) fetchLocation()
        else requestPermissions(
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
            REQUEST_LOCATION,
        )
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_LOCATION) return
        if (grantResults.any { it == PackageManager.PERMISSION_GRANTED }) fetchLocation()
        else pendingLocation?.error("denied", null, null).also { pendingLocation = null }
    }

    private fun fetchLocation() {
        location.current { fix ->
            val result = pendingLocation ?: return@current
            pendingLocation = null
            if (fix == null) result.error("timeout", null, null)
            else result.success(mapOf("lat" to fix.latitude, "lng" to fix.longitude, "accuracy" to fix.accuracy.toDouble()))
        }
    }

    // ── cheque file ──

    private fun pickCheque(result: MethodChannel.Result) {
        if (pendingPick != null) return result.error("busy", null, null)
        pendingPick = result
        val intent = Intent(Intent.ACTION_GET_CONTENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType("*/*")
            .putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("image/*", "application/pdf"))
        try {
            @Suppress("DEPRECATION")
            startActivityForResult(intent, REQUEST_PICK)
        } catch (e: ActivityNotFoundException) {
            pendingPick = null
            result.error("no_picker", null, null)
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_PICK) return
        val result = pendingPick ?: return
        pendingPick = null
        val uri = data?.data
        if (resultCode != RESULT_OK || uri == null) return result.success(null)
        worker.execute {
            try {
                val picked = readCheque(uri)
                main.post { if (picked == null) result.error("too_large", null, null) else result.success(picked) }
            } catch (e: Exception) {
                main.post { result.error("bad_file", null, null) }
            }
        }
    }

    /** The file's bytes (≤10 MB), its real type from the first bytes, a safe name. */
    private fun readCheque(uri: Uri): Map<String, Any>? {
        val bytes = contentResolver.openInputStream(uri)?.use { input ->
            val out = java.io.ByteArrayOutputStream()
            val buf = ByteArray(64 * 1024)
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                out.write(buf, 0, n)
                if (out.size() > MAX_CHEQUE_BYTES) return null
            }
            out.toByteArray()
        } ?: throw IllegalStateException("unreadable")
        val mime = sniff(bytes) ?: throw IllegalArgumentException("not an image or pdf")
        val shown = contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
            if (it.moveToFirst()) it.getString(0) else null
        }
        val name = (shown ?: "chek").replace(Regex("[^A-Za-z0-9._-]"), "_").take(60)
        return mapOf("bytes" to bytes, "mime" to mime, "name" to name)
    }

    private fun sniff(b: ByteArray): String? {
        fun at(i: Int, vararg sig: Int) = b.size >= i + sig.size && sig.indices.all { (b[i + it].toInt() and 0xFF) == sig[it] }
        // An ISO-BMFF "ftyp" box is also how MP4 video starts: the brand decides.
        val brand = if (b.size >= 12) String(b, 8, 4, Charsets.US_ASCII) else ""
        return when {
            at(0, 0xFF, 0xD8, 0xFF) -> "image/jpeg"
            at(0, 0x89, 0x50, 0x4E, 0x47) -> "image/png"
            at(0, 0x52, 0x49, 0x46, 0x46) && at(8, 0x57, 0x45, 0x42, 0x50) -> "image/webp"
            at(4, 0x66, 0x74, 0x79, 0x70) && brand in setOf("heic", "heix", "heim", "heis", "mif1", "msf1") -> "image/heic"
            at(0, 0x25, 0x50, 0x44, 0x46) -> "application/pdf"
            else -> null
        }
    }

    override fun onDestroy() {
        worker.shutdown()
        super.onDestroy()
    }

    private companion object {
        const val REQUEST_LOCATION = 41
        const val REQUEST_PICK = 42
        const val MAX_CHEQUE_BYTES = 10 * 1024 * 1024
    }
}
