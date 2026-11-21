import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing comes from a key.properties OUTSIDE the repository
// (KETOSHOP_KEY_PROPERTIES, set by tool/build_release.ps1). Without it the
// release build is signed with the debug key and skips the self-check.
val keyProperties = Properties().apply {
    System.getenv("KETOSHOP_KEY_PROPERTIES")?.let { path ->
        val file = File(path)
        if (file.isFile) file.inputStream().use { load(it) }
    }
}
val hasReleaseKey = keyProperties.getProperty("storeFile") != null

// Firebase (push) client config from app/google-services.json — public
// values, the same ones every installed APK carries. Without the file the
// app builds and runs with push switched off.
@Suppress("UNCHECKED_CAST")
val firebaseValues: Map<String, String> = run {
    val f = file("google-services.json")
    if (!f.isFile) return@run emptyMap()
    val root = groovy.json.JsonSlurper().parse(f) as Map<String, Any?>
    val info = root["project_info"] as Map<String, Any?>
    val client = (root["client"] as List<Map<String, Any?>>).first {
        val ci = it["client_info"] as Map<String, Any?>
        (ci["android_client_info"] as Map<String, Any?>)["package_name"] == "uz.ketoshop.app"
    }
    mapOf(
        "google_app_id" to ((client["client_info"] as Map<String, Any?>)["mobilesdk_app_id"] as String),
        "google_api_key" to ((client["api_key"] as List<Map<String, Any?>>).first()["current_key"] as String),
        "project_id" to (info["project_id"] as String),
        "gcm_defaultSenderId" to (info["project_number"] as String),
    )
}
val expectedCert: String =
    if (hasReleaseKey) (project.findProperty("ketoshop.signingCertSha256") as String? ?: "") else ""

android {
    namespace = "uz.ketoshop.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "uz.ketoshop.app"
        // Android 7.0+: network security config, Keystore EC keys, APK v2 signatures.
        minSdk = maxOf(24, flutter.minSdkVersion)
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // The SHA-256 of the certificate this build is signed with; the app
        // treats any other signer as a repackaged copy (security/Integrity.kt).
        buildConfigField("String", "SIGNING_CERT_SHA256", "\"$expectedCert\"")
        firebaseValues.forEach { (name, value) -> resValue("string", name, value) }
        buildConfigField("boolean", "PUSH_CONFIGURED", firebaseValues.isNotEmpty().toString())
        // Bridge protocol between the app and webapp/app_shim.js.
        buildConfigField("int", "BRIDGE_VERSION", "2")
    }

    buildFeatures {
        buildConfig = true
    }

    signingConfigs {
        if (hasReleaseKey) {
            create("release") {
                storeFile = file(keyProperties.getProperty("storeFile"))
                storePassword = keyProperties.getProperty("storePassword")
                keyAlias = keyProperties.getProperty("keyAlias")
                keyPassword = keyProperties.getProperty("keyPassword")
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName(if (hasReleaseKey) "release" else "debug")
            isMinifyEnabled = true
            isShrinkResources = true
            isDebuggable = false
            isJniDebuggable = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    // Google-only dependency metadata is not needed: the APK is not on Play yet.
    dependenciesInfo {
        includeInApk = false
        includeInBundle = false
    }

    packaging {
        resources {
            excludes += setOf("META-INF/*.version", "META-INF/*.kotlin_module", "kotlin/**", "DebugProbesKt.bin")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    // The app's only third-party code: Google's own push client (SECURITY.md).
    implementation("com.google.firebase:firebase-messaging:24.1.0")
    implementation("androidx.core:core:1.13.1")
}
