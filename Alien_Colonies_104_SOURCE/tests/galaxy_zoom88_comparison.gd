extends "res://tests/android_fleet87_regression.gd"
## Real client navigation with a complete server-authored 30/20/10 ring fixture.
## All requests remain intercepted by OfflineClient; no production state is read.

var topology_fixture: Dictionary
var comparisons: Array[Dictionary] = []
var screenshots: Array[String] = []

func sample(locale: String = "pl") -> Dictionary:
	var world: Dictionary = super.sample(locale)
	var home_planets: Array = world["galaxy"][0]["planets"].duplicate(true)
	var systems: Array = topology_fixture["systems"].duplicate(true)
	for system: Dictionary in systems:
		var id: String = str(system["id"])
		system["scout_target_id"] = id + "p1"
		if id == "s1":
			system["visibility"] = "colony"
			system["planets"] = home_planets
	world["galaxy"] = systems
	world["planet_galaxy_id"] = "g1"
	var galaxy: Dictionary = world["galaxies"][0].duplicate(true)
	galaxy.merge({"id": "g1", "name": "Aurora", "own_colonies": 2, "systems_count": 60}, true)
	world["galaxies"] = [galaxy]
	return world

func point_data(point: Vector2) -> Array:
	return [point.x, point.y]

func camera_snapshot(map: Control) -> Dictionary:
	var home: Dictionary = map._system_by_id("s1")
	var neighbor: Dictionary = map._system_by_id("s2")
	var home_point: Vector2 = map._screen_position(home)
	var neighbor_point: Vector2 = map._screen_position(neighbor)
	var radius: Vector2 = map._ellipse_radius()
	var visible_ids: Array[String] = []
	var relative_points: Dictionary = {}
	for hit: Dictionary in map.hit_points:
		var id: String = str(hit["id"])
		visible_ids.append(id)
		relative_points[id] = point_data(Vector2(hit["position"]) - home_point)
	visible_ids.sort()
	return {"size": point_data(map.size), "global_position": point_data(map.global_position),
		"zoom": map.get_zoom(), "pan": point_data(map._pan),
		"ellipse_radius": point_data(radius), "rendered_ring_radius": point_data(radius * map.get_zoom()),
		"system_count": map.systems.size(), "ring_topology": map._has_ring_topology,
		"selected_system": map.selected_id, "visible_count": visible_ids.size(), "visible_ids": visible_ids,
		"relative_visible_positions": relative_points,
		"home_position": point_data(home_point), "plot_center": point_data(map._plot_rect().get_center()),
		"home_center_error": home_point.distance_to(map._plot_rect().get_center()),
		"home_neighbor_distance": home_point.distance_to(neighbor_point)}

func capture(stage: String, dimensions: Vector2i) -> void:
	if "--capture" not in OS.get_cmdline_user_args():
		return
	if DisplayServer.get_name() == "headless":
		expect(false, "Capture requires a rendering display")
		return
	await RenderingServer.frame_post_draw
	var folder: String = "res://tests/galaxy_zoom88_screenshots"
	DirAccess.make_dir_recursive_absolute(folder)
	var path: String = "%s/pl_%dx%d_%s.png" % [folder, dimensions.x, dimensions.y, stage]
	var result: Error = get_viewport().get_texture().get_image().save_png(path)
	expect(result == OK, "Saved screenshot " + path)
	if result == OK:
		screenshots.append(path)

func compare_cameras(normal: Dictionary, picker: Dictionary, label: String) -> Dictionary:
	expect(normal["ring_topology"] and picker["ring_topology"], "Both views use server ring topology " + label)
	expect(normal["system_count"] == 60 and picker["system_count"] == 60, "Both views receive all 60 galaxy systems " + label)
	expect(is_equal_approx(float(normal["zoom"]), float(picker["zoom"])), "Picker uses actual Galaxy navigation zoom " + label)
	expect(normal["selected_system"] == "s1" and picker["selected_system"] == "s1", "Both views focus the active colony system " + label)
	expect(float(normal["home_center_error"]) <= 1.0 and float(picker["home_center_error"]) <= 1.0, "Home remains centered after container layout " + label)
	expect(int(normal["visible_count"]) >= 5 and int(picker["visible_count"]) >= 5, "Both views show multiple neighboring systems " + label)
	var spacing_delta: float = absf(float(normal["home_neighbor_distance"]) - float(picker["home_neighbor_distance"]))
	expect(spacing_delta <= 1.0, "Actual home-to-neighbor pixel scale matches " + label)
	var matched: int = 0
	var max_offset_error: float = 0.0
	for id: String in normal["relative_visible_positions"]:
		if not picker["relative_visible_positions"].has(id):
			continue
		matched += 1
		var a: Array = normal["relative_visible_positions"][id]
		var b: Array = picker["relative_visible_positions"][id]
		max_offset_error = maxf(max_offset_error, Vector2(a[0], a[1]).distance_to(Vector2(b[0], b[1])))
	expect(matched >= 5 and max_offset_error <= 1.0, "Shared neighbors have the same positions relative to home " + label)
	return {"common_visible_systems": matched, "max_relative_position_difference": max_offset_error,
		"home_neighbor_distance_difference": spacing_delta}

func diagnose_previous_view(map: Control, full_systems: Array, owner: String) -> Dictionary:
	var current_zoom: float = map.get_zoom()
	var current: Dictionary = camera_snapshot(map)
	map.focus_system("s1", 3.2)
	var old: Dictionary = camera_snapshot(map)
	var ratio: float = float(old["home_neighbor_distance"]) / float(current["home_neighbor_distance"])
	expect(ratio > 1.3, "Previous 3.2 view measurably magnifies neighbor spacing")
	expect(int(old["visible_count"]) <= int(current["visible_count"]), "Previous stronger zoom cannot reveal more neighbors")
	var artificial: Array = [
		{"id": "s1", "name": "TEST Home System", "galaxy_id": "g1", "visibility": "colony", "planets": full_systems[0]["planets"]},
		{"id": "s2", "name": "TEST Uncharted", "galaxy_id": "g1", "visibility": "unknown", "planets": []},
	]
	map.set_data(artificial, owner, "s1")
	map.focus_system("s1", 3.2)
	var sparse_old: Dictionary = camera_snapshot(map)
	map.focus_system("s1", current_zoom)
	var sparse_current: Dictionary = camera_snapshot(map)
	expect(not sparse_old["ring_topology"] and sparse_old["visible_count"] == 1, "Two-system test fixture reproduces one visible star at 3.2")
	expect(sparse_current["visible_count"] == 1, "Sparse fixture still shows one star at the Galaxy tab zoom")
	map.set_data(full_systems, owner, "s1")
	map.focus_system("s1", current_zoom)
	return {"previous_zoom": old, "previous_to_current_neighbor_spacing_ratio": ratio,
		"two_system_fixture_at_previous_zoom": sparse_old,
		"two_system_fixture_at_current_zoom": sparse_current}

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	topology_fixture = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/galaxy_zoom88_systems.json"))
	var ring_counts: Dictionary = {}
	for system: Dictionary in topology_fixture["systems"]:
		var ring: int = int(system["ring_index"])
		ring_counts[ring] = int(ring_counts.get(ring, 0)) + 1
	expect(ring_counts == {0: 30, 1: 20, 2: 10}, "Complete three-ring fixture contains 30/20/10 systems")
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720, 1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for dimensions: Vector2i in [Vector2i(720, 1280), Vector2i(720, 1600)]:
		window.size = dimensions
		new_client("pl")
		# Existing players have already dismissed the first-visit system tutorial.
		# Seed only this in-memory preference, then use the actual bottom button.
		var guidance = client.planetary_ui.galaxy_guidance
		guidance._visited[guidance._account_key()] = true
		await settle(12)
		client.nav_buttons[1].pressed.emit()
		await settle(16)
		expect(client.current_tab == 1 and client.galaxy_map.is_visible_in_tree(), "Bottom Galaxy button opens actual galaxy view")
		var controls_bottom: float = 0.0
		for child: Node in client.galaxy_overview.get_children():
			if child is Control and child.is_visible_in_tree():
				controls_bottom = maxf(controls_bottom, child.get_global_rect().end.y)
		var bottom_space: float = client.tabs[1].get_global_rect().end.y - controls_bottom
		expect(bottom_space >= -1.0 and bottom_space <= 32.0, "Normal Galaxy fills available height with controls inside the page")
		var normal: Dictionary = camera_snapshot(client.galaxy_map)
		await capture("normal_galaxy", dimensions)
		client._start_new_mission()
		await settle(16)
		var ui = client.fleet_navigation
		expect(ui._map_open() and ui.picker_map.is_visible_in_tree(), "New mission opens actual destination map")
		var picker: Dictionary = camera_snapshot(ui.picker_map)
		var camera_match: Dictionary = compare_cameras(normal, picker, str(dimensions))
		await capture("destination_picker", dimensions)
		var diagnostics: Dictionary = diagnose_previous_view(ui.picker_map, client.state["galaxy"], str(client.state["player"]["id"]))
		# The destination view must work before this account has ever opened Galaxy.
		# A fresh real UI tree prevents a hidden dependency on its previous layout.
		new_client("pl")
		await settle(12)
		expect(client.current_tab == 0, "Fresh client has not entered the Galaxy tab")
		client._start_new_mission()
		await settle(16)
		var first_ui = client.fleet_navigation
		expect(first_ui._map_open() and first_ui.picker_map.is_visible_in_tree(), "First navigation can open the destination map")
		var first_picker: Dictionary = camera_snapshot(first_ui.picker_map)
		var first_match: Dictionary = compare_cameras(normal, first_picker, str(dimensions) + " destination first")
		comparisons.append({"window": [dimensions.x, dimensions.y], "normal_galaxy": normal,
			"normal_controls_bottom": controls_bottom, "normal_bottom_space": bottom_space,
			"destination_picker": picker, "comparison": camera_match,
			"first_destination_picker": first_picker, "first_destination_comparison": first_match,
			"diagnostics": diagnostics})
	var report: Dictionary = {"result": "PASS" if failed.is_empty() else "FAIL", "checks": checks,
		"failures": failed.size(), "failed_checks": failed, "comparisons": comparisons,
		"fixture_source": topology_fixture["source_fixture"], "fixture_source_sha256": topology_fixture["source_sha256"],
		"ring_counts": ring_counts, "screenshots": screenshots,
		"scope": "Offline desktop Godot runtime; existing-player bottom navigation; no server or production data"}
	var output: FileAccess = FileAccess.open("res://tests/galaxy_zoom88_comparison_report.json", FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  "))
	output.close()
	print("Galaxy zoom88 comparison: %d checks; %d failures" % [checks, failed.size()])
	for comparison: Dictionary in comparisons:
		print(JSON.stringify({"window": comparison["window"], "normal_size": comparison["normal_galaxy"]["size"],
			"picker_size": comparison["destination_picker"]["size"],
			"normal_zoom": comparison["normal_galaxy"]["zoom"], "picker_zoom": comparison["destination_picker"]["zoom"],
			"normal_visible": comparison["normal_galaxy"]["visible_count"], "picker_visible": comparison["destination_picker"]["visible_count"],
			"scale_match": comparison["comparison"]}))
	get_tree().quit(1 if not failed.is_empty() else 0)
