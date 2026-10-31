extends RefCounted
## Read-only presentation/validation of the public state. Never guesses hidden
## planets, ownership, defence or flight prices. The server validates dispatch.

const GalaxyGuidance = preload("res://client/scripts/galaxy_guidance_model.gd")

const COLONIZATION_WARNING: String = "Uwaga: przy braku floty, obrony planetarnej i wsparcia sojuszników dodatkowa kolonia może zostać przejęta przez inną cywilizację. Planeta macierzysta jest chroniona przed przejęciem."

const MISSIONS: Array[String] = ["scout", "colonize", "attack", "transport", "expedition"]

static func dispatch_caption(mission: String) -> String:
	return {"scout": "Wyślij zwiad", "colonize": "Wyślij kolonizację", "attack": "Wyślij atak", "expedition": "Wyślij ekspedycję", "transport": "Wyślij transport"}.get(mission, "Wyślij flotę")

static func purpose(mission: String) -> String:
	return {"scout": "Poznaj zasoby i obronę celu.", "colonize": "Zajmij wolną planetę lub przejmij niebronioną kolonię. Po powodzeniu statki i zapasy pozostaną na miejscu.", "attack": "Zaangażuj obronę celu. Wynik walki nie jest gwarantowany.", "transport": "Dostarcz ładunek; statki wrócą do bazy."}.get(mission, "")

static func finite_number(value: Variant, fallback: float = -1.0) -> float:
	if not (value is int or value is float):
		return fallback
	return float(value) if is_finite(float(value)) else fallback

static func valid_quote(quote: Dictionary) -> bool:
	# Missing/malformed fields never become a free, instant, sendable trip.
	return bool(quote.get("ok", false)) and finite_number(quote.get("seconds")) > 0.0 and finite_number(quote.get("fuel_cost")) >= 0.0 and finite_number(quote.get("capacity")) >= 0.0

static func quoted_return(quote: Dictionary) -> Dictionary:
	# Preserve authoritative return timing separately from the conditional client
	# estimate: losses, colonization and tunnels can change or remove this leg.
	var at: float = finite_number(quote.get("return_at"))
	if at > 0.0:
		return {"at": at}
	var seconds: float = finite_number(quote.get("return_seconds"))
	return {"seconds": seconds} if seconds > 0.0 else {}

static func estimated_round_trip(quote: Dictionary, payload: Dictionary) -> float:
	# A clearly labelled client estimate for ordinary flights only. A tunnel's
	# outbound transfer says nothing about the duration of its natural return.
	if not valid_quote(quote) or str(payload.get("mission", "")) == "colonize" or str(payload.get("travel_mode", "")) == "tunnel" or quote.has("tunnel") or str(quote.get("route", {}).get("travel_mode", "")) == "tunnel":
		return -1.0
	return finite_number(quote.get("expedition", {}).get("round_trip_seconds")) if payload.get("mission") == "expedition" else finite_number(quote.get("seconds")) * 2.0

static func _positive_counts(values: Dictionary) -> Dictionary:
	var positive: Dictionary = {}
	for key: String in values:
		if int(values[key]) > 0:
			positive[key] = int(values[key])
	return positive

static func dispatched_fleet(action: Dictionary, response: Dictionary, previous_ids: Array) -> Dictionary:
	var snapshot: Variant = response.get("state", {})
	if not snapshot is Dictionary:
		return {}
	var explicit_id: String = str(response.get("fleet_id", ""))
	var matches: Array[Dictionary] = []
	for fleet: Dictionary in snapshot.get("fleets", []):
		var id: String = str(fleet.get("id", ""))
		if id.is_empty() or (not explicit_id.is_empty() and id != explicit_id) or (explicit_id.is_empty() and id in previous_ids):
			continue
		if str(fleet.get("origin_id", "")) != str(action.get("planet_id", "")) or str(fleet.get("target_id", "")) != str(action.get("target_id", "")) or str(fleet.get("mission", "")) != str(action.get("mission", "")):
			continue
		if str(fleet.get("scout_scope", "planet")) != str(action.get("scout_scope", "planet")):
			continue
		if str(action.get("scout_scope", "")) == "system" and str(fleet.get("target_system_id", "")) != str(action.get("target_system_id", "")):
			continue
		if _positive_counts(fleet.get("ships", {})) != _positive_counts(action.get("ships", {})):
			continue
		matches.append(fleet)
	# Concurrent commands in another client can make matching ambiguous. The
	# acknowledged command is still shown, but no unrelated countdown is chosen.
	return matches[0].duplicate(true) if matches.size() == 1 else {}

static func target(world: Dictionary, id: String, system_id: String = "") -> Dictionary:
	if not system_id.is_empty():
		for system: Dictionary in world.get("galaxy", []):
			if str(system.get("id", "")) == system_id and GalaxyGuidance.system_scout_target(system, str(world.get("planet_id", ""))) == id:
				return {"id": id, "name": str(system.get("name", system_id)), "known": false, "planet": {}, "system": system, "galaxy_id": str(system.get("galaxy_id", "g1")), "scout_scope": "system", "target_system_id": system_id}
		return {}
	var zone: Dictionary = world.get("expeditions", {}).get("zone", {})
	if not id.is_empty() and id == str(zone.get("id", "")):
		return {"id":id,"name":str(zone.get("name",I18n.t("Nieznany sektor"))),"known":false,"expedition":true,"planet":{},"system":{"id":zone.get("system_id","")},"galaxy_id":zone.get("galaxy_id","g1")}
	if id.is_empty():
		return {}
	# Known planets take precedence over a system's representative scout target.
	for system: Dictionary in world.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			if str(planet.get("id", "")) == id:
				return {"id": id, "name": str(planet.get("name", id)), "known": true, "planet": planet, "system": system, "galaxy_id": str(system.get("galaxy_id", "g1"))}
	for system: Dictionary in world.get("galaxy", []):
		if str(system.get("scout_target_id", "")) == id:
			return {"id": id, "name": str(system.get("name", id)), "known": false, "planet": {}, "system": system, "galaxy_id": str(system.get("galaxy_id", "g1"))}
	return {}

static func origin(world: Dictionary) -> Dictionary:
	var id: String = str(world.get("planet_id", ""))
	var found: Dictionary = target(world, id)
	if not found.is_empty():
		return found
	for planet: Dictionary in world.get("own_planets", []):
		if str(planet.get("id", "")) == id:
			return {"id": id, "name": str(planet.get("name", id)), "known": true, "planet": planet, "system": {"id": planet.get("system_id", "")}, "galaxy_id": str(planet.get("galaxy_id", "g1"))}
	return {"id": id, "name": str(world.get("planet_name", "")), "known": true, "planet": {}, "system": {}, "galaxy_id": str(world.get("planet_galaxy_id", "g1"))}

static func owned(world: Dictionary, record: Dictionary) -> bool:
	var player: String = str(world.get("player", {}).get("id", ""))
	return not player.is_empty() and str(record.get("planet", {}).get("owner_id", "")) == player

static func allied(world: Dictionary, record: Dictionary) -> bool:
	var alliance: String = str(world.get("alliance", {}).get("id", ""))
	return not alliance.is_empty() and alliance == str(record.get("planet", {}).get("alliance_id", ""))

static func default_mission(world: Dictionary, record: Dictionary) -> int:
	if bool(record.get("expedition",false)):
		return 4
	if str(record.get("scout_scope", "")) == "system" or not bool(record.get("known", false)):
		return 0
	if str(record.get("planet", {}).get("owner_type", "")) == "empty":
		return 1
	if owned(world, record) or allied(world, record):
		return 3
	# An enemy is not automatically attacked; recon is the safe default.
	return 0

static func mission_reason(world: Dictionary, record: Dictionary, mission: int, now: float) -> String:
	if mission == 4:
		var info: Dictionary = world.get("expeditions",{})
		if int(info.get("level",0)) < 1:
			return "Zbuduj bazę ekspedycyjną na planecie startowej."
		if int(info.get("active",0)) >= int(info.get("max_active",0)):
			return "Wszystkie miejsca na ekspedycje są zajęte. Rozbuduj bazę albo poczekaj na powrót floty."
		return "" if bool(record.get("expedition",false)) else "Wybierz strefę ekspedycyjną przy kolonii startowej."
	if bool(record.get("expedition",false)):
		return "Wybierz cel na mapie."
	if record.is_empty():
		return "Najpierw wybierz cel na mapie."
	if str(record.get("scout_scope", "")) == "system":
		return "" if mission == 0 else "Zwiad całego układu wymaga misji zwiadowczej."
	if str(record.get("id", "")) == str(world.get("planet_id", "")):
		return "To baza startowa. Wybierz inną planetę."
	if mission < 0 or mission >= MISSIONS.size():
		return "Wybierz rodzaj misji."
	if not bool(record.get("known", false)):
		return "Nieznany cel. Najpierw wyślij zwiad." if mission != 0 else ""
	var planet: Dictionary = record.get("planet", {})
	var kind: String = str(planet.get("owner_type", ""))
	match mission:
		1:
			if owned(world, record):
				return "Ta planeta już należy do twojego imperium."
			if kind == "player" and bool(world.get("colonization_capture", {}).get("enabled", false)):
				if bool(planet.get("is_home_planet", false)):
					return "Planeta matka — nie można jej przejąć."
				if not planet.has("is_home_planet"):
					return "Odśwież zwiad, aby sprawdzić, czy to planeta matka."
				if allied(world, record):
					return "Nie możesz przejąć kolonii sojusznika."
				if float(planet.get("protected_until", 0)) > now:
					return "Ochrona startowa · przejęcie niedostępne"
			elif kind != "empty":
				return "Kolonizacja wymaga wolnej planety."
		2:
			if kind == "empty" or owned(world, record):
				return "Atak wymaga obcej kolonii."
			if allied(world, record):
				return "Nie możesz atakować sojusznika."
			if kind == "player" and float(planet.get("protected_until", 0)) > now:
				return "Ochrona startowa · atak niedostępny"
		3:
			if not owned(world, record) and not allied(world, record):
				return "Transport: tylko własne kolonie lub sojusznicy."
	return ""

static func ship_total(ships: Dictionary) -> int:
	var total: int = 0
	for value: Variant in ships.values():
		total += maxi(0, int(value))
	return total

static func capacity(world: Dictionary, ships: Dictionary) -> int:
	var total: float = 0.0
	for entry: Dictionary in world.get("catalog", {}).get("ships", []):
		total += float(entry.get("capacity", 0)) * maxi(0, int(ships.get(str(entry.get("key", "")), 0)))
	# Match the server's six-decimal rounding before flooring fractional hull capacity.
	return floori(roundf(total * 1000000.0) / 1000000.0)

static func required_ship(world: Dictionary, mission: int) -> String:
	if mission in [0,4]:
		return "scout"
	if mission == 1:
		return "colonizer"
	if mission == 2:
		for entry: Dictionary in world.get("catalog", {}).get("ships", []):
			if str(entry.get("category", "")) == "combat" and int(world.get("ships", {}).get(str(entry.get("key", "")), 0)) > 0:
				return str(entry["key"])
	return ""

static func draft_reason(world: Dictionary, payload: Dictionary, now: float) -> String:
	var mission: int = MISSIONS.find(str(payload.get("mission", "")))
	var record: Dictionary = target(world, str(payload.get("target_id", "")), str(payload.get("target_system_id", "")) if str(payload.get("scout_scope", "")) == "system" else "")
	var reason: String = mission_reason(world, record, mission, now)
	if not reason.is_empty():
		return reason
	var ships: Dictionary = payload.get("ships", {})
	if ship_total(ships) == 0:
		return "Wybierz przynajmniej jeden statek."
	for key: String in ships:
		if int(ships[key]) < 0 or int(ships[key]) > int(world.get("ships", {}).get(key, 0)):
			return "Wybrana flota nie jest już dostępna w tej kolonii."
		if int(ships[key]) > 10000:
			return "Maksymalnie 10 000 statków jednego typu w misji."
	if mission in [0,4] and int(ships.get("scout", 0)) < 1:
		return "Dodaj zwiadowcę do wybranej floty."
	if mission == 1:
		if int(ships.get("colonizer", 0)) < 1:
			return "Dodaj kolonizator do wybranej floty."
		var pending: int = 0
		for fleet: Dictionary in world.get("fleets", []):
			if str(fleet.get("mission", "")) == "colonize" and str(fleet.get("status", "")) == "outbound":
				pending += 1
		if world.get("own_planets", []).size() + pending >= int(world.get("limits", {}).get("colonies", 12)):
			return "Osiągnięto limit kolonii, wliczając wysłane kolonizacje."
	if mission == 2:
		var combat: int = 0
		for entry: Dictionary in world.get("catalog", {}).get("ships", []):
			if str(entry.get("category", "")) == "combat":
				combat += int(ships.get(str(entry.get("key", "")), 0))
		if combat < 1:
			return "Dodaj okręt bojowy do wybranej floty."
	if mission == 4 and int(payload.get("expedition_hours",1)) not in [1,3,6]:
		return "Wybierz 1, 3 albo 6 godzin poszukiwań."
	var ordinary: int = 0
	for fleet: Dictionary in world.get("fleets",[]):
		if str(fleet.get("mission","")) != "expedition":
			ordinary += 1
	if mission != 4 and ordinary >= 8:
		return "Wszystkie 8 miejsc na misje jest zajęte."
	var cargo: Dictionary = payload.get("cargo", {})
	if ship_total(cargo) > capacity(world, ships):
		return "Ładunek przekracza pojemność wybranej floty."
	return ""
