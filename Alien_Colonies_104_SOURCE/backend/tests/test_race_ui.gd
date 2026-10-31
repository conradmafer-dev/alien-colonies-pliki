extends SceneTree
## Real server fixtures + real client controls, with a local intercepted transport.
## godot --headless --path . --script tests/test_race_ui.gd -- /tmp/alien-colonies-races.json

const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
const ArtLibrary = preload("res://client/scripts/art_library.gd")
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
const RACE_IDS: Array[String] = ["zetans", "symbionts", "automatons"]

class RaceOfflineClient:

	extends MobileSmoke.OfflineClient

	func _request(path: String, payload: Dictionary, kind: String, method: int = HTTPClient.METHOD_POST) -> void:
		# This transport records intent and remains pending until the test supplies
		# the response.  It never constructs HTTPRequest or reads saved credentials.
		if request_pending:
			return
		intercepted_requests.append({
			"path": path, "payload": payload.duplicate(true), "kind": kind,
			"method": method, "authenticated": not session_token.is_empty(),
		})
		request_kind = kind
		request_pending = true
		if kind == "action":
			uncertain_action = payload.duplicate(true)
		_refresh_race_controls()


var checks: int = 0
var failures: Array[String] = []
var client: RaceOfflineClient


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures.append(description)
		push_error(description)


func _settle() -> void:
	for _index: int in range(10):
		await process_frame


func _labels(node: Node) -> String:
	var value: String = node.text + "\n" if node is Label or node is Button else ""
	for child: Node in node.get_children():
		value += _labels(child)
	return value


func _width_issues(node: Node, limits: Rect2, result: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var bounds: Rect2 = child.get_global_rect()
			if bounds.position.x < limits.position.x - 1.0 or bounds.end.x > limits.end.x + 1.0:
				result.append("%s: %s outside %s" % [child.get_class(), bounds, limits])
			_width_issues(child, limits, result)


func _image_matches(image: TextureRect, art_key: String) -> bool:
	return image != null and image.texture != null and image.texture.resource_path.ends_with("/" + art_key + ".webp")


func _find_label(node: Node, caption: String) -> Label:
	if node is Label and node.text == caption:
		return node as Label
	for child: Node in node.get_children():
		var found: Label = _find_label(child, caption)
		if found != null:
			return found
	return null


func _mouse_button(point: Vector2, down: bool) -> void:
	var event: InputEventMouseButton = InputEventMouseButton.new()
	event.position = point
	event.global_position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if down else 0
	event.pressed = down
	root.push_input(event, true)


func _test_chooser(pending: Dictionary, chosen: Dictionary) -> void:
	client.session_token = "offline-test-session-token"
	client._apply_state(pending)
	await _settle()
	_expect(client.race_screen.visible and not client.app_screen.visible and not client.login_screen.visible,
		"An authenticated empire without a race opens the mandatory chooser")
	_expect(client.race_buttons.size() == 3 and client.race_cards.get_child_count() == 3,
		"The chooser presents exactly three complete race cards")
	_expect(client.race_scroll.get_script() == TouchScroll,
		"Race cards use the shared native touch-scroll component")
	var chooser_text: String = _labels(client.race_screen).to_lower()
	_expect(chooser_text.contains("stał") or chooser_text.contains("nie można zmieni") or chooser_text.contains("nie zmien"),
		"A permanent choice is explained before its action buttons")
	for physical_size: Vector2i in [Vector2i(720, 1280), Vector2i(360, 640), Vector2i(600, 1000)]:
		root.content_scale_size = Vector2i(600, 1000) if physical_size.x == 600 else Vector2i(720, 1280)
		root.size = physical_size
		await _settle()
		var issues: Array[String] = []
		_width_issues(client.race_cards, client.race_scroll.get_global_rect(), issues)
		_expect(issues.is_empty(), "Race cards fit a %dpx phone viewport: %s" % [physical_size.x, "; ".join(issues)])
		var usable: bool = client.race_scroll.size.y > 300 and client.race_cards.size.y > client.race_scroll.size.y
		for id: String in RACE_IDS:
			var button: Button = client.race_buttons[id]
			usable = usable and button.size.y >= 80 and button.size.x >= 250
			usable = usable and button.mouse_filter == Control.MOUSE_FILTER_PASS
			usable = usable and button.action_mode == BaseButton.ACTION_MODE_BUTTON_RELEASE
		_expect(usable, "All three choices remain large release-only touch targets with scrolling at %dpx" % physical_size.x)
		var readable_titles: bool = true
		for race: Dictionary in pending["races"]:
			var name_label: Label = _find_label(client.race_cards, race["name"])
			var weapon_label: Label = _find_label(client.race_cards, race["weapon_name"])
			readable_titles = readable_titles and name_label != null and name_label.get_line_count() <= 2
			readable_titles = readable_titles and weapon_label != null and weapon_label.get_line_count() <= 3
		_expect(readable_titles, "Race and weapon names stay readable rather than wrapping character-by-character at %dpx" % physical_size.x)

	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	await _settle()
	client.race_scroll.scroll_vertical = 180
	var card_id: int = client.race_cards.get_child(0).get_instance_id()
	var previous_scroll: int = client.race_scroll.scroll_vertical
	client._apply_state(pending.duplicate(true))
	await _settle()
	_expect(client.race_cards.get_child(0).get_instance_id() == card_id and client.race_scroll.scroll_vertical == previous_scroll,
		"Polling preserves race cards and the reader's scroll position")
	client.race_scroll.scroll_vertical = 0
	await _settle()
	var first: Button = client.race_buttons["zetans"]
	client.race_scroll.ensure_control_visible(first)
	await _settle()
	var point: Vector2 = first.get_global_rect().get_center()
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	root.push_input(motion, true)
	_mouse_button(point, true)
	_expect(client.race_scroll.get_global_rect().has_point(point) and first.button_pressed,
		"Scroll cancellation is exercised on an actual pressed visible race button")
	client.race_scroll.propagate_notification(Control.NOTIFICATION_SCROLL_BEGIN)
	_mouse_button(point, false)
	_expect(client.intercepted_requests.is_empty(), "Starting a scroll over a race button never chooses a race")

	client.session_token = ""
	client._choose_race("zetans")
	_expect(client.intercepted_requests.is_empty(), "Race selection cannot dispatch without an authenticated session")
	client.session_token = "offline-test-session-token"
	client.race_buttons["zetans"].pressed.emit()
	_expect(client.intercepted_requests.size() == 1, "A race choice dispatches exactly one command")
	if client.intercepted_requests.is_empty():
		return
	var request: Dictionary = client.intercepted_requests.back()
	var payload: Dictionary = request["payload"]
	_expect(request["path"] == "/api/action" and request["kind"] == "action" and request["authenticated"]
		and payload.get("type") == "choose_race" and payload.get("race_id") == "zetans"
		and not str(payload.get("request_id", "")).is_empty(),
		"The selected race uses the existing authenticated idempotent action contract")
	var disabled: bool = true
	for id: String in RACE_IDS:
		disabled = disabled and client.race_buttons[id].disabled
	client._choose_race("symbionts")
	_expect(disabled and client.intercepted_requests.size() == 1,
		"Pending selection disables all choices and prevents a conflicting second command")
	client._on_response(HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray())
	await _settle()
	_expect(not client.request_pending and client.race_buttons["symbionts"].disabled
		and client.race_status.text.contains("Brak połączenia") and client.uncertain_action == payload,
		"An uncertain network result keeps the same choice locked and explains recovery")
	client._poll()
	_expect(client.intercepted_requests.size() == 2 and client.intercepted_requests.back()["payload"] == payload,
		"Retry resends the identical choice with the same idempotency key")
	client._on_response(HTTPRequest.RESULT_SUCCESS, 409, PackedStringArray(),
		JSON.stringify({"ok": false, "error": "Wybór został odrzucony w teście."}).to_utf8_buffer())
	await _settle()
	_expect(client.race_screen.visible and client.race_status.text.contains("Wybór został odrzucony"),
		"A server rejection is visible on the chooser itself")
	_expect(not client.race_buttons["zetans"].disabled and client.uncertain_action.is_empty(),
		"An explicit rejection restores choice controls without replaying a rejected action")
	client.race_buttons["zetans"].pressed.emit()
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(),
		JSON.stringify({"ok": true, "state": chosen, "message": "Wybrano rasę."}).to_utf8_buffer())
	await _settle()
	_expect(not client.race_screen.visible and client.app_screen.visible and client.state["player"]["race_id"] == "zetans",
		"Only the accepted server response closes the chooser and opens the selected colony")


func _test_race_catalogs(fixtures: Dictionary) -> void:
	var distinct_paths: Dictionary = {}
	var fleet_stat_sets: Dictionary = {}
	for id: String in RACE_IDS:
		var snapshots: Dictionary = fixtures[id]
		client._apply_state(snapshots["chosen"])
		client._open_tab(2)
		await _settle()
		var state: Dictionary = snapshots["chosen"]
		var catalog: Dictionary = state["catalog"]
		var missing: Array[String] = []
		var current_race: Dictionary = {}
		for race: Dictionary in state["races"]:
			if race["id"] == id:
				current_race = race
		for kind: String in ["buildings", "ships", "research"]:
			var rows: Dictionary = client.building_rows if kind == "buildings" else client.ship_rows if kind == "ships" else client.research_rows
			for entry: Dictionary in catalog[kind]:
				var key: String = entry["key"]
				var controls: Dictionary = rows[key]
				if controls["heading"].text != entry["name"] or not _image_matches(controls.get("art"), entry["art_key"]):
					missing.append(kind + "/" + key)
				distinct_paths[entry["art_key"]] = true
		_expect(missing.is_empty(), "The actual 9 building, 5 ship and 3 research cards show this race's names and art: %s %s" % [id, missing])
		var ships_match: bool = true
		var ship_issues: Array[String] = []
		var stats: Array = []
		for ship: Dictionary in catalog["ships"]:
			var key: String = ship["key"]
			ships_match = ships_match and client.fleet_names[key].text == ship["name"]
			ships_match = ships_match and _image_matches(client.fleet_portraits[key], ship["art_key"])
			var controls: Dictionary = client.ship_rows[key]
			var expected: Dictionary = {
				"attack_stat": "Atak " + client._number(float(ship.get("effective_attack", ship["attack"]))),
				"hull_stat": "Kadłub " + client._number(float(ship["hull"])),
				"capacity_stat": "Ładownia " + client._number(float(ship["capacity"])),
			}
			for field: String in expected:
				var stat_label: Label = controls[field]
				var value_matches: bool = stat_label.text == expected[field]
				if field == "attack_stat":
					var attack_text: String = stat_label.text.trim_prefix("Atak ").replace(",", ".")
					value_matches = stat_label.text.begins_with("Atak ") and is_equal_approx(float(attack_text), float(ship.get("effective_attack", ship["attack"])))
				ships_match = ships_match and value_matches and stat_label.is_visible_in_tree()
				ships_match = ships_match and stat_label.get_line_count() == 1
				if not value_matches or not stat_label.is_visible_in_tree() or stat_label.get_line_count() != 1:
					ship_issues.append("%s/%s actual=%s expected=%s visible=%s lines=%s" % [key, field, stat_label.text, expected[field], stat_label.is_visible_in_tree(), stat_label.get_line_count()])
			stats.append([ship["attack"], ship["hull"], ship["capacity"]])
		fleet_stat_sets[JSON.stringify(stats)] = true
		_expect(ships_match, "All five mission-form names, portraits and ship stats follow the selected race: " + id + " " + str(ship_issues))
		_expect(client.race_identity.visible and client.race_name.text.contains(current_race["name"])
			and client.race_weapon.text.contains(current_race["weapon_name"])
			and _image_matches(client.race_portrait, current_race["portrait_art"])
			and _image_matches(client.race_colony, current_race["colony_art"]),
			"The first colony view visibly identifies the race, architecture and weapon: " + id)
		_expect(client.biome_toggle.visible and not client.colony_panorama.visible,
			"Race identity takes priority while the world's matching panorama remains accessible: " + id)
		client.biome_toggle.pressed.emit()
		client._apply_state(snapshots["chosen"].duplicate(true))
		await _settle()
		_expect(client.colony_panorama.visible and client.colony_illustration.texture == ArtLibrary.colony_texture(client.selected_planet),
			"Opening the world's panorama survives polling and keeps the matching planet biome: " + id)
		for field: String in ["portrait_art", "colony_art", "weapon_art"]:
			distinct_paths[current_race[field]] = true
		client._apply_state(snapshots["trained"])
		await _settle()
		var upgraded_stats: bool = true
		for ship: Dictionary in snapshots["trained"]["catalog"]["ships"]:
			var displayed: String = client.ship_rows[ship["key"]]["attack_stat"].text.trim_prefix("Atak ").replace(",", ".")
			upgraded_stats = upgraded_stats and is_equal_approx(float(displayed), float(ship["effective_attack"]))
		_expect(upgraded_stats, "Visible attack values preserve fractional research bonuses: " + id)
		client._apply_state(snapshots["fleet"])
		await _settle()
		var fleet_text: String = _labels(client.fleet_list)
		var all_labels: bool = true
		for ship: Dictionary in catalog["ships"]:
			all_labels = all_labels and fleet_text.contains(ship["name"] + " ×1")
			all_labels = all_labels and client.fleet_available[ship["key"]].text.contains("1")
		_expect(all_labels, "A real dispatched five-role fleet displays race names and remaining inventory: " + id)
		client._apply_state(snapshots["building"])
		await _settle()
		var building_name: String = ""
		for building: Dictionary in catalog["buildings"]:
			if building["key"] == "metal_mine":
				building_name = str(building["name"])
		_expect(client.queue_name.contains(building_name) and client.active_project_title.text.contains(building_name)
			and client.queue_bar.visible and client.building_rows["metal_mine"]["progress_panel"].visible,
			"The queue and sticky progress UI use the race's actual building name: " + id)
	var missing_art: Array[String] = []
	for path: String in distinct_paths:
		if ArtLibrary.texture(path) == null:
			missing_art.append(path)
	_expect(distinct_paths.size() == 54 and missing_art.is_empty(), "All 54 distinct race images, including nine unique buildings and three racial technologies, resolve: " + str(missing_art))
	_expect(fleet_stat_sets.size() == 3, "The three races expose different authoritative fleet stats")


func _test_compatibility_and_priority(fixture: Dictionary) -> void:
	client._apply_state(fixture["legacy"])
	await _settle()
	_expect(client.app_screen.visible and not client.race_screen.visible and not client.race_identity.visible,
		"A server without the race contract opens the existing game without a dead-end chooser")
	client._apply_state(fixture["blocked"])
	await _settle()
	var before_blocked: int = client.intercepted_requests.size()
	client._choose_race("symbionts")
	_expect(client.race_screen.visible and client.race_buttons["symbionts"].disabled
		and client.race_status.text == fixture["blocked"]["race_choice_reason"]
		and client.intercepted_requests.size() == before_blocked,
		"An active legacy project displays the server's wait reason and blocks race changes")
	client._apply_state(fixture["pending"])
	await _settle()
	_expect(not client.race_buttons["symbionts"].disabled and client.race_status.text != fixture["blocked"]["race_choice_reason"],
		"A completed legacy project clears the obsolete wait reason and unlocks choices")
	client.update_overlay.visible = true
	client.update_required = true
	client._sync_screen_visibility()
	var before: int = client.intercepted_requests.size()
	client._choose_race("symbionts")
	_expect(client.update_overlay.visible and not client.race_screen.visible and not client.app_screen.visible
		and client.intercepted_requests.size() == before,
		"A required update takes priority over race selection and blocks its action")
	client.update_required = false
	client.update_overlay.visible = false
	client._sync_screen_visibility()
	_expect(client.race_screen.visible, "Closing the update overlay returns to the pending race choice")
	client._reset_world()
	client._show_login()
	_expect(client.login_screen.visible and not client.race_screen.visible, "Clearing a session removes the race chooser")


func _run() -> void:
	var arguments: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if arguments.is_empty():
		push_error("Supply tests/make_race_fixture.py's local JSON path after --.")
		quit(2)
		return
	var fixture: Variant = JSON.parse_string(FileAccess.get_file_as_string(arguments[0]))
	if not fixture is Dictionary or not fixture.get("pending") is Dictionary:
		push_error("A generated local race fixture is required.")
		quit(2)
		return
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client = RaceOfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await _settle()
	await _test_chooser(fixture["pending"], fixture["races"]["zetans"]["chosen"])
	await _test_race_catalogs(fixture["races"])
	await _test_compatibility_and_priority(fixture)
	_expect(client.http == null and client.poll_timer == null,
		"Tests construct no HTTP client or poll timer and never contact production")
	print("Race UI: %d checks, %d failures; intercepted local transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
