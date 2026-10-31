extends "res://tests/android_fleet87_regression.gd"
const Timeline = preload("res://client/scripts/fleet_mission_timeline.gd")
const Scroll = preload("res://client/scripts/touch_scroll.gd")

func sample(locale: String = "en") -> Dictionary:
	var world: Dictionary = super.sample(locale)
	world["expeditions"] = {"schema":1,"level":5,"reward_bonus_percent":20,"highest_level":6,"max_active":2,"active":0,"hours":[1,3,6],"zone":{"id":"expedition:s1","name":"TEST Expedition zone","system_id":"s1","galaxy_id":"g1"}}
	world["buildings"]["expedition_base"] = 5
	return world

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for dimensions: Vector2i in [Vector2i(360,800),Vector2i(720,1600),Vector2i(360,640)]:
		window.size = dimensions
		new_client("pl")
		client._open_tab(2)
		client.fleet_navigation.open_expedition()
		await settle(15)
		expect(client.mission_picker.selected == 4,"Expedition opens its own composer")
		expect(client.selected_target == "expedition:s1","Nearby zone selected")
		expect(client.fleet_inputs.scout.value >= 1,"Scout added automatically")
		expect(client.fleet_navigation.expedition_box.is_visible_in_tree(),"Duration controls visible")
		expect(not client.fleet_navigation.choose_button.visible,"Nearby zone does not require enemy target")
		expect(not client.cargo_box.visible,"Hold remains available for finds")
		expect(client.fleet_navigation.expedition_choice.item_count == 3,"Three search duration choices")
		client.fleet_navigation.expedition_choice.select(1)
		client.fleet_navigation.expedition_choice.item_selected.emit(1)
		client.fleet_inputs.cargo.value = 1
		client.fleet_inputs.frigate.value = 4
		client._invalidate_quote()
		await pause()
		var payload: Dictionary = client._fleet_payload()
		expect(payload.mission == "expedition" and payload.expedition_hours == 3,"Selected duration reaches API")
		expect(payload.ships.scout >= 1 and payload.ships.frigate == 4 and payload.ships.cargo == 1,"Selected ships preserved")
		expect(not payload.has("travel_mode") and not payload.has("cargo"),"No tunnel or starting cargo")
		expect(client.request_pending and client.request_kind == "preview","Automatic quote requested")
		client._on_response(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"ok":true,"seconds":1234,"fuel_cost":432,"capacity":9000,"affordable":true,"shortfall":{},"return_at":client._server_now()+13268,"expedition":{"search_hours":3,"round_trip_seconds":13268}}).to_utf8_buffer())
		await settle(10)
		expect(not client.send_button.disabled,"Current server quote enables send")
		expect(client.fleet_navigation.route_metrics_text.contains("3 h"),"Search duration displayed")
		expect(client.fleet_mode_bar.size.y <= 100,"Navigation keeps version 102 height")
		expect(client.fleet_inputs.scout.size.y <= 80,"Quantity control keeps version 102 height")
		var legend: Node = client.galaxy_overview.find_child("FleetMapLegend",true,false)
		expect(legend.get_child(5).get_theme_color("font_color").is_equal_approx(client.galaxy_map.fleet_color({"mission":"expedition"})),"Legend matches expedition arrow")
		expect(client.ArtLibrary.texture("building_expedition_base") != null,"Building artwork loads")
		var flight: Dictionary = {"id":"exp103-test","mission":"expedition","status":"exploring","origin_id":source_id,"target_id":"expedition:s1","origin_name":"Home","target_name":"Unknown sector","ships":{"scout":1},"cargo":{},"can_recall":true,"started_at":100,"seconds":10800,"arrives_at":10900,"expedition":{"search_hours":3}}
		var timing: Dictionary = Timeline.timing(flight,200)
		expect(timing.position == 1.0 and timing.remaining == 10700,"Search marker remains at destination")
		client.compact_ui._open_fleet_details(flight)
		await settle(8)
		expect(client.compact_ui.modal_body.find_child("RecallExpedition",true,false) != null,"Active expedition offers recall")
		client.compact_ui.modal_body.find_child("RecallExpedition",true,false).pressed.emit()
		expect(client.captured[-1].payload.type == "recall_expedition" and client.captured[-1].payload.fleet_id == flight.id,"Recall addresses the exact fleet")
		expect(not str(client.captured[-1].payload.request_id).is_empty(),"Recall is idempotent")
		client.request_pending = false
		client.uncertain_action = {}
		client.state.expeditions.active = 2
		expect(not Model.draft_reason(client.state,payload,client._server_now()).is_empty(),"Occupied expedition slots disable dispatch")
		client.state.expeditions.active = 0
		client.mission_picker.select(0);client._mission_changed(0)
		expect(client.selected_target.is_empty(),"Ordinary mission discards virtual target")
		if "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless":
			client.fleet_navigation.open_expedition()
			await settle(15)
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png("res://tests/expedition103_%dx%d.png" % [dimensions.x,dimensions.y])
	expect(is_equal_approx(Scroll.MAX_VIEWPORTS_PER_SECOND,4.0*1.25),"Viewport momentum limit increased 25%")
	expect(is_equal_approx(Scroll.MAX_COAST_TO_GESTURE,4.5*1.25),"Gesture momentum limit increased 25%")
	var report: Dictionary = {"checks":checks,"failed":failed,"result":"PASS" if failed.is_empty() else "FAIL"}
	var file: FileAccess = FileAccess.open("res://tests/expedition103_report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "));file.close()
	print("EXPEDITION103_RESULT ",JSON.stringify(report))
	get_tree().quit(0 if failed.is_empty() else 1)
