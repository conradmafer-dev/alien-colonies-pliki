extends SceneTree
## Offline engine test. Generate the fixture with:
## python tests/make_localization_fixture.py /path/to/details075.json
## godot --headless --path . --script tests/test_catalog_details_075.gd -- /path/to/details075.json
## Python checks do NOT count this file as executed.
const DetailText = preload("res://client/scripts/catalog_details.gd")
class OfflineClient:
	extends "res://client/scripts/main.gd"
	var purchases: int = 0
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
	func _catalog_action(_kind: String, _key: String) -> void:
		purchases += 1

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
	for _frame: int in range(6):
		await process_frame
func click(point: Vector2) -> void:
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	Input.parse_input_event(motion)
	for down: bool in [true, false]:
		var event: InputEventMouseButton = InputEventMouseButton.new()
		event.position = point
		event.global_position = point
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = down
		Input.parse_input_event(event)

func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("Pass the generated offline fixture after --")
		quit(2)
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[-1]))
	if not data is Dictionary or not data.has("locales"):
		quit(2)
		return
	var language: Node = root.get_node("I18n")
	language.set_locale("en", false)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	var client: OfflineClient = OfflineClient.new()
	root.add_child(client)
	current_scene = client
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.set_process(false)
	client._apply_state(data["locales"]["en"]["zetans"]["ready"].duplicate(true))
	await settle()
	for rows: Dictionary in [client.building_rows, client.research_rows, client.ship_rows, client.defense_rows]:
		for key: String in rows:
			var controls: Dictionary = rows[key]
			var parts: PackedStringArray = DetailText.paragraphs(client, controls, true)
			expect(parts.size() >= 2, "Details include independent description: " + key)
			expect(parts[0].split("\n")[1].begins_with("Cost:"), "Cost immediately follows level/count: " + key)
			expect(parts[1] == str(controls["entry"]["description"]), "Description is shown despite collapsed legacy label: " + key)
			expect(controls["panel"].has_signal("details_requested"), "Whole card has a detail gesture: " + key)
	var mine: Dictionary = client.building_rows["metal_mine"]
	var text: String = "\n\n".join(DetailText.paragraphs(client, mine, true))
	expect(text.contains("Building output — metal") and text.contains(" / h"), "Mine shows numeric output and resource")
	expect(text.contains("Current (level") and text.contains("Next (level"), "Mine has current and next values")
	var yard: String = "\n\n".join(DetailText.paragraphs(client, client.building_rows["shipyard"], true))
	expect(yard.contains("Available ship and defense types"), "Yard shows actual project counts")
	expect(yard.contains("Shipyard production speed bonus") and yard.contains("Project time:"), "Yard displays real speed bonuses and project times")
	# Exercise actual GUI propagation over cost, level and the formerly inert gaps.
	client.tabs[0].ensure_control_visible(mine["panel"])
	await settle()
	var panel: Control = mine["panel"]
	var points: Array[Vector2] = [panel.get_global_rect().position + Vector2(4, 4), mine["level"].get_global_rect().get_center(), mine["costs"]["metal"]["amount"].get_global_rect().get_center()]
	for point: Vector2 in points:
		click(point)
		await settle()
		expect(client.compact_ui.details_open(), "Passive card area opens details")
		client.compact_ui.close_details()
		await settle()
	var purchases: int = client.purchases
	click(mine["action"].get_global_rect().get_center())
	await settle()
	expect(not client.compact_ui.details_open(), "Upgrade does not open details")
	expect(client.purchases == purchases + 1, "Upgrade executes once")
	# A scroll beginning between press/release cancels the panel-level handler.
	var down: InputEventMouseButton = InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT
	down.pressed = true
	down.position = Vector2(5,5)
	panel.call("_gui_input", down)
	panel.notification(Control.NOTIFICATION_SCROLL_BEGIN)
	down.pressed = false
	panel.call("_gui_input", down)
	expect(not client.compact_ui.details_open(), "Scrolling cannot open catalog details")
	for width: int in [360,450,720,1080]:
		root.size = Vector2i(width, int(width * 16.0 / 9.0))
		for amount: int in [0,12,999,1000000000]:
			client.state["player"]["swarm_crystals"] = amount
			client._refresh_skills()
			await settle()
			expect(client.skill_wallet_button.autowrap_mode == TextServer.AUTOWRAP_OFF, "Wallet never wraps")
			expect(client.skill_wallet_button.size.y <= 80, "Wallet stays within compact header")
			expect(client.skill_wallet_button.text == client._number(float(amount)), "Wallet remains numeric on direct skill refresh")
	# Unbuilt requirements are grouped exactly once.
	client._apply_state(data["locales"]["en"]["zetans"]["locked"].duplicate(true))
	await settle()
	var locked: String = "\n\n".join(DetailText.paragraphs(client,client.building_rows["echo_observatory"], true))
	expect(locked.count("Requirements") == 1, "Single requirements paragraph")
	expect(not locked.contains("Requires:"), "No duplicate disabled-action requirement sentence")
	expect(locked.contains("Not built yet"), "Unbuilt status in metadata")
	print("Catalog details 075: %d checks, %d failures" % [checks, failures])
	client.queue_free()
	await settle()
	quit(1 if failures else 0)
