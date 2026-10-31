extends RefCounted
## Full artwork stays above the text scroller and construction controls below it.
## Every card fills the same viewport; text starts directly below the artwork.

static func create(host, panel: PanelContainer, card: VBoxContainer) -> Dictionary:
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.custom_minimum_size.y = 0
	card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	card.add_theme_constant_override("separation", 10)
	var scroll: ScrollContainer = host.TouchScrollScript.new()
	scroll.name = "CatalogCardContentScroll"
	# Both nested scrollers receive DOWN; the carousel locks the dominant axis
	# before either one can move. Native scrolling still owns taps and inertia.
	scroll.mouse_filter = Control.MOUSE_FILTER_PASS
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	scroll.follow_focus = true
	card.add_child(scroll)
	var content: VBoxContainer = VBoxContainer.new()
	content.name = "CatalogCardContent"
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	# Keep the ordinary spacing between fields. Any spare height remains after
	# the last text field, above the pinned resource, time and action controls.
	content.alignment = BoxContainer.ALIGNMENT_BEGIN
	content.add_theme_constant_override("separation", 10)
	scroll.add_child(content)
	var footer: VBoxContainer = VBoxContainer.new()
	footer.name = "CatalogCardFooter"
	footer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	footer.add_theme_constant_override("separation", 8)
	card.add_child(footer)
	panel.set_meta("catalog_scroller", scroll)
	panel.set_meta("catalog_content", content)
	panel.set_meta("catalog_footer", footer)
	panel.set_meta("catalog_height_limit", 600.0)
	content.minimum_size_changed.connect(_fit_height.bind(panel))
	footer.minimum_size_changed.connect(_fit_height.bind(panel))
	panel.resized.connect(_fit_height.bind(panel))
	_fit_height.call_deferred(panel)
	return {"scroll": scroll, "content": content, "footer": footer}


static func set_height_limit(panel: PanelContainer, height: float) -> void:
	var full_height: float = maxf(1.0, height)
	panel.set_meta("catalog_height_limit", full_height)
	if absf(panel.custom_minimum_size.y - full_height) > 0.5:
		panel.custom_minimum_size.y = full_height
	# Also observe textures assigned after construction: EXPAND_IGNORE_SIZE does
	# not emit a minimum-size change for every texture assignment.
	_fit_height(panel)


static func _fit_height(panel: PanelContainer) -> void:
	if not is_instance_valid(panel) or not panel.has_meta("catalog_content") or bool(panel.get_meta("catalog_fitting", false)):
		return
	var content: VBoxContainer = panel.get_meta("catalog_content")
	var scroll: ScrollContainer = panel.get_meta("catalog_scroller")
	if not is_instance_valid(content) or not is_instance_valid(scroll):
		return
	panel.set_meta("catalog_fitting", true)
	var frame: Vector2 = panel.get_theme_stylebox("panel").get_minimum_size()
	var footer: VBoxContainer = panel.get_meta("catalog_footer")
	var card: VBoxContainer = scroll.get_parent()
	var footer_height: float = footer.get_combined_minimum_size().y
	var gap: float = card.get_theme_constant("separation")
	var text_height: float = content.get_combined_minimum_size().y
	var available: float = maxf(1.0, float(panel.get_meta("catalog_height_limit")) - frame.y - footer_height - gap)
	if panel.has_meta("catalog_art"):
		var artwork: Array = panel.get_meta("catalog_art")
		var art: Control = artwork[0]
		var picture: TextureRect = artwork[1]
		var texture: Texture2D = picture.texture
		art.visible = texture != null
		if texture != null:
			available = maxf(1.0, available - gap)
			var width: float = panel.custom_minimum_size.x if panel.custom_minimum_size.x > 1.0 else panel.size.x
			width = maxf(1.0, width - frame.x)
			var ratio: float = float(texture.get_height()) / maxf(1.0, texture.get_width())
			# Fit the whole picture. On a short screen or above active queues,
			# shrink it proportionally while reserving a useful text viewport.
			var text_reserve: float = minf(text_height, minf(160.0, maxf(64.0, available * 0.4)))
			var art_height: float = minf(width * ratio, maxf(1.0, available - text_reserve))
			var art_size: Vector2 = Vector2(art_height / ratio, art_height)
			if not art.custom_minimum_size.is_equal_approx(art_size):
				art.custom_minimum_size = art_size
			available = maxf(1.0, available - art_height)
	# Fill the middle even when this card has less text than its neighbor. The
	# artwork and footer therefore stay aligned throughout the carousel.
	if absf(scroll.custom_minimum_size.y - available) > 0.5:
		scroll.custom_minimum_size.y = available
	panel.set_meta("catalog_fitting", false)


static func fit_art(panel: PanelContainer, art: Control) -> void:
	var picture: TextureRect = art as TextureRect if art is TextureRect else art.get_node_or_null("Illustration") as TextureRect
	if picture == null:
		return
	panel.set_meta("catalog_art", [art, picture])
	var card: VBoxContainer = panel.get_meta("catalog_scroller").get_parent()
	art.reparent(card)
	card.move_child(art, 0)
	art.custom_minimum_size = Vector2.ZERO
	art.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	art.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	if art != picture:
		for overlay: Node in art.get_children():
			if overlay != picture and overlay is Control:
				overlay.hide()
	picture.minimum_size_changed.connect(_fit_height.bind(panel))
	_fit_height.call_deferred(panel)
