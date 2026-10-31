extends SceneTree

const RaceTheme = preload("res://client/scripts/race_theme.gd")
const MobileChoice = preload("res://client/scripts/mobile_choice.gd")
var checks: int = 0
var failures: int = 0

func _initialize() -> void:
	call_deferred("_run")

func _expect(value: bool, note: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(note)

func _same(first: Color, second: Color) -> bool:
	return first.to_html() == second.to_html()

func _contrast(first: Color, second: Color) -> float:
	var a: Color = first.srgb_to_linear()
	var b: Color = second.srgb_to_linear()
	var one: float = 0.2126 * a.r + 0.7152 * a.g + 0.0722 * a.b
	var two: float = 0.2126 * b.r + 0.7152 * b.g + 0.0722 * b.b
	return (maxf(one, two) + 0.05) / (minf(one, two) + 0.05)

func _run() -> void:
	root.size = Vector2i(720, 1000)
	var host: Control = Control.new()
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var theme: Theme = Theme.new()
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color("13251b")
	style.border_color = Color("2e4936")
	theme.set_stylebox("normal", "Button", style)
	theme.set_color("font_color", "Button", Color("e2ecdf"))
	host.theme = theme
	root.add_child(host)
	var label: Label = Label.new()
	label.add_theme_color_override("font_color", Color("91c89b"))
	host.add_child(label)
	var warning: Label = Label.new()
	warning.add_theme_color_override("font_color", Color("ff9287"))
	host.add_child(warning)
	var background: ColorRect = ColorRect.new()
	background.color = Color("08110d")
	host.add_child(background)
	var button: Button = Button.new()
	button.icon = RaceTheme.icon_texture("settings")
	host.add_child(button)
	var chrome: TextureRect = TextureRect.new()
	chrome.texture = RaceTheme.icon_texture("planet")
	host.add_child(chrome)
	var material: TextureRect = TextureRect.new()
	material.texture = RaceTheme.icon_texture("crystal")
	host.add_child(material)
	var original_material: Texture2D = material.texture
	var art: TextureRect = TextureRect.new()
	var art_pixels: Image = Image.create(2, 2, false, Image.FORMAT_RGBA8)
	art_pixels.fill(Color("91c89b"))
	art.texture = ImageTexture.create_from_image(art_pixels)
	var original_art: Texture2D = art.texture
	host.add_child(art)
	var fade: TextureRect = TextureRect.new()
	var fade_texture: GradientTexture2D = GradientTexture2D.new()
	var gradient: Gradient = Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.4, 1.0])
	gradient.colors = PackedColorArray([Color(0.03, 0.067, 0.051, 0.0), Color(0.03, 0.067, 0.051, 0.06), Color(0.03, 0.067, 0.051, 0.94)])
	fade_texture.gradient = gradient
	fade.texture = fade_texture
	fade.set_meta("race_theme_gradient", true)
	host.add_child(fade)
	var art_gradient: Gradient = gradient.duplicate() as Gradient
	var untagged: TextureRect = TextureRect.new()
	var untagged_texture: GradientTexture2D = GradientTexture2D.new()
	untagged_texture.gradient = art_gradient
	untagged.texture = untagged_texture
	host.add_child(untagged)
	var preserve: Label = Label.new()
	preserve.add_theme_color_override("font_color", Color("91c89b"))
	preserve.set_meta("race_theme_preserve", true)
	host.add_child(preserve)
	var chooser: Button = MobileChoice.new()
	chooser.position = Vector2(20, 20)
	chooser.size = Vector2(300, 80)
	chooser.add_item("Orion")
	chooser.add_item("Atlas")
	host.add_child(chooser)
	await process_frame
	for race_id: String in ["zetans", "automatons", "symbionts", "zetans"]:
		RaceTheme.set_race(race_id)
		RaceTheme.apply_tree(host)
		var palette: Dictionary = RaceTheme.palette()
		_expect(_same(label.get_theme_color("font_color"), palette["accent"]), race_id + " recolours existing override")
		_expect(_same(background.color, palette["bg"]), race_id + " recolours background")
		for point: int in range(gradient.get_point_count()):
			var expected_fade: Color = palette["bg"]
			expected_fade.a = [0.0, 0.06, 0.94][point]
			_expect(_same(gradient.get_color(point), expected_fade), race_id + " recolours tagged gradient point with original transparency")
		_expect(_same(art_gradient.get_color(1), Color(0.03, 0.067, 0.051, 0.06)), race_id + " preserves untagged art gradient")
		_expect(_same(style.bg_color, palette["panel"]), race_id + " recolours inherited styles")
		_expect(_same(warning.get_theme_color("font_color"), Color("ff9287")), race_id + " preserves danger")
		_expect(_same(preserve.get_theme_color("font_color"), Color("91c89b")), race_id + " supports opt-out for semantic subtree")
		_expect(material.texture == original_material and art.texture == original_art, race_id + " preserves resource and natural art")
		_expect(host.modulate == Color.WHITE and art.modulate == Color.WHITE, race_id + " never globally tints gameplay imagery")
		_expect(chrome.texture == RaceTheme.icon_texture("planet") and button.icon == RaceTheme.icon_texture("settings"), race_id + " updates existing navigation and menu icons")
		_expect(_contrast(palette["text"], palette["panel"]) >= 7.0, race_id + " primary text strong contrast")
		_expect(_contrast(palette["muted"], palette["panel"]) >= 4.5, race_id + " secondary text readable")
		_expect(_contrast(palette["accent"], palette["button"]) >= 4.5, race_id + " active controls readable")
		var before: Color = style.bg_color
		RaceTheme.apply_tree(host)
		_expect(_same(style.bg_color, before), race_id + " repeated application is stable")
		var later: Label = Label.new()
		later.add_theme_color_override("font_color", RaceTheme.color(Color("91c89b")))
		host.add_child(later)
		_expect(_same(later.get_theme_color("font_color"), palette["accent"]), race_id + " newly constructed controls use selected palette")
		chooser.open()
		await process_frame
		_expect(chooser.is_open(), race_id + " chooser opens")
		_expect(_same(chooser._panel.get_theme_stylebox("panel").bg_color, RaceTheme.color(Color("14291d"))), race_id + " new modal matches race")
		_expect(chooser._overlay.theme == host.theme, race_id + " modal retains inherited theme")
		chooser.close()
		await process_frame
		later.queue_free()
	for fixed: String in ["ff9287", "ffc56f", "edc77a", "321b1c", "b95451", "68b9ff", "ff6c63", "84dc86", "99d886"]:
		_expect(_same(RaceTheme.color(Color(fixed)), Color(fixed)), "Preserved semantic or faction colour " + fixed)
	RaceTheme.set_race("automatons")
	chooser.open()
	await process_frame
	RaceTheme.set_race("zetans")
	RaceTheme.apply_tree(host)
	_expect(_same(chooser._panel.get_theme_stylebox("panel").bg_color, RaceTheme.color(Color("14291d"))), "Already-open modal recolours with host")
	chooser.close()
	RaceTheme.set_race("")
	RaceTheme.apply_tree(host)
	_expect(_same(background.color, Color("08110d")) and RaceTheme.current_race() == "symbionts", "Logout resets to original green")
	for original: String in RaceTheme.BASE_COLORS:
		RaceTheme.set_race("zetans")
		var blue: Color = RaceTheme.color(Color(original))
		RaceTheme.set_race("automatons")
		var red: Color = RaceTheme.color(blue)
		RaceTheme.set_race("symbionts")
		_expect(_same(RaceTheme.color(red), Color(original)), "Lossless palette roundtrip " + original)
	print("RACIAL THEME: %d checks, %d failures" % [checks, failures])
	host.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
