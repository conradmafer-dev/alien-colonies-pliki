extends "res://tests/galaxy_zoom88_comparison.gd"
## Read-only UI layout measurement; calls only the existing layout function.

func control_data(node: Control) -> Dictionary:
	return {"name": str(node.name), "class": node.get_class(), "visible": node.visible,
		"visible_in_tree": node.is_visible_in_tree(), "size": point_data(node.size),
		"global_position": point_data(node.global_position),
		"combined_min": point_data(node.get_combined_minimum_size()),
		"custom_min": point_data(node.custom_minimum_size),
		"vertical_flags": node.size_flags_vertical}

func layout_snapshot(stage: String) -> Dictionary:
	var used: float = 32.0
	var body_children: Array[Dictionary] = []
	var overview_children: Array[Dictionary] = []
	for node: Node in client.tab_bodies[1].get_children():
		if node is Control:
			var row: Dictionary = control_data(node)
			row["counted"] = node.visible and node != client.galaxy_overview
			if row["counted"]:
				used += node.get_combined_minimum_size().y + 10.0
			body_children.append(row)
	for node: Node in client.galaxy_overview.get_children():
		if node is Control:
			var row: Dictionary = control_data(node)
			row["counted"] = node.visible and node != client.galaxy_map
			if row["counted"]:
				used += node.get_combined_minimum_size().y + 4.0
			overview_children.append(row)
	return {"stage": stage, "client": control_data(client), "tab": control_data(client.tabs[1]),
		"body": control_data(client.tab_bodies[1]), "overview": control_data(client.galaxy_overview),
		"map": control_data(client.galaxy_map), "used": used,
		"calculated_map_height": maxf(140.0, client.tabs[1].size.y - used),
		"body_children": body_children, "overview_children": overview_children}

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	topology_fixture = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/galaxy_zoom88_systems.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720, 1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	var report: Array[Dictionary] = []
	for dimensions: Vector2i in [Vector2i(720, 1280), Vector2i(720, 1600)]:
		window.size = dimensions
		new_client("pl")
		var guidance = client.planetary_ui.galaxy_guidance
		guidance._visited[guidance._account_key()] = true
		await settle(12)
		client.nav_buttons[1].pressed.emit()
		await settle(16)
		var measures: Array[Dictionary] = [layout_snapshot("settled_16_frames")]
		await settle(64)
		measures.append(layout_snapshot("settled_80_frames"))
		client.compact_ui._fit_map()
		measures.append(layout_snapshot("manual_fit_immediate"))
		await settle(16)
		measures.append(layout_snapshot("manual_fit_settled_16_frames"))
		await settle(64)
		measures.append(layout_snapshot("manual_fit_settled_80_frames"))
		report.append({"window": [dimensions.x, dimensions.y], "measurements": measures})
		for measure: Dictionary in measures:
			print(JSON.stringify({"window": [dimensions.x, dimensions.y], "stage": measure["stage"],
				"tab_size": measure["tab"]["size"], "body_size": measure["body"]["size"],
				"overview_size": measure["overview"]["size"], "map_size": measure["map"]["size"],
				"map_custom_min": measure["map"]["custom_min"], "used": measure["used"],
				"calculated_map_height": measure["calculated_map_height"]}))
	var output: FileAccess = FileAccess.open("res://tests/galaxy_layout88_diagnostic_report.json", FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  "))
	output.close()
	get_tree().quit()
