extends Control
## Three horizontal rows with descriptions; only real prerequisites are linked.

const LayoutScript = preload("res://client/scripts/research_layout.gd")
const ResourceInfo = preload("res://client/scripts/resource_info.gd")
const CatalogGuidance = preload("res://client/scripts/catalog_guidance.gd")
const CatalogDetails = preload("res://client/scripts/catalog_details.gd")

const NODE_HEIGHT: float = 330.0
const ROW_STEP: float = 366.0
const EDGE_GUTTER: float = 18.0
const HORIZONTAL_NODE_WIDTH: float = 330.0
const COLUMN_STEP: float = 400.0

var host
var entries: Dictionary = {}
var cards: Dictionary = {}
var selected_key: String = ""
var detail_action: Button
var detail_key: String = ""
var detail_level: int = -1
var detail_signature: String = ""
var signature: String = ""
var three_rows: bool = true
var using_three_rows: bool = false
var placements: Dictionary = {}
var node_height: float = NODE_HEIGHT
var row_step: float = ROW_STEP
var fit_queued: bool = false


func setup(client) -> void:
	host = client
	name = "TechnologyTree"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mouse_filter = Control.MOUSE_FILTER_PASS
	custom_minimum_size.y = ROW_STEP
	resized.connect(_layout)
	visibility_changed.connect(_fit_viewport)
	if host.tabs.size() > 3:
		host.tabs[3].resized.connect(_queue_fit_viewport)
	if host.tab_bodies.size() > 3:
		host.tab_bodies[3].minimum_size_changed.connect(_queue_fit_viewport)


func refresh(catalog: Array) -> void:
	three_rows = true
	var keys: Array[String] = []
	var last_row: int = 0
	entries.clear()
	for entry: Dictionary in catalog:
		var key: String = str(entry.get("key", ""))
		if key.is_empty() or (not three_rows and not entry.has("tree")):
			continue
		entries[key] = entry
		keys.append(key)
		last_row = maxi(last_row, int(entry.get("tree", {}).get("row", 0)))
	placements.clear()
	using_three_rows = false
	if three_rows:
		var graph: Dictionary = LayoutScript.three_rows(catalog)
		using_three_rows = bool(graph.get("valid", false))
		if using_three_rows:
			placements = graph["placements"]
			custom_minimum_size = Vector2(int(graph["columns"]) * COLUMN_STEP + EDGE_GUTTER * 2.0, LayoutScript.ROWS * row_step)
	# The endgame currently reaches row 9. Derive the scroll extent from data,
	# rather than clipping all technologies after the original eight rows.
	if not using_three_rows:
		custom_minimum_size = Vector2(0.0, (last_row + 1) * ROW_STEP)
	var next_signature: String = "|".join(keys)
	if signature != next_signature:
		signature = next_signature
		for child: Node in get_children():
			remove_child(child)
			child.queue_free()
		cards.clear()
		for key: String in keys:
			_make_card(key)
	_fit_viewport()
	_update_cards()
	if is_instance_valid(detail_action) and detail_action.is_visible_in_tree() and host.compact_ui.details_open() and entries.has(detail_key):
		var entry: Dictionary = entries[detail_key]
		if host.planned_queue_ui != null:
			host.planned_queue_ui.refresh_action_button(detail_action, entry, "research")
		if detail_signature != _detail_signature(entry):
			var scroll_y: int = host.compact_ui.modal_scroll.scroll_vertical
			open_details(detail_key)
			host.compact_ui._restore_details_scroll(scroll_y)
	queue_redraw()


func _make_card(key: String) -> void:
	var entry: Dictionary = entries[key]
	var button: Button = Button.new()
	button.name = "Technology_" + key
	button.action_mode = BaseButton.ACTION_MODE_BUTTON_RELEASE
	button.mouse_filter = Control.MOUSE_FILTER_PASS
	button.pressed.connect(open_details.bind(key))
	button.tooltip_text = host._server_text(entry.get("name", key))
	add_child(button)
	var margin: MarginContainer = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 9)
	button.add_child(margin)
	var stack: VBoxContainer = VBoxContainer.new()
	stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_theme_constant_override("separation", 4)
	margin.add_child(stack)
	var art: TextureRect = TextureRect.new()
	art.custom_minimum_size.y = 88
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_child(art)
	var title: Label = host._label("", 20)
	title.add_theme_font_size_override("font_size", 20)
	title.custom_minimum_size.y = 48
	title.max_lines_visible = 2
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_child(title)
	var level: Label = host._label("", 21)
	level.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	level.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_child(level)
	var status: Label = host._label("", 19)
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status.autowrap_mode = TextServer.AUTOWRAP_OFF
	status.clip_text = true
	status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_child(status)
	var description_scroll: ScrollContainer = host.TouchScrollScript.new()
	description_scroll.name = "TechnologyDescriptionScroll"
	description_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	description_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	description_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	description_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	description_scroll.custom_minimum_size.y = 24
	description_scroll.mouse_filter = Control.MOUSE_FILTER_PASS
	# The inner scroller must cancel its ancestor button too; native scroll
	# notifications only reach children, otherwise a reading swipe opens details.
	description_scroll.scroll_started.connect(func() -> void: button.notification(Control.NOTIFICATION_SCROLL_BEGIN))
	stack.add_child(description_scroll)
	var description: Label = host._label("", 21, "c9d9cb")
	description.name = "TechnologyBriefDescription"
	description.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	description.mouse_filter = Control.MOUSE_FILTER_IGNORE
	description_scroll.add_child(description)
	cards[key] = {"button": button, "title": title, "level": level, "status": status, "art": art, "description": description}


func _queue_fit_viewport() -> void:
	if fit_queued:
		return
	fit_queued = true
	_fit_viewport.call_deferred()


func _fit_viewport() -> void:
	fit_queued = false
	if is_instance_valid(host.research_tree_scroll) and not host.research_tree_scroll.item_rect_changed.is_connected(_queue_fit_viewport):
		host.research_tree_scroll.item_rect_changed.connect(_queue_fit_viewport)
	var available: float = ROW_STEP * LayoutScript.ROWS + 20.0
	if host.tabs.size() > 3 and host.tabs[3].size.y > 1.0:
		var tab: ScrollContainer = host.tabs[3]
		var tree_top: float = host.research_tree_scroll.global_position.y if is_instance_valid(host.research_tree_scroll) else tab.global_position.y
		available = maxf(1.0, tab.get_global_rect().end.y - tree_top)
		var navigation_height: float = 92.0
		if not host.nav_buttons.is_empty():
			navigation_height = host.nav_buttons[0].size.y
		# Bound fitting by the screen, not a minimum size influenced by our
		# own children. This also prevents resize loops during tab rebuilds.
		available = minf(available, maxf(1.0, host.global_position.y + host.size.y - float(host.mobile_insets.w) - tree_top - navigation_height - 10.0))
	# Reclaimed heading space belongs to the cards; descriptions scroll inside
	# each card on short displays, while all three rows remain visible.
	row_step = maxf(180.0, (available - 20.0) / LayoutScript.ROWS)
	node_height = row_step - 30.0
	if using_three_rows:
		var height: float = LayoutScript.ROWS * row_step
		if absf(custom_minimum_size.y - height) > 0.5:
			custom_minimum_size.y = height
	if is_instance_valid(host.research_tree_scroll) and absf(host.research_tree_scroll.custom_minimum_size.y - custom_minimum_size.y - 20.0) > 0.5:
		host.research_tree_scroll.custom_minimum_size.y = custom_minimum_size.y + 20.0
	_layout()


func _layout() -> void:
	var lane: float = maxf(1.0, (size.x - 2.0 * EDGE_GUTTER) / 3.0)
	for key: String in cards:
		var placement: Dictionary = placements.get(key, {}) if using_three_rows else entries[key].get("tree", {})
		var button: Button = cards[key]["button"]
		# Active/queued projects consume some of the reclaimed header space.
		# Reduce illustration/title height before shrinking the reading area.
		var compact_title: bool = node_height < 250.0
		cards[key]["art"].custom_minimum_size.y = clampf(node_height - (150.0 if compact_title else 170.0), 40.0, 88.0)
		cards[key]["title"].custom_minimum_size.y = 28.0 if compact_title else 48.0
		cards[key]["title"].max_lines_visible = 1 if compact_title else 2
		if using_three_rows:
			button.position = Vector2(EDGE_GUTTER + int(placement.get("column", 0)) * COLUMN_STEP, int(placement.get("row", 0)) * row_step + 8.0)
			button.size = Vector2(HORIZONTAL_NODE_WIDTH, node_height)
		else:
			button.position = Vector2(EDGE_GUTTER + int(placement.get("column", 0)) * lane + 8.0, int(placement.get("row", 0)) * row_step + 8.0)
			button.size = Vector2(maxf(1.0, lane - 16.0), NODE_HEIGHT)
	queue_redraw()


func _update_cards() -> void:
	var ancestors: Dictionary = _ancestors(selected_key)
	for key: String in cards:
		var entry: Dictionary = entries[key]
		var controls: Dictionary = cards[key]
		var level: int = int(entry.get("level", 0))
		var maximum: int = int(entry.get("max_level", 12))
		var ready: bool = bool(entry.get("requirements_met", false))
		var border: String = "45654c" if ready or level > 0 else "262626"
		if key == selected_key or ancestors.has(key):
			border = "edc77a"
		var button: Button = controls["button"]
		button.add_theme_stylebox_override("normal", host._style("101010" if level > 0 else "151515", border, 12, 4))
		button.add_theme_stylebox_override("hover", host._style("1d3326", "91c89b", 12, 4))
		button.add_theme_stylebox_override("pressed", host._style("2b4f36", "edc77a", 12, 4))
		controls["title"].text = host._server_text(entry.get("name", key))
		controls["description"].text = CatalogDetails.brief_description(host, entry)
		button.tooltip_text = controls["title"].text + "\n" + CatalogDetails.brief_description(host, entry)
		controls["level"].text = I18n.t("Poziom %d / %d") % [level, maximum]
		controls["art"].texture = host._catalog_texture(key, "research")
		var caption: String = I18n.t("Dostępne") if ready else I18n.t("Zablokowane")
		if level >= maximum:
			caption = I18n.t("Ukończono")
		elif level > 0 and ready:
			caption = I18n.t("Rozwijaj")
		var task: Dictionary = host.project_ui.task_for("research")
		if str(task.get("key", "")) == key:
			caption = I18n.t("W toku") + " · " + host._duration(float(task.get("ends_at", 0)) - host._server_now())
		controls["status"].text = caption
		controls["status"].add_theme_color_override("font_color", host._ui_color(Color("edc77a" if ready else "a0b3a4")))


func update_clock() -> void:
	if host.project_ui == null:
		return
	var task: Dictionary = host.project_ui.task_for("research")
	var key: String = str(task.get("key", ""))
	if cards.has(key):
		cards[key]["status"].text = I18n.t("W toku") + " · " + host._duration(float(task.get("ends_at", 0)) - host._server_now())
	refresh_detail_action()


func refresh_detail_action() -> void:
	if is_instance_valid(detail_action) and detail_action.is_visible_in_tree() and host.compact_ui.details_open() and entries.has(detail_key) and host.planned_queue_ui != null:
		host.planned_queue_ui.refresh_action_button(detail_action, entries[detail_key], "research")


func _ancestors(key: String, found: Dictionary = {}) -> Dictionary:
	var result: Dictionary = found.duplicate()
	if not entries.has(key):
		return result
	for requirement: Dictionary in entries[key].get("requirements", []):
		var parent: String = str(requirement.get("key", ""))
		if str(requirement.get("group", "")) == "research" and not result.has(parent):
			result[parent] = true
			result = _ancestors(parent, result)
	return result


func _draw() -> void:
	if host == null:
		return
	var highlighted: Dictionary = _ancestors(selected_key)
	highlighted[selected_key] = true
	var lane: float = maxf(1.0, (size.x - 2.0 * EDGE_GUTTER) / 3.0)
	for key: String in cards:
		var entry: Dictionary = entries[key]
		var target: Button = cards[key]["button"]
		for requirement: Dictionary in entry.get("requirements", []):
			var parent_key: String = str(requirement.get("key", ""))
			if str(requirement.get("group", "")) != "research" or not cards.has(parent_key):
				continue
			var source: Button = cards[parent_key]["button"]
			if using_three_rows:
				_draw_horizontal_edge(source, target, requirement, highlighted.has(key) and highlighted.has(parent_key))
				continue
			var start: Vector2 = source.position + Vector2(source.size.x * 0.5, source.size.y)
			var end: Vector2 = target.position + Vector2(target.size.x * 0.5, 0)
			var source_row: int = int(entries[parent_key].get("tree", {}).get("row", 0))
			var target_row: int = int(entry.get("tree", {}).get("row", 0))
			var source_col: int = int(entries[parent_key].get("tree", {}).get("column", 0))
			var target_col: int = int(entry.get("tree", {}).get("column", 0))
			var points: PackedVector2Array = PackedVector2Array([start])
			if target_row == source_row + 1:
				var middle: float = (start.y + end.y) * 0.5
				points.append(Vector2(start.x, middle))
				points.append(Vector2(end.x, middle))
			else:
				# Long edges travel in the lane gutters, never across a card.
				var gutter: float = EDGE_GUTTER + lane * target_col
				if target_col == 0:
					gutter = 8.0
				elif target_col == 2 and source_col == 2:
					gutter = size.x - 8.0
				points.append(Vector2(start.x, start.y + 20.0))
				points.append(Vector2(gutter, start.y + 20.0))
				points.append(Vector2(gutter, end.y - 22.0))
				points.append(Vector2(end.x, end.y - 22.0))
			points.append(end)
			var active: bool = highlighted.has(key) and highlighted.has(parent_key)
			var color: Color = host._ui_color(Color("edc77a" if active else "66896d" if bool(requirement.get("met", false)) else "262626"))
			draw_polyline(points, color, 3.0 if active else 2.0, true)
			draw_line(end + Vector2(-5, -7), end, color, 2.0, true)
			draw_line(end + Vector2(5, -7), end, color, 2.0, true)


func _draw_horizontal_edge(source: Button, target: Button, requirement: Dictionary, active: bool) -> void:
	var start: Vector2 = source.position + Vector2(source.size.x, source.size.y * 0.5)
	var end: Vector2 = target.position + Vector2(0.0, target.size.y * 0.5)
	var points: PackedVector2Array = PackedVector2Array([start])
	if is_equal_approx(start.y, end.y) and end.x - start.x < COLUMN_STEP:
		points.append(end)
	else:
		# Route long lines in the spaces between rows and columns, keeping
		# every technology card unobstructed. Arrowheads point left to right.
		var exit_x: float = start.x + 28.0
		var entry_x: float = end.x - 24.0
		var gutter_y: float = source.position.y + source.size.y + 26.0
		points.append(Vector2(exit_x, start.y))
		points.append(Vector2(exit_x, gutter_y))
		points.append(Vector2(entry_x, gutter_y))
		points.append(Vector2(entry_x, end.y))
		points.append(end)
	var color: Color = host._ui_color(Color("edc77a" if active else "66896d" if bool(requirement.get("met", false)) else "526357"))
	draw_polyline(points, color, 3.0 if active else 2.0, true)
	draw_line(end + Vector2(-7, -5), end, color, 2.0, true)
	draw_line(end + Vector2(-7, 5), end, color, 2.0, true)


func focus_technology(key: String) -> void:
	if not cards.has(key):
		return
	selected_key = key
	host.compact_ui.close_details()
	host._open_tab(3)
	_update_cards()
	queue_redraw()
	if using_three_rows and is_instance_valid(host.research_tree_scroll):
		host.research_tree_scroll.ensure_control_visible.call_deferred(cards[key]["button"])
	host.tabs[3].ensure_control_visible.call_deferred(cards[key]["button"])


func _detail_signature(entry: Dictionary) -> String:
	return JSON.stringify([entry, host.detailed_descriptions, host.state.get("resources", {}), host.state.get("production", {}), host.state.get("production_status", {}), host.state.get("limits", {})])


func open_details(key: String) -> void:
	if not entries.has(key) or host.compact_ui == null:
		return
	selected_key = key
	detail_key = key
	var entry: Dictionary = entries[key]
	detail_level = int(entry.get("level", 0))
	detail_signature = _detail_signature(entry)
	_update_cards()
	queue_redraw()
	host.compact_ui._begin_details(host._server_text(entry.get("name", key)))
	var body: VBoxContainer = host.compact_ui.modal_body
	var art: Texture2D = host._catalog_texture(key, "research")
	if art != null:
		host.compact_ui._details_art(art)
	body.add_child(host._label(I18n.t("Poziom %d / %d") % [detail_level, int(entry.get("max_level", 12))], 25))
	for text: String in CatalogDetails.description_paragraphs(host, entry, "research", host.detailed_descriptions):
		var description: Label = host._label(text, 23)
		description.name = "ResearchDescription"
		body.add_child(description)
	if entry.has("effect_current"):
		body.add_child(host._label(I18n.t("Teraz: ") + host._server_text(entry["effect_current"]), 22))
		if detail_level < int(entry.get("max_level", 12)):
			body.add_child(host._label(I18n.t("Następny poziom: ") + host._server_text(entry.get("effect_next", "")), 22, "edc77a"))
	elif key in ["propulsion", "weapons"]:
		body.add_child(host._label(I18n.t("Premia: +%d%% → +%d%%") % [detail_level * 15, mini(detail_level + 1, 12) * 15], 22))
	if detail_level < int(entry.get("max_level", 12)):
		body.add_child(ResourceInfo.label(host, ResourceInfo.cost(host, entry.get("cost", {})), 24))
		var time: Label = host._label(I18n.t("Czas: ") + host._duration(float(entry.get("seconds", 0))), 22)
		time.name = "ResearchTime"
		body.add_child(time)
	# The one action below Time becomes planning while empire research is busy.
	# Availability and commands still come from the authoritative catalog.
	var actions: VBoxContainer = VBoxContainer.new()
	actions.name = "ResearchDetailsActions"
	actions.add_theme_constant_override("separation", 12)
	body.add_child(actions)
	detail_action = host._button(I18n.t("Badaj"), _start.bind(key), true)
	detail_action.name = "StartResearchDetails"
	if host.planned_queue_ui != null:
		host.planned_queue_ui.refresh_action_button(detail_action, entry, "research")
	actions.add_child(detail_action)
	var reason: String = CatalogGuidance.explanation(host, entry, 1, "research")
	if not reason.is_empty():
		var explanation: Label = host._label(reason, 21, "edc77a")
		explanation.name = "ResearchDetailsExplanation"
		actions.add_child(explanation)
	var requirements: VBoxContainer = VBoxContainer.new()
	requirements.name = "ResearchRequirements"
	requirements.add_theme_constant_override("separation", 12)
	body.add_child(requirements)
	requirements.add_child(host._label(I18n.t("Wymagania"), 25))
	for requirement: Dictionary in entry.get("requirements", []):
		var parent: String = str(requirement.get("key", ""))
		var group: String = str(requirement.get("group", "buildings"))
		var current: int = int(requirement.get("current", host.state.get(group, {}).get(parent, 0)))
		var caption: String = ("✓ " if bool(requirement.get("met", false)) else "○ ") + host._server_text(requirement.get("name", parent)) + " · %d/%d" % [current, int(requirement.get("level", 0))]
		var callback: Callable = focus_technology.bind(parent) if group == "research" else host.compact_ui._open_catalog_target.bind(group, parent)
		requirements.add_child(host._button(caption, callback))
	var unlocks: Array = entry.get("unlocks", [])
	if not unlocks.is_empty():
		var section: VBoxContainer = VBoxContainer.new()
		section.name = "TechnologyUnlocks"
		section.add_theme_constant_override("separation", 12)
		body.add_child(section)
		section.add_child(host._label(I18n.t("Odblokowuje"), 25))
		section.add_child(host._label(I18n.t("Wymagany poziom tego badania; pozostałe wymagania sprawdzisz w szczegółach."), 20))
		for unlock: Dictionary in unlocks:
			var target_key: String = str(unlock.get("key", ""))
			var group: String = str(unlock.get("group", ""))
			var caption: String = I18n.t("Poziom %d · %s") % [int(unlock.get("level", 1)), host._server_text(unlock.get("name", target_key))]
			var link: Button = host._button(caption, host.compact_ui._open_catalog_target.bind(group, target_key))
			link.name = "Unlock_" + target_key
			link.icon = host._catalog_texture(target_key, group)
			link.expand_icon = true
			link.add_theme_constant_override("icon_max_width", 44)
			section.add_child(link)


func _open_building(key: String) -> void:
	if host.building_rows.has(key):
		host.compact_ui._open_catalog(host.building_rows[key])


func _start(key: String) -> void:
	host._catalog_action("research", key)
