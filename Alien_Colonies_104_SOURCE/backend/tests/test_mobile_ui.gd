extends SceneTree
## Local UI smoke test. No production HTTPRequest, polling or saved-session access.
## Generate fixture with tests/make_ui_fixture.py first, then run:
## godot --headless --path . --script tests/test_mobile_ui.gd -- /tmp/pogranicze-ui-fixture.json
## An optional second argument writes PNGs when a real display renderer is present.

class OfflineClient:

	extends "res://client/scripts/main.gd"

	var intercepted_requests: Array[Dictionary] = []

	func _ready() -> void:
		# Deliberately do not call super: it restores sessions and starts remote polling.
		theme = _make_theme()
		var background: ColorRect = ColorRect.new()
		background.color = ProjectSettings.get_setting("rendering/environment/defaults/default_clear_color")
		background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		background.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(background)
		_make_login()
		_make_app()
		_make_update_overlay()
		server_url = "http://127.0.0.1:1"
		baked_server_url = server_url
		server_field.text = server_url
		_refresh_connection_hint()
		set_process(false)

	func _notification(_what: int) -> void:
		pass

	func _request(path: String, payload: Dictionary, kind: String, method: int = HTTPClient.METHOD_POST) -> void:
		intercepted_requests.append({"path": path, "payload": payload, "kind": kind, "method": method})

	func _check_client_version() -> void:
		pass

	func _save_session() -> void:
		pass


var failures: Array[String] = []
var checks: int = 0
var client: OfflineClient
var screenshot_directory: String = ""


func _test_planet_geometry() -> void:
	var planet: Control = load("res://client/scripts/planet_art.gd").new()
	planet.custom_minimum_size = Vector2(112, 112)
	root.add_child(planet)
	_expect(planet.custom_minimum_size == Vector2(112, 112), "Planet illustration honors compact hero minimum")
	for radius: float in [10.0, 38.08, 61.2]:
		for shade: int in range(18):
			var horizontal: float = lerpf(-0.5, 0.85, float(shade) / 17.0)
			var shadow: PackedVector2Array = planet._night_side_polygon(Vector2(90, 90), radius, horizontal)
			_expect(not Geometry2D.triangulate_polygon(shadow).is_empty(), "Planet night-side triangulates at radius %s shade %d" % [radius, shade])
		for band: int in range(13):
			var y: float = -radius + float(band) * radius * 2.0 / 13.0
			var y_next: float = minf(y + radius * 2.0 / 13.0 + 1.0, radius)
			var latitude: PackedVector2Array = planet._latitude_band_polygon(Vector2(90, 90), radius, y, y_next)
			_expect(not Geometry2D.triangulate_polygon(latitude).is_empty(), "Planet latitude triangulates at radius %s band %d" % [radius, band])
	planet.free()


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures.append(description)
		push_error(description)


func _settle() -> void:
	for _index: int in range(8):
		await process_frame


func _find_button(node: Node, caption: String, tooltip: String = "") -> Button:
	if node is Button and ((not caption.is_empty() and node.text == caption) or (not tooltip.is_empty() and node.tooltip_text == tooltip)):
		return node as Button
	for child: Node in node.get_children():
		var found: Button = _find_button(child, caption, tooltip)
		if found != null:
			return found
	return null


func _check_child_widths(node: Node, limits: Rect2, description: String) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var bounds: Rect2 = child.get_global_rect()
			_expect(bounds.position.x >= limits.position.x - 1.0 and bounds.end.x <= limits.end.x + 1.0,
				"%s fits width: %s %s within %s" % [description, child.get_class(), bounds, limits])
			_check_child_widths(child, limits, description)


func _test_compact_features(initial: Dictionary) -> void:
	client._apply_state(initial)
	client._notify("Połączono • świat zapisany na serwerze")
	_expect(not client.connection_label.visible, "Routine connected message is hidden")
	client._notify("Test błędu połączenia", true)
	_expect(client.connection_label.visible, "Connection error remains visible")
	client._notify("Połączono • świat zapisany na serwerze")
	var menu: Button = _find_button(client, "", "Ustawienia i połączenie")
	_expect(menu != null, "Settings menu control exists")
	if menu != null:
		var panel: Control = client.options_panel.get_parent()
		_expect(not panel.visible, "Connection settings start collapsed")
		menu.pressed.emit()
		_expect(panel.visible, "Settings button opens connection menu")
		menu.pressed.emit()
		_expect(not panel.visible, "Settings button closes connection menu")
	var controls: Dictionary = client.building_rows["metal_mine"]
	var description: Label = controls["description"]
	_expect(not description.visible, "Building description starts collapsed")
	var details: Button = _find_button(description.get_parent(), "i")
	_expect(details != null, "Building information button exists")
	if details != null:
		details.pressed.emit()
		_expect(description.visible, "Information button expands description")
		client._apply_state(initial.duplicate(true))
		_expect(description.visible, "Polling preserves expanded description")
		details.pressed.emit()
		_expect(not description.visible, "Information button collapses description")
	var ship: Dictionary = client.ship_rows["scout"]
	var amount = ship["amount"]
	var entry: Dictionary = ship["entry"]
	amount.value = 3
	for key: String in client.RESOURCE_KEYS:
		var price: Label = ship["costs"][key]["amount"]
		_expect(price.text == client._number(float(entry["cost"].get(key, 0)) * 3.0), "Ship price updates for three ships: " + key)
	_expect(ship["time"].text == client._duration(float(entry["seconds"]) * 3.0), "Ship duration updates for three ships")
	var poor: Dictionary = initial.duplicate(true)
	poor["resources"] = {"metal": 0, "crystal": 0, "fuel": 0}
	client._apply_state(poor)
	_expect(ship["action"].disabled, "Insufficient aggregate resources disable ship build")
	_expect(ship["reason"].visible, "Insufficient resource reason remains visible")
	client._apply_state(initial)
	amount.value = 1
	await _settle()


func _capture(name: String) -> void:
	if screenshot_directory.is_empty() or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var rendered: Image = root.get_texture().get_image()
	if rendered != null and not rendered.is_empty():
		var error: Error = rendered.save_png(screenshot_directory.path_join(name + ".png"))
		_expect(error == OK, "Screenshot saved: " + name)


func _run() -> void:
	var arguments: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if arguments.is_empty():
		push_error("Supply the local JSON fixture path after --.")
		quit(2)
		return
	var fixture: Variant = JSON.parse_string(FileAccess.get_file_as_string(arguments[0]))
	if not fixture is Dictionary:
		push_error("The local UI fixture must be a JSON dictionary.")
		quit(2)
		return
	if arguments.size() >= 2:
		screenshot_directory = arguments[1]
		DirAccess.make_dir_recursive_absolute(screenshot_directory)
	root.content_scale_size = Vector2i(720, 1280)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.size = Vector2i(720, 1280)
	_test_planet_geometry()
	client = OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await _settle()
	client._show_login()
	await _settle()
	_expect(client.login_screen.visible, "Login is visible without any network request")
	await _capture("login")
	client._apply_state(fixture["initial"])
	await _settle()
	_expect(client.app_screen.visible, "Offline server fixture opens empire UI")
	_expect(client.tabs.size() == 5, "All five navigation sections remain available")
	_expect(client.building_rows.size() == 6, "All six building types remain available")
	_expect(client.ship_rows.size() == 5, "All five ship types remain available")
	_expect(client.research_rows.size() == 2, "Both research types remain available")
	for key: String in client.ui_textures:
		_expect(client.ui_textures[key] is Texture2D, "Graphical UI asset loads: " + key)
	for index: int in range(client.tabs.size()):
		client._open_tab(index)
		await _settle()
		var rect: Rect2 = client.tabs[index].get_global_rect()
		_expect(client.tabs[index].visible, "Tab %d is visible" % index)
		_expect(rect.position.x >= -1.0 and rect.end.x <= 721.0, "Tab %d fits phone width" % index)
		_expect(rect.size.y >= 350.0, "Tab %d has usable vertical content space" % index)
		_check_child_widths(client.tab_bodies[index], rect, "Tab %d" % index)
		await _capture("tab_%d" % index)
		if index == 2:
			client._set_fleet_mode(1)
			await _settle()
			_check_child_widths(client.tab_bodies[index], rect, "Fleet construction")
			client._set_fleet_mode(0)
		print("UI_LAYOUT tab=%d rect=%s content=%s" % [index, rect, client.tab_bodies[index].size])
	client._open_tab(0)
	client._apply_state(fixture["building"])
	await _settle()
	_expect(client.queue_end > 0.0, "Active build queue displays")
	_expect(client.queue_bar.visible, "Active build displays graphical queue progress")
	var initial_progress: float = client.queue_bar.value
	client.received_at_msec -= int(client.queue_duration * 500.0)
	client._update_clock()
	_expect(client.queue_bar.value > initial_progress, "Queue progress advances with elapsed local time")
	var halfway_progress: float = client.queue_bar.value
	client.received_at_msec -= int(client.queue_duration * 250.0)
	client._update_clock()
	_expect(client.queue_bar.value >= halfway_progress and client.queue_bar.value <= 100.0, "Queue progress is monotonic and bounded")
	await _capture("building")
	client._apply_state(fixture["completed"])
	await _settle()
	_expect(client.queue_end == 0.0, "Completed build clears queue")
	_expect(not client.queue_bar.visible, "Completed build hides graphical queue progress")
	_expect(int(client.state["buildings"]["metal_mine"]) == 2, "Completed build updates level")
	for button: Button in client.nav_buttons:
		var rect: Rect2 = button.get_global_rect()
		_expect(rect.end.x <= 721.0 and rect.end.y <= 1281.0, "Navigation button fits viewport")
	_expect(client.intercepted_requests.is_empty(), "Smoke test makes zero network requests")
	_expect(client.http == null and client.poll_timer == null, "No HTTP client or polling timer constructed")
	await _test_compact_features(fixture["initial"])
	# Trigger existing action signals only against the intercepted local transport.
	var build_button: Button = client.building_rows["metal_mine"]["action"]
	build_button.pressed.emit()
	_expect(client.intercepted_requests.size() == 1, "Build action remains connected")
	if not client.intercepted_requests.is_empty():
		var build_request: Dictionary = client.intercepted_requests.back()
		_expect(build_request["path"] == "/api/action", "Build keeps authoritative action endpoint")
		_expect(build_request["payload"].get("type") == "build" and build_request["payload"].get("key") == "metal_mine", "Build carries the selected catalog key")
		_expect(not str(build_request["payload"].get("request_id", "")).is_empty(), "Build retains idempotency request ID")
	var research_button: Button = client.research_rows["propulsion"]["action"]
	research_button.pressed.emit()
	_expect(client.intercepted_requests.back()["payload"].get("type") == "research", "Research action remains connected")
	var ship_button: Button = client.ship_rows["scout"]["action"]
	ship_button.pressed.emit()
	_expect(client.intercepted_requests.back()["payload"].get("type") == "ship", "Ship construction remains connected")
	_expect(int(client.intercepted_requests.back()["payload"].get("amount", 0)) == 1, "Ship action carries selected amount")
	# A short portrait viewport must keep navigation usable, not force the whole root tall.
	root.content_scale_size = Vector2i(720, 1000)
	root.size = Vector2i(720, 1000)
	await _settle()
	for button: Button in client.nav_buttons:
		var short_rect: Rect2 = button.get_global_rect()
		_expect(short_rect.end.x <= 721.0 and short_rect.end.y <= 1001.0, "Navigation fits short portrait viewport")
	_expect(client.tabs[0].size.y >= 200.0, "Short portrait viewport leaves scrollable content space")
	await _capture("short_portrait")
	var large_resources: Dictionary = fixture["initial"].duplicate(true)
	large_resources["resources"] = {"metal": 9876543210.0, "crystal": 8765432109.0, "fuel": 7654321098.0}
	large_resources["production"] = {"metal": 9876543.0, "crystal": 8765432.0, "fuel": 7654321.0}
	client._apply_state(large_resources)
	root.content_scale_size = Vector2i(600, 1000)
	root.size = Vector2i(600, 1000)
	await _settle()
	for index: int in range(client.tabs.size()):
		client._open_tab(index)
		await _settle()
		var narrow_rect: Rect2 = client.tabs[index].get_global_rect()
		_expect(narrow_rect.end.x <= 601.0, "Narrow tab %d fits viewport" % index)
		_check_child_widths(client.tab_bodies[index], narrow_rect, "Narrow tab %d" % index)
		await _capture("narrow_tab_%d" % index)
		if index == 2:
			client._set_fleet_mode(1)
			await _settle()
			_check_child_widths(client.tab_bodies[index], narrow_rect, "Narrow fleet construction")
			client._set_fleet_mode(0)
	for key: String in client.RESOURCE_KEYS:
		var resource_count: Label = client.resource_labels[key]["count"]
		var card_bounds: Rect2 = resource_count.get_parent().get_global_rect()
		_expect(card_bounds.end.x <= 601.0, "Large resource card fits narrow viewport: " + key)
		_check_child_widths(resource_count.get_parent(), card_bounds, "Large resources " + key)
	if failures.is_empty():
		print("PASS mobile_ui: %d checks; no network access" % checks)
		quit(0)
	else:
		print("FAIL mobile_ui: %d/%d failed" % [failures.size(), checks])
		quit(1)
