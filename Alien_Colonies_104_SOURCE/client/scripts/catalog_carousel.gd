extends VBoxContainer
## Presentation only: keep existing catalog controls alive while browsing.
## Native touch scrolling cancels card taps and action buttons during a swipe.
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
const CardLayout = preload("res://client/scripts/catalog_card_layout.gd")
const GAP: float = 16.0
const PEEK: float = 30.0
const MAX_CARD_WIDTH: float = 760.0

var host
var cards: HBoxContainer
var scroll: ScrollContainer
var previous: Button
var next: Button
var counter: Label
var card_width: float = 0.0
var layout_queued: bool = false
var catalog_kind: String = "build"
var viewport_height: float = 0.0


func setup(client, kind: String) -> void:
	host = client
	catalog_kind = kind
	name = "BuildingCarousel" if kind == "build" else "DefenseCarousel" if kind == "defense" else "ShipCarousel"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	mouse_filter = Control.MOUSE_FILTER_PASS
	add_theme_constant_override("separation", 10)
	var navigation: HBoxContainer = host._row(self)
	previous = host._button("‹", _step.bind(-1))
	previous.name = "PreviousCatalogCard"
	previous.tooltip_text = I18n.t("Poprzednia karta")
	previous.custom_minimum_size = Vector2(68, 56)
	previous.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	navigation.add_child(previous)
	counter = host._label("0 / 0", 22, "a5d5ac")
	counter.name = "CatalogCardCounter"
	counter.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	counter.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	navigation.add_child(counter)
	next = host._button("›", _step.bind(1))
	next.name = "NextCatalogCard"
	next.tooltip_text = I18n.t("Następna karta")
	next.custom_minimum_size = Vector2(68, 56)
	next.size_flags_horizontal = Control.SIZE_SHRINK_END
	navigation.add_child(next)
	scroll = TouchScroll.new()
	scroll.name = "CatalogHorizontalScroll"
	scroll.lock_nested_scroll_axis = true
	scroll.mouse_filter = Control.MOUSE_FILTER_PASS
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	add_child(scroll)
	cards = HBoxContainer.new()
	cards.name = "CatalogCards"
	cards.add_theme_constant_override("separation", int(GAP))
	cards.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	scroll.add_child(cards)
	cards.child_order_changed.connect(refresh)
	cards.minimum_size_changed.connect(_height_changed)
	scroll.get_h_scroll_bar().value_changed.connect(_update_navigation)
	resized.connect(refresh)
	visibility_changed.connect(refresh)
	if not host.tabs.is_empty():
		host.tabs[0 if kind == "build" else 2].resized.connect(refresh)
	get_parent().minimum_size_changed.connect(refresh)
	refresh()


func refresh() -> void:
	if not layout_queued:
		layout_queued = true
		_layout.call_deferred()


func _layout() -> void:
	layout_queued = false
	if host == null or not is_instance_valid(scroll) or not is_instance_valid(cards):
		return
	var available: float = scroll.size.x if scroll.size.x > 1.0 else size.x
	if available <= 1.0:
		return
	var old_index: int = current_index()
	var width: float = minf(MAX_CARD_WIDTH, maxf(1.0, available - PEEK - GAP))
	var width_changed: bool = absf(width - card_width) > 1.0
	card_width = width
	for card: Node in cards.get_children():
		if card is Control:
			card.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
			card.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
			if absf(card.custom_minimum_size.x - width) > 1.0:
				card.custom_minimum_size.x = width
	if width_changed and old_index > 0:
		_scroll_to.call_deferred(old_index)
	_update_navigation()
	_height_changed.call_deferred()


func _height_changed() -> void:
	if host == null or not is_instance_valid(scroll) or not is_instance_valid(cards):
		return
	# Never derive the viewport from the tallest card: long descriptions and
	# locked requirements must scroll inside that card, not push the game down.
	var height: float = viewport_height
	if height <= 0.0 and not host.tabs.is_empty():
		var tab: ScrollContainer = host.tabs[0 if catalog_kind == "build" else 2]
		var bottom: float = tab.global_position.y + tab.size.y
		if not host.nav_buttons.is_empty():
			var navigation: Control = host.nav_buttons[0].get_parent()
			var viewport_bottom: float = host.global_position.y + host.size.y - host.mobile_insets.w - navigation.size.y - 10.0
			bottom = minf(bottom, viewport_bottom)
		height = maxf(1.0, bottom - global_position.y)
	elif height <= 0.0:
		height = maxf(360.0, host.size.y * 0.60)
	var navigation_height: float = previous.get_parent().get_combined_minimum_size().y
	var bar_height: float = scroll.get_h_scroll_bar().get_combined_minimum_size().y
	var card_limit: float = maxf(1.0, height - navigation_height - 10.0 - bar_height)
	for child: Node in cards.get_children():
		if child is PanelContainer:
			CardLayout.set_height_limit(child, card_limit)
	# The catalog is a fixed-height viewport, independent of each entry's text.
	# Every card reaches its bottom, keeping costs and actions on the same line.
	var content_height: float = card_limit + bar_height
	if absf(scroll.custom_minimum_size.y - content_height) > 0.5:
		scroll.custom_minimum_size.y = content_height


func current_index() -> int:
	if not is_instance_valid(cards) or cards.get_child_count() == 0 or card_width <= 0.0:
		return 0
	return clampi(roundi(float(scroll.scroll_horizontal) / (card_width + GAP)), 0, cards.get_child_count() - 1)


func _step(direction: int) -> void:
	var position: float = float(scroll.scroll_horizontal) / maxf(1.0, card_width + GAP)
	_scroll_to(floori(position) + 1 if direction > 0 else ceili(position) - 1)


func _scroll_to(index: int) -> void:
	if cards.get_child_count() == 0:
		return
	index = clampi(index, 0, cards.get_child_count() - 1)
	scroll.scroll_horizontal = roundi(index * (card_width + GAP))
	_update_navigation()


func _update_navigation(_value: float = 0.0) -> void:
	if not is_instance_valid(counter) or not is_instance_valid(cards):
		return
	var count: int = cards.get_child_count()
	var index: int = current_index()
	counter.text = "%d / %d" % [index + 1 if count else 0, count]
	var bar: HScrollBar = scroll.get_h_scroll_bar()
	var maximum: float = maxf(0.0, bar.max_value - bar.page)
	previous.disabled = count <= 1 or scroll.scroll_horizontal <= 0
	next.disabled = count <= 1 or float(scroll.scroll_horizontal) >= maximum - 1.0
