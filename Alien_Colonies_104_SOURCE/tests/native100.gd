extends "res://tests/galaxy_zoom88_comparison.gd"
const Map100 = preload("res://client/scripts/galaxy_map.gd")
const Report100 = preload("res://client/scripts/report_summary.gd")

func sample(locale: String = "en") -> Dictionary:
	var world: Dictionary = super.sample(locale)
	world["galaxies"][0]["systems_count"] = 155
	return world

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	topology_fixture = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/six_ring99.json"))
	var contract: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://backend/web/play/tests/fixtures/fleet-motion100.json"))
	var fleet: Dictionary = contract["fleet"]
	var original: Dictionary = fleet.duplicate(true)
	for entry: Dictionary in contract["samples"]:
		var value: Dictionary = Map100.FleetMotion.sample(fleet, float(entry["now"]))
		expect(absf(float(value["progress"]) - float(entry["progress"])) < 0.000001, "Server-clock fraction at " + str(entry["now"]))
		expect(int(value["index"]) == int(entry["index"]), "Weighted paid segment at " + str(entry["now"]))
		expect(absf(float(value["fraction"]) - float(entry["fraction"])) < 0.000001, "Fraction within weighted segment at " + str(entry["now"]))
	var returned: Dictionary = fleet.duplicate(true)
	returned.merge({"status":"returning", "started_at":1120.0, "arrives_at":1240.0}, true)
	var plan: Dictionary = Map100.FleetMotion.plan(returned)
	expect(plan["segments"][0]["from_system_id"] == "s3" and plan["segments"][0]["to_system_id"] == "s2", "Returning ship reverses the paid path")
	expect(Map100.FleetMotion.sample(returned,1180.0)["index"] == 0, "Returning segment keeps its original weight")
	var recalled: Dictionary = returned.duplicate(true)
	recalled["map_return_fraction"] = 0.5
	var recall_plan: Dictionary = Map100.FleetMotion.plan(recalled)
	expect(absf(float(recall_plan["total"]) - 2.0) < 0.000001, "Early recall keeps only travelled distance")
	expect(absf(float(recall_plan["segments"][0]["from_fraction"]) - 2.0 / 3.0) < 0.000001, "Recall starts at the actual turnaround point")
	var held: Dictionary = fleet.duplicate(true)
	held["status"] = "holding"
	expect(Map100.FleetMotion.progress(held,1010.0) == 1.0, "Defending ship stays at its destination during its holding timer")
	var tunnel: Dictionary = fleet.duplicate(true)
	tunnel["route"]["travel_mode"] = "tunnel"
	expect(Map100.FleetMotion.plan(tunnel)["mode"] == "tunnel", "Tunnel never becomes an orbital corridor")
	var legacy: Dictionary = fleet.duplicate(true)
	legacy["route"] = {}
	expect(Map100.FleetMotion.plan(legacy)["segments"][0]["kind"] == "legacy", "Old flights without a saved corridor stay explicit legacy paths")
	expect(fleet == original, "Map sampling never mutates a real fleet or its route")
	for kind_value: String in Report100.ICON_PATHS:
		var icon: Texture2D = Report100.icon_texture({"kind": kind_value})
		expect(icon != null and icon.get_size() == Vector2(96,96), "Vector report icon is valid: " + kind_value)
	expect(Report100.icon_kind({"kind":"invalid","battle_replay_available":true}) == "battle", "Legacy battle icon fallback is factual")
	await new_client("en")
	var world: Dictionary = sample("en")
	world["server_time"] = 1000.0
	world["fleets"] = [fleet, returned, held]
	client._apply_state_now(world,Time.get_ticks_msec())
	client._open_tab(2)
	var action: Dictionary = {"type":"fleet", "planet_id":source_id, "mission":"scout", "target_id":free_id, "ships":{"scout":1}}
	client.fleet_navigation.dispatch_result(action,HTTPRequest.RESULT_SUCCESS,400,{"ok":false})
	expect(client.current_tab == 2, "Rejected launch does not open a false flight map")
	client.fleet_navigation.dispatch_result(action,HTTPRequest.RESULT_SUCCESS,200,{"ok":true,"state":world})
	await settle()
	expect(client.current_tab == 1 and client.galaxy_overview.visible, "Confirmed launch automatically opens Galaxy")
	expect(is_equal_approx(client.galaxy_map.get_zoom(),client.galaxy_map.MAX_ZOOM), "Post-launch map opens at maximum zoom")
	expect(not client.compact_ui.modal.visible, "Post-launch map is not covered by the previous receipt window")
	var map: Control = client.galaxy_map
	expect(map._fleet_overlay.records.size() == 3, "All own flights in this galaxy are displayed")
	expect(map._fleet_overlay.is_processing() and not map.is_processing(), "Only the flight overlay animates, the static map does not process each frame")
	for zoom: float in [1.0,2.4,4.5,6.0]:
		map._zoom = zoom
		map._pan = Vector2(30,-20)
		map._refresh_layout()
		var paths: Array = map._fleet_overlay.records[0]["paths"]
		expect(paths[0].size() == 13 and paths[1].size() == 2, "Fleet follows orbital arcs and straight bridges at zoom " + str(zoom))
		var point: Vector2 = paths[0][0] + map._fleet_overlay.position
		expect(point.distance_to(map._screen_position(map._system_by_id("s1"))) < 0.01, "Fleet path stays anchored through pan/zoom")
		var reverse_paths: Array = map._fleet_overlay.records[1]["paths"]
		point = reverse_paths[0][0] + map._fleet_overlay.position
		expect(point.distance_to(map._screen_position(map._system_by_id("s3"))) < 0.01, "Return starts from the destination system")
	var recall_fleet: Dictionary = returned.duplicate(true)
	recall_fleet["map_return_fraction"] = 0.5
	map.set_fleets([fleet, recall_fleet],1130.0)
	var outgoing_path: PackedVector2Array = map._fleet_overlay.records[0]["paths"][1]
	var recall_path: PackedVector2Array = map._fleet_overlay.records[1]["paths"][0]
	var turnaround: Vector2 = map._fleet_overlay._path_sample(outgoing_path,1.0/3.0)["point"]
	expect(turnaround.distance_to(recall_path[0]) < 0.01, "Early return is visually continuous at the real turnaround point")
	var jump: Dictionary = fleet.duplicate(true)
	jump["target_system_id"] = "foreign-system"
	jump["target_galaxy_id"] = "g2"
	jump["route"]["intergalactic"] = true
	map.set_fleets([jump],1010.0)
	var portal: Vector2 = map._fleet_overlay.records[0]["paths"][0][-1] + map._fleet_overlay.position
	var portal_world: Vector2 = (portal-map._map_to_screen(Vector2.ZERO))/map._zoom
	map._zoom=2.4
	map._pan=Vector2(-50,60)
	map._refresh_layout()
	portal = map._fleet_overlay.records[0]["paths"][0][-1] + map._fleet_overlay.position
	var transformed_world: Vector2 = (portal-map._map_to_screen(Vector2.ZERO))/map._zoom
	expect(portal_world.distance_to(transformed_world) < 0.01, "Intergalactic gateway stays anchored in the galaxy while the camera moves")
	client._open_tab(0)
	await settle()
	expect(not map._fleet_overlay.is_processing(), "Hidden maps stop animation processing")
	for entry: Dictionary in client.captured:
		expect(str(entry.get("kind","")) != "action", "Displaying flights never dispatches an extra order")
	var report: Dictionary = {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,
		"scope":"Actual native controller/UI with intercepted commands; source test, not a physical Android device."}
	FileAccess.open("res://docs/version100/native100_report.json",FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("NATIVE100 ",JSON.stringify(report))
	get_tree().quit(0 if failed.is_empty() else 1)

