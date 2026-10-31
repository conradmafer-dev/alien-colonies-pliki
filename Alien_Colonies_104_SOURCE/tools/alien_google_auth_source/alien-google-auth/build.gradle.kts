plugins { id("com.android.library") }

android {
    namespace = "com.conradmafer.aliencolonies.auth"
    compileSdk = 36
    buildToolsVersion = "36.0.0"
    defaultConfig {
        minSdk = 23
        consumerProguardFiles("consumer-rules.pro")
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildTypes {
        getByName("release") { isMinifyEnabled = false }
    }
}

dependencies {
    compileOnly("org.godotengine:godot:4.5.1.stable")
    implementation("androidx.credentials:credentials:1.6.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.6.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.2.0")
}

for (variant in listOf("debug", "release")) {
    val title = variant.replaceFirstChar { it.uppercase() }
    tasks.register<Copy>("install${title}Addon") {
        dependsOn("assemble$title")
        from(layout.buildDirectory.file("outputs/aar/alien-google-auth-$variant.aar"))
        into(rootProject.layout.projectDirectory.dir("../../addons/AlienGoogleAuth/bin/$variant"))
        rename { "AlienGoogleAuth-$variant.aar" }
    }
}
tasks.register("installAddons") {
    dependsOn("installDebugAddon", "installReleaseAddon")
}
