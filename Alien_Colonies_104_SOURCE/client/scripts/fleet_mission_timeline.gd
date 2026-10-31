extends Control
## One authoritative flight leg. Home is always left and target always right;
## reaching a local deadline never invents a return trip or changes server state.

const RaceTheme = preload("res://client/scripts/race_theme.gd")

static func marker_color(snapshot: Dictionary) -> Color:
	# The map ship and the Active missions ship share one race-aware accent.
	return RaceTheme.color(Color("edc77a") if str(snapshot.get("art_key", "")).begins_with("swarm/") else Color("91c89b"))

var fleet: Dictionary = {}
var title: String = ""
var texture: Texture2D
var accent: Color = Color("91c89b")
var now_provider: Callable
var duration_formatter: Callable
var heading: Label
var origin_heading: Label
var target_heading: Label
var origin_caption: Label
var target_caption: Label
var countdown: Label
var progress: float = 0.0
var ship_position: float = 0.0
var returning: bool = false
var holding: bool = false
var known_duration: bool = false
var _redraw_clock: float = 0.0


func setup(snapshot: Dictionary, caption: String, art: Texture2D, tint: Color, clock: Callable, formatter: Callable) -> void:
	fleet = snapshot.duplicate(true)
	title = caption
	texture = art
	accent = tint
	now_provider = clock
	duration_formatter = formatter
	returning = str(fleet.get("status", "outbound")) == "returning"
	holding = str(fleet.get("status", "outbound")) in ["holding","exploring"]
	if is_instance_valid(heading):
		_set_captions()
		update_clock()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip_contents = true
	custom_minimum_size = Vector2(0, 176)
	heading = _caption("", 22)
	origin_heading = _caption(I18n.t("START"), 14, Color(accent, 0.85))
	target_heading = _caption(I18n.t("CEL"), 14, Color(accent, 0.85))
	origin_caption = _caption("", 20)
	target_caption = _caption("", 20)
	for label: Label in [origin_caption, target_caption]:
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.max_lines_visible = 2
	target_heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	target_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	countdown = _caption("", 19, accent)
	countdown.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	resized.connect(_layout)
	visibility_changed.connect(_visibility_changed)
	_set_captions()
	_layout()
	update_clock()
	_visibility_changed()


func _caption(value: String, font_size: int, color: Color = Color("e7eee4")) -> Label:
	var label: Label = Label.new()
	label.text = value
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.autowrap_mode = TextServer.AUTOWRAP_OFF
	label.clip_text = true
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	add_child(label)
	return label


func _set_captions() -> void:
	heading.text = title
	origin_caption.text = str(fleet.get("origin_name", I18n.t("Baza")))
	target_caption.text = str(fleet.get("target_name", I18n.t("Cel")))


func _layout() -> void:
	if not is_instance_valid(heading):
		return
	var width: float = maxf(0.0, size.x)
	var column: float = maxf(0.0, (width - 20.0) * 0.5)
	heading.position = Vector2(48, 0)
	heading.size = Vector2(maxf(0.0, width - 70), 32)
	origin_heading.position = Vector2(0, 39)
	origin_heading.size = Vector2(column, 20)
	target_heading.position = Vector2(width - column, 39)
	target_heading.size = Vector2(column, 20)
	origin_caption.position = Vector2(0, 60)
	origin_caption.size = Vector2(column, 48)
	target_caption.position = Vector2(width - column, 60)
	target_caption.size = Vector2(column, 48)
	countdown.position = Vector2(0, 144)
	countdown.size = Vector2(width, 28)
	queue_redraw()


func _visibility_changed() -> void:
	set_process(is_visible_in_tree())
	if is_visible_in_tree() and is_instance_valid(countdown):
		update_clock()


func _visible_on_screen() -> bool:
	if not is_visible_in_tree():
		return false
	var visible_rect: Rect2 = get_global_rect().intersection(get_viewport_rect())
	var ancestor: Node = get_parent()
	while ancestor is Control and visible_rect.has_area():
		if ancestor.clip_contents:
			visible_rect = visible_rect.intersection(ancestor.get_global_rect())
		ancestor = ancestor.get_parent()
	return visible_rect.has_area()


func _process(delta: float) -> void:
	# No rebuilding/reloading assets, and no drawing off-screen scroll cards.
	if not _visible_on_screen():
		return
	_redraw_clock += delta
	if _redraw_clock >= 1.0 / 30.0:
		_redraw_clock = 0.0
		update_clock()


static func _number(value: Variant, fallback: float = 0.0) -> float:
	if not (value is int or value is float or (value is String and value.is_valid_float())):
		return fallback
	var number: float = float(value)
	return number if is_finite(number) else fallback


static func timing(snapshot: Dictionary, now: float) -> Dictionary:
	var deadline: float = _number(snapshot.get("arrives_at", 0))
	var duration: float = _number(snapshot.get("seconds", 0))
	var started: float = _number(snapshot.get("started_at", 0))
	if started > 0.0 and deadline > started:
		duration = deadline - started
	var is_holding: bool = str(snapshot.get("status", "outbound")) in ["holding","exploring"]
	var is_returning: bool = str(snapshot.get("status", "outbound")) == "returning"
	if is_holding:
		deadline = _number(snapshot.get("hold_until", deadline), deadline)
	var remaining: float = maxf(0.0, deadline - _number(now)) if deadline > 0.0 else 0.0
	var has_duration: bool = duration > 0.0 and deadline > 0.0
	var fraction: float = clampf(1.0 - remaining / duration, 0.0, 1.0) if has_duration else 0.0
	if deadline > 0.0 and remaining <= 0.0:
		fraction = 1.0
	return {"progress": fraction, "position": 1.0 if is_holding else (1.0 - fraction if is_returning else fraction),
		"remaining": remaining, "known_duration": has_duration, "known_deadline": deadline > 0.0,
		"holding": is_holding, "returning": is_returning}


func update_clock() -> void:
	if not now_provider.is_valid() or not is_instance_valid(countdown):
		return
	var values: Dictionary = timing(fleet, _number(now_provider.call()))
	progress = float(values["progress"])
	ship_position = float(values["position"])
	known_duration = bool(values["known_duration"])
	var remaining: float = float(values["remaining"])
	var caption: String
	if not bool(values["known_deadline"]):
		caption = I18n.t("Stacjonuje") if holding else I18n.t("Czas przylotu niedostępny")
	elif remaining <= 0.0:
		caption = I18n.t("Rozliczanie misji…")
	else:
		var duration: String = str(duration_formatter.call(remaining)) if duration_formatter.is_valid() else "%ds" % ceili(remaining)
		if holding:
			caption = I18n.t("Poszukiwania: jeszcze %s" if fleet.get("status") == "exploring" else "Odlot za %s") % duration
		elif returning:
			caption = I18n.t("Powrót do bazy za %s") % duration
		else:
			caption = I18n.t("Dotarcie za ") + duration
	if countdown.text != caption:
		countdown.text = caption
	queue_redraw()


func _draw() -> void:
	if size.x < 48:
		return
	if texture != null:
		draw_texture_rect(texture, Rect2(0, 0, 36, 32), false)
	var font: Font = ThemeDB.fallback_font
	draw_string(font, Vector2(size.x - 16, 27), "›", HORIZONTAL_ALIGNMENT_LEFT, 16, 26, Color(accent, 0.75))
	var left: Vector2 = Vector2(14, 124)
	var right: Vector2 = Vector2(size.x - 14, 124)
	draw_line(left, right, Color(accent, 0.20), 8.0, true)
	var location: Vector2 = left.lerp(right, ship_position)
	if holding:
		draw_line(left, right, Color(accent, 0.7), 8.0, true)
	elif known_duration or progress >= 1.0:
		draw_line(right if returning else left, location, accent, 8.0, true)
	else:
		draw_dashed_line(left, right, Color(accent, 0.45), 2.0, 9.0, true)
	for endpoint: Vector2 in [left, right]:
		draw_circle(endpoint, 7, Color("101b24"))
		draw_arc(endpoint, 6, 0, TAU, 24, accent, 2.0, true)
	# A directional ship silhouette remains legible at phone size. Its heading
	# reverses on a server-confirmed return while the two labels stay fixed.
	var facing: float = -1.0 if returning else 1.0
	var hull: PackedVector2Array = PackedVector2Array()
	for vertex: Vector2 in [Vector2(13, 0), Vector2(-10, -9), Vector2(-5, 0), Vector2(-10, 9)]:
		hull.append(location + Vector2(vertex.x * facing, vertex.y))
	draw_circle(location, 15, Color("101b24"))
	draw_colored_polygon(hull, accent)
