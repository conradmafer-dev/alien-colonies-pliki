extends Control
## Update 100: cached map with a separate, clock-driven fleet overlay.
## Server-defined concentric rings and travel links, with a legacy ellipse fallback.
signal system_selected(system_id: String)
signal view_changed(zoom: float)

const Routes = preload("res://client/scripts/galaxy_routes.gd")
const RaceTheme = preload("res://client/scripts/race_theme.gd")
const FLEET_COLORS: Dictionary = {
	"scout": Color("91a8c8"), "attack": Color("ff9295"),
	"alliance_attack": Color("ff9295"), "transport": Color("e4c17a"),
	"colonize": Color("9be4ad"), "alliance_defense": Color("bcabff"),
	"returning": Color("b6bdc8"), "expedition": Color("d7a6ff"),
}

static func fleet_color(fleet: Dictionary) -> Color:
	if str(fleet.get("status", "")) == "returning":
		return FLEET_COLORS["returning"]
	if str(fleet.get("mission", "scout")) == "scout":
		return RaceTheme.color(Color("91c89b"))
	return FLEET_COLORS.get(str(fleet.get("mission", "scout")), FLEET_COLORS["scout"])

const CHROME_KEYS: Array[String] = ["bg", "panel", "border", "accent", "text", "muted"]

const TAP_DEADZONE: float = 12.0
const MIN_ZOOM: float = 1.0
const MAX_ZOOM: float = 6.0
const DEFAULT_FOCUS_ZOOM: float = MAX_ZOOM
const ZOOM_STEP: float = 1.4
const ORBIT_FLATTENING: float = 0.60
const GALAXY_ART_SCALE: float = 1.65
const GALAXY_CORE_POINTS: Dictionary = {
	"aurora": Vector2(0.495052083333, 0.465234375000),
	"nexus": Vector2(0.500260416667, 0.500390625000),
	"omega": Vector2(0.501302083333, 0.501171875000),
	"zephyr": Vector2(0.499479166667, 0.498828125000),
	"eclipse": Vector2(0.502466001157, 0.496131004051),
	"void": Vector2(0.500034172871, 0.499450871045),
}
const GALAXY_ART_PATH: String = "res://client/assets/art/galaxies/aurora.webp"
const OWNER_COLORS: Dictionary = {
	"own": Color("91c89b"), "player": Color("ffc879"),
	"alien": Color("ff777f"), "empty": Color("aabdaf"),
}

var route_origin_id: String = ""
var route_target_id: String = ""
var _authoritative_route: Dictionary = {}

var systems: Array = []
var player_id: String = ""
var selected_id: String = ""
var hit_points: Array[Dictionary] = []
var label_layout: Array[Dictionary] = []
var font: Font
var _zoom: float = DEFAULT_FOCUS_ZOOM
var _pan: Vector2 = Vector2.ZERO
var _resize_focus_id: String = ""
var _tap_origin: Vector2 = Vector2.ZERO
var _last_pointer: Vector2 = Vector2.ZERO
var _tap_pending: bool = false
var _pointer_down: bool = false
var _touch_index: int = -1
var _using_touch: bool = false
var _touch_points: Dictionary = {}
var _pinch_active: bool = false
var _normalized_positions: Dictionary = {}
var _ring_points: PackedVector2Array = PackedVector2Array()
var _ring_paths: Array[PackedVector2Array] = []
var _has_ring_topology: bool = false
var _graph: Dictionary = {}
var _bridges: Array[Dictionary] = []
var _route_system_ids: Array[String] = []
var _galaxy_art: Texture2D
var _palette: Dictionary = {}
var _fleet_overlay: FleetOverlay
var _projection_revision: int = 0


func _init() -> void:
	# This canvas draws its own chrome, outside Control theme overrides. Start
	# with the shared palette even before a host/state refresh supplies colors.
	var shared: Dictionary = RaceTheme.palette()
	for key: String in CHROME_KEYS:
		_palette[key] = shared[key]
	set_meta("touch_scroll_preserve_input", true)
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	texture_repeat = CanvasItem.TEXTURE_REPEAT_DISABLED


func _ready() -> void:
	custom_minimum_size = Vector2(0, 640)
	font = ThemeDB.fallback_font
	if ResourceLoader.exists(GALAXY_ART_PATH):
		_galaxy_art = load(GALAXY_ART_PATH) as Texture2D
	I18n.language_changed.connect(_refresh_layout)
	resized.connect(_on_resized)
	_rebuild_projection()
	_fleet_overlay = FleetOverlay.new()
	_fleet_overlay.map = self
	add_child(_fleet_overlay)
	_fleet_overlay.rebuild()


func set_fleets(fleets: Array, server_now: float) -> void:
	if is_instance_valid(_fleet_overlay):
		_fleet_overlay.set_fleets(fleets, server_now)


func set_race_palette(value: Dictionary) -> void:
	for key: String in _palette:
		if value.has(key):
			_palette[key] = RaceTheme.color(value[key])
	_refresh_layout()


func set_galaxy_art(texture: Texture2D) -> void:
	if _galaxy_art != texture and texture != null:
		_galaxy_art = texture
		queue_redraw()


func set_data(value: Array, owner: String, selected: String) -> void:
	systems = value
	player_id = owner
	selected_id = selected
	_rebuild_projection()


func set_route(origin_id: String, target_id: String, route: Dictionary = {}) -> void:
	if route_origin_id == origin_id and route_target_id == target_id and _authoritative_route == route:
		return
	route_origin_id = origin_id
	route_target_id = target_id
	_authoritative_route = route.duplicate(true)
	_rebuild_route()
	queue_redraw()

func get_zoom() -> float:
	return _zoom


func zoom_in() -> void:
	_set_zoom(_zoom * ZOOM_STEP, _plot_rect().get_center())


func zoom_out() -> void:
	_set_zoom(_zoom / ZOOM_STEP, _plot_rect().get_center())


func reset_view() -> void:
	_resize_focus_id = ""
	_zoom = MIN_ZOOM
	_pan = Vector2.ZERO
	_refresh_layout()
	view_changed.emit(_zoom)


func focus_system(id: String, requested_zoom: float = 0.0) -> void:
	var value: Dictionary = _system_by_id(id)
	if value.is_empty():
		return
	selected_id = id
	_resize_focus_id = id
	_zoom = clampf(requested_zoom, MIN_ZOOM, MAX_ZOOM) if requested_zoom > 0.0 else maxf(_zoom, 2.0)
	_pan = (_plot_rect().get_center() - _base_position(value)) * _zoom
	_refresh_layout()
	view_changed.emit(_zoom)


func _on_resized() -> void:
	_rebuild_projection()
	# Container sizing can finish after opening the map. Keep the requested
	# system centred until the player starts moving or zooming the camera.
	if not _resize_focus_id.is_empty():
		focus_system(_resize_focus_id, _zoom)


func ownership_counts(value: Dictionary) -> Dictionary:
	var counts: Dictionary = {"own": 0, "player": 0, "alien": 0, "empty": 0}
	for planet: Dictionary in value.get("planets", []):
		var owner_type: String = str(planet.get("owner_type", "empty"))
		if owner_type == "alien":
			counts["alien"] += 1
		elif owner_type == "player":
			var category: String = "own" if not player_id.is_empty() and str(planet.get("owner_id", "")) == player_id else "player"
			counts[category] += 1
		elif owner_type == "empty":
			counts["empty"] += 1
	return counts



func _plot_rect() -> Rect2:
	return Rect2(Vector2(54, 115), Vector2(maxf(size.x - 108, 1), maxf(size.y - 210, 1)))


func _visible_rect() -> Rect2:
	return Rect2(Vector2(12, 82), Vector2(maxf(size.x - 24, 1), maxf(size.y - 126, 1)))


func _system_by_id(id: String) -> Dictionary:
	for value: Dictionary in systems:
		if str(value.get("id", "")) == id:
			return value
	return {}


func _ellipse_radius() -> Vector2:
	var plot: Rect2 = _plot_rect()
	# Fit one horizontal ellipse into the available space. Deriving each axis
	# independently from the panel made narrow portrait maps circular or tall.
	# Keeping both axes tied together also preserves the shape after rotation.
	var horizontal: float = minf(plot.size.x * 0.5, plot.size.y * 0.43 / ORBIT_FLATTENING)
	return Vector2(horizontal, horizontal * ORBIT_FLATTENING)


func _rebuild_projection() -> void:
	_projection_revision += 1
	_normalized_positions.clear()
	_ring_points.clear()
	_ring_paths.clear()
	_has_ring_topology = _valid_ring_topology()
	var radius: Vector2 = _ellipse_radius()
	var samples: Array[Vector2] = []
	var lengths: Array[float] = [0.0]
	# Equal arc lengths keep the ends of the projected ellipse readable. All
	# rings share the same phase, so bridge placement follows server ring_order.
	for index: int in range(721):
		var angle: float = -PI * 0.5 + TAU * float(index) / 720.0
		var point: Vector2 = Vector2(cos(angle), sin(angle)) * radius
		samples.append(point)
		if index > 0:
			lengths.append(lengths.back() + point.distance_to(samples[index - 1]))
		if index % 4 == 0:
			_ring_points.append(point)
	var ordered: Array = systems.duplicate()
	ordered.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return _id_before(str(a.get("id", "")), str(b.get("id", ""))))
	var ring_radii: Dictionary = {}
	for index: int in range(ordered.size()):
		var value: Dictionary = ordered[index]
		var id: String = str(value.get("id", ""))
		var count: int = int(value["ring_size"]) if _has_ring_topology else ordered.size()
		var slot: int = int(value["ring_order"]) if _has_ring_topology else index
		var scale: float = float(value["ring_radius"]) if _has_ring_topology else 1.0
		if _has_ring_topology:
			ring_radii[int(value["ring_index"])] = scale
		if count == 1 and not _has_ring_topology:
			_normalized_positions[id] = Vector2.ZERO
			continue
		var wanted: float = lengths.back() * float(slot) / float(count)
		var sample_index: int = 1
		while sample_index < lengths.size() - 1 and lengths[sample_index] < wanted:
			sample_index += 1
		var span: float = lengths[sample_index] - lengths[sample_index - 1]
		var fraction: float = (wanted - lengths[sample_index - 1]) / maxf(span, 0.001)
		_normalized_positions[id] = samples[sample_index - 1].lerp(samples[sample_index], fraction) * scale
	if _has_ring_topology:
		var rings: Array = ring_radii.keys()
		rings.sort()
		for ring: int in rings:
			var path: PackedVector2Array = PackedVector2Array()
			for point: Vector2 in _ring_points:
				path.append(point * float(ring_radii[ring]))
			_ring_paths.append(path)
	else:
		_ring_paths.append(_ring_points)
	_rebuild_graph()
	_rebuild_route()
	_refresh_layout()


func _valid_ring_topology() -> bool:
	if systems.is_empty():
		return false
	for value: Dictionary in systems:
		if not value.has("ring_index") or not value.has("ring_order") or not value.has("ring_size") or not value.has("ring_radius") or not value.get("connections") is Array:
			return false
		if int(value["ring_index"]) < 0 or int(value["ring_size"]) < 1 or int(value["ring_order"]) < 0 or int(value["ring_order"]) >= int(value["ring_size"]) or float(value["ring_radius"]) <= 0.0 or float(value["ring_radius"]) > 1.0:
			return false
	return true


func _id_before(left: String, right: String) -> bool:
	return left.naturalnocasecmp_to(right) < 0


func _rebuild_graph() -> void:
	_graph.clear()
	_bridges.clear()
	if not _has_ring_topology:
		return
	_graph = Routes.graph(systems)
	for id: String in _graph:
		for edge: Dictionary in _graph[id]:
			var target: String = str(edge["system_id"])
			if str(edge["kind"]) == "bridge" and _id_before(id, target):
				_bridges.append({"from": id, "to": target})
	_bridges.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return _id_before(str(a["from"]), str(b["from"])) if str(a["from"]) != str(b["from"]) else _id_before(str(a["to"]), str(b["to"])))


func _route_uses_corridors() -> bool:
	return str(_authoritative_route.get("mode", "")) not in ["tunnel", "intergalactic"] and str(_authoritative_route.get("travel_mode", "")) not in ["tunnel", "intergalactic"]


func _rebuild_route() -> void:
	_route_system_ids.clear()
	if not _has_ring_topology or not _route_uses_corridors():
		return
	var supplied: Variant = _authoritative_route.get("system_ids", [])
	if supplied is Array and not supplied.is_empty() and str(supplied[0]) == route_origin_id and str(supplied[-1]) == route_target_id:
		var valid: bool = true
		for index: int in range(supplied.size()):
			var id: String = str(supplied[index])
			if not _graph.has(id):
				valid = false
				break
			if index > 0:
				var linked: bool = false
				for edge: Dictionary in _graph.get(str(supplied[index - 1]), []):
					if str(edge["system_id"]) == id:
						linked = true
						break
				if not linked:
					valid = false
					break
		if valid:
			for id: Variant in supplied:
				_route_system_ids.append(str(id))
			return
	var found: Dictionary = Routes.shortest_path(_graph, route_origin_id, route_target_id)
	for id: Variant in found.get("system_ids", []):
		_route_system_ids.append(str(id))


func get_route_system_ids() -> Array[String]:
	return _route_system_ids.duplicate()


func _base_position(value: Dictionary) -> Vector2:
	return _plot_rect().get_center() + Vector2(_normalized_positions.get(str(value.get("id", "")), Vector2.ZERO))


func _map_to_screen(point: Vector2) -> Vector2:
	return _plot_rect().get_center() + point * _zoom + _pan


func _screen_position(value: Dictionary) -> Vector2:
	return _map_to_screen(Vector2(_normalized_positions.get(str(value.get("id", "")), Vector2.ZERO)))


func _clamp_pan() -> void:
	var limits: Vector2 = _plot_rect().size * (_zoom - 1.0) * 0.5
	if _zoom > MIN_ZOOM:
		# Outer-ring colonies must also be able to reach the viewport centre.
		for position: Vector2 in _normalized_positions.values():
			limits = limits.max(position.abs() * _zoom)
	if systems.size() <= 1:
		limits = Vector2.ZERO
	_pan = _pan.clamp(-limits, limits)


func _refresh_layout() -> void:
	_clamp_pan()
	if is_instance_valid(_fleet_overlay):
		_fleet_overlay.rebuild()
	hit_points.clear()
	if size.x < 100 or size.y < 210:
		label_layout.clear()
		queue_redraw()
		return
	var visible_area: Rect2 = _visible_rect().grow(-13)
	for value: Dictionary in systems:
		var center: Vector2 = _screen_position(value)
		if visible_area.has_point(center):
			hit_points.append({"position": center, "id": str(value.get("id", ""))})
	_layout_labels()
	queue_redraw()


func _set_zoom(value: float, anchor: Vector2) -> void:
	_resize_focus_id = ""
	var next_zoom: float = clampf(value, MIN_ZOOM, MAX_ZOOM)
	if is_equal_approx(next_zoom, _zoom):
		return
	var pivot: Vector2 = _plot_rect().get_center()
	_pan = anchor - pivot - (anchor - pivot - _pan) * (next_zoom / _zoom)
	_zoom = next_zoom
	_refresh_layout()
	view_changed.emit(_zoom)


func _layout_labels() -> void:
	label_layout.clear()
	if font == null:
		font = ThemeDB.fallback_font
	var ordered: Array[Dictionary] = hit_points.duplicate()
	ordered.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var priority_a: int = _label_priority(str(a["id"]))
		var priority_b: int = _label_priority(str(b["id"]))
		return priority_a > priority_b if priority_a != priority_b else str(a["id"]).naturalnocasecmp_to(str(b["id"])) < 0)
	var visible: Rect2 = _visible_rect().grow(-3)
	for target: Dictionary in ordered:
		var id: String = str(target["id"])
		var point: Vector2 = target["position"]
		var value: Dictionary = _system_by_id(id)
		var text_value: String = "? " + id.trim_prefix("s") if str(value.get("visibility", "")) == "unknown" else str(value.get("name", id))
		if text_value.length() > 19:
			text_value = text_value.left(18) + "…"
		var font_size: int = 19 if id == selected_id else (18 if _zoom >= 1.5 else 16)
		var text_size: Vector2 = font.get_string_size(text_value, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
		var box_size: Vector2 = Vector2(text_size.x + 10, font_size + 7)
		var direction: Vector2 = Vector2(_normalized_positions.get(id, Vector2.UP)).normalized()
		var outward: Vector2 = Vector2(signf(direction.x) * (box_size.x * 0.5 + 20), 0)
		if absf(direction.y) > 0.70:
			outward = Vector2(0, signf(direction.y) * (box_size.y * 0.5 + 18))
		var offsets: Array[Vector2] = [outward, outward * 1.75, outward + Vector2(22, 0), outward - Vector2(22, 0), Vector2(0, -30), Vector2(0, 30), -outward, -outward * 1.65]
		for offset: Vector2 in offsets:
			var rect: Rect2 = Rect2(point + offset - box_size * 0.5, box_size)
			if not visible.encloses(rect):
				continue
			var blocked: bool = false
			for prior: Dictionary in label_layout:
				if rect.grow(3).intersects(prior["rect"]):
					blocked = true
					break
			if not blocked:
				for other: Dictionary in hit_points:
					if rect.grow(16 if str(other["id"]) == selected_id else 12).has_point(other["position"]):
						blocked = true
						break
			if not blocked:
				label_layout.append({"id": id, "text": text_value, "rect": rect, "font_size": font_size, "star": point})
				break


func _label_priority(id: String) -> int:
	if id == selected_id:
		return 3
	return 2 if int(ownership_counts(_system_by_id(id))["own"]) > 0 else 1


func _draw() -> void:
	if font == null:
		font = ThemeDB.fallback_font
	draw_style_box(_panel(), Rect2(Vector2.ZERO, size))
	_draw_stars()
	_draw_galaxy()
	_draw_circuit()
	_draw_route()
	if systems.is_empty():
		_centered_text(I18n.t("Brak danych galaktyki"), size * 0.5, 23, _palette["muted"])
	for target: Dictionary in hit_points:
		_draw_system(_system_by_id(str(target["id"])), target["position"])
	_draw_labels()
	_draw_heading()
	_draw_footer()


func _draw_stars() -> void:
	for index: int in range(150):
		var raw_point: Vector2 = Vector2(fposmod(float(index * 173 + 19), maxf(size.x, 1.0)), fposmod(float(index * 89 + 33), maxf(size.y, 1.0)))
		var point: Vector2 = _map_to_screen(raw_point - _plot_rect().get_center())
		var alpha: float = 0.12 + float(index % 5) * 0.033
		draw_circle(point, 1.0 if index % 9 == 0 else 0.60, Color(0.76, 0.81, 0.90, alpha))


func _draw_galaxy() -> void:
	var center: Vector2 = _map_to_screen(Vector2.ZERO)
	var radius: Vector2 = _ellipse_radius()
	if _galaxy_art != null:
		var art_rect: Rect2 = _galaxy_art_rect()
		draw_texture_rect(_galaxy_art, art_rect, false, Color(0.85, 0.85, 0.90, 0.74))
		_draw_art_edge_fade(art_rect)
	else:
		# The map remains readable even while an optional art import is pending.
		for ring: int in range(15, 0, -1):
			draw_circle(center, float(ring) * radius.x * 0.035 * _zoom, Color(0.65, 0.65, 0.86, 0.016))
		for arm: int in range(4):
			var spiral: PackedVector2Array = PackedVector2Array()
			for sample: int in range(81):
				var fraction: float = float(sample) / 80.0
				var angle: float = fraction * PI * 1.45 + float(arm) * PI * 0.5
				spiral.append(_map_to_screen(Vector2(cos(angle), sin(angle)) * radius * fraction * 0.75))
			draw_polyline(spiral, Color(0.57, 0.61, 0.80, 0.13), 8.0 * _zoom, true)
	if _zoom < 1.6 and not systems.is_empty() and (not _has_ring_topology or radius.x > 200.0):
		_centered_text(I18n.t("JĄDRO GALAKTYKI"), center + Vector2(0, 5), 14, Color(0.84, 0.86, 0.92, 0.68))


func _galaxy_art_rect() -> Rect2:
	var center: Vector2 = _map_to_screen(Vector2.ZERO)
	if _galaxy_art == null:
		return Rect2(center, Vector2.ZERO)
	var source_size: Vector2 = _galaxy_art.get_size()
	if source_size.x <= 0.0 or source_size.y <= 0.0:
		return Rect2(center, Vector2.ZERO)
	var radius: Vector2 = _ellipse_radius()
	var bounds: Vector2 = Vector2(radius.x * 2.2, radius.y * 2.0) * _zoom * GALAXY_ART_SCALE
	var fit_scale: float = minf(bounds.x / source_size.x, bounds.y / source_size.y)
	var art_size: Vector2 = source_size * fit_scale
	var focal: Vector2 = GALAXY_CORE_POINTS.get(_galaxy_art.resource_path.get_file().get_basename(), Vector2(0.5, 0.5))
	return Rect2(center - art_size * focal, art_size)


func _draw_art_edge_fade(rect: Rect2) -> void:
	# Fade the decorative texture in map space, without changing the asset.
	var depth: float = 40.0 * _zoom
	var opaque: Color = _palette["bg"]
	var clear: Color = Color(opaque, 0.0)
	var left: float = rect.position.x
	var top: float = rect.position.y
	var right: float = rect.end.x
	var bottom: float = rect.end.y
	draw_polygon(PackedVector2Array([Vector2(left, top), Vector2(right, top), Vector2(right, top + depth), Vector2(left, top + depth)]), PackedColorArray([opaque, opaque, clear, clear]))
	draw_polygon(PackedVector2Array([Vector2(left, bottom), Vector2(right, bottom), Vector2(right, bottom - depth), Vector2(left, bottom - depth)]), PackedColorArray([opaque, opaque, clear, clear]))
	draw_polygon(PackedVector2Array([Vector2(left, top), Vector2(left, bottom), Vector2(left + depth, bottom), Vector2(left + depth, top)]), PackedColorArray([opaque, opaque, clear, clear]))
	draw_polygon(PackedVector2Array([Vector2(right, top), Vector2(right, bottom), Vector2(right - depth, bottom), Vector2(right - depth, top)]), PackedColorArray([opaque, opaque, clear, clear]))


func _draw_circuit() -> void:
	if systems.size() <= 1:
		return
	var accent: Color = _palette["accent"]
	for points: PackedVector2Array in _ring_paths:
		var path: PackedVector2Array = PackedVector2Array()
		for point: Vector2 in points:
			path.append(_map_to_screen(point))
		draw_polyline(path, Color(accent, 0.045), 8.0, true)
		draw_polyline(path, Color(accent, 0.29), 1.4, true)
	for bridge: Dictionary in _bridges:
		var start: Vector2 = _map_to_screen(_normalized_positions[bridge["from"]])
		var end: Vector2 = _map_to_screen(_normalized_positions[bridge["to"]])
		draw_line(start, end, Color(accent, 0.07), 7.0, true)
		draw_line(start, end, Color(accent, 0.50), 1.8, true)
		# A small gate mark distinguishes bridges from decorative orbit lines.
		var middle: Vector2 = (start + end) * 0.5
		var normal: Vector2 = (end - start).orthogonal().normalized() * 4.0
		draw_line(middle - normal, middle + normal, Color(accent, 0.75), 2.0, true)


func _route_segment_points(from_id: String, to_id: String) -> PackedVector2Array:
	var start: Vector2 = _normalized_positions[from_id]
	var end: Vector2 = _normalized_positions[to_id]
	var from_system: Dictionary = _system_by_id(from_id)
	var to_system: Dictionary = _system_by_id(to_id)
	if int(from_system.get("ring_index", -1)) != int(to_system.get("ring_index", -2)):
		return PackedVector2Array([_map_to_screen(start), _map_to_screen(end)])
	# Follow the orbit itself instead of cutting across a different ring.
	var radius: Vector2 = _ellipse_radius() * float(from_system.get("ring_radius", 1.0))
	var start_angle: float = atan2(start.y / maxf(radius.y, 0.001), start.x / maxf(radius.x, 0.001))
	var end_angle: float = atan2(end.y / maxf(radius.y, 0.001), end.x / maxf(radius.x, 0.001))
	var angle_delta: float = wrapf(end_angle - start_angle, -PI, PI)
	var points: PackedVector2Array = PackedVector2Array()
	for index: int in range(13):
		var angle: float = start_angle + angle_delta * float(index) / 12.0
		points.append(_map_to_screen(Vector2(cos(angle), sin(angle)) * radius))
	return points


func _draw_route() -> void:
	# A cross-galaxy origin is intentionally not plotted in this galaxy.
	var origin: Dictionary = _system_by_id(route_origin_id)
	var target: Dictionary = _system_by_id(route_target_id)
	if origin.is_empty() or target.is_empty():
		return
	var start: Vector2 = _screen_position(origin)
	var end: Vector2 = _screen_position(target)
	var accent: Color = _palette["accent"]
	draw_arc(start, 24, 0, TAU, 48, accent, 2.0, true)
	if _has_ring_topology:
		if not _route_uses_corridors():
			return
		for index: int in range(1, _route_system_ids.size()):
			var points: PackedVector2Array = _route_segment_points(_route_system_ids[index - 1], _route_system_ids[index])
			draw_polyline(points, Color(accent, 0.15), 8.0, true)
			draw_polyline(points, Color(accent, 0.96), 3.0, true)
		if _route_system_ids.size() > 1:
			var final_points: PackedVector2Array = _route_segment_points(_route_system_ids[-2], _route_system_ids[-1])
			_draw_route_arrow(final_points[-2], final_points[-1], accent)
		return
	# Old servers have no travel graph; retain their direct-distance preview.
	if start.distance_to(end) > 60:
		var direction: Vector2 = (end - start).normalized()
		var to: Vector2 = end - direction * 25
		draw_dashed_line(start + direction * 29, to, Color(accent, 0.8), 2.5, 10, true)
		_draw_route_arrow(start, to, accent)


func _draw_route_arrow(start: Vector2, end: Vector2, color: Color) -> void:
	if start.is_equal_approx(end):
		return
	var direction: Vector2 = (end - start).normalized()
	var normal: Vector2 = direction.orthogonal()
	var to: Vector2 = end - direction * (13.0 if _has_ring_topology else 0.0)
	draw_polyline(PackedVector2Array([to - direction * 9 + normal * 5, to, to - direction * 9 - normal * 5]), color, 2.5, true)

func _owner_color(category: String) -> Color:
	return _palette["accent"] if category == "own" else OWNER_COLORS[category]


func _system_glyph_radius(center: Vector2) -> float:
	var radius: float = 12.0 if _zoom < 1.5 else 16.0
	if not _has_ring_topology:
		return radius
	# On a narrow destination picker the overview still shows all sixty
	# systems. Shrink markers, not hit targets, so intel rings do not overlap.
	for other: Dictionary in hit_points:
		var distance: float = center.distance_to(other["position"])
		if distance > 0.1:
			radius = minf(radius, maxf(4.5, distance * 0.26))
	return radius


func _draw_system(value: Dictionary, center: Vector2) -> void:
	if value.is_empty():
		return
	var selected: bool = str(value.get("id", "")) == selected_id
	var counts: Dictionary = ownership_counts(value)
	var categories: Array[String] = []
	for category: String in ["own", "player", "alien", "empty"]:
		if int(counts[category]) > 0:
			categories.append(category)
	var radius: float = _system_glyph_radius(center)
	var visibility: String = str(value.get("visibility", ""))
	if visibility == "unknown":
		draw_circle(center, radius, Color(_palette["panel"], 0.94))
		draw_arc(center, radius, -PI, PI, 32, _palette["accent"] if selected else _palette["muted"], 1.4, true)
		var question_size: int = mini(18, maxi(10, int(radius * 1.5)))
		_centered_text("?", center + Vector2(0, question_size * 0.33), question_size, _palette["muted"])
		return
	var intel_radius: float = radius + minf(7.0, radius * 0.4) if _has_ring_topology else 21.0
	if visibility == "observed":
		draw_arc(center, intel_radius, -PI, PI, 48, Color(_palette["accent"], .55), 1.3, true)
	elif visibility in ["scouted", "remembered"]:
		for segment: int in range(8):
			draw_arc(center, intel_radius, segment * TAU / 8, segment * TAU / 8 + .4, 6, Color(_palette["muted"], .55), 1.3, true)
	var star_tint: Color = Color("e5eefb")
	if selected:
		draw_circle(center, radius + 9, Color(_palette["accent"], 0.15))
		draw_arc(center, radius + 7, -PI, PI, 64, _palette["accent"], 1.8, true)
	for ring: int in range(4, 0, -1):
		draw_circle(center, 4.0 + float(ring) * 2, Color(star_tint, 0.025 + float(4 - ring) * 0.015))
	draw_circle(center, 3.5, star_tint)
	draw_circle(center + Vector2(-1, -1), 1.1, Color.WHITE)
	for index: int in range(categories.size()):
		var arc_span: float = TAU / float(categories.size())
		var start: float = -PI * 0.5 + float(index) * arc_span + 0.10
		draw_arc(center, radius, start, start + arc_span - 0.20, 26, _owner_color(categories[index]), 2.6, true)


func _draw_labels() -> void:
	for item: Dictionary in label_layout:
		var rect: Rect2 = item["rect"]
		var star: Vector2 = item["star"]
		var selected: bool = str(item["id"]) == selected_id
		var box: StyleBoxFlat = StyleBoxFlat.new()
		box.bg_color = Color(_palette["bg"], 0.88)
		box.set_corner_radius_all(4)
		draw_style_box(box, rect)
		if rect.get_center().distance_to(star) > 48:
			var near: Vector2 = star.clamp(rect.position, rect.end)
			draw_line(star.lerp(near, 0.35), near, Color(_palette["muted"], 0.25), 1, true)
		draw_string(font, rect.position + Vector2(5, int(item["font_size"])), str(item["text"]), HORIZONTAL_ALIGNMENT_LEFT, -1, int(item["font_size"]), _palette["accent"] if selected else _palette["text"])


func _draw_heading() -> void:
	draw_rect(Rect2(Vector2(1, 1), Vector2(maxf(size.x - 2, 1), 72)), Color(_palette["panel"], 1.0))
	var active: Dictionary = _system_by_id(selected_id)
	if active.is_empty():
		draw_string(font, Vector2(20, 30), I18n.t("WYBIERZ UKŁAD"), HORIZONTAL_ALIGNMENT_LEFT, size.x - 40, 20, _palette["accent"])
		draw_string(font, Vector2(20, 57), I18n.t("%d układów • dotknij gwiazdy") % systems.size(), HORIZONTAL_ALIGNMENT_LEFT, size.x - 40, 18, _palette["muted"])
		return
	var name_text: String = str(active.get("name", selected_id))
	var available_width: float = maxf(size.x - 40, 1)
	var heading_size: int = 26
	while font.get_string_size(name_text, HORIZONTAL_ALIGNMENT_LEFT, -1, heading_size).x > available_width and heading_size > 16:
		heading_size -= 1
	draw_string(font, Vector2(20, 30), name_text, HORIZONTAL_ALIGNMENT_LEFT, available_width, heading_size, _palette["text"])
	if str(active.get("visibility", "")) == "unknown":
		draw_string(font, Vector2(20, 58), I18n.t("Nieznany układ · wyślij zwiad"), HORIZONTAL_ALIGNMENT_LEFT, available_width, 18, _palette["muted"])
		return
	var counts: Dictionary = ownership_counts(active)
	var labels: Dictionary = {"own": I18n.t("Twoje"), "player": I18n.t("Gracze"), "alien": I18n.t("Rój"), "empty": I18n.t("Wolne")}
	var cursor: float = 20
	for category: String in ["own", "player", "alien", "empty"]:
		if int(counts[category]) <= 0:
			continue
		var text_value: String = "%s %d" % [str(labels[category]), int(counts[category])]
		draw_circle(Vector2(cursor + 3, 52), 3, _owner_color(category))
		draw_string(font, Vector2(cursor + 12, 58), text_value, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, _owner_color(category))
		cursor += font.get_string_size(text_value, HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x + 31


func _draw_footer() -> void:
	draw_rect(Rect2(Vector2(1, size.y - 36), Vector2(maxf(size.x - 2, 1), 35)), Color(_palette["panel"], 1.0))
	draw_string(font, Vector2(16, size.y - 13), I18n.t("Przesuwaj • zbliżaj dwoma palcami"), HORIZONTAL_ALIGNMENT_LEFT, maxf(size.x - 100, 1), 14, _palette["muted"])
	draw_string(font, Vector2(size.x - 62, size.y - 12), "×%.1f" % _zoom, HORIZONTAL_ALIGNMENT_LEFT, 50, 16, _palette["text"])


func _centered_text(value: String, point: Vector2, font_size: int, color: Color) -> void:
	var text_size: Vector2 = font.get_string_size(value, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
	draw_string(font, point - Vector2(text_size.x * 0.5, 0), value, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _panel() -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = _palette["bg"]
	box.border_color = _palette["border"]
	box.set_border_width_all(1)
	box.set_corner_radius_all(20)
	return box


func _gui_input(event: InputEvent) -> void:
	# Android emits a mouse event for primary touch. Never process both.
	if event.device == -1:
		return
	if event is InputEventScreenTouch:
		_handle_touch(event as InputEventScreenTouch)
	elif event is InputEventScreenDrag:
		var drag: InputEventScreenDrag = event as InputEventScreenDrag
		if not _touch_points.has(drag.index):
			return
		if _touch_points.size() >= 2:
			var keys: Array = _touch_points.keys()
			var old_a: Vector2 = _touch_points[keys[0]]
			var old_b: Vector2 = _touch_points[keys[1]]
			_touch_points[drag.index] = drag.position
			var new_a: Vector2 = _touch_points[keys[0]]
			var new_b: Vector2 = _touch_points[keys[1]]
			var previous_zoom: float = _zoom
			_set_zoom(_zoom * new_a.distance_to(new_b) / maxf(old_a.distance_to(old_b), 1.0), (old_a + old_b) * 0.5)
			if not is_equal_approx(_zoom, previous_zoom) or _zoom > MIN_ZOOM:
				_resize_focus_id = ""
				_pan += (new_a + new_b - old_a - old_b) * 0.5
				_refresh_layout()
		elif _using_touch and drag.index == _touch_index and _pointer_down:
			_touch_points[drag.index] = drag.position
			_drag_pointer(drag.position)
		accept_event()
	elif event is InputEventMagnifyGesture:
		var magnify: InputEventMagnifyGesture = event as InputEventMagnifyGesture
		_set_zoom(_zoom * magnify.factor, magnify.position)
		_tap_pending = false
		accept_event()
	elif event is InputEventMouseButton and not _using_touch:
		var mouse_event: InputEventMouseButton = event as InputEventMouseButton
		if mouse_event.button_index == MOUSE_BUTTON_WHEEL_UP or mouse_event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			if mouse_event.pressed and Rect2(Vector2.ZERO, size).has_point(mouse_event.position):
				_set_zoom(_zoom * (1.2 if mouse_event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.2), mouse_event.position)
				accept_event()
			return
		if mouse_event.button_index != MOUSE_BUTTON_LEFT:
			return
		if mouse_event.pressed and Rect2(Vector2.ZERO, size).has_point(mouse_event.position):
			_begin_tap(mouse_event.position)
			accept_event()
		elif not mouse_event.pressed and _pointer_down:
			_finish_tap(mouse_event.position)
			accept_event()
	elif event is InputEventMouseMotion and not _using_touch and _pointer_down:
		_drag_pointer((event as InputEventMouseMotion).position)
		accept_event()


func _handle_touch(event: InputEventScreenTouch) -> void:
	if event.pressed:
		if not Rect2(Vector2.ZERO, size).has_point(event.position) or _touch_points.size() >= 2:
			return
		_touch_points[event.index] = event.position
		_using_touch = true
		if _touch_points.size() == 1:
			_touch_index = event.index
			_begin_tap(event.position)
		else:
			_pinch_active = true
			_tap_pending = false
		accept_event()
	elif _touch_points.has(event.index):
		_touch_points.erase(event.index)
		if event.canceled:
			_tap_pending = false
		if _pinch_active:
			_tap_pending = false
			if not _touch_points.is_empty():
				_touch_index = int(_touch_points.keys()[0])
				_last_pointer = _touch_points[_touch_index]
				_tap_origin = _last_pointer
			else:
				_clear_gesture()
		elif _touch_points.is_empty():
			_finish_tap(event.position)
			_clear_gesture()
		accept_event()


func _notification(what: int) -> void:
	if what == NOTIFICATION_SCROLL_BEGIN or what == NOTIFICATION_VISIBILITY_CHANGED or what == NOTIFICATION_EXIT_TREE:
		_clear_gesture()


func _clear_gesture() -> void:
	_tap_pending = false
	_pointer_down = false
	_touch_index = -1
	_using_touch = false
	_pinch_active = false
	_touch_points.clear()


func _begin_tap(point: Vector2) -> void:
	_tap_origin = point
	_last_pointer = point
	_tap_pending = true
	_pointer_down = true


func _cancel_moved_tap(point: Vector2) -> void:
	if point.distance_to(_tap_origin) > TAP_DEADZONE:
		_tap_pending = false


func _drag_pointer(point: Vector2) -> void:
	var was_pending: bool = _tap_pending
	_cancel_moved_tap(point)
	if not _tap_pending:
		_resize_focus_id = ""
		var old_pan: Vector2 = _pan
		_pan += point - (_tap_origin if was_pending else _last_pointer)
		_clamp_pan()
		if not _pan.is_equal_approx(old_pan):
			_refresh_layout()
	_last_pointer = point


func _finish_tap(point: Vector2) -> void:
	var select: bool = _tap_pending and point.distance_to(_tap_origin) <= TAP_DEADZONE and _visible_rect().has_point(point)
	_tap_pending = false
	_pointer_down = false
	if not select:
		return
	# Labels are real touch targets too; tapping a long name must not select
	# a neighbouring star merely because its centre happens to be closer.
	for label: Dictionary in label_layout:
		if Rect2(label["rect"]).has_point(point):
			selected_id = str(label["id"])
			_refresh_layout()
			system_selected.emit(selected_id)
			return
	var nearest: String = ""
	var distance: float = 30.0 if _zoom < 1.5 else 39.0
	for target: Dictionary in hit_points:
		var candidate: Vector2 = target["position"]
		var current_distance: float = point.distance_to(candidate)
		if current_distance < distance:
			distance = current_distance
			nearest = str(target["id"])
	if not nearest.is_empty():
		selected_id = nearest
		_refresh_layout()
		system_selected.emit(nearest)


# Timing and distance allocation are shared with the web client (fleet-motion.js).
class FleetMotion:
	extends RefCounted

	static func plan(fleet: Dictionary) -> Dictionary:
		var route: Dictionary = fleet.get("route", {})
		var ids: Array = route.get("system_ids", [])
		var origin: String = str(fleet.get("origin_system_id", ids.front() if not ids.is_empty() else ""))
		var target: String = str(fleet.get("target_system_id", ids.back() if not ids.is_empty() else ""))
		var mode: String = "tunnel" if str(route.get("travel_mode", "")) == "tunnel" else ("intergalactic" if bool(route.get("intergalactic", false)) else "normal")
		var segments: Array[Dictionary] = []
		if mode == "normal":
			for edge: Dictionary in route.get("segments", []):
				if not str(edge.get("from_system_id", "")).is_empty() and not str(edge.get("to_system_id", "")).is_empty() and float(edge.get("distance", 0)) > 0:
					segments.append(edge.duplicate(true))
		if segments.is_empty():
			segments.append({"from_system_id": origin, "to_system_id": target, "kind": ("local" if origin == target else "legacy") if mode == "normal" else mode, "distance": 1.0})
		var returning: bool = str(fleet.get("status", "")) == "returning"
		if returning:
			segments.reverse()
			for edge: Dictionary in segments:
				var start: Variant = edge["from_system_id"]
				edge["from_system_id"] = edge["to_system_id"]
				edge["to_system_id"] = start
		if returning and fleet.has("map_return_fraction") and float(fleet["map_return_fraction"]) < 1.0:
			var full_distance: float = 0.0
			for edge: Dictionary in segments:
				full_distance += float(edge["distance"])
			var skipped: float = full_distance * (1.0 - clampf(float(fleet["map_return_fraction"]), 0, 1))
			while not segments.is_empty() and skipped >= float(segments[0]["distance"]) - 0.0000000001:
				skipped -= float(segments.pop_front()["distance"])
			if not segments.is_empty():
				segments[0]["from_fraction"] = skipped / float(segments[0]["distance"])
				segments[0]["distance"] = float(segments[0]["distance"]) - skipped
			else:
				segments.append({"from_system_id": origin, "to_system_id": origin, "kind": "stationary", "distance": 1.0})
		var total: float = 0.0
		for edge: Dictionary in segments:
			total += float(edge["distance"])
		return {"segments": segments, "total": total, "returning": returning, "mode": mode,
			"from_galaxy": str(fleet.get("target_galaxy_id" if returning else "origin_galaxy_id", route.get("target_galaxy_id" if returning else "origin_galaxy_id", ""))),
			"to_galaxy": str(fleet.get("origin_galaxy_id" if returning else "target_galaxy_id", route.get("origin_galaxy_id" if returning else "target_galaxy_id", "")))}

	static func progress(fleet: Dictionary, now: float) -> float:
		if str(fleet.get("status", "")) in ["holding","exploring"]:
			return 1.0
		var end: float = float(fleet.get("arrives_at", 0))
		var start: float = float(fleet.get("started_at", end - float(fleet.get("seconds", 0))))
		if end <= 0 or not is_finite(now):
			return 0.0
		if end <= start:
			return 1.0 if now >= end else 0.0
		return clampf((now - start) / (end - start), 0.0, 1.0)

	static func sample(fleet: Dictionary, now: float, route_plan: Dictionary = {}) -> Dictionary:
		var value: Dictionary = plan(fleet) if route_plan.is_empty() else route_plan
		var fraction: float = progress(fleet, now)
		var remaining: float = fraction * float(value["total"])
		var segments: Array = value["segments"]
		for index: int in range(segments.size()):
			var distance: float = float(segments[index]["distance"])
			if remaining < distance or index == segments.size() - 1:
				return {"progress": fraction, "index": index, "fraction": clampf(remaining / distance, 0, 1)}
			remaining -= distance
		return {"progress": fraction, "index": 0, "fraction": 0.0}


class FleetOverlay:
	extends Control
	var map: Control
	var records: Array[Dictionary] = []
	var stamp: float = 0.0
	var ticks: int = 0
	var accumulator: float = 0.0
	var _built_revision: int = -1
	var _built_map_size: Vector2 = Vector2(-1,-1)

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		clip_contents = true
		visibility_changed.connect(_update_processing)
		_update_processing()

	func marker_color(fleet: Dictionary) -> Color:
		return map.fleet_color(fleet)

	func set_fleets(fleets: Array, server_now: float) -> void:
		stamp = server_now
		ticks = Time.get_ticks_msec()
		records.clear()
		_built_revision = -1
		for fleet: Dictionary in fleets:
			var plan_value: Dictionary = FleetMotion.plan(fleet)
			var visible: bool = false
			for edge: Dictionary in plan_value["segments"]:
				if map._normalized_positions.has(str(edge["from_system_id"])) or map._normalized_positions.has(str(edge["to_system_id"])):
					visible = true
			if visible:
				records.append({"fleet": fleet.duplicate(true), "plan": plan_value, "paths": []})
		rebuild()
		_update_processing()

	func rebuild() -> void:
		if map == null:
			return
		var area: Rect2 = map._visible_rect()
		position = area.position
		size = area.size
		# Paid route geometry changes with geography or panel size, never with
		# each drag sample. Pan/zoom only transforms its cached map-space points.
		if _built_revision == map._projection_revision and _built_map_size == map.size:
			_transform_paths()
			return
		var galaxy: String = str(map.systems[0].get("galaxy_id", "")) if not map.systems.is_empty() else ""
		for record: Dictionary in records:
			var paths: Array[PackedVector2Array] = []
			var plan_value: Dictionary = record["plan"]
			record["cross"] = ""
			if str(plan_value["mode"]) != "normal" and str(plan_value["from_galaxy"]) != str(plan_value["to_galaxy"]):
				var departing: bool = galaxy == str(plan_value["from_galaxy"])
				var edge: Dictionary = plan_value["segments"][0]
				var id: String = str(edge["from_system_id"] if departing else edge["to_system_id"])
				if map._normalized_positions.has(id):
					var point: Vector2 = map._map_to_screen(map._normalized_positions[id])
					var portal_world: Vector2 = map._plot_rect().position + map._plot_rect().size * Vector2(0.94 if departing else 0.06, 0.18) - map._plot_rect().get_center()
					var portal: Vector2 = map._map_to_screen(portal_world)
					paths.append(PackedVector2Array([point, portal] if departing else [portal, point]))
					record["cross"] = "depart" if departing else "arrive"
			else:
				for edge: Dictionary in plan_value["segments"]:
					var from_id: String = str(edge["from_system_id"])
					var to_id: String = str(edge["to_system_id"])
					if not map._normalized_positions.has(from_id) or not map._normalized_positions.has(to_id):
						paths.append(PackedVector2Array())
						continue
					var path: PackedVector2Array
					if str(edge.get("kind", "")) == "orbit":
						path = map._route_segment_points(from_id, to_id)
					elif str(edge.get("kind", "")) == "local":
						var center: Vector2 = map._map_to_screen(map._normalized_positions[from_id])
						path = PackedVector2Array()
						for index: int in range(37):
							var angle: float = float(index) / 36.0 * TAU
							path.append(center + Vector2(sin(angle) * 12.0, (1 - cos(angle)) * 7.0) * map._zoom)
					else:
						path = PackedVector2Array([map._map_to_screen(map._normalized_positions[from_id]), map._map_to_screen(map._normalized_positions[to_id])])
					if edge.has("from_fraction"):
						var trimmed: PackedVector2Array = PackedVector2Array()
						var fraction: float = float(edge["from_fraction"])
						for index: int in range(37):
							trimmed.append(_path_sample(path, lerpf(fraction, 1.0, float(index) / 36.0))["point"])
						path = trimmed
					paths.append(path)
			for path_index: int in range(paths.size()):
				var path: PackedVector2Array = paths[path_index]
				for index: int in range(path.size()):
					path[index] = (path[index] - map._map_to_screen(Vector2.ZERO)) / map._zoom
				paths[path_index] = path
			record["world_paths"] = paths
		_built_revision = map._projection_revision
		_built_map_size = map.size
		_transform_paths()

	func _transform_paths() -> void:
		var origin: Vector2 = map._map_to_screen(Vector2.ZERO) - position
		var zoom: float = map._zoom
		for record: Dictionary in records:
			var paths: Array[PackedVector2Array] = []
			for world_path: PackedVector2Array in record.get("world_paths", []):
				var path: PackedVector2Array = PackedVector2Array()
				path.resize(world_path.size())
				for index: int in range(path.size()):
					path[index] = origin + world_path[index] * zoom
				paths.append(path)
			record["paths"] = paths
		queue_redraw()

	func _update_processing() -> void:
		set_process(is_visible_in_tree() and not records.is_empty())

	func _process(delta: float) -> void:
		accumulator += delta
		if accumulator >= 1.0 / 30.0:
			accumulator = fmod(accumulator, 1.0 / 30.0)
			queue_redraw()

	func _path_sample(path: PackedVector2Array, fraction: float) -> Dictionary:
		if path.size() < 2:
			return {}
		# Orbit samples are spaced by angle, matching the paid orbital distance.
		var position_value: float = clampf(fraction, 0, 1) * float(path.size() - 1)
		var index: int = mini(floori(position_value), path.size() - 2)
		return {"point": path[index].lerp(path[index + 1], position_value - float(index)), "direction": (path[index + 1] - path[index]).normalized()}

	func _draw() -> void:
		var now: float = stamp + float(Time.get_ticks_msec() - ticks) / 1000.0
		for record: Dictionary in records:
			var fleet: Dictionary = record["fleet"]
			var plan_value: Dictionary = record["plan"]
			var paths: Array = record["paths"]
			var color: Color = marker_color(fleet)
			var jump: bool = str(plan_value["mode"]) != "normal"
			for path: PackedVector2Array in paths:
				if path.size() > 1:
					if jump or str(plan_value["segments"][0].get("kind", "")) == "legacy":
						draw_dashed_line(path[0], path[-1], Color(color, 0.45), 1.5, 7.0, true)
					else:
						draw_polyline(path, Color(color, 0.4), 1.5, true)
			var sample_value: Dictionary = FleetMotion.sample(fleet, now, plan_value)
			var index: int = int(sample_value["index"])
			var fraction: float = float(sample_value["fraction"])
			var cross: String = str(record["cross"])
			if not cross.is_empty():
				var progress_value: float = float(sample_value["progress"])
				if (cross == "depart" and progress_value > 0.5) or (cross == "arrive" and progress_value < 0.5):
					continue
				index = 0
				fraction = progress_value * 2 if cross == "depart" else (progress_value - 0.5) * 2
			if index >= paths.size():
				continue
			var plotted: Dictionary = _path_sample(paths[index], fraction)
			if plotted.is_empty():
				continue
			var point: Vector2 = plotted["point"]
			var direction: Vector2 = plotted["direction"]
			var normal: Vector2 = direction.orthogonal()
			draw_circle(point, 12.0, Color("03080e"))
			var ship: PackedVector2Array = PackedVector2Array([point + direction * 9, point - direction * 6 + normal * 5, point - direction * 3, point - direction * 6 - normal * 5])
			var marker: Color = marker_color(fleet)
			draw_colored_polygon(ship, marker)
			draw_arc(point, 11.0, 0, TAU, 24, Color(marker, 0.65), 1.0, true)
			if jump:
				draw_string(ThemeDB.fallback_font, point + Vector2(16, -12), I18n.t("Tunel" if str(plan_value["mode"]) == "tunnel" else "Lot międzygalaktyczny"), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, color)
