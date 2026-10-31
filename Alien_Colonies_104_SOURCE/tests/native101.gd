extends "res://tests/galaxy_zoom88_comparison.gd"
const Timeline101 = preload("res://client/scripts/fleet_mission_timeline.gd")

func sample(locale: String = "en") -> Dictionary:
	var world: Dictionary = super.sample(locale)
	world["galaxies"][0]["systems_count"] = 155
	return world

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	topology_fixture = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/six_ring99.json"))
	var contract: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://backend/web/play/tests/fixtures/fleet-motion100.json"))
	get_tree().root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_tree().root.content_scale_size = Vector2i(720,1280)
	get_tree().root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for dimensions: Vector2i in [Vector2i(360,800),Vector2i(720,1600)]:
		get_tree().root.size = dimensions
		new_client("en")
		var guidance = client.planetary_ui.galaxy_guidance
		guidance._visited[guidance._account_key()] = true
		var world: Dictionary = sample("en")
		world["server_time"] = 1000.0
		world["fleets"] = [contract["fleet"].duplicate(true)]
		client._apply_state_now(world,Time.get_ticks_msec())
		await settle(12)
		client.nav_buttons[1].pressed.emit()
		await settle(16)
		var map: Control = client.galaxy_map
		expect(map.MAX_ZOOM == 6.0 and map.MAX_ZOOM > 4.5, "Raised native zoom ceiling is 6x")
		expect(map.get_zoom() == map.MAX_ZOOM, "Galaxy navigation defaults to maximum")
		expect(float(camera_snapshot(map)["home_center_error"]) < 1, "Default maximum centres source colony")
		map.zoom_in()
		expect(map.get_zoom() == map.MAX_ZOOM, "Zoom-in cannot exceed the raised ceiling")
		map.reset_view()
		expect(map.get_zoom() == 1.0, "Fit all remains an explicit usable overview")
		client._open_tab(2)
		var action: Dictionary = {"type":"fleet","planet_id":source_id,"mission":"scout","target_id":unknown_id,"ships":{"scout":1}}
		client.fleet_navigation.dispatch_result(action,HTTPRequest.RESULT_SUCCESS,200,{"ok":true,"state":world})
		await settle(16)
		expect(client.current_tab == 1 and client.galaxy_overview.visible, "Successful launch opens Galaxy")
		expect(map.get_zoom() == map.MAX_ZOOM, "Successful launch restores maximum after manual Fit all")
		expect(float(camera_snapshot(map)["home_center_error"]) < 1, "Post-launch maximum centres launch source")
		client.selected_target = unknown_id
		client.fleet_navigation.open_destination_map()
		await settle(16)
		var nav = client.fleet_navigation
		expect(nav.picker_map_panel.visible and not nav.picker_planet_panel.visible, "Change destination opens galaxy map for an existing target")
		expect(nav.picker_map.get_zoom() == map.MAX_ZOOM, "Destination map defaults to the same maximum")
		expect(nav.browse_system == "s2", "Existing target system remains selected")
		var selected: Dictionary = nav.picker_map._system_by_id("s2")
		expect(nav.picker_map._screen_position(selected).distance_to(nav.picker_map._plot_rect().get_center()) < 1, "Change destination centres existing target after layout")
		expect(client.selected_target == unknown_id, "Opening the map does not replace an existing mission target")
		nav._select_system("s2")
		expect(nav.picker_planet_panel.visible and not nav.picker_map_panel.visible, "Explicit system selection opens planet choices")
		expect(nav._destination_back(), "Back from planets returns one level")
		await settle(12)
		expect(nav.picker_map_panel.visible and nav.picker_map.get_zoom() == map.MAX_ZOOM, "Back preserves the maximum galaxy camera")
		client.compact_ui.close_details()
		client._open_tab(2)
		for race: String in ["zetans","automatons","symbionts"]:
			client._apply_race_palette(race)
			for status: String in ["outbound","returning","holding"]:
				for swarm_art: bool in [false,true]:
					var fleet: Dictionary = contract["fleet"].duplicate(true)
					fleet["status"] = status
					fleet["art_key"] = "swarm/scout" if swarm_art else "races/" + race + "/scout"
					client.state["fleets"] = [fleet]
					client.fleets_signature = ""
					client.compact_ui.refresh_fleets()
					await settle(2)
					var timeline: Control = client.fleet_list.get_child(0).get_meta("fleet_timeline")
					var expected: Color = client._ui_color(Color("edc77a") if swarm_art else Color("91c89b"))
					expect(timeline.accent.is_equal_approx(expected), "Active missions retains its existing accent: " + race + "/" + status)
					expect(map._fleet_overlay.marker_color(fleet).is_equal_approx(timeline.accent), "Map ship equals actual mission ship: " + race + "/" + status)
	var report: Dictionary = {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,
		"scope":"Actual native UI with intercepted commands; Godot4.5.1 headless desktop, not physical Android"}
	var file: FileAccess = FileAccess.open("user://native101_report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("Native101: ",JSON.stringify(report))
	get_tree().quit(0 if failed.is_empty() else 1)
