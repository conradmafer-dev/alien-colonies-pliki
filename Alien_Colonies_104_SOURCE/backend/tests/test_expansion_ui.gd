extends SceneTree
## Authoritative 0.5.0 catalogs in real mobile controls, without HTTP or sessions.
## Generate fixture with make_expansion_ui_fixture.py, then pass its path after --.

const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
const ArtLibrary = preload("res://client/scripts/art_library.gd")
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
const MobileQuantity = preload("res://client/scripts/mobile_quantity.gd")
const NEW_SHIPS: Array[String] = ["interceptor", "siege", "freighter"]
var client: MobileSmoke.OfflineClient
var checks: int = 0
var failures: Array[String] = []


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, caption: String) -> void:
	checks += 1
	if not condition:
		failures.append(caption)
		push_error(caption)


func _settle() -> void:
	for _frame: int in range(8):
		await process_frame


func _width_issues(node: Node, bounds: Rect2, issues: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var rect: Rect2 = child.get_global_rect()
			if rect.position.x < bounds.position.x - 1 or rect.end.x > bounds.end.x + 1:
				issues.append(str(child.name) + " " + str(rect))
			_width_issues(child, bounds, issues)


func _check_race(id: String, fixture: Dictionary) -> void:
	client._apply_state(fixture["locked"])
	await _settle()
	_expect(client.building_rows.size() == 12 and client.research_rows.size() == 6 and client.ship_rows.size() == 8,
		id + ": full 12/6/8 catalog is visible")
	_expect(client.unique_building_list.get_child_count() == 6 and client.building_list.get_child_count() == 6
		and client.unique_building_section.get_index() > client.building_list.get_index(),
		id + ": all six racial buildings remain below infrastructure")
	_expect(client.fleet_inputs.size() == 8 and client.fleet_selection_list.get_child_count() == 8,
		id + ": mission selector supports all eight classes")
	for key: String in NEW_SHIPS:
		var controls: Dictionary = client.ship_rows[key]
		_expect(controls["action"].disabled and controls["requirements"].get_child_count() >= 2,
			id + "/" + key + ": locked ship advertises real prerequisites")
		_expect(controls["role"].visible and not controls["role"].text.is_empty(),
			id + "/" + key + ": new role is visible on the card")
		var mixed: bool = false
		for requirement: Dictionary in controls["entry"].get("requirements", []):
			mixed = mixed or requirement.get("group") == "research"
		_expect(mixed, id + "/" + key + ": research prerequisites are not treated as buildings")
		_expect(client.fleet_inputs[key].get_script() == MobileQuantity
			and client.fleet_inputs[key].edit_gate != null,
			id + "/" + key + ": quantity reuses swipe-safe tap-to-edit control")
	client._apply_state(fixture["ready"])
	await _settle()
	for key: String in NEW_SHIPS:
		_expect(not client.ship_rows[key]["action"].disabled,
			id + "/" + key + ": meeting prerequisites unlocks construction")
	for kind: String in ["buildings", "research", "ships"]:
		var rows: Dictionary = client.building_rows if kind == "buildings" else client.research_rows if kind == "research" else client.ship_rows
		for entry: Dictionary in fixture["ready"]["catalog"][kind]:
			var controls: Dictionary = rows[entry["key"]]
			_expect(controls["art"].texture != null and controls["art"].texture.resource_path.ends_with(str(entry["art_key"]) + ".webp"),
				id + "/" + str(entry["key"]) + ": dedicated race artwork loads")
			var art: Texture2D = controls["art"].texture
			_expect(art != null and art.get_width() >= 512 and art.get_height() >= 512,
				id + "/" + str(entry["key"]) + ": illustration has usable phone resolution")
			for resource: String in client.RESOURCE_KEYS:
				_expect(controls["costs"][resource]["amount"].get_line_count() <= 1,
					id + "/" + str(entry["key"]) + ": " + resource + " cost stays horizontal")
	for tab: int in [0, 2, 3]:
		client._open_tab(tab)
		if tab == 2:
			client._set_fleet_mode(1)
		await _settle()
		var issues: Array[String] = []
		_width_issues(client.tab_bodies[tab], client.tabs[tab].get_global_rect(), issues)
		_expect(issues.is_empty(), id + ": expansion cards fit a 600px phone on tab %d: %s" % [tab, issues])
		_expect(client.tabs[tab].get_script() == TouchScroll, id + ": expanded list retains touch scrolling on tab " + str(tab))
	client._open_fleet_missions()
	await _settle()
	for key: String in client.fleet_inputs:
		client.fleet_inputs[key].value = 2 if key in NEW_SHIPS else 0
	client.tabs[2].scroll_vertical = 450
	await _settle()
	var previous_scroll: int = client.tabs[2].scroll_vertical
	var selector_id: int = client.fleet_inputs["siege"].get_instance_id()
	var card_id: int = client.ship_rows["siege"]["panel"].get_instance_id()
	var texture: Texture2D = client.ship_rows["siege"]["art"].texture
	client._apply_state(fixture["ready"].duplicate(true))
	await _settle()
	_expect(client.fleet_inputs["siege"].get_instance_id() == selector_id
		and client.ship_rows["siege"]["panel"].get_instance_id() == card_id
		and client.ship_rows["siege"]["art"].texture == texture,
		id + ": polling retains controls and loaded art")
	_expect(client.tabs[2].scroll_vertical == previous_scroll and client.fleet_inputs["siege"].value == 2,
		id + ": polling retains scroll position and selected quantity")
	client.intercepted_requests.clear()
	client.selected_target = str(fixture["ready"]["galaxy"][0]["planets"][0]["id"])
	client._preview_fleet()
	_expect(client.intercepted_requests.size() == 1, id + ": route preview uses intercepted transport")
	if not client.intercepted_requests.is_empty():
		var ships: Dictionary = client.intercepted_requests.back()["payload"].get("ships", {})
		_expect(ships.size() == 8 and ships.get("interceptor") == 2 and ships.get("siege") == 2 and ships.get("freighter") == 2,
			id + ": actual mission request contains all selected new classes")
	client._apply_state(fixture["maximum"])
	await _settle()
	for kind: String in ["buildings", "research"]:
		var rows: Dictionary = client.building_rows if kind == "buildings" else client.research_rows
		for entry: Dictionary in fixture["maximum"]["catalog"][kind]:
			if int(entry.get("max_level", 0)) == 0:
				continue
			var controls: Dictionary = rows[entry["key"]]
			_expect(controls["action"].text == "Maksimum" and controls["action"].disabled and not controls["effect_next"].visible,
				id + "/" + str(entry["key"]) + ": level cap has no nonexistent next upgrade")
	var reduced: Dictionary = fixture["ready"].duplicate(true)
	reduced["catalog"]["ships"] = reduced["catalog"]["ships"].filter(func(entry: Dictionary) -> bool: return entry["key"] != "siege")
	client._apply_state(reduced)
	await _settle()
	_expect(not client.fleet_inputs.has("siege") and not client.ship_rows.has("siege") and not client._fleet_payload()["ships"].has("siege"),
		id + ": removed server classes leave no stale card, selector or payload")
	_expect(client._ships_text({"siege": 3, "future_ship": 7}, {"siege": "Tarany", "future_ship": "Nowa flota"}).contains("Nowa flota ×7"),
		id + ": reports preserve future or removed ship classes")
	if id == "zetans":
		var future: Dictionary = fixture["ready"].duplicate(true)
		var extra: Dictionary = client.ship_rows["interceptor"]["entry"].duplicate(true)
		extra["key"] = "future_ship"
		extra["name"] = "Nowa klasa serwera"
		future["catalog"]["ships"].append(extra)
		future["ships"]["future_ship"] = 3
		client._apply_state(future)
		await _settle()
		_expect(client.fleet_inputs.has("future_ship") and client.fleet_names["future_ship"].text == "Nowa klasa serwera",
			"Future server class creates a named selector without changing client constants")
		client.fleet_inputs["future_ship"].value = 2
		_expect(client._fleet_payload()["ships"].get("future_ship") == 2,
			"Future server class participates in the common mission payload")
		client._apply_state(fixture["ready"])
		await _settle()
		_expect(not client.fleet_inputs.has("future_ship"), "Catalog rollback removes the future selector")
	client._open_tab(0)
	await _settle()
	client.tabs[0].scroll_vertical = 400
	client.nav_buttons[0].pressed.emit()
	await _settle()
	_expect(client.tabs[0].scroll_vertical == 0, id + ": Planeta still returns to the top")


func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Pass the fixture from make_expansion_ui_fixture.py")
		quit(2)
		return
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not fixture.get("races", {}).get("zetans", {}).has("locked"):
		push_error("Invalid expansion fixture; generate make_expansion_ui_fixture.py output")
		quit(2)
		return
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(600, 1280)
	root.size = Vector2i(600, 1280)
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.session_token = "offline-expansion-ui"
	await _settle()
	_expect(client.CLIENT_VERSION_CODE == 28 and client.CLIENT_VERSION_NAME == "0.6.1", "Expansion version and Android code")
	for id: String in ["zetans", "symbionts", "automatons"]:
		await _check_race(id, fixture["races"][id])
	_expect(ArtLibrary.texture("races/zetans/living_vault") == null, "Wrong-race art remains rejected")
	_expect(client.http == null and client.poll_timer == null, "Expansion tests never contact the hosted server")
	print("Expansion UI: %d checks, %d failures; offline transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
