extends RefCounted
## Presentation of authoritative catalog values. This helper never authorizes an
## order, forecasts a future bonus, or changes the selected quantity/resources.
const RESOURCE_KEYS: Array[String] = ["metal", "crystal", "fuel"]
const PlayerActivity = preload("res://client/scripts/player_activity.gd")
const RESOURCE_NAMES: Dictionary = {"metal": "Metal", "crystal": "Kryształy", "fuel": "Paliwo"}
const BUILDING_ROLES: Dictionary = {
	"metal_mine": "Produkcja metalu", "crystal_mine": "Produkcja kryształów",
	"refinery": "Produkcja paliwa", "power_plant": "Energia kolonii",
	"shipyard": "Budowa statków i obrony", "lab": "Badania technologii",
	"observatory": "Obserwacja sąsiednich układów",
	"phase_vault": "Magazynowanie i ochrona surowców",
	"living_vault": "Magazynowanie i ochrona surowców",
	"armored_vault": "Magazynowanie i ochrona surowców"
}
const EFFECT_ROLES: Dictionary = {
	"mining_energy_reduction": "Oszczędzanie energii", "scout_time_reduction": "Szybszy zwiad",
	"research_crystal_refund": "Zwrot kosztów badań", "batch_time_reduction_per_extra": "Szybsza produkcja seryjna",
	"defense_first_volley": "Wzmocnienie obrony", "wreck_recovery_fraction": "Odzysk metalu",
	"building_time_reduction": "Szybsza rozbudowa", "colony_start_building_bonus": "Rozwój nowych kolonii",
	"renewal_fraction": "Regeneracja obrony", "ship_time_reduction": "Szybsza budowa floty",
	"protected_resources": "Ochrona surowców", "fleet_fuel_reduction": "Oszczędzanie paliwa",
	"production_all": "Wzmocnienie produkcji", "production_metal": "Wzmocnienie produkcji metalu"
}

static func role(entry: Dictionary, kind: String) -> String:
	if kind != "build":
		return ""
	var key: String = str(entry.get("key", ""))
	if BUILDING_ROLES.has(key):
		return I18n.t(str(BUILDING_ROLES[key]))
	var effect: String = str(entry.get("building_effect", {}).get("key", ""))
	return I18n.t(str(EFFECT_ROLES[effect])) if EFFECT_ROLES.has(effect) else ""

static func _has_next(entry: Dictionary) -> bool:
	return not (int(entry.get("max_level", 0)) > 0 and int(entry.get("level", 0)) >= int(entry["max_level"]))

static func _number(host, value: float) -> String:
	return host._stat_number(value)

static func _pair(host, entry: Dictionary, metric: Dictionary, unit: String = "") -> String:
	if metric.get("current") == null:
		return ""
	var current: float = float(metric["current"])
	var result: String = _number(host, current)
	if _has_next(entry) and metric.get("next") != null:
		var following: float = float(metric["next"])
		var delta: float = following - current
		result += " → " + _number(host, following)
		result += " (" + ("+" if delta >= 0 else "") + _number(host, delta) + ")"
	return result + unit

static func building_effect(host, entry: Dictionary) -> String:
	var metrics: Dictionary = {}
	for value: Variant in entry.get("details", {}).get("metrics", []):
		if value is Dictionary:
			metrics[str(value.get("key", ""))] = value
	var lines: PackedStringArray = PackedStringArray()
	var resource: String = str(entry.get("production_resource", ""))
	if RESOURCE_NAMES.has(resource) and metrics.has("mine_" + resource):
		var output: String = _pair(host, entry, metrics["mine_" + resource], " / h")
		if not output.is_empty():
			lines.append(I18n.t(str(RESOURCE_NAMES[resource])) + ": " + output)
	var key: String = str(entry.get("key", ""))
	var primary: String = "energy_supply" if key == "power_plant" else "lab_speed_bonus" if key == "lab" else "shipyard_speed_bonus" if key == "shipyard" else ""
	if not primary.is_empty() and metrics.has(primary):
		var output: String = _pair(host, entry, metrics[primary], "%" if primary.ends_with("bonus") else "")
		if not output.is_empty():
			lines.append((I18n.t("Energia kolonii") if primary == "energy_supply" else I18n.t("Premia do tempa")) + ": " + output)
	if metrics.has("energy_use"):
		var output: String = _pair(host, entry, metrics["energy_use"])
		if not output.is_empty():
			lines.append(I18n.t("Zużycie energii: %s") % output)
	if metrics.has("storage_capacity"):
		var output: String = _pair(host, entry, metrics["storage_capacity"])
		if not output.is_empty():
			lines.append(I18n.t("Pojemność każdego magazynu: %s") % output)
	# No local production/energy formula: legacy servers keep their supplied text.
	return "\n".join(lines)

static func missing_requirements(entry: Dictionary, state: Dictionary) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var seen: Dictionary = {}
	for value: Variant in entry.get("requirements", []):
		if not value is Dictionary:
			continue
		var requirement: Dictionary = value
		var group: String = str(requirement.get("group", "buildings"))
		var key: String = str(requirement.get("key", ""))
		var current: int = int(requirement.get("current", state.get(group, {}).get(key, 0)))
		var met: bool = bool(requirement.get("met", current >= int(requirement.get("level", 0))))
		var identity: String = group + ":" + key
		if met or key.is_empty() or seen.has(identity):
			continue
		seen[identity] = true
		var item: Dictionary = requirement.duplicate(true)
		item["current"] = current
		item["group"] = group
		result.append(item)
	return result

static func blockers(entry: Dictionary, state: Dictionary, amount: int = 1, kind: String = "build") -> Dictionary:
	var maximum: bool = kind not in ["ship", "defense"] and not _has_next(entry)
	var result: Dictionary = {"maximum": maximum, "deficits": {}, "eta_seconds": null, "no_production": [], "capacity_blocked": [], "requirements": []}
	if maximum:
		return result
	result["requirements"] = missing_requirements(entry, state)
	var eta: float = 0.0
	var can_accumulate: bool = true
	var limits: Dictionary = state.get("limits", {})
	for resource: String in RESOURCE_KEYS:
		var cost: float = maxf(0.0, float(entry.get("cost", {}).get(resource, 0))) * maxi(1, amount)
		var owned: float = maxf(0.0, float(state.get("resources", {}).get(resource, 0)))
		var deficit: float = maxf(0.0, cost - owned)
		if deficit <= 0.000001:
			continue
		result["deficits"][resource] = deficit
		var cap: Variant = state.get("storage", {}).get("capacity", {}).get(resource, limits.get("resource_cap"))
		if cap is Dictionary:
			cap = cap.get(resource)
		if cap != null and cost > float(cap):
			result["capacity_blocked"].append(resource)
			can_accumulate = false
		var rate: float = PlayerActivity.production_rate(state, resource)
		if rate <= 0.0:
			result["no_production"].append(resource)
			can_accumulate = false
		else:
			# State.production is the server's actual per-hour rate, after bonuses
			# and energy. Resource shortages accrue simultaneously, not serially.
			eta = maxf(eta, deficit * 3600.0 / rate)
	if can_accumulate and not result["deficits"].is_empty():
		result["eta_seconds"] = ceilf(eta)
	return result

static func explanation(host, entry: Dictionary, amount: int = 1, kind: String = "build", include_requirements: bool = true) -> String:
	var data: Dictionary = blockers(entry, host.state, amount, kind)
	if bool(data["maximum"]):
		return I18n.t("Maksymalny poziom.")
	var lines: PackedStringArray = PackedStringArray()
	var reason: String = host._server_text(entry.get("reason", ""))
	# Structured requirements already appear once on a construction card.
	# Preserve unrelated blockers, resource deficits and queue messages.
	var raw_reason: String = str(entry.get("reason", "")).strip_edges()
	var requirement_reason: bool = raw_reason.begins_with("Wymaga:") or reason.begins_with(I18n.t("Wymaga:")) or reason.begins_with("Requires:")
	if not reason.is_empty() and (include_requirements or not requirement_reason or entry.get("requirements", []).is_empty()):
		lines.append(reason)
	var missing: PackedStringArray = PackedStringArray()
	for resource: String in RESOURCE_KEYS:
		if data["deficits"].has(resource):
			missing.append(I18n.t(str(RESOURCE_NAMES[resource])) + ": " + str(ceili(float(data["deficits"][resource]))))
	if not missing.is_empty():
		lines.append(I18n.t("Brakuje: %s") % " · ".join(missing))
	if data["eta_seconds"] != null:
		lines.append(I18n.t("Przy obecnej produkcji: około %s, bez kolejnych wydatków.") % host._duration(float(data["eta_seconds"])))
	elif not data["capacity_blocked"].is_empty():
		var storage_reason: String = I18n.t("Rozbuduj skarbiec: pojemność magazynu jest za mała.")
		if not lines.has(storage_reason):
			lines.append(storage_reason)
	elif not data["no_production"].is_empty():
		lines.append(I18n.t("Produkcja wstrzymana — nieaktywność") if PlayerActivity.production_paused(host.state) else I18n.t("Brak produkcji części potrzebnych surowców. Samo czekanie nie wystarczy."))
	return "\n".join(lines)
