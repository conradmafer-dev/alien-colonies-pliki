extends SceneTree
## Integration test exercising the real main.gd language rebuild and _ready.
## The test subclass intercepts transport, session persistence and scene factory.
## It never contacts a network endpoint or reads/writes real game sessions.

class OfflineLanguageClient:
	extends "res://client/scripts/main.gd"

	var fixtures: Dictionary = {}
	var polls: int = 0
	var gameplay_requests: Array[Dictionary] = []
	var session_saves: int = 0

	func _load_session() -> void:
		server_url = "http://127.0.0.1:1"
		baked_server_url = server_url
		session_token = "offline-language-test-session"
		name_field.text = "offline-test-default"

	func _save_session() -> void:
		session_saves += 1

	func _request(path: String, payload: Dictionary, kind: String, method: int = HTTPClient.METHOD_POST) -> void:
		gameplay_requests.append({"path": path, "payload": payload.duplicate(true), "kind": kind, "method": method})

	# Keep the optional force argument from main.gd; all polling stays offline.
	func _poll(_force: bool = false) -> void:
		polls += 1
		if connection_editing or session_token.is_empty():
			return
		var locale_service: Node = get_tree().root.get_node("I18n")
		var sample: Dictionary = fixtures.get(locale_service.locale, {})
		if not sample.is_empty():
			_apply_state(sample.duplicate(true))

	func _check_client_version() -> void:
		pass

	func _new_language_client() -> Control:
		var replacement: OfflineLanguageClient = OfflineLanguageClient.new()
		replacement.fixtures = fixtures
		return replacement

var checks: int = 0
var failures: int = 0
var client: OfflineLanguageClient

func _initialize() -> void:
	_run.call_deferred()

func _expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(message)

func _settle() -> void:
	for _frame: int in range(4):
		await process_frame

func _active_client() -> OfflineLanguageClient:
	for child: Node in root.get_children():
		if child is OfflineLanguageClient:
			return child as OfflineLanguageClient
	return null

func _all_file_text(directory: String) -> String:
	var result: String = ""
	var access: DirAccess = DirAccess.open(directory)
	if access == null:
		return result
	for filename: String in access.get_files():
		if filename.ends_with(".cfg"):
			result += FileAccess.get_file_as_string(directory.path_join(filename))
	return result

func _run() -> void:
	if not OS.get_environment("XDG_DATA_HOME").contains("alien-language-"):
		push_error("Use disposable XDG_DATA_HOME containing alien-language-; refusing real preferences")
		quit(2)
		return
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var fixture_path: String = args[-1] if not args.is_empty() else ""
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(fixture_path))
	if not data is Dictionary or not data.has("locales"):
		push_error("Pass make_localization_fixture.py output after the suite path")
		quit(2)
		return
	var service: Node = root.get_node("I18n")
	service.set_locale("en", false)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(600, 1280)
	root.size = Vector2i(600, 1280)
	client = OfflineLanguageClient.new()
	for code: String in ["en", "pl", "de", "es", "fr"]:
		client.fixtures[code] = data["locales"][code]["zetans"]["ready"]
	root.add_child(client)
	current_scene = client
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	# Real _ready constructs all timer/HTTPRequest infrastructure; transport is
	# intercepted before any network method can run.
	client.set_process(false)
	client.poll_timer.stop()
	client.update_timer.stop()
	await _settle()
	_expect(client.http != null and client.poll_timer != null and client.update_timer != null, "Test exercises production _ready timer and UI construction")
	_expect(client.gameplay_requests.is_empty(), "Startup does not send gameplay commands")
	_expect(client.polls == 1, "Startup asks offline transport for exactly one world state")
	var planet_id: String = client.selected_planet
	var system_id: String = client.selected_system
	var target_id: String = str(client.target_picker.get_item_metadata(2))
	client.selected_target = target_id
	client._sync_target()
	client._open_tab(2)
	client._set_fleet_mode(1)
	client.mission_picker.select(3)
	client.options_panel.get_parent().visible = true
	client.name_field.text = "Konto"
	client.password_field.text = "NEVER-PERSIST-THIS-TEST-PASSWORD"
	client.fleet_inputs["scout"].value = 3
	client.fleet_inputs["cargo"].editor.text = "4"
	client.cargo_inputs["metal"].value = 37
	client.cargo_inputs["crystal"].editor.text = "42"
	client.galaxy_overview.visible = false
	client.biome_expanded = true
	var original: OfflineLanguageClient = client
	# Pending actions must block the scene replacement and preserve retry IDs.
	client.request_pending = true
	client.pending_language = "fr"
	client._apply_language_change()
	_expect(_active_client() == original and service.locale == "en", "Language change waits while an HTTP request is pending")
	_expect(client.pending_language == "fr", "Requested language remains queued")
	client.request_pending = false
	client.uncertain_action = {"type": "build", "request_id": "do-not-repeat"}
	client._apply_language_change()
	_expect(_active_client() == original and service.locale == "en", "Uncertain gameplay action blocks language change")
	_expect(client.uncertain_action.get("request_id") == "do-not-repeat", "Uncertain command ID is preserved")
	_expect(client.gameplay_requests.is_empty(), "Blocked language switches never resend gameplay actions")
	client.uncertain_action.clear()
	client.update_request_pending = true
	client._apply_language_change()
	_expect(_active_client() == original, "Pending update check blocks language rebuild")
	client.update_request_pending = false
	client._apply_language_change()
	client = _active_client()
	_expect(client != null and client != original, "Safe switch creates a fresh translated client")
	if client == null:
		quit(1)
		return
	client.set_process(false)
	client.poll_timer.stop()
	client.update_timer.stop()
	await _settle()
	_expect(current_scene == client, "SceneTree current scene points to the replacement")
	_expect(service.locale == "fr", "Safe switch selects French")
	_expect(client.selected_planet == planet_id, "Language rebuild preserves selected planet ID")
	_expect(client.selected_system == system_id, "Language rebuild preserves selected system ID")
	_expect(client.selected_target == target_id, "Language rebuild preserves destination ID")
	_expect(client.current_tab == 2 and client.fleet_mode == 1, "Language rebuild preserves Fleet/Construction tabs")
	_expect(client.mission_picker.selected == 3, "Language rebuild preserves transport mission type")
	_expect(client.options_panel.get_parent().visible, "Language rebuild keeps settings expanded")
	_expect(client.fleet_inputs["scout"].value == 3 and client.fleet_inputs["cargo"].value == 4, "Committed and uncommitted ship quantities survive rebuild")
	_expect(client.cargo_inputs["metal"].value == 37 and client.cargo_inputs["crystal"].value == 42, "Committed and uncommitted cargo quantities survive rebuild")
	_expect(client.name_field.text == "Konto", "Player-entered empire name is not translated")
	_expect(client.password_field.text == "NEVER-PERSIST-THIS-TEST-PASSWORD", "Login password survives only in memory")
	_expect(not client.language_resume.has("password"), "Temporary resume data removes password")
	_expect(not client.galaxy_overview.visible and client.galaxy_toggle.text == service.t("Mapa"), "Language rebuild preserves galaxy system view")
	_expect(client.biome_expanded, "Language rebuild preserves expanded landscape")
	_expect(not client.quote_ready, "Language rebuild invalidates stale fleet quotes")
	_expect(client.gameplay_requests.is_empty() and client.polls == 1, "Replacement reloads state once without repeating any action")
	_expect(client.mission_picker.get_item_text(3) == "Transport", "Mission controls are built in the selected language")
	var french_resource: String = service.t("KRYSZTAŁ").capitalize()
	_expect(french_resource == "Cristal", "French resource catalog is active")
	var settings: ConfigFile = ConfigFile.new()
	_expect(settings.load("user://language.cfg") == OK and settings.get_value("language", "selected", "") == "fr", "Safe switch persists French")
	_expect(not FileAccess.file_exists("user://session.cfg"), "UI test never creates real game sessions")
	_expect(not _all_file_text("user://").contains("NEVER-PERSIST-THIS-TEST-PASSWORD"), "No preference/config file contains the login password")
	print("Language switch: %d checks, %d failures; all transport intercepted" % [checks, failures])
	quit(0 if failures == 0 else 1)
