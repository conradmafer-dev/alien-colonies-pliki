extends Node
## Actual native controller/UI with all command writes intercepted.
const Model = preload("res://client/scripts/fleet_navigation_model.gd")

class OfflineClient:
	extends "res://client/scripts/main.gd"
	var captured: Array[Dictionary] = []
	var notifications: Array[String] = []
	func _load_session() -> void:
		server_url = "http://127.0.0.1:1"
		baked_server_url = server_url
		session_token = ""
	func _save_session() -> void:
		pass
	func _load_ui_preferences() -> void:
		pass
	func _poll(_force: bool = false) -> void:
		pass
	func _check_client_version() -> void:
		pass
	func _refresh_report_scope() -> void:
		report_scope = ""
	func _notify(message: String, _error: bool = false) -> void:
		notifications.append(message)
	func _request(path: String, payload: Dictionary, kind: String, _method: int = HTTPClient.METHOD_POST) -> void:
		if request_pending:
			return
		if kind == "action":
			if not uncertain_action.is_empty() and str(uncertain_action.get("request_id", "")) != str(payload.get("request_id", "")):
				return
			uncertain_action = payload.duplicate(true)
		captured.append({"path": path, "payload": payload.duplicate(true), "kind": kind})
		request_kind = kind
		request_pending = true

var checks: int = 0
var failed: Array[String] = []
var client: OfflineClient
var fixtures: Dictionary
var source_id: String
var free_id: String
var other_id: String
var unknown_id: String = "s2p1"

func _ready() -> void:
	_run.call_deferred()

func expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failed.append(message)
		push_error(message)

func settle(frames: int = 8) -> void:
	for _frame: int in range(frames):
		await get_tree().process_frame

func pause(seconds: float = 0.65) -> void:
	await get_tree().create_timer(seconds).timeout
	await settle()

func count_kind(kind: String) -> int:
	var count: int = 0
	for request: Dictionary in client.captured:
		if request["kind"] == kind:
			count += 1
	return count

func sample(locale: String = "en") -> Dictionary:
	var world: Dictionary = fixtures["zetans"][locale].duplicate(true)
	source_id = str(world["planet_id"])
	var home: Dictionary = Model.target(world, source_id)["planet"].duplicate(true)
	free_id = "s1p1" if source_id != "s1p1" else "s1p2"
	other_id = "s1p3" if source_id != "s1p3" else "s1p4"
	var free: Dictionary = home.duplicate(true)
	free.merge({"id": free_id, "name": "TEST Unclaimed", "system_id": "s1", "owner_type": "empty", "owner_id": "", "owner_name": "", "alliance_id": "", "protected_until": 0}, true)
	var other: Dictionary = home.duplicate(true)
	other.merge({"id": other_id, "name": "TEST Second Colony", "system_id": "s1"}, true)
	home["system_id"] = "s1"
	world["planet_galaxy_id"] = "g1"
	world["galaxy"] = [
		{"id": "s1", "name": "TEST Home System", "galaxy_id": "g1", "x": 1, "y": 1, "visibility": "observed", "planets": [home, free, other]},
		{"id": "s2", "name": "TEST Uncharted", "galaxy_id": "g1", "x": 2, "y": 2, "visibility": "unknown", "planets": [], "scout_target_id": unknown_id},
	]
	world["own_planets"] = [home, other]
	world["fleets"] = []
	for key: String in world["ships"]:
		world["ships"][key] = 0
	world["ships"].merge({"scout": 3, "colonizer": 2, "cargo": 2, "frigate": 8}, true)
	return world

func new_client(locale: String = "en") -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client)
		client.queue_free()
	I18n.set_locale(locale, false)
	client = OfflineClient.new()
	get_tree().root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.communications.timer.stop()
	client._apply_state_now(sample(locale), Time.get_ticks_msec())
	client.session_token = "OFFLINE-TEST-ONLY"

func respond_quote(affordable: bool = true, fuel: int = 432) -> void:
	expect(client.request_kind == "preview" and client.request_pending, "Automatic preview is waiting for server")
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"ok": true, "seconds": 1234, "fuel_cost": fuel, "capacity": 9000, "affordable": affordable, "shortfall": {"fuel": 123 if not affordable else 0}, "message": ""}).to_utf8_buffer())

func _run() -> void:
	var fixture_path: String = "res://backend/tests/fixtures/android_0112.json"
	if not FileAccess.file_exists(fixture_path):
		fixture_path = "res://tests/fixtures/android_0112.json"
	fixtures = JSON.parse_string(FileAccess.get_file_as_string(fixture_path))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720, 1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	window.size = Vector2i(720, 1600)
	new_client()
	await settle()
	var ui = client.fleet_navigation
	client._start_new_mission()
	await settle()
	expect(ui._map_open(), "New mission opens destination map")
	expect(client.compact_ui.modal_missions.visible and client.compact_ui.modal_close.visible, "Active missions and Back visible in map")
	expect(not client.preview_button.visible, "No mandatory Check route action")
	expect(ui.choose_button.get_parent() != ui.dock_summary.get_parent(), "Change destination belongs to target card, not dock")
	await pause()
	expect(count_kind("preview") == 0 and count_kind("action") == 0, "No quote or dispatch for missing destination")
	client.fleet_inputs["frigate"].value = 3
	client.cargo_inputs["metal"].value = 80
	ui._select_system("s1")
	await settle()
	expect(ui.picker_planets.is_visible_in_tree(), "Selecting system reveals planets immediately")
	expect(not ui.picker_map.is_visible_in_tree(), "Galaxy map does not push planet selection below fold")
	expect(ui.picker_planets.get_child_count() == 3, "Known system lists its actual planets")
	ui._show_system_map()
	await settle()
	expect(ui.picker_map.is_visible_in_tree(), "Return from planet panel restores galaxy map")
	expect(int(client.fleet_inputs["frigate"].value) == 3 and int(client.cargo_inputs["metal"].value) == 80, "Map navigation preserves fleet and cargo")
	ui._select_system("s1")
	ui._select_destination(free_id)
	await settle()
	expect(not ui._map_open() and client.compact_ui.composing, "Planet selection returns directly to fleet form")
	expect(client.selected_planet == source_id and client.selected_target == free_id, "Target selection never changes origin")
	expect(client.mission_picker.selected == 1 and int(client.fleet_inputs["colonizer"].value) == 1, "Free target chooses colonization and required ship")
	expect(int(client.fleet_inputs["frigate"].value) == 3 and int(client.cargo_inputs["metal"].value) == 80, "Target selection retains escort and supplies")
	expect(client.send_button.disabled, "Send disabled before server quote")
	client.send_button.pressed.emit()
	expect(count_kind("action") == 0, "Premature activation never sends")
	await pause()
	expect(count_kind("preview") == 1, "A stable completed draft automatically requests one server quote")
	expect(count_kind("action") == 0, "Automatic quote never automatically sends")
	# Change while old server response is in flight. Old quote must not unlock send.
	client.fleet_inputs["frigate"].value = 4
	await pause()
	expect(count_kind("preview") == 1, "No overlapping preview requests while server is busy")
	respond_quote(true, 111)
	await settle()
	expect(not client.quote_ready and client.send_button.disabled, "Stale quote cannot enable dispatch")
	await pause()
	expect(count_kind("preview") == 2, "Latest draft gets its quote after stale response completes")
	expect(int(client.captured[-1]["payload"]["ships"]["frigate"]) == 4, "Automatic retry quotes latest ship quantities")
	respond_quote(false)
	await settle()
	expect(client.send_button.disabled, "Unaffordable authoritative quote blocks send")
	expect(ui.dock_summary.get_parsed_text().contains("123"), "Exact resource deficit visible beside send")
	var before: int = count_kind("preview")
	await pause()
	expect(count_kind("preview") == before, "Unaffordable quote does not produce an automatic retry loop")
	# Debounce burst of quantity edits, cargo edits and manual text commit.
	client.fleet_inputs["frigate"].value = 5
	await get_tree().create_timer(0.10).timeout
	client.cargo_inputs["metal"].value = 90
	await get_tree().create_timer(0.10).timeout
	client.fleet_inputs["frigate"].value = 6
	await pause()
	expect(count_kind("preview") == before + 1, "Rapid edits debounce into one quote")
	expect(int(client.captured[-1]["payload"]["cargo"]["metal"]) == 90, "Cargo changes included in automatic quote")
	respond_quote()
	await settle()
	expect(not client.send_button.disabled and client.quote_ready, "Only current affordable server quote unlocks send")
	expect(ui.dock_summary.get_parsed_text().contains("432"), "Dock shows exact server fuel")
	expect(ui.dock_summary.get_parsed_text().contains("90"), "Dock shows current cargo")
	expect(count_kind("action") == 0, "Receiving an affordable quote still never sends")
	await pause()
	expect(count_kind("preview") == before + 1, "Accepted stable quote is reused, not polled repeatedly")
	client.send_button.pressed.emit()
	await settle()
	expect(count_kind("action") == 1, "One deliberate send activation dispatches immediately")
	expect(not client.compact_ui.details_open(), "No mandatory confirmation modal")
	expect(client.captured[-1]["path"] == "/api/action", "Dispatch uses established authenticated action endpoint")
	expect(client.captured[-1]["payload"]["target_id"] == free_id, "Dispatch targets selected planet")
	expect(int(client.captured[-1]["payload"]["ships"]["frigate"]) == 6, "Dispatch uses exact quoted ships")
	expect(int(client.captured[-1]["payload"]["cargo"]["metal"]) == 90, "Dispatch uses exact quoted cargo")
	expect(not str(client.captured[-1]["payload"].get("request_id", "")).is_empty(), "Dispatch retains idempotency request ID")
	client.send_button.pressed.emit()
	ui.dispatch_departure()
	await pause()
	expect(count_kind("action") == 1, "Rapid repeated activation cannot send twice")
	# Uncertain command blocks new quotes and later dispatch until reconciled.
	client._on_response(HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), "{}".to_utf8_buffer())
	client.fleet_inputs["frigate"].value = 5
	await pause()
	expect(count_kind("action") == 1 and client.send_button.disabled, "Uncertain dispatch cannot be replaced by a fresh send")
	# Research changes while pricing must invalidate an otherwise identical payload.
	new_client("en")
	await settle()
	ui = client.fleet_navigation
	client._start_new_mission()
	ui._select_destination(other_id)
	client.fleet_inputs["cargo"].value = 1
	await pause()
	expect(client.request_kind == "preview", "World-race preview is in flight")
	var changed_world: Dictionary = client.state.duplicate(true)
	changed_world["research"]["propulsion"] = int(changed_world.get("research", {}).get("propulsion", 0)) + 1
	client._apply_state_now(changed_world, Time.get_ticks_msec())
	respond_quote(true, 777)
	await settle()
	expect(not client.quote_ready and client.send_button.disabled, "World stat change while pricing rejects obsolete quote")
	await pause()
	expect(client.request_kind == "preview", "World stat change automatically requests a fresh quote")
	respond_quote()
	await settle()
	expect(not client.send_button.disabled, "Fresh world quote restores send")
	client.cargo_inputs["metal"].value = 10
	await pause()
	expect(client.request_kind == "preview", "ABA test has a quote in flight")
	client.cargo_inputs["metal"].value = 11
	client.cargo_inputs["metal"].value = 10
	respond_quote(true, 333)
	await settle()
	expect(client.send_button.disabled, "Changing a draft away and back rejects the older generation")
	await pause()
	expect(client.request_kind == "preview", "ABA rejection still schedules a fresh current-generation quote")
	respond_quote()
	await settle()
	expect(not client.send_button.disabled, "ABA refresh recovers without a manual Check route")
	# A usable wormhole is another payload edit, never an unpriced route switch.
	client.state["megastructures"] = {"gate_level": 1, "origin_id": source_id, "energy": 1000, "capacity": 1000, "window": {"id": "OFFLINE-WINDOW", "target_id": other_id, "ready_at": client._server_now() - 1.0, "closes_at": client._server_now() + 3600.0}}
	client.megastructure_ui.tick()
	expect(not client.megastructure_ui.travel_mode.disabled, "Synthetic wormhole is actually usable")
	client.megastructure_ui.travel_mode.button_pressed = true
	expect(client.send_button.disabled, "Travel mode edit immediately invalidates normal-flight quote")
	await pause()
	expect(client.request_kind == "preview" and str(client.captured[-1]["payload"].get("travel_mode", "")) == "tunnel", "Travel mode change automatically requests authoritative tunnel quote")
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"ok": true, "seconds": 2, "fuel_cost": 5, "capacity": 9000, "affordable": false, "shortfall": {"fuel": 123}, "tunnel": {"energy_shortfall": 17}}).to_utf8_buffer())
	await settle()
	expect(client.send_button.disabled and ui.dock_summary.get_parsed_text().contains("123") and ui.dock_summary.get_parsed_text().contains("17"), "Tunnel fuel and energy deficits are exact and block send")
	# Start a separate clean client for cancellation, request queue and invalid data.
	new_client("pl")
	await settle()
	ui = client.fleet_navigation
	client._start_new_mission()
	ui._select_destination(other_id)
	client.fleet_inputs["cargo"].value = 1
	client.cargo_inputs["metal"].value = 45
	client.compact_ui.close_composer()
	await pause()
	expect(count_kind("preview") == 0, "Leaving composer cancels pending automatic quote")
	client.compact_ui.open_composer()
	await pause()
	expect(count_kind("preview") == 1, "Reopening a valid draft resumes automatic pricing")
	respond_quote()
	await settle()
	ui.open_destination_map()
	await settle()
	client.compact_ui.close_details()
	await settle()
	expect(client.selected_target == other_id and int(client.fleet_inputs["cargo"].value) == 1 and int(client.cargo_inputs["metal"].value) == 45, "Back from map preserves complete draft")
	expect(not client.send_button.disabled, "Returning unchanged map preserves valid quote")
	ui.open_destination_map()
	ui._select_system("s2")
	await settle()
	expect(ui.picker_planets.get_child_count() == 1, "Unknown system exposes recon action without fabricated planets")
	ui._select_destination(unknown_id)
	await pause()
	expect(client.mission_picker.selected == 0 and int(client.fleet_inputs["scout"].value) == 1, "Unknown target chooses scout and required ship")
	expect(ui.route_view.target_texture == null and not ui.details_button.visible, "Unknown planet art and details remain hidden")
	respond_quote()
	await settle()
	client.mission_picker.select(0)
	client._mission_changed(0)
	await pause()
	expect(client.request_kind == "preview", "Mission change automatically refreshes quote")
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"ok": true, "seconds": 0, "fuel_cost": 0, "capacity": 0, "affordable": true}).to_utf8_buffer())
	await settle()
	expect(client.send_button.disabled and not client.quote_ready, "Malformed quote never becomes free instant dispatch")
	before = count_kind("preview")
	await pause()
	expect(count_kind("preview") == before, "Malformed server data does not trigger an infinite retry loop")
	expect(client.preview_button.visible, "Explicit retry appears after malformed server data")
	ui.retry_quote()
	await pause()
	expect(client.request_kind == "preview", "Explicit retry obtains a new automatic quote")
	respond_quote()
	await settle()
	client.fleet_inputs["scout"].editor.grab_focus()
	client.fleet_inputs["scout"].editor.text = "2"
	client.fleet_inputs["scout"].editor.text_changed.emit("2")
	expect(client.send_button.disabled, "Uncommitted quantity text immediately locks send")
	await pause()
	expect(client.request_kind == "preview" and int(client.captured[-1]["payload"]["ships"]["scout"]) == 2, "Focused quantity text is committed automatically before quote")
	respond_quote()
	await settle()
	before = count_kind("preview")
	client.fleet_inputs["scout"].editor.text = "x"
	client.fleet_inputs["scout"].editor.text_changed.emit("x")
	await pause()
	expect(client.send_button.disabled and count_kind("preview") == before, "Invalid number text neither prices nor dispatches an old value")
	client.fleet_inputs["scout"].editor.text = "1"
	client.fleet_inputs["scout"].editor.text_changed.emit("1")
	await pause()
	expect(client.request_kind == "preview" and int(client.captured[-1]["payload"]["ships"]["scout"]) == 1, "Correcting number text resumes pricing without extra click")
	respond_quote()
	await settle()
	# Layout assertions in narrow and tall portrait windows, both user languages.
	for locale: String in ["en", "pl"]:
		new_client(locale)
		await settle()
		ui = client.fleet_navigation
		client._start_new_mission()
		ui._select_destination(other_id)
		client.fleet_inputs["cargo"].value = 1
		client.cargo_inputs["metal"].value = 45
		await pause()
		respond_quote()
		await settle()
		for dimensions: Vector2i in [Vector2i(360, 780), Vector2i(720, 1280), Vector2i(720, 1600), Vector2i(1080, 2400)]:
			window.size = dimensions
			await settle(12)
			expect(ui.route_view.size.x <= client.size.x + 1, "Route fits %s %s" % [locale, dimensions])
			expect(client.send_button.get_global_rect().end.y <= client.get_global_rect().end.y + 2, "Send remains inside viewport %s %s" % [locale, dimensions])
			expect(ui.dock_summary.get_global_rect().end.y <= client.send_button.get_global_rect().position.y + 2, "Quote stays above send %s %s" % [locale, dimensions])
			expect(client.fleet_active_button.is_visible_in_tree(), "Active missions remain visible in composer %s %s" % [locale, dimensions])
			expect(client.fleet_mode_buttons[0].is_visible_in_tree() and client.fleet_mode_buttons[0].text == I18n.t("Wstecz"), "Back remains visible in composer %s %s" % [locale, dimensions])
			ui.open_destination_map()
			ui._select_system("s1")
			await settle()
			expect(client.compact_ui.modal_missions.is_visible_in_tree() and client.compact_ui.modal_close.is_visible_in_tree(), "Map navigation stays visible %s %s" % [locale, dimensions])
			expect(ui.picker_planets.get_global_rect().position.y < client.size.y * 0.55, "Planets begin near top of screen %s %s" % [locale, dimensions])
			client.compact_ui.close_details()
			await settle()
	var report: Dictionary = {"result": "PASS" if failed.is_empty() else "FAIL", "checks": checks, "failures": failed.size(), "failed_checks": failed}
	var report_file: FileAccess = FileAccess.open("res://runtime_report.json", FileAccess.WRITE)
	report_file.store_string(JSON.stringify(report, "  "))
	report_file.close()
	print("Android fleet87: %d checks; %d failures" % [checks, failed.size()])
	get_tree().quit(1 if not failed.is_empty() else 0)
