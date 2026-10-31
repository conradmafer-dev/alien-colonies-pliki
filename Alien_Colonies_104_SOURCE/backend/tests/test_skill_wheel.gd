extends SceneTree
## Uses the authoritative server graph exported as JSON, without network or saves.
## python3 -c 'import json; from server.skill_tree import public_state; print(json.dumps(public_state("zetans", [], 30)))' > /tmp/skill-wheel.json
## godot --headless --path . --script tests/test_skill_wheel.gd -- /tmp/skill-wheel.json

const Wheel = preload("res://client/scripts/skill_wheel.gd")
const RaceTheme = preload("res://client/scripts/race_theme.gd")
var checks: int = 0
var failures: Array[String] = []
var selections: Array[String] = []


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func _run() -> void:
	var arguments: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if arguments.is_empty():
		push_error("Pass the public_state JSON fixture path after --")
		quit(2)
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(arguments[0]))
	if not parsed is Dictionary:
		push_error("Skill tree fixture must be a JSON dictionary")
		quit(2)
		return
	var wheel: Control = Wheel.new()
	root.add_child(wheel)
	wheel.size = Vector2(720, 790)
	wheel.node_selected.connect(func(node_id: String) -> void: selections.append(node_id))
	wheel.set_tree(parsed)
	await process_frame
	_expect(wheel.nodes.size() == 60, "The canvas consumes all 60 authoritative graph nodes")
	_expect(wheel.mouse_filter == Control.MOUSE_FILTER_STOP and bool(wheel.get_meta("touch_scroll_preserve_input")),
		"The wheel owns its gesture rectangle instead of a surrounding vertical scroller")
	_expect(wheel.RACE_COLORS["zetans"] == Color("62aaff") and wheel.RACE_COLORS["automatons"] == Color("ff645b")
		and wheel.RACE_COLORS["symbionts"] == Color("66e889"), "The three requested race colors are distinct and exact")
	for theme_race: String in ["zetans", "automatons", "symbionts"]:
		RaceTheme.set_race(theme_race)
		for token: String in ["030707", "020404", "020604", "0b1514", "070d0c", "0a1510", "4d6b63", "91b5ab"]:
			var shade: Color = wheel._chrome(token)
			if theme_race == "zetans":
				_expect(shade.b > shade.r and shade.b >= shade.g, "Zetan wheel chrome is blue: " + token)
			elif theme_race == "automatons":
				_expect(shade.r > shade.b and shade.r > shade.g, "Automaton wheel chrome is red: " + token)
			else:
				_expect(shade.to_html() == Color(token).to_html(), "Symbiont wheel retains original green: " + token)
		for skill_race: String in ["zetans", "automatons", "symbionts", "shared"]:
			_expect(wheel._tint({"race_id": skill_race}) == wheel.RACE_COLORS[skill_race],
				"Changing chrome never recolours another race's skill or gold shared node: " + skill_race)
		wheel.queue_redraw()
		await process_frame
	RaceTheme.set_race("")
	var roots: Dictionary = parsed["roots"]
	var empty_radius: float = float(parsed.get("empty_radius", 300.0))
	for node: Dictionary in wheel.nodes:
		var center: Vector2 = wheel._point(node)
		var radius: float = wheel._radius(node)
		_expect(center.length() - radius >= empty_radius, "Every skill disk stays outside the empty center: " + str(node["id"]))
		if roots.values().has(str(node["id"])):
			_expect(radius == 100.0, "Signature root is the largest 100-unit disk: " + str(node["id"]))
		else:
			_expect(radius <= 52.0, "Ordinary skills remain smaller than the signature: " + str(node["id"]))
	for edge: Array in wheel.edges:
		var a: Vector2 = wheel._point(wheel._by_id[str(edge[0])])
		var b: Vector2 = wheel._point(wheel._by_id[str(edge[1])])
		var nearest: Vector2 = Geometry2D.get_closest_point_to_segment(Vector2.ZERO, a, b)
		_expect(nearest.length() >= empty_radius, "A connection never crosses the empty center")
	for width: float in [600.0, 720.0]:
		wheel.size = Vector2(width, 790.0)
		wheel.fit_all()
		await process_frame
		_expect(wheel.hit_points.size() == 60, "Overview retains all 60 targets at width %d" % int(width))
		for race_id: String in ["zetans", "automatons", "symbionts"]:
			wheel.focus_race(race_id)
			var point: Vector2 = wheel._world_to_screen(wheel._point(wheel._by_id[str(roots[race_id])]))
			_expect(Rect2(Vector2.ZERO, wheel.size).has_point(point), "Focus opens the requested race root at width %d: %s" % [int(width), race_id])
			_expect(wheel.selected_id == str(roots[race_id]), "Race focus keeps the signature selected")
	for viewport_size: Vector2 in [Vector2(680, 500), Vector2(560, 350)]:
		wheel.size = viewport_size
		wheel.fit_all()
		for node: Dictionary in wheel.nodes:
			var node_center: Vector2 = wheel._world_to_screen(wheel._point(node))
			var node_radius: float = wheel._radius(node) * wheel.get_zoom()
			var inset: Rect2 = Rect2(Vector2.ZERO, viewport_size).grow(-node_radius)
			_expect(inset.has_point(node_center), "Całość fits every complete skill disk in a short mobile canvas %s: %s" % [viewport_size, str(node["id"])])
	wheel.size = Vector2(720, 790)
	for node: Dictionary in wheel.nodes:
		var node_id: String = str(node["id"])
		wheel.focus_node(node_id)
		var point: Vector2 = wheel._world_to_screen(wheel._point(node))
		_expect(point.is_equal_approx(wheel.size * 0.5), "Focus reaches each outer and inner node: " + node_id)
		var before: int = selections.size()
		_touch(wheel, 0, point, true)
		_expect(selections.size() == before, "Touch down never selects or purchases a skill")
		_touch(wheel, 0, point, false)
		_expect(selections.size() == before + 1 and selections.back() == node_id,
			"A completed stationary tap picks the correct mini artwork: " + node_id)
	var selected: String = str(roots["zetans"])
	wheel.focus_node(selected)
	var center: Vector2 = wheel.size * 0.5
	var before: int = selections.size()
	var pan_before: Vector2 = wheel._pan
	_touch(wheel, 0, center, true)
	_drag(wheel, 0, center + Vector2(80, 60))
	_touch(wheel, 0, center + Vector2(80, 60), false)
	_expect(wheel._pan.is_equal_approx(pan_before + Vector2(80, 60)), "A one-finger drag pans both axes")
	_expect(selections.size() == before, "Panning from a skill icon never selects it on release")
	wheel.focus_node(selected)
	_touch(wheel, 0, center, true)
	_drag(wheel, 0, center + Vector2(70, 0))
	_drag(wheel, 0, center)
	_touch(wheel, 0, center, false)
	_expect(selections.size() == before, "Returning a dragged finger to its starting point does not turn it into a tap")
	wheel.focus_node(selected)
	_touch(wheel, 0, center, true)
	_touch(wheel, 0, center, false, true)
	_expect(selections.size() == before and wheel._touches.is_empty(), "Canceled Android touch cannot select and clears gesture state")
	wheel.focus_node(selected)
	var zoom_before: float = wheel.get_zoom()
	var first: Vector2 = center + Vector2(-60, 0)
	var second: Vector2 = center + Vector2(60, 0)
	var anchor_world: Vector2 = wheel._screen_to_world(center)
	_touch(wheel, 3, first, true)
	_touch(wheel, 8, second, true)
	_drag(wheel, 3, center + Vector2(-95, 0))
	_drag(wheel, 8, center + Vector2(95, 0))
	_expect(wheel.get_zoom() > zoom_before, "Spreading two fingers zooms the wheel")
	_expect(wheel._screen_to_world(center).distance_to(anchor_world) < 0.1, "A symmetric pinch keeps the same skill beneath its midpoint")
	_touch(wheel, 8, center + Vector2(95, 0), false)
	_drag(wheel, 3, center)
	_touch(wheel, 3, center, false)
	_expect(selections.size() == before, "Lifting either pinch finger never causes an accidental node selection")
	_expect(wheel._touches.is_empty() and wheel._touch_index == -1, "All pinch contacts are released cleanly")
	# Android can synthesize mouse events from the same physical touch.
	_mouse_button(wheel, center, true)
	_mouse_button(wheel, center, false)
	_expect(selections.size() == before, "An emulated mouse click following a touch is ignored")
	wheel._last_touch_msec = -1000
	wheel.focus_node(selected)
	_mouse_button(wheel, center, true)
	_mouse_button(wheel, center, false)
	_expect(selections.size() == before + 1 and selections.back() == selected, "A genuine desktop click still selects")
	before = selections.size()
	_mouse_button(wheel, center, true)
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.position = center + Vector2(50, 30)
	wheel._gui_input(motion)
	_mouse_button(wheel, center + Vector2(50, 30), false)
	_expect(selections.size() == before, "Desktop dragging never selects on release")
	wheel.focus_node(selected)
	var anchor: Vector2 = center + Vector2(77, -84)
	anchor_world = wheel._screen_to_world(anchor)
	var scroll: InputEventMouseButton = InputEventMouseButton.new()
	scroll.position = anchor
	scroll.button_index = MOUSE_BUTTON_WHEEL_DOWN
	scroll.pressed = true
	wheel._gui_input(scroll)
	_expect(wheel._screen_to_world(anchor).distance_to(anchor_world) < 0.1, "Mouse wheel zoom anchors beneath the pointer")
	wheel.zoom_by(10000)
	_expect(is_equal_approx(wheel.get_zoom(), Wheel.MAX_ZOOM), "Maximum zoom is bounded")
	wheel.zoom_by(0.00001)
	_expect(is_equal_approx(wheel.get_zoom(), Wheel.MIN_ZOOM), "Minimum zoom is bounded")
	wheel.focus_node(selected)
	wheel.select_node(selected)
	pan_before = wheel._pan
	zoom_before = wheel.get_zoom()
	wheel.set_tree(parsed.duplicate(true))
	_expect(wheel._pan.is_equal_approx(pan_before) and is_equal_approx(wheel.get_zoom(), zoom_before)
		and wheel.selected_id == selected, "Server polling preserves the player's selected node and camera")
	_touch(wheel, 4, center, true)
	wheel.hide()
	_expect(wheel._touches.is_empty() and not wheel._mouse_down, "Closing the overlay clears all pending gestures")
	wheel.show()
	before = selections.size()
	_touch(wheel, 4, center, false)
	_expect(selections.size() == before, "A stale release after reopening cannot select")
	_touch(wheel, 0, Vector2(-5, -5), true)
	_expect(wheel._touches.is_empty(), "A contact outside the wheel cannot steal another control's gesture")
	# Exercise Godot's actual GUI routing as well as the gesture state machine.
	# The nonzero panel offset catches mixing viewport and local touch positions.
	root.size = Vector2i(720, 1280)
	wheel.position = Vector2(20, 100)
	wheel.size = Vector2(680, 900)
	wheel.focus_node(selected)
	await process_frame
	var global_point: Vector2 = wheel.get_global_rect().get_center()
	before = selections.size()
	for down: bool in [true, false]:
		var native_touch: InputEventScreenTouch = InputEventScreenTouch.new()
		native_touch.position = global_point
		native_touch.index = 11
		native_touch.pressed = down
		root.push_input(native_touch, true)
	_expect(selections.size() == before + 1 and selections.back() == selected,
		"Native viewport touch routing selects the correct node in an offset canvas")
	before = selections.size()
	pan_before = wheel._pan
	var native_press: InputEventScreenTouch = InputEventScreenTouch.new()
	native_press.position = global_point
	native_press.index = 12
	native_press.pressed = true
	root.push_input(native_press, true)
	var native_drag: InputEventScreenDrag = InputEventScreenDrag.new()
	native_drag.position = global_point + Vector2(90, 45)
	native_drag.index = 12
	native_drag.relative = Vector2(90, 45)
	root.push_input(native_drag, true)
	var native_release: InputEventScreenTouch = InputEventScreenTouch.new()
	native_release.position = native_drag.position
	native_release.index = 12
	native_release.pressed = false
	root.push_input(native_release, true)
	_expect(wheel._pan.is_equal_approx(pan_before + Vector2(90, 45)) and selections.size() == before,
		"Native touch dragging pans an offset canvas without selecting on release")
	wheel.queue_free()
	await process_frame
	print("SKILL WHEEL: %d checks, %d failures" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)


func _touch(wheel: Control, index: int, point: Vector2, down: bool, canceled: bool = false) -> void:
	var event: InputEventScreenTouch = InputEventScreenTouch.new()
	event.index = index
	event.position = point
	event.pressed = down
	event.canceled = canceled
	wheel._gui_input(event)


func _drag(wheel: Control, index: int, point: Vector2) -> void:
	var event: InputEventScreenDrag = InputEventScreenDrag.new()
	event.index = index
	event.position = point
	wheel._gui_input(event)


func _mouse_button(wheel: Control, point: Vector2, down: bool) -> void:
	var event: InputEventMouseButton = InputEventMouseButton.new()
	event.position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = down
	wheel._gui_input(event)
