extends SceneTree

const Art = preload("res://art_library.gd")
const OldArt = preload("res://art_library83.gd")
var assertions: int = 0
var failures: Array[String] = []

func _expect(ok: bool, message: String) -> void:
	assertions += 1
	if not ok:
		failures.append(message)
		push_error(message)

func _initialize() -> void:
	var catalogs: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://catalogs.json"))
	for race: String in catalogs:
		var buildings: Array = catalogs[race]["buildings"]
		_expect(buildings.size() == 13, race + ": thirteen building catalog entries")
		var mapped_buildings: Array[String] = []
		for group: String in catalogs[race]:
			for entry: Dictionary in catalogs[race][group]:
				var key: String = entry["key"]
				var current: String = Art.catalog_art_key(entry, key, race)
				if group == "buildings":
					mapped_buildings.append(current)
				if key == "observatory":
					_expect(current == "races/" + race + "/observatory", race + ": old server observatory payload gets separate art")
					_expect(current != OldArt.catalog_art_key(entry, key, race), race + ": observatory no longer uses legacy laboratory/echo artwork")
				else:
					_expect(current == OldArt.catalog_art_key(entry, key, race), race + "/" + group + "/" + key + ": unchanged mapping")
				_expect(not current.is_empty(), race + "/" + group + "/" + key + ": mapped")
		var unique: Dictionary = {}
		for value: String in mapped_buildings:
			unique[value] = true
		_expect(unique.size() == 13, race + ": all thirteen buildings use different art keys")
		_expect(Art.catalog_art_key({"key": "observatory", "art_key": "races/" + race + "/lab"}) == "races/" + race + "/observatory", race + ": infer race from legacy art_key")
		_expect(Art.catalog_art_key({"key": "observatory", "art_key": "lab"}, "", race) == "races/" + race + "/observatory", race + ": plain lab fallback uses caller race")
		_expect(Art.catalog_art_key({"key": "lab", "art_key": "races/" + race + "/lab"}, "", race) == "races/" + race + "/lab", race + ": laboratory mapping preserved")
		_expect(Art.catalog_art_key({"unit_key": "observatory", "race_id": race}) == "races/" + race + "/observatory", race + ": replay unit_key works")
		_expect(Art.catalog_art_key({}, "observatory", race) == "races/" + race + "/observatory", race + ": fallback catalog ID works")
		_expect("observatory" in Art.RACE_ASSETS, race + ": new image allowed")
		_expect(Art.RACE_ASSETS.size() + Art.UNIQUE_RACE_ASSETS[race].size() <= Art.MAX_CACHED_RACE_ART, race + ": full art set fits cache")
		var pixel: Image = Image.create(1, 1, false, Image.FORMAT_RGBA8)
		pixel.fill(Color.WHITE)
		var texture: ImageTexture = ImageTexture.create_from_image(pixel)
		Art.release_other_races(race)
		for key: String in Art.RACE_ASSETS + Art.UNIQUE_RACE_ASSETS[race]:
			Art.cache_texture("races/" + race + "/" + key, texture)
		_expect(Art.textures.has("races/" + race + "/observatory"), race + ": observatory remains cached with full art set")
		_expect(Art.textures.has("races/" + race + "/lab"), race + ": separate lab remains cached")
	_expect(Art.catalog_art_key({"key": "echo_observatory", "race_id": "zetans", "art_key": "races/zetans/echo_observatory"}) == "races/zetans/echo_observatory", "Zetan Echo Observatory retains separate identity")
	_expect(Art.catalog_art_key({"key": "observatory", "race_id": "unknown", "art_key": "custom/observatory"}) == "custom/observatory", "Unknown race preserves supplied fallback")
	_expect(Art.catalog_art_key({"key": "observatory", "race_id": "swarm", "art_key": "swarm/lab"}) == "swarm/lab", "Swarm is not remapped")
	var legacy_defenses: Dictionary = {"phase_sentinel": "races/zetans/echo_observatory", "iron_bastion": "races/automatons/magnetic_citadel", "rooted_spore": "races/symbionts/renewal_grove", "acid_spire": "swarm/weapon"}
	for defense: String in legacy_defenses:
		_expect(Art.catalog_art_key({"key": defense, "art_key": legacy_defenses[defense]}) == Art.defense_art_key(defense), defense + ": legacy defense alias remains supported")
	var report: Dictionary = {"assertions": assertions, "failures": failures, "passed": failures.is_empty(), "source": "Actual offline World catalog, memory database; network blocked", "scope": "Catalog IDs, all buildings/ships/research/defenses, legacy fallbacks, race cache capacity", "art_files_checked": false}
	var output: FileAccess = FileAccess.open("res://test_report.json", FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  "))
	output.close()
	print(JSON.stringify(report))
	Art.textures.clear()
	quit(0 if failures.is_empty() else 1)
