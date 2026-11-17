package uz.ketoshop.app.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec

/**
 * The phone's identity for the shop: a P-256 key generated inside the
 * Android Keystore (TEE). The private half can't be read by the app, by
 * root tools copying files, or by a backup; only its signatures leave.
 * The server keeps the public half and checks every request against it.
 *
 * TEE rather than StrongBox on purpose: a StrongBox signature takes
 * 50-150 ms, and every API call is signed.
 */
object DeviceKey {
    private const val ALIAS = "ketoshop.device.v1"

    @Volatile private var cached: PrivateKey? = null

    private fun store(): KeyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    @Synchronized
    private fun ensure(): KeyStore {
        val ks = store()
        if (!ks.containsAlias(ALIAS)) {
            val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
                .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                .setDigests(KeyProperties.DIGEST_SHA256)
                .setUserAuthenticationRequired(false)
                .build()
            KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore").run {
                initialize(spec)
                generateKeyPair()
            }
            cached = null
        }
        return ks
    }

    /** base64url SubjectPublicKeyInfo (DER). */
    fun publicKey(): String = b64u(ensure().getCertificate(ALIAS).publicKey.encoded)

    /** ECDSA-SHA256 over `prefix + base64url(sha256(body))`, DER signature, base64url. */
    fun sign(prefix: String, body: ByteArray): String {
        val key = cached ?: (ensure().getKey(ALIAS, null) as PrivateKey).also { cached = it }
        val bodyHash = b64u(MessageDigest.getInstance("SHA-256").digest(body))
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(key)
        signer.update((prefix + bodyHash).toByteArray(Charsets.UTF_8))
        return b64u(signer.sign())
    }

    @Synchronized
    fun reset() {
        cached = null
        store().run { if (containsAlias(ALIAS)) deleteEntry(ALIAS) }
    }

    fun b64u(bytes: ByteArray): String =
        Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
}
