extends SceneTree
## Fleet navigation, race presentation and 0.3.3 Swarm location using a real server fixture.
## Generate tests/make_unique_building_fixture.py first. All HTTP is intercepted.
const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
const RaceTheme = preload("res://client/scripts/race_theme.gd")
const RACES: Array[String] = ["zetans", "automatons", "symbionts"]
var client: MobileSmoke.OfflineClient
var checks: int = 0
var failures: Array[String] = []
var screenshots: String = ""


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, caption: String) -> void:
	checks += 1
	if not condition:
		failures.append(caption)
		push_error(caption)


func _settle() -> void:
	for _frame: int in range(10):
		await process_frame


func _bounds(node: Node, area: Rect2, issues: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var rect: Rect2 = child.get_global_rect()
			if rect.position.x < area.position.x - 1 or rect.end.x > area.end.x + 1:
				issues.append(str(child.name) + " " + str(rect))
			_bounds(child, area, issues)


func _button_named(node: Node, caption: String) -> Button:
	if node is Button and node.text == caption:
		return node as Button
	for child: Node in node.get_children():
		var found: Button = _button_named(child, caption)
		if found != null:
			return found
	return null


func _capture(name_value: String) -> void:
	if screenshots.is_empty() or DisplayServer.get_name() == "headless":
		return
	await _settle()
	await RenderingServer.frame_post_draw
	_expect(root.get_texture().get_image().save_png(screenshots.path_join(name_value + ".png")) == OK,
		"Saved rendered screenshot " + name_value)


func _palette_check(id: String) -> void:
	var colors: Dictionary = RaceTheme.palette(id)
	_expect(RaceTheme.current_race() == id, id + ": received account selects its racial palette")
	var accent: Color = colors["accent"]
	_expect((accent.b > accent.r and accent.b > accent.g) if id == "zetans" else (accent.r > accent.g and accent.r > accent.b) if id == "automatons" else (accent.g > accent.r and accent.g > accent.b), id + ": blue/red/green identity is visible in actual accent")
	_expect((client.get_child(0) as ColorRect).color.is_equal_approx(colors["bg"]), id + ": existing main background updates to race")
	var options_style: StyleBoxFlat = client.options_panel.get_parent().get_theme_stylebox("panel")
	_expect(options_style.bg_color.is_equal_approx(colors["panel"]), id + ": existing settings panel updates to race")
	_expect(client.theme.get_color("font_color", "Label").is_equal_approx(colors["text"]), id + ": inherited text theme updates to race")
	_expect(client.galaxy_map.get("_palette")["accent"].is_equal_approx(accent), id + ": map chrome receives the same race accent")
	var nav_caption: Label = client.nav_buttons[client.current_tab].get_meta("caption")
	_expect(nav_caption.get_theme_color("font_color").is_equal_approx(accent), id + ": active navigation follows the current race")
	_expect(client.resource_labels["fuel"]["count"].get_theme_color("font_color").is_equal_approx(Color("ffc56f")), id + ": resource warning retains its distinct semantic colour")


func _dynamic_palette_check(id: String) -> void:
	client._open_fleet_missions()
	client.mission_picker.open()
	await _settle()
	_expect(client.mission_picker.is_open(), id + ": mission selection opens shared touch modal")
	if client.mission_picker.is_open():
		var style: StyleBoxFlat = client.mission_picker._panel.get_theme_stylebox("panel")
		_expect(style.bg_color.is_equal_approx(RaceTheme.color(Color("14291d"))), id + ": newly created choice panel uses racial fill")
		_expect(style.border_color.is_equal_approx(RaceTheme.color(Color("66896d"))), id + ": newly created choice panel uses racial outline")
		var issues: Array[String] = []
		_bounds(client.mission_picker._panel, client.mission_picker._panel.get_global_rect(), issues)
		_expect(issues.is_empty(), id + ": choice modal fits mobile width")
		client.mission_picker.close()
	await _settle()
	client._open_release_panel("account")
	await _settle()
	_expect(client.release_panel.visible and client.release_panel.get_child(0).color.is_equal_approx(RaceTheme.palette(id)["bg"]), id + ": existing account overlay background follows race")
	var action: Button = client.release_panel.buttons[0]
	var action_style: StyleBoxFlat = action.get_theme_stylebox("normal")
	_expect(action_style.bg_color.is_equal_approx(RaceTheme.color(Color("2b4f36"))), id + ": new account action uses racial button fill")
	_expect(client.release_panel.status.get_theme_color("font_color").is_equal_approx(RaceTheme.color(Color("a5d5ac"))), id + ": new account status uses racial text accent")
	client._close_release_panel()
	await _settle()


func _race_test(id: String, fixture: Dictionary) -> void:
	client._apply_state(fixture["improved"])
	client._open_fleet_missions()
	await _settle()
	_palette_check(id)
	await _dynamic_palette_check(id)
	_expect(client.current_tab == 2 and client.fleet_mode == 0 and client.fleet_mode_bar.is_visible_in_tree(), id + ": fleet opens with reachable mode switch")
	_expect(client.fleet_mode_buttons[0].text == "Misje" and client.fleet_mode_buttons[1].text == "Budowa", id + ": two clear mode captions")
	_expect(not client.tabs[2].is_ancestor_of(client.fleet_mode_bar), id + ": fleet switch is outside scrolling content")
	var build_badges: int = 0
	var research_badges: int = 0
	for entry: Dictionary in fixture["improved"]["catalog"]["buildings"]:
		if bool(entry.get("unique", false)):
			build_badges += 1
			var badge: Label = client.building_rows[entry["key"]]["badge"]
			_expect(not badge.visible and badge.text.is_empty(), id + ": no redundant unique-building badge on " + str(entry["key"]))
	for entry: Dictionary in fixture["improved"]["catalog"]["research"]:
		if bool(entry.get("unique", false)):
			research_badges += 1
			var badge: Label = client.research_rows[entry["key"]]["badge"]
			_expect(badge.visible and badge.text == "BADANIE RASY", id + ": research badge still identifies " + str(entry["key"]))
	_expect(build_badges == 3 and research_badges >= 1, id + ": real fixture covers racial buildings and research")
	# Prepare a legitimate server preview. View changes must never send ships or erase it.
	client._prepare_planet_mission(str(fixture["colony_payload"]["target_id"]), 1)
	for key: String in client.SHIP_KEYS:
		client.fleet_inputs[key].value = 1 if key == "colonizer" else 0
	client.ship_rows["scout"]["amount"].value = 3
	client._preview_fleet()
	client.request_kind = "preview"
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify(fixture["colony_preview"]).to_utf8_buffer())
	_expect(client.quote_ready and not client.send_button.disabled, id + ": real server quote accepted before view changes")
	var fingerprint: String = client._fleet_fingerprint()
	var quote_text: String = client.quote_label.text
	client.intercepted_requests.clear()
	for width: int in [720, 600]:
		root.content_scale_size = Vector2i(width, 1280)
		root.size = Vector2i(width, 1280)
		for mode: int in [1, 0]:
			client.fleet_mode_buttons[mode].pressed.emit()
			await _settle()
			_expect(client.fleet_mode == mode and client.fleet_missions_view.visible == (mode == 0) and client.fleet_build_view.visible == (mode == 1), id + ": only selected fleet content visible at %dpx mode %d" % [width, mode])
			_expect(client.fleet_mode_buttons[mode].button_pressed and not client.fleet_mode_buttons[1 - mode].button_pressed, id + ": mode selection has one active button")
			_expect(client.tabs[2].scroll_vertical == 0, id + ": selected fleet mode starts at top")
			_expect(client._fleet_fingerprint() == fingerprint and client.ship_rows["scout"]["amount"].value == 3, id + ": mission and shipyard quantities survive view changes")
			_expect(client.quote_ready and client.quote_label.text == quote_text and not client.send_button.disabled, id + ": accepted route quote survives view changes")
			_expect(client.intercepted_requests.is_empty(), id + ": mode toggle performs no network action")
			var issues: Array[String] = []
			_bounds(client.tabs[2], client.tabs[2].get_global_rect(), issues)
			_bounds(client.fleet_mode_bar, client.fleet_mode_bar.get_global_rect(), issues)
			_expect(issues.is_empty(), id + ": fleet width fits %dpx mode %d: %s" % [width, mode, issues])
			_expect(client.fleet_mode_buttons[mode].size.x >= 200 and client.fleet_mode_buttons[mode].size.y >= 64, id + ": mode controls remain comfortable touch targets")
			_expect(client.tabs[2].get_global_rect().position.y >= client.fleet_mode_bar.get_global_rect().end.y, id + ": scroll content begins below fixed mode panel")
			var panel_position: Vector2 = client.fleet_mode_bar.global_position
			client.tabs[2].scroll_vertical = 500
			await _settle()
			_expect(client.tabs[2].scroll_vertical > 100 and client.fleet_mode_bar.global_position.is_equal_approx(panel_position), id + ": panel stays pinned while real content scrolls")
			_expect(client.fleet_mode_bar.is_visible_in_tree(), id + ": mode switch still reachable when scrolled")
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client._set_fleet_mode(1)
	for other_tab: int in [0, 1, 3, 4]:
		client._open_tab(other_tab)
		await _settle()
		_expect(not client.fleet_mode_bar.is_visible_in_tree(), id + ": other navigation hides fleet bar on tab " + str(other_tab))
		client._open_tab(2)
		await _settle()
		_expect(client.fleet_mode == 1 and client.fleet_build_view.is_visible_in_tree() and client.fleet_mode_bar.is_visible_in_tree(), id + ": returning to fleet remembers construction view")
	# Hunting scarce crystals is map navigation, distinct from explicitly preparing a mission.
	var swarm_target: String = str(client.state["alien"]["recommended_target_id"])
	var swarm_system: Dictionary = {}
	for system: Dictionary in client.state["galaxy"]:
		for planet: Dictionary in system["planets"]:
			if str(planet["id"]) == swarm_target and str(planet["owner_type"]) == "alien":
				swarm_system = system
	_expect(not swarm_system.is_empty(), id + ": server fixture recommends a known Swarm planet")
	client._open_skill_wheel()
	await _settle()
	var hunt: Button = _button_named(client.skill_overlay, "Zdobądź kryształy Roju")
	_expect(client.skill_open and hunt != null and hunt.is_visible_in_tree(), id + ": crystal hunt is reachable inside the skill wheel")
	client.intercepted_requests.clear()
	if hunt != null:
		hunt.pressed.emit()
	await _settle()
	_expect(not client.skill_open and client.current_tab == 1 and client.galaxy_overview.is_visible_in_tree(), id + ": crystal hunt closes wheel and opens the galaxy map")
	_expect(client.selected_system == str(swarm_system.get("id", "")) and client.galaxy_map.get("selected_id") == client.selected_system, id + ": both map and planet list select the Swarm system")
	var point: Vector2 = client.galaxy_map.call("_screen_position", swarm_system)
	var map_area: Rect2 = client.galaxy_map.call("_visible_rect")
	_expect(client.galaxy_map.call("get_zoom") >= 2.0 and map_area.has_point(point), id + ": Swarm location is visible in the focused map")
	_expect(client.tabs[1].scroll_vertical == 0 and client.galaxy_toggle.text == "Układ" and not client.fleet_mode_bar.is_visible_in_tree(), id + ": map starts at top with system-view action and no fleet form")
	_expect(client._fleet_fingerprint() == fingerprint and client.ship_rows["scout"]["amount"].value == 3 and client.fleet_mode == 1, id + ": crystal hunt preserves mission target, quantities and fleet subview")
	_expect(client.quote_ready and client.quote_label.text == quote_text and not client.send_button.disabled, id + ": crystal hunt preserves the accepted route quote")
	_expect(client.intercepted_requests.is_empty(), id + ": crystal hunt never previews or dispatches a fleet")
	await _capture(id + "_swarm_location")
	if id == "symbionts":
		client.state["alien"]["recommended_target_id"] = "removed-planet"
		client._hunt_swarm()
		await _settle()
		var fallback: Dictionary = client._swarm_location()
		_expect(not fallback.is_empty() and client.selected_system == str(fallback.get("system_id", "")) and client.galaxy_overview.is_visible_in_tree(), "Stale recommendation falls back to a real known Swarm location")
		var original_galaxy: Array = client.state["galaxy"].duplicate(true)
		for system: Dictionary in client.state["galaxy"]:
			for planet: Dictionary in system["planets"]:
				if str(planet["owner_type"]) == "alien":
					planet["owner_type"] = "empty"
		client._hunt_swarm()
		await _settle()
		_expect(client._swarm_location().is_empty() and client.galaxy_overview.is_visible_in_tree() and is_equal_approx(client.galaxy_map.call("get_zoom"), 1.0), "No known Swarm opens the full galaxy without inventing a target")
		_expect(client.intercepted_requests.is_empty() and client._fleet_fingerprint() == fingerprint and client.quote_ready, "Missing or stale Swarm targets still preserve the planned fleet and send no requests")
		client.state["galaxy"] = original_galaxy
		client.state["alien"]["recommended_target_id"] = swarm_target
	# Galaxy selection and explicit mission deep links override remembered construction mode.
	var target: String = str(fixture["colony_payload"]["target_id"])
	client.intercepted_requests.clear()
	client._target_from_map(target, "empty", false)
	await _settle()
	_expect(client.current_tab == 2 and client.fleet_mode == 0 and client.mission_picker.selected == 1 and client.selected_target == target, id + ": galaxy empty-planet selection opens colony mission form")
	_expect(client.intercepted_requests.is_empty() and not client.quote_ready, id + ": galaxy selection sends no fleet and requires fresh route preview")
	client._set_fleet_mode(1)
	client._prepare_planet_mission(target, 0)
	await _settle()
	_expect(client.fleet_mode == 0 and client.fleet_missions_view.is_visible_in_tree() and client.mission_picker.selected == 0, id + ": explicit scout action opens Missions view")
	_expect(client.intercepted_requests.is_empty(), id + ": prefilled scout action is navigation only")
	await _capture(id + "_fleet_missions")
	client._set_fleet_mode(1)
	await _capture(id + "_fleet_construction")
	client._open_tab(0)
	await _capture(id + "_planet")
	client._open_tab(1)
	client.galaxy_overview.visible = true
	client.tabs[1].scroll_vertical = 0
	client.galaxy_map.call("reset_view")
	await _capture(id + "_galaxy")
	client._set_fleet_mode(1)
	client._reset_world()
	_expect(client.fleet_mode == 0 and client.fleet_missions_view.visible and not client.fleet_build_view.visible, id + ": clearing account resets fleet mode for next login")


func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Pass fixture from tests/make_unique_building_fixture.py")
		quit(2)
		return
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if args.size() > 1 and DisplayServer.get_name() != "headless":
		screenshots = args[1]
		DirAccess.make_dir_recursive_absolute(screenshots)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.session_token = "offline-test-token"
	await _settle()
	for id: String in RACES:
		await _race_test(id, fixture["races"][id])
	# Repeat account transitions without a reset to catch stale colours in existing controls.
	for id: String in ["automatons", "zetans", "symbionts", "zetans"]:
		client._apply_state(fixture["races"][id]["improved"])
		await _settle()
		_palette_check(id)
	_expect(client.http == null and client.poll_timer == null, "No live network requests or polling")
	print("0.3.3 UI: %d checks, %d failures; offline transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
