extends Control
## Original, data-driven constellation of racial skills. Purchases belong to the
## authenticated parent UI; this canvas only navigates and selects nodes.
signal node_selected(node_id: String)
signal view_changed(zoom: float)

const SkillIcon = preload("res://client/scripts/skill_icon.gd")
const RaceTheme = preload("res://client/scripts/race_theme.gd")

const MIN_ZOOM: float = 0.12
const MAX_ZOOM: float = 1.3
const TAP_DEADZONE: float = 12.0
const RACE_COLORS: Dictionary = {
	"zetans": Color("62aaff"),
	"automatons": Color("ff645b"),
	"symbionts": Color("66e889"),
	"shared": Color("d6c898"),
}

var tree_data: Dictionary = {}
var nodes: Array = []
var edges: Array = []
var selected_id: String = ""
var hit_points: Array[Dictionary] = []
var _by_id: Dictionary = {}
var _zoom: float = 0.60
var _pan: Vector2 = Vector2.ZERO
var _font: Font
var _first_tree: bool = true
var _touches: Dictionary = {}
var _touch_origin: Vector2 = Vector2.ZERO
var _touch_last: Vector2 = Vector2.ZERO
var _touch_index: int = -1
var _gesture_cancelled: bool = false
var _pinch_center: Vector2 = Vector2.ZERO
var _pinch_distance: float = 0.0
var _mouse_down: bool = false
var _mouse_origin: Vector2 = Vector2.ZERO
var _mouse_last: Vector2 = Vector2.ZERO
var _mouse_dragged: bool = false
var _last_touch_msec: int = -1000


func _init() -> void:
	set_meta("touch_scroll_preserve_input", true)
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	focus_mode = Control.FOCUS_ALL


func _ready() -> void:
	_font = ThemeDB.fallback_font
	I18n.language_changed.connect(queue_redraw)
	resized.connect(_refresh_layout)
	_refresh_layout()


func set_tree(value: Dictionary) -> void:
	tree_data = value.duplicate(true)
	nodes = tree_data.get("nodes", [])
	edges = tree_data.get("edges", [])
	_by_id.clear()
	for node: Dictionary in nodes:
		_by_id[str(node.get("id", ""))] = node
	if not _by_id.has(selected_id):
		selected_id = ""
	if _first_tree and not nodes.is_empty():
		_first_tree = false
		fit_all()
	else:
		_refresh_layout()


func get_zoom() -> float:
	return _zoom


func select_node(node_id: String, emit_selection: bool = false) -> void:
	if not _by_id.has(node_id):
		return
	selected_id = node_id
	queue_redraw()
	if emit_selection:
		node_selected.emit(node_id)


func focus_race(race_id: String) -> void:
	var roots: Dictionary = tree_data.get("roots", {})
	var root_id: String = str(roots.get(race_id, ""))
	if root_id.is_empty():
		var largest: float = -1.0
		for node: Dictionary in nodes:
			if str(node.get("race_id", "")) == race_id and _radius(node) > largest:
				root_id = str(node.get("id", ""))
				largest = _radius(node)
	if not _by_id.has(root_id):
		return
	var point: Vector2 = _point(_by_id[root_id])
	# Looking outward reveals the first branching choices beside the signature.
	_zoom = 0.68
	_pan = -(point + point.normalized() * 150.0) * _zoom
	select_node(root_id)
	_refresh_layout()
	view_changed.emit(_zoom)


func focus_node(node_id: String) -> void:
	if not _by_id.has(node_id):
		return
	_zoom = maxf(_zoom, 0.75)
	_pan = -_point(_by_id[node_id]) * _zoom
	select_node(node_id)
	_refresh_layout()
	view_changed.emit(_zoom)


func fit_all() -> void:
	var bounds: Rect2 = _bounds().grow(80.0)
	if bounds.size.x <= 0.0 or bounds.size.y <= 0.0:
		return
	_zoom = clampf(minf(maxf(size.x, 1.0) / bounds.size.x,
		maxf(size.y, 1.0) / bounds.size.y), MIN_ZOOM, MAX_ZOOM)
	_pan = -bounds.get_center() * _zoom
	_refresh_layout()
	view_changed.emit(_zoom)


func zoom_by(factor: float) -> void:
	if factor <= 0.0:
		return
	_zoom_at(_zoom * factor, size * 0.5)


func _point(node: Dictionary) -> Vector2:
	return Vector2(float(node.get("x", 0.0)), float(node.get("y", 0.0)))


func _radius(node: Dictionary) -> float:
	return maxf(float(node.get("size", 38.0)), 12.0)


func _tint(node: Dictionary) -> Color:
	return RACE_COLORS.get(str(node.get("race_id", "shared")), RACE_COLORS["shared"])


func _world_to_screen(point: Vector2) -> Vector2:
	return size * 0.5 + _pan + point * _zoom


func _screen_to_world(point: Vector2) -> Vector2:
	return (point - size * 0.5 - _pan) / _zoom


func _bounds() -> Rect2:
	if nodes.is_empty():
		return Rect2(Vector2(-1200.0, -1200.0), Vector2(2400.0, 2400.0))
	var low: Vector2 = Vector2(INF, INF)
	var high: Vector2 = Vector2(-INF, -INF)
	for node: Dictionary in nodes:
		var padding: Vector2 = Vector2.ONE * (_radius(node) + 35.0)
		low = low.min(_point(node) - padding)
		high = high.max(_point(node) + padding)
	return Rect2(low, high - low)


func _clamp_pan() -> void:
	var bounds: Rect2 = _bounds()
	var allowance: Vector2 = size * 0.30
	_pan = _pan.clamp(-bounds.end * _zoom - allowance,
		-bounds.position * _zoom + allowance)


func _refresh_layout() -> void:
	_clamp_pan()
	hit_points.clear()
	var viewport_rect: Rect2 = Rect2(Vector2.ZERO, size).grow(100.0)
	for node: Dictionary in nodes:
		var point: Vector2 = _world_to_screen(_point(node))
		if viewport_rect.has_point(point):
			hit_points.append({"id": str(node.get("id", "")), "position": point,
				"radius": maxf(_radius(node) * _zoom, 24.0)})
	queue_redraw()


func _zoom_at(value: float, anchor: Vector2) -> void:
	var next_zoom: float = clampf(value, MIN_ZOOM, MAX_ZOOM)
	if is_equal_approx(next_zoom, _zoom):
		return
	var world_anchor: Vector2 = _screen_to_world(anchor)
	_zoom = next_zoom
	_pan = anchor - size * 0.5 - world_anchor * _zoom
	_refresh_layout()
	view_changed.emit(_zoom)


func _chrome(value: String) -> Color:
	# Only neutral canvas chrome follows the account. Skill sectors, ornaments,
	# node rims and artwork must retain their own race, including neighbouring
	# civilizations reached through the shared wheel.
	return RaceTheme.color(Color(value))


func _draw() -> void:
	if _font == null:
		_font = ThemeDB.fallback_font
	draw_rect(Rect2(Vector2.ZERO, size), _chrome("030707"))
	_draw_stars()
	_draw_sector_traces()
	_draw_links()
	# Paint after ornaments and links: even a decorative curve can never fill
	# the deliberately empty inner circle. Nodes are outside its boundary.
	var center: Vector2 = _world_to_screen(Vector2.ZERO)
	var empty_radius: float = float(tree_data.get("empty_radius", 300.0)) * _zoom
	draw_circle(center, empty_radius, _chrome("020404"))
	draw_arc(center, empty_radius, 0.0, TAU, 128, Color(_chrome("4d6b63"), 0.35), 1.0, true)
	draw_arc(center, empty_radius + 7.0 * _zoom, 0.0, TAU, 128,
		Color(_chrome("4d6b63"), 0.12), 1.0, true)
	for entry: Dictionary in hit_points:
		_draw_node(_by_id[str(entry["id"])], entry["position"])


func _draw_stars() -> void:
	# Deterministic low-contrast star field follows the world while panning.
	for index: int in range(180):
		var world: Vector2 = Vector2(fposmod(float(index * 641 + 37), 4000.0) - 2000.0,
			fposmod(float(index * 977 + 111), 4000.0) - 2000.0)
		if world.length() <= float(tree_data.get("empty_radius", 300.0)) + 10.0:
			continue
		var point: Vector2 = _world_to_screen(world)
		if Rect2(Vector2.ZERO, size).has_point(point):
			draw_circle(point, 0.8 if index % 9 != 0 else 1.3,
				Color(_chrome("91b5ab"), 0.14 + float(index % 4) * 0.045))


func _draw_sector_traces() -> void:
	var roots: Dictionary = tree_data.get("roots", {})
	for race_id: String in ["zetans", "automatons", "symbionts"]:
		var root_id: String = str(roots.get(race_id, ""))
		if not _by_id.has(root_id):
			continue
		var root_point: Vector2 = _point(_by_id[root_id])
		var direction: Vector2 = root_point.normalized()
		var angle: float = direction.angle()
		var tint: Color = RACE_COLORS[race_id]
		var screen_root: Vector2 = _world_to_screen(root_point)
		# Colored radial aura uses concentric outlines, not a solid sector pie.
		for layer: int in range(4):
			var halo_radius: float = (116.0 + float(layer) * 13.0) * _zoom
			draw_arc(screen_root, halo_radius, angle - PI * 0.80, angle + PI * 0.80,
				60, Color(tint, 0.10 - float(layer) * 0.017), maxf(1.0, 3.0 * _zoom), true)
		match race_id:
			"zetans":
				_draw_zetan_ornaments(root_point, angle, tint)
			"automatons":
				_draw_automaton_ornaments(root_point, angle, tint)
			"symbionts":
				_draw_symbiont_ornaments(root_point, angle, tint)
		# The distant segmented rim hints at the long routes to other races.
		for segment: int in range(13):
			var start: float = angle - 0.53 + float(segment) * 0.085
			draw_arc(_world_to_screen(Vector2.ZERO), 1265.0 * _zoom,
				start, start + 0.052, 10, Color(tint, 0.17), maxf(1.0, _zoom * 2.0), true)


func _draw_zetan_ornaments(origin: Vector2, angle: float, tint: Color) -> void:
	for side: float in [-1.0, 1.0]:
		var chain: PackedVector2Array = PackedVector2Array()
		for step: int in range(33):
			var t: float = float(step) / 32.0
			var radial: float = 455.0 + 700.0 * t
			var theta: float = angle + side * (0.16 + 0.39 * sin(t * PI * 0.68))
			chain.append(_world_to_screen(Vector2.from_angle(theta) * radial))
		draw_polyline(chain, Color(tint, 0.21), maxf(1.0, 2.0 * _zoom), true)
		for step: int in range(4):
			var point: Vector2 = origin + Vector2.from_angle(angle + side * 0.55) * (190.0 + float(step) * 145.0)
			var center: Vector2 = _world_to_screen(point)
			draw_arc(center, (26.0 + float(step) * 9.0) * _zoom,
				angle + side * 0.35, angle + PI * 1.8, 42, Color(tint, 0.16), 1.0, true)
			draw_circle(center + Vector2.from_angle(angle + 0.8) * (26.0 + float(step) * 9.0) * _zoom,
				maxf(1.2, 3.0 * _zoom), Color(tint, 0.44))


func _draw_automaton_ornaments(origin: Vector2, angle: float, tint: Color) -> void:
	var forward: Vector2 = Vector2.from_angle(angle)
	var tangent: Vector2 = forward.orthogonal()
	for side: float in [-1.0, 1.0]:
		var path: PackedVector2Array = PackedVector2Array()
		for step: int in range(7):
			var along: float = 40.0 + float(step) * 115.0
			var across: float = side * (133.0 + float(step) * 46.0)
			path.append(_world_to_screen(origin + forward * along + tangent * across))
			path.append(_world_to_screen(origin + forward * (along + 85.0) + tangent * across))
		draw_polyline(path, Color(tint, 0.23), maxf(1.0, 2.0 * _zoom), true)
		for step: int in range(6):
			var point: Vector2 = origin + forward * (135.0 + float(step) * 121.0) + tangent * side * (147.0 + float(step) * 45.0)
			var center: Vector2 = _world_to_screen(point)
			var radius: float = 9.0 * _zoom
			draw_rect(Rect2(center - Vector2.ONE * radius, Vector2.ONE * radius * 2.0), Color(tint, 0.25), false, 1.0)
			draw_line(center - tangent * 22.0 * _zoom, center + tangent * 22.0 * _zoom,
				Color(tint, 0.18), 1.0, true)


func _draw_symbiont_ornaments(origin: Vector2, angle: float, tint: Color) -> void:
	var forward: Vector2 = Vector2.from_angle(angle)
	var tangent: Vector2 = forward.orthogonal()
	for side: float in [-1.0, 1.0]:
		var vine: PackedVector2Array = PackedVector2Array()
		for step: int in range(49):
			var t: float = float(step) / 48.0
			var point: Vector2 = origin + forward * (70.0 + 700.0 * t) + tangent * side * (120.0 + 285.0 * t + 26.0 * sin(t * TAU * 1.7))
			vine.append(_world_to_screen(point))
		draw_polyline(vine, Color(tint, 0.23), maxf(1.0, 2.3 * _zoom), true)
		for step: int in range(7):
			var t: float = (float(step) + 0.5) / 7.0
			var point: Vector2 = origin + forward * (70.0 + 700.0 * t) + tangent * side * (120.0 + 285.0 * t + 26.0 * sin(t * TAU * 1.7))
			var leaf: PackedVector2Array = PackedVector2Array([
				_world_to_screen(point),
				_world_to_screen(point + forward * 12.0 + tangent * side * 38.0),
				_world_to_screen(point + forward * 51.0 + tangent * side * 62.0),
				_world_to_screen(point + forward * 37.0 + tangent * side * 13.0),
			])
			draw_colored_polygon(leaf, Color(tint, 0.075))
			leaf.append(leaf[0])
			draw_polyline(leaf, Color(tint, 0.22), 1.0, true)
			draw_line(_world_to_screen(point), leaf[2], Color(tint, 0.15), 1.0, true)


func _draw_links() -> void:
	for edge: Array in edges:
		if edge.size() < 2 or not _by_id.has(str(edge[0])) or not _by_id.has(str(edge[1])):
			continue
		var from_node: Dictionary = _by_id[str(edge[0])]
		var to_node: Dictionary = _by_id[str(edge[1])]
		var from: Vector2 = _world_to_screen(_point(from_node))
		var to: Vector2 = _world_to_screen(_point(to_node))
		var active: bool = bool(from_node.get("unlocked", false)) and bool(to_node.get("unlocked", false))
		var frontier: bool = bool(from_node.get("unlocked", false)) != bool(to_node.get("unlocked", false))
		var tint: Color = _tint(from_node).lerp(_tint(to_node), 0.5)
		if active:
			draw_line(from, to, Color(tint, 0.12), maxf(5.0, 12.0 * _zoom), true)
			draw_line(from, to, Color(tint, 0.88), maxf(1.8, 3.5 * _zoom), true)
		elif frontier:
			draw_line(from, to, Color(tint, 0.40), maxf(1.4, 2.5 * _zoom), true)
		else:
			draw_line(from, to, Color(tint, 0.17), maxf(1.0, 2.0 * _zoom), true)
		# Small regularly spaced route markers make the very long cross-race
		# arc legible without simulating additional purchasable skills.
		var mid: Vector2 = from.lerp(to, 0.5)
		draw_circle(mid, maxf(1.0, 2.8 * _zoom), Color(tint, 0.55 if active else 0.20))


func _draw_node(node: Dictionary, center: Vector2) -> void:
	var radius: float = _radius(node) * _zoom
	var is_root: bool = _radius(node) >= 90.0
	var unlocked: bool = bool(node.get("unlocked", false))
	var available: bool = bool(node.get("available", false))
	var affordable: bool = bool(node.get("affordable", false))
	var selected: bool = selected_id == str(node.get("id", ""))
	var tint: Color = _tint(node)
	var intensity: float = 1.0 if unlocked else (0.77 if available else 0.35)
	if selected or unlocked or affordable:
		for layer: int in range(3, 0, -1):
			draw_circle(center, radius + float(layer) * 4.0,
				Color(tint, (0.040 if selected else 0.020) * float(4 - layer)))
	draw_circle(center, radius + 3.0 * _zoom, _chrome("020604"))
	draw_circle(center, radius, _chrome("0b1514") if unlocked else _chrome("070d0c"))
	draw_circle(center - Vector2.ONE * radius * 0.13, radius * 0.82,
		Color(tint, 0.08 if unlocked else 0.035))
	var frame_width: float = maxf(1.2, (4.0 if is_root else 2.5) * _zoom)
	draw_arc(center, radius, 0.0, TAU, 80 if is_root else 40,
		Color(tint, intensity), frame_width, true)
	if is_root:
		draw_arc(center, radius - 8.0 * _zoom, 0.0, TAU, 80, Color(tint, intensity * 0.42), 1.0, true)
		for index: int in range(12):
			var ray: Vector2 = Vector2.from_angle(float(index) * TAU / 12.0)
			draw_line(center + ray * (radius + 5.0 * _zoom), center + ray * (radius + 12.0 * _zoom),
				Color(tint, intensity * 0.7), maxf(1.0, _zoom * 2.0), true)
	elif _radius(node) >= 50.0:
		draw_arc(center, radius + 5.0 * _zoom, -PI * 0.15, PI * 0.75, 25, Color(tint, intensity * 0.60), 1.0, true)
		draw_arc(center, radius + 5.0 * _zoom, PI * 0.85, PI * 1.75, 25, Color(tint, intensity * 0.60), 1.0, true)
	_draw_skill_icon(node, center, radius * (0.63 if is_root else 0.62), Color(tint, intensity))
	if unlocked:
		var check_center: Vector2 = center + Vector2(0.68, 0.65) * radius
		draw_circle(check_center, maxf(4.0, 9.0 * _zoom), _chrome("0a1510"))
		draw_polyline(PackedVector2Array([
			check_center + Vector2(-4.0, 0.0) * _zoom,
			check_center + Vector2(-1.0, 3.0) * _zoom,
			check_center + Vector2(5.0, -4.0) * _zoom,
		]), Color(tint, 0.95), maxf(1.2, 2.5 * _zoom), true)
	elif affordable:
		draw_circle(center + Vector2(0.70, 0.70) * radius, maxf(2.5, 5.0 * _zoom), Color("efd994"))
	if selected:
		draw_arc(center, radius + 8.0, -PI * 0.12, PI * 0.80, 30, Color("f4e9c7"), 2.0, true)
		draw_arc(center, radius + 8.0, PI * 0.88, PI * 1.80, 30, Color("f4e9c7"), 2.0, true)


func _draw_skill_icon(node: Dictionary, center: Vector2, radius: float, tint: Color) -> void:
	var icon_rect: Rect2 = Rect2(center - Vector2.ONE * radius, Vector2.ONE * radius * 2.0)
	SkillIcon.draw_icon(self, str(node.get("icon", node.get("id", ""))), icon_rect, tint)


func _select_at(point: Vector2) -> void:
	var best_id: String = ""
	var best_distance: float = INF
	for entry: Dictionary in hit_points:
		var distance: float = point.distance_to(entry["position"])
		if distance <= float(entry["radius"]) and distance < best_distance:
			best_id = str(entry["id"])
			best_distance = distance
	if not best_id.is_empty():
		select_node(best_id, true)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_handle_touch(event)
		accept_event()
	elif event is InputEventScreenDrag:
		_handle_drag(event)
		accept_event()
	elif event is InputEventMagnifyGesture:
		_zoom_at(_zoom * event.factor, event.position)
		accept_event()
	elif event is InputEventPanGesture:
		_pan -= event.delta * 18.0
		_refresh_layout()
		accept_event()
	elif event is InputEventMouseButton:
		if not _touches.is_empty() or Time.get_ticks_msec() - _last_touch_msec < 500:
			accept_event()
			return
		if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
			_zoom_at(_zoom * 1.18, event.position)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
			_zoom_at(_zoom / 1.18, event.position)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_mouse_down = true
				_mouse_dragged = false
				_mouse_origin = event.position
				_mouse_last = event.position
			elif _mouse_down:
				_mouse_down = false
				if not _mouse_dragged and event.position.distance_to(_mouse_origin) <= TAP_DEADZONE:
					_select_at(event.position)
			accept_event()
	elif event is InputEventMouseMotion and _mouse_down:
		if event.position.distance_to(_mouse_origin) > TAP_DEADZONE:
			_mouse_dragged = true
		if _mouse_dragged:
			_pan += event.position - _mouse_last
			_refresh_layout()
		_mouse_last = event.position
		accept_event()


func _handle_touch(event: InputEventScreenTouch) -> void:
	if event.pressed and not Rect2(Vector2.ZERO, size).has_point(event.position):
		return
	_last_touch_msec = Time.get_ticks_msec()
	_mouse_down = false
	if event.pressed:
		_touches[event.index] = event.position
		if _touches.size() == 1:
			_touch_index = event.index
			_touch_origin = event.position
			_touch_last = event.position
			_gesture_cancelled = false
		else:
			_gesture_cancelled = true
			_begin_pinch()
	else:
		if not _touches.has(event.index):
			return
		var can_select: bool = _touches.size() == 1 and not _gesture_cancelled and not event.canceled
		can_select = can_select and event.index == _touch_index and event.position.distance_to(_touch_origin) <= TAP_DEADZONE
		_touches.erase(event.index)
		if can_select:
			_select_at(event.position)
		if _touches.is_empty():
			_touch_index = -1
			_pinch_distance = 0.0
		elif _touches.size() == 1:
			_touch_index = int(_touches.keys()[0])
			_touch_last = _touches[_touch_index]
			_gesture_cancelled = true
		else:
			_begin_pinch()


func _begin_pinch() -> void:
	if _touches.size() < 2:
		return
	var keys: Array = _touches.keys()
	var first: Vector2 = _touches[keys[0]]
	var second: Vector2 = _touches[keys[1]]
	_pinch_center = (first + second) * 0.5
	_pinch_distance = first.distance_to(second)


func _handle_drag(event: InputEventScreenDrag) -> void:
	if not _touches.has(event.index):
		return
	_last_touch_msec = Time.get_ticks_msec()
	_touches[event.index] = event.position
	if _touches.size() >= 2:
		_gesture_cancelled = true
		var old_center: Vector2 = _pinch_center
		var old_distance: float = _pinch_distance
		_begin_pinch()
		if old_distance > 4.0 and _pinch_distance > 4.0:
			_zoom_at(_zoom * _pinch_distance / old_distance, old_center)
		_pan += _pinch_center - old_center
		_refresh_layout()
	elif event.index == _touch_index:
		if event.position.distance_to(_touch_origin) > TAP_DEADZONE:
			_gesture_cancelled = true
		if _gesture_cancelled:
			_pan += event.position - _touch_last
			_refresh_layout()
		_touch_last = event.position


func _cancel_gesture() -> void:
	_touches.clear()
	_touch_index = -1
	_pinch_distance = 0.0
	_gesture_cancelled = true
	_mouse_down = false
	_mouse_dragged = true


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_WINDOW_FOCUS_OUT or what == NOTIFICATION_VISIBILITY_CHANGED and not is_visible_in_tree():
		_cancel_gesture()
