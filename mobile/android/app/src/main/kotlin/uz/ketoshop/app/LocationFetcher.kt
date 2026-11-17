package uz.ketoshop.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper

/**
 * One position for the delivery pin, from the platform LocationManager (no
 * Google Play services needed).
 *
 * Why the first version said «Joylashuvni aniqlab bo'lmadi» too often:
 * indoors GPS gives nothing in 25 s; a phone with only "approximate"
 * permission made the GPS request fail silently; a last known position was
 * used only if under 2 minutes old. Now: every usable provider is asked at
 * once (fused on Android 12+, network, GPS — GPS only with precise
 * permission), a fix within 100 m is taken at once, the best one after 10 s,
 * and at 25 s a last known position up to 10 minutes old. The shop page
 * then lets the buyer move the pin on its map either way.
 */
class LocationFetcher(private val context: Context) {
    private val main = Handler(Looper.getMainLooper())
    private val lm get() = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    fun enabled(): Boolean = if (Build.VERSION.SDK_INT >= 28) lm.isLocationEnabled
    else providers().isNotEmpty()

    private fun precise(): Boolean =
        context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun providers(): List<String> {
        val all = runCatching { lm.allProviders }.getOrDefault(emptyList())
        val wanted = buildList {
            if (Build.VERSION.SDK_INT >= 31) add(LocationManager.FUSED_PROVIDER)
            add(LocationManager.NETWORK_PROVIDER)
            if (precise()) add(LocationManager.GPS_PROVIDER)
        }
        return wanted.filter { it in all && runCatching { lm.isProviderEnabled(it) }.getOrDefault(false) }
    }

    @SuppressLint("MissingPermission") // the caller checked it
    private fun lastKnown(maxAgeMs: Long): Location? =
        (providers() + LocationManager.PASSIVE_PROVIDER)
            .mapNotNull { runCatching { lm.getLastKnownLocation(it) }.getOrNull() }
            .filter { System.currentTimeMillis() - it.time <= maxAgeMs }
            .minByOrNull { it.accuracy }

    @SuppressLint("MissingPermission") // the caller checked it
    fun current(done: (Location?) -> Unit) {
        val manager = lm
        val sources = providers()
        var best: Location? = null
        var finished = false

        // A full object, not a lambda: before Android 11 these methods are
        // abstract, and a lambda listener crashes when the system calls them.
        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                if (best == null || location.accuracy < best!!.accuracy) best = location
                if (location.accuracy <= GOOD_ENOUGH_M) finish(location)
            }

            @Deprecated("Deprecated in Java")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
            override fun onProviderEnabled(provider: String) = Unit
            override fun onProviderDisabled(provider: String) = Unit

            fun finish(result: Location?) {
                if (finished) return
                finished = true
                runCatching { manager.removeUpdates(this) }
                main.removeCallbacksAndMessages(TOKEN)
                done(result)
            }
        }

        if (sources.isEmpty()) {
            listener.finish(lastKnown(STALE_OK_MS))
            return
        }
        for (provider in sources) {
            runCatching { manager.requestLocationUpdates(provider, 0L, 0f, listener, Looper.getMainLooper()) }
        }
        main.postAtTime({ if (best != null) listener.finish(best) }, TOKEN, android.os.SystemClock.uptimeMillis() + BEST_AFTER_MS)
        main.postAtTime({ listener.finish(best ?: lastKnown(STALE_OK_MS)) }, TOKEN,
            android.os.SystemClock.uptimeMillis() + GIVE_UP_MS)
    }

    private companion object {
        const val GOOD_ENOUGH_M = 100f
        const val BEST_AFTER_MS = 10_000L
        const val GIVE_UP_MS = 25_000L
        const val STALE_OK_MS = 10 * 60_000L
        val TOKEN = Any()
    }
}
