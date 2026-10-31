extends SceneTree
## Five languages, three races and 60 skills; disposable fixture, no real HTTP.
var MobileSmoke: GDScript
var MobileQuantity: GDScript
var TouchScroll: GDScript
var client: Control
var language: Node
var checks: int = 0
var failures: Array[String] = []
var fixture: Dictionary = {}

func _initialize() -> void:
	_run.call_deferred()

func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures.append(description)
		push_error(description)

func _settle() -> void:
	for _frame: int in range(5):
		await process_frame

func _bounds(node: Node, bounds: Rect2, issues: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var rect: Rect2 = child.get_global_rect()
			if rect.position.x < bounds.position.x - 1.0 or rect.end.x > bounds.end.x + 1.0:
				var caption: String = str(child.get("text")) if child is Label or child is Button else ""
				issues.append("%s %s [%s]" % [str(child.get_path()), rect, caption])
			_bounds(child, bounds, issues)

func _geometry(node: Control, caption: String) -> void:
	var issues: Array[String] = []
	_bounds(node, node.get_global_rect(), issues)
	_expect(issues.is_empty(), caption + ": " + str(issues))

func _catalog_expected(code: String, source: String) -> String:
	var selected: Dictionary = fixture["expected_catalogs"][code]
	var english: Dictionary = fixture["expected_catalogs"]["en"]
	return str(selected.get(source, english.get(source, source)))

func _check_race(code: String, race: String, states: Dictionary) -> void:
	var context: String = code + "/" + race
	client._apply_state(states["locked"])
	await _settle()
	_expect(client.building_rows.size() == 12 and client.research_rows.size() == 6 and client.ship_rows.size() == 8,
		context + ": full racial content remains visible")
	client._apply_state(states["ready"])
	await _settle()
	_expect(client.state["player"]["name"] == "Konto" and client.state["planet_name"] == "Rój", context + ": player-created names remain literal")
	for kind: String in ["buildings", "research", "ships"]:
		var rows: Dictionary = client.building_rows if kind == "buildings" else client.research_rows if kind == "research" else client.ship_rows
		for entry: Dictionary in states["ready"]["catalog"][kind]:
			var key: String = str(entry["key"])
			var controls: Dictionary = rows[key]
			var source: String = fixture["source_names"][race][kind][key]
			var expected: String = _catalog_expected(code, source)
			_expect(str(entry["name"]) == expected and controls["heading"].text == expected,
				context + "/" + key + ": authored catalog name reaches the visible card")
			_expect(controls["description"].text.begins_with(str(entry["description"])),
				context + "/" + key + ": localized description reaches the card unchanged")
			for resource: String in client.RESOURCE_KEYS:
				var amount: Label = controls["costs"][resource]["amount"]
				_expect(amount.autowrap_mode == TextServer.AUTOWRAP_OFF and amount.get_line_count() <= 1,
					context + "/" + key + "/" + resource + ": quantity is one horizontal token")
			if kind == "ships":
				_expect(client.fleet_names[key].text == expected, context + "/" + key + ": mission selector uses localized ship name")
	for tab: int in range(5):
		client._open_tab(tab)
		if tab == 2:
			client._set_fleet_mode(1)
		await _settle()
		_geometry(client.tabs[tab], context + ": tab %d stays within 600px viewport" % tab)
		_expect(client.tabs[tab].get_script() == TouchScroll, context + ": tab %d retains shared touch scroller" % tab)
	client._open_fleet_missions()
	await _settle()
	_geometry(client.tabs[2], context + ": mission form stays within viewport")
	var selected_quantities: Dictionary = {}
	for key: String in client.fleet_inputs:
		var amount: Control = client.fleet_inputs[key]
		amount.value = 2
		selected_quantities[key] = int(amount.value)
		_expect(amount.get_script() == MobileQuantity and amount.editor.mouse_filter == Control.MOUSE_FILTER_IGNORE
			and amount.edit_gate.mouse_filter == Control.MOUSE_FILTER_PASS and amount.edit_gate.action_mode == BaseButton.ACTION_MODE_BUTTON_RELEASE,
			context + "/" + key + ": numbers retain release-only swipe-safe input")
		var events: Array[bool] = []
		var callback: Callable = func() -> void: events.append(true)
		amount.edit_gate.edit_requested.connect(callback)
		amount.edit_gate._begin_tap()
		amount.edit_gate.notification(Control.NOTIFICATION_SCROLL_BEGIN)
		amount.edit_gate._complete_tap()
		_expect(events.is_empty(), context + "/" + key + ": scroll never requests keyboard")
		amount.edit_gate.edit_requested.disconnect(callback)
	client.intercepted_requests.clear()
	client.selected_target = str(states["ready"]["galaxy"][0]["planets"][0]["id"])
	client._preview_fleet()
	_expect(client.intercepted_requests.size() == 1, context + ": one offline route preview")
	if client.intercepted_requests.size() == 1:
		_expect(client.intercepted_requests[0]["payload"]["ships"] == selected_quantities,
			context + ": localized ship names never change wire keys or quantities")
	client.intercepted_requests.clear()
	client._open_skill_wheel()
	await _settle()
	var nodes: Array = states["ready"]["skill_tree"]["nodes"]
	_expect(nodes.size() == 60, context + ": whole 60-node shared wheel exists")
	for node: Dictionary in nodes:
		var source: String = fixture["source_skills"][race][node["id"]]
		var expected: String = _catalog_expected(code, source)
		client._select_skill_node(str(node["id"]))
		_expect(str(node["name"]) == expected and client.skill_detail_title.text == expected,
			context + "/" + str(node["id"]) + ": skill name translated without changing node ID")
		_expect(client.skill_detail_description.text.begins_with(str(node["description"])) and not client.skill_detail_description.text.is_empty(),
			context + "/" + str(node["id"]) + ": translated skill effect visible")
	await _settle()
	_geometry(client.skill_margin, context + ": skill wheel controls fit viewport")
	_expect(client.intercepted_requests.is_empty(), context + ": browsing translated skills never buys a skill")
	client._close_skill_wheel()
	for mode: String in ["account", "help", "attacks"]:
		client._open_release_panel(mode)
		await _settle()
		_geometry(client.release_panel.scroll, context + ": " + mode + " panel fits viewport")
		client._close_release_panel()
		await _settle()
	client._apply_state(states["maximum"])
	await _settle()
	for kind: String in ["buildings", "research"]:
		var rows: Dictionary = client.building_rows if kind == "buildings" else client.research_rows
		for entry: Dictionary in states["maximum"]["catalog"][kind]:
			if int(entry.get("max_level", 0)) > 0:
				_expect(rows[entry["key"]]["action"].text == _catalog_expected(code, "Maksimum")
					and rows[entry["key"]]["action"].disabled, context + "/" + str(entry["key"]) + ": localized maximum state")
	client._open_tab(0)
	await _settle()
	client.tabs[0].scroll_vertical = 300
	client.nav_buttons[0].pressed.emit()
	await _settle()
	_expect(client.tabs[0].scroll_vertical == 0, context + ": Planet navigation still returns to top")
	_expect(client.http == null and client.poll_timer == null, context + ": no HTTP client or polling exists")

func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Pass fixture from tests/make_localization_fixture.py")
		quit(2)
		return
	fixture = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	fixture["expected_catalogs"] = {}
	for code: String in ["en", "pl", "de", "es", "fr"]:
		fixture["expected_catalogs"][code] = JSON.parse_string(FileAccess.get_file_as_string("res://localization/%s.json" % code))
	language = root.get_node("I18n")
	var initial_locale: String = str(language.locale)
	if not FileAccess.file_exists(language.SETTINGS_PATH):
		_expect(initial_locale == "en", "Fresh installation defaults to English")
	_expect(language.normalize_locale("unsupported") == "en" and language.normalize_locale("de-DE") == "de", "Unknown language falls back to English and regional tags normalize")
	language.set_locale("unsupported", false)
	_expect(language.locale == "en" and language.t("Zamknij") == "Close", "Unknown locale actually renders English")
	MobileSmoke = load("res://tests/test_mobile_ui.gd")
	MobileQuantity = load("res://client/scripts/mobile_quantity.gd")
	TouchScroll = load("res://client/scripts/touch_scroll.gd")
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(600, 1280)
	root.size = Vector2i(600, 1280)
	for code: String in ["en", "pl", "de", "es", "fr"]:
		language.set_locale(code, false)
		client = MobileSmoke.OfflineClient.new()
		root.add_child(client)
		client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		client.session_token = "offline-localization-ui"
		await _settle()
		_geometry(client.login_screen, code + ": translated login fits viewport")
		var expected_numbers: Dictionary = {"en": "11.2 K", "pl": "11,2 tys.", "de": "11,2 Tsd.", "es": "11,2 mil", "fr": "11,2 k"}
		_expect(client._number(11200) == expected_numbers[code], code + ": compact quantities use localized decimals and units")
		_expect(client._duration(3661) == "1h 01min" and client._duration(65) == "1min 05s", code + ": duration units stay concise and horizontal")
		for race: String in ["zetans", "symbionts", "automatons"]:
			await _check_race(code, race, fixture["locales"][code][race])
		client.queue_free()
		await _settle()
	language.set_locale(initial_locale, false)
	print("Localized game: %d checks, %d failures; 5 languages × 3 races; offline only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
