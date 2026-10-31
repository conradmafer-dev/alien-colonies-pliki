extends SceneTree
## godot --headless --path . --script tests/test_mobile_quantity.gd
## Native button drag cancellation is simulated using the engine notification.

const MobileQuantity = preload("res://client/scripts/mobile_quantity.gd")
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")

var checks: int = 0
var failures: int = 0
var changes: Array[float] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var quantity: MobileQuantity = MobileQuantity.new()
	quantity.min_value = 0
	quantity.max_value = 999999
	var theme_value: Theme = Theme.new()
	var field_style: StyleBoxFlat = StyleBoxFlat.new()
	field_style.content_margin_left = 14
	field_style.content_margin_right = 14
	theme_value.set_stylebox("normal", "LineEdit", field_style)
	theme_value.default_font_size = 26
	quantity.theme = theme_value
	quantity.value_changed.connect(func(next: float) -> void: changes.append(next))
	root.add_child(quantity)
	await process_frame
	await process_frame
	_expect(quantity.get_combined_minimum_size().x <= 250, "Counter fits a dedicated narrow phone row")
	for button: Button in [quantity.minus_button, quantity.plus_button]:
		_expect(button.size.x >= 72 and button.size.y >= 76, "Both quantity buttons have full finger-sized targets")
		_expect(button.mouse_filter == Control.MOUSE_FILTER_PASS, "A quantity button passes a drag to the page")
		_expect(button.action_mode == BaseButton.ACTION_MODE_BUTTON_RELEASE, "Quantity changes wait until release")
	_expect(quantity.editor.virtual_keyboard_type == LineEdit.KEYBOARD_TYPE_NUMBER, "Typing uses the numeric keyboard")
	_expect(quantity.editor.mouse_filter == Control.MOUSE_FILTER_IGNORE, "Editor leaves pointer handling to its tap gate while keeping keyboard input")
	_expect(quantity.minus_button.disabled and not quantity.plus_button.disabled, "Lower bound disables decrement only")
	quantity.plus_button.pressed.emit()
	quantity.plus_button.pressed.emit()
	quantity.minus_button.pressed.emit()
	_expect(quantity.value == 1 and changes == [1.0, 2.0, 1.0], "Each button activation changes the value once")
	var previous_count: int = changes.size()
	quantity.value = quantity.value
	quantity.apply()
	_expect(changes.size() == previous_count, "Repeated assignment and apply do not emit duplicate events")
	quantity.editor.text = "  124  "
	quantity.apply()
	_expect(quantity.value == 124 and quantity.editor.text == "124", "Manual integer input commits without whitespace")
	quantity.editor.text = "999999999999999999"
	quantity.apply()
	_expect(quantity.value == 999999 and quantity.editor.text == "999999", "Large pasted quantities clamp safely without integer overflow")
	await process_frame
	await process_frame
	var text_width: float = quantity.editor.get_theme_font("font").get_string_size(quantity.editor.text, HORIZONTAL_ALIGNMENT_LEFT, -1, quantity.editor.get_theme_font_size("font_size")).x
	var inner_width: float = quantity.editor.size.x - quantity.editor.get_theme_stylebox("normal").get_minimum_size().x
	_expect(text_width <= inner_width, "All six cargo digits fit in the smallest editor using the game's padded field theme")
	_expect(quantity.plus_button.disabled and not quantity.minus_button.disabled, "Upper bound disables increment only")
	quantity.editor.text = "-25"
	quantity.apply()
	_expect(quantity.value == 0 and quantity.editor.text == "0", "Negative cargo clamps to the minimum")
	for invalid: String in ["", " ", "abc", "NaN", "Inf", "1.5", "1e3", "2+2"]:
		quantity.value = 42
		previous_count = changes.size()
		quantity.editor.text = invalid
		quantity.apply()
		_expect(quantity.value == 42 and quantity.editor.text == "42" and changes.size() == previous_count, "Invalid edit '%s' restores the previous value without an event" % invalid)
	quantity.editor.text = "12"
	previous_count = changes.size()
	quantity.plus_button.pressed.emit()
	_expect(quantity.value == 13 and changes.size() == previous_count + 1, "Increment commits an unsubmitted edit and step with one signal")
	quantity.value = 50
	previous_count = changes.size()
	quantity.max_value = 10
	_expect(quantity.value == 10 and changes.size() == previous_count + 1, "Reducing the maximum clamps once")
	quantity.min_value = 20
	_expect(quantity.min_value == 20 and quantity.max_value == 20 and quantity.value == 20, "Raising minimum above maximum creates a valid single-value range")
	quantity.max_value = 5
	_expect(quantity.min_value == 5 and quantity.max_value == 5 and quantity.value == 5, "Lowering maximum below minimum keeps bounds ordered")
	_expect(quantity.minus_button.disabled and quantity.plus_button.disabled, "Single-value range disables both buttons")
	quantity.min_value = 0.2
	quantity.max_value = 8.9
	quantity.value = 3.8
	_expect(quantity.min_value == 1 and quantity.max_value == 8 and quantity.value == 4, "Public numeric properties keep integer quantities inside integer bounds")
	previous_count = changes.size()
	for invalid: float in [NAN, INF, -INF]:
		quantity.value = invalid
		quantity.min_value = invalid
		quantity.max_value = invalid
	_expect(quantity.min_value == 1 and quantity.max_value == 8 and quantity.value == 4 and changes.size() == previous_count, "Non-finite values never poison the numeric range or emit changes")
	quantity.step = 0
	_expect(quantity.step == 1, "Zero step retains an effective increment")
	quantity.step = -2
	quantity.plus_button.pressed.emit()
	_expect(quantity.step == 2 and quantity.value == 6, "Negative step is normalized to a positive integer")
	quantity.step = INF
	_expect(quantity.step == 1, "Non-finite step falls back to one")
	quantity.queue_free()
	await process_frame
	await _test_scroll_cancellation()
	print("Mobile quantity: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)


func _test_scroll_cancellation() -> void:
	var scroll: ScrollContainer = TouchScroll.new()
	scroll.position = Vector2(10, 10)
	scroll.size = Vector2(350, 300)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var body: VBoxContainer = VBoxContainer.new()
	body.custom_minimum_size = Vector2(330, 1300)
	var quantity: MobileQuantity = MobileQuantity.new()
	body.add_child(quantity)
	scroll.add_child(body)
	root.add_child(scroll)
	await process_frame
	await process_frame
	_expect(quantity.mouse_filter == Control.MOUSE_FILTER_PASS, "Native page scroll reaches through the quantity row")
	_expect(quantity.editor.mouse_filter == Control.MOUSE_FILTER_IGNORE, "Scroll setup preserves tap-versus-drag routing on quantity input")
	var point: Vector2 = quantity.plus_button.get_global_rect().get_center()
	_mouse_move(point)
	_mouse_button(point, true)
	_expect(quantity.value == 0, "Finger-down does not increment")
	_mouse_button(point, false)
	_expect(quantity.value == 1, "Stationary tap increments once")
	_mouse_move(point)
	_mouse_button(point, true)
	scroll.propagate_notification(Control.NOTIFICATION_SCROLL_BEGIN)
	_mouse_button(point, false)
	_expect(quantity.value == 1, "Starting a native scroll cancels a held quantity button")
	quantity.editor.text = "7"
	quantity.apply()
	quantity.editor.text_submitted.emit("7")
	quantity.editor.focus_exited.emit()
	_expect(quantity.value == 7, "Repeated submission and focus exit preserve the chosen quantity")
	scroll.queue_free()
	await process_frame


func _mouse_button(point: Vector2, down: bool) -> void:
	var event: InputEventMouseButton = InputEventMouseButton.new()
	event.position = point
	event.global_position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if down else 0
	event.pressed = down
	root.push_input(event, true)


func _mouse_move(point: Vector2) -> void:
	var event: InputEventMouseMotion = InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	root.push_input(event, true)


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
