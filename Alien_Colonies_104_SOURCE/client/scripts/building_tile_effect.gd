extends RefCounted
## One short purpose/effect from the same authoritative values as the details.
const RESOURCE_LABELS: Dictionary = {"metal": "Metal: %s/h", "crystal": "Kryształy: %s/h", "fuel": "Paliwo: %s/h"}
const EFFECTS: Dictionary = {
	"mining_energy_reduction": "Energia kopalń −%s%%",
	"scout_time_reduction": "Czas zwiadu −%s%%",
	"research_crystal_refund": "Badania: zwrot kryształów %s%%",
	"batch_time_reduction_per_extra": "Partia: −%s%% czasu / kolejny",
	"defense_first_volley": "1. salwa obrony +%s%%",
	"wreck_recovery_fraction": "Metal z wraków: %s%%",
	"building_time_reduction": "Czas budynków −%s%%",
	"colony_start_building_bonus": "Nowa kolonia: 4 budynki +%s poz.",
	"renewal_fraction": "Regeneracja obrony +%s p.p.",
	"ship_time_reduction": "Statki i obrona: czas −%s%%",
	"protected_resources": "Chroni %s / surowiec",
	"fleet_fuel_reduction": "Paliwo lotów −%s%%",
	"production_all": "Wydobycie +%s%%",
	"production_metal": "Wydobycie metalu +%s%%"
}

static func text(host, entry: Dictionary) -> String:
	var key: String = str(entry.get("key", ""))
	var first_level: bool = int(entry.get("level", 0)) == 0
	var field: String = "next" if first_level else "current"
	var metrics: Dictionary = {}
	for metric: Dictionary in entry.get("details", {}).get("metrics", []):
		metrics[str(metric.get("key", ""))] = metric.get(field)
	var result: String = ""
	if entry.has("production_resource"):
		var resource: String = str(entry["production_resource"])
		var value: Variant = metrics.get("mine_" + resource)
		if value != null:
			result = I18n.t(str(RESOURCE_LABELS[resource])) % _number(host, float(value))
	elif key == "power_plant":
		# The building output is authoritative and nonlinear; colony details
		# may also include the reserve and Dyson power.
		var output: Variant = entry.get("energy_supply_next" if first_level else "energy_supply_current")
		if output != null:
			result = I18n.t("Energia: +%s") % _number(host, float(output))
		elif metrics.get("energy_supply") != null:
			result = I18n.t("Energia kolonii: %s") % _number(host, float(metrics["energy_supply"]))
	elif key in ["lab", "shipyard"]:
		var value: Variant = metrics.get("lab_speed_bonus" if key == "lab" else "shipyard_speed_bonus")
		if value != null and float(value) > 0:
			result = (I18n.t("Badania: tempo +%s%%") if key == "lab" else I18n.t("Statki i obrona: tempo +%s%%")) % _number(host, float(value))
		else:
			result = I18n.t("Umożliwia badania") if key == "lab" else I18n.t("Buduje statki i obronę")
	elif key == "expedition_base":
		result = str(entry.get("effect_next" if first_level else "effect_current",""))
	elif key == "observatory":
		var observation: Dictionary = entry.get("observation", {}).get(field, {})
		if observation.has("range"):
			result = I18n.t("Podgląd: ±%s ukł.") % str(int(observation["range"]))
	elif metrics.get("storage_capacity") != null:
		result = I18n.t("Magazyny: %s / surowiec") % _number(host, float(metrics["storage_capacity"]))
	elif entry.has("building_effect"):
		var effect: Dictionary = entry["building_effect"]
		var effect_key: String = str(effect.get("key", ""))
		var value: Variant = effect.get(field)
		if EFFECTS.has(effect_key) and value != null:
			var number: float = float(value)
			if effect_key not in ["protected_resources", "colony_start_building_bonus"]: number *= 100.0
			result = I18n.t(str(EFFECTS[effect_key])) % _number(host, number)
	elif bool(entry.get("unique", false)):
		# Older servers already send true localized effects. Never infer balance
		# by parsing those strings or duplicating level multipliers in the client.
		result = str(entry.get("effect_next" if first_level else "effect_current", ""))
	if first_level and not result.is_empty():
		result = I18n.t("%s (poz. 1)") % result
	return result

static func _number(host, value: float) -> String:
	return host._number(value) if absf(value) >= 10000 else host._stat_number(value)
