extends Control
## Schematic origin -> destination, using the same planets as the galaxy UI.
## The arrow is not a geographic scale and never supplies a fictional distance.

var origin_name: String = ""
var target_name: String = ""
var origin_texture: Texture2D
var target_texture: Texture2D
var background_texture: Texture2D
var accent: Color = Color("7bcde5")
var origin_caption: Label
var target_caption: Label
var origin_heading: Label
var target_heading: Label

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip_contents = true
	custom_minimum_size = Vector2(0, 194)
	origin_heading = _caption(I18n.t("START"), 16)
	target_heading = _caption(I18n.t("CEL"), 16)
	origin_caption = _caption(origin_name, 21)
	target_caption = _caption(target_name, 21)
	resized.connect(_layout)
	_layout()

func _caption(value: String, font_size: int) -> Label:
	var label: Label = Label.new()
	label.text = value
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.max_lines_visible = 2
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.add_theme_font_size_override("font_size", font_size)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(label)
	return label

func set_route(start_name: String, end_name: String, start_art: Texture2D, end_art: Texture2D, background: Texture2D, tint: Color) -> void:
	origin_name = start_name
	target_name = end_name
	origin_texture = start_art
	target_texture = end_art
	background_texture = background
	accent = tint
	if is_instance_valid(origin_caption):
		origin_caption.text = origin_name
		target_caption.text = target_name
		_layout()
	queue_redraw()

func _layout() -> void:
	var column: float = maxf(80.0, size.x * 0.40)
	origin_heading.position = Vector2(8, 8)
	origin_heading.size = Vector2(column, 24)
	target_heading.position = Vector2(size.x - column - 8, 8)
	target_heading.size = Vector2(column, 24)
	origin_caption.position = Vector2(8, 137)
	origin_caption.size = Vector2(column, 53)
	target_caption.position = Vector2(size.x - column - 8, 137)
	target_caption.size = Vector2(column, 53)
	queue_redraw()

func _draw() -> void:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = Color("0a1420")
	box.border_color = Color(accent, 0.45)
	box.set_border_width_all(1)
	box.set_corner_radius_all(15)
	draw_style_box(box, Rect2(Vector2.ZERO, size))
	if background_texture != null:
		draw_texture_rect(background_texture, Rect2(Vector2.ZERO, size), false, Color(0.65, 0.72, 0.85, 0.22))
	var left: Vector2 = Vector2(size.x * 0.21, 84)
	var right: Vector2 = Vector2(size.x * 0.79, 84)
	var from: Vector2 = left + Vector2(57, 0)
	var to: Vector2 = right - Vector2(57, 0)
	if to.x > from.x:
		draw_dashed_line(from, to, Color(accent, 0.95), 3.0, 11.0, true)
		draw_polyline(PackedVector2Array([to + Vector2(-11, -8), to, to + Vector2(-11, 8)]), accent, 3.0, true)
	_draw_planet(origin_texture, left)
	_draw_planet(target_texture, right)

func _draw_planet(texture: Texture2D, center: Vector2) -> void:
	draw_circle(center, 50, Color(accent, 0.09))
	if texture != null:
		draw_texture_rect(texture, Rect2(center - Vector2(47, 47), Vector2(94, 94)), false)
	else:
		draw_circle(center, 35, Color("142638"))
		draw_arc(center, 35, 0, TAU, 48, Color(accent, 0.6), 1.5, true)
		draw_string(ThemeDB.fallback_font, center + Vector2(-10, 12), "?", HORIZONTAL_ALIGNMENT_LEFT, 40, 35, accent)
