extends SceneTree
## Actual server contracts, real touch controls, and intercepted local transport.
## godot --headless --path . --script tests/test_racial_research_ui.gd -- fixture.json
## Optional second argument: screenshot directory (requires a real renderer).

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


func _capture(id: String) -> void:
	if screenshots.is_empty():
		return
	client.tabs[3].scroll_vertical = maxi(0, roundi(client.unique_research_section.position.y))
	await _settle()
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(screenshots.path_join(id + "_racial_research.png"))


func _race_test(id: String, fixture: Dictionary) -> void:
	var key: String = fixture["key"]
	client._apply_state(fixture["chosen"])
	client._open_tab(3)
	await _settle()
	var controls: Dictionary = client.research_rows[key]
	var entry: Dictionary = controls["entry"]
	_expect(client.unique_research_section.visible and client.unique_research_list.get_child_count() == 1,
		id + ": one technology belongs to the selected race")
	_expect(client.research_rows.size() == 3 and client.research_list.get_child_count() == 2,
		id + ": both ordinary research types remain alongside racial research")
	_expect(controls["panel"].get_parent() == client.unique_research_list
		and client.unique_research_section.get_index() < client.research_list.get_index(),
		id + ": research stays in its own section ahead of ordinary technologies")
	_expect(client.unique_building_list.get_child_count() == 3 and client.building_list.get_child_count() == 6,
		id + ": shared card code never puts racial research among buildings")
	_expect(client.skill_entry.visible and client.skill_entry_button.visible,
		id + ": the established skill wheel remains accessible")
	_expect(client.unique_research_heading.text.contains(fixture["chosen"]["race"]["name"]),
		id + ": section names the selected race")
	_expect(client.tabs[3].get_script() == TouchScroll,
		id + ": racial research uses the common touch-scrolling component")
	_expect(controls["badge"].visible and controls["badge"].text == "BADANIE RASY",
		id + ": badge clearly distinguishes research from construction")
	_expect(controls["art"].texture != null and controls["art"].texture.resource_path.ends_with(str(entry["art_key"]) + ".webp"),
		id + ": card loads its original racial research illustration")
	_expect(controls["level"].text == "Poziom 0 / 5" and controls["effect_current"].text == "Jeszcze nie zbadano",
		id + ": unresearched technology shows its five-level progression")
	_expect(controls["effect_next"].visible and controls["effect_next"].text.contains(entry["effect_next"]),
		id + ": first attainable effect is visible without opening a description")
	var style: StyleBoxFlat = controls["panel"].get_theme_stylebox("panel")
	_expect(style.border_color == Color(client._race_building_accent()), id + ": technology keeps its race colour")
	_expect(controls["requirements"].get_child_count() == 2 and controls["action"].disabled,
		id + ": both prerequisite buildings are visible and gate the initial technology")
	client._apply_state(fixture["lab_only"])
	await _settle()
	_expect(controls["action"].disabled and controls["requirements"].get_child(0).text.begins_with("✓")
		and controls["requirements"].get_child(1).text.begins_with("Wymaga:"),
		id + ": a laboratory alone cannot bypass the racial-building requirement")
	client._apply_state(fixture["ready"])
	await _settle()
	_expect(not controls["action"].disabled and controls["action"].text == "Badaj",
		id + ": satisfying both prerequisites unlocks research")
	for width: int in [720, 600]:
		root.content_scale_size = Vector2i(width, 1280)
		root.size = Vector2i(width, 1280)
		await _settle()
		var issues: Array[String] = []
		_width_issues(client.unique_research_section, client.tabs[3].get_global_rect(), issues)
		_expect(issues.is_empty(), id + ": cards and requirement labels fit %dpx: %s" % [width, issues])
		_expect(controls["action"].size.x >= 176 and controls["action"].size.y >= 72,
			id + ": comfortable research tap target at " + str(width))
		for resource: String in client.RESOURCE_KEYS:
			_expect(controls["costs"][resource]["amount"].get_line_count() == 1,
				id + ": research prices remain whole horizontal numbers at " + str(width))
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	await _settle()
	var instance_id: int = controls["panel"].get_instance_id()
	client.tabs[3].scroll_vertical = 240
	var previous_scroll: int = client.tabs[3].scroll_vertical
	client._apply_state(fixture["ready"].duplicate(true))
	await _settle()
	_expect(client.research_rows[key]["panel"].get_instance_id() == instance_id and client.tabs[3].scroll_vertical == previous_scroll,
		id + ": polling preserves the card and scroll position")
	client.intercepted_requests.clear()
	controls["action"].pressed.emit()
	_expect(client.intercepted_requests.size() == 1 and client.intercepted_requests[0]["payload"].get("key") == key
		and client.intercepted_requests[0]["payload"].get("type") == "research",
		id + ": research button dispatches the authoritative technology key")
	client._apply_state(fixture["active"])
	await _settle()
	_expect(controls["progress_panel"].visible and controls["progress_bar"].value > 0 and controls["progress_bar"].value < 100,
		id + ": a real research job displays its running progress")
	_expect(client.active_project.visible and client.queue_name.contains(controls["heading"].text),
		id + ": sticky project bar names the active technology")
	_expect(client.research_rows["weapons"]["action"].disabled,
		id + ": other research respects the occupied shared queue")
	client._apply_state(fixture["completed"])
	await _settle()
	_expect(controls["level"].text == "Poziom 1 / 5" and not controls["progress_panel"].visible,
		id + ": real completion updates level and removes progress")
	client._apply_state(fixture["improved"])
	await _settle()
	_expect(controls["level"].text == "Poziom 2 / 5" and controls["effect_current"].text.begins_with("Teraz:")
		and controls["effect_next"].text.begins_with("Następny:"), id + ": subsequent levels show current and next effects")
	await _capture(id)
	await _check_production(id)
	client._open_tab(3)
	client._apply_state(fixture["maximum"])
	await _settle()
	_expect(controls["action"].disabled and controls["action"].text == "Maksimum" and not controls["effect_next"].visible,
		id + ": maximum research never advertises a sixth level")
	var reduced: Dictionary = fixture["ready"].duplicate(true)
	reduced["catalog"]["research"].remove_at(0)
	client._apply_state(reduced)
	await _settle()
	_expect(not client.research_rows.has(key) and not client.unique_research_section.visible
		and client.unique_research_list.get_child_count() == 0 and client.research_list.get_child_count() == 2,
		id + ": a removed server entry leaves no stale research card")
	client._apply_state(fixture["ready"])
	await _settle()
	_expect(client.unique_research_list.get_child(0) == client.research_rows[key]["panel"],
		id + ": a restored entry returns to the right research section")
	client._open_tab(0)
	await _settle()
	client.tabs[0].scroll_vertical = 400
	client.nav_buttons[0].pressed.emit()
	await _settle()
	_expect(client.tabs[0].scroll_vertical == 0, id + ": tapping Planeta still returns to the top")


func _check_production(id: String) -> void:
	client._open_tab(2)
	await _settle()
	for key: String in client.ship_rows:
		var ship: Dictionary = client.ship_rows[key]
		var entry: Dictionary = ship["entry"]
		_expect(ship["production_effect"].visible == (id == "symbionts"), id + "/" + key + ": only Symbiont production shows multiplication")
		if id == "symbionts":
			_expect(ship["production_effect"].text == "Namnażanie ×1,4", id + "/" + key + ": multiplier preserves fractional racial progress")
		if id == "zetans":
			_expect(ship["description"].text.contains("Prędkość: " + client._stat_number(float(entry["effective_speed"]))),
				id + "/" + key + ": speed displays the authoritative antigravity result without applying it twice")
		for amount: int in [1, 3, 20]:
			ship["amount"].value = amount
			_expect(ship["refund"].visible == (id == "automatons"), id + "/" + key + ": recycling refund visibility at batch " + str(amount))
			if id == "automatons":
				for resource: String in client.RESOURCE_KEYS:
					var expected: int = int(entry["cost"].get(resource, 0)) * amount / 10
					_expect(ship["refund_costs"][resource]["amount"].text == "+" + client._number(expected),
						id + "/" + key + ": preview floors the total batch refund for " + resource + "/" + str(amount))
		ship["amount"].value = 1
	for key: String in client.building_rows:
		_expect(client.building_rows[key]["refund"].visible == (id == "automatons"), id + "/" + key + ": building refund follows research progress")
	for key: String in client.research_rows:
		_expect(not client.research_rows[key]["refund"].visible, id + "/" + key + ": research never advertises construction recycling")
	if id == "automatons":
		root.content_scale_size = Vector2i(600, 1280)
		root.size = Vector2i(600, 1280)
		await _settle()
		var issues: Array[String] = []
		_width_issues(client.ship_list, client.tabs[2].get_global_rect(), issues)
		_expect(issues.is_empty(), "Recycling batch previews fit narrow mobile cards: " + str(issues))
		root.content_scale_size = Vector2i(720, 1280)
		root.size = Vector2i(720, 1280)


func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Supply the fixture from tests/make_racial_research_fixture.py")
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
	_expect(not client.unique_research_section.visible and client.unique_research_list.get_child_count() == 0
		and client.research_rows.size() == 2 and client.research_list.get_child_count() == 2,
		"A genuine legacy server keeps its original two research cards without stale racial entries")
	_expect(not client.unique_building_section.visible and client.building_rows.size() == 6,
		"Legacy compatibility also restores the original building layout")
	_expect(ArtLibrary.texture("races/zetans/recycling") == null and ArtLibrary.texture("races/automatons/multiplication") == null,
		"Asset whitelist rejects technologies assigned to the wrong race")
	_expect(client.http == null and client.poll_timer == null, "Research UI tests never contact a server or read sessions")
	print("Racial research UI: %d checks, %d failures; offline transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
