extends RefCounted
## Original vector mini illustrations for the passive wheel.
## Coordinates are normalized; the helper never changes CanvasItem transforms.


class IconPreview extends Control:
	var painter: Callable
	var icon: String = "":
		set(value):
			icon = value
			queue_redraw()
	var tint: Color = Color("79c8ff"):
		set(value):
			tint = value
			queue_redraw()

	func _draw() -> void:
		if painter.is_valid():
			painter.call(self, icon, Rect2(Vector2.ZERO, size), tint)


class Brush extends RefCounted:
	var canvas: CanvasItem
	var center: Vector2
	var unit: float
	var ink: Color
	var light: Color
	var shade: Color
	var width: float

	func _init(target: CanvasItem, rect: Rect2, color: Color) -> void:
		canvas = target
		center = rect.get_center()
		unit = maxf(0.0, minf(rect.size.x, rect.size.y)) * 0.42
		ink = color
		# A dimmed/transparent locked-node tint must dim every highlight as well.
		var peak := maxf(color.r, maxf(color.g, color.b))
		light = color.lerp(Color(peak, peak, peak, color.a), 0.67)
		shade = Color(color.r * 0.38, color.g * 0.38, color.b * 0.38, color.a)
		width = maxf(0.65, unit * 0.068)

	func at(x: float, y: float) -> Vector2:
		return center + Vector2(x, y) * unit

	func line(x1: float, y1: float, x2: float, y2: float, color: Color = Color.TRANSPARENT, weight: float = 1.0) -> void:
		canvas.draw_line(at(x1, y1), at(x2, y2), ink if color == Color.TRANSPARENT else color, width * weight, true)

	func path(points: Array, color: Color = Color.TRANSPARENT, weight: float = 1.0, close: bool = false) -> void:
		var vertices := PackedVector2Array()
		for point: Vector2 in points:
			vertices.append(center + point * unit)
		if close and not vertices.is_empty():
			vertices.append(vertices[0])
		if vertices.size() > 1:
			canvas.draw_polyline(vertices, ink if color == Color.TRANSPARENT else color, width * weight, true)

	func polygon(points: Array, color: Color = Color.TRANSPARENT) -> void:
		var vertices := PackedVector2Array()
		for point: Vector2 in points:
			vertices.append(center + point * unit)
		if vertices.size() >= 3:
			canvas.draw_colored_polygon(vertices, ink if color == Color.TRANSPARENT else color)

	func circle(x: float, y: float, radius: float, color: Color = Color.TRANSPARENT, filled: bool = true, weight: float = 1.0) -> void:
		canvas.draw_circle(at(x, y), radius * unit, ink if color == Color.TRANSPARENT else color, filled, -1.0 if filled else width * weight, true)

	func arc(x: float, y: float, radius: float, start: float, finish: float, color: Color = Color.TRANSPARENT, weight: float = 1.0) -> void:
		canvas.draw_arc(at(x, y), radius * unit, start, finish, 28, ink if color == Color.TRANSPARENT else color, width * weight, true)

	func ellipse(x: float, y: float, rx: float, ry: float, angle: float = 0.0, color: Color = Color.TRANSPARENT, filled: bool = false) -> void:
		var points: Array = []
		for index in range(32):
			var theta := TAU * float(index) / 32.0
			points.append(Vector2(x, y) + Vector2(cos(theta) * rx, sin(theta) * ry).rotated(angle))
		if filled:
			polygon(points, color)
		else:
			path(points, color, 1.0, true)

	func diamond(x: float, y: float, rx: float, ry: float, color: Color = Color.TRANSPARENT, filled: bool = false) -> void:
		var points := [Vector2(x, y - ry), Vector2(x + rx, y), Vector2(x, y + ry), Vector2(x - rx, y)]
		if filled:
			polygon(points, color)
		else:
			path(points, color, 1.0, true)

	func rays(x: float, y: float, inside: float, outside: float, count: int, rotation: float = 0.0, color: Color = Color.TRANSPARENT) -> void:
		for index in range(count):
			var angle := rotation + TAU * float(index) / float(count)
			line(x + cos(angle) * inside, y + sin(angle) * inside, x + cos(angle) * outside, y + sin(angle) * outside, color)

	func spark(x: float, y: float, radius: float, color: Color = Color.TRANSPARENT) -> void:
		polygon([Vector2(x, y - radius), Vector2(x + radius * 0.24, y - radius * 0.24), Vector2(x + radius, y), Vector2(x + radius * 0.24, y + radius * 0.24), Vector2(x, y + radius), Vector2(x - radius * 0.24, y + radius * 0.24), Vector2(x - radius, y), Vector2(x - radius * 0.24, y - radius * 0.24)], color)

	func arrow(x1: float, y1: float, x2: float, y2: float, color: Color = Color.TRANSPARENT) -> void:
		line(x1, y1, x2, y2, color)
		var direction := Vector2(x2 - x1, y2 - y1).normalized()
		var tip := Vector2(x2, y2)
		var left := tip - direction * 0.23 + direction.orthogonal() * 0.16
		var right := tip - direction * 0.23 - direction.orthogonal() * 0.16
		path([left, tip, right], color)


static func make_preview(icon: String, tint: Color, min_side: float = 96.0) -> Control:
	var preview := IconPreview.new()
	preview.painter = draw_icon
	preview.icon = icon
	preview.tint = tint
	preview.custom_minimum_size = Vector2(min_side, min_side)
	preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return preview


static func draw_icon(canvas: CanvasItem, icon: String, rect: Rect2, tint: Color) -> void:
	if rect.size.x <= 0.0 or rect.size.y <= 0.0:
		return
	var b := Brush.new(canvas, rect, tint)
	_draw_motif(b, icon)


static func _draw_motif(b: Brush, icon: String) -> void:
	match icon:
		"zetans_signature":
			# A large alien eye suspended inside three psionic orbits.
			b.ellipse(0, 0, 0.90, 0.38, -0.30, b.shade)
			b.ellipse(0, 0, 0.90, 0.38, 0.30, b.shade)
			b.path([Vector2(-0.85, 0), Vector2(-0.46, -0.40), Vector2(0, -0.52), Vector2(0.46, -0.40), Vector2(0.85, 0), Vector2(0.46, 0.40), Vector2(0, 0.52), Vector2(-0.46, 0.40)], b.ink, 1.45, true)
			b.circle(0, 0, 0.31, b.ink)
			b.circle(0, 0, 0.19, b.shade)
			b.circle(0.06, -0.07, 0.09, b.light)
			b.spark(0, -0.80, 0.14, b.light)
			b.circle(-0.84, 0.26, 0.06, b.light)
			b.circle(0.84, -0.26, 0.06, b.light)
		"automatons_signature":
			# Armored mechanical core with eight heavy teeth and a bright power slit.
			b.rays(0, 0, 0.68, 0.91, 8, PI / 8, b.ink)
			b.path([Vector2(-0.34, -0.69), Vector2(0.34, -0.69), Vector2(0.69, -0.34), Vector2(0.69, 0.34), Vector2(0.34, 0.69), Vector2(-0.34, 0.69), Vector2(-0.69, 0.34), Vector2(-0.69, -0.34)], b.ink, 1.65, true)
			b.diamond(0, 0, 0.46, 0.52, b.shade, true)
			b.diamond(0, 0, 0.46, 0.52, b.light)
			b.line(-0.17, -0.23, 0.17, 0.23, b.light, 2.4)
			b.line(-0.36, 0.45, 0.36, 0.45, b.ink)
		"symbionts_signature":
			# An asymmetrical living heart; luminous vessels run into a root system.
			b.polygon([Vector2(-0.61, -0.51), Vector2(-0.31, -0.68), Vector2(0, -0.36), Vector2(0.34, -0.65), Vector2(0.68, -0.38), Vector2(0.63, 0.13), Vector2(0.18, 0.66), Vector2(-0.22, 0.51), Vector2(-0.59, 0.10)], b.shade)
			b.path([Vector2(-0.61, -0.51), Vector2(-0.31, -0.68), Vector2(0, -0.36), Vector2(0.34, -0.65), Vector2(0.68, -0.38), Vector2(0.63, 0.13), Vector2(0.18, 0.66), Vector2(-0.22, 0.51), Vector2(-0.59, 0.10)], b.ink, 1.45, true)
			b.path([Vector2(0.08, -0.27), Vector2(-0.06, 0.02), Vector2(0.17, 0.42)], b.light, 1.3)
			b.path([Vector2(-0.06, 0.02), Vector2(-0.35, -0.05), Vector2(-0.46, -0.30)], b.light)
			b.path([Vector2(-0.03, 0.09), Vector2(0.32, -0.07), Vector2(0.41, -0.33)], b.light)
			b.path([Vector2(-0.20, 0.48), Vector2(-0.48, 0.70), Vector2(-0.55, 0.86)], b.ink)
			b.path([Vector2(0.34, 0.51), Vector2(0.53, 0.71), Vector2(0.46, 0.90)], b.ink)
			b.arc(0, 0.03, 0.84, 3.58, 5.02, b.shade)
		"crystal_memory":
			b.diamond(0, -0.12, 0.42, 0.72, b.shade, true)
			b.diamond(0, -0.12, 0.42, 0.72, b.light)
			b.path([Vector2(0, -0.83), Vector2(0.12, -0.08), Vector2(0, 0.59)], b.ink)
			b.line(-0.39, -0.12, 0.42, -0.12, b.ink)
			b.arc(0, 0.2, 0.67, 0.15, 2.99, b.ink)
			b.circle(-0.66, 0.29, 0.08, b.light)
			b.circle(0.66, 0.29, 0.08, b.light)
		"thought_lattice":
			for point: Vector2 in [Vector2(-0.61, -0.42), Vector2(0.07, -0.71), Vector2(0.63, -0.17), Vector2(0.37, 0.62), Vector2(-0.48, 0.51)]:
				b.line(0, 0, point.x, point.y, b.ink)
				b.circle(point.x, point.y, 0.12, b.light)
			b.path([Vector2(-0.61, -0.42), Vector2(0.07, -0.71), Vector2(0.63, -0.17), Vector2(0.37, 0.62), Vector2(-0.48, 0.51)], b.shade, 1.1, true)
			b.circle(0, 0, 0.22, b.ink, false)
			b.circle(0, 0, 0.08, b.light)
		"silver_resonance":
			b.diamond(0, 0, 0.26, 0.64, b.light, true)
			b.arc(0, 0, 0.47, -1.03, 1.03, b.ink)
			b.arc(0, 0, 0.47, PI - 1.03, PI + 1.03, b.ink)
			b.arc(0, 0, 0.74, -0.87, 0.87, b.light)
			b.arc(0, 0, 0.74, PI - 0.87, PI + 0.87, b.light)
			b.circle(0, -0.84, 0.06, b.ink)
			b.circle(0, 0.84, 0.06, b.ink)
		"omniscient_eye":
			b.polygon([Vector2(0, -0.82), Vector2(0.82, 0.61), Vector2(-0.82, 0.61)], b.shade)
			b.path([Vector2(0, -0.82), Vector2(0.82, 0.61), Vector2(-0.82, 0.61)], b.ink, 1.15, true)
			b.ellipse(0, 0.14, 0.49, 0.25, 0, b.light)
			b.circle(0, 0.14, 0.14, b.light)
			b.line(0, -0.52, 0, -0.30, b.ink)
			b.line(-0.55, 0.76, 0.55, 0.76, b.ink)
		"space_curvature":
			b.circle(0.21, -0.12, 0.24, b.light)
			b.ellipse(0, 0.04, 0.83, 0.29, -0.40, b.ink)
			b.arc(0.21, -0.12, 0.54, -1.6, 0.65, b.shade)
			b.path([Vector2(-0.76, -0.57), Vector2(-0.41, -0.38), Vector2(-0.36, 0.05), Vector2(-0.57, 0.63)], b.light)
			b.circle(0.76, -0.30, 0.07, b.light)
		"silent_impulse":
			b.path([Vector2(-0.34, 0.68), Vector2(-0.34, -0.35), Vector2(0, -0.70), Vector2(0.34, -0.35), Vector2(0.34, 0.68)], b.ink, 1.3)
			b.line(0, -0.31, 0, 0.37, b.light, 1.5)
			b.arrow(-0.74, 0.32, -0.58, -0.14, b.shade)
			b.arrow(0.74, 0.32, 0.58, -0.14, b.shade)
			b.circle(0, 0.73, 0.075, b.light)
		"dimension_pocket":
			b.path([Vector2(-0.68, -0.34), Vector2(0, -0.76), Vector2(0.68, -0.34), Vector2(0.68, 0.40), Vector2(0, 0.80), Vector2(-0.68, 0.40)], b.ink, 1.2, true)
			b.path([Vector2(-0.68, -0.34), Vector2(0, 0.05), Vector2(0.68, -0.34)], b.ink)
			b.line(0, 0.05, 0, 0.80, b.ink)
			b.ellipse(0, -0.29, 0.30, 0.15, 0, b.light)
			b.circle(0, -0.29, 0.055, b.light)
		"gravity_gate":
			b.ellipse(0, 0, 0.53, 0.78, 0, b.ink)
			b.ellipse(0, 0, 0.35, 0.61, 0, b.light)
			b.arrow(-0.90, 0.04, 0.41, 0.04, b.light)
			b.line(-0.67, 0.37, -0.38, 0.37, b.shade)
			b.line(-0.72, -0.30, -0.35, -0.30, b.shade)
			b.spark(0.61, -0.60, 0.19, b.light)
		"phase_blade":
			b.polygon([Vector2(-0.37, 0.51), Vector2(0.15, -0.59), Vector2(0.73, -0.83), Vector2(0.40, -0.20)], b.shade)
			b.path([Vector2(-0.37, 0.51), Vector2(0.15, -0.59), Vector2(0.73, -0.83), Vector2(0.40, -0.20)], b.light, 1.1, true)
			b.line(-0.30, 0.45, 0.63, -0.71, b.ink)
			b.line(-0.58, 0.27, -0.06, 0.67, b.ink, 1.7)
			b.line(-0.48, 0.55, -0.69, 0.80, b.light, 1.8)
			b.line(-0.63, -0.15, -0.31, -0.55, b.shade)
		"weakness_scan":
			b.arc(0, 0, 0.64, -1.36, -0.23, b.ink)
			b.arc(0, 0, 0.64, 0.23, 1.36, b.ink)
			b.arc(0, 0, 0.64, PI - 1.36, PI - 0.23, b.ink)
			b.arc(0, 0, 0.64, PI + 0.23, PI + 1.36, b.ink)
			b.line(-0.89, 0, -0.33, 0, b.light)
			b.line(0.33, 0, 0.89, 0, b.light)
			b.line(0, -0.89, 0, -0.33, b.light)
			b.line(0, 0.33, 0, 0.89, b.light)
			b.path([Vector2(-0.20, -0.24), Vector2(0.03, -0.05), Vector2(-0.06, 0.12), Vector2(0.20, 0.25)], b.light, 1.5)
		"blue_singularity":
			b.circle(0, 0, 0.29, b.shade)
			b.arc(0, 0, 0.34, 0.35, 5.37, b.light, 1.5)
			b.arc(0.07, 0.03, 0.59, 1.13, 5.85, b.ink)
			b.ellipse(0, 0, 0.88, 0.24, -0.43, b.ink)
			b.circle(-0.72, 0.31, 0.085, b.light)
			b.spark(0.50, -0.66, 0.14, b.light)
		"swarm_prism":
			b.polygon([Vector2(0, -0.82), Vector2(0.56, 0.40), Vector2(-0.56, 0.40)], b.shade)
			b.path([Vector2(0, -0.82), Vector2(0.56, 0.40), Vector2(-0.56, 0.40)], b.light, 1.2, true)
			b.line(-0.88, -0.10, -0.13, 0.04, b.ink)
			b.line(0.20, 0.04, 0.83, -0.31, b.light)
			b.line(0.29, 0.18, 0.88, 0.18, b.ink)
			b.line(0.40, 0.34, 0.81, 0.63, b.ink)
			b.circle(-0.31, 0.71, 0.06, b.light)
			b.circle(0, 0.71, 0.09, b.ink)
			b.circle(0.31, 0.71, 0.06, b.light)
		"titanium_drill":
			b.path([Vector2(-0.26, -0.79), Vector2(0.30, -0.79), Vector2(0.43, -0.34), Vector2(0.19, 0.31), Vector2(0, 0.78), Vector2(-0.26, 0.31), Vector2(-0.43, -0.34)], b.ink, 1.2, true)
			b.line(-0.37, -0.37, 0.34, -0.57, b.light, 1.4)
			b.line(-0.32, -0.07, 0.37, -0.27, b.light, 1.4)
			b.line(-0.23, 0.23, 0.25, 0.08, b.light, 1.4)
			b.path([Vector2(-0.82, 0.73), Vector2(-0.57, 0.56), Vector2(-0.38, 0.78)], b.shade)
			b.path([Vector2(0.40, 0.78), Vector2(0.62, 0.54), Vector2(0.84, 0.70)], b.shade)
		"assembly_line":
			b.path([Vector2(-0.76, 0.28), Vector2(0.76, 0.28), Vector2(0.76, 0.64), Vector2(-0.76, 0.64)], b.ink, 1.2, true)
			for x: float in [-0.50, 0.0, 0.50]:
				b.circle(x, 0.46, 0.085, b.light)
			b.path([Vector2(-0.16, 0.14), Vector2(-0.16, -0.20), Vector2(0.18, -0.20), Vector2(0.18, 0.14)], b.light, 1.2, true)
			b.path([Vector2(-0.67, -0.76), Vector2(-0.67, -0.40), Vector2(-0.26, -0.40), Vector2(0, -0.56), Vector2(0.33, -0.40)], b.ink, 1.4)
			b.line(0.33, -0.40, 0.33, -0.17, b.ink)
			b.circle(-0.26, -0.40, 0.10, b.light)
		"plasma_furnace":
			b.path([Vector2(-0.60, 0.70), Vector2(-0.60, -0.49), Vector2(-0.27, -0.72), Vector2(0.27, -0.72), Vector2(0.60, -0.49), Vector2(0.60, 0.70)], b.ink, 1.3, true)
			b.polygon([Vector2(-0.25, 0.32), Vector2(-0.33, 0.04), Vector2(-0.09, -0.39), Vector2(0.03, -0.10), Vector2(0.20, -0.29), Vector2(0.34, 0.08), Vector2(0.18, 0.34)], b.light)
			b.line(-0.40, 0.51, 0.40, 0.51, b.ink, 1.4)
			b.line(-0.78, -0.17, -0.60, -0.17, b.light)
			b.line(0.60, -0.17, 0.78, -0.17, b.light)
		"endless_factory":
			b.path([Vector2(-0.79, 0.69), Vector2(-0.79, -0.06), Vector2(-0.33, -0.35), Vector2(-0.33, -0.05), Vector2(0.17, -0.35), Vector2(0.17, -0.05), Vector2(0.77, -0.05), Vector2(0.77, 0.69)], b.ink, 1.3, true)
			b.path([Vector2(0.43, -0.05), Vector2(0.43, -0.73), Vector2(0.69, -0.73), Vector2(0.69, -0.05)], b.light)
			b.line(-0.52, 0.20, -0.52, 0.42, b.light, 1.7)
			b.line(-0.11, 0.20, -0.11, 0.42, b.light, 1.7)
			b.line(0.31, 0.20, 0.31, 0.42, b.light, 1.7)
			b.arc(-0.52, -0.63, 0.17, 0.25, 5.85, b.shade)
			b.arc(-0.22, -0.63, 0.17, 3.40, 9.05, b.shade)
		"armor_ribs":
			b.polygon([Vector2(-0.66, -0.71), Vector2(0.66, -0.71), Vector2(0.56, 0.27), Vector2(0, 0.85), Vector2(-0.56, 0.27)], b.shade)
			b.path([Vector2(-0.66, -0.71), Vector2(0.66, -0.71), Vector2(0.56, 0.27), Vector2(0, 0.85), Vector2(-0.56, 0.27)], b.ink, 1.2, true)
			for y: float in [-0.38, -0.03, 0.29]:
				b.path([Vector2(-0.40, y), Vector2(0, y + 0.22), Vector2(0.40, y)], b.light, 1.3)
		"cargo_module":
			b.path([Vector2(-0.72, -0.51), Vector2(0.72, -0.51), Vector2(0.72, 0.59), Vector2(-0.72, 0.59)], b.ink, 1.35, true)
			b.line(-0.42, -0.51, -0.42, 0.59, b.light)
			b.line(0.42, -0.51, 0.42, 0.59, b.light)
			b.path([Vector2(-0.23, -0.51), Vector2(-0.23, -0.77), Vector2(0.23, -0.77), Vector2(0.23, -0.51)], b.ink)
			b.line(-0.19, -0.08, 0.19, -0.08, b.ink)
			b.line(-0.19, 0.18, 0.19, 0.18, b.ink)
			b.circle(-0.63, 0.76, 0.07, b.light)
			b.circle(0.63, 0.76, 0.07, b.light)
		"red_reactor":
			b.ellipse(0, -0.52, 0.51, 0.21, 0, b.ink)
			b.line(-0.51, -0.52, -0.51, 0.50, b.ink, 1.3)
			b.line(0.51, -0.52, 0.51, 0.50, b.ink, 1.3)
			b.arc(0, 0.22, 0.52, 0.05, PI - 0.05, b.ink)
			b.polygon([Vector2(0.05, -0.34), Vector2(-0.25, 0.07), Vector2(-0.04, 0.07), Vector2(-0.12, 0.45), Vector2(0.27, -0.02), Vector2(0.05, -0.02)], b.light)
			b.line(-0.76, -0.17, -0.51, -0.17, b.shade, 1.7)
			b.line(0.51, 0.19, 0.76, 0.19, b.shade, 1.7)
		"orbital_fortress":
			b.ellipse(0, 0.08, 0.87, 0.31, -0.26, b.shade)
			b.path([Vector2(-0.53, 0.43), Vector2(-0.53, -0.28), Vector2(-0.30, -0.28), Vector2(-0.30, -0.59), Vector2(0.30, -0.59), Vector2(0.30, -0.28), Vector2(0.53, -0.28), Vector2(0.53, 0.43)], b.ink, 1.35, true)
			b.path([Vector2(-0.17, 0.43), Vector2(-0.17, 0.04), Vector2(0.17, 0.04), Vector2(0.17, 0.43)], b.light)
			b.line(-0.38, -0.46, -0.62, -0.65, b.light, 1.3)
			b.line(0.38, -0.46, 0.62, -0.65, b.light, 1.3)
			b.circle(0.70, -0.15, 0.07, b.light)
		"magnetic_rail":
			b.path([Vector2(-0.72, 0.54), Vector2(0.39, -0.57), Vector2(0.53, -0.43), Vector2(-0.58, 0.68)], b.ink, 1.1, true)
			b.path([Vector2(-0.35, 0.80), Vector2(0.76, -0.31), Vector2(0.90, -0.17), Vector2(-0.21, 0.94)], b.ink, 1.1, true)
			b.arrow(-0.17, 0.33, 0.72, -0.58, b.light)
			b.line(-0.57, -0.10, -0.23, -0.10, b.shade)
			b.line(-0.40, -0.28, -0.40, 0.07, b.shade)
			b.spark(0.77, -0.74, 0.13, b.light)
		"hunter_algorithm":
			b.path([Vector2(-0.42, -0.63), Vector2(0.42, -0.63), Vector2(0.42, 0.42), Vector2(0.15, 0.70), Vector2(-0.42, 0.42)], b.ink, 1.2, true)
			b.path([Vector2(-0.19, -0.21), Vector2(0, -0.02), Vector2(0.19, -0.21)], b.light, 1.8)
			b.line(0, -0.02, 0, 0.35, b.light)
			for y: float in [-0.42, -0.05, 0.30]:
				b.line(-0.73, y, -0.42, y, b.shade)
				b.line(0.42, y, 0.73, y, b.shade)
			b.circle(-0.73, -0.42, 0.065, b.light)
			b.circle(0.73, 0.30, 0.065, b.light)
		"pressure_synthesis":
			b.path([Vector2(-0.64, -0.47), Vector2(-0.64, 0.58), Vector2(0.64, 0.58), Vector2(0.64, -0.47)], b.ink, 1.35)
			b.line(-0.84, -0.47, 0.84, -0.47, b.ink, 1.4)
			b.arrow(0, -0.88, 0, -0.17, b.light)
			b.arrow(-0.84, 0.07, -0.40, 0.07, b.light)
			b.arrow(0.84, 0.07, 0.40, 0.07, b.light)
			b.polygon([Vector2(0, -0.07), Vector2(0.20, 0.22), Vector2(0.10, 0.40), Vector2(-0.10, 0.40), Vector2(-0.20, 0.22)], b.light)
			b.line(-0.41, 0.77, 0.41, 0.77, b.shade)
		"annihilation_battery":
			b.path([Vector2(-0.67, 0.42), Vector2(-0.67, 0.66), Vector2(0.67, 0.66), Vector2(0.67, 0.42)], b.ink, 1.3, true)
			for x: float in [-0.44, 0, 0.44]:
				b.path([Vector2(x - 0.12, 0.42), Vector2(x - 0.12, -0.44), Vector2(x + 0.12, -0.44), Vector2(x + 0.12, 0.42)], b.ink, 1.1, true)
				b.line(x, -0.56, x, -0.88, b.light, 1.8)
			b.line(-0.83, 0.80, 0.83, 0.80, b.shade)
		"fermentation_bladder":
			b.path([Vector2(-0.20, -0.73), Vector2(-0.20, -0.41), Vector2(-0.56, -0.02), Vector2(-0.61, 0.35), Vector2(-0.37, 0.70), Vector2(0.32, 0.74), Vector2(0.59, 0.39), Vector2(0.52, -0.02), Vector2(0.18, -0.41), Vector2(0.18, -0.73)], b.ink, 1.3, true)
			b.arc(0, 0.26, 0.40, 0.1, PI - 0.1, b.shade, 1.8)
			b.circle(-0.22, 0.21, 0.10, b.light)
			b.circle(0.16, 0.39, 0.075, b.light)
			b.circle(0.14, -0.02, 0.07, b.light)
			b.line(-0.31, -0.73, 0.29, -0.73, b.light)
		"rapid_budding":
			b.path([Vector2(-0.05, 0.81), Vector2(-0.05, 0.10), Vector2(0.24, -0.40)], b.ink, 1.4)
			b.ellipse(-0.29, -0.03, 0.24, 0.39, -0.78, b.ink)
			b.ellipse(0.33, -0.53, 0.24, 0.33, 0.50, b.light)
			b.ellipse(0.30, 0.22, 0.19, 0.30, 0.79, b.ink)
			b.line(-0.08, 0.04, -0.41, -0.20, b.light)
			b.circle(-0.61, 0.47, 0.06, b.light)
			b.circle(-0.72, 0.16, 0.085, b.shade)
			b.spark(0.68, -0.21, 0.16, b.light)
		"golden_lymph":
			b.path([Vector2(-0.13, -0.87), Vector2(-0.40, -0.42), Vector2(-0.68, 0.12), Vector2(-0.62, 0.51), Vector2(-0.34, 0.72), Vector2(0.06, 0.74), Vector2(0.40, 0.49), Vector2(0.43, 0.08), Vector2(0.15, -0.42)], b.ink, 1.2, true)
			b.path([Vector2(-0.16, -0.30), Vector2(-0.33, 0.10), Vector2(-0.28, 0.43)], b.light, 1.6)
			b.spark(0.52, -0.42, 0.25, b.light)
			b.spark(0.65, 0.51, 0.12, b.ink)
		"rebirth_heart":
			b.path([Vector2(0, -0.26), Vector2(-0.25, -0.53), Vector2(-0.55, -0.37), Vector2(-0.56, -0.01), Vector2(0, 0.55), Vector2(0.56, -0.01), Vector2(0.55, -0.37), Vector2(0.25, -0.53)], b.light, 1.3, true)
			b.path([Vector2(-0.33, 0.02), Vector2(-0.14, 0.02), Vector2(-0.04, -0.12), Vector2(0.10, 0.22), Vector2(0.21, 0.02), Vector2(0.35, 0.02)], b.ink, 1.2)
			b.arc(0, 0, 0.80, -0.65, 2.55, b.ink)
			b.path([Vector2(-0.81, 0.23), Vector2(-0.67, 0.47), Vector2(-0.42, 0.42)], b.ink)
			b.spark(-0.57, -0.67, 0.13, b.light)
		"ancestral_memory":
			b.path([Vector2(0, 0.75), Vector2(0, -0.15), Vector2(-0.34, -0.45), Vector2(-0.56, -0.44)], b.ink, 1.3)
			b.path([Vector2(0, 0.24), Vector2(0.42, -0.06), Vector2(0.51, -0.36)], b.ink, 1.3)
			b.line(0, -0.15, 0.05, -0.68, b.ink)
			b.circle(-0.63, -0.45, 0.18, b.ink, false)
			b.circle(0.06, -0.76, 0.13, b.light)
			b.circle(0.54, -0.50, 0.19, b.ink, false)
			b.ellipse(-0.30, 0.28, 0.15, 0.29, -0.80, b.shade, true)
			b.path([Vector2(-0.27, 0.84), Vector2(0, 0.60), Vector2(0.31, 0.84)], b.light)
		"silica_garden":
			b.diamond(-0.35, 0.02, 0.19, 0.48, b.ink)
			b.diamond(0.04, -0.14, 0.22, 0.65, b.light)
			b.diamond(0.43, 0.11, 0.17, 0.41, b.ink)
			b.arc(0.01, 0.03, 0.70, 0.39, 2.77, b.ink)
			b.ellipse(-0.57, 0.41, 0.16, 0.27, -0.87, b.shade, true)
			b.ellipse(0.57, 0.46, 0.14, 0.24, 0.84, b.shade, true)
			b.line(0, 0.52, 0, 0.88, b.light)
		"collector_tendrils":
			b.arc(-0.34, -0.12, 0.32, PI, TAU + 0.82, b.ink, 1.2)
			b.arc(0.34, -0.12, 0.32, PI - 0.82, TAU, b.ink, 1.2)
			b.path([Vector2(-0.66, -0.12), Vector2(-0.61, 0.44), Vector2(-0.19, 0.82)], b.ink, 1.2)
			b.path([Vector2(0.66, -0.12), Vector2(0.61, 0.44), Vector2(0.19, 0.82)], b.ink, 1.2)
			b.diamond(0, -0.53, 0.17, 0.31, b.light, true)
			b.circle(0, 0.24, 0.06, b.light)
			b.circle(0, 0.47, 0.085, b.light)
		"colony_mind":
			b.ellipse(0, 0.25, 0.68, 0.40, 0, b.ink)
			b.path([Vector2(-0.45, 0.24), Vector2(-0.17, 0.02), Vector2(0.13, 0.30), Vector2(0.45, 0.03)], b.light)
			b.line(-0.42, -0.04, -0.52, -0.43, b.ink)
			b.line(0, -0.13, 0, -0.67, b.ink)
			b.line(0.42, -0.04, 0.52, -0.43, b.ink)
			b.circle(-0.55, -0.53, 0.14, b.light)
			b.circle(0, -0.78, 0.12, b.light)
			b.circle(0.55, -0.53, 0.14, b.light)
			b.path([Vector2(-0.37, 0.61), Vector2(-0.50, 0.86), Vector2(-0.69, 0.83)], b.shade)
			b.path([Vector2(0.37, 0.61), Vector2(0.50, 0.86), Vector2(0.69, 0.83)], b.shade)
		"living_chitin":
			b.ellipse(0, 0.02, 0.55, 0.78, 0, b.shade, true)
			b.ellipse(0, 0.02, 0.55, 0.78, 0, b.ink)
			b.line(0, -0.69, 0, 0.75, b.light, 1.2)
			for y: float in [-0.41, -0.03, 0.35]:
				b.path([Vector2(-0.46, y), Vector2(-0.18, y + 0.12), Vector2(0, y + 0.28), Vector2(0.18, y + 0.12), Vector2(0.46, y)], b.ink)
			b.line(-0.58, -0.20, -0.79, -0.34, b.shade)
			b.line(0.58, 0.25, 0.79, 0.39, b.shade)
		"vacuum_metabolism":
			b.path([Vector2(-0.08, -0.57), Vector2(-0.38, -0.43), Vector2(-0.62, -0.02), Vector2(-0.57, 0.53), Vector2(-0.24, 0.59), Vector2(-0.10, 0.27), Vector2(-0.08, -0.57)], b.ink, 1.2)
			b.path([Vector2(0.08, -0.57), Vector2(0.38, -0.43), Vector2(0.62, -0.02), Vector2(0.57, 0.53), Vector2(0.24, 0.59), Vector2(0.10, 0.27), Vector2(0.08, -0.57)], b.ink, 1.2)
			b.line(0, -0.88, 0, -0.13, b.light, 1.3)
			b.line(0, -0.13, -0.34, 0.20, b.light)
			b.line(0, -0.13, 0.34, 0.20, b.light)
			b.spark(0.67, -0.59, 0.16, b.light)
			b.circle(-0.74, 0.73, 0.055, b.light)
		"elastic_chamber":
			b.ellipse(0, 0.10, 0.44, 0.60, 0, b.ink)
			b.ellipse(0, 0.10, 0.25, 0.40, 0, b.shade)
			b.arrow(-0.24, 0.10, -0.83, 0.10, b.light)
			b.arrow(0.24, 0.10, 0.83, 0.10, b.light)
			b.path([Vector2(-0.26, -0.39), Vector2(-0.34, -0.61), Vector2(-0.20, -0.80)], b.ink)
			b.path([Vector2(0.26, 0.60), Vector2(0.34, 0.77), Vector2(0.20, 0.90)], b.ink)
		"leviathan_wings":
			b.path([Vector2(0, -0.40), Vector2(-0.32, -0.69), Vector2(-0.89, -0.39), Vector2(-0.75, 0.50), Vector2(-0.28, 0.24), Vector2(0, 0.69), Vector2(0.28, 0.24), Vector2(0.75, 0.50), Vector2(0.89, -0.39), Vector2(0.32, -0.69)], b.ink, 1.2, true)
			b.line(0, -0.38, 0, 0.71, b.light, 1.5)
			b.path([Vector2(-0.08, -0.18), Vector2(-0.50, -0.36), Vector2(-0.74, 0.45)], b.light)
			b.path([Vector2(0.08, -0.18), Vector2(0.50, -0.36), Vector2(0.74, 0.45)], b.light)
			b.line(-0.50, -0.36, -0.28, 0.24, b.shade)
			b.line(0.50, -0.36, 0.28, 0.24, b.shade)
		"border_beacon":
			b.path([Vector2(-0.42, 0.73), Vector2(-0.19, -0.03), Vector2(0.19, -0.03), Vector2(0.42, 0.73)], b.ink, 1.2, true)
			b.circle(0, -0.30, 0.17, b.light)
			b.arc(0, -0.30, 0.40, PI + 0.32, TAU - 0.32, b.ink)
			b.arc(0, -0.30, 0.61, PI + 0.38, TAU - 0.38, b.shade)
			b.line(-0.61, 0.73, 0.61, 0.73, b.light)
		"synthetic_lens":
			b.ellipse(0.09, -0.12, 0.50, 0.60, 0.40, b.light)
			b.ellipse(0.09, -0.12, 0.27, 0.42, 0.40, b.ink)
			b.line(-0.24, 0.42, -0.55, 0.78, b.ink, 1.8)
			b.path([Vector2(-0.71, -0.31), Vector2(-0.50, -0.31), Vector2(-0.23, -0.12), Vector2(0.27, -0.12), Vector2(0.62, 0.16), Vector2(0.85, 0.16)], b.shade)
			b.spark(0.60, -0.68, 0.16, b.light)
		"pulse_relay":
			b.path([Vector2(-0.87, 0.20), Vector2(-0.50, 0.20), Vector2(-0.33, -0.27), Vector2(-0.12, 0.47), Vector2(0.08, -0.11), Vector2(0.22, 0.20), Vector2(0.87, 0.20)], b.light, 1.3)
			b.path([Vector2(-0.46, -0.54), Vector2(-0.46, -0.77), Vector2(0.46, -0.77), Vector2(0.46, -0.54)], b.ink)
			b.path([Vector2(-0.46, 0.58), Vector2(-0.46, 0.77), Vector2(0.46, 0.77), Vector2(0.46, 0.58)], b.ink)
			b.circle(-0.87, 0.20, 0.065, b.ink)
			b.circle(0.87, 0.20, 0.065, b.ink)
		"memory_alloy":
			b.path([Vector2(-0.78, 0.11), Vector2(-0.38, -0.49), Vector2(0.69, -0.29), Vector2(0.83, 0.36), Vector2(0.33, 0.61), Vector2(-0.78, 0.36)], b.ink, 1.2, true)
			b.path([Vector2(-0.78, 0.11), Vector2(0.29, 0.34), Vector2(0.69, -0.29)], b.light)
			b.line(0.29, 0.34, 0.33, 0.61, b.light)
			b.path([Vector2(-0.39, -0.04), Vector2(-0.13, -0.14), Vector2(0.02, 0.02), Vector2(0.30, -0.10)], b.light)
			b.arc(-0.17, -0.40, 0.42, 3.44, 5.87, b.shade)
		"precision_circuit":
			b.path([Vector2(-0.31, -0.31), Vector2(0.31, -0.31), Vector2(0.31, 0.31), Vector2(-0.31, 0.31)], b.ink, 1.3, true)
			b.spark(0, 0, 0.20, b.light)
			b.path([Vector2(-0.31, -0.13), Vector2(-0.64, -0.13), Vector2(-0.64, -0.65)], b.ink)
			b.path([Vector2(0.13, -0.31), Vector2(0.13, -0.66), Vector2(0.65, -0.66)], b.ink)
			b.path([Vector2(0.31, 0.13), Vector2(0.64, 0.13), Vector2(0.64, 0.65)], b.ink)
			b.path([Vector2(-0.13, 0.31), Vector2(-0.13, 0.66), Vector2(-0.65, 0.66)], b.ink)
			for point: Vector2 in [Vector2(-0.64, -0.72), Vector2(0.72, -0.66), Vector2(0.64, 0.72), Vector2(-0.72, 0.66)]:
				b.circle(point.x, point.y, 0.075, b.light)
		"transfer_dock":
			b.path([Vector2(-0.67, -0.77), Vector2(-0.67, 0.65), Vector2(0.67, 0.65), Vector2(0.67, -0.77)], b.ink, 1.4)
			b.line(-0.67, -0.17, -0.43, -0.17, b.light)
			b.line(0.43, -0.17, 0.67, -0.17, b.light)
			b.path([Vector2(0, -0.76), Vector2(0.27, -0.19), Vector2(0.14, 0.25), Vector2(-0.14, 0.25), Vector2(-0.27, -0.19)], b.light, 1.1, true)
			b.arrow(0, 0.47, 0, 0.84, b.ink)
		"cooperation_node":
			b.ellipse(-0.26, 0, 0.48, 0.29, -0.63, b.ink)
			b.ellipse(0.26, 0, 0.48, 0.29, -0.63, b.light)
			b.line(-0.56, -0.57, -0.73, -0.74, b.shade)
			b.line(0.56, 0.57, 0.73, 0.74, b.shade)
			b.circle(0, 0, 0.075, b.light)
			b.spark(0.48, -0.65, 0.18, b.ink)
		"steel_seed":
			b.ellipse(0, -0.20, 0.35, 0.57, 0.43, b.ink)
			b.path([Vector2(-0.20, 0.30), Vector2(0.02, -0.13), Vector2(0.22, -0.61)], b.light)
			b.line(-0.22, -0.26, 0.12, -0.05, b.ink)
			b.line(-0.07, -0.50, 0.28, -0.29, b.ink)
			b.path([Vector2(-0.19, 0.31), Vector2(-0.10, 0.56), Vector2(-0.38, 0.82)], b.ink)
			b.path([Vector2(-0.10, 0.56), Vector2(0.26, 0.66), Vector2(0.43, 0.87)], b.ink)
		"conductive_tissue":
			b.ellipse(0, 0, 0.69, 0.48, -0.25, b.shade, true)
			b.ellipse(0, 0, 0.69, 0.48, -0.25, b.ink)
			b.path([Vector2(-0.88, 0.24), Vector2(-0.48, 0.10), Vector2(-0.13, 0.12), Vector2(0.25, -0.19), Vector2(0.79, -0.23)], b.light, 1.2)
			b.line(-0.13, 0.12, -0.25, -0.32, b.light)
			b.line(0.25, -0.19, 0.42, 0.24, b.light)
			b.circle(-0.25, -0.32, 0.09, b.ink)
			b.circle(0.42, 0.24, 0.09, b.ink)
		"adaptive_core":
			b.path([Vector2(-0.61, -0.36), Vector2(0, -0.74), Vector2(0.61, -0.36), Vector2(0.61, 0.36), Vector2(0, 0.74), Vector2(-0.61, 0.36)], b.ink, 1.1, true)
			b.arc(0, 0, 0.42, -0.67, 2.31, b.light)
			b.path([Vector2(-0.43, 0.10), Vector2(-0.30, 0.30), Vector2(-0.07, 0.27)], b.light)
			b.ellipse(0.05, -0.03, 0.13, 0.23, 0.55, b.light, true)
			b.line(-0.78, -0.47, -0.61, -0.36, b.shade)
			b.line(0.61, 0.36, 0.78, 0.47, b.shade)
		"trail_hunter":
			b.ellipse(-0.32, 0.31, 0.19, 0.31, 0.33, b.ink, true)
			b.circle(-0.54, 0.03, 0.07, b.light)
			b.circle(-0.36, -0.07, 0.08, b.light)
			b.circle(-0.16, -0.01, 0.075, b.light)
			b.ellipse(0.35, -0.35, 0.16, 0.25, -0.22, b.ink, true)
			b.circle(0.13, -0.63, 0.06, b.light)
			b.circle(0.32, -0.71, 0.07, b.light)
			b.circle(0.50, -0.62, 0.065, b.light)
			b.arrow(0.26, 0.71, 0.71, 0.19, b.shade)
		"recovery_chamber":
			b.ellipse(0, 0, 0.40, 0.67, 0, b.ink)
			b.path([Vector2(-0.29, 0.34), Vector2(-0.09, 0.14), Vector2(0.10, 0.35), Vector2(0.27, 0.11)], b.light)
			b.arc(0, 0, 0.79, -1.05, 1.07, b.shade)
			b.arc(0, 0, 0.79, PI - 1.05, PI + 1.07, b.shade)
			b.path([Vector2(0.65, 0.44), Vector2(0.38, 0.69), Vector2(0.36, 0.38)], b.ink)
			b.path([Vector2(-0.65, -0.44), Vector2(-0.38, -0.69), Vector2(-0.36, -0.38)], b.ink)
			b.circle(0, -0.29, 0.10, b.light)
		"symbiotic_joint":
			b.path([Vector2(-0.82, -0.45), Vector2(-0.31, -0.45), Vector2(-0.07, -0.19)], b.ink, 1.7)
			b.path([Vector2(-0.82, -0.11), Vector2(-0.40, -0.11), Vector2(-0.16, 0.15)], b.ink, 1.7)
			b.circle(0.04, 0.07, 0.28, b.light, false, 1.3)
			b.path([Vector2(0.21, 0.30), Vector2(0.50, 0.57), Vector2(0.72, 0.47), Vector2(0.82, 0.61)], b.ink, 1.5)
			b.path([Vector2(0.31, 0.03), Vector2(0.55, -0.09), Vector2(0.70, 0.02), Vector2(0.84, -0.11)], b.ink)
			b.circle(0.04, 0.07, 0.075, b.ink)
		"living_capacitor":
			b.path([Vector2(-0.70, -0.09), Vector2(-0.39, -0.09), Vector2(-0.20, -0.28)], b.ink)
			b.path([Vector2(0.20, 0.26), Vector2(0.39, 0.09), Vector2(0.70, 0.09)], b.ink)
			b.arc(0.25, 0, 0.63, PI - 0.91, PI + 0.91, b.light, 1.6)
			b.arc(-0.25, 0, 0.63, -0.91, 0.91, b.light, 1.6)
			b.ellipse(-0.24, -0.62, 0.11, 0.21, -0.55, b.ink, true)
			b.ellipse(0.24, 0.62, 0.11, 0.21, -0.55, b.ink, true)
			b.spark(0, 0, 0.17, b.light)
		"star_spore":
			b.circle(0.20, -0.20, 0.39, b.shade)
			b.circle(0.20, -0.20, 0.39, b.ink, false)
			b.spark(0.20, -0.20, 0.25, b.light)
			b.path([Vector2(-0.14, 0.04), Vector2(-0.45, 0.27), Vector2(-0.76, 0.32)], b.ink)
			b.path([Vector2(0.02, 0.18), Vector2(-0.20, 0.51), Vector2(-0.57, 0.73)], b.ink)
			b.circle(-0.82, 0.35, 0.06, b.light)
			b.circle(-0.63, 0.78, 0.075, b.light)
			b.circle(0.69, -0.61, 0.055, b.light)
		"gravity_tendril":
			b.arc(0.08, -0.18, 0.38, -2.46, 2.12, b.light, 1.2)
			b.path([Vector2(-0.12, 0.14), Vector2(-0.31, 0.38), Vector2(-0.24, 0.67), Vector2(0.07, 0.83)], b.ink, 1.5)
			b.path([Vector2(-0.28, 0.46), Vector2(-0.52, 0.55), Vector2(-0.63, 0.78)], b.ink)
			b.circle(0.11, -0.20, 0.12, b.light)
			b.ellipse(0.11, -0.20, 0.71, 0.23, -0.40, b.shade)
			b.circle(0.69, -0.46, 0.075, b.ink)
		"mirror_membrane":
			b.ellipse(-0.04, 0, 0.43, 0.78, -0.19, b.ink)
			b.path([Vector2(-0.10, -0.51), Vector2(0.16, -0.28), Vector2(-0.16, 0.06), Vector2(0.12, 0.32), Vector2(-0.04, 0.53)], b.light)
			b.path([Vector2(-0.85, -0.15), Vector2(-0.45, 0.05), Vector2(-0.84, 0.34)], b.shade)
			b.arrow(0.27, 0.01, 0.83, -0.31, b.light)
			b.spark(0.61, 0.48, 0.16, b.ink)
		"crystal_echo":
			b.diamond(-0.30, 0, 0.25, 0.65, b.light)
			b.path([Vector2(-0.05, -0.53), Vector2(0.20, 0), Vector2(-0.05, 0.53)], b.ink)
			b.path([Vector2(0.24, -0.42), Vector2(0.44, 0), Vector2(0.24, 0.42)], b.ink)
			b.path([Vector2(0.53, -0.31), Vector2(0.70, 0), Vector2(0.53, 0.31)], b.shade)
			b.line(-0.30, -0.65, -0.30, 0.65, b.ink)
			b.spark(-0.56, -0.67, 0.13, b.light)
		"light_neurons":
			b.circle(0, 0, 0.20, b.light)
			b.path([Vector2(-0.17, -0.15), Vector2(-0.37, -0.48), Vector2(-0.65, -0.59)], b.ink, 1.2)
			b.line(-0.37, -0.48, -0.30, -0.82, b.ink)
			b.path([Vector2(0.17, -0.10), Vector2(0.46, -0.33), Vector2(0.78, -0.22)], b.ink, 1.2)
			b.line(0.46, -0.33, 0.58, -0.66, b.ink)
			b.path([Vector2(-0.06, 0.20), Vector2(-0.16, 0.46), Vector2(0.15, 0.77)], b.ink, 1.2)
			b.line(-0.16, 0.46, -0.56, 0.65, b.ink)
			b.spark(-0.65, -0.59, 0.14, b.light)
			b.spark(0.78, -0.22, 0.13, b.light)
			b.spark(-0.56, 0.65, 0.13, b.light)
		"resonant_bud":
			b.ellipse(-0.18, -0.07, 0.24, 0.43, -0.33, b.ink)
			b.ellipse(0.18, -0.07, 0.24, 0.43, 0.33, b.ink)
			b.diamond(0, -0.32, 0.16, 0.41, b.light, true)
			b.line(0, 0.35, 0, 0.83, b.ink, 1.3)
			b.arc(0, -0.04, 0.69, -0.70, 0.70, b.shade)
			b.arc(0, -0.04, 0.69, PI - 0.70, PI + 0.70, b.shade)
			b.ellipse(-0.22, 0.56, 0.11, 0.26, -0.80, b.shade, true)
		"consciousness_bridge":
			b.arc(0, 0.17, 0.60, PI, TAU, b.ink, 1.4)
			b.arc(0, 0.20, 0.36, PI, TAU, b.light, 1.2)
			b.line(-0.61, 0.17, -0.61, 0.67, b.ink, 1.4)
			b.line(0.61, 0.17, 0.61, 0.67, b.ink, 1.4)
			b.circle(-0.61, 0.71, 0.12, b.light)
			b.circle(0.61, 0.71, 0.12, b.light)
			b.spark(0, -0.68, 0.17, b.light)
			b.line(-0.85, -0.08, -0.73, -0.21, b.shade)
			b.line(0.73, -0.21, 0.85, -0.08, b.shade)
		_:
			b.diamond(0.0, 0.0, 0.5, 0.73)
			b.spark(0.0, 0.0, 0.2, b.light)
