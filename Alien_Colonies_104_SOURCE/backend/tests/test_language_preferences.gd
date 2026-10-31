extends SceneTree
## Run each mode in a separate process with an isolated XDG_DATA_HOME containing
## "alien-language-". Modes: fresh -> persisted -> unsupported -> nonpersist.
## No main scene, gameplay requests or session files are loaded.

var checks: int = 0
var failures: int = 0

func _initialize() -> void:
	_run.call_deferred()

func _expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(message)

func _run() -> void:
	if not OS.get_environment("XDG_DATA_HOME").contains("alien-language-"):
		push_error("Use a disposable XDG_DATA_HOME containing alien-language-; refusing real preferences")
		quit(2)
		return
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var mode: String = args[-1] if not args.is_empty() else ""
	var service: Node = root.get_node("I18n")
	var path: String = "user://language.cfg"
	var settings: ConfigFile = ConfigFile.new()
	if mode == "fresh":
		_expect(not FileAccess.file_exists(path), "Fresh process has no language preference")
		_expect(OS.get_locale().begins_with("pl"), "Host locale is Polish for first-launch default check")
		_expect(service.locale == "en", "First launch explicitly uses English even on Polish OS")
		_expect(TranslationServer.get_locale().begins_with("en"), "Godot locale also starts English")
		_expect(service.t("Planeta") == "Planet", "First-run labels use English catalog")
		_expect(service.set_locale("fr-FR"), "French selection persists successfully")
		_expect(service.locale == "fr", "Regional language selection normalizes to French")
		_expect(settings.load(path) == OK, "Language settings were written")
		_expect(settings.get_value("language", "selected", "") == "fr", "Stored language is French")
	elif mode == "persisted":
		_expect(service.locale == "fr", "Separate process restores saved French")
		_expect(service.t("Planeta") == "Planète", "French translation survives process restart")
		_expect(TranslationServer.get_locale().begins_with("fr"), "Godot receives restored French locale")
		settings.set_value("language", "selected", "zz-Unknown")
		_expect(settings.save(path) == OK, "Unsupported preference fixture saved")
	elif mode == "unsupported":
		_expect(service.locale == "en", "Unsupported stored language falls back to English")
		_expect(service.t("Planeta") == "Planet", "Unsupported preference uses English strings")
		_expect(service.normalize_locale("de-DE") == "de", "Supported regional tags normalize")
		_expect(service.normalize_locale("  pt_BR  ") == "en", "Unsupported regional tags fall back")
		_expect(service.set_locale("es", false), "Nonpersistent locale switch succeeds")
		_expect(service.locale == "es", "Nonpersistent switch changes runtime locale")
		_expect(settings.load(path) == OK, "Saved preference remains readable")
		_expect(settings.get_value("language", "selected", "") == "zz-Unknown", "Nonpersistent switch does not overwrite saved preference")
	elif mode == "nonpersist":
		_expect(service.locale == "en", "Next process ignores previous nonpersistent Spanish selection")
		_expect(service.t("Planeta") == "Planet", "Final restart uses English fallback")
	else:
		push_error("Expected fresh, persisted, unsupported or nonpersist mode")
		quit(2)
		return
	_expect(not FileAccess.file_exists("user://session.cfg"), "Preferences test never creates or reads game sessions")
	print("Language preferences %s: %d checks, %d failures; isolated user path %s" % [mode, checks, failures, OS.get_user_data_dir()])
	quit(0 if failures == 0 else 1)
