extends "res://tests/android_fleet87_regression.gd"
## Full client layout/navigation checks with all network writes intercepted.
const MapCanvas = preload("res://client/scripts/galaxy_map.gd")

var metrics: Array[Dictionary] = []
var screenshots: Array[String] = []

func sample(locale: String = "en") -> Dictionary:
	var world: Dictionary = super.sample(locale)
	world["galaxy"].append({"id": "s99", "name": "TEST Second Galaxy", "galaxy_id": "g2", "x": 1, "y": 1, "visibility": "unknown", "planets": [], "scout_target_id": "s99p1"})
	return world

func rect_data(control: Control) -> Dictionary:
	var rect: Rect2 = control.get_global_rect()
	return {"x": rect.position.x, "y": rect.position.y, "width": rect.size.x, "height": rect.size.y, "bottom": rect.end.y}

func escape() -> void:
	var press: InputEventKey = InputEventKey.new()
	press.keycode = KEY_ESCAPE
	press.physical_keycode = KEY_ESCAPE
	press.pressed = true
	# Route through the viewport, including focused controls and unhandled input.
	get_tree().root.push_input(press, true)
	await settle()
	var release: InputEventKey = press.duplicate()
	release.pressed = false
	get_tree().root.push_input(release, true)
	await settle()

func pan_map(map: Control) -> void:
	var origin: Vector2 = map.size * 0.5
	var press: InputEventMouseButton = InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = origin
	map._gui_input(press)
	var drag: InputEventMouseMotion = InputEventMouseMotion.new()
	drag.position = origin + Vector2(36, -24)
	drag.relative = Vector2(36, -24)
	drag.button_mask = MOUSE_BUTTON_MASK_LEFT
	map._gui_input(drag)
	var release: InputEventMouseButton = press.duplicate()
	release.pressed = false
	release.position = drag.position
	map._gui_input(release)

func capture_stage(stage: String, dimensions: Vector2i, locale: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args() or locale != "pl":
		return
	if DisplayServer.get_name() == "headless":
		expect(false, "Screenshot capture requires a rendering display")
		return
	await RenderingServer.frame_post_draw
	var folder: String = "res://tests/fleet_destination88_screenshots"
	DirAccess.make_dir_recursive_absolute(folder)
	var path: String = "%s/%s_%dx%d_%s.png" % [folder, locale, dimensions.x, dimensions.y, stage]
	var result: Error = get_viewport().get_texture().get_image().save_png(path)
	expect(result == OK, "Saved screenshot " + path)
	if result == OK:
		screenshots.append(path)

func check_layout(dimensions: Vector2i, locale: String) -> void:
	var ui = client.fleet_navigation
	var compact = client.compact_ui
	var scroll_rect: Rect2 = compact.modal_scroll.get_global_rect()
	var controls_height: float = 0
	var visible_count: int = 0
	for child: Node in ui.picker_map_panel.get_children():
		if child is Control and child.visible:
			visible_count += 1
			if child != ui.picker_map:
				controls_height += child.get_combined_minimum_size().y
	controls_height += ui.picker_map_panel.get_theme_constant("separation") * maxi(0, visible_count - 1)
	var expected_height: float = maxf(260.0, floorf(scroll_rect.size.y - controls_height - 4.0))
	var label: String = "%s %s" % [locale, dimensions]
	expect(absf(ui.picker_map.size.y - expected_height) <= 2.0, "Map uses remaining viewport height " + label)
	expect(ui.picker_map.size.y >= scroll_rect.size.y * 0.65, "Map occupies most of destination content " + label)
	expect(ui.picker_map.get_global_rect().position.y >= scroll_rect.position.y - 1, "Map top lies inside scroll viewport " + label)
	expect(ui.picker_map.get_global_rect().end.y <= scroll_rect.end.y + 1, "Map bottom lies inside scroll viewport " + label)
	expect(ui.picker_systems.get_global_rect().end.y <= scroll_rect.end.y + 1, "System selector stays on screen " + label)
	expect(compact.modal_close.get_global_rect().end.y <= client.get_global_rect().end.y, "Back stays on screen " + label)
	expect(compact.modal_missions.is_visible_in_tree(), "Active missions remain available " + label)
	expect(compact.modal_scroll.scroll_vertical == 0, "No scrolling is required for map controls " + label)
	for child: Node in ui.picker_map_panel.get_children():
		if child is HBoxContainer:
			for button: Node in child.get_children():
				if button is Control:
					expect(button.get_global_rect().end.y <= scroll_rect.end.y + 1, "Navigation or zoom control is on screen " + label)
	metrics.append({"window": [dimensions.x, dimensions.y], "locale": locale,
		"logical_client": [client.size.x, client.size.y], "map": rect_data(ui.picker_map),
		"scroll": rect_data(compact.modal_scroll), "system_selector": rect_data(ui.picker_systems),
		"map_fraction_of_content": ui.picker_map.size.y / scroll_rect.size.y,
		"expected_map_height": expected_height, "zoom": ui.picker_map.get_zoom()})

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720, 1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["en", "pl"]:
		for dimensions: Vector2i in [Vector2i(720, 1280), Vector2i(720, 1600), Vector2i(450, 800)]:
			window.size = dimensions
			new_client(locale)
			await settle(12)
			var ui = client.fleet_navigation
			var compact = client.compact_ui
			client._start_new_mission()
			await settle(12)
			expect(ui._map_open(), "Destination map opens")
			expect(is_equal_approx(ui.picker_map.get_zoom(), MapCanvas.DEFAULT_FOCUS_ZOOM), "Destination map starts at shared Galaxy focus zoom")
			check_layout(dimensions, locale)
			await capture_stage("galaxy", dimensions, locale)
			client.fleet_inputs["frigate"].value = 3
			client.cargo_inputs["metal"].value = 80
			ui.picker_map.zoom_in()
			pan_map(ui.picker_map)
			await settle()
			var saved_pan: Vector2 = ui.picker_map._pan
			var saved_zoom: float = ui.picker_map.get_zoom()
			ui._select_system("s1")
			await settle()
			expect(ui.picker_planet_panel.is_visible_in_tree() and not ui.picker_map_panel.visible, "System selection opens its planet panel")
			await capture_stage("system", dimensions, locale)
			compact.modal_close.pressed.emit()
			await settle()
			expect(ui._map_open() and ui.picker_map_panel.is_visible_in_tree(), "First visible Back returns from system to galaxy")
			expect(not ui.picker_planet_panel.visible, "First Back hides planet panel")
			expect(ui.picker_map._pan.is_equal_approx(saved_pan) and is_equal_approx(ui.picker_map.get_zoom(), saved_zoom), "Back preserves map pan and zoom")
			await capture_stage("back_to_galaxy", dimensions, locale)
			compact.modal_close.pressed.emit()
			await settle()
			expect(not ui._map_open() and compact.composing, "Second visible Back returns to fleet form")
			expect(int(client.fleet_inputs["frigate"].value) == 3 and int(client.cargo_inputs["metal"].value) == 80, "Back preserves chosen ships and cargo")
			ui.open_destination_map()
			await settle()
			ui._change_galaxy(1)
			await settle()
			expect(ui.browse_galaxy == "g2" and is_equal_approx(ui.picker_map.get_zoom(), MapCanvas.DEFAULT_FOCUS_ZOOM), "Changing galaxy starts at shared Galaxy focus zoom")
			ui._select_system("s99")
			await settle()
			get_tree().root.propagate_notification(NOTIFICATION_WM_GO_BACK_REQUEST)
			await settle()
			expect(ui._map_open() and ui.picker_map_panel.visible, "Android Back returns system to galaxy")
			expect(not get_tree().quit_on_go_back, "Android Back is still intercepted inside galaxy picker")
			get_tree().root.propagate_notification(NOTIFICATION_WM_GO_BACK_REQUEST)
			await settle()
			expect(not ui._map_open() and compact.composing, "Second Android Back returns to form")
			ui.open_destination_map()
			await settle()
			ui.picker_galaxy.open()
			await settle()
			expect(ui.picker_galaxy.is_open(), "Galaxy dropdown opens above destination map")
			get_tree().root.propagate_notification(NOTIFICATION_WM_GO_BACK_REQUEST)
			await settle()
			expect(ui._map_open() and ui.picker_map_panel.visible and not ui.picker_galaxy.is_open(), "Android Back dismisses dropdown while preserving map")
			expect(not get_tree().quit_on_go_back, "Closing dropdown keeps map Android Back guard")
			ui.picker_systems.open()
			await settle()
			expect(ui.picker_systems.is_open(), "System dropdown opens above destination map")
			await escape()
			expect(ui._map_open() and ui.picker_map_panel.visible and not ui.picker_systems.is_open(), "Escape dismisses dropdown while preserving map")
			ui._select_system("s1")
			await settle()
			compact.modal_close.grab_focus()
			await escape()
			expect(ui._map_open() and ui.picker_map_panel.visible, "Escape returns system to galaxy")
			await escape()
			expect(not ui._map_open() and compact.composing, "Second Escape returns galaxy to form")
			ui.open_destination_map()
			ui._select_system("s1")
			await settle()
			ui._select_destination(free_id)
			await settle()
			expect(not ui._map_open() and compact.composing and client.selected_target == free_id, "Choosing planet forcibly closes picker directly into composer")
			expect(client.selected_planet == source_id, "Destination selection preserves origin")
			ui.open_destination_map()
			await settle()
			expect(ui.picker_planet_panel.visible, "Reopening an existing destination selects its system")
			expect(is_equal_approx(ui.picker_map.get_zoom(), MapCanvas.DEFAULT_FOCUS_ZOOM), "Reopened destination starts at shared Galaxy focus zoom")
			ui._select_destination(free_id)
			await settle()
			expect(not ui._map_open(), "Choosing unchanged destination also closes picker directly")
			for attempt: int in range(3):
				ui.open_destination_map()
				await settle()
				compact.go_back()
				await settle()
				expect(ui._map_open() and ui.picker_map_panel.visible, "Repeated opening keeps one Back handler")
				compact.go_back()
				await settle()
				expect(not ui._map_open(), "Repeated picker closes on second Back")
			var fit_connections: int = 0
			for connection: Dictionary in compact.modal_scroll.get_signal_connection_list("resized"):
				var handler: Callable = connection["callable"]
				if handler.get_method() == "_fit_destination_map":
					fit_connections += 1
			expect(fit_connections == 1, "Repeated opening retains only one map resize connection")
			compact._begin_details("Ordinary details")
			await settle()
			expect(not compact.modal_back_handler.is_valid(), "Unrelated details clear fleet hierarchy handler")
			compact.go_back()
			await settle()
			expect(not compact.details_open(), "Unrelated details retain single Back close")
	var report: Dictionary = {"result": "PASS" if failed.is_empty() else "FAIL", "checks": checks,
		"failures": failed.size(), "failed_checks": failed, "layout_metrics": metrics, "screenshots": screenshots}
	var output: FileAccess = FileAccess.open("res://tests/fleet_destination88_report.json", FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  "))
	output.close()
	print("Fleet destination88: %d checks; %d failures" % [checks, failed.size()])
	print(JSON.stringify(metrics))
	get_tree().quit(1 if not failed.is_empty() else 0)
