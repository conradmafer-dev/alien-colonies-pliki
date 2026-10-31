extends Button
## A number is edited on a completed tap, never on finger-down. The native
## release button passes the original gesture to the ancestor ScrollContainer,
## whose NOTIFICATION_SCROLL_BEGIN cancels its pending activation.
## LineEdit remains keyboard-focusable but receives no pointer-selection drags.

signal edit_requested

var _touches: Dictionary = {}
var _touch_sequence_canceled: bool = false
var _tap_canceled: bool = false


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_PASS
	focus_mode = Control.FOCUS_NONE
	action_mode = BaseButton.ACTION_MODE_BUTTON_RELEASE
	mouse_default_cursor_shape = Control.CURSOR_IBEAM
	tooltip_text = I18n.t("Dotknij, aby wpisać ilość")
	# Keep the LineEdit's own racial theme, text and focus outline visible.
	for kind: String in ["normal", "hover", "pressed", "disabled", "focus", "hover_pressed"]:
		add_theme_stylebox_override(kind, StyleBoxEmpty.new())
	button_down.connect(_begin_tap)
	pressed.connect(_complete_tap)


func _input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
	if event is InputEventScreenTouch:
		var touch: InputEventScreenTouch = event as InputEventScreenTouch
		if touch.pressed:
			if _touches.is_empty():
				_touch_sequence_canceled = false
			_touches[touch.index] = true
			if _touches.size() > 1:
				_touch_sequence_canceled = true
				_cancel_tap()
		else:
			if touch.canceled:
				_touch_sequence_canceled = true
				_cancel_tap()
			_touches.erase(touch.index)
	elif event is InputEventMouseButton:
		# Godot dispatches its emulated mouse release before the source touch.
		# Inspect canceled here as well, before BaseButton can emit pressed.
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index == MOUSE_BUTTON_LEFT and mouse.canceled:
			_cancel_tap()
	# Observe only: no accept_event(), handled flag or synthetic input replay.


func _notification(what: int) -> void:
	if what == Control.NOTIFICATION_SCROLL_BEGIN or what == Control.NOTIFICATION_DRAG_BEGIN:
		_tap_canceled = true
	elif what == NOTIFICATION_VISIBILITY_CHANGED and not is_visible_in_tree():
		_touches.clear()
		_touch_sequence_canceled = false
		_tap_canceled = true
	elif what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_touches.clear()
		_touch_sequence_canceled = false
		_cancel_tap()


func _begin_tap() -> void:
	_tap_canceled = _touches.size() > 1 or (_touch_sequence_canceled and not _touches.is_empty())


func _cancel_tap() -> void:
	_tap_canceled = true
	# The same native cancellation path used by ScrollContainer. This changes
	# only this button's pending action and does not consume the input gesture.
	notification(Control.NOTIFICATION_SCROLL_BEGIN)


func _complete_tap() -> void:
	if not _tap_canceled and is_visible_in_tree():
		edit_requested.emit()


func _ready() -> void:
	I18n.language_changed.connect(_refresh_language)


func _refresh_language() -> void:
	tooltip_text = I18n.t("Dotknij, aby wpisać ilość")
