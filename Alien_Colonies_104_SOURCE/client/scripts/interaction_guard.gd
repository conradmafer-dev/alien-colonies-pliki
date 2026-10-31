extends Node
## Delay server-driven layout changes while a real input gesture is in progress.
## Godot's buttons/ScrollContainer still decide which releases are clicks.
## Interrupted contacts must also release the engine's touch-to-mouse owner;
## otherwise one lost Android UP prevents every native scroller from starting.

const RELEASE_GRACE_MSEC: int = 120
const INTERRUPTED_FRAME_MSEC: int = 2000
var touches: Dictionary = {}
var activation_keys: Dictionary = {}
var mouse_down: bool = false
var quiet_until_msec: int = 0
var last_frame_msec: int = 0
var mouse_position: Vector2 = Vector2.ZERO
var _recovering: bool = false
var idle_refreshes: Dictionary = {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("state_refresh_guards")
	last_frame_msec = Time.get_ticks_msec()


func scroll_motion() -> void:
	# Native inertia continues after UP. Keep a snapshot queued until the
	# scrollbars have stopped, including wheel/keyboard/programmatic movement.
	quiet_until_msec = maxi(quiet_until_msec, Time.get_ticks_msec() + 180)


func _process(_delta: float) -> void:
	var now: int = Time.get_ticks_msec()
	if _frame_interrupted(now):
		cancel_interaction()
	last_frame_msec = now
	if not busy() and not idle_refreshes.is_empty():
		# Read-only panels share the same input barrier. Deliver at most one
		# pending rebuild per frame instead of rebuilding chat/ranking together.
		var key: String = str(idle_refreshes.keys()[0])
		var refresh: Callable = idle_refreshes[key]
		idle_refreshes.erase(key)
		if refresh.is_valid():
			refresh.call()


func defer_refresh(key: String, refresh: Callable) -> bool:
	if not busy():
		idle_refreshes.erase(key)
		return false
	idle_refreshes[key] = refresh
	return true


func _input(event: InputEvent) -> void:
	if _recovering:
		observe(event)
		return
	var stalled: bool = _frame_interrupted(Time.get_ticks_msec()) and (mouse_down or not touches.is_empty())
	if event is InputEventScreenTouch and event.pressed and not event.canceled and event.device != -1:
		if touches.has(event.index) or stalled:
			# DOWN for an already-held index proves that its old UP was lost.
			# Cancel the stale contact, then route this actual new DOWN once so
			# Godot can generate its missing mouse press for native scrolling.
			_recover_press(event)
			return
	if stalled:
		# The native emulated mouse DOWN arrives just before its ScreenTouch.
		# Let the source touch above recover both together, with its real index.
		if event is InputEventMouseButton and event.device == -1 and event.pressed:
			observe(event)
			return
		if event is InputEventMouseButton and event.device != -1 and event.pressed:
			_recover_press(event)
			return
		cancel_interaction()
		# A delayed UP must never activate the control held before the stall.
		if event is InputEventMouseButton or event is InputEventScreenTouch or event is InputEventScreenDrag or event is InputEventMouseMotion:
			get_viewport().set_input_as_handled()
			return
	observe(event)


func observe(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed and not event.canceled:
			touches[event.index] = event.position
		else:
			touches.erase(event.index)
			quiet_until_msec = Time.get_ticks_msec() + RELEASE_GRACE_MSEC
	elif event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			mouse_position = event.position
			mouse_down = event.pressed and not event.canceled
			if not mouse_down:
				quiet_until_msec = Time.get_ticks_msec() + RELEASE_GRACE_MSEC
		elif event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			quiet_until_msec = Time.get_ticks_msec() + RELEASE_GRACE_MSEC
	elif event is InputEventScreenDrag and touches.has(event.index):
		touches[event.index] = event.position
	elif event is InputEventMouseMotion:
		mouse_position = event.position
	elif event is InputEventKey and event.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		if event.pressed:
			activation_keys[event.keycode] = true
		else:
			activation_keys.erase(event.keycode)
			quiet_until_msec = Time.get_ticks_msec() + RELEASE_GRACE_MSEC


func busy() -> bool:
	return mouse_down or not touches.is_empty() or not activation_keys.is_empty() or Time.get_ticks_msec() < quiet_until_msec


func reset() -> void:
	touches.clear()
	activation_keys.clear()
	mouse_down = false
	quiet_until_msec = 0
	last_frame_msec = Time.get_ticks_msec()


func _frame_interrupted(now: int) -> bool:
	# This measures a gap between processed frames, never the age of a hold.
	return last_frame_msec > 0 and now - last_frame_msec > INTERRUPTED_FRAME_MSEC


func cancel_interaction(extra_touch: InputEventScreenTouch = null) -> void:
	if _recovering:
		return
	_recovering = true
	var interrupted: Dictionary = touches.duplicate()
	if extra_touch != null:
		interrupted[extra_touch.index] = extra_touch.position
	var had_mouse: bool = mouse_down
	reset()
	# Cancel pending actions before releases, including custom catalog cards.
	if is_inside_tree():
		get_parent().propagate_notification(Control.NOTIFICATION_SCROLL_BEGIN)
		get_tree().call_group("touch_scroll_surfaces", "cancel_gesture")
	# Dispatch in order immediately, ahead of any already-buffered UP/DOWN.
	# This project keeps Godot's default agile_event_flushing=false.
	var accumulated: bool = Input.use_accumulated_input
	Input.use_accumulated_input = false
	for index: Variant in interrupted:
		var released: InputEventScreenTouch = InputEventScreenTouch.new()
		released.index = int(index)
		released.position = interrupted[index]
		released.pressed = false
		released.canceled = true
		Input.parse_input_event(_window_event(released))
	if had_mouse:
		var released: InputEventMouseButton = InputEventMouseButton.new()
		released.position = mouse_position
		released.global_position = mouse_position
		released.button_index = MOUSE_BUTTON_LEFT
		released.pressed = false
		released.canceled = true
		Input.parse_input_event(_window_event(released))
	Input.use_accumulated_input = accumulated
	if is_inside_tree():
		get_parent().propagate_notification(Control.NOTIFICATION_SCROLL_END)
	reset()
	_recovering = false


func _recover_press(event: InputEvent) -> void:
	cancel_interaction(event as InputEventScreenTouch)
	_recovering = true
	var accumulated: bool = Input.use_accumulated_input
	Input.use_accumulated_input = false
	Input.parse_input_event(_window_event(event))
	Input.use_accumulated_input = accumulated
	_recovering = false
	# The nested event was delivered normally; suppress only its outer original.
	get_viewport().set_input_as_handled()


func _window_event(event: InputEvent) -> InputEvent:
	# _input receives viewport coordinates after canvas stretch. Input parses
	# physical window coordinates, so undo that localization exactly once.
	var transform: Transform2D = get_viewport().get_final_transform() if is_inside_tree() else Transform2D.IDENTITY
	var result: InputEvent = event.xformed_by(transform)
	if result is InputEventMouse:
		result.global_position = result.position
	return result


func _notification(what: int) -> void:
	if what in [NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_APPLICATION_FOCUS_IN, NOTIFICATION_APPLICATION_RESUMED]:
		cancel_interaction()
