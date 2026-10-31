extends Control

const ArtLibrary = preload("res://client/scripts/art_library.gd")
var alien_world: bool = false
var planet_id: String = ""


func _ready() -> void:
	# Hero cards may request a smaller illustration before entering the tree.
	if custom_minimum_size == Vector2.ZERO:
		custom_minimum_size = Vector2(180, 180)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)


func _draw() -> void:
	var portrait: Texture2D = ArtLibrary.texture("swarm/planet") if alien_world and not ArtLibrary.planet_environments.has(planet_id) else ArtLibrary.planet_texture(planet_id)
	if portrait != null:
		var side: float = minf(size.x, size.y)
		draw_texture_rect(portrait, Rect2((size - Vector2.ONE * side) / 2.0, Vector2.ONE * side), false)
		return
	var center: Vector2 = size / 2.0
	var radius: float = minf(size.x, size.y) * 0.34
	if radius <= 0.0:
		return
	var tint: Color = Color("3babc3") if not alien_world else Color("b25366")
	for i: int in range(8, 0, -1):
		draw_circle(center, radius + float(i) * 2.1, Color(tint, 0.022))
	draw_circle(center, radius, Color("16394f"))
	# Deterministic latitude bands, all points stay inside the planet silhouette.
	for band: int in range(13):
		var y: float = -radius + float(band) * radius * 2.0 / 13.0
		var y_next: float = minf(y + radius * 2.0 / 13.0 + 1.0, radius)
		var poly: PackedVector2Array = _latitude_band_polygon(center, radius, y, y_next)
		var band_color: Color = tint.darkened(0.22 + 0.2 * sin(float(band) * 2.7))
		draw_colored_polygon(poly, band_color)
	# Layered translucent night side leaves a bright crescent at upper left.
	for shade: int in range(18):
		var horizontal: float = lerpf(-0.5, 0.85, float(shade) / 17.0)
		var points: PackedVector2Array = _night_side_polygon(center, radius, horizontal)
		draw_colored_polygon(points, Color(0.015, 0.035, 0.08, 0.05))
	draw_arc(center, radius, PI * 0.94, PI * 1.92, 64, Color("97eff6"), 1.8, true)
	draw_arc(center, radius + 18.0, 0.4, 2.3, 42, Color(0.33, 0.85, 0.93, 0.23), 1.0, true)
	draw_circle(center + Vector2(-radius - 12, -radius - 2), 2.5, Color("ffc56f"))


func _night_side_polygon(center: Vector2, radius: float, horizontal: float) -> PackedVector2Array:
	var points: PackedVector2Array = PackedVector2Array()
	# Exactly -PI/2..PI/2 keeps y monotone. Extending past a pole folds the
	# outer edge back through the terminator and produces self-intersections.
	points.append(center + Vector2(0.0, -radius))
	for step: int in range(1, 32):
		var angle: float = -PI / 2.0 + PI * float(step) / 32.0
		points.append(center + Vector2(cos(angle), sin(angle)) * radius)
	points.append(center + Vector2(0.0, radius))
	# The poles are shared by both edges; include them only once.
	for step: int in range(31, 0, -1):
		var angle: float = -PI / 2.0 + PI * float(step) / 32.0
		points.append(center + Vector2(cos(angle) * horizontal, sin(angle)) * radius)
	return points


func _latitude_band_polygon(center: Vector2, radius: float, y: float, y_next: float) -> PackedVector2Array:
	var points: PackedVector2Array = PackedVector2Array()
	for side: int in range(2):
		for step: int in range(12):
			var line_y: float = lerpf(y, y_next, float(step) / 11.0) if side == 0 else lerpf(y_next, y, float(step) / 11.0)
			var edge: float = sqrt(maxf(0.0, radius * radius - line_y * line_y))
			var point: Vector2 = center + Vector2(-edge if side == 0 else edge, line_y)
			if points.is_empty() or not point.is_equal_approx(points[points.size() - 1]):
				points.append(point)
	if points.size() > 1 and points[0].is_equal_approx(points[points.size() - 1]):
		points.resize(points.size() - 1)
	return points
