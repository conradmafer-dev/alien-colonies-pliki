extends RefCounted
## Read-only Khar discovery navigation. Uses the current public snapshot only;
## a selected destination is never a route quote or permission to send a fleet.

const Routes = preload("res://client/scripts/galaxy_routes.gd")


static func nearest(state: Dictionary, origin_planet_id: String = "") -> Dictionary:
	var systems: Array[Dictionary] = _systems(state.get("galaxy"))
	var origin: Dictionary = _origin(state, systems, origin_planet_id)
	var available_galaxies: Dictionary = _available_galaxies(state)
	var route_cache: Dictionary = {"cross_links": _has_cross_galaxy_edges(systems)}
	var by_galaxy: Dictionary = {}
	for system: Dictionary in systems:
		var galaxy_id: String = _galaxy_id(system)
		if not by_galaxy.has(galaxy_id):
			by_galaxy[galaxy_id] = []
		by_galaxy[galaxy_id].append(system)
	var candidates: Array[Dictionary] = []
	for system: Dictionary in systems:
		if not available_galaxies.has(_galaxy_id(system)) or not _discovered(system):
			continue
		for planet: Dictionary in system["planets"]:
			if _id(planet.get("id")).is_empty() or _id(planet.get("owner_type")) != "alien" or not _discovered(planet):
				continue
			# A colony-only system reveals our own planet, not its neighbours.
			if _id(system.get("visibility")) == "colony" and _id(planet.get("visibility")) not in ["observed", "scouted", "remembered"]:
				continue
			var measured: Dictionary = _distance(state, systems, by_galaxy, route_cache, origin, system, planet)
			var location: Dictionary = {
				"galaxy_id": _galaxy_id(system),
				"galaxy_name": _galaxy_name(state, _galaxy_id(system)),
				"system_id": _id(system.get("id")),
				"system_name": _name(system),
				"planet_id": _id(planet.get("id")),
				"planet_name": _name(planet),
				"origin_planet_id": _id(origin.get("planet", {}).get("id")),
				"distance": measured["info"],
				"distance_known": bool(measured["info"].get("known", false)),
				"intel_kind": _id(planet.get("visibility", system.get("visibility", ""))),
			}
			candidates.append({"location": location, "rank": measured["rank"], "value": measured["value"], "slot_delta": measured["slot_delta"]})
	if candidates.is_empty():
		return {}
	candidates.sort_custom(_candidate_before)
	return candidates[0]["location"]


static func _candidate_before(a: Dictionary, b: Dictionary) -> bool:
	for key: String in ["rank", "value", "slot_delta"]:
		if float(a[key]) != float(b[key]):
			return float(a[key]) < float(b[key])
	# IDs are stable across response ordering, translated names and recommendations.
	for key: String in ["galaxy_id", "system_id", "planet_id"]:
		var left: String = str(a["location"][key])
		var right: String = str(b["location"][key])
		if left != right:
			var comparison: int = left.naturalnocasecmp_to(right)
			return comparison < 0 if comparison != 0 else left < right
	return false


static func _distance(state: Dictionary, systems: Array[Dictionary], by_galaxy: Dictionary, route_cache: Dictionary, origin: Dictionary, target_system: Dictionary, target: Dictionary) -> Dictionary:
	var unknown: Dictionary = {"rank": 5, "value": INF, "slot_delta": INF, "info": {"kind": "unknown", "known": false, "reason": "origin_unknown"}}
	if origin.is_empty():
		return unknown
	var from_system: Dictionary = origin["system"]
	var from_planet: Dictionary = origin["planet"]
	var from_id: String = _id(from_system.get("id"))
	var target_id: String = _id(target_system.get("id"))
	var same_galaxy: bool = _galaxy_id(from_system) == _galaxy_id(target_system)
	var from_slot: float = _number(from_planet.get("slot"))
	var target_slot: float = _number(target.get("slot"))
	var slot_delta: float = absf(from_slot - target_slot) if is_finite(from_slot) and is_finite(target_slot) else INF
	unknown["rank"] = 3 if same_galaxy else 4
	unknown["slot_delta"] = slot_delta
	unknown["info"]["reason"] = "distance_not_disclosed"
	if same_galaxy and from_id == target_id:
		var info: Dictionary = {"kind": "same_system", "known": is_finite(slot_delta), "unit": "orbital_slots"}
		if is_finite(slot_delta):
			info["value"] = slot_delta
		return {"rank": 0, "value": slot_delta, "slot_delta": slot_delta, "info": info}
	# Public connections include orbital, radial and wormhole edges. Keep their
	# supplied distances and direction; never invent a connection or reverse edge.
	var local_systems: Array = by_galaxy.get(_galaxy_id(from_system), [])
	var route_systems: Array = local_systems if same_galaxy else systems
	var route_key: String = "local:" + _galaxy_id(from_system) if same_galaxy else "all"
	if bool(route_cache["cross_links"]) and Routes.has_topology(systems):
		# A disclosed shortcut may leave and re-enter the same galaxy.
		route_systems = systems
		route_key = "all"
	if not route_cache.has(route_key):
		route_cache[route_key] = _routes_from(route_systems, from_id)
	var routes: Dictionary = route_cache[route_key]
	var has_topology: bool = bool(routes["has_topology"])
	if routes["distances"].has(target_id):
		var path: Array[String] = [target_id]
		var cursor: String = target_id
		while routes["previous"].has(cursor):
			cursor = str(routes["previous"][cursor])
			path.push_front(cursor)
		var distance: float = float(routes["distances"][target_id])
		return {"rank": 1, "value": distance, "slot_delta": slot_delta, "info": {"kind": "corridor", "known": true, "value": distance, "unit": "sector", "system_ids": path}}
	if same_galaxy:
		if has_topology:
			# Match GalaxyGuidanceModel: an incomplete/disconnected graph is unknown,
			# not a deceptively short straight line through missing corridors.
			unknown["info"]["reason"] = "no_public_corridor_route"
			return unknown
		var ax: float = _number(from_system.get("x"))
		var ay: float = _number(from_system.get("y"))
		var bx: float = _number(target_system.get("x"))
		var by: float = _number(target_system.get("y"))
		if is_finite(ax) and is_finite(ay) and is_finite(bx) and is_finite(by):
			var distance: float = Vector2(ax, ay).distance_to(Vector2(bx, by))
			# The established older-state navigation rule in BeginnerGuideModel adds
			# 0.08 per orbital slot. This is a selection estimate, not a fleet quote.
			if is_finite(slot_delta):
				distance += slot_delta * 0.08
			if is_finite(distance):
				return {"rank": 1, "value": distance, "slot_delta": slot_delta, "info": {"kind": "legacy_sector", "known": true, "value": distance, "unit": "sector", "estimate": true}}
		return unknown
	# A galaxy's distance_mly belongs to the server's active colony. Do not reuse
	# that number while the user has selected another origin and state is in flight.
	if _id(from_planet.get("id")) == _id(state.get("planet_id")):
		for galaxy: Dictionary in _dictionaries(state.get("galaxies")):
			if _id(galaxy.get("id")) != _galaxy_id(target_system):
				continue
			var distance: float = _number(galaxy.get("distance_mly"))
			if is_finite(distance) and distance >= 0.0:
				# MLY and sector units are different scales: keep known local routes
				# first, then choose the closest disclosed external galaxy.
				return {"rank": 2, "value": distance, "slot_delta": INF, "info": {"kind": "intergalactic", "known": true, "value": distance, "unit": "million_light_years", "scope": "galaxy"}}
	return unknown


static func _routes_from(systems: Array, origin_id: String) -> Dictionary:
	var result: Dictionary = {"has_topology": false, "distances": {}, "previous": {}}
	for system: Dictionary in systems:
		result["has_topology"] = result["has_topology"] or system.has("connections")
	if not result["has_topology"] or not Routes.has_topology(systems):
		return result
	var graph: Dictionary = Routes.graph(systems)
	if not graph.has(origin_id):
		return result
	# One single-source pass for all candidate colonies, with exactly the shared
	# GalaxyRoutes distance precision, ID order and strict-improvement tie policy.
	# Rebuilding/rerunning the graph for every Khar planet causes avoidable stalls.
	var distances: Dictionary = {origin_id: 0.0}
	var previous: Dictionary = {}
	var pending: Array[String] = [origin_id]
	var visited: Dictionary = {}
	while not pending.is_empty():
		pending.sort_custom(func(a: String, b: String) -> bool:
			return float(distances[a]) < float(distances[b]) if float(distances[a]) != float(distances[b]) else Routes.id_before(a, b))
		var current: String = pending.pop_front()
		if visited.has(current):
			continue
		visited[current] = true
		for edge: Dictionary in graph.get(current, []):
			var target: String = str(edge["system_id"])
			if visited.has(target):
				continue
			var distance: float = roundf((float(distances[current]) + float(edge["distance"])) * 100000000.0) / 100000000.0
			if not is_finite(distance):
				continue
			if not distances.has(target) or distance < float(distances[target]):
				distances[target] = distance
				previous[target] = current
				if not pending.has(target):
					pending.append(target)
	result["distances"] = distances
	result["previous"] = previous
	return result


static func _has_cross_galaxy_edges(systems: Array[Dictionary]) -> bool:
	var galaxies: Dictionary = {}
	for system: Dictionary in systems:
		galaxies[_id(system.get("id"))] = _galaxy_id(system)
	for system: Dictionary in systems:
		for edge: Dictionary in _dictionaries(system.get("connections")):
			var target: String = _id(edge.get("system_id"))
			if galaxies.has(target) and str(galaxies[target]) != _galaxy_id(system):
				return true
	return false


static func _origin(state: Dictionary, systems: Array[Dictionary], requested: String) -> Dictionary:
	var own: Dictionary = {}
	for planet: Dictionary in _dictionaries(state.get("own_planets")):
		var id: String = _id(planet.get("id"))
		if not id.is_empty():
			own[id] = true
	var player: Dictionary = state.get("player") if state.get("player") is Dictionary else {}
	var player_id: String = _id(player.get("id"))
	var locations: Dictionary = {}
	for system: Dictionary in systems:
		for planet: Dictionary in system["planets"]:
			var id: String = _id(planet.get("id"))
			var owned: bool = own.has(id) or (not player_id.is_empty() and _id(planet.get("owner_type")) == "player" and _id(planet.get("owner_id")) == player_id)
			if not id.is_empty() and owned:
				locations[id] = {"system": system, "planet": planet}
	for id: String in [requested, _id(state.get("selected_planet")), _id(state.get("planet_id")), _id(state.get("home_id"))]:
		if locations.has(id):
			return locations[id]
	var ids: Array = locations.keys()
	ids.sort_custom(func(a: String, b: String) -> bool: return Routes.id_before(a, b))
	return locations[ids[0]] if not ids.is_empty() else {}


static func _systems(value: Variant) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for entry: Dictionary in _dictionaries(value):
		if _id(entry.get("id")).is_empty() or _id(entry.get("visibility")) == "hidden" or (entry.get("visible") is bool and not entry["visible"]):
			continue
		var system: Dictionary = entry.duplicate()
		system["id"] = _id(entry.get("id"))
		system["planets"] = _dictionaries(entry.get("planets"))
		# GalaxyRoutes expects numeric edge weights. Discard malformed edge records
		# before handing them to its shared, deterministic Dijkstra implementation.
		if entry.get("connections") is Array:
			var edges: Array[Dictionary] = []
			for edge: Dictionary in _dictionaries(entry["connections"]):
				var distance: float = _number(edge.get("distance"))
				var target_id: String = _id(edge.get("system_id"))
				if not target_id.is_empty() and is_finite(distance) and distance > 0.0:
					edges.append({"system_id": target_id, "distance": distance, "kind": _id(edge.get("kind", "orbit"))})
			system["connections"] = edges
		result.append(system)
	return result


static func _discovered(record: Dictionary) -> bool:
	if record.has("visibility") and not (record["visibility"] is String or record["visibility"] is StringName):
		return false
	if _id(record.get("visibility")).to_lower() in ["unknown", "hidden", "undiscovered", "unseen"]:
		return false
	for key: String in ["discovered", "is_discovered", "known", "visible"]:
		if record.get(key) is bool and not record[key]:
			return false
	# Older public snapshots omit visibility but expose known planet ownership.
	return true


static func _galaxy_id(system: Dictionary) -> String:
	var id: String = _id(system.get("galaxy_id", "g1"))
	return id if not id.is_empty() else "g1"


static func _galaxy_name(state: Dictionary, id: String) -> String:
	for galaxy: Dictionary in _dictionaries(state.get("galaxies")):
		if _id(galaxy.get("id")) == id:
			return _name(galaxy)
	return id


static func _available_galaxies(state: Dictionary) -> Dictionary:
	# _galaxy_catalog() uses g1 for old/empty states. A target outside the actual
	# selector catalog would be reset to another galaxy by _refresh_galaxy().
	if not state.get("galaxies") is Array or state["galaxies"].is_empty():
		return {"g1": true}
	var result: Dictionary = {}
	for galaxy: Dictionary in _dictionaries(state["galaxies"]):
		var id: String = _id(galaxy.get("id"))
		if not id.is_empty():
			result[id] = true
	return result


static func _name(record: Dictionary) -> String:
	var name: String = _id(record.get("name"))
	return name if not name.is_empty() else _id(record.get("id"))


static func _dictionaries(value: Variant) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if value is Array:
		for entry: Variant in value:
			if entry is Dictionary:
				result.append(entry)
	return result


static func _id(value: Variant) -> String:
	if value is String or value is StringName:
		return str(value).strip_edges()
	if value is int:
		return str(value)
	if value is float and is_finite(value) and value == floorf(value):
		return str(int(value))
	return ""


static func _number(value: Variant) -> float:
	if value is int or value is float:
		return float(value) if is_finite(float(value)) else INF
	if value is String and value.is_valid_float():
		return float(value) if is_finite(float(value)) else INF
	return INF
