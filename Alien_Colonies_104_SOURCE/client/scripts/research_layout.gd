extends RefCounted
## Three horizontal rows. Only research requirements affect progression.
const ROWS: int = 3


static func three_rows(catalog: Array) -> Dictionary:
	var items: Array[Dictionary] = []
	var keys: Dictionary = {}
	for entry: Dictionary in catalog:
		var key: String = str(entry.get("key", ""))
		if key.is_empty() or keys.has(key):
			continue
		keys[key] = true
		items.append(entry)
	items.sort_custom(_before)
	var parents: Dictionary = {}
	for entry: Dictionary in items:
		var required: Array[String] = []
		for requirement: Dictionary in entry.get("requirements", []):
			var parent: String = str(requirement.get("key", ""))
			if str(requirement.get("group", "")) == "research" and keys.has(parent) and not required.has(parent):
				required.append(parent)
		parents[str(entry["key"])] = required
	# First derive logical depth from the graph, independently of catalog order
	# and old server row coordinates. This groups independent peers together.
	var depths: Dictionary = {}
	var pending: Array[Dictionary] = items.duplicate()
	while not pending.is_empty():
		var ready_index: int = -1
		for index: int in range(pending.size()):
			var ready: bool = true
			for parent: String in parents[str(pending[index]["key"])]:
				if not depths.has(parent):
					ready = false
					break
			if ready:
				ready_index = index
				break
		if ready_index < 0:
			# A malformed server graph must not hang or switch the screen back
			# to vertical scrolling. Keep every item reachable in three rows.
			var fallback: Dictionary = {}
			for index: int in range(items.size()):
				fallback[str(items[index]["key"])] = {"row": index % ROWS, "column": index / ROWS, "depth": 0}
			return {"valid": true, "placements": fallback, "columns": ceili(float(items.size()) / ROWS), "rows": ROWS}
		var item: Dictionary = pending.pop_at(ready_index)
		var key: String = str(item["key"])
		var depth: int = 0
		for parent: String in parents[key]:
			depth = maxi(depth, int(depths[parent]) + 1)
		depths[key] = depth
	var placements: Dictionary = {}
	var columns: int = 0
	var maximum_depth: int = 0
	for key: String in depths:
		maximum_depth = maxi(maximum_depth, int(depths[key]))
	for depth: int in range(maximum_depth + 1):
		var peers: Array[Dictionary] = []
		var first_column: int = columns
		for item: Dictionary in items:
			var key: String = str(item["key"])
			if int(depths[key]) != depth:
				continue
			peers.append(item)
			for parent: String in parents[key]:
				first_column = maxi(first_column, int(placements[parent]["column"]) + 1)
		# A tier with more than three peers continues into later columns.
		# No cap hides late technologies, and no child precedes a parent.
		var occupied: Dictionary = {}
		for item: Dictionary in peers:
			var key: String = str(item["key"])
			var column: int = first_column
			var preferred_row: int = clampi(int(item.get("tree", {}).get("column", 0)), 0, ROWS - 1)
			var row: int = preferred_row
			while occupied.has(Vector2i(column, row)):
				var found: bool = false
				for offset: int in range(ROWS):
					var candidate: int = (preferred_row + offset) % ROWS
					if not occupied.has(Vector2i(column, candidate)):
						row = candidate
						found = true
						break
				if found:
					break
				column += 1
			occupied[Vector2i(column, row)] = true
			placements[key] = {"row": row, "column": column, "depth": depth}
			columns = maxi(columns, column + 1)
	return {"valid": true, "placements": placements, "columns": columns, "rows": ROWS}


static func _before(a: Dictionary, b: Dictionary) -> bool:
	var a_tree: Dictionary = a.get("tree", {})
	var b_tree: Dictionary = b.get("tree", {})
	if int(a_tree.get("row", 0)) != int(b_tree.get("row", 0)):
		return int(a_tree.get("row", 0)) < int(b_tree.get("row", 0))
	if int(a_tree.get("column", 0)) != int(b_tree.get("column", 0)):
		return int(a_tree.get("column", 0)) < int(b_tree.get("column", 0))
	return str(a.get("key", "")) < str(b.get("key", ""))
