extends RefCounted
## Read-only recommendations from the same catalog and queues used by the UI.
## Never orders projects, changes server onboarding or infers completed timers.

static func entry(state: Dictionary, group: String, key: String) -> Dictionary:
	for item: Dictionary in state.get("catalog", {}).get(group, []):
		if str(item.get("key", "")) == key:
			return item
	return {}


static func scout_report(report: Dictionary) -> bool:
	return report.has("planet_scout") or report.has("scout") or str(report.get("type", "")) == "scout" or (report.get("system_scout") is Dictionary and not report["system_scout"].is_empty())


static func completed_veteran(state: Dictionary) -> bool:
	# Starter ships and level-one facilities are deliberately NOT veteran proof.
	return bool(state.get("onboarding", {}).get("finished", false)) or state.get("own_planets", []).size() >= 2


static func evaluate(state: Dictionary, memory: Dictionary = {}) -> Dictionary:
	if str(state.get("player", {}).get("id", "")).is_empty() or str(state.get("player", {}).get("race_id", "")).is_empty() or state.get("catalog", {}).is_empty():
		return {}
	if bool(memory.get("finished", false)) or completed_veteran(state):
		return {"finished": true}
	var production: Dictionary = _production_entry(state)
	var production_done: bool = bool(memory.get("production_done", false))
	for item: Dictionary in state.get("catalog", {}).get("buildings", []):
		if item.has("production_resource") and int(item.get("level", 0)) >= 2:
			production_done = true
	var result: Dictionary
	if not production_done and not production.is_empty():
		# Fix an actual shortage before recommending more energy consumption.
		var energy: Dictionary = _energy_entry(state)
		if float(state.get("energy", {}).get("factor", 1.0)) < 0.999 and not energy.is_empty():
			result = _project(state, "buildings", energy, "Przywróć pełne wydobycie", "Kolonii brakuje energii. Więcej energii przywróci wydajność kopalń.")
		else:
			result = _project(state, "buildings", production, "Rozwiń wydobycie", "Ulepsz wydobycie, aby szybciej gromadzić surowce na kolejne projekty.")
	else:
		var energy: Dictionary = _energy_entry(state)
		if float(state.get("energy", {}).get("factor", 1.0)) < 0.999 and not energy.is_empty():
			result = _project(state, "buildings", energy, "Przywróć pełne wydobycie", "Kolonii brakuje energii. Więcej energii przywróci wydajność kopalń.")
		else:
			result = _exploration(state, memory)
	result["production_done"] = production_done
	if bool(result.get("waiting", false)):
		result["parallel"] = _parallel(state, result)
	return result


static func _exploration(state: Dictionary, _memory: Dictionary) -> Dictionary:
	for report: Dictionary in state.get("reports", []):
		if scout_report(report):
			return {"title": "Odczytaj wynik zwiadu", "description": "Raport pokazuje wolne planety i właścicieli w układzie. Otwórz go przed planowaniem kolejnej misji." if report.has("system_scout") else "Raport pokazuje, co zwiadowca odkrył na planecie. Otwórz go przed planowaniem kolejnej misji.", "action": "reports", "key": str(report.get("id", "")), "button": "Otwórz raporty"}
	for fleet: Dictionary in state.get("fleets", []):
		if str(fleet.get("mission", "")) == "scout":
			return {"title": "Zwiad jest w drodze", "description": "Wynik pojawi się w Raportach po dotarciu zwiadowcy do celu. W tym czasie możesz rozwijać kolonię.", "action": "missions", "key": str(fleet.get("id", "")), "button": "Pokaż misję", "waiting": true, "lane": "flight"}
	var scout: Dictionary = entry(state, "ships", "scout")
	if int(state.get("ships", {}).get("scout", 0)) > 0:
		var target: String = _scout_target(state)
		return {"title": "Poznaj sąsiednią planetę", "description": "Masz zwiadowcę. Wybierz cel i sprawdź paliwo oraz czas lotu przed wysłaniem. Zwiad nie jest atakiem.", "action": "scout" if not target.is_empty() else "galaxy", "key": target, "button": "Przygotuj zwiad" if not target.is_empty() else "Wybierz cel na mapie"}
	if not scout.is_empty():
		var required: Dictionary = _first_requirement(state, "ships", scout, {})
		if not required.is_empty():
			return _project(state, str(required.group), required.entry, "Przygotuj pierwszy zwiad", "Ukończ wymagane budynki i badania, aby rozpocząć budowę zwiadowcy.")
		return _project(state, "ships", scout, "Zbuduj zwiadowcę", "Zwiadowca odkrywa planety i dostarcza raporty. W szczegółach wybierz liczbę statków i potwierdź budowę.")
	# An older server without this entry must not receive an invented project.
	return {"title": "Poznaj galaktykę", "description": "Otwórz mapę, aby obejrzeć układy i dostępne cele zwiadu.", "action": "galaxy", "key": "", "button": "Otwórz mapę"}


static func _first_requirement(state: Dictionary, group: String, item: Dictionary, visited: Dictionary) -> Dictionary:
	var identity: String = group + ":" + str(item.get("key", ""))
	if visited.has(identity):
		return {}
	visited[identity] = true
	var candidates: Array[Dictionary] = []
	for requirement: Dictionary in item.get("requirements", []):
		if bool(requirement.get("met", false)):
			continue
		var required_group: String = str(requirement.get("group", "buildings"))
		var required: Dictionary = entry(state, required_group, str(requirement.get("key", "")))
		if required.is_empty():
			continue
		var deeper: Dictionary = _first_requirement(state, required_group, required, visited.duplicate())
		candidates.append(deeper if not deeper.is_empty() else {"group": required_group, "entry": required})
	# An available parallel prerequisite takes priority over one already queued.
	for candidate: Dictionary in candidates:
		if bool(candidate.entry.get("enabled", false)) and _queued(state, str(candidate.group), str(candidate.entry.get("key", ""))).is_empty():
			return candidate
	return candidates[0] if not candidates.is_empty() else {}


static func _project(state: Dictionary, group: String, item: Dictionary, title: String, description: String) -> Dictionary:
	var key: String = str(item.get("key", ""))
	var queued: Dictionary = _queued(state, group, key)
	var lane: String = _lane(group)
	var busy: bool = not queued.is_empty() or _lane_busy(state, lane)
	return {"title": title, "description": description, "action": "building" if group == "buildings" else "research" if group == "research" else "ship", "key": key,
		"button": "Pokaż projekt", "name": str(item.get("name", "")), "reason": str(item.get("reason", "")),
		"waiting": busy, "lane": lane, "queued": not queued.is_empty(), "planned": bool(queued.get("planned", false)), "ends_at": float(queued.get("ends_at", 0))}


static func _lane(group: String) -> String:
	return "build" if group in ["build", "building", "buildings"] else "research" if group == "research" else "ship"


static func _queued(state: Dictionary, group: String, key: String) -> Dictionary:
	var lane: String = _lane(group)
	for task: Dictionary in state.get("queue", []):
		if _lane(str(task.get("kind", ""))) == lane and str(task.get("key", "")) == key:
			return task
	var research: Variant = state.get("research_queue")
	if group == "research" and research is Dictionary and str(research.get("key", "")) == key:
		return research
	for task: Dictionary in state.get("planned_orders", []):
		if str(task.get("planet_id", "")) == str(state.get("planet_id", "")) and _lane(str(task.get("kind", ""))) == lane and str(task.get("key", "")) == key and str(task.get("status", "")) not in ["blocked", "paused_subscription"]:
			var queued: Dictionary = task.duplicate()
			queued["planned"] = true
			return queued
	return {}


static func _lane_busy(state: Dictionary, lane: String) -> bool:
	for task: Dictionary in state.get("queue", []):
		if _lane(str(task.get("kind", ""))) == lane:
			return true
	return lane == "research" and state.get("research_queue") is Dictionary and not state.research_queue.is_empty()


static func _production_entry(state: Dictionary) -> Dictionary:
	var best: Dictionary = {}
	for item: Dictionary in state.get("catalog", {}).get("buildings", []):
		if not item.has("production_resource") or int(item.get("level", 0)) >= int(item.get("max_level", 12)):
			continue
		if best.is_empty() or int(item.get("level", 0)) < int(best.get("level", 0)):
			best = item
	return best


static func _energy_entry(state: Dictionary) -> Dictionary:
	for item: Dictionary in state.get("catalog", {}).get("buildings", []):
		if item.has("energy_supply_per_level") and int(item.get("level", 0)) < int(item.get("max_level", 12)):
			return item
		for metric: Dictionary in item.get("details", {}).get("metrics", []):
			if str(metric.get("key", "")) == "energy_supply" and metric.get("next") != null and float(metric.next) > float(metric.get("current", 0)):
				return item
	return {}


static func _parallel(state: Dictionary, waiting: Dictionary) -> Dictionary:
	var busy_lane: String = str(waiting.get("lane", ""))
	# The existing starter fleet can explore while a building is under construction.
	if busy_lane != "flight" and int(state.get("ships", {}).get("scout", 0)) > 0:
		var no_scout_flight: bool = true
		for fleet: Dictionary in state.get("fleets", []):
			no_scout_flight = no_scout_flight and str(fleet.get("mission", "")) != "scout"
		if no_scout_flight:
			return {"action": "galaxy", "key": "", "button": "W tym czasie: wybierz cel zwiadu"}
	var scout: Dictionary = entry(state, "ships", "scout")
	if not scout.is_empty() and int(state.get("ships", {}).get("scout", 0)) == 0:
		var required: Dictionary = _first_requirement(state, "ships", scout, {})
		if not required.is_empty() and _lane(str(required.group)) != busy_lane and bool(required.entry.get("enabled", false)):
			return {"action": "building" if required.group == "buildings" else "research", "key": str(required.entry.key), "button": "W tym czasie: przygotuj zwiadowcę"}
		if busy_lane != "ship" and bool(scout.get("enabled", false)) and _queued(state, "ships", "scout").is_empty():
			return {"action": "ship", "key": "scout", "button": "W tym czasie: zbuduj zwiadowcę"}
	if busy_lane != "build" and not _lane_busy(state, "build"):
		var production: Dictionary = _production_entry(state)
		if bool(production.get("enabled", false)) and _queued(state, "buildings", str(production.get("key", ""))).is_empty():
			return {"action": "building", "key": str(production.key), "button": "W tym czasie: rozwiń wydobycie"}
	return {"action": "galaxy", "key": "", "button": "W tym czasie: obejrzyj mapę"}


static func _scout_target(state: Dictionary) -> String:
	var owned: Dictionary = {}
	for planet: Dictionary in state.get("own_planets", []):
		owned[str(planet.get("id", ""))] = true
	var origin: Dictionary = {}
	var origin_slot: float = 0.0
	for system: Dictionary in state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			if str(planet.get("id", "")) == str(state.get("planet_id", "")):
				origin = system
				origin_slot = float(planet.get("slot", 0))
	var candidates: Array[Dictionary] = []
	for system: Dictionary in state.get("galaxy", []):
		if str(system.get("galaxy_id", state.get("planet_galaxy_id", "g1"))) != str(state.get("planet_galaxy_id", "g1")):
			continue
		var same_system: bool = not origin.is_empty() and str(system.get("id", "")) == str(origin.get("id", ""))
		var distance: float = INF
		if origin.has("x") and origin.has("y") and system.has("x") and system.has("y"):
			distance = Vector2(float(origin.x), float(origin.y)).distance_to(Vector2(float(system.x), float(system.y)))
		for planet: Dictionary in system.get("planets", []):
			var id: String = str(planet.get("id", ""))
			if id.is_empty() or owned.has(id) or str(planet.get("owner_id", "")) == str(state.get("player", {}).get("id", "")):
				continue
			candidates.append({"id": id, "same_system": same_system,
				"distance": distance + absf(float(planet.get("slot", origin_slot)) - origin_slot) * 0.08,
				"unowned": str(planet.get("owner_type", "")) == "empty"})
	candidates.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if bool(a.same_system) != bool(b.same_system):
			return bool(a.same_system)
		if float(a.distance) != float(b.distance):
			return float(a.distance) < float(b.distance)
		if bool(a.unowned) != bool(b.unowned):
			return bool(a.unowned)
		return str(a.id) < str(b.id))
	return str(candidates[0].id) if not candidates.is_empty() else ""
