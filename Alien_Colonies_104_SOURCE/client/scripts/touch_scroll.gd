extends ScrollContainer
## Native dragging, focus and button cancellation; time-sampled release momentum.
## The native ScrollContainer must receive events through every passive ancestor:
## STOP on a card/button makes dragging work only in the gaps between controls.
## Taps, keyboard input and multiple fingers remain owned by the engine.
## Editors and popups retain their own gestures.

## Enabled only by horizontal catalogs with vertically scrolling card content.
## Observe the same mouse stream that Godot uses for native touch scrolling;
## processing ScreenDrag as well would count the emulated contact twice.
var lock_nested_scroll_axis: bool = false
var _axis_contact: bool = false
var _axis_device: int = 0
var _axis_motion: Vector2 = Vector2.ZERO
var _locked_axis: int = -1
var _axis_surfaces: Array[ScrollContainer] = []

const MOTION_WINDOW_USEC: int = 100000
const MIN_MOTION_SECONDS: float = 0.04
const RELEASE_PAUSE_USEC: int = 100000
const MIN_FLING_DISTANCE: float = 14.0
const MIN_FLING_SPEED: float = 80.0
const STOP_SPEED: float = 8.0
const MOMENTUM_DECAY: float = 4.2
const MAX_VIEWPORTS_PER_SECOND: float = 5.0
const MAX_COAST_TO_GESTURE: float = 5.625
var _kinetic_contact: bool = false
var _kinetic_device: int = 0
var _native_scrolled: bool = false
var _motion_position: Vector2 = Vector2.ZERO
var _last_motion: Vector2 = Vector2.ZERO
var _last_motion_usec: int = 0
var _motion_points: Array[Vector2] = []
var _motion_times: Array[int] = []
var _kinetic_velocity: Vector2 = Vector2.ZERO
var _kinetic_position: Vector2 = Vector2.ZERO
var _applying_kinetic: bool = false


func _ready() -> void:
	scroll_deadzone = 12
	add_to_group("touch_scroll_surfaces")
	get_h_scroll_bar().value_changed.connect(_scroll_moved)
	get_v_scroll_bar().value_changed.connect(_scroll_moved)
	scroll_started.connect(_native_drag_started)
	set_process_input(true)
	set_process(false)
	_watch_branch(self)


func _scroll_moved(_value: float) -> void:
	if not _applying_kinetic and not _kinetic_velocity.is_zero_approx():
		# A wheel, scrollbar, keyboard or explicit jump takes over immediately.
		_kinetic_velocity = Vector2.ZERO
		set_process(false)
	if is_visible_in_tree():
		get_tree().call_group("state_refresh_guards", "scroll_motion")


func _gui_input(event: InputEvent) -> void:
	if not DisplayServer.is_touchscreen_available():
		return
	# Start only after the actual GUI target has passed its press to this
	# scroller. An editor, popup or scrollbar above it keeps its own input.
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed and not event.canceled:
		_begin_kinetic_contact(event.device)
		if lock_nested_scroll_axis:
			_axis_contact = true
			_axis_device = event.device
			_axis_motion = Vector2.ZERO
			_locked_axis = -1
			_axis_surfaces = _related_scroll_surfaces()


func _input(event: InputEvent) -> void:
	_observe_kinetic_input(event)
	if not lock_nested_scroll_axis:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed and not event.canceled:
			_reset_axis_lock()
			if is_visible_in_tree() and get_global_rect().has_point(event.position):
				# Stop old inertia before GUI delivery starts the new native
				# contact in the inner and outer scrollers. Doing this in
				# _gui_input would already cancel the inner scroller's DOWN.
				for surface: ScrollContainer in _related_scroll_surfaces():
					_stop_native_drag(surface)
		elif _axis_contact and event.device == _axis_device:
			if event.canceled:
				cancel_gesture()
			else:
				# The winner still receives UP normally and keeps its inertia.
				_reset_axis_lock()
	elif event is InputEventMouseMotion and _axis_contact and event.device == _axis_device and _locked_axis < 0:
		_axis_motion += event.relative
		if maxf(absf(_axis_motion.x), absf(_axis_motion.y)) <= scroll_deadzone:
			return
		_locked_axis = Vector2.AXIS_X if absf(_axis_motion.x) > absf(_axis_motion.y) else Vector2.AXIS_Y
		# Cancel the losing native contacts BEFORE this motion reaches GUI
		# handlers. The chosen direction lasts until UP, even when the finger
		# curves, reverses or reaches the end of a card. No layout modes change.
		for surface: ScrollContainer in _axis_surfaces:
			if not is_instance_valid(surface):
				continue
			var loses_axis: bool = surface.vertical_scroll_mode != SCROLL_MODE_DISABLED if _locked_axis == Vector2.AXIS_X else surface.horizontal_scroll_mode != SCROLL_MODE_DISABLED
			if loses_axis:
				_stop_native_drag(surface)


func _related_scroll_surfaces() -> Array[ScrollContainer]:
	var surfaces: Array[ScrollContainer] = [self]
	for node: Node in find_children("*", "ScrollContainer", true, false):
		surfaces.append(node as ScrollContainer)
	var ancestor: Node = get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			surfaces.append(ancestor as ScrollContainer)
		ancestor = ancestor.get_parent()
	return surfaces


func _stop_native_drag(surface: ScrollContainer) -> void:
	if is_instance_valid(surface):
		if surface.has_method("_cancel_kinetic_motion"):
			surface._cancel_kinetic_motion()
		# Godot 4.5.1's setter calls _cancel_drag even when unchanged.
		var position: Vector2 = Vector2(surface.get_h_scroll_bar().value, surface.get_v_scroll_bar().value)
		surface.scroll_vertical = surface.scroll_vertical
		surface.get_h_scroll_bar().value = position.x
		surface.get_v_scroll_bar().value = position.y


func _reset_axis_lock() -> void:
	_axis_contact = false
	_axis_device = 0
	_axis_motion = Vector2.ZERO
	_locked_axis = -1
	_axis_surfaces.clear()


func cancel_gesture() -> void:
	# The native setter calls ScrollContainer::_cancel_drag even if unchanged.
	# Keep position, stop inertia and release a touch interrupted by an overlay.
	for surface: ScrollContainer in _axis_surfaces:
		_stop_native_drag(surface)
	_reset_axis_lock()
	_stop_native_drag(self)
	propagate_notification(Control.NOTIFICATION_SCROLL_BEGIN)
	propagate_notification(Control.NOTIFICATION_SCROLL_END)


func _clock_usec() -> int:
	return Time.get_ticks_usec()


func _begin_kinetic_contact(device: int) -> void:
	_cancel_kinetic_motion()
	_kinetic_contact = true
	_kinetic_device = device
	_motion_points.append(Vector2.ZERO)
	_motion_times.append(_clock_usec())


func _native_drag_started() -> void:
	if _kinetic_contact:
		_native_scrolled = true


func _observe_kinetic_input(event: InputEvent) -> void:
	if not DisplayServer.is_touchscreen_available():
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			# A new touch anywhere stops a previous fling, even on a header.
			if not _kinetic_velocity.is_zero_approx():
				_stop_native_drag(self)
		elif _kinetic_contact and event.device == _kinetic_device:
			if event.canceled:
				_cancel_kinetic_motion()
			elif _native_scrolled:
				var release_velocity: Vector2 = _release_velocity(_clock_usec())
				# Cancel the native frame-delta estimate before GUI receives UP.
				# Native scroll-begin has already cancelled pending button clicks.
				_stop_native_drag(self)
				_kinetic_position = Vector2(get_h_scroll_bar().value, get_v_scroll_bar().value)
				_kinetic_velocity = release_velocity
				set_process(not _kinetic_velocity.is_zero_approx())
			else:
				_cancel_kinetic_motion()
	elif event is InputEventMouseMotion and _kinetic_contact and event.device == _kinetic_device:
		_sample_motion(-event.relative, _clock_usec())


func _sample_motion(motion: Vector2, now: int) -> void:
	if horizontal_scroll_mode == SCROLL_MODE_DISABLED:
		motion.x = 0.0
	if vertical_scroll_mode == SCROLL_MODE_DISABLED:
		motion.y = 0.0
	if motion.is_zero_approx():
		return
	if motion.dot(_last_motion) < 0.0 and motion.length() >= 1.0:
		# Releasing after a reversal follows the new direction, never the old fling.
		_motion_points = [_motion_position]
		_motion_times = [_last_motion_usec if _last_motion_usec > 0 else now]
	_motion_position += motion
	_last_motion = motion
	_last_motion_usec = now
	if not _motion_times.is_empty() and now == _motion_times.back():
		_motion_points[_motion_points.size() - 1] = _motion_position
	else:
		_motion_points.append(_motion_position)
		_motion_times.append(now)
	_prune_motion_history(now)


func _prune_motion_history(now: int) -> void:
	while _motion_times.size() > 2 and _motion_times[1] < now - MOTION_WINDOW_USEC:
		_motion_times.pop_front()
		_motion_points.pop_front()


func _release_velocity(now: int) -> Vector2:
	if _motion_times.is_empty() or _last_motion_usec <= 0 or now - _last_motion_usec >= RELEASE_PAUSE_USEC:
		return Vector2.ZERO
	_prune_motion_history(now)
	var distance: Vector2 = _motion_position - _motion_points[0]
	if distance.length() < MIN_FLING_DISTANCE:
		return Vector2.ZERO
	var elapsed: float = maxf(MIN_MOTION_SECONDS, float(now - _motion_times[0]) / 1000000.0)
	var velocity: Vector2 = distance / elapsed
	for axis: int in range(2):
		var page: float = get_h_scroll_bar().page if axis == Vector2.AXIS_X else get_v_scroll_bar().page
		var limit: float = minf(maxf(1.0, page) * MAX_VIEWPORTS_PER_SECOND,
			absf(distance[axis]) * MOMENTUM_DECAY * MAX_COAST_TO_GESTURE)
		velocity[axis] = clampf(velocity[axis], -limit, limit)
		if absf(velocity[axis]) < MIN_FLING_SPEED:
			velocity[axis] = 0.0
	return velocity


func _process(delta: float) -> void:
	if _kinetic_velocity.is_zero_approx():
		set_process(false)
		return
	# Integrate exponential slowing analytically. The distance is independent of
	# refresh rate; no displacement is divided by the duration of a render frame.
	var decay: float = exp(-MOMENTUM_DECAY * maxf(0.0, delta))
	_kinetic_position += _kinetic_velocity * ((1.0 - decay) / MOMENTUM_DECAY)
	_kinetic_velocity *= decay
	_applying_kinetic = true
	for axis: int in range(2):
		var bar: ScrollBar = get_h_scroll_bar() if axis == Vector2.AXIS_X else get_v_scroll_bar()
		if (axis == Vector2.AXIS_X and horizontal_scroll_mode == SCROLL_MODE_DISABLED) or (axis == Vector2.AXIS_Y and vertical_scroll_mode == SCROLL_MODE_DISABLED):
			_kinetic_velocity[axis] = 0.0
			_kinetic_position[axis] = bar.value
			continue
		var limit: float = maxf(0.0, bar.max_value - bar.page)
		var bounded: float = clampf(_kinetic_position[axis], 0.0, limit)
		if not is_equal_approx(bounded, _kinetic_position[axis]) or absf(_kinetic_velocity[axis]) < STOP_SPEED:
			_kinetic_velocity[axis] = 0.0
		_kinetic_position[axis] = bounded
		bar.value = bounded
	_applying_kinetic = false
	if _kinetic_velocity.is_zero_approx():
		set_process(false)


func _cancel_kinetic_motion() -> void:
	_kinetic_contact = false
	_native_scrolled = false
	_motion_position = Vector2.ZERO
	_last_motion = Vector2.ZERO
	_last_motion_usec = 0
	_motion_points.clear()
	_motion_times.clear()
	_kinetic_velocity = Vector2.ZERO
	set_process(false)


func _notification(what: int) -> void:
	if not is_node_ready():
		return
	if what in [NOTIFICATION_DISABLED, NOTIFICATION_PAUSED, NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED]:
		cancel_gesture()
	elif what == NOTIFICATION_VISIBILITY_CHANGED and not is_visible_in_tree():
		cancel_gesture()


func _watch_branch(node: Node) -> void:
	if node != self and _owns_input(node):
		return
	_prepare_control(node)
	if not node.child_entered_tree.is_connected(_watch_branch):
		node.child_entered_tree.connect(_watch_branch)
	# A custom node may set its filter in _ready(), after child_entered_tree.
	if node != self and not node.is_node_ready():
		var after_ready: Callable = _prepare_control.bind(node)
		if not node.ready.is_connected(after_ready):
			node.ready.connect(after_ready, CONNECT_ONE_SHOT)
	for child: Node in node.get_children():
		_watch_branch(child)


func _owns_input(node: Node) -> bool:
	return node is ScrollContainer or node is Window or node is SubViewport \
		or node is LineEdit or node is TextEdit or node is SpinBox \
		or node is OptionButton or node is MenuButton or node is ColorPickerButton \
		or node is Slider or node is ScrollBar or node is Tree or node is ItemList \
		or bool(node.get_meta("touch_scroll_preserve_input", false))


func _prepare_control(node: Node) -> void:
	if not is_instance_valid(node) or node == self or _owns_input(node):
		return
	if node is Label or node is TextureRect or node is ColorRect or node is ProgressBar:
		(node as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
	elif node is Container or node is Panel:
		(node as Control).mouse_filter = Control.MOUSE_FILTER_PASS
	elif node is BaseButton:
		var button: BaseButton = node as BaseButton
		button.mouse_filter = Control.MOUSE_FILTER_PASS
		# Native NOTIFICATION_SCROLL_BEGIN cancels a pending release action.
		# Actions on press cannot be undone once a finger starts moving.
		button.action_mode = BaseButton.ACTION_MODE_BUTTON_RELEASE
	elif node is Control and node.get_class() == "Control" and node.get_script() == null:
		(node as Control).mouse_filter = Control.MOUSE_FILTER_PASS
