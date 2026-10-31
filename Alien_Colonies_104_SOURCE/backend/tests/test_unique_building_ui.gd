extends SceneTree
## Real server snapshots and real mobile controls; all requests are intercepted.
## godot --headless --path . --script tests/test_unique_building_ui.gd -- fixture.json
## Optional second argument: directory for rendered screenshots (requires display).

const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
const ArtLibrary = preload("res://client/scripts/art_library.gd")
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
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


func _width_issues(node: Node, bounds: Rect2, issues: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var rect: Rect2 = child.get_global_rect()
			if rect.position.x < bounds.position.x - 1 or rect.end.x > bounds.end.x + 1:
				issues.append(str(child.name) + " " + str(rect))
			_width_issues(child, bounds, issues)


func _capture(name_value: String, panel: Control) -> void:
	if screenshots.is_empty():
		return
	client.tabs[0].scroll_vertical = maxi(0, roundi(panel.position.y + client.unique_building_section.position.y))
	await _settle()
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(screenshots.path_join(name_value + ".png"))


func _race_test(id: String, fixture: Dictionary) -> void:
	client._apply_state(fixture["chosen"])
	client._open_tab(0)
	await _settle()
	var catalog: Array = fixture["chosen"]["catalog"]["buildings"]
	_expect(client.unique_building_section.visible and client.unique_building_list.get_child_count() == 3,
		id + ": exactly three unique buildings are separated from infrastructure")
	_expect(client.building_rows.size() == 9 and client.building_list.get_child_count() == 6,
		id + ": all six basic roles remain available alongside new buildings")
	_expect(client.building_heading.get_index() < client.building_list.get_index()
		and client.building_list.get_index() < client.unique_building_section.get_index()
		and client.unique_building_section.get_index() == client.tab_bodies[0].get_child_count() - 1,
		id + ": all infrastructure precedes the final racial-building section")
	_expect(client.unique_building_heading.text.contains(fixture["chosen"]["race"]["name"]),
		id + ": the section identifies the selected race")
	_expect(client.tabs[0].get_script() == TouchScroll,
		id + ": unique cards retain shared touch scrolling")
	var unique_keys: Array[String] = []
	for entry: Dictionary in catalog:
		var key: String = entry["key"]
		var controls: Dictionary = client.building_rows[key]
		if not bool(entry.get("unique", false)):
			_expect(not controls["badge"].visible and not controls["effects"].visible,
				id + "/" + key + ": basic buildings receive no invented special effect")
			continue
		unique_keys.append(key)
		_expect(controls["panel"].get_parent() == client.unique_building_list and controls["panel"].get_index() == unique_keys.size() - 1,
			id + "/" + key + ": ordering follows this race's authoritative catalog")
		_expect(controls["art"].texture != null and controls["art"].texture.resource_path.ends_with(str(entry["art_key"]) + ".webp"),
			id + "/" + key + ": large card loads its own original racial building art")
		_expect(not controls["badge"].visible and controls["badge"].text.is_empty() and controls["level"].text == "Poziom 0 / 5",
			id + "/" + key + ": badge removed while five-level progression remains visible")
		_expect(controls["effect_next"].visible and controls["effect_next"].text.contains(entry["effect_next"]),
			id + "/" + key + ": next-level gameplay effect is visible without opening details")
		var panel_style: StyleBoxFlat = controls["panel"].get_theme_stylebox("panel")
		_expect(panel_style.border_color == Color(client._race_building_accent()),
			id + "/" + key + ": card border uses the selected race's accent")
		_expect(controls["requirements"].get_child_count() == entry["requirements"].size(),
			id + "/" + key + ": all prerequisites have short dedicated labels")
		for requirement: Dictionary in entry["requirements"]:
			if not bool(requirement["met"]):
				_expect(controls["action"].disabled, id + "/" + key + ": unmet prerequisites disable construction")

	for width: int in [720, 600]:
		root.content_scale_size = Vector2i(width, 1280)
		root.size = Vector2i(width, 1280)
		await _settle()
		var issues: Array[String] = []
		_width_issues(client.unique_building_section, client.tabs[0].get_global_rect(), issues)
		_expect(issues.is_empty(), id + ": special cards fit %dpx without overflow: %s" % [width, issues])
		_expect(client.unique_building_section.get_global_rect().position.y >= client.building_list.get_global_rect().end.y,
			id + ": rendered racial buildings stay below all infrastructure at " + str(width))
		for key: String in unique_keys:
			var controls: Dictionary = client.building_rows[key]
			_expect(controls["action"].size.x >= 176 and controls["action"].size.y >= 72,
				id + "/" + key + ": comfortable build target at width " + str(width))
			var whole_tokens: bool = true
			for resource: String in client.RESOURCE_KEYS:
				var label: Label = controls["costs"][resource]["amount"]
				whole_tokens = whole_tokens and label.get_line_count() == 1
			_expect(whole_tokens, id + "/" + key + ": prices never wrap into vertical digits at " + str(width))
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client._apply_state(fixture["ready"])
	await _settle()
	var first_key: String = fixture["first_key"]
	var instance_id: int = client.building_rows[first_key]["panel"].get_instance_id()
	client.tabs[0].scroll_vertical = 230
	var scroll_value: int = client.tabs[0].scroll_vertical
	client._apply_state(fixture["ready"].duplicate(true))
	await _settle()
	_expect(client.building_rows[first_key]["panel"].get_instance_id() == instance_id and client.tabs[0].scroll_vertical == scroll_value,
		id + ": polling preserves controls and scroll position")
	_expect(client.unique_building_section.get_index() > client.building_list.get_index(),
		id + ": polling never moves racial buildings above infrastructure")
	client.intercepted_requests.clear()
	client.building_rows[first_key]["action"].pressed.emit()
	_expect(client.intercepted_requests.size() == 1 and client.intercepted_requests[0]["payload"].get("key") == first_key
		and client.intercepted_requests[0]["payload"].get("type") == "build",
		id + ": build button dispatches the unique key through the existing action contract")
	client._apply_state(fixture["active"])
	await _settle()
	var active: Dictionary = client.building_rows[first_key]
	_expect(active["progress_panel"].visible and active["progress_bar"].value > 0 and active["progress_bar"].value < 100,
		id + ": a genuine unique-building job shows live progress")
	_expect(client.active_project.visible and client.queue_name.contains(active["heading"].text),
		id + ": persistent project bar identifies the unique structure")
	client._apply_state(fixture["improved"])
	await _settle()
	for key: String in unique_keys:
		var controls: Dictionary = client.building_rows[key]
		_expect(controls["level"].text == "Poziom 2 / 5" and controls["effect_current"].text.begins_with("Teraz:")
			and controls["effect_next"].text.begins_with("Następny:"),
			id + "/" + key + ": completed levels show current and next effect")
	client.selected_target = fixture["colony_payload"]["target_id"]
	client.mission_picker.select(1)
	for key: String in client.SHIP_KEYS:
		client.fleet_inputs[key].value = 1 if key == "colonizer" else 0
	client._preview_fleet()
	client.request_kind = "preview"
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify(fixture["colony_preview"]).to_utf8_buffer())
	_expect(client.quote_ready and client.quote_label.text.contains(str(fixture["colony_preview"]["message"])),
		id + ": route preview shows the authoritative server note before dispatch")
	if id == "symbionts":
		_expect(client.quote_label.text.contains("na poziomie 3"), "Pioneer nursery level 2 previews economic buildings at level 3")
		client._apply_state(fixture["colony_upgraded"])
		_expect(not client.quote_ready and client.send_button.disabled, "A completed nursery upgrade invalidates the old colony quote")
		client._apply_state(fixture["improved"])
	await _capture(id + "_unique_buildings", client.building_rows[first_key]["panel"])
	if id == "automatons":
		client._open_tab(2)
		var ship: Dictionary = client.ship_rows["scout"]
		var entry: Dictionary = ship["entry"]
		for amount: int in [1, 2, 3, 20]:
			ship["amount"].value = amount
			var reduction: float = minf(float(entry["batch_time_reduction_cap"]), float(entry["batch_time_reduction_per_extra"]) * (amount - 1))
			var expected: float = maxf(1, ceilf(float(entry["seconds"]) * amount * (1 - reduction)))
			_expect(ship["time"].text == client._duration(expected), "Automaton batch quote matches server rounding for " + str(amount) + " ships")
			_expect(ship["batch_effect"].visible == (amount > 1), "Batch speed benefit is shown only when applied: " + str(amount))
		ship["amount"].value = 1
	if id == "zetans":
		var research: Dictionary = client.research_rows["weapons"]
		_expect(research["batch_effect"].visible and research["batch_effect"].text.contains("zwykłych kryształów"),
			"Zetan research preview shows the ordinary-crystal refund separately from Swarm currency")
	client._open_tab(0)
	client._apply_state(fixture["maximum"])
	await _settle()
	var maximum: Dictionary = client.building_rows[first_key]
	_expect(maximum["action"].disabled and maximum["action"].text == "Maksimum" and not maximum["effect_next"].visible,
		id + ": maxed structures cannot advertise a nonexistent sixth level")
	var reduced: Dictionary = fixture["ready"].duplicate(true)
	for index: int in range(reduced["catalog"]["buildings"].size()):
		if reduced["catalog"]["buildings"][index]["key"] == first_key:
			reduced["catalog"]["buildings"].remove_at(index)
			break
	client._apply_state(reduced)
	await _settle()
	_expect(not client.building_rows.has(first_key) and client.building_rows.size() == 8 and client.unique_building_list.get_child_count() == 2,
		id + ": removed catalog entries are removed from the dictionary and visual tree")
	client._apply_state(fixture["ready"])
	await _settle()
	_expect(client.unique_building_list.get_child(0) == client.building_rows[first_key]["panel"],
		id + ": reintroduced entries regain their correct order")
	_expect(client.unique_building_section.get_index() > client.building_list.get_index(),
		id + ": reintroduced racial cards remain after infrastructure")
	client.state["speed"] = 1.0
	client._update_clock()
	_expect(client.clock_label.text.begins_with("Czas • ") and not client.clock_label.text.contains("×"),
		id + ": normal game time shows no test multiplier")
	client.state["speed"] = 2.0
	client._update_clock()
	_expect(client.clock_label.text.begins_with("Czas ×2 • "),
		id + ": a nonstandard server's real time multiplier is never hidden")


func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Supply the fixture produced by tests/make_unique_building_fixture.py")
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
	client.session_token = "offline-test-session"
	await _settle()
	for race: String in RACES:
		await _race_test(race, fixture["races"][race])
	client._apply_state(fixture["legacy"])
	await _settle()
	_expect(not client.unique_building_section.visible and client.unique_building_list.get_child_count() == 0
		and client.building_rows.size() == 6 and client.building_list.get_child_count() == 6,
		"A genuine older server restores its six-building interface with no stale racial cards")
	_expect(client.building_heading.text == "Rozbudowa kolonii", "Legacy servers keep their existing heading")
	_expect(ArtLibrary.texture("races/zetans/world_root") == null and ArtLibrary.texture("races/symbionts/serial_forge") == null,
		"Art whitelist rejects structures assigned to the wrong race")
	_expect(client.http == null and client.poll_timer == null, "UI test never creates a real network request or poll timer")
	print("Unique building UI: %d checks, %d failures; offline transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
