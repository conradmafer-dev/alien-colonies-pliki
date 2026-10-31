extends RefCounted
## Public corridor topology. Presentation never substitutes for a server quote.

static func id_before(left: String, right: String) -> bool:
	return left.naturalnocasecmp_to(right) < 0


static func has_topology(systems: Array) -> bool:
	if systems.is_empty():
		return false
	for value: Dictionary in systems:
		if not value.get("connections") is Array:
			return false
	return true


static func graph(systems: Array) -> Dictionary:
	var known: Dictionary = {}
	var result: Dictionary = {}
	for value: Dictionary in systems:
		known[str(value.get("id", ""))] = true
	for value: Dictionary in systems:
		var id: String = str(value.get("id", ""))
		var edges: Array[Dictionary] = []
		for entry: Variant in value.get("connections", []):
			if not entry is Dictionary:
				continue
			var edge: Dictionary = entry
			var target: String = str(edge.get("system_id", ""))
			var distance: float = float(edge.get("distance", 0.0))
			if target == id or not known.has(target) or not is_finite(distance) or distance <= 0.0:
				continue
			edges.append({"system_id": target, "distance": distance, "kind": str(edge.get("kind", "orbit"))})
		edges.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			return id_before(str(a["system_id"]), str(b["system_id"])))
		result[id] = edges
	return result


static func shortest_path(graph_value: Dictionary, origin: String, destination: String) -> Dictionary:
	if not graph_value.has(origin) or not graph_value.has(destination):
		return {}
	# Match server Dijkstra exactly: (distance, numeric system ID), sorted
	# neighbours and predecessor replacement only for a strict improvement.
	var distances: Dictionary = {origin: 0.0}
	var previous: Dictionary = {}
	var pending: Array[String] = [origin]
	var visited: Dictionary = {}
	while not pending.is_empty():
		pending.sort_custom(func(a: String, b: String) -> bool:
			return float(distances[a]) < float(distances[b]) if float(distances[a]) != float(distances[b]) else id_before(a, b))
		var current: String = pending.pop_front()
		if visited.has(current):
			continue
		visited[current] = true
		if current == destination:
			var ids: Array[String] = [current]
			var cursor: String = current
			while previous.has(cursor):
				cursor = str(previous[cursor])
				ids.push_front(cursor)
			return {"system_ids": ids, "distance": float(distances[current])}
		for edge: Dictionary in graph_value.get(current, []):
			var target: String = str(edge["system_id"])
			if visited.has(target):
				continue
			var candidate: float = roundf((float(distances[current]) + float(edge["distance"])) * 100000000.0) / 100000000.0
			if not distances.has(target) or candidate < float(distances[target]):
				distances[target] = candidate
				previous[target] = current
				if not pending.has(target):
					pending.append(target)
	return {}
