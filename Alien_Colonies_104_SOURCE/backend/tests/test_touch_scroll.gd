extends SceneTree
## Run: godot --headless --path . --script tests/test_touch_scroll.gd
## Native drag coverage additionally needs a touchscreen-capable display or
## Godot's --emulate-touchscreen option. No HTTP or account mutation occurs.

const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
const GalaxyMap = preload("res://client/scripts/galaxy_map.gd")
var checks: int = 0
var failures: int = 0
var taps: int = 0
var selected: int = 0
var native_begins: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var scroll: ScrollContainer = TouchScroll.new()
	scroll.position = Vector2(10, 10)
	scroll.size = Vector2(360, 320)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var body: VBoxContainer = VBoxContainer.new()
	body.custom_minimum_size = Vector2(330, 1400)
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var panel: PanelContainer = PanelContainer.new()
	var stack: VBoxContainer = VBoxContainer.new()
	var label: Label = Label.new()
	label.text = "Kopalnia metalu"
	label.custom_minimum_size.y = 60
	var button: Button = Button.new()
	button.text = "Ulepsz"
	button.custom_minimum_size.y = 70
	button.pressed.connect(func() -> void: taps += 1)
	stack.add_child(label)
	stack.add_child(button)
	panel.add_child(stack)
	body.add_child(panel)
	scroll.add_child(body)
	root.add_child(scroll)
	await process_frame
	await process_frame
	_expect(panel.mouse_filter == Control.MOUSE_FILTER_PASS, "Card panels pass gestures to their scroll ancestor")
	_expect(stack.mouse_filter == Control.MOUSE_FILTER_PASS, "Nested layout containers preserve bubbling")
	_expect(label.mouse_filter == Control.MOUSE_FILTER_IGNORE, "Passive labels never swallow touch")
	_expect(button.mouse_filter == Control.MOUSE_FILTER_PASS, "Drag can start on an action button")
	_expect(button.action_mode == BaseButton.ACTION_MODE_BUTTON_RELEASE, "Action waits for release so scrolling can cancel it")
	_expect(scroll.get_v_scroll_bar().mouse_filter == Control.MOUSE_FILTER_STOP, "Native scrollbar keeps its input")
	var late_panel: PanelContainer = PanelContainer.new()
	var late_button: Button = Button.new()
	late_panel.add_child(late_button)
	body.add_child(late_panel)
	_expect(late_panel.mouse_filter == Control.MOUSE_FILTER_PASS and late_button.mouse_filter == Control.MOUSE_FILTER_PASS, "Dynamically populated catalog cards receive the same fix")
	var line: LineEdit = LineEdit.new()
	var spin: SpinBox = SpinBox.new()
	var option: OptionButton = OptionButton.new()
	var line_filter: int = line.mouse_filter
	var spin_filter: int = spin.mouse_filter
	var spin_edit_filter: int = spin.get_line_edit().mouse_filter
	var option_filter: int = option.mouse_filter
	var option_mode: int = option.action_mode
	body.add_child(line)
	body.add_child(spin)
	body.add_child(option)
	_expect(line.mouse_filter == line_filter, "Text field selection and keyboard gestures are unchanged")
	_expect(spin.mouse_filter == spin_filter and spin.get_line_edit().mouse_filter == spin_edit_filter, "SpinBox and internal editor keep numeric editing")
	_expect(option.mouse_filter == option_filter and option.action_mode == option_mode, "OptionButton popup input is unchanged")
	var nested: ScrollContainer = ScrollContainer.new()
	var nested_panel: PanelContainer = PanelContainer.new()
	var nested_original_filter: int = nested_panel.mouse_filter
	nested.add_child(nested_panel)
	body.add_child(nested)
	_expect(nested_panel.mouse_filter == nested_original_filter, "Outer scroller does not rewrite a nested scroller's controls")
	await process_frame
	await process_frame
	var point: Vector2 = button.get_global_rect().get_center()
	_mouse_move(point, Vector2.ZERO)
	_mouse_button(point, true)
	_expect(taps == 0, "Button press alone does not activate")
	_mouse_button(point, false)
	_expect(taps == 1, "Stationary button tap activates exactly once")
	_mouse_move(point, Vector2.ZERO)
	_mouse_button(point, true)
	scroll.propagate_notification(Control.NOTIFICATION_SCROLL_BEGIN)
	_mouse_button(point, false)
	_expect(taps == 1, "Native scroll-begin notification cancels a pending button action")
	scroll.scroll_started.connect(func() -> void: native_begins += 1)
	if DisplayServer.is_touchscreen_available():
		for origin: Vector2 in [label.get_global_rect().get_center(), button.get_global_rect().get_center()]:
			scroll.scroll_vertical = 0
			await process_frame
			_mouse_move(origin, Vector2.ZERO)
			_mouse_button(origin, true)
			_mouse_move(origin - Vector2(0, 50), Vector2(0, -50), MOUSE_BUTTON_MASK_LEFT)
			_expect(scroll.scroll_vertical > 0, "Native touch scrolling advances when drag starts over content")
			_mouse_button(origin - Vector2(0, 50), false)
		_expect(native_begins >= 2, "Engine detects both native drag gestures")
		_expect(taps == 1, "A native drag over the action button does not purchase")
	else:
		print("Native kinetic drag not exercised: this DisplayServer has no touchscreen. Use --emulate-touchscreen with a graphical display.")
	scroll.queue_free()
	await process_frame
	await _test_map()
	print("Touch scroll: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)


func _test_map() -> void:
	var map: Control = GalaxyMap.new()
	root.add_child(map)
	map.size = Vector2(340, 370)
	map.system_selected.connect(func(_id: String) -> void: selected += 1)
	await process_frame
	var points: Array[Dictionary] = [{"position": Vector2(80, 80), "id": "aster"}]
	map.hit_points = points
	_map_touch(map, Vector2(80, 80), true, 0)
	_expect(selected == 0, "Galaxy does not select a star on touch-down")
	_map_touch(map, Vector2(80, 80), false, 0)
	_expect(selected == 1, "Galaxy selects once on a stationary release")
	_map_touch(map, Vector2(80, 80), true, 0)
	var drag: InputEventScreenDrag = InputEventScreenDrag.new()
	drag.index = 0
	drag.position = Vector2(80, 20)
	map._gui_input(drag)
	_map_touch(map, Vector2(80, 80), false, 0)
	_expect(selected == 1, "Dragging away and back never selects a galaxy target")
	_map_touch(map, Vector2(80, 80), true, 0)
	map.notification(Control.NOTIFICATION_SCROLL_BEGIN)
	_map_touch(map, Vector2(80, 80), false, 0)
	_expect(selected == 1, "Native scrolling cancels a galaxy tap")
	_map_touch(map, Vector2(80, 80), true, 0)
	_map_touch(map, Vector2(80, 80), true, 1)
	_map_touch(map, Vector2(80, 80), false, 1)
	_expect(selected == 1, "A second finger cannot release the first finger's galaxy tap")
	_map_touch(map, Vector2(80, 80), false, 0)
	_expect(selected == 2, "Original finger retains its own tap")
	var emulated: InputEventMouseButton = InputEventMouseButton.new()
	emulated.device = -1
	emulated.position = Vector2(80, 80)
	emulated.button_index = MOUSE_BUTTON_LEFT
	emulated.pressed = true
	map._gui_input(emulated)
	emulated.pressed = false
	map._gui_input(emulated)
	_expect(selected == 2, "Touch-emulated mouse does not duplicate galaxy activation")
	map.queue_free()
	await process_frame


func _map_touch(map: Control, point: Vector2, down: bool, index: int) -> void:
	var event: InputEventScreenTouch = InputEventScreenTouch.new()
	event.position = point
	event.pressed = down
	event.index = index
	map._gui_input(event)


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
