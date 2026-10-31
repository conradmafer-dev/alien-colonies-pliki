extends SceneTree
## Real GUI gestures plus deterministic time samples through exported Android GDC.
class TimedScroll:
	extends "res://client/scripts/touch_scroll.gd"
	var now_usec: int = 1000000
	func _clock_usec() -> int:
		return now_usec

var checks: int = 0
var failed: Array[String] = []
var samples: Array[Dictionary] = []
var taps: int = 0

func _initialize() -> void:
	_run.call_deferred()

func expect(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failed.append(text)
		push_error(text)

func frames(count: int = 3) -> void:
	for i: int in range(count): await process_frame

func touch_time(usec: int) -> void:
	for node: Node in get_nodes_in_group("touch_scroll_surfaces"):
		if node is TimedScroll: node.now_usec += usec

func press(position: Vector2, down: bool) -> void:
	var event := InputEventMouseButton.new()
	event.position = position
	event.global_position = position
	event.button_index = MOUSE_BUTTON_LEFT
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if down else 0
	event.pressed = down
	Input.parse_input_event(event.xformed_by(root.get_final_transform()))

func move(position: Vector2, relative: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.position = position
	event.global_position = position
	event.relative = relative
	event.velocity = relative / 0.05
	event.button_mask = MOUSE_BUTTON_MASK_LEFT
	Input.parse_input_event(event.xformed_by(root.get_final_transform()))

func make_scroll(horizontal: bool = false) -> TimedScroll:
	var scroll := TimedScroll.new()
	scroll.position = Vector2(20,20)
	scroll.size = Vector2(600,600)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO if horizontal else ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED if horizontal else ScrollContainer.SCROLL_MODE_AUTO
	var body := Control.new()
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.custom_minimum_size = Vector2(10000,500) if horizontal else Vector2(500,10000)
	scroll.add_child(body)
	scroll.set_meta("test_body",body)
	root.add_child(scroll)
	return scroll

func value(scroll: ScrollContainer, horizontal: bool = false) -> float:
	return scroll.get_h_scroll_bar().value if horizontal else scroll.get_v_scroll_bar().value

func coast(scroll: TimedScroll, fps: float) -> void:
	scroll.set_process(false)
	for frame: int in range(int(3 * fps)):
		scroll._process(1.0 / fps)

func swipe(scroll: TimedScroll, distance: float, horizontal: bool = false, pause_usec: int = 0) -> Dictionary:
	var point := Vector2(300,400)
	var step: Vector2 = Vector2(-distance / 2,0) if horizontal else Vector2(0,-distance / 2)
	var before: float = value(scroll,horizontal)
	press(point,true)
	for i: int in range(2):
		touch_time(50000)
		point += step
		move(point,step)
		await frames(1)
	touch_time(pause_usec + 1000)
	var dragged: float = value(scroll,horizontal) - before
	press(point,false)
	scroll.set_process(false)
	return {"drag":dragged,"v0":scroll._kinetic_velocity,"released":value(scroll,horizontal)}

func _run() -> void:
	Input.use_accumulated_input = false
	expect(DisplayServer.is_touchscreen_available(), "Touchscreen emulation is enabled")
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720,1280)
	root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for dimensions: Vector2i in [Vector2i(360,640),Vector2i(450,800),Vector2i(720,1280)]:
		root.size = dimensions
		await frames()
		for horizontal: bool in [false,true]:
			var reference: float = -1
			for fps: float in [30.0,60.0,90.0,120.0]:
				var scroll := make_scroll(horizontal)
				await frames()
				var motion: Dictionary = await swipe(scroll,60,horizontal)
				expect(absf(motion["drag"] - 60) < 1, "Drag follows finger at %s/%s" % [dimensions,horizontal])
				coast(scroll,fps)
				var extra: float = value(scroll,horizontal) - motion["released"]
				expect(extra > 100 and extra <= 270, "Deliberate swipe has bounded smooth coast")
				if reference < 0: reference = extra
				expect(absf(extra-reference) < 1, "Momentum distance independent of 30/60/90/120 Hz")
				expect(scroll._kinetic_velocity.is_zero_approx(), "Momentum stops without lingering drift")
				samples.append({"size":str(dimensions),"horizontal":horizontal,"fps":fps,"drag":motion["drag"],"coast":extra})
				scroll.queue_free(); await frames()
			for distance: float in [5,12]:
				var scroll := make_scroll(horizontal); await frames()
				var motion: Dictionary = await swipe(scroll,distance,horizontal)
				coast(scroll,60)
				expect(absf(value(scroll,horizontal)-motion["released"]) < 0.01, "Tiny motion never launches a fling: %s" % distance)
				scroll.queue_free(); await frames()
	var scroll := make_scroll(); await frames()
	var motion: Dictionary = await swipe(scroll,60,false,100000)
	coast(scroll,60)
	expect(is_equal_approx(value(scroll),motion["released"]), "Pausing finger before UP stops the fling")
	scroll.queue_free(); await frames()
	scroll = make_scroll(); await frames()
	scroll.scroll_vertical = 500
	var point := Vector2(300,300)
	press(point,true); touch_time(50000)
	point.y -= 60; move(point,Vector2(0,-60)); await frames(1)
	touch_time(50000)
	point.y += 80; move(point,Vector2(0,80)); await frames(1)
	touch_time(1000); press(point,false)
	var reversed_at: float = value(scroll)
	expect(scroll._kinetic_velocity.y < 0, "Reversal releases momentum in the last finger direction")
	coast(scroll,60)
	expect(value(scroll) < reversed_at, "Reversed gesture continues naturally in the new direction")
	scroll.queue_free(); await frames()
	scroll = make_scroll(); await frames()
	motion = await swipe(scroll,100)
	expect(not scroll._kinetic_velocity.is_zero_approx(), "Useful momentum exists after a deliberate gesture")
	press(Vector2(5,5),true)
	expect(scroll._kinetic_velocity.is_zero_approx(), "New touch on a header stops momentum immediately")
	press(Vector2(5,5),false)
	scroll.queue_free(); await frames()
	scroll = make_scroll(); await frames()
	motion = await swipe(scroll,100)
	scroll.cancel_gesture()
	expect(scroll._kinetic_velocity.is_zero_approx(), "Overlay cancellation stops all momentum")
	scroll.queue_free(); await frames()
	scroll = make_scroll(); await frames()
	var limit: float = scroll.get_v_scroll_bar().max_value-scroll.get_v_scroll_bar().page
	scroll.scroll_vertical = int(limit-30)
	motion = await swipe(scroll,100)
	coast(scroll,120)
	expect(value(scroll) <= limit and value(scroll) >= 0, "Content remains within bounds")
	scroll.queue_free(); await frames()
	await test_buttons()
	await test_nested()
	var report := {"result":"PASS" if failed.is_empty() else "FAIL", "checks":checks,"failed":failed,"samples":samples,
		"scope":"Actual compiled Android touch controller and sparse index, emulated touch GUI; headless desktop, no physical Android"}
	FileAccess.open("user://scroll100_report.json",FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("SCROLL100 ",JSON.stringify(report))
	quit(0 if failed.is_empty() else 1)

func test_buttons() -> void:
	var scroll := make_scroll()
	var button := Button.new()
	button.size = Vector2(500,100)
	button.text = "Action"
	button.pressed.connect(func(): taps += 1)
	scroll.get_meta("test_body").add_child(button)
	await frames()
	var point: Vector2 = button.get_global_rect().get_center()
	press(point,true); touch_time(50000); press(point,false)
	expect(taps == 1, "Stationary tap activates exactly once")
	press(point,true); touch_time(50000)
	point.y -= 40
	move(point,Vector2(0,-40)); await frames(1)
	touch_time(1000); press(point,false)
	expect(taps == 1, "Drag over action button never activates it")
	scroll.queue_free(); await frames()

func test_nested() -> void:
	for horizontal: bool in [true,false]:
		var outer := TimedScroll.new()
		outer.lock_nested_scroll_axis = true
		outer.position = Vector2(20,20); outer.size = Vector2(600,500)
		outer.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		var row := HBoxContainer.new()
		row.custom_minimum_size = Vector2(1800,500)
		var inner := TimedScroll.new()
		inner.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		inner.custom_minimum_size = Vector2(600,500)
		var content := Control.new(); content.custom_minimum_size = Vector2(500,3000)
		inner.add_child(content); row.add_child(inner)
		var spacer := Control.new(); spacer.custom_minimum_size = Vector2(1200,500); row.add_child(spacer)
		outer.add_child(row); root.add_child(outer); await frames()
		var point := Vector2(300,300)
		press(point,true); touch_time(50000)
		var delta := Vector2(-60,-10) if horizontal else Vector2(-10,-60)
		point += delta; move(point,delta); await frames(1)
		expect(value(outer,true)>0 if horizontal else value(inner)>0, "Dominant axis scrolls")
		expect(value(inner)==0 if horizontal else value(outer,true)==0, "Losing nested axis stays still")
		touch_time(50000)
		delta = Vector2(0,-80) if horizontal else Vector2(-80,0)
		point += delta; move(point,delta); await frames(1)
		expect(value(inner)==0 if horizontal else value(outer,true)==0, "Curved gesture retains original axis lock")
		press(point,false)
		outer.cancel_gesture(); inner.cancel_gesture()
		outer.queue_free(); await frames()
