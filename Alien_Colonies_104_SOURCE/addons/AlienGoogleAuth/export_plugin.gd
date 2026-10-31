@tool
extends EditorPlugin

var export_plugin : AuthExportPlugin


func _enter_tree ( ) -> void :
    export_plugin = AuthExportPlugin . new ( )
    add_export_plugin ( export_plugin )


func _exit_tree ( ) -> void :
    remove_export_plugin ( export_plugin )
    export_plugin = null


class AuthExportPlugin extends EditorExportPlugin :
    func _supports_platform ( platform : EditorExportPlatform ) -> bool :
        return platform is EditorExportPlatformAndroid


    func _get_android_libraries ( _platform : EditorExportPlatform , debug : bool ) -> PackedStringArray :
        var variant : String = "debug" if debug else "release"
        return PackedStringArray ( [ "AlienGoogleAuth/bin/%s/AlienGoogleAuth-%s.aar" % [ variant , variant ] ] )


    func _get_android_dependencies ( _platform : EditorExportPlatform , _debug : bool ) -> PackedStringArray :
        return PackedStringArray ( [
            "androidx.credentials:credentials:1.6.0" ,
            "androidx.credentials:credentials-play-services-auth:1.6.0" ,
            "com.google.android.libraries.identity.googleid:googleid:1.2.0" ,
        ] )


    func _get_name ( ) -> String :
        return "AlienGoogleAuth"
