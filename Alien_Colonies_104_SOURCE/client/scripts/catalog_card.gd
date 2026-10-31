extends PanelContainer
## The passive surface of a catalog card is a details button. Native action and
## quantity controls retain their own input; scrolling never opens the dialog.
signal details_requested

var excluded_controls: Array = []
var pressed_pointer: int = -2
var press_position: Vector2
var motion_distance: float = 0.0
const DRAG_THRESHOLD: float = 12.0

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_PASS
	focus_mode = Control.FOCUS_ALL
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	set_process_input(false)

func _excluded(local_point: Vector2) -> bool:
	var global_point: Vector2 = get_global_transform() * local_point
	for node in excluded_controls:
		if is_instance_valid(node) and node.is_visible_in_tree() and node.get_global_rect().has_point(global_point):
			return true
	return false

func _cancel_press() -> void:
	pressed_pointer = -2
	set_process_input(false)

func _notification(what: int) -> void:
	if what in [NOTIFICATION_SCROLL_BEGIN, NOTIFICATION_VISIBILITY_CHANGED, NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED]:
		_cancel_press()

func _input(event: InputEvent) -> void:
	if pressed_pointer == -2:
		return
	if event is InputEventMouseMotion and pressed_pointer == -1:
		motion_distance += event.relative.length()
	elif event is InputEventScreenDrag and pressed_pointer == event.index:
		motion_distance += event.relative.length()
	elif event is InputEventScreenTouch and event.pressed and ((pressed_pointer >= 0 and pressed_pointer != event.index) or (pressed_pointer == -1 and event.index > 0)):
		_cancel_press()
	if motion_distance > DRAG_THRESHOLD:
		_cancel_press()

func _gui_input(event: InputEvent) -> void:
	var canceled: bool = false
	if event is InputEventScreenTouch:
		canceled = event.canceled
	elif event is InputEventMouseButton:
		canceled = event.canceled
	if canceled:
		_cancel_press()
		return
	if event is InputEventKey and has_focus() and event.pressed and not event.echo and event.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		accept_event()
		details_requested.emit()
		return
	var pointer: int = -2
	var down: bool = false
	var point: Vector2
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		pointer = -1
		down = event.pressed
		point = event.position
	elif event is InputEventScreenTouch:
		pointer = event.index
		down = event.pressed
		point = event.position
	else:
		return
	if down:
		if pressed_pointer == -2 and not _excluded(point):
			pressed_pointer = pointer
			press_position = point
			motion_distance = 0.0
			set_process_input(true)
		# Leave the press unhandled: the parent ScrollContainer owns drags.
	elif pressed_pointer == pointer:
		var valid_tap: bool = point.distance_to(press_position) <= DRAG_THRESHOLD and Rect2(Vector2.ZERO, size).has_point(point) and not _excluded(point)
		_cancel_press()
		if valid_tap:
			accept_event()
			details_requested.emit()
