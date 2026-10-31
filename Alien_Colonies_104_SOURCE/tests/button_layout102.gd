extends "res://tests/android_fleet87_regression.gd"

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720, 1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for dimensions: Vector2i in [Vector2i(360, 800), Vector2i(720, 1600), Vector2i(360, 640)]:
		window.size = dimensions
		new_client("en")
		client.selected_target = unknown_id
		client.compact_ui.open_composer()
		await settle(25)
		var quantity = client.fleet_inputs["scout"]
		client.fleet_descriptions["scout"].text = "A living scout that reveals a planet's resources, fleet and defenses. Can also update ownership information for every planet in a system. ".repeat(3)
		await settle(8)
		print("LAYOUT102 ", JSON.stringify({"window":str(dimensions),"bar":str(client.fleet_mode_bar.size),"bar_min":str(client.fleet_mode_bar.get_combined_minimum_size()),"bar_anchors":[client.fleet_mode_bar.anchor_top,client.fleet_mode_bar.anchor_bottom],"parent":str(client.fleet_mode_bar.get_parent().size),"nav":str(client.fleet_mode_buttons[0].size),"quantity":str(quantity.size),"ship_row":str(quantity.get_parent().size),"description":str(client.fleet_descriptions["scout"].size),"minus":str(quantity.minus_button.size)}))
		expect(client.fleet_mode_bar.size.y <= 100.0,"Fleet navigation stays compact at " + str(dimensions))
		expect(quantity.size.y <= 80.0,"Quantity stays compact beside a wrapped ship description at " + str(dimensions))
		expect(quantity.minus_button.size.y <= 80.0 and quantity.plus_button.size.y <= 80.0 and quantity.editor.size.y <= 80.0,"All quantity controls keep touch-sized height")
		expect(quantity.get_parent().size.y > quantity.size.y * 2.0,"Regression fixture has a tall description beside the counter")
		var before: float = quantity.value
		quantity.plus_button.pressed.emit()
		expect(quantity.value == before + 1.0,"Plus still changes the selected fleet")
		quantity.minus_button.pressed.emit()
		expect(quantity.value == before,"Minus still changes the selected fleet")
		client.fleet_mode_bar.offset_bottom = 480
		client._fit_fleet_mode_bar()
		await settle(8)
		expect(client.fleet_mode_bar.size.y <= 100.0,"Toolbar recovers from the reported oversized height")
		var legend: Node = client.galaxy_overview.find_child("FleetMapLegend",true,false)
		var missions: Array[String] = ["scout","transport","colonize","attack","returning"]
		var expected: Array[Color] = [Color("91a8c8"),Color("e4c17a"),Color("9be4ad"),Color("ff9295"),Color("b6bdc8")]
		for index: int in range(missions.size()):
			var snapshot: Dictionary = {"mission":missions[index],"status":missions[index]}
			var color: Color = client.galaxy_map._fleet_overlay.marker_color(snapshot)
			expect(color.to_html(false) == expected[index].to_html(false),"Map mission has the requested semantic color: " + missions[index])
			expect(legend.get_child(index).get_theme_color("font_color").is_equal_approx(color),"Legend exactly matches the moving arrow: " + missions[index])
		expect(client.galaxy_map.fleet_color({"mission":"scout"}).is_equal_approx(preload("res://client/scripts/fleet_mission_timeline.gd").marker_color({})),"Scout preserves the current gentle blue")
		for locale: String in ["en","pl","de","es","fr"]:
			I18n.set_locale(locale,false)
			client._fit_fleet_mode_bar()
			await settle(4)
			expect(client.fleet_mode_bar.size.y <= 100.0,"Toolbar stays compact after language switch: " + locale)
		if "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless":
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png("res://tests/buttons102_%dx%d.png" % [dimensions.x,dimensions.y])
	var report: Dictionary = {"checks":checks,"failed":failed,"result":"PASS" if failed.is_empty() else "FAIL"}
	var file: FileAccess = FileAccess.open("res://tests/button_layout102_report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("LAYOUT102_RESULT ",JSON.stringify(report))
	get_tree().quit(0 if failed.is_empty() else 1)
