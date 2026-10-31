extends Node
## Authored text only. Do not pass player names, identifiers or URLs to t().
## Client catalogs also contain Android-only UI; never replace them with server subsets.
## English is the explicit first-run default.

signal language_changed

const LOCALES: Array[String] = ["en", "pl", "de", "es", "fr"]
const LANGUAGE_NAMES: Array[String] = ["English", "Polski", "Deutsch", "Español", "Français"]
const SETTINGS_PATH: String = "user://language.cfg"
var locale: String = "en"
var _catalogs: Dictionary = {}


func _init() -> void:
	_load_catalogs()
	var settings: ConfigFile = ConfigFile.new()
	if settings.load(SETTINGS_PATH) == OK:
		locale = normalize_locale(str(settings.get_value("language", "selected", "en")))
	TranslationServer.set_locale(locale)


func normalize_locale(value: String) -> String:
	var code: String = value.strip_edges().to_lower().replace("_", "-").get_slice("-", 0)
	return code if code in LOCALES else "en"


func _load_catalogs() -> void:
	for code: String in LOCALES:
		var path: String = "res://localization/%s.json" % code
		var parsed: Variant = null
		if FileAccess.file_exists(path):
			parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
		_catalogs[code] = parsed if parsed is Dictionary else {}


func t(source: String) -> String:
	if source.is_empty():
		return source
	var translated: String = str(_catalogs.get(locale, {}).get(source, ""))
	if not translated.is_empty():
		return translated
	# An incomplete non-English catalog always falls back to English.
	return str(_catalogs.get("en", {}).get(source, source))


func decimal(value: String) -> String:
	if locale == "en":
		return value
	var point: int = value.find(".")
	while point >= 0:
		if point > 0 and point + 1 < value.length() and value.substr(point - 1, 1).is_valid_int() and value.substr(point + 1, 1).is_valid_int():
			value = value.substr(0, point) + "," + value.substr(point + 1)
		point = value.find(".", point + 1)
	return value


func set_locale(value: String, persist: bool = true) -> bool:
	var next: String = normalize_locale(value)
	if persist:
		var settings: ConfigFile = ConfigFile.new()
		settings.set_value("language", "selected", next)
		if settings.save(SETTINGS_PATH) != OK:
			return false
	if locale != next:
		locale = next
		TranslationServer.set_locale(locale)
		language_changed.emit()
	return true
