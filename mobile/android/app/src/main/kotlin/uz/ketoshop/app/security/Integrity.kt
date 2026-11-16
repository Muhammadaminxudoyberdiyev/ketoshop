package uz.ketoshop.app.security

import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import android.os.Debug
import java.io.File
import java.security.MessageDigest
import uz.ketoshop.app.BuildConfig

/**
 * What the app can tell about the phone it runs on. None of this is proof
 * (an attacker who controls the phone can lie to it) — it raises the cost of
 * casual tampering, and the server logs it with every login and refresh
 * (app_auth.py, APP_REQUIRE_CLEAN). The strong guarantees come from TLS
 * pinning and the Keystore-bound request signature.
 */
object Integrity {
    fun check(context: Context): Map<String, Any> = mapOf(
        "rooted" to rooted(),
        "hooked" to hooked(),
        "debugged" to debugged(context),
        "emulator" to emulator(),
        "tampered" to tampered(context),
        "deviceName" to deviceName(),
    )

    private val suPaths = listOf(
        "/system/bin/su", "/system/xbin/su", "/sbin/su", "/system/su", "/vendor/bin/su",
        "/su/bin/su", "/data/local/xbin/su", "/data/local/bin/su", "/data/adb/magisk",
        "/sbin/.magisk", "/system/app/Superuser.apk", "/data/adb/ksu", "/data/adb/ap",
    )

    private fun rooted(): Boolean =
        Build.TAGS?.contains("test-keys") == true || suPaths.any { runCatching { File(it).exists() }.getOrDefault(false) }

    /** Frida / Xposed / LSPosed / Substrate in this process, or Frida's port open. */
    private fun hooked(): Boolean {
        val libraries = listOf("frida", "xposed", "lsposed", "substrate", "zygisk")
        val maps = runCatching { File("/proc/self/maps").readText() }.getOrDefault("").lowercase()
        if (libraries.any { maps.contains(it) }) return true
        // Frida's agent runs its own threads inside the process.
        val threads = setOf("gum-js-loop", "gmain", "gdbus", "pool-frida")
        val threadNames = runCatching {
            File("/proc/self/task").listFiles()?.mapNotNull { runCatching { File(it, "comm").readText().trim() }.getOrNull() }
        }.getOrNull() ?: emptyList()
        if (threadNames.any { it in threads }) return true
        val xposed = runCatching { Class.forName("de.robv.android.xposed.XposedBridge"); true }.getOrDefault(false)
        if (xposed) return true
        // 27042/27043 = 0x69A2/0x69A3, frida-server's default ports, in LISTEN state (0A).
        return listOf("/proc/net/tcp", "/proc/net/tcp6").any { path ->
            runCatching { File(path).readLines() }.getOrDefault(emptyList()).any { line ->
                val cols = line.trim().split(Regex("\\s+"))
                cols.size > 3 && cols[3] == "0A" && (cols[1].endsWith(":69A2") || cols[1].endsWith(":69A3"))
            }
        }
    }

    private fun debugged(context: Context): Boolean {
        if (Debug.isDebuggerConnected() || Debug.waitingForDebugger()) return true
        val tracer = runCatching {
            File("/proc/self/status").readLines().firstOrNull { it.startsWith("TracerPid:") }
                ?.substringAfter(":")?.trim()?.toIntOrNull() ?: 0
        }.getOrDefault(0)
        if (tracer != 0) return true
        val debuggable = context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0
        return debuggable && !BuildConfig.DEBUG
    }

    private fun emulator(): Boolean {
        val f = Build.FINGERPRINT.lowercase()
        return f.startsWith("generic") || f.contains("emulator") || f.contains("sdk_gphone") ||
            Build.MODEL.contains("Emulator") || Build.MODEL.contains("Android SDK built for") ||
            Build.HARDWARE.contains("goldfish") || Build.HARDWARE.contains("ranchu") ||
            Build.PRODUCT.contains("sdk") && Build.BRAND.startsWith("generic")
    }

    /** Re-signed APK: the signing certificate is not the one this build expects. */
    private fun tampered(context: Context): Boolean {
        val expected = BuildConfig.SIGNING_CERT_SHA256.lowercase().replace(":", "")
        if (expected.isEmpty()) return false
        val certs: List<ByteArray> = runCatching {
            val pm = context.packageManager
            if (Build.VERSION.SDK_INT >= 28) {
                val info = pm.getPackageInfo(context.packageName, PackageManager.GET_SIGNING_CERTIFICATES).signingInfo
                val signers = if (info?.hasMultipleSigners() == true) info.apkContentsSigners else info?.signingCertificateHistory
                signers?.map { it.toByteArray() } ?: emptyList()
            } else {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(context.packageName, PackageManager.GET_SIGNATURES).signatures?.map { it.toByteArray() }
                    ?: emptyList()
            }
        }.getOrDefault(emptyList())
        if (certs.isEmpty()) return true
        val sha = MessageDigest.getInstance("SHA-256")
        return certs.none { cert -> sha.digest(cert).joinToString("") { "%02x".format(it) } == expected }
    }

    private fun deviceName(): String {
        val maker = Build.MANUFACTURER.replaceFirstChar { it.uppercase() }
        val model = Build.MODEL
        val name = if (model.startsWith(maker, ignoreCase = true)) model else "$maker $model"
        return name.take(60)
    }
}
