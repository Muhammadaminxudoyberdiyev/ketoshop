package uz.ketoshop.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.net.HttpURLConnection
import java.net.URL

/** Build-wide constants shared by the native parts. */
object Ks {
    /** The shop's host (Dart: AppConfig.host). Images, updates and pages come only from here. */
    const val HOST = "keto.standart-eko.uz"

    fun isOurs(uri: Uri?): Boolean = uri != null && uri.scheme == "https" && uri.host == HOST

    /** A path on our site from a push or a link: "/", "/?product=12" — never "//other". */
    fun cleanPath(path: String?): String? {
        val p = path?.trim().orEmpty()
        if (p.isEmpty() || !p.startsWith("/") || p.startsWith("//") || p.any { it.isWhitespace() || it == '\\' }) return null
        return p
    }
}

/** Firebase hands every push here; the app renders it (PushNotifier). */
class PushService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        PushPrefs.saveToken(this, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        PushNotifier.show(this, message.data)
    }
}

object PushPrefs {
    private const val FILE = "ks_push"

    fun saveToken(ctx: Context, token: String) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putString("token", token).apply()
    }

    fun markAsked(ctx: Context) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putBoolean("asked", true).apply()
    }

    fun asked(ctx: Context): Boolean =
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).getBoolean("asked", false)

    /** Firebase is set up in this build and initialised. */
    fun available(ctx: Context): Boolean = BuildConfig.PUSH_CONFIGURED && runCatching {
        com.google.firebase.FirebaseApp.getInstance()
    }.isSuccess

    fun token(ctx: Context, done: (String?) -> Unit) {
        if (!available(ctx)) return done(null)
        runCatching {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                done(if (task.isSuccessful) task.result else null)
            }
        }.onFailure { done(null) }
    }

    fun deleteToken(ctx: Context) {
        if (available(ctx)) runCatching { FirebaseMessaging.getInstance().deleteToken() }
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().remove("token").apply()
    }
}

/**
 * Shows one server-made push. Nothing here knows a message type: the data
 * carries the title, text, picture, the phone's notification category
 * (channel id + its name in the buyer's language + importance) and the page
 * a tap opens — new kinds need only server code (push.py).
 */
object PushNotifier {
    const val EXTRA_URL = "ks_push_url"
    const val ACTION_OPEN = "uz.ketoshop.app.PUSH_OPEN"
    private val CHANNEL_RE = Regex("^[a-z0-9_]{1,40}$")
    private const val MAX_IMAGE = 3 * 1024 * 1024

    fun show(ctx: Context, data: Map<String, String>) {
        val title = data["title"].orEmpty().take(120)
        val body = data["body"].orEmpty().take(600)
        if (title.isBlank() && body.isBlank()) return
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        val channel = data["ch"]?.takeIf { CHANNEL_RE.matches(it) } ?: "yangilik"
        if (Build.VERSION.SDK_INT >= 26) {
            val importance = when (data["ch_imp"]) {
                "high" -> NotificationManager.IMPORTANCE_HIGH
                "low" -> NotificationManager.IMPORTANCE_LOW
                else -> NotificationManager.IMPORTANCE_DEFAULT
            }
            val name = data["ch_name"]?.takeIf { it.isNotBlank() }?.take(60) ?: "Ketoshop"
            val existing = nm.getNotificationChannel(channel)
            if (existing == null) {
                nm.createNotificationChannel(NotificationChannel(channel, name, importance))
            } else if (existing.name != name) {
                // Renaming keeps the buyer's own settings for the channel.
                nm.createNotificationChannel(NotificationChannel(channel, name, existing.importance))
            }
        }
        val id = (data["id"]?.toLongOrNull() ?: System.currentTimeMillis()).hashCode()
        val open = Intent(ctx, MainActivity::class.java).apply {
            action = ACTION_OPEN
            putExtra(EXTRA_URL, Ks.cleanPath(data["url"]) ?: "/")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = PendingIntent.getActivity(ctx, id, open,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

        @Suppress("DEPRECATION")
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(ctx, channel)
        else Notification.Builder(ctx).setPriority(
            if (data["ch_imp"] == "high") Notification.PRIORITY_HIGH else Notification.PRIORITY_DEFAULT)
        builder.setSmallIcon(R.drawable.ic_stat_ketoshop)
            .setColor(ctx.getColor(R.color.ks_brand))
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .setStyle(Notification.BigTextStyle().bigText(body))
        image(data["image"])?.let { bitmap ->
            builder.setLargeIcon(bitmap)
                .setStyle(Notification.BigPictureStyle().bigPicture(bitmap).setSummaryText(body))
        }
        runCatching { nm.notify("ks", id, builder.build()) }
    }

    /** A picture from our own host only, at most 3 MB, scaled for a notification. */
    private fun image(url: String?): Bitmap? {
        val uri = url?.let { runCatching { Uri.parse(it) }.getOrNull() } ?: return null
        if (!Ks.isOurs(uri)) return null
        return runCatching {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.connectTimeout = 6000
            conn.readTimeout = 8000
            conn.instanceFollowRedirects = false
            try {
                if (conn.responseCode != 200 || conn.contentLength > MAX_IMAGE) return null
                val bytes = conn.inputStream.use { input ->
                    val out = java.io.ByteArrayOutputStream()
                    val buf = ByteArray(16 * 1024)
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        if (out.size() > MAX_IMAGE) return null
                    }
                    out.toByteArray()
                }
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                var sample = 1
                while (bounds.outWidth / sample > 1080 || bounds.outHeight / sample > 1080) sample *= 2
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
            } finally {
                conn.disconnect()
            }
        }.getOrNull()
    }
}
