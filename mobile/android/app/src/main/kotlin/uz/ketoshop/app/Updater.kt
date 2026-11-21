package uz.ketoshop.app

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * «Yangilash» inside the app (owner, 2026-11-21): the new APK comes from our
 * own server (app_release.py), its SHA-256 must match what /app/v1/config
 * announced, and Android's own installer takes it from there — it refuses
 * any APK not signed with our key. The buyer allows "install from this app"
 * once and taps «O'rnatish» each time; Android allows nothing quieter
 * outside Play.
 */
class Updater(private val activity: Activity) {
    private var waitingFile: File? = null

    /** Runs off the main thread. progress(0..100); result: "installing",
     *  "need_permission" (settings opened, install continues on return),
     *  "bad_hash", "bad_url" or "error". */
    fun downloadAndInstall(url: String, sha256: String, progress: (Int) -> Unit): String {
        val uri = runCatching { Uri.parse(url) }.getOrNull()
        if (!Ks.isOurs(uri) || !Regex("^[0-9a-f]{64}$").matches(sha256)) return "bad_url"
        val dir = File(activity.cacheDir, "updates").apply { mkdirs() }
        dir.listFiles()?.forEach { it.delete() }
        val file = File(dir, "ketoshop-update.apk")
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15000
        conn.readTimeout = 30000
        conn.instanceFollowRedirects = false
        try {
            if (conn.responseCode != 200) return "error"
            val total = conn.contentLengthLong.takeIf { it > 0 } ?: -1L
            val digest = MessageDigest.getInstance("SHA-256")
            var done = 0L
            var lastPct = -1
            conn.inputStream.use { input ->
                file.outputStream().use { out ->
                    val buf = ByteArray(64 * 1024)
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        digest.update(buf, 0, n)
                        done += n
                        if (done > 200L * 1024 * 1024) return "error"
                        if (total > 0) {
                            val pct = (done * 100 / total).toInt()
                            if (pct != lastPct) { lastPct = pct; progress(pct) }
                        }
                    }
                }
            }
            val actual = digest.digest().joinToString("") { "%02x".format(it) }
            if (actual != sha256) {
                file.delete()
                return "bad_hash"
            }
        } catch (e: Exception) {
            file.delete()
            return "error"
        } finally {
            conn.disconnect()
        }
        return install(file)
    }

    fun install(file: File): String {
        if (Build.VERSION.SDK_INT >= 26 && !activity.packageManager.canRequestPackageInstalls()) {
            waitingFile = file
            activity.runOnUiThread {
                runCatching {
                    activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:${activity.packageName}")))
                }
            }
            return "need_permission"
        }
        val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.files", file)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.runOnUiThread { runCatching { activity.startActivity(intent) } }
        return "installing"
    }

    /** Back from the "install unknown apps" switch: carry on if it is on now. */
    fun onResume() {
        val file = waitingFile ?: return
        if (Build.VERSION.SDK_INT >= 26 && !activity.packageManager.canRequestPackageInstalls()) return
        waitingFile = null
        if (file.isFile) install(file)
    }
}
