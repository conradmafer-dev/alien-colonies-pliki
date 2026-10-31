extends SceneTree
## Offline integration checks for the illustrated 0.1.7 presentation.
## Reuses the existing transport/session-safe client; never constructs HTTPRequest.
## godot --headless --path . --script tests/test_presentation_ui.gd -- /path/to/ui-fixture.json
## These are layout/state checks, not screenshot or physical Android validation.

const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
const ArtLibrary = preload("res://client/scripts/art_library.gd")
const PlanetArt = preload("res://client/scripts/planet_art.gd")
const ART_KEYS: Array[String] = [
	"colony_panorama", "planet_ocean", "planet_desert", "planet_ice", "planet_volcanic",
	"metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab",
	"scout", "cargo", "colonizer", "frigate", "cruiser",
]

var client: MobileSmoke.OfflineClient
var checks: int = 0
var failures: Array[String] = []


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures.append(description)
		push_error(description)


func _settle() -> void:
	for _index: int in range(8):
		await process_frame


func _button(node: Node, caption: String) -> Button:
	if node is Button and node.text == caption:
		return node as Button
	for child: Node in node.get_children():
		var result: Button = _button(child, caption)
		if result != null:
			return result
	return null


func _has_label(node: Node, caption: String) -> bool:
	if node is Label and node.text == caption:
		return true
	for child: Node in node.get_children():
		if _has_label(child, caption):
			return true
	return false


func _portrait(node: Node) -> Control:
	if node.get_script() == PlanetArt:
		return node as Control
	for child: Node in node.get_children():
		var result: Control = _portrait(child)
		if result != null:
			return result
	return null


func _check_widths(node: Node, limits: Rect2, description: String) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var bounds: Rect2 = child.get_global_rect()
			_expect(bounds.position.x >= limits.position.x - 1 and bounds.end.x <= limits.end.x + 1,
				"%s fits: %s %s within %s" % [description, child.get_class(), bounds, limits])
			_check_widths(child, limits, description)


func _test_art() -> void:
	var paths: Dictionary = {}
	for key: String in ART_KEYS:
		var texture: Texture2D = ArtLibrary.texture(key)
		_expect(texture != null, "Raster artwork loads: " + key)
		if texture == null:
			continue
		_expect(texture.resource_path.ends_with(".png"), "Artwork uses actual PNG: " + key)
		_expect(texture.get_width() >= 512 and texture.get_height() >= 512, "Artwork is larger than an icon: " + key)
		paths[texture.resource_path] = true
	_expect(paths.size() == 16, "All 16 artwork keys use separate assets")
	var variants: Dictionary = {}
	for id: String in ["s1p1", "s1p2", "s1p3", "s2p1", "s3p1", "s30p3"]:
		var variant: String = ArtLibrary.planet_variant(id)
		variants[variant] = true
		_expect(variant in ArtLibrary.PLANETS, "Planet selects a known biome: " + id)
		_expect(ArtLibrary.planet_texture(id) == ArtLibrary.planet_texture(id), "Repeated planet lookup preserves visual identity: " + id)
	_expect(variants.size() >= 3, "Neighboring planet IDs provide visible biome variety")


func _test_actual_planets(initial: Dictionary) -> void:
	client._apply_state(initial.duplicate(true))
	client._open_tab(1)
	await _settle()
	_expect(not client.galaxy_overview.visible, "Galaxy starts with readable system list")
	_expect(client.galaxy_toggle.is_visible_in_tree() and client.galaxy_toggle.text == "Mapa", "Overview toggle is visible above the system list")
	for system: Dictionary in initial["galaxy"]:
		client._choose_system(str(system["id"]))
		await _settle()
		var planets: Array = system["planets"]
		_expect(planets.size() == 3, "Server fixture has three real planets: " + str(system["id"]))
		_expect(client.planet_list.get_child_count() == planets.size(), "System cards show exactly the actual server planets")
		_expect(client.system_heading.text == str(system["name"]), "System heading keeps its server name")
		for index: int in range(planets.size()):
			var card: Node = client.planet_list.get_child(index)
			_expect(_has_label(card, str(planets[index]["name"])), "Planet card keeps its server name")
			_expect(_has_label(card, "POZYCJA %s" % str(planets[index]["slot"])), "Planet card keeps its actual slot")
			var art: Control = _portrait(card)
			_expect(art != null, "Planet card has a portrait")
			if art != null:
				_expect(str(art.get("planet_id")) == str(planets[index]["id"]), "Portrait identity follows actual planet ID")
	client._focus_home_system()
	await _settle()


func _test_overview(initial: Dictionary, dimensions: Vector2i) -> void:
	root.content_scale_size = dimensions
	root.size = dimensions
	client._apply_state(initial.duplicate(true))
	client._open_tab(0)
	await _settle()
	var panorama: Control = client.tab_bodies[0].get_node("ColonyPanorama") as Control
	_expect(panorama.size.y >= 300, "Colony panorama is at least 300 px high: " + str(dimensions))
	var illustration: TextureRect = panorama.get_node("Illustration") as TextureRect
	_expect(illustration.texture == ArtLibrary.colony_texture(client.selected_planet), "Colony hero uses the selected planet's matching raster panorama")
	_check_widths(panorama, client.tabs[0].get_global_rect(), "Panorama " + str(dimensions))
	client._open_tab(1)
	if not client.galaxy_overview.visible:
		client.galaxy_toggle.pressed.emit()
	await _settle()
	_expect(client.galaxy_overview.is_visible_in_tree() and client.galaxy_toggle.text == "Układ", "Map toggle opens overview: " + str(dimensions))
	var map: Control = client.galaxy_map
	_expect(map.clip_contents, "Map clips labels and stars to its viewport")
	_expect(map.size.x <= dimensions.x and map.size.y >= 400, "Map has bounded phone dimensions")
	var reset: Button = _button(client.galaxy_overview, "Całość")
	var plus: Button = _button(client.galaxy_overview, "+")
	var minus: Button = _button(client.galaxy_overview, "−")
	var home: Button = _button(client.galaxy_overview, "Moja")
	_expect(reset != null and plus != null and minus != null and home != null, "All map navigation controls are visible in UI")
	if reset == null or plus == null or minus == null or home == null:
		return
	reset.pressed.emit()
	var base_zoom: float = float(map.call("get_zoom"))
	plus.pressed.emit()
	_expect(float(map.call("get_zoom")) > base_zoom, "Plus button increases actual map zoom")
	minus.pressed.emit()
	_expect(is_equal_approx(float(map.call("get_zoom")), base_zoom), "Minus button reverses zoom step")
	_expect(map.get("hit_points").size() == initial["galaxy"].size(), "Overview exposes every actual system")
	var first_system: String = str(initial["galaxy"][0]["id"])
	client._choose_system(first_system)
	home.pressed.emit()
	var home_system: String = ""
	for system: Dictionary in initial["galaxy"]:
		for planet: Dictionary in system["planets"]:
			if str(planet["id"]) == client.selected_planet:
				home_system = str(system["id"])
	_expect(client.selected_system == home_system and str(map.get("selected_id")) == home_system, "Home button selects the active colony's actual system")
	_expect(float(map.call("get_zoom")) >= 2, "Home button focuses map on colony")
	await _settle()
	_check_widths(client.tab_bodies[1], client.tabs[1].get_global_rect(), "Galaxy overview " + str(dimensions))
	for navigation: Button in client.nav_buttons:
		_expect(navigation.get_global_rect().end.y <= dimensions.y + 1, "Bottom navigation fits portrait height")
	map.emit_signal("system_selected", first_system)
	await _settle()
	_expect(client.selected_system == first_system, "Overview selection uses the same system picker")
	_expect(not client.galaxy_overview.visible and client.galaxy_toggle.text == "Mapa", "Selecting a star returns to its system list")
	_expect(client.tabs[1].scroll_vertical == 0, "Selecting a star returns to top of system view")


func _test_prefilled_action(caption: String, mission: int, target: String) -> void:
	client._open_tab(1)
	await _settle()
	var action: Button = _button(client.planet_list, caption)
	_expect(action != null and not action.disabled, "Planet action is available: " + caption)
	if action == null or action.disabled:
		return
	var request_count: int = client.intercepted_requests.size()
	# An old quote must never remain usable for this newly selected mission.
	client.quote_ready = true
	client.send_button.disabled = false
	action.pressed.emit()
	await _settle()
	_expect(client.tabs[2].visible, "Planet action opens existing fleet form: " + caption)
	_expect(client.selected_target == target and str(client.target_picker.get_selected_metadata()) == target, "Planet action selects exact target: " + caption)
	_expect(client.mission_picker.selected == mission, "Planet action selects matching mission: " + caption)
	_expect(client.cargo_box.visible == (mission == 3), "Cargo fields match mission: " + caption)
	_expect(not client.quote_ready and client.send_button.disabled, "Planet action requires a fresh quote before sending: " + caption)
	_expect(client.intercepted_requests.size() == request_count, "Planet action does not send a request or fleet: " + caption)


func _test_actions_and_protection(initial: Dictionary) -> void:
	var local_state: Dictionary = initial.duplicate(true)
	var action_system: Dictionary = {}
	for system: Dictionary in local_state["galaxy"]:
		var includes_home: bool = false
		for planet: Dictionary in system["planets"]:
			includes_home = includes_home or str(planet["id"]) == str(initial["home_id"])
		if not includes_home:
			action_system = system
			break
	_expect(not action_system.is_empty(), "Fixture has a system outside the home colony")
	if action_system.is_empty():
		return
	var planets: Array = action_system["planets"]
	var ids: Array[String] = [str(planets[0]["id"]), str(planets[1]["id"]), str(planets[2]["id"])]
	var old_texture: Texture2D = ArtLibrary.planet_texture(ids[1])
	planets[0].merge({"owner_type": "empty", "owner_id": "", "owner_name": ""}, true)
	planets[1].merge({"owner_type": "player", "owner_id": "offline-neighbor", "owner_name": "Sąsiad testowy", "protected_until": float(initial["server_time"]) + 60}, true)
	planets[2].merge({"owner_type": "player", "owner_id": str(initial["player"]["id"]), "owner_name": str(initial["player"]["name"])}, true)
	client._apply_state(local_state)
	client._choose_system(str(action_system["id"]))
	client._open_tab(1)
	await _settle()
	_expect(ArtLibrary.planet_texture(ids[1]) == old_texture, "Changing owner never changes the planet's biome texture")
	_expect(_has_label(client.planet_list, "○ Wolna planeta"), "Unowned planet status is readable")
	_expect(_has_label(client.planet_list, "● Sąsiad testowy"), "Neighbor owner name is readable")
	_expect(_has_label(client.planet_list, "● Twoja kolonia"), "Other owned colony is clearly marked")
	var attack: Button = _button(client.planet_list, "Atak")
	_expect(attack != null and attack.disabled, "Protected player cannot be attacked from planet card")
	_expect(client.planet_actions.size() == 1 and client.planet_actions[0]["protection"].visible, "Protected target explains why attack is unavailable")
	await _test_prefilled_action("Kolonizuj", 1, ids[0])
	await _test_prefilled_action("Zwiad", 0, ids[1])
	await _test_prefilled_action("Transport", 3, ids[2])
	client.received_at_msec -= 61000
	client._update_clock()
	_expect(attack != null and not attack.disabled, "Attack becomes available when protection expires through clock update")
	_expect(not client.planet_actions[0]["protection"].visible, "Expired protection explanation disappears without polling")
	await _test_prefilled_action("Atak", 2, ids[1])
	client._open_tab(1)
	await _settle()
	_check_widths(client.tab_bodies[1], client.tabs[1].get_global_rect(), "Planet actions at narrow width")


func _run() -> void:
	var arguments: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if arguments.is_empty():
		push_error("Supply a local JSON fixture path after --.")
		quit(2)
		return
	var fixture: Variant = JSON.parse_string(FileAccess.get_file_as_string(arguments[0]))
	if not fixture is Dictionary or not fixture.get("initial") is Dictionary:
		push_error("A fixture with an initial state is required.")
		quit(2)
		return
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	_test_art()
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await _settle()
	await _test_actual_planets(fixture["initial"])
	for dimensions: Vector2i in [Vector2i(720, 1280), Vector2i(600, 1000)]:
		await _test_overview(fixture["initial"], dimensions)
	await _test_actions_and_protection(fixture["initial"])
	_expect(client.intercepted_requests.is_empty(), "All presentation navigation/actions make zero network requests")
	_expect(client.http == null and client.poll_timer == null, "Offline client never constructs HTTP transport or polling")
	if failures.is_empty():
		print("PASS presentation_ui: %d checks; offline layout/state only, no rendered screenshots" % checks)
		quit(0)
	else:
		print("FAIL presentation_ui: %d/%d failed" % [failures.size(), checks])
		quit(1)
