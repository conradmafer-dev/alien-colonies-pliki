extends RefCounted

const ApkManifest = preload("res://client/scripts/apk_manifest.gd")

## Called only after an explicit tap and successful download verification.
## Android retains the final say over package identity, signature and installation.
static func request_install(apk_path: String, expected_version_code: int) -> Dictionary:
	if OS.get_name() != "Android":
		return _failure(I18n.t("Instalację APK można uruchomić na telefonie z Androidem."))
	var global_path: String = ProjectSettings.globalize_path(apk_path).simplify_path()
	var allowed_directory: String = ProjectSettings.globalize_path("user://updates/").simplify_path().trim_suffix("/") + "/"
	if not global_path.begins_with(allowed_directory) or not global_path.ends_with(".apk") or not FileAccess.file_exists(apk_path):
		return _failure(I18n.t("Brakuje gotowego pliku aktualizacji. Pobierz go ponownie."))
	# Dynamic access keeps desktop/editor imports independent of Android classes.
	if not Engine.has_singleton("AndroidRuntime") or not Engine.has_singleton("JavaClassWrapper"):
		return _failure(I18n.t("Nie można uruchomić instalatora w tej wersji aplikacji."))
	var runtime: Object = Engine.get_singleton("AndroidRuntime")
	var java: Object = Engine.get_singleton("JavaClassWrapper")
	var activity: Object = runtime.call("getActivity")
	if activity == null or java.call("get_exception") != null:
		return _failure(I18n.t("Android nie jest jeszcze gotowy do instalacji. Spróbuj ponownie."))
	var manager: Object = activity.call("getPackageManager")
	if manager == null or java.call("get_exception") != null:
		return _failure(I18n.t("Nie można sprawdzić pliku aktualizacji."))
	var expected_package: String = str(activity.call("getPackageName"))
	if expected_package.is_empty() or java.call("get_exception") != null:
		return _failure(I18n.t("Nie można sprawdzić pliku aktualizacji."))
	# Do not depend on the Java bridge exposing PackageInfo instance fields.
	# The old packageName field check falsely rejected this user's APK, although
	# Android installed it as an update. Read the bounded binary manifest instead.
	var identity: Dictionary = ApkManifest.read_apk(global_path)
	var verified: Dictionary = ApkManifest.validate_identity(identity, expected_package, expected_version_code)
	if not bool(verified.get("ok", false)):
		return _identity_failure(str(verified.get("reason", "manifest_unreadable")))
	var version: Object = java.call("wrap", "android.os.Build$VERSION")
	if version == null or java.call("get_exception") != null:
		return _failure(I18n.t("Nie można sprawdzić ustawień instalacji Androida."))
	var sdk: int = int(version.get("SDK_INT"))
	if java.call("get_exception") != null:
		return _failure(I18n.t("Nie można sprawdzić ustawień instalacji Androida."))
	if sdk >= 26:
		var allowed: bool = bool(manager.call("canRequestPackageInstalls"))
		if java.call("get_exception") != null:
			return _failure(I18n.t("Nie można sprawdzić zgody na instalowanie aktualizacji."))
		if not allowed:
			return _open_install_settings(activity, java)
	# Godot documents shell_open(globalize_path(user://...)) on Android.
	# The actual hand-off of a private APK to the device installer still requires
	# an Android smoke test with the user's export templates; no silent install.
	var error: Error = OS.shell_open(global_path)
	if error != OK:
		return _failure(I18n.t("Nie udało się otworzyć instalatora. Sprawdź zgodę na instalację i spróbuj ponownie."))
	return {"ok": true, "message": I18n.t("Potwierdź instalację w oknie Androida. Jeśli ją anulujesz, możesz ponownie wybrać „Zainstaluj”.")}


static func _open_install_settings(activity: Object, java: Object) -> Dictionary:
	var intent_class: Object = java.call("wrap", "android.content.Intent")
	if intent_class == null or java.call("get_exception") != null:
		return _failure(I18n.t("Nie udało się otworzyć ustawień instalowania aplikacji."))
	var uri_class: Object = java.call("wrap", "android.net.Uri")
	if uri_class == null or java.call("get_exception") != null:
		return _failure(I18n.t("Nie udało się otworzyć ustawień instalowania aplikacji."))
	var package_name: String = str(activity.call("getPackageName"))
	if package_name.is_empty() or java.call("get_exception") != null:
		return _failure(I18n.t("Nie udało się otworzyć ustawień instalowania aplikacji."))
	var uri: Object = uri_class.call("parse", "package:" + package_name)
	if uri == null or java.call("get_exception") != null:
		return _failure(I18n.t("Nie udało się otworzyć ustawień instalowania aplikacji."))
	var intent: Object = intent_class.call("Intent")
	if intent == null or java.call("get_exception") != null:
		return _failure(I18n.t("Nie udało się otworzyć ustawień instalowania aplikacji."))
	intent.call("setAction", "android.settings.MANAGE_UNKNOWN_APP_SOURCES")
	if java.call("get_exception") != null:
		return _failure(I18n.t("Nie udało się otworzyć ustawień instalowania aplikacji."))
	intent.call("setData", uri)
	if java.call("get_exception") != null:
		return _failure(I18n.t("Nie udało się otworzyć ustawień instalowania aplikacji."))
	activity.call("startActivity", intent)
	if java.call("get_exception") != null:
		return _failure(I18n.t("W ustawieniach Androida zezwól tej grze na instalowanie aplikacji, a potem spróbuj ponownie."))
	return {"ok": true, "message": I18n.t("Zezwól tej grze na instalowanie aplikacji. Wróć do gry i ponownie wybierz „Zainstaluj”.")}


static func _failure(message: String) -> Dictionary:
	return {"ok": false, "message": message}


static func _identity_failure(reason: String) -> Dictionary:
	if reason == "package_mismatch":
		return _failure(I18n.t("Pobrany plik jest przeznaczony dla innej aplikacji. Sprawdź ponownie dostępne wydanie."))
	if reason == "version_mismatch":
		return _failure(I18n.t("Pobrany plik ma inną wersję niż ogłoszona. Sprawdź ponownie dostępne wydanie."))
	return _failure(I18n.t("Nie można odczytać danych pobranego APK (%s). Pobierz plik ponownie lub zainstaluj wydanie przez przeglądarkę.") % reason)
