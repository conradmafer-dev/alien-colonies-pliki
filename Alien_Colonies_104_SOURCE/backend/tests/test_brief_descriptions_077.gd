extends SceneTree
## Real engine test, separate from Python/source checks. Offline, no real accounts.
## python tests/make_localization_fixture.py /tmp/brief077.json
## godot --headless --path . --script tests/test_brief_descriptions_077.gd -- /tmp/brief077.json
const DetailText = preload("res://client/scripts/catalog_details.gd")
const Preferences = preload("res://client/scripts/ui_preferences.gd")

class OfflineClient:
	extends "res://client/scripts/main.gd"
	func _load_session() -> void:
		server_url = "http://127.0.0.1:1"
		baked_server_url = server_url
		session_token = ""
	func _save_session() -> void:
		pass
	func _poll(_force: bool = false) -> void:
		pass
	func _check_client_version() -> void:
		pass
	func _refresh_report_scope() -> void:
		report_scope = ""

var checks: int = 0
var failures: int = 0

func _initialize() -> void:
	_run.call_deferred()

func expect(value: bool, reason: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(reason)

func settle() -> void:
	for _frame: int in range(5):
		await process_frame

func rendered(client: Control) -> String:
	var content: Node = client.compact_ui.modal_body.get_node("CatalogDetailsParagraphs")
	var text: PackedStringArray = PackedStringArray()
	for child: Node in content.get_children():
		if child is Label:
			text.append(child.text)
	return "\n\n".join(text)

func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("Pass a freshly generated five-language fixture after --")
		quit(2)
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[-1]))
	if not data is Dictionary or not data.has("locales"):
		quit(2)
		return
	var prefs_path: String = "user://test_brief077_%d.cfg" % Time.get_ticks_usec()
	var language: Node = root.get_node("I18n")
	language.set_locale("en", false)
	expect(not Preferences.load_detailed_descriptions(prefs_path), "Missing config starts brief")
	var malformed: ConfigFile = ConfigFile.new()
	malformed.set_value("interface", "detailed_descriptions", "true")
	malformed.save(prefs_path)
	expect(not Preferences.load_detailed_descriptions(prefs_path), "Text is not mistaken for a bool")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(prefs_path))
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	var client: OfflineClient = OfflineClient.new()
	client.interface_settings_path = prefs_path
	root.add_child(client)
	current_scene = client
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.set_process(false)
	client._apply_state(data["locales"]["en"]["zetans"]["ready"].duplicate(true))
	await settle()
	expect(not client.detailed_descriptions, "Default client is brief")
	expect(not client.detailed_descriptions_button.button_pressed, "Settings switch is initially off")
	expect(client.detailed_descriptions_button.get_parent() == client.options_panel, "Switch is in Settings")
	var mine: Dictionary = client.building_rows["metal_mine"]
	client.compact_ui._open_catalog(mine)
	await settle()
	var text: String = rendered(client)
	expect(text.contains("Extracts metal."), "Short resource description")
	expect(text.contains("Production bonuses:") and text.contains("Output:"), "Modifier and output retained")
	expect(text.contains("Next level:") and text.contains("Energy use:"), "Next output and energy retained")
	expect(not text.contains("efficiency") and not text.contains("Colony output"), "No efficiency or totals in brief")
	client.detailed_descriptions_button.button_pressed = true
	await settle()
	expect(client.detailed_descriptions, "Toggle changes mode")
	expect(Preferences.load_detailed_descriptions(prefs_path), "True value persisted")
	text = rendered(client)
	expect(text.contains("Building output") and text.contains("Colony output"), "Open panel refreshes into full details")
	client.compact_ui.close_details()
	var restored: OfflineClient = OfflineClient.new()
	restored.interface_settings_path = prefs_path
	root.add_child(restored)
	restored.poll_timer.stop()
	restored.update_timer.stop()
	restored.set_process(false)
	expect(restored.detailed_descriptions, "New client instance loads stored value")
	restored.queue_free()
	await settle()
	client.detailed_descriptions_button.button_pressed = false
	expect(not Preferences.load_detailed_descriptions(prefs_path), "False value persisted, not reset to true")
	for locale: String in ["en", "pl", "de", "es", "fr"]:
		language.set_locale(locale, false)
		for race: String in ["zetans", "automatons", "symbionts"]:
			client._apply_state(data["locales"][locale][race]["ready"].duplicate(true))
			await settle()
			for key: String in ["metal_mine", "crystal_mine", "refinery", "shipyard", "lab"]:
				var control: Dictionary = client.building_rows[key]
				var brief: PackedStringArray = DetailText.paragraphs(client, control)
				var full: PackedStringArray = DetailText.paragraphs(client, control, true)
				expect(brief[0].split("\n")[1].begins_with(language.t("Koszt: %s").get_slice("%s", 0)), "Cost still follows level")
				expect(brief[1] == language.t(DetailText.BRIEF_DESCRIPTIONS[key]), "Localized short description: " + locale + "/" + key)
				expect(full.size() > brief.size(), "Full mode retains extra information: " + key)
				if key in ["shipyard", "lab"]:
					expect(not "\n\n".join(brief).contains(language.t("Progi odblokowania")), "Unlock thresholds hidden by default")
					expect(not "\n\n".join(brief).contains(language.t("Skrócenie czasu dzięki poziomowi budynku")), "No redundant time-reduction paragraph")
		client._apply_state(data["locales"][locale]["zetans"]["locked"].duplicate(true))
		await settle()
		var locked: String = "\n\n".join(DetailText.paragraphs(client, client.building_rows["echo_observatory"]))
		expect(locked.count(language.t("Wymagania")) == 1, "Requirements retained once in brief")
		expect(not locked.contains(language.t("Wymaga:")), "Duplicate reason remains suppressed")
		client._apply_state(data["locales"][locale]["zetans"]["maximum"].duplicate(true))
		await settle()
		for key: String in ["metal_mine", "shipyard", "lab"]:
			var capped: String = "\n\n".join(DetailText.paragraphs(client, client.building_rows[key]))
			expect(not capped.contains(language.t("Następny poziom: %s").get_slice("%s", 0)), "No next level at cap")
	language.set_locale("en", false)
	client.queue_free()
	await settle()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(prefs_path))
	print("Brief descriptions 077: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
