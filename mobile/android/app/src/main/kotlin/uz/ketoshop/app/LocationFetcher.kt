package uz.ketoshop.app

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Handler
import android.os.Looper

/**
 * One fresh position for the delivery pin, from the platform LocationManager
 * (no Google Play services needed). GPS and network are asked together; a
 * fix within 50 m is taken at once, otherwise the best one after 12 s, and
 * after 25 s a recent last-known position or a timeout.
 */
class LocationFetcher(private val context: Context) {
    private val main = Handler(Looper.getMainLooper())

    fun enabled(): Boolean {
        val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        return if (Build.VERSION.SDK_INT >= 28) lm.isLocationEnabled
        else lm.isProviderEnabled(LocationManager.GPS_PROVIDER) || lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
    }

    @SuppressLint("MissingPermission") // checked by the caller
    fun current(done: (Location?) -> Unit) {
        val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .filter { runCatching { lm.isProviderEnabled(it) }.getOrDefault(false) }
        var best: Location? = null
        var finished = false
        lateinit var listener: LocationListener

        fun finish(result: Location?) {
            if (finished) return
            finished = true
            runCatching { lm.removeUpdates(listener) }
            main.removeCallbacksAndMessages(null)
            done(result)
        }

        listener = LocationListener { location ->
            if (best == null || location.accuracy < best!!.accuracy) best = location
            if (location.accuracy <= 50f) finish(location)
        }
        for (provider in providers) {
            runCatching { lm.requestLocationUpdates(provider, 0L, 0f, listener, Looper.getMainLooper()) }
        }
        main.postDelayed({ if (best != null) finish(best) }, 12_000)
        main.postDelayed({
            val recent = providers.mapNotNull { runCatching { lm.getLastKnownLocation(it) }.getOrNull() }
                .filter { System.currentTimeMillis() - it.time < 2 * 60_000 }
                .minByOrNull { it.accuracy }
            finish(best ?: recent)
        }, 25_000)
        if (providers.isEmpty()) finish(null)
    }
}
