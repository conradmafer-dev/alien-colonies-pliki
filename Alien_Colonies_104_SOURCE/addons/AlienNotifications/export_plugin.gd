@tool
extends EditorPlugin
var exporter: AndroidPushExport
func _enter_tree() -> void:
    exporter = AndroidPushExport.new()
    add_export_plugin(exporter)
func _exit_tree() -> void:
    remove_export_plugin(exporter)
class AndroidPushExport extends EditorExportPlugin:
    func _supports_platform(platform: EditorExportPlatform) -> bool:
        return platform is EditorExportPlatformAndroid
    func _get_android_libraries(_platform: EditorExportPlatform, debug: bool) -> PackedStringArray:
        var variant: String = "debug" if debug else "release"
        return PackedStringArray(["AlienNotifications/bin/%s/AlienNotifications-%s.aar" % [variant, variant]])
    func _get_android_dependencies(_platform: EditorExportPlatform, _debug: bool) -> PackedStringArray:
        return PackedStringArray(["com.google.firebase:firebase-messaging:25.0.1"])
    func _get_name() -> String:
        return "AlienNotifications"

