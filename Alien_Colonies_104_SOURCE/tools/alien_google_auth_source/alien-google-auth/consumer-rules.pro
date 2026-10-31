# Godot finds the plugin class and methods by reflection.
-keep class com.conradmafer.aliencolonies.auth.AlienGoogleAuth { public *; }
-keep class com.conradmafer.aliencolonies.auth.GoogleAuthReturnActivity { public *; }
-keepclassmembers class * { @org.godotengine.godot.plugin.UsedByGodot <methods>; }
