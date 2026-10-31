extends SceneTree
## Read-only map tests. No network, accounts or galaxy mutations.
## godot --headless --path . --script tests/test_galaxy_map.gd

const GalaxyMap = preload("res://client/scripts/galaxy_map.gd")
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
const NAMES: Array[String] = ["Helios", "Vega", "Orion", "Lyra", "Nadir", "Aster", "Talos", "Iris", "Atlas", "Selene", "Draco", "Aurora", "Kronos", "Eos", "Polaris", "Mira", "Nexus", "Arden", "Ereb", "Cygnus", "Boreas", "Zefir", "Tytan", "Perseusz", "Arka", "Solara", "Kepler", "Andara", "Vesper", "Rubież"]
var checks: int = 0
var failures: int = 0
var selections: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var map: Control = GalaxyMap.new()
	root.add_child(map)
	map.size = Vector2(600, 640)
	map.system_selected.connect(func(id: String) -> void: selections.append(id))
	await process_frame
	_expect(map.mouse_filter == Control.MOUSE_FILTER_STOP, "Map owns only its rectangle's gestures")
	_expect(bool(map.get_meta("touch_scroll_preserve_input", false)), "Outer scrolling respects map gestures")
	map.set_data([], "me", "")
	_expect(map.hit_points.is_empty(), "Empty galaxy has no targets")
	map.zoom_in()
	map._pan = Vector2(2000, 2000)
	map._refresh_layout()
	_expect(map._pan == Vector2.ZERO, "Empty galaxy cannot pan into nowhere")
	var single: Dictionary = {"id": "one", "name": "Samotna gwiazda", "x": -5, "y": 80, "planets": []}
	map.set_data([single], "me", "one")
	map.reset_view()
	_expect(map.hit_points.size() == 1, "One system is visible")
	_expect(Vector2(map.hit_points[0]["position"]).is_equal_approx(map._plot_rect().get_center()), "Single system is centered, not placed at upper left")
	map.focus_system("one")
	_expect(map._pan == Vector2.ZERO, "Single system remains centered on focus")
	var mixed: Dictionary = {"planets": [
		{"owner_type": "player", "owner_id": "me"},
		{"owner_type": "player", "owner_id": "neighbor"},
		{"owner_type": "alien", "owner_id": "khar"},
		{"owner_type": "empty", "owner_id": ""},
	]}
	var counts: Dictionary = map.ownership_counts(mixed)
	for category: String in ["own", "player", "alien", "empty"]:
		_expect(int(counts[category]) == 1, "Mixed system retains %s independently" % category)
	map.player_id = ""
	counts = map.ownership_counts({"planets": [{"owner_type": "empty", "owner_id": ""}]})
	_expect(int(counts["own"]) == 0 and int(counts["empty"]) == 1, "Unknown player never owns empty planets")
	map.player_id = "khar"
	counts = map.ownership_counts({"planets": [{"owner_type": "alien", "owner_id": "khar"}]})
	_expect(int(counts["own"]) == 0 and int(counts["alien"]) == 1, "Alien status cannot be masked by matching owner ID")
	var fixture: Array = _fixture()
	for width: int in [600, 720]:
		map.size = Vector2(width, 640)
		map.set_data(fixture, "me", "s1")
		map.reset_view()
		await process_frame
		_expect(map.hit_points.size() == 30, "All 30 systems fit at width %d" % width)
		var previous_count: int = selections.size()
		for target: Dictionary in map.hit_points.duplicate(true):
			var position: Vector2 = target["position"]
			_expect(position.y + 47 < map.size.y - 30, "Last-row label stays above footer at width %d" % width)
			_expect(position.y - 26 > 71, "First-row selection ring stays below heading")
			_touch(map, position, true)
			_expect(selections.size() == previous_count, "Touch-down does not select")
			_touch(map, position, false)
			previous_count += 1
			_expect(selections.back() == str(target["id"]), "Every visible star maps to the correct system")
		var radii: Vector2 = map._ellipse_radius()
		var center: Vector2 = map._plot_rect().get_center()
		var near_min: float = INF
		var near_max: float = 0.0
		for index: int in range(fixture.size()):
			var point_value: Vector2 = (map._base_position(fixture[index]) - center) / radii
			_expect(absf(point_value.length_squared() - 1.0) < 0.0001, "Every system lies on the same ellipse at width %d" % width)
			var next: Dictionary = fixture[(index + 1) % fixture.size()]
			var spacing: float = map._base_position(fixture[index]).distance_to(map._base_position(next))
			near_min = minf(near_min, spacing)
			near_max = maxf(near_max, spacing)
		_expect(near_max / near_min < 1.03, "Equal arc lengths keep ellipse ends from crowding")
		_expect(map._ring_points[0].distance_to(map._ring_points[-1]) < 0.01, "Circuit closes around all systems")
		_expect(map.label_layout.size() >= 14, "Overview labels enough systems to orient the player")
		_check_labels(map, "overview %d" % width)
		var base_positions: Dictionary = {}
		for value: Dictionary in fixture:
			base_positions[value["id"]] = map._base_position(value)
		var reversed: Array = fixture.duplicate(true)
		reversed.reverse()
		map.set_data(reversed, "me", "s1")
		for value: Dictionary in fixture:
			_expect(map._base_position(value).is_equal_approx(base_positions[value["id"]]), "State order cannot move a system")
			_expect(int(value["x"]) == (int(str(value["id"]).substr(1)) - 1) % 6, "Map never rewrites server flight coordinates")
		map.set_data(fixture, "me", "s1")
		map.focus_system("s20")
		_check_labels(map, "zoomed %d" % width)

	map.reset_view()
	map.zoom_in()
	_expect(is_equal_approx(map.get_zoom(), 1.4), "Zoom button increases scale")
	map.zoom_out()
	_expect(is_equal_approx(map.get_zoom(), 1.0), "Zoom-out returns to overview")
	for index: int in range(20):
		map.zoom_in()
	_expect(is_equal_approx(map.get_zoom(), map.MAX_ZOOM), "Maximum zoom is clamped")
	var scale_before: float = map.get_zoom()
	map.focus_system("unknown")
	_expect(is_equal_approx(map.get_zoom(), scale_before), "Unknown focus target cannot alter view")
	for value: Dictionary in fixture:
		map.focus_system(str(value["id"]))
		_expect(map._plot_rect().grow(1).has_point(map._screen_position(value)), "Focus can reach every edge system")
	map.reset_view()
	map.zoom_in()
	var point: Vector2 = map._plot_rect().get_center()
	var count_before: int = selections.size()
	_touch(map, point, true)
	_drag(map, point + Vector2(55, 30))
	_touch(map, point + Vector2(55, 30), false)
	_expect(map._pan.is_equal_approx(Vector2(55, 30)), "Dragging pans an enlarged map")
	_expect(selections.size() == count_before, "A pan does not select a system")
	map.reset_view()
	count_before = selections.size()
	var pinch_center: Vector2 = map._plot_rect().get_center()
	_touch_index(map, pinch_center - Vector2(50, 0), true, 0)
	_touch_index(map, pinch_center + Vector2(50, 0), true, 1)
	_drag_index(map, pinch_center + Vector2(100, 0), 1)
	_expect(map.get_zoom() > 1.0, "Two-finger pinch zooms the map")
	_expect(not map._tap_pending, "Pinch cancels tap selection")
	_touch_index(map, pinch_center + Vector2(100, 0), false, 1)
	_drag_index(map, pinch_center - Vector2(20, 0), 0)
	_touch_index(map, pinch_center - Vector2(20, 0), false, 0)
	_expect(selections.size() == count_before, "Pinch and remaining-finger drag never select a star")
	_expect(map._touch_points.is_empty() and not map._pinch_active, "Pinch release clears fingers")
	map._pan = Vector2(100000, -100000)
	map._refresh_layout()
	var max_pan: Vector2 = map._plot_rect().size * (map.get_zoom() - 1.0) * 0.5
	_expect(map._pan.is_equal_approx(Vector2(max_pan.x, -max_pan.y)), "Pan is clamped to galaxy bounds")
	for index: int in range(20):
		map.zoom_out()
	_expect(is_equal_approx(map.get_zoom(), map.MIN_ZOOM), "Minimum zoom is clamped")
	_expect(map._pan == Vector2.ZERO, "Overview cannot drift off screen")
	_touch(map, Vector2(-20, -20), true)
	_expect(not map._pointer_down, "A touch outside the map never starts a gesture")
	_touch(map, Vector2(-20, -20), false)
	_touch(map, Vector2(100, 200), true)
	var canceled: InputEventScreenTouch = InputEventScreenTouch.new()
	canceled.position = Vector2(100, 200)
	canceled.index = 0
	canceled.pressed = false
	canceled.canceled = true
	map._gui_input(canceled)
	_expect(not map._pointer_down and not map._tap_pending, "Canceled Android touches clear selection and drag state")
	_touch(map, Vector2(100, 200), true)
	map.notification(Control.NOTIFICATION_VISIBILITY_CHANGED)
	_expect(not map._pointer_down and map._touch_index == -1, "Switching tabs clears gestures")
	var scroll: ScrollContainer = TouchScroll.new()
	var nested_map: Control = GalaxyMap.new()
	scroll.add_child(nested_map)
	root.add_child(scroll)
	await process_frame
	_expect(nested_map.mouse_filter == Control.MOUSE_FILTER_STOP, "Native page scroll preserves nested map filter after ready")
	scroll.queue_free()
	map.size = Vector2(720, 640)
	map.set_data(fixture, "me", "s20")
	map.reset_view()
	if "--render" in load("res://tests/test_arguments.gd").user_args():
		var screenshot_dir: String = OS.get_environment("ALIEN_MAP_SCREENSHOTS")
		if screenshot_dir.is_empty():
			screenshot_dir = ProjectSettings.globalize_path("user://map_032")
		DirAccess.make_dir_recursive_absolute(screenshot_dir)
		root.size = Vector2i(720, 640)
		root.content_scale_size = Vector2i(720, 640)
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(screenshot_dir.path_join("galaxy_032_overview.png"))
		map.focus_system("s20")
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(screenshot_dir.path_join("galaxy_032_zoom.png"))
	map.queue_free()
	await process_frame
	print("Galaxy map: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)


func _fixture() -> Array:
	var result: Array = []
	for index: int in range(NAMES.size()):
		result.append({"id": "s%d" % (index + 1), "name": NAMES[index], "x": index % 6, "y": floori(float(index) / 6), "planets": [{"owner_type": "empty", "owner_id": ""}]})
	return result


func _touch(map: Control, point: Vector2, down: bool) -> void:
	var event: InputEventScreenTouch = InputEventScreenTouch.new()
	event.index = 0
	event.position = point
	event.pressed = down
	map._gui_input(event)


func _drag(map: Control, point: Vector2) -> void:
	var event: InputEventScreenDrag = InputEventScreenDrag.new()
	event.index = 0
	event.position = point
	map._gui_input(event)


func _expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)


func _check_labels(map: Control, context: String) -> void:
	for first: int in range(map.label_layout.size()):
		var rect: Rect2 = map.label_layout[first]["rect"]
		_expect(map._visible_rect().encloses(rect), "Label stays outside toolbar/footer in %s" % context)
		for target: Dictionary in map.hit_points:
			_expect(not rect.grow(11).has_point(target["position"]), "Label leaves every star exposed in %s" % context)
		for second: int in range(first + 1, map.label_layout.size()):
			_expect(not rect.intersects(map.label_layout[second]["rect"]), "Labels never overlap in %s" % context)


func _touch_index(map: Control, point: Vector2, down: bool, finger: int) -> void:
	var event: InputEventScreenTouch = InputEventScreenTouch.new()
	event.index = finger
	event.position = point
	event.pressed = down
	map._gui_input(event)


func _drag_index(map: Control, point: Vector2, finger: int) -> void:
	var event: InputEventScreenDrag = InputEventScreenDrag.new()
	event.index = finger
	event.position = point
	map._gui_input(event)
