extends RefCounted
## Original raster art shared by UI views. No network requests or gameplay state.

## Catalog v1 order is fixed: ownership, names and polling never change a world's art.
const PLANETS: Array[String] = ["ocean", "desert", "ice", "volcanic", "jungle", "amethyst", "rust", "coral", "twilight", "storm", "obsidian", "crater"]
const BUILDINGS: Array[String] = ["metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab"]
const SHIPS: Array[String] = ["scout", "cargo", "colonizer", "frigate", "cruiser", "interceptor", "siege", "freighter", "battleship", "dreadnought", "flagship", "titan"]
const CAPITAL_SHIPS: Array[String] = ["battleship", "dreadnought", "flagship", "titan"]
const RESEARCH_ICONS: Array[String] = ["antigravity", "brood_sovereignty", "capital_shipbuilding", "capital_weapons", "chitin_layers", "coherent_plasma", "composite_armor", "computing", "corrosive_spores", "dyson_design", "energy_technology", "folding_cargo", "fusion_power", "graviton_control", "hyperspace", "megastructures", "metabolic_drive", "modular_cargo", "multiplication", "nanotechnology", "orbital_engineering", "phase_hulls", "propulsion", "psionic_command", "recycling", "robotics", "siege_algorithms", "siege_autonomy", "spacetime_stability", "stellar_collectors", "stellar_engineering", "superconductors", "titan_core", "weapons", "wormhole_theory"]
const RACES: Array[String] = ["zetans", "symbionts", "automatons"]
const RACE_ASSETS: Array[String] = ["portrait", "colony", "weapon", "metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab", "observatory", "scout", "cargo", "colonizer", "frigate", "cruiser", "interceptor", "siege", "freighter", "battleship", "dreadnought", "flagship", "titan"]
const UNIQUE_RACE_ASSETS: Dictionary = {
	"zetans": ["phase_sentinel", "echo_observatory", "phase_matrix", "synapse_archive", "antigravity", "quantum_foundry", "phase_vault", "gravitic_logistics", "phase_hulls", "coherent_plasma", "folding_cargo"],
	"automatons": ["iron_bastion", "serial_forge", "magnetic_citadel", "wreck_recycler", "recycling", "assembly_hub", "armored_vault", "ore_processor", "composite_armor", "siege_algorithms", "modular_cargo"],
	"symbionts": ["rooted_spore", "world_root", "pioneer_nursery", "renewal_grove", "multiplication", "brood_chamber", "living_vault", "nutrient_reservoir", "chitin_layers", "corrosive_spores", "metabolic_drive"],
}
const SWARM_ASSETS: Array[String] = ["acid_spire", "portrait", "colony", "weapon", "metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab", "scout", "cargo", "colonizer", "frigate", "cruiser", "crystal", "planet", "raid"]
## Client-side mappings work with the existing 0.7.0 server and saved reports.
## Defense aliases must not change building pictures or the generic Swarm weapon.
const DEFENSE_ART: Dictionary = {
	"phase_sentinel": "races/zetans/phase_sentinel",
	"iron_bastion": "races/automatons/iron_bastion",
	"rooted_spore": "races/symbionts/rooted_spore",
	"acid_spire": "swarm/acid_spire",
}
const MAX_CACHED_SWARM_ART: int = 12
## A full 0.11 catalogue must fit, or each poll would evict/reload its own art.
const MAX_CACHED_RACE_ART: int = 48
const MAX_CACHED_COLONIES: int = 3
const MAX_CACHED_GALAXIES: int = 2
const GALAXIES: Array[String] = ["aurora", "eclipse", "nexus", "omega", "zephyr", "void"]
static var textures: Dictionary = {}
static var planet_environments: Dictionary = {}
static var colony_cache_keys: Array[String] = []
static var race_cache_keys: Array[String] = []
static var swarm_cache_keys: Array[String] = []
static var galaxy_cache_keys: Array[String] = []


static func defense_art_key(unit_key: String) -> String:
	return str(DEFENSE_ART.get(unit_key, ""))


static func catalog_art_key(entry: Dictionary, fallback: String = "", race_id: String = "") -> String:
	# IDs, not localized display names, select the picture. Saved solo and
	# coalition replays use unit_key; catalog entries use key.
	var key: String = str(entry.get("unit_key", entry.get("key", fallback)))
	var race: String = str(entry.get("race_id", entry.get("race", race_id)))
	var supplied: String = str(entry.get("art_key", ""))
	if race.is_empty() and supplied.begins_with("races/"):
		race = supplied.get_slice("/", 1)
	if key in RESEARCH_ICONS:
		return "research/" + key
	if key in CAPITAL_SHIPS and race in RACES:
		return "races/" + race + "/" + key
	# Existing servers reuse lab / echo_observatory art for this separate building.
	# Override by catalog ID so laboratories and the Zetan Echo Observatory stay distinct.
	if key == "observatory" and race in RACES:
		return "races/" + race + "/observatory"
	var defense: String = defense_art_key(key)
	if not defense.is_empty():
		return defense
	return supplied if not supplied.is_empty() else fallback


static func normalized_key(key: String) -> String:
	# The synchronous catalogue and background replay loader use the same IDs.
	if key.begins_with("fleet/"):
		var fleet_parts: PackedStringArray = key.split("/")
		if fleet_parts.size() != 3 or not fleet_parts[1] in RACES or not fleet_parts[2] in CAPITAL_SHIPS:
			return ""
		return "races/" + fleet_parts[1] + "/" + fleet_parts[2]
	if key in RESEARCH_ICONS:
		return "research/" + key
	return key


static func texture_path(key: String) -> String:
	key = normalized_key(key)
	if key.is_empty(): return ""
	if key.begins_with("research/"):
		var research_parts: PackedStringArray = key.split("/")
		if research_parts.size() != 2 or not research_parts[1] in RESEARCH_ICONS: return ""
	if key.begins_with("galaxies/"):
		var galaxy_parts: PackedStringArray = key.split("/")
		if galaxy_parts.size() != 2 or not galaxy_parts[1] in GALAXIES: return ""
	if key.begins_with("races/"):
		var parts: PackedStringArray = key.split("/")
		if parts.size() != 3 or not parts[1] in RACES: return ""
		if not parts[2] in RACE_ASSETS and not parts[2] in UNIQUE_RACE_ASSETS.get(parts[1], []): return ""
	if key.begins_with("swarm/"):
		var parts: PackedStringArray = key.split("/")
		if parts.size() != 2 or not parts[1] in SWARM_ASSETS: return ""
	var filename: String = key
	if key in BUILDINGS: filename = "building_" + key
	elif key in SHIPS: filename = "ship_" + key
	elif key == "propulsion": filename = "ship_scout"
	elif key == "weapons": filename = "ship_cruiser"
	var path: String = "res://client/assets/art/" + filename + ".webp"
	return path if ResourceLoader.exists(path) else ""


static func cache_texture(key: String, loaded: Texture2D) -> void:
	key = normalized_key(key)
	if key.is_empty() or loaded == null: return
	textures[key] = loaded
	_remember_colony(key)
	_remember_race(key)
	_remember_swarm(key)
	_remember_galaxy(key)


static func texture(key: String) -> Texture2D:
	key = normalized_key(key)
	if textures.has(key):
		cache_texture(key, textures[key])
		return textures[key] as Texture2D
	var path: String = texture_path(key)
	if path.is_empty(): return null
	var loaded: Texture2D = load(path) as Texture2D
	cache_texture(key, loaded)
	return loaded


static func _remember_colony(key: String) -> void:
	# Keep only recent panoramas. Planet portraits and shared catalog art stay cached.
	if not key.begins_with("worlds/colony_"):
		return
	colony_cache_keys.erase(key)
	colony_cache_keys.append(key)
	while colony_cache_keys.size() > MAX_CACHED_COLONIES:
		var oldest: String = colony_cache_keys.pop_front()
		textures.erase(oldest)


static func update_planets(state: Dictionary) -> void:
	planet_environments.clear()
	for system: Dictionary in state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			var kind: String = str(planet.get("environment", {}).get("type", ""))
			if kind in PLANETS:
				planet_environments[str(planet.get("id", ""))] = kind
	var own_type: String = str(state.get("environment", {}).get("type", ""))
	if own_type in PLANETS:
		planet_environments[str(state.get("planet_id", ""))] = own_type


static func planet_variant(planet_id: String) -> String:
	if planet_environments.has(planet_id):
		return str(planet_environments[planet_id])
	# Stable visual fallback for servers predating physical environments.
	var value: int = 0
	for i: int in range(planet_id.length()):
		value = (value * 31 + planet_id.unicode_at(i)) % 65521
	return PLANETS[value % PLANETS.size()]


static func planet_texture(planet_id: String) -> Texture2D:
	return texture("worlds/planet_" + planet_variant(planet_id))


static func colony_texture(planet_id: String) -> Texture2D:
	return texture("worlds/colony_" + planet_variant(planet_id))


static func _remember_race(key: String) -> void:
	if not key.begins_with("races/"):
		return
	race_cache_keys.erase(key)
	race_cache_keys.append(key)
	while race_cache_keys.size() > MAX_CACHED_RACE_ART:
		var oldest: String = race_cache_keys.pop_front()
		textures.erase(oldest)


static func release_other_races(selected_id: String) -> void:
	# Selection previews are released after choosing or leaving the empire.
	for key: String in race_cache_keys.duplicate():
		if selected_id.is_empty() or not key.begins_with("races/" + selected_id + "/"):
			race_cache_keys.erase(key)
			textures.erase(key)


static func _remember_swarm(key: String) -> void:
	if not key.begins_with("swarm/"):
		return
	swarm_cache_keys.erase(key)
	swarm_cache_keys.append(key)
	while swarm_cache_keys.size() > MAX_CACHED_SWARM_ART:
		var oldest: String = swarm_cache_keys.pop_front()
		textures.erase(oldest)


static func _remember_galaxy(key: String) -> void:
	# Only current and previous galaxy in this explicit cache.
	# Active scene nodes may still hold their own resource references.
	if not key.begins_with("galaxies/"):
		return
	galaxy_cache_keys.erase(key)
	galaxy_cache_keys.append(key)
	while galaxy_cache_keys.size() > MAX_CACHED_GALAXIES:
		var oldest: String = galaxy_cache_keys.pop_front()
		textures.erase(oldest)
