extends "res://tests/galaxy_zoom88_comparison.gd"
## Full native navigation and all six optical cores, using public offline geography.
var core_checks: Array = []
var optical_profiles: Dictionary = {}

func sample(locale: String = "pl") -> Dictionary:
	var world: Dictionary = super.sample(locale)
	world["galaxies"][0]["systems_count"] = 155
	return world

func check_core(map: Control, name: String) -> void:
	expect(map._galaxy_art.get_size() == Vector2(2048,1366), name + " imported high-resolution Android texture")
	var focal: Vector2 = map.GALAXY_CORE_POINTS[name]
	for zoom: float in [1.0, 2.4, 4.5]:
		for pan: Vector2 in [Vector2.ZERO, Vector2(91, -47)]:
			map._zoom = zoom
			map._pan = pan
			map._refresh_layout()
			var rect: Rect2 = map._galaxy_art_rect()
			var error: float = (rect.position + rect.size * focal).distance_to(map._map_to_screen(Vector2.ZERO))
			expect(error < 0.01, "%s optical core remains on orbital centre at %.1f zoom" % [name, zoom])
			core_checks.append({"galaxy":name,"zoom":zoom,"pan":point_data(pan),"error_pixels":error})
			for system: Dictionary in map.systems:
				var point: Vector2 = map._screen_position(system)
				expect(rect.grow(-2).has_point(point), name + " every system lies inside the artwork")
				if name in ["void","eclipse"] and int(system.get("ring_index",-1)) == 4:
					var core: Vector2 = rect.position + rect.size * focal
					var horizon: float = float(optical_profiles[name]["dark_horizon_radius_pixels"]) * rect.size.x / 2048.0
					expect(point.distance_to(core) > horizon + map._system_glyph_radius(point), name + " entire inner system glyph stays outside the event horizon")


func capture(stage: String, dimensions: Vector2i) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	var folder: String = "res://tests/galaxy99_screenshots"
	DirAccess.make_dir_recursive_absolute(folder)
	var path: String = "%s/%dx%d_%s.png" % [folder, dimensions.x, dimensions.y, stage]
	expect(get_viewport().get_texture().get_image().save_png(path) == OK, "Saved native screenshot")
	screenshots.append(path)

func _run() -> void:
	optical_profiles = JSON.parse_string(FileAccess.get_file_as_string("res://docs/version99/galaxy_optical_profiles99.json"))
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	topology_fixture = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/six_ring99.json"))
	var counts: Dictionary = {}
	for system: Dictionary in topology_fixture["systems"]:
		var ring: int = int(system["ring_index"])
		counts[ring] = int(counts.get(ring, 0)) + 1
	expect(counts == {0:30,1:20,2:10,3:40,4:5,5:50}, "All six rings, 155 systems from the server")
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600)]:
		window.size = dimensions
		new_client("pl")
		var guidance = client.planetary_ui.galaxy_guidance
		guidance._visited[guidance._account_key()] = true
		await settle(12)
		client.nav_buttons[1].pressed.emit()
		await settle(16)
		var map: Control = client.galaxy_map
		expect(client.current_tab == 1 and map.is_visible_in_tree(), "Actual Galaxy navigation opens map")
		expect(map.systems.size() == 155 and map._ring_paths.size() == 6, "Native map renders every expanded ring")
		var normal: Dictionary = camera_snapshot(map)
		expect(is_equal_approx(float(normal["zoom"]), map.MAX_ZOOM), "Galaxy opens at maximum zoom")
		await capture("galaxy_focused",dimensions)
		for name: String in map.GALAXY_CORE_POINTS:
			map.set_galaxy_art(load("res://client/assets/art/galaxies/"+name+".webp"))
			check_core(map,name)
			map.reset_view()
			await settle(2)
			await capture(name+"_overview",dimensions)
		var outer: Dictionary = {}
		for system: Dictionary in map.systems:
			if int(system.get("ring_index",-1)) == 5:
				outer = system
				break
		map.focus_system(str(outer["id"]),map.DEFAULT_FOCUS_ZOOM)
		await settle(4)
		expect(map._screen_position(outer).distance_to(map._plot_rect().get_center()) < 1, "New outer system can be centred")
		client._start_new_mission()
		await settle(16)
		var picker: Control = client.fleet_navigation.picker_map
		expect(picker.is_visible_in_tree() and picker.systems.size() == 155, "Mission destination map includes new rings")
		var target: Dictionary = camera_snapshot(picker)
		expect(is_equal_approx(float(target["zoom"]), picker.MAX_ZOOM), "New mission opens at maximum zoom")
		expect(is_equal_approx(float(normal["zoom"]),float(target["zoom"])), "Both native maps use the same focus zoom")
		expect(float(normal["home_center_error"]) < 1 and float(target["home_center_error"]) < 1, "Active colony centred after container layout")
		expect(absf(float(normal["home_neighbor_distance"])-float(target["home_neighbor_distance"])) < 1, "Galaxy and mission picker preserve the same map scale")
		check_core(picker,"aurora")
		picker.focus_system("s1",picker.DEFAULT_FOCUS_ZOOM)
		await capture("destination_picker",dimensions)
		comparisons.append({"window":[dimensions.x,dimensions.y],"normal":normal,"picker":target})
	var report: Dictionary = {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,
		"ring_counts":counts,"core_checks":core_checks,"screenshots":screenshots,"navigation":comparisons,
		"scope":"Actual native Godot UI, offline public fixture; no physical Android or Firebase delivery test"}
	var file: FileAccess = FileAccess.open("res://tests/galaxy99_expansion_report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("Galaxy 99: %d checks, %d failures" % [checks,failed.size()])
	get_tree().quit(1 if not failed.is_empty() else 0)
