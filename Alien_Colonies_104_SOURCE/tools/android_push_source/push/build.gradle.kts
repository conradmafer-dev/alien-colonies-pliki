plugins { id("com.android.library") }
android {
    namespace = "com.conradmafer.aliencolonies.push"
    compileSdk = 36
    buildToolsVersion = "36.0.0"
    defaultConfig { minSdk = 24 }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildTypes { getByName("release") { isMinifyEnabled = false } }
}
dependencies {
    compileOnly("org.godotengine:godot:4.5.1.stable")
    implementation("com.google.firebase:firebase-messaging:25.0.1")
}

