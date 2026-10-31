extends RefCounted
## One interface palette for login and every civilization. Species artwork,
## gameplay identity colors, resource icons and warning colors stay separate.

const UI_RACE: String = "zetans"
# Idle surfaces are pure black. Keep the separate hover/pressed/selected tokens
# blue so interaction states stay visible against the shared black canvas.
const IDLE_SURFACES: Array[String] = [
	"08110d", "13251b", "142219", "0b1a12", "14291d", "0a1710",
	"152a1d", "070c0c", "050b08", "030707", "020404", "020604",
	"070d0c", "17271e", "09110d", "101e16"
]
const BASE_COLORS: Array[String] = [
	"08110d", "e7eee4", "e2ecdf", "7f9384", "8caa94", "91c89b", 
	"3b6047", "edf3e9", "1d3326", "39553f", "284633", "2c5139", 
	"142219", "293c2d", "0b1a12", "36533e", "11291b", "14291d", 
	"45654c", "0a1710", "66896d", "2b4f36", "d4ebd6", "13251b", 
	"2e4936", "a0b3a4", "a4ef77", "a8bcac", "c9d9cb", "94ab9a", 
	"93aa9a", "152a1d", "314b39", "a5d5ac", "c9d8cb", "c8ddcb", 
	"9bb0a0", "274a33", "070c0c", "050b08", "284b33", "b7e3bd", 
	"030707", "020404", "020604", "0b1514", "070d0c", "0a1510", "4d6b63", "91b5ab",
	# Additional chrome tokens used by hints, descriptions and research links.
	"17271e", "4d6848", "d9efbb", "e8efdf", "c5d4c8", "526357", "bad4c3", "d9e7dc",
	"09110d", "101e16", "34543e", "a1b4a6"
]
const CHROME_ICONS: Array[String] = [
	"planet", "galaxy", "fleet", "research", "reports", "settings", "chat", "shield", "time", 
	"metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab", 
	"scout", "cargo", "colonizer", "frigate", "cruiser", "propulsion", "weapons"
]
static var _colors: Dictionary = {}
static var _canonical: Dictionary = {}
static var _icons: Dictionary = {}
static var _override_candidates: Dictionary = {}
static var _script_property_hooks: Dictionary = {}

static func set_race(_race_id: String) -> bool:
	# Retain the existing caller API without recoloring the UI on account/race
	# changes or triggering a full theme-tree traversal on regular state polls.
	return false

static func current_race() -> String:
	return UI_RACE

static func _tint(source: Color, race_id: String) -> Color:
	if race_id == "symbionts":
		return source


	var hue: float = 0.598 if race_id == "zetans" else 0.986
	return Color.from_hsv(hue, source.s, source.v, source.a)

static func _prepare() -> void :
	if not _colors.is_empty():
		return
	# Recognize old red/green theme values as well, so apply_tree can normalize
	# existing controls to blue without touching unrelated semantic colors.
	for race_id: String in ["symbionts", "zetans", "automatons"]:
		var entries: Dictionary = {}
		for key: String in BASE_COLORS:
			var tinted: Color = _tint(Color(key), race_id)
			entries[key] = tinted
			_canonical[tinted.to_html(false)] = key
		_colors[race_id] = entries

	for key: String in BASE_COLORS:
		_canonical[key] = key
	for key: String in IDLE_SURFACES:
		_colors[UI_RACE][key] = Color.BLACK

static func color(source: Color) -> Color:
	_prepare()
	var key: String = source.to_html(false)
	if not _canonical.has(key):
		return source
	var result: Color = _colors[UI_RACE][_canonical[key]]
	result.a = source.a
	return result

static func palette(_race_id: String = "") -> Dictionary:
	_prepare()
	var tokens: Dictionary = _colors[UI_RACE]
	return {
		"bg": tokens["08110d"], "panel": tokens["13251b"], 
		"border": tokens["2e4936"], "accent": tokens["91c89b"], 
		"text": tokens["e7eee4"], "muted": tokens["a0b3a4"], 
		"button": Color.BLACK, "highlight": tokens["a4ef77"]
	}

static func _remembered_color(owner: Object, property: String, source: Color) -> Color:
	var memory: Dictionary = owner.get_meta("race_theme_colors", {})
	var record: Dictionary = memory.get(property, {})
	var original: Color = source
	if not record.is_empty() and source.is_equal_approx(record["mapped"]):
		original = record["original"]
	var mapped: Color = color(original)
	memory[property] = {"original": original, "mapped": mapped}
	owner.set_meta("race_theme_colors", memory)
	return mapped

static func _style(box: StyleBox, seen: Dictionary) -> bool:
	if not box is StyleBoxFlat:
		return false
	var styles: Dictionary = seen["styles"]
	var id: int = box.get_instance_id()
	if styles.has(id):
		return bool(styles[id]["changed"])
	var flat: StyleBoxFlat = box as StyleBoxFlat
	var record: Dictionary = {"resource": flat, "blocked": flat.is_blocking_signals(), "changed": false}
	styles[id] = record
	flat.set_block_signals(true)
	for property: String in ["bg_color", "border_color", "shadow_color"]:
		var original: Color = flat.get(property)
		var mapped: Color = _remembered_color(flat, property, original)
		if not original.is_equal_approx(mapped):
			flat.set(property, mapped)
			record["changed"] = true
	return bool(record["changed"])

static func _theme(theme: Theme, seen: Dictionary) -> void :
	var themes: Dictionary = seen["themes"]
	if theme == null or themes.has(theme.get_instance_id()):
		return



	var record: Dictionary = {"resource": theme, "blocked": theme.is_blocking_signals(), "changed": false}
	themes[theme.get_instance_id()] = record
	theme.set_block_signals(true)
	for kind: String in theme.get_type_list():
		for key: String in theme.get_color_list(kind):
			var original: Color = theme.get_color(key, kind)
			var mapped: Color = _remembered_color(theme, kind + "/" + key, original)
			if not original.is_equal_approx(mapped):
				theme.set_color(key, kind, mapped)
				record["changed"] = true
		for key: String in theme.get_stylebox_list(kind):
			if _style(theme.get_stylebox(key, kind), seen):
				record["changed"] = true

static func _publish_changes(records: Dictionary) -> void :
	for record: Dictionary in records.values():
		var resource: Resource = record["resource"]
		resource.set_block_signals(bool(record["blocked"]))
		if bool(record["changed"]) and not bool(record["blocked"]):
			resource.emit_changed()

static func apply_tree(root: Node) -> void :
	if not is_instance_valid(root):
		return
	var seen: Dictionary = {"themes": {}, "styles": {}}
	_apply(root, seen)


	_publish_changes(seen["styles"])
	_publish_changes(seen["themes"])

static func _has_script_property_hooks(control: Control) -> bool:
	var script: Script = control.get_script() as Script
	if script == null:
		return false
	if not _script_property_hooks.has(script):
		var custom: bool = false


		for method: Dictionary in script.get_script_method_list():
			if str(method["name"]) in ["_get_property_list", "_validate_property"]:
				custom = true
				break
		_script_property_hooks[script] = custom
	return bool(_script_property_hooks[script])

static func _native_override_candidates(control: Control) -> Dictionary:
	var kind: StringName = control.get_class()
	if not _override_candidates.has(kind):
		var colors: PackedStringArray = PackedStringArray()
		var styles: PackedStringArray = PackedStringArray()



		for entry: Dictionary in control.get_property_list():
			var property: String = str(entry["name"])
			if property.begins_with("theme_override_colors/"):
				colors.append(property.trim_prefix("theme_override_colors/"))
			elif property.begins_with("theme_override_styles/"):
				styles.append(property.trim_prefix("theme_override_styles/"))
		_override_candidates[kind] = {"colors": colors, "styles": styles}
	return _override_candidates[kind]

static func _apply_overrides(control: Control, seen: Dictionary) -> void :
	var colors: PackedStringArray = PackedStringArray()
	var styles: PackedStringArray = PackedStringArray()
	if _has_script_property_hooks(control):



		for entry: Dictionary in control.get_property_list():
			if (int(entry["usage"]) & PROPERTY_USAGE_STORAGE) == 0:
				continue
			var property: String = str(entry["name"])
			if property.begins_with("theme_override_colors/"):
				colors.append(property)
			elif property.begins_with("theme_override_styles/"):
				styles.append(property)
	else:
		var candidates: Dictionary = _native_override_candidates(control)
		for key: String in candidates["colors"]:
			if control.has_theme_color_override(key):
				colors.append("theme_override_colors/" + key)
		for key: String in candidates["styles"]:
			if control.has_theme_stylebox_override(key):
				styles.append("theme_override_styles/" + key)
	var bulk_overrides: bool = false
	for property: String in colors:
		var value: Variant = control.get(property)
		if value is Color:
			var mapped: Color = _remembered_color(control, property, value)
			if not value.is_equal_approx(mapped):
				if not bulk_overrides:
					control.begin_bulk_theme_override()
					bulk_overrides = true
				control.set(property, mapped)
	for property: String in styles:
		var box: StyleBox = control.get(property) as StyleBox
		if box != null:
			_style(box, seen)
	if bulk_overrides:
		control.end_bulk_theme_override()

static func _apply(node: Node, seen: Dictionary) -> void :
	if node.is_queued_for_deletion() or bool(node.get_meta("race_theme_preserve", false)):
		return
	if node is Control:
		var control: Control = node as Control
		_theme(control.theme, seen)
		_apply_overrides(control, seen)
		if control is ColorRect:
			var rect: ColorRect = control as ColorRect
			rect.color = _remembered_color(rect, "color", rect.color)
		if control is TextureRect:
			var art: TextureRect = control as TextureRect
			if art.texture != null and art.texture.has_meta("race_theme_icon"):
				art.texture = icon_texture(str(art.texture.get_meta("race_theme_icon")))
			elif bool(art.get_meta("race_theme_gradient", false)) and art.texture is GradientTexture2D:


				var gradient: Gradient = (art.texture as GradientTexture2D).gradient
				if gradient != null:
					for point: int in range(gradient.get_point_count()):
						gradient.set_color(point, _remembered_color(gradient, "point_" + str(point), gradient.get_color(point)))
		if control is Button:
			var button: Button = control as Button
			if button.icon != null and button.icon.has_meta("race_theme_icon"):
				button.icon = icon_texture(str(button.icon.get_meta("race_theme_icon")))
	for child: Node in node.get_children():
		_apply(child, seen)

static func icon_texture(key: String) -> Texture2D:
	var cache_key: String = (UI_RACE if key in CHROME_ICONS else "fixed") + "/" + key
	if _icons.has(cache_key):
		return _icons[cache_key] as Texture2D
	var path: String = "res://client/assets/ui/" + key + ".svg"
	if not ResourceLoader.exists(path):
		return null
	var source: Texture2D = load(path) as Texture2D
	if source == null:
		return null
	if key not in CHROME_ICONS:
		_icons[cache_key] = source
		return source



	var pixels: Image = source.get_image()
	if pixels.is_compressed():
		pixels.decompress()
	for y: int in range(pixels.get_height()):
		for x: int in range(pixels.get_width()):
			var source_color: Color = pixels.get_pixel(x, y)
			if source_color.a > 0.0 and source_color.h >= 0.2 and source_color.h <= 0.48:
				pixels.set_pixel(x, y, _tint(source_color, UI_RACE))
	var result: ImageTexture = ImageTexture.create_from_image(pixels)
	result.set_meta("race_theme_icon", key)
	_icons[cache_key] = result
	return result
