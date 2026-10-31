extends Node
class TestClient:
	extends "res://client/scripts/main.gd"
	var url: String
	func _load_session() -> void:
		server_url = url; baked_server_url = url; session_token = ""
	func _save_session() -> void: pass
	func _poll(_force: bool = false) -> void: pass
	func _check_client_version() -> void: pass
	func _refresh_report_scope() -> void: report_scope = ""
var client: TestClient
var checks: int = 0
var failures: int = 0
var shots: String
var fixture: Dictionary
var url: String

func _ready() -> void: run.call_deferred()
func expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1; push_error(message)
func settle() -> void:
	for i: int in range(8): await get_tree().process_frame
func shot(name: String) -> void:
	if shots.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(shots.path_join(name+".png"))
func click(button: Button) -> void:
	var point: Vector2 = button.get_global_rect().get_center()
	var motion: InputEventMouseMotion = InputEventMouseMotion.new(); motion.position = point; motion.global_position = point
	Input.parse_input_event(motion)
	for down: bool in [true,false]:
		var event: InputEventMouseButton = InputEventMouseButton.new()
		event.position = point; event.global_position = point; event.button_index = MOUSE_BUTTON_LEFT; event.pressed = down
		Input.parse_input_event(event)
	await settle()
func fresh(locale: String) -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client); client.queue_free()
	get_tree().root.get_node("I18n").set_locale(locale,false)
	client = TestClient.new(); client.url = url
	get_tree().root.add_child(client); client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop(); client.update_timer.stop(); client.communications.timer.stop()
	client.session_token = fixture["token"]; client._apply_state(fixture["states"][locale].duplicate(true))
	client._open_tab(4)
	await settle()
func wait_replay() -> void:
	var deadline: int = Time.get_ticks_msec()+10000
	while is_instance_valid(client.compact_ui.battle_viewer) and client.compact_ui.battle_viewer.replay.is_empty() and Time.get_ticks_msec()<deadline:
		await get_tree().process_frame
	expect(is_instance_valid(client.compact_ui.battle_viewer) and not client.compact_ui.battle_viewer.replay.is_empty(),"Authenticated replay loaded")
func geometry(view) -> void:
	var width: float = view.size.x
	for side: String in ["attacker","defender"]:
		for unit: Dictionary in view.replay[side]["units"]:
			expect(view.board.textures[side+":"+unit["key"]]!=null,"Unit uses correct artwork")
	for button: Button in [view.pause_button,view.previous_button,view.next_button,view.speed_button,view.skip_button]:
		expect(button.size.y>=56,"Touch target height")
		expect(button.get_global_rect().end.x <= get_viewport().get_visible_rect().end.x+1,"Controls fit viewport")
	expect(view.board.size.x <= width+1,"Arena fits horizontally")
	for rect: Rect2 in view.board.cards.values():
		expect(Rect2(Vector2.ZERO,view.board.size).encloses(rect),"Every unit fits arena")
func run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	fixture = JSON.parse_string(FileAccess.get_file_as_string(args[0])); url = args[1]
	shots = args[2] if args.size()>2 else ""
	if not shots.is_empty(): DirAccess.make_dir_recursive_absolute(shots)
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["pl","en","de","es","fr"]:
		window.size = Vector2i(720,1600)
		await fresh(locale)
		# Click an actual Reports list entry, not a test-only replay widget.
		await click(client.report_list.get_child(0))
		await wait_replay()
		var view = client.compact_ui.battle_viewer
		if not is_instance_valid(view) or view.replay.is_empty(): continue
		expect(view.playing,"Opening a report starts playback automatically")
		await click(view.pause_button)
		expect(not view.playing,"Pause responds to pointer input")
		var previous: int = view.index
		await get_tree().create_timer(.12).timeout
		expect(view.index==previous,"Paused replay remains stable")
		var before: String = JSON.stringify(client.state)
		for i: int in range(view.replay["rounds"].size()):
			view.seek_round(i)
			expect(view.frames[view.index]["state"]==view.replay["rounds"][i]["after"],"Round picker shows exact completed round")
			expect(not view.playing,"Round inspection stays paused")
			var last_phase: String = ""
			for frame: Dictionary in view.frames:
				if frame["round"]!=i: continue
				if frame["kind"]=="heal": expect(last_phase!="fire","Healing follows damage")
				last_phase = frame["kind"]
			if i==0 and locale=="pl":
				await settle(); await shot("round_1_pl")
		await click(view.skip_button)
		expect(view.frames[view.index]["state"]==view.replay["final"],"Skip shows exact final counts and wounds")
		expect(not view.playing,"Replay stops at result")
		await click(view.pause_button)
		expect(view.playing and view.index<3,"Replay restarts from opening")
		await click(view.speed_button); expect(view.speed==2,"Double speed")
		await click(view.pause_button)
		# Inspect animation frames and screen sizes, including every unit type.
		for kind: String in ["fire","impact","heal"]:
			var found: bool = false
			for i: int in range(view.frames.size()):
				if view.frames[i]["kind"]==kind:
					view.index=i;view._show();view.board.show_frame(view.frames[i],.42)
					await settle(); found=true
					if locale=="pl": await shot(kind+"_pl")
					break
			expect(found,"Real fixture contains phase: "+kind)
		for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520)]:
			window.size=dimensions;await settle();geometry(view)
		expect(JSON.stringify(client.state)==before,"Playback never changes gameplay state")
		view.index=0;view.elapsed=0;view.playing=true;view.speed=50;view._show()
		var finish_deadline: int = Time.get_ticks_msec()+10000
		while view.playing and Time.get_ticks_msec()<finish_deadline: await get_tree().process_frame
		expect(not view.playing and view.frames[view.index]["kind"]=="result","Automatic playback reaches final result")
		view.playing=true
		view._notification(NOTIFICATION_APPLICATION_PAUSED)
		expect(not view.playing,"Backgrounding pauses playback")
		view.playing=true
		client.compact_ui.close_details()
		expect(view.stopped and not view.playing,"Closing stops playback and cancels requests")
		client.compact_ui._open_report(client.state["reports"][1]);await wait_replay()
		view=client.compact_ui.battle_viewer;view.playing=false
		window.size=Vector2i(720,1280)
		await settle();geometry(view)
		expect(view.replay["attacker"]["units"].size()==8,"All ship types shown")
		if locale=="pl": await shot("all_units_pl")
		client.compact_ui._open_report(client.state["reports"][2]);await wait_replay()
		view=client.compact_ui.battle_viewer;expect(view.replay["rounds"].is_empty(),"Empty target has no invented rounds")
		view.skip();expect(not view.playing,"Empty-target result works")
		client.compact_ui._open_report(client.state["reports"][3]);await settle()
		expect(not is_instance_valid(client.compact_ui.battle_viewer),"Historical report stays textual")
		# Failed fetch leaves the report readable and offers retry.
		client.compact_ui._open_report({"id":"missing-report","title":"Missing","text":"Fallback report","battle_replay_available":true})
		view=client.compact_ui.battle_viewer
		var deadline: int = Time.get_ticks_msec()+5000
		while not view.retry_button.visible and Time.get_ticks_msec()<deadline: await get_tree().process_frame
		expect(view.retry_button.visible,"Fetch error is visible and retryable")
		client.compact_ui.close_details()
	print("Battle replay UI 0.9.4: ",checks," checks; ",failures," failures")
	get_tree().quit(1 if failures else 0)
