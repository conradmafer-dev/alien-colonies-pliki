extends SceneTree
## Run only after the final project import/export has completed.
## Reads imported resources; does not run the editor, import, UI or any network.
const Art = preload("res://client/scripts/art_library.gd")
const NEW_SIZE: Vector2 = Vector2(1536, 1024)
const SYMBIONT_BUILDINGS: Array[String] = [
	"metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab",
	"world_root", "pioneer_nursery", "renewal_grove", "brood_chamber",
	"living_vault", "nutrient_reservoir", "observatory",
]
var assertions: int = 0
var failures: Array[String] = []
var checked: Array[Dictionary] = []
var loaded: Dictionary = {}

func _expect(ok: bool, message: String) -> void:
	assertions += 1
	if not ok:
		failures.append(message)
		push_error(message)

func _entry(catalogs: Dictionary, race: String, key: String) -> Dictionary:
	for entry: Dictionary in catalogs.get(race, {}).get("buildings", []):
		if str(entry.get("key", "")) == key:
			return entry
	return {}

func _check_texture(catalogs: Dictionary, race: String, key: String, is_new: bool) -> void:
	var entry: Dictionary = _entry(catalogs, race, key)
	var identity: String = race + "/" + key
	_expect(not entry.is_empty(), identity + ": actual catalog entry exists")
	var art_key: String = Art.catalog_art_key(entry, key, race)
	_expect(art_key == "races/" + identity, identity + ": catalog resolves dedicated art")
	var texture: Texture2D = Art.texture(art_key)
	_expect(texture != null, identity + ": imported texture loads")
	if texture == null:
		checked.append({"key": identity, "art_key": art_key, "loaded": false})
		return
	loaded[identity] = texture
	var size: Vector2 = texture.get_size()
	_expect(size.x > 0 and size.y > 0, identity + ": nonzero dimensions")
	if is_new:
		_expect(size == NEW_SIZE, identity + ": new image is 1536x1024")
	var expected_path: String = "res://client/assets/art/" + art_key + ".webp"
	_expect(texture.resource_path == expected_path, identity + ": imported resource path")
	checked.append({
		"key": identity, "art_key": art_key, "loaded": true,
		"resource_path": texture.resource_path, "rid": texture.get_rid().get_id(),
		"width": int(size.x), "height": int(size.y), "new_image": is_new,
	})

func _distinct(first: String, second: String) -> void:
	var a: Texture2D = loaded.get(first)
	var b: Texture2D = loaded.get(second)
	if a == null or b == null:
		_expect(false, first + " vs " + second + ": both images required for distinctness")
		return
	# Headless dummy renderers may not allocate distinct GPU RIDs; imported paths
	# still identify the real, separately loaded resource files.
	_expect(a.resource_path != b.resource_path or a.get_rid() != b.get_rid(), first + " vs " + second + ": separate imported resources")

func _initialize() -> void:
	var test_dir: String = get_script().resource_path.get_base_dir()
	var fixture_path: String = test_dir.path_join("catalogs.json")
	var catalogs: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(fixture_path))
	_expect(catalogs.size() == 3, "Actual offline catalog fixture contains all three races")
	for key: String in SYMBIONT_BUILDINGS:
		_check_texture(catalogs, "symbionts", key, true)
	for race: String in ["zetans", "automatons"]:
		_check_texture(catalogs, race, "observatory", true)
		_check_texture(catalogs, race, "lab", false)
	_check_texture(catalogs, "zetans", "echo_observatory", false)
	_expect(checked.size() == 18, "Exactly 15 new and 3 preserved building images checked")
	for race: String in ["zetans", "symbionts", "automatons"]:
		_distinct(race + "/observatory", race + "/lab")
	_distinct("zetans/observatory", "zetans/echo_observatory")
	_distinct("zetans/lab", "zetans/echo_observatory")
	var report: Dictionary = {
		"passed": failures.is_empty(), "assertions": assertions, "failures": failures,
		"checked": checked, "project_root": ProjectSettings.globalize_path("res://"),
		"scope": "Final imported art: 13 Symbiont buildings, 2 other Observatories, Zetan/Automaton labs, Zetan Echo Observatory",
		"network_used": false, "editor_or_import_started": false,
	}
	var output: FileAccess = FileAccess.open(test_dir.path_join("loaded_art84_report.json"), FileAccess.WRITE)
	if output == null:
		push_error("Cannot write loaded_art84_report.json")
		quit(2)
		return
	output.store_string(JSON.stringify(report, "  "))
	output.close()
	print(JSON.stringify({"passed": failures.is_empty(), "assertions": assertions, "failures": failures, "textures_checked": checked.size()}))
	loaded.clear()
	Art.textures.clear()
	quit(0 if failures.is_empty() else 1)
