extends RefCounted
## Read-only navigation policy built exclusively from the current public state.
## Fleet composition, fuel and final permissions remain server-validated.

const Routes = preload("res://client/scripts/galaxy_routes.gd")

static func is_owned(state: Dictionary, planet: Dictionary) -> bool:
	var player_id: String = str(state.get("player", {}).get("id", ""))
	return not player_id.is_empty() and str(planet.get("owner_type", "")) == "player" and str(planet.get("owner_id", "")) == player_id


static func location(state: Dictionary, planet_id: String) -> Dictionary:
	if planet_id.is_empty():
		return {}
	for system: Dictionary in state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			if str(planet.get("id", "")) == planet_id:
				return {"system": system, "planet": planet}
	return {}


static func home_location(state: Dictionary, active_planet: String) -> Dictionary:
	# Use the active owned colony, then the home colony, then a known owned colony.
	# Never assume numeric system ordering or teleport the active fleet origin.
	for id: String in [active_planet, str(state.get("home_id", ""))]:
		var found: Dictionary = location(state, id)
		if not found.is_empty() and is_owned(state, found["planet"]):
			return found
	for system: Dictionary in state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			if is_owned(state, planet):
				return {"system": system, "planet": planet}
	return {}


static func distance_info(state: Dictionary, origin_id: String, target: Dictionary) -> Dictionary:
	var origin: Dictionary = location(state, origin_id)
	var destination: Dictionary = location(state, str(target.get("id", "")))
	if origin.is_empty() or destination.is_empty():
		return {"kind": "unknown"}
	if origin_id == str(target.get("id", "")):
		return {"kind": "origin"}
	var a: Dictionary = origin["system"]
	var b: Dictionary = destination["system"]
	var from_galaxy: String = str(a.get("galaxy_id", "g1"))
	var to_galaxy: String = str(b.get("galaxy_id", "g1"))
	if from_galaxy != to_galaxy:
		# Public galaxy distances are measured from the active colony by the server.
		if origin_id == str(state.get("planet_id", "")):
			for galaxy: Dictionary in state.get("galaxies", []):
				if str(galaxy.get("id", "")) == to_galaxy and galaxy.has("distance_mly"):
					return {"kind": "intergalactic", "value": float(galaxy["distance_mly"])}
		return {"kind": "unknown"}
	if str(a.get("id", "")) == str(b.get("id", "")):
		return {"kind": "same_system", "origin_slot": int(origin["planet"].get("slot", 0)), "target_slot": int(target.get("slot", 0))}
	if a.get("connections") is Array or b.get("connections") is Array:
		var same_galaxy: Array = []
		for system: Dictionary in state.get("galaxy", []):
			if str(system.get("galaxy_id", "g1")) == from_galaxy:
				same_galaxy.append(system)
		if Routes.has_topology(same_galaxy):
			var route: Dictionary = Routes.shortest_path(Routes.graph(same_galaxy), str(a.get("id", "")), str(b.get("id", "")))
			if not route.is_empty():
				return {"kind": "sector", "value": float(route["distance"]), "system_ids": route["system_ids"]}
		# Never display a straight-line estimate for a missing corridor route.
		return {"kind": "unknown"}
	if a.has("x") and a.has("y") and b.has("x") and b.has("y"):
		return {"kind": "sector", "value": Vector2(float(a["x"]), float(a["y"])).distance_to(Vector2(float(b["x"]), float(b["y"])))}
	return {"kind": "unknown"}


static func intel_info(state: Dictionary, target: Dictionary, now: float) -> Dictionary:
	if is_owned(state, target):
		return {"kind": "own"}
	# System reconnaissance reveals ownership, not necessarily the planet's fleet.
	var snapshot: Dictionary = target.get("planet_scout", {})
	var at: float = float(snapshot.get("scouted_at", 0))
	if at <= 0 and bool(target.get("has_scout", false)):
		at = float(target.get("scouted_at", 0))
	if at > 0:
		return {"kind": "scout", "age": maxf(0.0, now - at)}
	return {"kind": "unknown"}


static func can_attempt_colonization(state: Dictionary, target: Dictionary, now: float) -> bool:
	if is_owned(state, target) or str(target.get("visibility", "")) == "unknown":
		return false
	if str(target.get("owner_type", "")) == "empty":
		return true
	if not bool(state.get("colonization_capture", {}).get("enabled", false)) or str(target.get("owner_type", "")) != "player" or not target.has("is_home_planet") or bool(target["is_home_planet"]):
		return false
	var alliance: String = str(state.get("alliance", {}).get("id", ""))
	if not alliance.is_empty() and alliance == str(target.get("alliance_id", "")):
		return false
	return float(target.get("protected_until", 0)) <= now


static func target_actions(state: Dictionary, target: Dictionary, origin_id: String, now: float) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if str(target.get("id", "")).is_empty() or str(target.get("id", "")) == origin_id:
		return result
	var owner: String = str(target.get("owner_type", ""))
	var owned: bool = is_owned(state, target)
	var alliance_id: String = str(state.get("alliance", {}).get("id", ""))
	var allied: bool = owner == "player" and not alliance_id.is_empty() and str(target.get("alliance_id", "")) == alliance_id
	if not owned:
		result.append({"key": "scout", "mission": 0, "enabled": true})
	# Do not reveal or suggest ownership-dependent actions for unknown targets.
	if str(target.get("visibility", "")) == "unknown":
		return result
	if owner == "empty":
		result.append({"key": "colonize", "mission": 1, "enabled": true})
	elif owned or allied:
		result.append({"key": "transport", "mission": 3, "enabled": true})
	elif owner in ["player", "alien"]:
		if can_attempt_colonization(state, target, now):
			result.append({"key": "capture", "mission": 1, "enabled": true})
		var protected_until: float = float(target.get("protected_until", 0)) if owner == "player" else 0.0
		result.append({"key": "attack", "mission": 2, "enabled": protected_until <= now, "protected_seconds": maxf(0.0, protected_until - now)})
	return result


static func system_scout_target(system: Dictionary, origin_id: String = "") -> String:
	# New servers expose one stable, public survey anchor on every system.
	var explicit: String = str(system.get("system_scout_target_id", system.get("scout_target_id", "")))
	if not explicit.is_empty():
		return explicit
	# Compatibility with older public states: re-scout any known remote planet.
	var planets: Array = system.get("planets", []).duplicate()
	planets.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a.get("slot", 0)) < int(b.get("slot", 0)) if int(a.get("slot", 0)) != int(b.get("slot", 0)) else str(a.get("id", "")).naturalnocasecmp_to(str(b.get("id", ""))) < 0)
	for planet: Dictionary in planets:
		var id: String = str(planet.get("id", ""))
		if not id.is_empty() and id != origin_id:
			return id
	return ""
