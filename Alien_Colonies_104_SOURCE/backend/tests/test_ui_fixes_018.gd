extends SceneTree
## Offline regressions for the actual phone defects reported in 0.1.7.
## Checks text shaping as well as bounds: a one-digit-wide Label still fits bounds!
## godot --headless --path . --script tests/test_ui_fixes_018.gd -- /path/to/ui-fixture.json
## Uses intercepted transport and does not load credentials or contact a server.

const MobileSmoke = preload("res://tests/test_mobile_ui.gd")

var client: MobileSmoke.OfflineClient
var checks: int = 0
var failures: Array[String] = []


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


func _label(node: Node, caption: String) -> Label:
	if node is Label and node.text == caption:
		return node as Label
	for child: Node in node.get_children():
		var result: Label = _label(child, caption)
		if result != null:
			return result
	return null


func _buttons(node: Node) -> Array[Button]:
	var result: Array[Button] = []
	for child: Node in node.get_children():
		if child is Button:
			result.append(child as Button)
		result.append_array(_buttons(child))
	return result


func _progress(node: Node) -> ProgressBar:
	if node is ProgressBar:
		return node as ProgressBar
	for child: Node in node.get_children():
		var result: ProgressBar = _progress(child)
		if result != null:
			return result
	return null


func _fits_width(control: Control, limits: Rect2, description: String) -> void:
	var bounds: Rect2 = control.get_global_rect()
	_expect(bounds.position.x >= limits.position.x - 1.0 and bounds.end.x <= limits.end.x + 1.0,
		"%s stays in the phone column: %s within %s" % [description, bounds, limits])


func _single_line(caption: Label, description: String) -> void:
	_expect(caption.get_line_count() == 1, description + " reads on one horizontal line")
	var font: Font = caption.get_theme_font("font")
	var font_size: int = caption.get_theme_font_size("font_size")
	var text_width: float = font.get_string_size(caption.text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	_expect(caption.size.x + 1.0 >= text_width,
		"%s retains full glyph width (%s px for %s px text)" % [description, caption.size.x, text_width])


func _check_catalog(rows: Dictionary, tab_index: int, description: String) -> void:
	client._open_tab(tab_index)
	if tab_index == 2:
		client._set_fleet_mode(1)
	await _settle()
	var limits: Rect2 = client.tabs[tab_index].get_global_rect()
	for key: String in rows:
		var controls: Dictionary = rows[key]
		for resource: String in client.RESOURCE_KEYS:
			var item: Dictionary = controls["costs"][resource]
			if item["row"].visible:
				var caption: Label = item["amount"]
				_single_line(caption, "%s %s %s '%s'" % [description, key, resource, caption.text])
				_fits_width(item["row"], limits, description + " complete cost token")
		_single_line(controls["time"], description + " project duration")
		_fits_width(controls["action"], limits, description + " action button")


func _test_text(initial: Dictionary, width: int) -> void:
	root.content_scale_size = Vector2i(width, 1280)
	root.size = Vector2i(width, 1280)
	client._apply_state(initial.duplicate(true))
	await _settle()
	var mine: Dictionary = client.building_rows["metal_mine"]
	_expect(mine["costs"]["metal"]["amount"].text == "330", "Reported 3/3/0 is the intact 330 metal price")
	_expect(mine["costs"]["crystal"]["amount"].text == "116", "Reported 1/1/6 is the intact 116 crystal price")
	await _check_catalog(client.building_rows, 0, "Buildings at %d" % width)
	await _check_catalog(client.research_rows, 3, "Research at %d" % width)
	await _check_catalog(client.ship_rows, 2, "Shipyard at %d" % width)
	# Exercise longer values and totals through the actual order control.
	client.ship_rows["colonizer"]["amount"].value = 20
	await _settle()
	await _check_catalog(client.ship_rows, 2, "Twenty-ship prices at %d" % width)
	client.ship_rows["colonizer"]["amount"].value = 1
	client._open_tab(1)
	if not client.galaxy_overview.visible:
		client.galaxy_toggle.pressed.emit()
	await _settle()
	for marker: String in ["● Twoje", "● Gracze", "● Rój", "○ Wolne"]:
		var caption: Label = _label(client.galaxy_overview, marker)
		_expect(caption != null, "Galaxy legend keeps the meaning of " + marker)
		if caption != null:
			_single_line(caption, "Galaxy legend %s at %d" % [marker, width])
			_fits_width(caption, client.tabs[1].get_global_rect(), "Galaxy legend")
	for key: String in client.RESOURCE_KEYS:
		_single_line(client.resource_labels[key]["count"], "Header resource " + key)
		_single_line(client.resource_labels[key]["rate"], "Header production " + key)


func _check_counter(counter: Control, limits: Rect2, description: String) -> void:
	_fits_width(counter, limits, description)
	var buttons: Array[Button] = _buttons(counter)
	_expect(buttons.size() >= 2, description + " has separate decrease and increase targets")
	for button: Button in buttons:
		_expect(button.size.x >= 64.0 and button.size.y >= 72.0,
			"%s tap target '%s' is at least 64 by 72 (%s)" % [description, button.text, button.size])
		_fits_width(button, limits, description + " button")
	var editor: LineEdit = counter.get_line_edit()
	_expect(editor.size.x >= 80.0 and editor.size.y >= 72.0, description + " has a readable direct number entry")
	_fits_width(editor, limits, description + " number entry")


func _test_counters(initial: Dictionary) -> void:
	client._apply_state(initial.duplicate(true))
	client._open_fleet_missions()
	client.mission_picker.select(3)
	client._mission_changed(3)
	await _settle()
	var limits: Rect2 = client.tabs[2].get_global_rect()
	for key: String in client.fleet_inputs:
		_check_counter(client.fleet_inputs[key], limits, "Mission ships " + key)
	for key: String in client.cargo_inputs:
		_check_counter(client.cargo_inputs[key], limits, "Cargo " + key)
	client._set_fleet_mode(1)
	await _settle()
	for key: String in client.ship_rows:
		_check_counter(client.ship_rows[key]["amount"], limits, "Build ships " + key)
	var order: Control = client.ship_rows["scout"]["amount"]
	order.get_line_edit().text = "3"
	order.apply()
	await _settle()
	_expect(is_equal_approx(order.value, 3.0), "Shipyard direct entry commits three ships")
	_expect(client.ship_rows["scout"]["costs"]["metal"]["amount"].text == "300", "Three-ship order visibly updates aggregate metal price")
	_expect(client.ship_rows["scout"]["time"].text == client._duration(18.0), "Three-ship order visibly updates total duration")
	order.value = 1


func _test_planet_return() -> void:
	client._open_tab(0)
	await _settle()
	client.tabs[0].scroll_vertical = 900
	await _settle()
	_expect(client.tabs[0].scroll_vertical > 0, "Planet page has genuinely been scrolled down")
	client.nav_buttons[0].pressed.emit()
	await _settle()
	_expect(client.tabs[0].scroll_vertical == 0, "Tapping current Planeta returns to the colony panorama")
	client.tabs[0].scroll_vertical = 700
	client._open_tab(3)
	await _settle()
	client.nav_buttons[0].pressed.emit()
	await _settle()
	_expect(client.tabs[0].scroll_vertical == 0, "Returning from research through Planeta also resets scroll")


func _test_pickers(initial: Dictionary) -> void:
	client._apply_state(initial.duplicate(true))
	var examples: Array[Dictionary] = [
		{"picker": client.planet_picker, "tab": 0, "label": "Owned planet"},
		{"picker": client.system_picker, "tab": 1, "label": "Galaxy systems"},
		{"picker": client.target_picker, "tab": 2, "label": "Mission target"},
		{"picker": client.mission_picker, "tab": 2, "label": "Mission type"},
	]
	for example: Dictionary in examples:
		client._open_tab(example["tab"])
		if example["tab"] == 2:
			client._set_fleet_mode(0)
		if example["tab"] == 1 and client.galaxy_overview.visible:
			client.galaxy_toggle.pressed.emit()
		await _settle()
		var picker: Button = example["picker"]
		var description: String = example["label"]
		_expect(not picker is OptionButton and picker.has_method("open"), description + " uses an in-game touch list")
		_expect(picker.item_count > 0, description + " retains actual game choices")
		var previous: int = picker.selected
		picker.pressed.emit()
		await _settle()
		_expect(picker.is_open(), description + " opens from its displayed button")
		if not picker.is_open():
			continue
		var scroll: ScrollContainer = picker.find_child("ChoiceScroll", true, false) as ScrollContainer
		var panel: Control = picker.find_child("ChoicePanel", true, false) as Control
		_expect(scroll != null and panel != null, description + " has a bounded scrollable game panel")
		if panel != null:
			_fits_width(panel, Rect2(Vector2.ZERO, root.content_scale_size), description + " dialog")
			_expect(panel.global_position.y >= 0.0 and panel.get_global_rect().end.y <= 1280.0, description + " dialog fits phone height")
		if scroll != null:
			var rows: Node = scroll.get_node("ChoiceRows")
			_expect(rows.get_child_count() == picker.item_count, description + " exposes every available choice")
			for row: Node in rows.get_children():
				if row is Button:
					_expect(row.size.y >= 76.0, description + " choices have finger-sized row heights")
			if picker.item_count > 12:
				_expect(scroll.get_v_scroll_bar().max_value > scroll.size.y, description + " long list has a scrollable range")
		picker.close()
		await _settle()
		_expect(not picker.is_open() and picker.selected == previous, description + " dismisses without changing selection")
		picker.open()
		await _settle()
		if example["tab"] == 0:
			client._show_login()
		else:
			client._open_tab(0)
		await _settle()
		_expect(not picker.is_open(), description + " cannot leave a stale modal above another screen")
		client._apply_state(initial.duplicate(true))


func _active_state(building: Dictionary, kind: String, key: String, quantity: int) -> Dictionary:
	var result: Dictionary = building.duplicate(true)
	var group: String = "ships" if kind == "ship" else "research" if kind == "research" else "buildings"
	var duration: float = 0.0
	for entry: Dictionary in result["catalog"][group]:
		if entry["key"] == key:
			duration = float(entry["seconds"]) * quantity
	result["queue"] = [{"id": "offline-018", "kind": kind, "key": key, "amount": quantity,
		"level": 2, "ends_at": float(result["server_time"]) + duration}]
	return result


func _test_progress(building: Dictionary, initial: Dictionary) -> void:
	var panel: Control = client.find_child("ActiveProject", true, false) as Control
	_expect(panel != null, "An active project has a shared progress area below resources")
	if panel == null:
		return
	var shared_bar: ProgressBar = _progress(panel)
	_expect(shared_bar != null, "Shared active project includes a graphical progress bar")
	if shared_bar == null:
		return
	var cases: Array[Dictionary] = [
		{"kind": "build", "key": "metal_mine", "quantity": 1, "tab": 0, "rows": client.building_rows},
		{"kind": "research", "key": "propulsion", "quantity": 1, "tab": 3, "rows": client.research_rows},
		{"kind": "ship", "key": "scout", "quantity": 3, "tab": 2, "rows": client.ship_rows},
	]
	for example: Dictionary in cases:
		var state: Dictionary = _active_state(building, example["kind"], example["key"], example["quantity"])
		client._apply_state(state)
		client._open_tab(example["tab"])
		if example["tab"] == 2:
			client._set_fleet_mode(1)
		await _settle()
		var active: Dictionary = example["rows"][example["key"]]
		_expect(active.has("progress_panel") and active.has("progress_bar") and active.has("progress_label"),
			"Active %s has progress beside the specific project" % example["kind"])
		if not active.has("progress_bar"):
			continue
		var active_bar: ProgressBar = active["progress_bar"]
		_expect(active["progress_panel"].is_visible_in_tree() and active_bar.is_visible_in_tree(),
			"Progress is visible on the active %s card" % example["kind"])
		for rows: Dictionary in [client.building_rows, client.research_rows, client.ship_rows]:
			for key: String in rows:
				var expected: bool = rows == example["rows"] and key == example["key"]
				_expect(rows[key]["progress_panel"].visible == expected, "Progress does not appear on unrelated project " + key)
		var duration: float = client.queue_duration
		client.received_at_msec -= int(duration * 500.0)
		client._update_clock()
		_expect(active_bar.value >= 49.0 and active_bar.value <= 52.0, "Active card shows half of its actual queued duration")
		_expect(absf(shared_bar.value - active_bar.value) < 0.1, "Shared and in-card progress agree")
		if example["kind"] == "ship":
			client.ship_rows["scout"]["amount"].value = 20
			client._update_clock()
			_expect(is_equal_approx(client.queue_duration, duration), "Editing a future ship order does not change active batch duration")
			_expect(active_bar.value >= 49.0 and active_bar.value <= 52.0, "Active batch progress keeps the queued quantity")
			client.ship_rows["scout"]["amount"].value = 1
		var fixed_y: float = panel.global_position.y
		client.tabs[example["tab"]].scroll_vertical = 1300
		await _settle()
		_expect(panel.is_visible_in_tree() and is_equal_approx(panel.global_position.y, fixed_y), "Shared project progress remains visible after scrolling past the card")
		for tab_index: int in [0, 1, 2, 3, 4]:
			client._open_tab(tab_index)
			await _settle()
			_expect(panel.is_visible_in_tree(), "Active project is visible from tab %d" % tab_index)
			_expect(panel.get_global_rect().end.y <= client.tabs[tab_index].get_global_rect().position.y + 1.0,
				"Shared progress does not overlap scrolling tab content")
		client.received_at_msec -= int(duration * 1000.0)
		client._update_clock()
		_expect(is_equal_approx(active_bar.value, 100.0) and is_equal_approx(shared_bar.value, 100.0), "Elapsed project progress clamps at 100 percent")
		_expect(panel.visible and active["progress_panel"].visible, "Elapsed time waits for server confirmation instead of hiding the project")
		_expect(active["action"].disabled, "Elapsed local timer does not authorize another project")
		_expect("Kończenie" in active["progress_label"].text, "Completed timer explains that project completion is pending")
		client._apply_state(initial.duplicate(true))
		await _settle()
		_expect(not panel.visible and not client.queue_bar.visible, "Server-confirmed empty queue clears shared and planet progress")
		for rows: Dictionary in [client.building_rows, client.research_rows, client.ship_rows]:
			for key: String in rows:
				_expect(not rows[key]["progress_panel"].visible, "Server confirmation clears card progress " + key)


func _run() -> void:
	var arguments: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if arguments.is_empty():
		push_error("Supply a local JSON fixture path after --.")
		quit(2)
		return
	var fixture: Variant = JSON.parse_string(FileAccess.get_file_as_string(arguments[0]))
	if not fixture is Dictionary:
		push_error("The local fixture must contain a JSON object.")
		quit(2)
		return
	root.content_scale_size = Vector2i(720, 1280)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.size = Vector2i(720, 1280)
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await _settle()
	for width: int in [720, 600]:
		await _test_text(fixture["initial"], width)
		await _test_counters(fixture["initial"])
	await _test_pickers(fixture["initial"])
	await _test_planet_return()
	await _test_progress(fixture["building"], fixture["initial"])
	_expect(client.intercepted_requests.is_empty(), "UI regression checks make no gameplay requests")
	_expect(client.http == null and client.poll_timer == null, "Regression client cannot contact a production server")
	client.free()
	if failures.is_empty():
		print("UI_FIXES_018_PASS checks=%d" % checks)
		quit(0)
	else:
		print("UI_FIXES_018_FAIL checks=%d failures=%d" % [checks, failures.size()])
		quit(1)
