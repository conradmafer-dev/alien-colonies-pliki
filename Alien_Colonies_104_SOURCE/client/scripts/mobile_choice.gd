extends Button

const RaceTheme = preload("res://client/scripts/race_theme.gd")
## A touch-friendly OptionButton replacement. The list is a normal in-game
## ScrollContainer, so dragging over a row scrolls and cancels its pending tap.

signal item_selected(index: int)

const TouchScrollScript = preload("res://client/scripts/touch_scroll.gd")
const ROW_HEIGHT: float = 80.0
static var _back_guard_count: int = 0
static var _original_quit_on_go_back: bool = true

@export var dialog_title: String = "Wybierz"
var item_count: int:
	get:
		return _items.size()
var selected: int:
	get:
		return _selected
	set(value):
		select(value)

var _items: Array[Dictionary] = []
var _selected: int = -1
var _layer: CanvasLayer
var _overlay: Control
var _panel: PanelContainer
var _list: ScrollContainer
var _rows: VBoxContainer
var _search: LineEdit
var _backdrop_origin: Vector2
var _backdrop_down: bool = false
var _backdrop_dragged: bool = false
var _back_guard_active: bool = false
var _keyboard_baseline_height: int = 0
var _keyboard_overlap: float = 0.0


func _ready() -> void:
	I18n.language_changed.connect(_refresh_language)
	pressed.connect(open)
	visibility_changed.connect(_owner_visibility_changed)
	action_mode = BaseButton.ACTION_MODE_BUTTON_RELEASE
	mouse_filter = Control.MOUSE_FILTER_PASS
	alignment = HORIZONTAL_ALIGNMENT_LEFT
	text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	set_process(false)
	set_process_input(false)


func add_item(caption: String, id: int = -1) -> void:
	_items.append({"text": caption, "id": _items.size() if id < 0 else id, "metadata": null})
	if _selected < 0:
		select(0)
	if is_open():
		_refresh_rows()


func clear() -> void:
	close()
	_items.clear()
	_selected = -1
	text = ""


func set_item_metadata(index: int, value: Variant) -> void:
	if index >= 0 and index < item_count:
		_items[index]["metadata"] = value


func get_item_metadata(index: int) -> Variant:
	return _items[index]["metadata"] if index >= 0 and index < item_count else null


func get_item_text(index: int) -> String:
	return str(_items[index]["text"]) if index >= 0 and index < item_count else ""


func get_item_id(index: int) -> int:
	return int(_items[index]["id"]) if index >= 0 and index < item_count else -1


func get_selected_id() -> int:
	return get_item_id(_selected)


func get_selected_metadata() -> Variant:
	return get_item_metadata(_selected)


func select(index: int) -> void:
	if index < -1 or index >= item_count:
		return
	_selected = index
	text = get_item_text(index)
	# Programmatic refreshes must never trigger a mission/planet request.
	if is_open():
		for row: Node in _rows.get_children():
			if row is Button:
				var row_index: int = int(row.get_meta("choice_index", -1))
				(row as Button).set_pressed_no_signal(row_index == index)
				(row as Button).text = ("✓  " if row_index == index else "     ") + get_item_text(row_index)


func is_open() -> bool:
	return is_instance_valid(_layer)


func open() -> void:
	if disabled or item_count == 0 or not is_inside_tree() or not is_visible_in_tree() or is_open():
		return
	_acquire_back_guard()
	_keyboard_baseline_height = DisplayServer.window_get_size().y
	_layer = CanvasLayer.new()
	_layer.name = "MobileChoiceLayer"
	_layer.layer = 80
	# An ancestor page scroller must not rewrite this separate modal's filters.
	_layer.set_meta("touch_scroll_preserve_input", true)
	add_child(_layer)
	_overlay = Control.new()
	_overlay.name = "ChoiceOverlay"
	_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_overlay.theme = _inherited_theme()
	_layer.add_child(_overlay)
	_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var backdrop: ColorRect = ColorRect.new()
	backdrop.name = "Backdrop"
	backdrop.color = RaceTheme.color(Color("050b08db"))
	backdrop.mouse_filter = Control.MOUSE_FILTER_STOP
	_overlay.add_child(backdrop)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.gui_input.connect(_backdrop_input)
	_panel = PanelContainer.new()
	_panel.name = "ChoicePanel"
	_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = RaceTheme.color(Color("14291d"))
	style.border_color = RaceTheme.color(Color("66896d"))
	style.set_border_width_all(1)
	style.set_corner_radius_all(20)
	style.content_margin_left = 18
	style.content_margin_right = 18
	style.content_margin_top = 18
	style.content_margin_bottom = 18
	_panel.add_theme_stylebox_override("panel", style)
	_overlay.add_child(_panel)
	var body: VBoxContainer = VBoxContainer.new()
	body.add_theme_constant_override("separation", 12)
	_panel.add_child(body)
	var header: HBoxContainer = HBoxContainer.new()
	header.add_theme_constant_override("separation", 12)
	body.add_child(header)
	var heading: Label = Label.new()
	heading.name = "ChoiceTitle"
	heading.text = I18n.t(dialog_title)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	heading.add_theme_font_size_override("font_size", 28)
	header.add_child(heading)
	var dismiss: Button = Button.new()
	dismiss.name = "CloseChoice"
	dismiss.text = I18n.t("Zamknij")
	dismiss.custom_minimum_size = Vector2(132, 72)
	dismiss.add_theme_font_size_override("font_size", 23)
	dismiss.pressed.connect(close)
	header.add_child(dismiss)
	if item_count > 12:
		_search = LineEdit.new()
		_search.name = "Search"
		_search.placeholder_text = I18n.t("Szukaj…")
		_search.custom_minimum_size.y = 72
		_search.add_theme_font_size_override("font_size", 24)
		_search.text_changed.connect(func(_query: String) -> void: _refresh_rows())
		_search.text_submitted.connect(func(_query: String) -> void: _hide_search_keyboard())
		body.add_child(_search)
	_list = TouchScrollScript.new()
	_list.name = "ChoiceScroll"
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_list.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	body.add_child(_list)
	_rows = VBoxContainer.new()
	_rows.name = "ChoiceRows"
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rows.add_theme_constant_override("separation", 8)
	_list.add_child(_rows)
	_refresh_rows()
	_overlay.resized.connect(_layout_panel)
	_layout_panel()
	dismiss.grab_focus()
	set_process(true)
	set_process_input(true)
	call_deferred("_reveal_selected")


func _inherited_theme() -> Theme:
	var current: Node = self
	while current != null:
		if current is Control and (current as Control).theme != null:
			return (current as Control).theme
		current = current.get_parent()
	return null


func _layout_panel() -> void:
	if not is_open():
		return
	var available: Vector2 = _overlay.size
	available.y = maxf(0.0, available.y - _keyboard_overlap)
	var width: float = minf(680.0, available.x - 32.0)
	var desired_height: float = 128.0 + minf(item_count, 8) * (ROW_HEIGHT + 8.0)
	if is_instance_valid(_search):
		desired_height += 84.0
	var height: float = minf(desired_height, available.y - 48.0)
	_panel.size = Vector2(maxf(0.0, width), maxf(0.0, height))
	_panel.position = (available - _panel.size) * 0.5


func _refresh_rows() -> void:
	if not is_open() or not is_instance_valid(_rows):
		return
	for child: Node in _rows.get_children():
		_rows.remove_child(child)
		child.queue_free()
	var query: String = _search.text.strip_edges().to_lower() if is_instance_valid(_search) else ""
	for index: int in range(item_count):
		var caption: String = get_item_text(index)
		if not query.is_empty() and not caption.to_lower().contains(query):
			continue
		var row: Button = Button.new()
		row.name = "Choice_%d" % index
		row.text = ("✓  " if index == _selected else "     ") + caption
		row.set_meta("choice_index", index)
		row.custom_minimum_size.y = ROW_HEIGHT
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.alignment = HORIZONTAL_ALIGNMENT_LEFT
		row.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		row.add_theme_font_size_override("font_size", 26)
		row.toggle_mode = true
		row.set_pressed_no_signal(index == _selected)
		row.pressed.connect(_choose.bind(index))
		_rows.add_child(row)
	if _rows.get_child_count() == 0:
		var empty: Label = Label.new()
		empty.text = I18n.t("Brak wyników")
		empty.custom_minimum_size.y = ROW_HEIGHT
		empty.add_theme_font_size_override("font_size", 24)
		_rows.add_child(empty)
	_list.scroll_vertical = 0


func _reveal_selected() -> void:
	if not is_open():
		return
	for child: Node in _rows.get_children():
		if child is Button and int(child.get_meta("choice_index", -1)) == _selected:
			_list.ensure_control_visible(child as Control)
			return


func _choose(index: int) -> void:
	if not is_open() or disabled or index < 0 or index >= item_count:
		return
	select(index)
	close()
	item_selected.emit(index)


func close() -> void:
	var was_open: bool = is_open()
	if was_open:
		_hide_search_keyboard()
		_layer.visible = false
		remove_child(_layer)
		_layer.queue_free()
	_layer = null
	_overlay = null
	_panel = null
	_list = null
	_rows = null
	_search = null
	_backdrop_down = false
	_backdrop_dragged = false
	_keyboard_overlap = 0.0
	_release_back_guard()
	set_process(false)
	set_process_input(false)
	if was_open and is_inside_tree() and is_visible_in_tree() and not disabled:
		grab_focus()


func _process(_delta: float) -> void:
	if disabled or not is_visible_in_tree():
		close()
		return
	_update_keyboard_overlap()


func _update_keyboard_overlap() -> void:
	if not DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):
		return
	var keyboard_height: int = DisplayServer.virtual_keyboard_get_height()
	var window_height: int = DisplayServer.window_get_size().y
	if keyboard_height == 0:
		_keyboard_baseline_height = window_height
	# Some Android windows resize for the keyboard; others draw beneath it.
	# Remove only the portion that the platform has not already excluded.
	var already_resized: int = maxi(0, _keyboard_baseline_height - window_height)
	var overlap_pixels: int = maxi(0, keyboard_height - already_resized)
	var screen_inverse: Transform2D = get_viewport().get_screen_transform().affine_inverse()
	var overlap: float = float(overlap_pixels) * screen_inverse.y.length()
	if not is_equal_approx(_keyboard_overlap, overlap):
		_keyboard_overlap = overlap
		_layout_panel()


func _hide_search_keyboard() -> void:
	if is_instance_valid(_search):
		if _search.has_focus():
			_search.release_focus()
		# A tapped result can already have taken focus from the editor while
		# Android is still showing its keyboard.
		if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):
			DisplayServer.virtual_keyboard_hide()


func _acquire_back_guard() -> void:
	if _back_guard_active:
		return
	if _back_guard_count == 0:
		_original_quit_on_go_back = get_tree().quit_on_go_back
	_back_guard_count += 1
	_back_guard_active = true
	get_tree().quit_on_go_back = false


func _release_back_guard() -> void:
	if not _back_guard_active:
		return
	_back_guard_active = false
	_back_guard_count = maxi(0, _back_guard_count - 1)
	if _back_guard_count == 0 and is_inside_tree():
		get_tree().quit_on_go_back = _original_quit_on_go_back


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_GO_BACK_REQUEST and is_open():
		# Keep automatic quitting disabled until this notification is finished.
		close.call_deferred()
	elif what == NOTIFICATION_EXIT_TREE:
		_release_back_guard()


func _owner_visibility_changed() -> void:
	if is_open() and not is_visible_in_tree():
		close()


func _input(event: InputEvent) -> void:
	if is_open() and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
		close()


func _backdrop_input(event: InputEvent) -> void:
	# A deliberate tap dismisses; sliding a finger on the dimmed background
	# must not accidentally dismiss the list or reach the game underneath.
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			_backdrop_origin = event.position
			_backdrop_down = true
			_backdrop_dragged = false
		elif _backdrop_down:
			var dismiss: bool = not _backdrop_dragged and event.position.distance_to(_backdrop_origin) <= 12.0
			_backdrop_down = false
			if dismiss:
				close()
	elif event is InputEventMouseMotion and _backdrop_down:
		if event.position.distance_to(_backdrop_origin) > 12.0:
			_backdrop_dragged = true


func _refresh_language() -> void:
	# Only translate authored dialog chrome; items may contain player names.
	# Keep the search text, selection, open modal and its scroll position.
	if not is_open():
		return
	var heading: Label = _panel.find_child("ChoiceTitle", true, false) as Label
	if is_instance_valid(heading):
		heading.text = I18n.t(dialog_title)
	var dismiss: Button = _panel.find_child("CloseChoice", true, false) as Button
	if is_instance_valid(dismiss):
		dismiss.text = I18n.t("Zamknij")
	if is_instance_valid(_search):
		_search.placeholder_text = I18n.t("Szukaj…")
	var scroll_position: int = _list.scroll_vertical
	_refresh_rows()
	_list.set_deferred("scroll_vertical", scroll_position)
