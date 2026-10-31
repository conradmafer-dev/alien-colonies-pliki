extends Node
## Real Godot layout and input handlers with synthetic server-authored fixtures.

class OfflineClient:
	extends "res://client/scripts/main.gd"
	var clock_offset: float = 0.0
	var commands: Array[Dictionary] = []
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
	func _server_now() -> float:
		return float(state.get("server_time", 1900000000)) + clock_offset
	func _request(_path: String, payload: Dictionary, kind: String, _method: int = HTTPClient.METHOD_POST) -> void:
		if kind in ["action", "preview"]:
			commands.append(payload.duplicate(true))

var checks: int = 0
var failures: int = 0
var client: OfflineClient
var screenshots: String = ""


func _ready() -> void:
	_run.call_deferred()


func expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(message)


func settle() -> void:
	for _frame: int in range(8):
		await get_tree().process_frame


func shot(filename: String) -> void:
	if screenshots.is_empty() or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(screenshots.path_join(filename + ".png"))


func localized_client(locale: String) -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client)
		client.queue_free()
	var root: Window = get_tree().root
	root.get_node("I18n").set_locale(locale, false)
	client = OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.communications.timer.stop()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty():
		get_tree().quit(2)
		return
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if args.size() > 1:
		screenshots = args[1]
		DirAccess.make_dir_recursive_absolute(screenshots)
	var root: Window = get_tree().root
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	root.size = Vector2i(720, 1600)
	localized_client("en")
	client._apply_state(fixture["early"]["en"])
	client._open_tab(3)
	await settle()
	expect(client.research_tree.visible, "Real tree is visible")
	expect(not client.research_list.visible and not client.unique_research_section.visible, "Old research lists yield to the tree")
	expect(client.research_tree.cards.size() == 21, "All 21 technologies are reachable")
	for dimensions: Vector2i in [Vector2i(720, 1280), Vector2i(720, 1600), Vector2i(1080, 2520)]:
		root.size = dimensions
		await settle()
		expect(client.size.x >= 719, "Logical width is retained")
		if dimensions.y * 9 > dimensions.x * 16:
			expect(client.size.y > 1280, "Taller devices expand the logical viewport")
		for button: Button in client.nav_buttons:
			expect(button.get_global_rect().end.y <= client.size.y + 1, "Bottom navigation stays on screen")
		for key: String in client.research_tree.cards:
			var card: Dictionary = client.research_tree.cards[key]
			var button: Button = card["button"]
			expect(button.position.x >= 0 and button.get_rect().end.x <= client.research_tree.size.x + 1, "Technology fits horizontally: " + key)
			expect(card["status"].get_global_rect().end.y <= button.get_global_rect().end.y + 1, "Card content fits vertically: " + key)
	root.size = Vector2i(720, 1600)
	await settle()
	await shot("technology_en_tall")
	client.research_tree.cards["computing"]["button"].pressed.emit()
	await settle()
	expect(client.compact_ui.details_open(), "Tap opens technology details")
	expect(not client.research_tree.detail_action.disabled, "Affordable available research is actionable")
	client.research_tree.detail_action.pressed.emit()
	expect(not client.commands.is_empty() and client.commands[-1].get("key") == "computing", "Research button sends the actual research command")
	client.research_tree.focus_technology("wormhole_theory")
	await settle()
	expect(client.tabs[3].scroll_vertical > 0, "Prerequisite navigation scrolls to the chosen node")
	await shot("technology_final_path")
	client.megastructure_ui.entry_button.pressed.emit()
	await settle()
	expect(client.compact_ui.details_open(), "Megastructure project panel opens")
	expect(client.megastructure_ui.build_buttons.has("dyson"), "Dyson construction action exists")
	expect(client.megastructure_ui.build_buttons["dyson"].disabled, "Locked construction cannot be submitted")
	client.compact_ui.close_details()
	for locale: String in ["pl", "de", "es", "fr"]:
		localized_client(locale)
		client._apply_state(fixture["early"][locale])
		client._open_tab(3)
		client.tabs[3].scroll_vertical = 0
		await settle()
		for key: String in client.research_tree.cards:
			var card: Dictionary = client.research_tree.cards[key]
			expect(card["status"].get_global_rect().end.y <= card["button"].get_global_rect().end.y + 1, "Translated text stays in card: " + locale + ":" + key)
		if locale == "pl":
			await shot("technology_pl_tall")
	localized_client("en")
	client._apply_state(fixture["open"]["en"])
	client.selected_target = str(fixture["target_id"])
	client._sync_target()
	client.compact_ui.open_composer()
	client._update_mission_hint()
	await settle()
	expect(client.megastructure_ui.fleet_box.visible, "Built wormhole exposes fleet controls")
	expect(not client.megastructure_ui.travel_mode.disabled, "Ready matching window allows tunnel selection")
	client.megastructure_ui.travel_mode.button_pressed = true
	client.fleet_inputs["scout"].value = 1
	expect(client._fleet_payload().get("travel_mode") == "tunnel", "Tunnel choice reaches the fleet payload")
	await shot("wormhole_fleet")
	client.quote_ready = true
	client.preview_fingerprint = client._fleet_fingerprint()
	client.clock_offset = 301
	client.megastructure_ui.tick()
	expect(not client.quote_ready, "Window expiry invalidates the prior quote")
	expect(client.megastructure_ui.travel_mode.disabled, "Expired window cannot be used")
	var count: int = client.commands.size()
	client._send_fleet()
	expect(client.commands.size() == count, "Expired tunnel never silently sends a normal fleet")
	client.clock_offset = 0
	client._apply_state(fixture["late"]["en"])
	client.megastructure_ui.open_projects()
	await settle()
	await shot("dyson_completed")
	client.compact_ui.close_details()
	var legacy: Dictionary = fixture["early"]["en"].duplicate(true)
	legacy.erase("technology_tree")
	client._apply_state(legacy)
	expect(not client.research_tree.visible and client.research_list.visible, "Older server keeps working with legacy research view")
	print("Technology UI 0.8.0: %d checks, %d failures" % [checks, failures])
	get_tree().quit(1 if failures else 0)
