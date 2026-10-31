extends Node

class OfflineClient:
	extends "res://client/scripts/main.gd"
	var commands: Array[Dictionary] = []
	func _load_session() -> void:
		server_url = "http://127.0.0.1:1"
		baked_server_url = server_url
		session_token = ""
	func _save_session() -> void: pass
	func _poll(_force: bool = false) -> void: pass
	func _check_client_version() -> void: pass
	func _refresh_report_scope() -> void: report_scope = ""
	func _server_now() -> float: return float(state.get("server_time", 1900000000))
	func _request(_path: String, payload: Dictionary, kind: String, _method: int = HTTPClient.METHOD_POST) -> void:
		if kind in ["action", "preview"]: commands.append(payload.duplicate(true))

var checks: int = 0
var failures: int = 0
var client: OfflineClient
var shots: String = ""

func _ready() -> void: run.call_deferred()
func expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(message)
func settle() -> void:
	for frame: int in range(6): await get_tree().process_frame
func shot(name: String) -> void:
	if shots.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(shots.path_join(name + ".png"))
func labels(node: Node) -> String:
	var result: String = str(node.text) + "\n" if node is Label or node is Button else ""
	for child: Node in node.get_children(): result += labels(child)
	return result
func fresh_client(locale: String) -> void:
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

func run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if args.size() > 1:
		shots = args[1]
		DirAccess.make_dir_recursive_absolute(shots)
	var root: Window = get_tree().root
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720,1280)
	root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	root.size = Vector2i(720,1600)
	fresh_client("en")
	client._apply_state(fixture["fresh"]["en"])
	await settle()
	expect(client.planetary_ui.summary.visible, "Planet summary is present")
	expect(client.planetary_ui.summary.text.contains("Slots"), "Slots visible on colony screen")
	expect(client.building_rows.has("observatory"), "Observatory is a real upgrade card")
	expect(not client.building_rows["observatory"]["action"].disabled, "Affordable observatory is buildable")
	client.building_rows["observatory"]["action"].pressed.emit()
	expect(client.commands[-1].get("key") == "observatory", "Upgrade sends observatory to server")
	for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520)]:
		root.size = dimensions
		await settle()
		for button: Button in client.nav_buttons:
			expect(button.get_global_rect().end.y <= client.size.y + 1, "Navigation fits screen")
		expect(client.planetary_ui.summary.get_global_rect().end.x <= client.size.x + 1, "Summary fits width")
	root.size = Vector2i(720,1600)
	client._open_tab(1)
	client._show_full_galaxy_map()
	await settle()
	await shot("unknown_galaxy_en")
	client._choose_system(str(fixture["unknown_system"]))
	client.galaxy_overview.hide()
	client.compact_ui.sync_galaxy()
	client._refresh_system_planets()
	await settle()
	expect(labels(client.planet_list).contains("Scout system"), "Unknown system has a scout action")
	expect(not labels(client.planet_list).contains("Orion"), "Unknown target owner is hidden")
	for child: Node in client.planet_list.get_children():
		if child is Button and child.text == "Scout system": child.pressed.emit(); break
	await settle()
	expect(client.mission_picker.selected == 0 and not client.selected_target.is_empty(), "Scout bearing reaches fleet composer")
	expect(client.planetary_ui.unknown_target(client.selected_target), "Unknown target remains tagged")
	client._apply_state(fixture["basic"]["en"])
	client.compact_ui._open_planet(str(fixture["target_id"]))
	await settle()
	expect(labels(client.compact_ui.modal_body).contains("Orion"), "Basic observation reveals owner")
	expect(not labels(client.compact_ui.modal_body).contains("Buildings · live view"), "Basic observation hides building details")
	client.compact_ui.close_details()
	client._apply_state(fixture["advanced"]["en"])
	client.compact_ui._open_planet(str(fixture["target_id"]))
	await settle()
	expect(labels(client.compact_ui.modal_body).contains("Buildings · live view"), "Advanced observation shows live buildings")
	expect(labels(client.compact_ui.modal_body).contains("level 7"), "Current observed level is shown")
	client._apply_state(fixture["advanced_changed"]["en"])
	await settle()
	expect(labels(client.compact_ui.modal_body).contains("level 8"), "Open planet panel refreshes live after poll")
	await shot("observed_planet_en")
	client.compact_ui.close_details()
	client._open_tab(1)
	client._show_full_galaxy_map()
	await settle()
	await shot("observed_galaxy_en")
	client._apply_state(fixture["scouted"]["en"])
	client.compact_ui._open_planet(str(fixture["target_id"]))
	await settle()
	expect(labels(client.compact_ui.modal_body).contains("no live updates"), "Scout observation is visibly historical")
	expect(not labels(client.compact_ui.modal_body).contains("Buildings · live view"), "Scout does not masquerade as live building data")
	client.compact_ui.close_details()
	client._apply_state(fixture["full"]["en"])
	for key: String in client.building_rows:
		expect(client.building_rows[key]["action"].disabled, "Full planet disables building upgrade: " + key)
	for locale: String in ["pl","de","es","fr"]:
		fresh_client(locale)
		client._apply_state(fixture["advanced"][locale])
		await settle()
		expect(client.planetary_ui.summary.get_global_rect().end.x <= client.size.x + 1, "Localized summary fits: " + locale)
		client.compact_ui._open_catalog(client.building_rows["observatory"])
		await settle()
		expect(client.compact_ui.modal_body.size.x <= client.size.x, "Localized observatory details fit: " + locale)
		if locale == "pl":
			await shot("observatory_pl")
			client.compact_ui.close_details()
			client._open_tab(0)
			await settle()
			await shot("colony_slots_pl")
			client.planetary_ui.summary.pressed.emit()
			await settle()
			await shot("planet_conditions_pl")
		client.compact_ui.close_details()
	print("Planetary UI 0.9.0: %d checks, %d failures" % [checks,failures])
	get_tree().quit(1 if failures else 0)
