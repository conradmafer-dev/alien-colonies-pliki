extends SceneTree
# Focused real-renderer regression: native touchscreen drag through free lane
# directly over Fleet number editors. Never contacts or mutates a live server.
const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
var client: MobileSmoke.OfflineClient
var checks: int = 0
var failures: int = 0
var screenshot_directory: String = ""
var edit_starts: int = 0

func _initialize() -> void:
	_run.call_deferred()

func _expect(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		push_error(message)

func _settle() -> void:
	for i: int in range(8):
		await process_frame

func _mouse(point: Vector2, down: bool) -> void:
	var ev := InputEventMouseButton.new()
	ev.position = point
	ev.global_position = point
	ev.button_index = MOUSE_BUTTON_LEFT
	ev.button_mask = MOUSE_BUTTON_MASK_LEFT if down else 0
	ev.pressed = down
	root.push_input(ev, true)

func _motion(point: Vector2, relative: Vector2, mask: int = 0) -> void:
	var ev := InputEventMouseMotion.new()
	ev.position = point
	ev.global_position = point
	ev.relative = relative
	ev.button_mask = mask
	root.push_input(ev, true)

func _tap(point: Vector2) -> void:
	_motion(point, Vector2.ZERO)
	_mouse(point, true)
	await process_frame
	_mouse(point, false)
	await _settle()

func _swipe(point: Vector2, distance: float = 96) -> void:
	_motion(point, Vector2.ZERO)
	_mouse(point, true)
	for i: int in range(1, 7):
		_motion(point - Vector2(0, distance * i / 6.0), Vector2(0, -distance / 6.0), MOUSE_BUTTON_MASK_LEFT)
		await process_frame
	_mouse(point - Vector2(0, distance), false)
	await _settle()

func _amounts() -> Array[float]:
	var result: Array[float] = []
	for amount in client.fleet_inputs.values():
		result.append(amount.value)
	for amount in client.cargo_inputs.values():
		result.append(amount.value)
	for row in client.ship_rows.values():
		result.append(row.amount.value)
	return result

func _center_amount(amount: Control) -> void:
	var scroll: ScrollContainer = client.tabs[2]
	scroll.scroll_vertical += roundi(amount.get_global_rect().get_center().y - scroll.get_global_rect().get_center().y)
	await _settle()

func _check_amount(amount: Control, label_value: String) -> void:
	var scroll: ScrollContainer = client.tabs[2]
	amount.editor.unedit()
	amount.editor.release_focus()
	await _center_amount(amount)
	var origin: Vector2 = amount.editor.get_global_rect().get_center()
	_expect(scroll.get_global_rect().has_point(origin), label_value + ": gesture starts directly over a visible number")
	var prior: Array[float] = _amounts()
	var before_edits: int = edit_starts
	var before: int = scroll.scroll_vertical
	var bar: VScrollBar = scroll.get_v_scroll_bar()
	var distance: float = -96.0 if before >= int(bar.max_value - bar.page) - 20 else 96.0
	_motion(origin, Vector2.ZERO)
	_mouse(origin, true)
	await process_frame
	_expect(not amount.editor.has_focus() and not amount.editor.is_editing(), label_value + ": finger-down does not focus or begin typing")
	for i: int in range(1, 7):
		_motion(origin - Vector2(0, distance * i / 6.0), Vector2(0, -distance / 6.0), MOUSE_BUTTON_MASK_LEFT)
		await process_frame
	_mouse(origin - Vector2(0, distance), false)
	await _settle()
	_expect(abs(scroll.scroll_vertical - before) > 20, label_value + ": native drag on number scrolls the page")
	_expect(edit_starts == before_edits and not amount.editor.is_editing(), label_value + ": drag never starts editing or keyboard activation")
	_expect(_amounts() == prior, label_value + ": drag changes no quantity")
	await _center_amount(amount)
	origin = amount.editor.get_global_rect().get_center()
	_motion(origin, Vector2.ZERO)
	_mouse(origin, true)
	await process_frame
	_expect(not amount.editor.has_focus(), label_value + ": stationary press still waits for release")
	_mouse(origin, false)
	await _settle()
	_expect(amount.editor.has_focus() and amount.editor.is_editing(), label_value + ": completed tap starts native numeric editing")
	_expect(edit_starts == before_edits + 1, label_value + ": tap starts editing exactly once")
	_expect(amount.editor.has_selection(), label_value + ": tap selects quantity ready for replacement")
	# A second gesture over an already active number must still scroll, without
	# another edit activation, changed digits or a pointer text-selection drag.
	await _center_amount(amount)
	before = scroll.scroll_vertical
	distance = -96.0 if before >= int(bar.max_value - bar.page) - 20 else 96.0
	await _swipe(amount.editor.get_global_rect().get_center(), distance)
	_expect(abs(scroll.scroll_vertical - before) > 20, label_value + ": active number also passes a drag to the page")
	_expect(edit_starts == before_edits + 1 and _amounts() == prior, label_value + ": active-number drag does not reactivate editing or change values")
	amount.editor.unedit()
	amount.editor.release_focus()

func _check_end(label_value: String) -> void:
	var scroll: ScrollContainer = client.tabs[2]
	var bar: VScrollBar = scroll.get_v_scroll_bar()
	for i: int in range(24):
		if scroll.scroll_vertical >= int(bar.max_value - bar.page) - 2:
			break
		var viewport: Rect2 = scroll.get_global_rect()
		await _swipe(Vector2(viewport.end.x - 50, viewport.end.y - 90), 380)
	_expect(scroll.scroll_vertical >= int(bar.max_value - bar.page) - 2, label_value + ": repeated native swipes reach list end")
	var last: Control = client.fleet_list if client.fleet_mode == 0 else client.ship_rows["cruiser"].amount
	_expect(scroll.get_global_rect().intersects(last.get_global_rect()), label_value + ": final fleet content is visible")

func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Pass the fixture from tests/make_unique_building_fixture.py; optional second argument is screenshot directory. Run with a renderer and --emulate-touchscreen.")
		quit(2)
		return
	if args.size() > 1:
		screenshot_directory = args[1]
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.session_token = "offline-touch-test"
	await _settle()
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	client._apply_state(fixture.races.symbionts.improved)
	for amount in client.fleet_inputs.values() + client.cargo_inputs.values():
		amount.editor.editing_toggled.connect(func(active: bool) -> void:
			if active: edit_starts += 1)
	for row in client.ship_rows.values():
		row.amount.editor.editing_toggled.connect(func(active: bool) -> void:
			if active: edit_starts += 1)
	client._open_fleet_missions()
	client.mission_picker.select(3)
	client._mission_changed(3)
	await _settle()
	_expect(DisplayServer.is_touchscreen_available(), "Actual display has emulated touchscreen enabled")
	for width: int in [720, 600]:
		root.content_scale_size = Vector2i(width, 1280)
		root.size = Vector2i(width, 1280)
		client._set_fleet_mode(0)
		await _settle()
		for key: String in client.SHIP_KEYS:
			await _check_amount(client.fleet_inputs[key], "%d mission %s" % [width, key])
		for key: String in client.RESOURCE_KEYS:
			await _check_amount(client.cargo_inputs[key], "%d cargo %s" % [width, key])
		await _check_end("%d missions" % width)
		var amount: Control = client.cargo_inputs["metal"]
		await _center_amount(amount)
		amount.value = 10
		await _tap(amount.plus_button.get_global_rect().get_center())
		_expect(amount.value == 11, "%d cargo plus tap works once" % width)
		await _tap(amount.minus_button.get_global_rect().get_center())
		_expect(amount.value == 10, "%d cargo minus tap works once" % width)
		await _tap(amount.editor.get_global_rect().get_center())
		_expect(amount.editor.has_focus(), "%d numeric field accepts native focus" % width)
		amount.editor.select_all()
		for digit: String in "123456":
			var key := InputEventKey.new()
			key.unicode = digit.unicode_at(0)
			key.pressed = true
			root.push_input(key, true)
			key.pressed = false
			root.push_input(key, true)
		amount.editor.release_focus()
		await _settle()
		_expect(amount.value == 123456, "%d numeric field commits six-digit cargo" % width)
		var font: Font = amount.editor.get_theme_font("font")
		var text_size: Vector2 = font.get_string_size(amount.editor.text, HORIZONTAL_ALIGNMENT_LEFT, -1, amount.editor.get_theme_font_size("font_size"))
		_expect(text_size.x < amount.editor.size.x - amount.editor.get_theme_stylebox("normal").get_minimum_size().x, "%d six cargo digits remain visible" % width)
		client._set_fleet_mode(1)
		await _settle()
		for key: String in client.SHIP_KEYS:
			await _check_amount(client.ship_rows[key].amount, "%d build %s" % [width, key])
		await _check_end("%d construction" % width)
	_expect(client.intercepted_requests.is_empty(), "Interaction checks issue no purchase, preview or dispatch request")
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client._set_fleet_mode(0)
	await _settle()
	await _center_amount(client.fleet_inputs["cargo"])
	if not screenshot_directory.is_empty():
		DirAccess.make_dir_recursive_absolute(screenshot_directory)
		await RenderingServer.frame_post_draw
		_expect(root.get_texture().get_image().save_png(screenshot_directory.path_join("fleet_touch_numbers.png")) == OK, "Saved actual rendered touch quantity screenshot")
	print("Quantity 0.3.5 direct touch: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
