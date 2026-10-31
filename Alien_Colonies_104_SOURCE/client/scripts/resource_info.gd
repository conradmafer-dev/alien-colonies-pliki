extends RefCounted
## Resource values carry stable, language-independent markers until rendering.
## Never parse translated prose or interpret server/player text as BBCode.
const KEYS: Array[String] = ["metal", "crystal", "fuel"]
const NAMES: Dictionary = {"metal": "METAL", "crystal": "KRYSZTAŁ", "fuel": "PALIWO"}
const START: String = "\uE000resource:"
const END: String = "\uE001"

static func storage_capacity(state: Dictionary, resource: String) -> float:
	return maxf(0.0, float(state.get("storage", {}).get("capacity", {}).get(resource, 0)))


static func storage_full(state: Dictionary, resource: String) -> bool:
	var capacity: float = storage_capacity(state, resource)
	if capacity <= 0:
		return false
	var full: Dictionary = state.get("storage", {}).get("full", {})
	if full.has(resource):
		return bool(full[resource])
	return float(state.get("resources", {}).get(resource, 0)) >= capacity


static func token(resource: String) -> String:
	return START + resource + END if resource in KEYS else resource


static func cost(host, values: Dictionary, exact: bool = true, include_zero: bool = false) -> String:
	var parts: PackedStringArray = PackedStringArray()
	for resource: String in KEYS:
		var value: float = float(values.get(resource, 0))
		if include_zero or value > 0:
			var number: String = host._stat_number(value) if exact else host._number(value)
			parts.append(token(resource) + "\u00A0" + number)
	return " · ".join(parts) if not parts.is_empty() else I18n.t("Bez kosztu surowców")


static func plain(text: String) -> String:
	for resource: String in KEYS:
		text = text.replace(token(resource), I18n.t(str(NAMES[resource])).capitalize())
	return text


static func label(host, text: String, font_size: int = 23, color: String = "e7eee4") -> RichTextLabel:
	var node: RichTextLabel = RichTextLabel.new()
	node.fit_content = true
	node.scroll_active = false
	node.selection_enabled = false
	node.context_menu_enabled = false
	node.bbcode_enabled = false
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	node.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	node.add_theme_font_size_override("normal_font_size", maxi(22, font_size))
	node.add_theme_color_override("default_color", host._ui_color(Color(color)))
	set_text(node, host, text)
	return node


static func set_text(node: RichTextLabel, host, text: String) -> void:
	# Fleet and report refresh paths may call this every frame. Rebuilding an
	# unchanged rich label would repeatedly invalidate container measurements.
	if node.has_meta("resource_source") and str(node.get_meta("resource_source")) == text and str(node.get_meta("resource_locale", "")) == I18n.locale:
		return
	node.clear()
	var accessible: String = plain(text)
	node.tooltip_text = accessible
	node.accessibility_name = accessible
	node.set_meta("resource_source", text)
	node.set_meta("resource_locale", I18n.locale)
	var rendered_keys: PackedStringArray = PackedStringArray()
	var offset: int = 0
	while offset < text.length():
		var start: int = text.find(START, offset)
		if start < 0:
			node.add_text(text.substr(offset))
			break
		node.add_text(text.substr(offset, start - offset))
		var end: int = text.find(END, start + START.length())
		if end < 0:
			node.add_text(text.substr(start))
			break
		var resource: String = text.substr(start + START.length(), end - start - START.length())
		if resource in KEYS:
			var texture: Texture2D = host._texture(resource)
			if texture != null:
				var pixels: int = node.get_theme_font_size("normal_font_size") + 5
				node.add_image(texture, pixels, pixels)
				rendered_keys.append(resource)
			else:
				node.add_text(I18n.t(str(NAMES[resource])).capitalize())
		else:
			node.add_text(text.substr(start, end + END.length() - start))
		offset = end + END.length()
	node.set_meta("resource_icons", rendered_keys)
