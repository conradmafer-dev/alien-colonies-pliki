extends Node
## Native regression scene. Run with Godot 4.5+ after importing the project.
## Deliberately not called a passed test until this scene actually runs.

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
var client: OfflineClient
var snapshots: Dictionary = {}


func _ready() -> void:
	_run.call_deferred()


func expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)


func settle() -> void:
	for _frame: int in range(8):
		await get_tree().process_frame


func new_client(race: String, locale: String = "en") -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client)
		client.queue_free()
	get_tree().root.get_node("I18n").set_locale(locale, false)
	client = OfflineClient.new()
	get_tree().root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.communications.timer.stop()
	client._apply_state(snapshots[race][locale].duplicate(true))
	client.session_token = "LOCAL-NATIVE-REGRESSION-ONLY"


func touch(index: int, down: bool, canceled: bool = false) -> InputEventScreenTouch:
	var event: InputEventScreenTouch = InputEventScreenTouch.new()
	event.index = index
	event.pressed = down
	event.canceled = canceled
	return event


func _run() -> void:
	var root: Window = get_tree().root
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	root.size = Vector2i(720, 1600)
	var path: String = "res://tests/fixtures/android_0112.json"
	if not FileAccess.file_exists(path):
		push_error("Missing test fixture: " + path)
		get_tree().quit(2)
		return
	snapshots = JSON.parse_string(FileAccess.get_file_as_string(path))
	var image_paths: Dictionary = {}
	for race: String in ["zetans", "symbionts", "automatons"]:
		new_client(race)
		client._open_tab(3)
		await settle()
		expect(client.research_tree.cards.size() == 25, race + ": all technologies")
		expect(client.ship_rows.size() == 12, race + ": all twelve ship classes")
		expect(client.research_tree.custom_minimum_size.y == 3120, "All ten rows are scrollable")
		for dimensions: Vector2i in [Vector2i(720, 1280), Vector2i(720, 1600), Vector2i(1080, 2520)]:
			root.size = dimensions
			await settle()
			for key: String in client.research_tree.cards:
				var card: Dictionary = client.research_tree.cards[key]
				var rect: Rect2 = card["button"].get_rect()
				expect(rect.end.y <= client.research_tree.size.y + 1, "Node inside scroll extent: " + key)
				expect(rect.position.x >= 0 and rect.end.x <= client.research_tree.size.x + 1, "Node inside width: " + key)
				expect(card["art"].texture != null, "Research texture imported: " + key)
		for key: String in client.ArtLibrary.CAPITAL_SHIPS:
			var art: Texture2D = client.ship_rows[key]["art"].texture
			expect(art != null, "Ship texture imported: " + race + "/" + key)
			if art != null:
				expect(art.resource_path.ends_with("races/" + race + "/" + key + ".webp"), "No aliased capital texture")
				expect(not image_paths.has(art.resource_path), "Each capital has a separate file")
				image_paths[art.resource_path] = true
				expect(client.fleet_portraits[key].texture == art, "Fleet composer uses the same dedicated art")
		client.research_tree.open_details("capital_shipbuilding")
		await settle()
		expect(client.compact_ui.modal_body.find_child("TechnologyUnlocks", true, false) != null, "Research shows what it unlocks")
		client.compact_ui._open_catalog_target("ships", "titan")
		await settle()
		var link: Button = client.compact_ui.modal_body.find_child("Requirement_titan_core", true, false)
		expect(link != null, "Titan detail has a research link")
		if link != null:
			link.pressed.emit()
			await settle()
			expect(client.research_tree.detail_key == "titan_core", "Requirement opens correct technology")
		client.research_tree.focus_technology("titan_core")
		await settle()
		expect(client.tabs[3].scroll_vertical > 0, "Endgame navigation scrolls down")
		client.compact_ui._open_catalog_target("megastructures", "dyson")
		await settle()
		expect(client.megastructure_ui.build_buttons.has("dyson"), "Dyson requirement opens stellar projects")
		client.compact_ui.close_details()
	expect(image_paths.size() == 12, "Twelve unique capital illustration resources")
	for locale: String in ["en", "pl", "de", "es", "fr"]:
		new_client("zetans", locale)
		await settle()
		expect(client.ship_rows["titan"]["heading"].text == snapshots["zetans"][locale]["catalog"]["ships"][-1]["name"], "Localized titan: " + locale)
		var settings: Button = client.find_child("SettingsButton", true, false)
		expect(settings != null, "Settings entry remains visible")
		settings.pressed.emit()
		expect(client.options_panel.get_parent().visible, "Settings opens with one activation")
		settings.pressed.emit()
		expect(not client.options_panel.get_parent().visible, "Settings closes with one activation")
	new_client("zetans")
	await settle()
	var old_metal: float = float(client.state["resources"]["metal"])
	var next_state: Dictionary = client.state.duplicate(true)
	next_state["resources"]["metal"] = old_metal + 23
	client.interaction_guard.observe(touch(0, true))
	client._apply_state(next_state)
	expect(float(client.state["resources"]["metal"]) == old_metal, "Held finger prevents state/controls being replaced")
	expect(not client.deferred_state.is_empty(), "Latest update waits for gesture completion")
	client.interaction_guard.observe(touch(1, true))
	client.interaction_guard.observe(touch(0, false))
	expect(client.interaction_guard.busy(), "Second held finger still blocks layout refresh")
	client.interaction_guard.observe(touch(1, false, true))
	await get_tree().create_timer(0.18).timeout
	await settle()
	expect(float(client.state["resources"]["metal"]) == old_metal + 23, "Deferred state applies after release grace")
	client.interaction_guard.observe(touch(0, true))
	client.interaction_guard.reset()
	expect(not client.interaction_guard.busy(), "Lost app focus can clear a held gesture")
	# Exercise real production transport setup against loopback port 1, never a live server.
	client._request_state("/api/state")
	expect(not client.request_pending, "Polling never locks real command buttons")
	expect(client.state_request_pending, "Read request has its own pending flag")
	var stale_generation: int = client.state_request_generation
	client._request("/api/action", {"type": "research", "key": "computing", "planet_id": client.selected_planet, "request_id": "local-only-order"}, "action")
	expect(not client.state_request_pending, "Command cancels the older GET")
	expect(client.state_request_generation > stale_generation, "Canceled GET loses its generation")
	expect(client.request_pending, "Real command remains protected from duplicates")
	client._on_state_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"ok": true, "state": next_state}).to_utf8_buffer(), stale_generation)
	expect(client.request_pending, "Late GET cannot clear a real command's busy flag")
	client.http.cancel_request()
	client.request_pending = false
	client.request_kind = ""
	client.uncertain_action.clear()
	client._cancel_state_request()
	print("Android 0.11.2 native scene: %d checks, %d failures" % [checks, failures])
	get_tree().quit(1 if failures else 0)
