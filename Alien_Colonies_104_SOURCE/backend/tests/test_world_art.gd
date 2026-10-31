extends SceneTree
## Offline contract checks for paired worlds and colony panoramas.
## godot --headless --path . --script tests/test_world_art.gd -- /tmp/pogranicze-ui-fixture.json
## No HTTPRequest, saved sessions, server writes, or production-world access.

const ArtLibrary = preload("res://client/scripts/art_library.gd")
const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
const VARIANTS: Array[String] = [
	"ocean", "desert", "ice", "volcanic", "jungle", "amethyst",
	"rust", "coral", "twilight", "storm", "obsidian", "crater",
]

var checks: int = 0
var failures: Array[String] = []
var representatives: Dictionary = {}
var client: MobileSmoke.OfflineClient


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


func _test_pairs_and_identity() -> void:
	_expect(ArtLibrary.PLANETS == VARIANTS, "All twelve intended world types are available")
	for system: int in range(1, 31):
		for slot: int in range(1, 4):
			var planet_id: String = "s%dp%d" % [system, slot]
			var variant: String = ArtLibrary.planet_variant(planet_id)
			_expect(variant in VARIANTS, "Natural server ID selects a supported biome: " + planet_id)
			_expect(ArtLibrary.planet_variant(planet_id) == variant, "Repeated ID lookup remains stable: " + planet_id)
			if not representatives.has(variant):
				representatives[variant] = planet_id
	_expect(representatives.size() == 12, "The actual ninety-position galaxy can display all twelve biomes")
	var unique_paths: Dictionary = {}
	for variant: String in VARIANTS:
		for prefix: String in ["planet_", "colony_"]:
			var path: String = "res://client/assets/art/worlds/%s%s.webp" % [prefix, variant]
			_expect(ResourceLoader.exists(path), "World artwork is imported: " + path)
			if not ResourceLoader.exists(path):
				continue
			var texture: Texture2D = load(path) as Texture2D
			_expect(texture != null, "World artwork decodes as a texture: " + path)
			if texture == null:
				continue
			unique_paths[texture.resource_path] = true
			if prefix == "planet_":
				_expect(texture.get_width() == texture.get_height(), "Planet portrait remains square: " + variant)
				_expect(texture.get_width() >= 256 and texture.get_width() <= 512, "Planet portrait has bounded mobile resolution: " + variant)
			else:
				_expect(texture.get_width() > texture.get_height(), "Colony image is panoramic: " + variant)
				_expect(texture.get_width() >= 640 and texture.get_width() <= 1280, "Colony panorama has bounded mobile resolution: " + variant)
				_expect(texture.get_height() <= 1280, "Colony panorama height is bounded: " + variant)
		if not representatives.has(variant):
			continue
		var planet_id: String = str(representatives[variant])
		var portrait: Texture2D = ArtLibrary.planet_texture(planet_id)
		var panorama: Texture2D = ArtLibrary.colony_texture(planet_id)
		_expect(portrait != null and panorama != null, "Both presentations resolve for " + planet_id)
		if portrait != null and panorama != null:
			_expect(portrait.resource_path.ends_with("/planet_" + variant + ".webp"), "Planet ID resolves to its named portrait: " + variant)
			_expect(panorama.resource_path.ends_with("/colony_" + variant + ".webp"), "Colony panorama matches that same world identity: " + variant)
			_expect(ArtLibrary.planet_texture(planet_id) == portrait, "Repeated portrait lookup reuses the texture: " + variant)
			_expect(ArtLibrary.colony_texture(planet_id) == panorama, "Repeated panorama lookup reuses the texture: " + variant)
	_expect(unique_paths.size() == 24, "Each planet and colony has its own image resource")


func _test_panorama_cache() -> void:
	ArtLibrary.textures.clear()
	ArtLibrary.colony_cache_keys.clear()
	var portraits: Dictionary = {}
	for variant: String in VARIANTS:
		if representatives.has(variant):
			portraits[variant] = ArtLibrary.planet_texture(str(representatives[variant]))
	var building: Texture2D = ArtLibrary.texture("metal_mine")
	_expect(ArtLibrary.MAX_CACHED_COLONIES == 3, "Only three large colony panoramas are retained")
	for variant: String in VARIANTS:
		if not representatives.has(variant):
			continue
		var planet_id: String = str(representatives[variant])
		var panorama: Texture2D = ArtLibrary.colony_texture(planet_id)
		_expect(panorama != null, "A newly visited colony loads: " + variant)
		_expect(ArtLibrary.colony_cache_keys.size() <= 3, "Panorama cache stays bounded after visiting " + variant)
		var cached_panoramas: int = 0
		for key: Variant in ArtLibrary.textures:
			var cached: Texture2D = ArtLibrary.textures[key] as Texture2D
			if cached != null and cached.resource_path.get_file().begins_with("colony_"):
				cached_panoramas += 1
		_expect(cached_panoramas <= 3, "Large textures are actually evicted, not just removed from bookkeeping: " + variant)
		_expect(ArtLibrary.texture("metal_mine") == building, "Panorama eviction keeps building art cached: " + variant)
		for known: String in portraits:
			var key: String = "worlds/planet_" + known
			_expect(ArtLibrary.textures.has(key) and ArtLibrary.textures[key] == portraits[known], "Panorama eviction retains the cached planet portrait: " + known)
	if representatives.has("ocean"):
		var returning: Texture2D = ArtLibrary.colony_texture(str(representatives["ocean"]))
		_expect(returning != null and returning.resource_path.ends_with("/colony_ocean.webp"), "Returning to an evicted colony restores its original biome")
		_expect(ArtLibrary.colony_cache_keys.size() <= 3, "Returning to a colony keeps the panorama cache bounded")


func _test_selected_colony(initial: Dictionary) -> void:
	var home_id: String = str(initial.get("planet_id", initial.get("home_id", "")))
	var second_id: String = ""
	for variant: String in VARIANTS:
		if variant != ArtLibrary.planet_variant(home_id) and representatives.has(variant):
			second_id = str(representatives[variant])
			break
	_expect(not home_id.is_empty() and not second_id.is_empty(), "Two distinct colony biomes are available for selection")
	if home_id.is_empty() or second_id.is_empty():
		return
	var local_state: Dictionary = initial.duplicate(true)
	local_state["own_planets"] = [
		{"id": home_id, "name": "Kolonia testowa A"},
		{"id": second_id, "name": "Kolonia testowa B"},
	]
	local_state["planet_id"] = home_id
	var original_state: Dictionary = local_state.duplicate(true)
	client._apply_state(local_state)
	await _settle()
	_expect(client.colony_illustration != null, "Colony view exposes its actual panorama control")
	if client.colony_illustration == null:
		return
	_expect(client.colony_illustration.texture != null and client.colony_illustration.texture == ArtLibrary.colony_texture(home_id), "Initial colony shows its matching panorama")
	_expect(local_state == original_state, "Applying colony artwork does not mutate the supplied game state")
	var original_texture: Texture2D = client.colony_illustration.texture
	# The picker may request state, but it must not pretend another colony is active
	# until its state has arrived. The transport is intercepted by OfflineClient.
	client.session_token = "offline-fixture-session"
	var request_count: int = client.intercepted_requests.size()
	client.planet_picker.item_selected.emit(1)
	_expect(client.selected_planet == home_id and client.colony_illustration.texture == original_texture, "Pending colony selection preserves the currently displayed colony")
	_expect(client.intercepted_requests.size() == request_count + 1, "Colony selection requests exactly one new state")
	if client.intercepted_requests.size() > request_count:
		var request: Dictionary = client.intercepted_requests.back()
		_expect(str(request["path"]) == "/api/state?planet_id=" + second_id, "Colony selector keeps the existing state endpoint and selected ID")
		_expect(request["method"] == HTTPClient.METHOD_GET and request["payload"].is_empty(), "Colony selection never performs a gameplay write")
	var next_state: Dictionary = local_state.duplicate(true)
	next_state["planet_id"] = second_id
	var expected_state: Dictionary = next_state.duplicate(true)
	client._apply_state(next_state)
	await _settle()
	var selected_texture: Texture2D = client.colony_illustration.texture
	_expect(client.selected_planet == second_id, "Arriving state selects the requested colony")
	_expect(selected_texture != null and selected_texture == ArtLibrary.colony_texture(second_id) and selected_texture != original_texture, "Changing colonies changes the panorama to the corresponding biome")
	_expect(client.planet_title.text == "Kolonia testowa B", "Colony name and panorama change together")
	_expect(next_state == expected_state and client.state == expected_state, "Illustration update preserves all authoritative state values")
	for _poll: int in range(3):
		var repeated: Dictionary = expected_state.duplicate(true)
		repeated["server_time"] = float(repeated["server_time"]) + _poll + 1
		client._apply_state(repeated)
		await _settle()
		_expect(client.colony_illustration.texture == selected_texture, "Repeated polling retains the selected colony panorama")
		_expect(client.state == repeated and repeated["resources"] == expected_state["resources"], "Art refresh does not change resources or server state")
	client._open_tab(1)
	client._open_tab(0)
	await _settle()
	_expect(client.colony_illustration.texture == selected_texture, "Navigating away and back preserves the selected colony panorama")
	client._apply_state(original_state.duplicate(true))
	await _settle()
	_expect(client.colony_illustration.texture == ArtLibrary.colony_texture(home_id), "Returning to the home colony restores its matching panorama")
	_expect(client.intercepted_requests.size() == request_count + 1, "Art changes and repeated polling issue no additional requests")
	_expect(client.http == null and client.poll_timer == null, "No HTTP client or polling timer was constructed")


func _run() -> void:
	var arguments: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if arguments.is_empty():
		push_error("Supply the local UI fixture JSON after --.")
		quit(2)
		return
	var fixture: Variant = JSON.parse_string(FileAccess.get_file_as_string(arguments[0]))
	if not fixture is Dictionary or not fixture.get("initial") is Dictionary:
		push_error("A local fixture with an initial state is required.")
		quit(2)
		return
	_test_pairs_and_identity()
	_test_panorama_cache()
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await _settle()
	await _test_selected_colony(fixture["initial"])
	if failures.is_empty():
		print("PASS world_art: %d checks; paired worlds, bounded texture cache, offline colony selection" % checks)
		quit(0)
	else:
		print("FAIL world_art: %d/%d failed" % [failures.size(), checks])
		quit(1)
