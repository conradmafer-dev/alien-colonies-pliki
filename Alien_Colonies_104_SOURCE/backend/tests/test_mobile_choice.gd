extends SceneTree
## Offline viewport checks. Add --emulate-touchscreen on a touchscreen-capable
## display for the engine's kinetic drag path; cancellation is always checked.

const MobileChoice = preload("res://client/scripts/mobile_choice.gd")
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")

var checks: int = 0
var failures: int = 0
var selected_events: Array[int] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	root.size = Vector2i(720, 1000)
	root.content_scale_size = Vector2i(720, 1000)
	var owner: Control = Control.new()
	root.add_child(owner)
	owner.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var outer: ScrollContainer = TouchScroll.new()
	outer.size = Vector2(600, 600)
	owner.add_child(outer)
	var body: VBoxContainer = VBoxContainer.new()
	body.custom_minimum_size = Vector2(580, 1300)
	outer.add_child(body)
	var choice: Button = MobileChoice.new()
	choice.dialog_title = "Wybierz układ"
	choice.custom_minimum_size = Vector2(500, 80)
	body.add_child(choice)
	choice.item_selected.connect(func(index: int) -> void: selected_events.append(index))
	_expect(choice.selected == -1 and choice.item_count == 0, "Empty choice has no selected item")
	choice.open()
	_expect(not choice.is_open(), "An empty choice never creates an invalid modal")
	for index: int in range(90):
		choice.add_item("Atlas %d / Planeta %d" % [index, index])
		choice.set_item_metadata(index, "planet_%d" % index)
	choice.select(2)
	_expect(choice.text == "Atlas 2 / Planeta 2", "Programmatic selection updates the visible caption")
	_expect(choice.get_item_metadata(2) == "planet_2" and choice.get_selected_id() == 2, "Selection retains stable metadata and ids")
	_expect(selected_events.is_empty(), "Programmatic selection never triggers gameplay requests")
	choice.select(999)
	_expect(choice.selected == 2, "Out-of-range selection does not corrupt a valid selection")
	await process_frame
	await process_frame
	_expect(choice.mouse_filter == Control.MOUSE_FILTER_PASS, "Closed chooser lets the outer page receive a drag")
	if DisplayServer.is_touchscreen_available():
		var closed_origin: Vector2 = choice.get_global_rect().get_center()
		_mouse_move(closed_origin, Vector2.ZERO)
		_mouse_button(closed_origin, true)
		_mouse_move(closed_origin - Vector2(0, 32), Vector2(0, -32), MOUSE_BUTTON_MASK_LEFT)
		_mouse_button(closed_origin - Vector2(0, 32), false)
		_expect(outer.scroll_vertical > 0 and not choice.is_open(), "Dragging a closed chooser scrolls the page without opening its list")
		outer.scroll_vertical = 0
	choice.open()
	choice.open()
	await process_frame
	await process_frame
	_expect(choice.is_open() and choice.get_child_count() == 1, "Repeated opening produces a single modal")
	var panel: Control = choice._panel
	var scroller: ScrollContainer = choice._list
	var rows: VBoxContainer = choice._rows
	_expect(root.get_visible_rect().encloses(panel.get_global_rect()), "Modal fits the short phone viewport")
	_expect(scroller.size.y < rows.size.y and scroller.size.y > 100, "Long list has a bounded scrolling viewport")
	_expect(rows.get_child_count() == 90, "Every planet remains available in the list")
	choice.set_process(false)
	choice._keyboard_overlap = 400.0
	choice._layout_panel()
	await process_frame
	await process_frame
	_expect(choice._panel.get_global_rect().end.y <= 600.0, "Modal stays above a simulated 400px keyboard overlap")
	_expect(choice._search.get_global_rect().end.y < 600.0 and choice._list.size.y >= 80.0, "Search and at least one full destination row remain visible above the keyboard")
	choice._keyboard_overlap = 0.0
	choice._layout_panel()
	choice.set_process(true)
	await process_frame
	await process_frame
	var first: Button = rows.get_child(0)
	_expect(first.size.y >= 80 and first.size.x >= 400, "Whole rows are large touch targets")
	_expect(first.mouse_filter == Control.MOUSE_FILTER_PASS and first.action_mode == BaseButton.ACTION_MODE_BUTTON_RELEASE, "Rows bubble drags to native scrolling and select only on release")
	_expect(first.autowrap_mode == TextServer.AUTOWRAP_OFF, "Long planet captions stay on one horizontal line")
	scroller.scroll_vertical = 0
	await process_frame
	var origin: Vector2 = first.get_global_rect().get_center()
	_mouse_move(origin, Vector2.ZERO)
	_mouse_button(origin, true)
	_expect(selected_events.is_empty(), "Touch-down on a row does not choose a planet")
	scroller.propagate_notification(Control.NOTIFICATION_SCROLL_BEGIN)
	_mouse_button(origin, false)
	_expect(selected_events.is_empty() and choice.is_open(), "A native scroll start cancels row activation")
	if DisplayServer.is_touchscreen_available():
		_mouse_move(origin, Vector2.ZERO)
		_mouse_button(origin, true)
		_mouse_move(origin - Vector2(0, 70), Vector2(0, -70), MOUSE_BUTTON_MASK_LEFT)
		_expect(scroller.scroll_vertical > 0, "Dragging over a list row advances native scrolling")
		_mouse_button(origin - Vector2(0, 70), false)
		_expect(selected_events.is_empty() and choice.is_open(), "A native drag never selects a target")
	else:
		print("Native kinetic drag requires a touchscreen-capable DisplayServer; scroll cancellation verified via engine notification.")
	choice._search.text = "Atlas 89 /"
	choice._search.text_changed.emit(choice._search.text)
	await process_frame
	await process_frame
	_expect(choice._rows.get_child_count() == 1, "Search makes distant destinations easy to find")
	var last: Button = choice._rows.get_child(0)
	_expect(int(last.get_meta("choice_index")) == 89, "Search preserves the destination's original index")
	origin = last.get_global_rect().get_center()
	_mouse_move(origin, Vector2.ZERO)
	_mouse_button(origin, true)
	_mouse_button(origin, false)
	_expect(selected_events == [89] and choice.selected == 89, "A stationary tap selects the correct destination exactly once")
	_expect(not choice.is_open(), "A completed selection dismisses the overlay")
	await process_frame
	choice.open()
	await process_frame
	await process_frame
	var outside: Vector2 = Vector2(3, 3)
	_mouse_move(outside, Vector2.ZERO)
	_mouse_button(outside, true)
	_mouse_move(Vector2(3, 65), Vector2(0, 62), MOUSE_BUTTON_MASK_LEFT)
	_mouse_move(outside, Vector2(0, -62), MOUSE_BUTTON_MASK_LEFT)
	_mouse_button(outside, false)
	_expect(choice.is_open(), "A backdrop drag returning to its origin does not dismiss")
	_mouse_move(outside, Vector2.ZERO)
	_mouse_button(outside, true)
	_mouse_button(outside, false)
	_expect(not choice.is_open(), "A deliberate backdrop tap dismisses")
	await process_frame
	choice.open()
	owner.hide()
	await process_frame
	_expect(not choice.is_open(), "Changing page or hiding the owner removes its overlay")
	owner.show()
	choice.open()
	choice.disabled = true
	await process_frame
	_expect(not choice.is_open(), "Disabling the chooser also closes its overlay")
	choice.disabled = false
	choice.open()
	choice.clear()
	await process_frame
	_expect(not choice.is_open() and choice.selected == -1 and choice.item_count == 0, "Refreshing an emptied list cannot leave a stale modal")
	for caption: String in ["Zwiad", "Kolonizacja", "Atak", "Transport"]:
		choice.add_item(caption)
	root.size = Vector2i(480, 720)
	root.content_scale_size = Vector2i(480, 720)
	choice.open()
	await process_frame
	await process_frame
	_expect(root.get_visible_rect().encloses(choice._panel.get_global_rect()), "Four mission choices fit the small phone viewport")
	_expect(choice._search == null, "Short mission list has no unnecessary search field")
	choice.close()
	var editor: LineEdit = LineEdit.new()
	owner.add_child(editor)
	editor.grab_focus()
	choice.close()
	choice.clear()
	_expect(root.gui_get_focus_owner() == editor, "Polling or clearing a closed chooser never steals an editor's focus")
	choice.add_item("Zwiad")
	var original_back: bool = quit_on_go_back
	choice.open()
	_expect(not quit_on_go_back, "An open chooser prevents Android Back from quitting the game")
	choice.notification(Node.NOTIFICATION_WM_GO_BACK_REQUEST)
	await process_frame
	_expect(not choice.is_open() and quit_on_go_back == original_back, "Android Back closes the list and restores the previous game policy")
	quit_on_go_back = false
	choice.open()
	choice.close()
	_expect(not quit_on_go_back, "Closing a chooser preserves a pre-existing custom Android Back policy")
	quit_on_go_back = original_back
	choice.open()
	owner.queue_free()
	await process_frame
	_expect(quit_on_go_back == original_back, "Destroying an open chooser restores Android Back policy")
	print("Mobile choice: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)


func _mouse_button(point: Vector2, down: bool) -> void:
	var event: InputEventMouseButton = InputEventMouseButton.new()
	event.position = point
	event.global_position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if down else 0
	event.pressed = down
	root.push_input(event, true)


func _mouse_move(point: Vector2, relative: Vector2, mask: int = 0) -> void:
	var event: InputEventMouseMotion = InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	event.relative = relative
	event.button_mask = mask
	root.push_input(event, true)


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
