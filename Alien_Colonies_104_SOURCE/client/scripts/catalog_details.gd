extends RefCounted
const ResourceInfo = preload("res://client/scripts/resource_info.gd")
## Formats authoritative catalog data, not the visibility of compact widgets.
## One string is one paragraph; current/next values share a paragraph.
## Brief is the default. Detailed mode retains the full authoritative breakdown.
const BRIEF_DESCRIPTIONS: Dictionary = {
	"metal_mine": "Wydobywa metal.",
	"crystal_mine": "Wydobywa kryształy.",
	"refinery": "Produkuje paliwo.",
	"power_plant": "Dostarcza energię kolonii.",
	"shipyard": "Buduje statki i obronę planetarną.",
	"lab": "Prowadzi badania technologiczne."
}
const METRIC_LABELS: Dictionary = {
	"mine_metal": "Wydobycie budynku — metal", "mine_crystal": "Wydobycie budynku — kryształy", "mine_fuel": "Wydobycie budynku — paliwo",
	"colony_metal": "Produkcja kolonii — metal", "colony_crystal": "Produkcja kolonii — kryształy", "colony_fuel": "Produkcja kolonii — paliwo",
	"energy_use": "Zużycie energii budynku", "energy_supply": "Produkcja energii", "energy_efficiency": "Wydajność wydobycia przy dostępnej energii",
	"storage_capacity": "Pojemność każdego magazynu",
	"shipyard_projects": "Dostępne typy statków i obrony", "research_projects": "Dostępne projekty badań",
	"shipyard_speed_bonus": "Premia stoczni do tempa produkcji",
	"lab_speed_bonus": "Premia laboratorium do tempa badań",
	"facility_time_reduction": "Skrócenie czasu dzięki poziomowi budynku",
	"fleet_speed_bonus": "Premia badania do prędkości floty", "fleet_attack_bonus": "Premia badania do ataku floty"
}
const NOTES: Dictionary = {
	"shipyard_speed_rule": "Mnożnik tempa produkcji wynosi 1 + poziom stoczni. Obejmuje statki i obronę budowane na tej planecie.",
	"lab_speed_rule": "Mnożnik tempa badań wynosi 1 + poziom laboratorium na planecie rozpoczynającej badanie.",
	"storage_per_resource": "Pojemność dotyczy osobno metalu, kryształów i paliwa. Pełny magazyn wstrzymuje wydobycie danego surowca. Dostawy mogą przekroczyć limit.",
	"facility_time_scope": "Premie do tempa są sumowane między poziomami, a z innymi bonusami łączą się mnożnikowo. Wyższe tempo skraca czas, ale nie obniża kosztu. Już rozpoczęte projekty zachowują swój termin.",
	"production_actual": "Wydobycie uwzględnia rasę, umiejętności, budynki i dostępną energię. Produkcja kolonii obejmuje również wydobycie bazowe.",
	"next_local_only": "Podgląd następnego poziomu zakłada niezmienione pozostałe budynki i bonusy. Niedobór energii może ograniczyć przyrost produkcji.",
	"shipyard_unlocks_only": "Buduje statki i obronę planetarną. Poziomy odblokowują projekty; sam poziom stoczni nie skraca czasu produkcji.",
	"lab_unlocks_only": "Umożliwia badania i odblokowuje ich kolejne projekty. Sam poziom laboratorium nie skraca czasu badań.",
	"research_bonus_only": "Podana premia pochodzi z tego badania. Pozostałe bonusy rasy, umiejętności i badań są naliczane osobno."
}

static func brief_description(host, entry: Dictionary) -> String:
	# The server owns the wording and localization. Older servers only supply
	# description; blank or null brief fields must not erase that fallback.
	var brief: Variant = entry.get("brief_description")
	if brief is String and not brief.strip_edges().is_empty():
		return host._server_text(brief).strip_edges()
	return host._server_text(entry.get("description", "")).strip_edges()


static func description_paragraphs(host, entry: Dictionary, kind: String, detailed: bool = false) -> PackedStringArray:
	var sections: PackedStringArray = PackedStringArray()
	var full: String = host._server_text(entry.get("description", "")).strip_edges()
	var brief: String = brief_description(host, entry) if kind in ["ship", "research"] else full
	if not detailed and kind == "build" and BRIEF_DESCRIPTIONS.has(str(entry.get("key", ""))):
		brief = I18n.t(str(BRIEF_DESCRIPTIONS[str(entry["key"])]))
	if not brief.is_empty():
		sections.append(brief)
	if detailed and not full.is_empty() and full != brief:
		sections.append(full)
	return sections


static func unit_traits(host, entry: Dictionary, resource_icons: bool = false) -> PackedStringArray:
	var stats: PackedStringArray = PackedStringArray()
	if entry.has("speed"):
		var template: String = I18n.t("Prędkość: %s · Współczynnik: %s") if resource_icons else I18n.t("Prędkość: %s · Współczynnik paliwa: %s")
		var fuel: String = (ResourceInfo.token("fuel") + "\u00A0" if resource_icons else "") + host._stat_number(float(entry.get("effective_fuel", entry.get("fuel", 0))))
		stats.append(template % [host._stat_number(float(entry.get("effective_speed", entry.get("speed", 0)))), fuel])
	if float(entry.get("first_volley_multiplier", 1)) > 1:
		stats.append(I18n.t("Pierwsza salwa: +%s%%") % host._stat_number((float(entry["first_volley_multiplier"]) - 1.0) * 100.0))
	if float(entry.get("regeneration_fraction", 0)) > 0:
		stats.append(I18n.t("Regeneracja: %s%%") % host._stat_number(float(entry["regeneration_fraction"]) * 100.0))
	if float(entry.get("damage_reduction", 0)) > 0:
		stats.append(I18n.t("Redukcja obrażeń: %s%%") % host._stat_number(float(entry["damage_reduction"]) * 100.0))
	if float(entry.get("swarm_attack_multiplier", 1.0)) > 1.0:
		stats.append(I18n.t("Przeciw Rojowi · +%s%% ataku") % host._stat_number((float(entry["swarm_attack_multiplier"]) - 1.0) * 100.0))
	return stats


static func _value(host, value: float, unit: String) -> String:
	var text: String = host._stat_number(value)
	if unit == "per_hour":
		return text + " / h"
	if unit == "percent":
		return text + "%"
	return text

static func _exact_cost(host, cost: Dictionary, resource_icons: bool = false) -> String:
	if resource_icons:
		return ResourceInfo.cost(host, cost)
	var parts: PackedStringArray = PackedStringArray()
	for resource: String in host.RESOURCE_KEYS:
		var value: float = float(cost.get(resource, 0))
		if value > 0:
			parts.append(host._stat_number(value) + " " + I18n.t(str(host.RESOURCE_NAMES[resource])).to_lower())
	return " · ".join(parts) if not parts.is_empty() else I18n.t("Bez kosztu surowców")

static func _pair(level: int, current: String, following: String) -> String:
	var text: String = I18n.t("Teraz (poziom %d): %s") % [level, current]
	if not following.is_empty():
		text += "\n" + I18n.t("Następny (poziom %d): %s") % [level + 1, following]
	return text

static func _legacy_details(host, entry: Dictionary, kind: String) -> Dictionary:
	# Compatibility with the preceding server. Do not guess hidden multipliers.
	var key: String = str(entry.get("key", ""))
	var level: int = int(entry.get("level", 0))
	var has_next: bool = level < int(entry.get("max_level", 0))
	var metrics: Array = []
	var notes: Array = []
	var energy: Dictionary = host.state.get("energy", {})
	var supply: float = float(energy.get("supply", 0))
	if kind == "build" and entry.has("production_resource"):
		var resource: String = str(entry["production_resource"])
		# A legacy per_level field is not a constant increment. Without details
		# show only values supplied by the server; never invent a linear preview.
		metrics = [{"key": "colony_" + resource, "current": float(host.state.get("production", {}).get(resource, 0)), "next": null, "unit": "per_hour"}]
		if entry.has("energy_use_current"):
			metrics.append({"key": "energy_use", "current": entry["energy_use_current"], "next": entry.get("energy_use_next") if has_next else null})
		notes = ["production_actual", "next_local_only"]
	elif kind == "build" and key == "power_plant":
		metrics = [{"key": "energy_supply", "current": entry.get("energy_supply_current", supply), "next": entry.get("energy_supply_next") if has_next else null}]
	elif kind == "build" and key in ["shipyard", "lab"]:
		var available_now: Array = []
		var available_next: Array = []
		var milestones: Array = []
		var groups: Array = ["ships", "defenses"] if key == "shipyard" else ["research"]
		for group: String in groups:
			for target: Dictionary in host.state.get("catalog", {}).get(group, []):
				var met_now: bool = true
				var met_next: bool = true
				for req: Dictionary in target.get("requirements", []):
					met_now = met_now and bool(req.get("met", false))
					if str(req.get("group", "buildings")) == "buildings" and str(req.get("key", "")) == key:
						met_next = met_next and level + 1 >= int(req.get("level", 0))
						var other_met: bool = true
						for other: Dictionary in target.get("requirements", []):
							if str(other.get("group", "buildings")) != "buildings" or str(other.get("key", "")) != key:
								other_met = other_met and bool(other.get("met", false))
						milestones.append({"name": target.get("name", ""), "level": int(req.get("level", 0)), "other_requirements_met": other_met})
					else:
						met_next = met_next and bool(req.get("met", false))
				if met_now:
					available_now.append(target.get("name", ""))
				if met_next:
					available_next.append(target.get("name", ""))
		var unlocked: Array = []
		if has_next:
			for name in available_next:
				if not available_now.has(name):
					unlocked.append(name)
		return {"metrics": [{"key": "shipyard_projects" if key == "shipyard" else "research_projects", "current": available_now.size(), "next": available_next.size() if has_next else null}], "notes": ["shipyard_unlocks_only" if key == "shipyard" else "lab_unlocks_only"], "available_now": available_now, "unlocks_next": unlocked, "milestones": milestones}
	elif kind == "research" and key in ["propulsion", "weapons"]:
		metrics = [{"key": "fleet_speed_bonus" if key == "propulsion" else "fleet_attack_bonus", "current": level * 15.0, "next": (level + 1) * 15.0 if has_next else null, "unit": "percent"}]
		notes = ["research_bonus_only"]
	return {"metrics": metrics, "notes": notes}

static func _signed_percent(host, value: float) -> String:
	return ("+" if value > 0.000001 else "") + host._stat_number(value) + "%"


static func resource_effect(host, entry: Dictionary, following: bool, fallback: String) -> String:
	# These values are supplied by the server. Unknown/legacy effects keep their
	# authored prose instead of inferring a bonus from a translated sentence.
	var effect: Dictionary = entry.get("building_effect", {})
	var value: Variant = effect.get("next" if following else "current")
	if value == null:
		return fallback
	var percentage: String = host._stat_number(float(value) * 100.0) + "%"
	match str(effect.get("key", "")):
		"research_crystal_refund":
			return I18n.t("Zwrot z badań: %s") % (ResourceInfo.token("crystal") + "\u00A0" + percentage)
		"fleet_fuel_reduction":
			return I18n.t("Zużycie wypraw: %s") % (ResourceInfo.token("fuel") + "\u00A0−" + percentage)
		"wreck_recovery_fraction":
			return I18n.t("Odzysk z wraków: %s") % (ResourceInfo.token("metal") + "\u00A0" + percentage)
		"production_metal":
			return I18n.t("Wydobycie: %s") % (ResourceInfo.token("metal") + "\u00A0+" + percentage)
	return fallback


static func _brief_metrics(host, entry: Dictionary, kind: String, detail: Dictionary, resource_icons: bool = false) -> PackedStringArray:
	var sections: PackedStringArray = PackedStringArray()
	var key: String = str(entry.get("key", ""))
	var level: int = int(entry.get("level", 0))
	var has_next: bool = level < int(entry.get("max_level", 0))
	var metrics: Dictionary = {}
	for metric: Dictionary in detail.get("metrics", []):
		metrics[str(metric.get("key", ""))] = metric
	if kind == "build" and entry.has("production_resource"):
		# A single combined modifier, computed by the server, excludes global
		# economy speed and power shortage. Output numbers below already include it.
		if entry.has("production_bonus_percent"):
			sections.append(I18n.t("Bonusy wydobycia: %s") % _signed_percent(host, float(entry["production_bonus_percent"])))
		var resource_key: String = "mine_" + str(entry["production_resource"])
		if metrics.has(resource_key):
			var output: Dictionary = metrics[resource_key]
			var icon: String = ResourceInfo.token(str(entry["production_resource"])) + "\u00A0" if resource_icons else ""
			var rates: String = I18n.t("Wydobycie: %s") % (icon + _value(host, float(output["current"]), "per_hour"))
			if has_next and output.get("next") != null:
				rates += "\n" + I18n.t("Następny poziom: %s") % (icon + _value(host, float(output["next"]), "per_hour"))
			sections.append(rates)
		if metrics.has("energy_use"):
			var energy: Dictionary = metrics["energy_use"]
			var energy_text: String = host._stat_number(float(energy["current"]))
			if has_next and energy.get("next") != null:
				energy_text += " → " + host._stat_number(float(energy["next"]))
			sections.append(I18n.t("Zużycie energii: %s") % energy_text)
		return sections
	if kind == "build" and key in ["shipyard", "lab"]:
		var speed_key: String = "shipyard_speed_bonus" if key == "shipyard" else "lab_speed_bonus"
		if metrics.has(speed_key):
			var speed: Dictionary = metrics[speed_key]
			var current: String = _signed_percent(host, float(speed["current"])) if level > 0 else I18n.t("Niedostępne")
			var text: String = (I18n.t("Tempo produkcji: %s") if key == "shipyard" else I18n.t("Tempo badań: %s")) % current
			if has_next and speed.get("next") != null:
				text += "\n" + I18n.t("Następny poziom: %s") % _signed_percent(host, float(speed["next"]))
			sections.append(text)
		else:
			# Old servers have no speed mechanic. Do not invent a client-only bonus.
			sections.append(I18n.t("Tempo: brak danych z serwera."))
		return sections
	# Keep just the essential effect of the other basic building/research types.
	# Unique buildings already supply an authoritative current/next effect pair.
	var allowed: Array[String] = []
	if kind == "build" and key == "power_plant":
		allowed = ["energy_supply"]
	elif kind == "build" and metrics.has("storage_capacity"):
		allowed = ["storage_capacity"]
	elif kind == "research" and not bool(entry.get("unique", false)):
		allowed = ["fleet_speed_bonus", "fleet_attack_bonus"]
	for metric_key: String in allowed:
		if not metrics.has(metric_key):
			continue
		var metric: Dictionary = metrics[metric_key]
		var now: String = _value(host, float(metric["current"]), str(metric.get("unit", "number")))
		var following: String = _value(host, float(metric["next"]), str(metric.get("unit", "number"))) if has_next and metric.get("next") != null else ""
		sections.append(I18n.t(str(METRIC_LABELS[metric_key])) + "\n" + _pair(level, now, following))
	return sections


static func paragraphs(host, controls: Dictionary, detailed: bool = false, include_requirements: bool = true, resource_icons: bool = false) -> PackedStringArray:
	var entry: Dictionary = controls.get("entry", {})
	var kind: String = str(controls.get("kind", "build"))
	var level: int = int(entry.get("level", 0))
	var max_level: int = int(entry.get("max_level", 0))
	var units: bool = kind in ["ship", "defense"]
	var amount: int = int(controls["amount"].value) if controls.get("amount") != null else 1
	var sections: PackedStringArray = PackedStringArray()
	var cost: Dictionary = {}
	for resource: String in host.RESOURCE_KEYS:
		cost[resource] = float(entry.get("cost", {}).get(resource, 0)) * amount
	# Meta paragraph: level, then COST immediately, then time and unbuilt status.
	var meta: String = str(controls["level"].text)
	if units or level < max_level:
		meta += "\n" + I18n.t("Koszt: %s") % _exact_cost(host, cost, resource_icons)
		meta += "\n" + I18n.t("Czas: %s") % host._duration(host._catalog_seconds(entry, amount))
	else:
		meta += "\n" + I18n.t("Maksymalny poziom.")
	if not units and level == 0:
		meta += "\n" + (I18n.t("Jeszcze nie zbadano") if kind == "research" else I18n.t("Jeszcze nie zbudowano"))
	sections.append(meta)
	if kind == "build" and entry.has("building_fields"):
		var fields: Dictionary = entry["building_fields"]
		sections.append(I18n.t("Ulepszenie zajmie 1 slot · wolne: %d / %d") % [int(fields.get("free", 0)), int(fields.get("total", 0))])
	if entry.has("observation"):
		var observation: Dictionary = entry["observation"]
		sections.append(I18n.t("Obecnie") + "\n" + host.planetary_ui.observation_text(observation.get("current", {})))
		if level < max_level:
			sections.append(I18n.t("Następny poziom") + "\n" + host.planetary_ui.observation_text(observation.get("next", {})))
	# The plain-language purpose stays visible even with detailed mode off.
	sections.append_array(description_paragraphs(host, entry, kind, detailed))
	if detailed and entry.has("production_bonus_percent"):
		sections.append(I18n.t("Bonusy wydobycia: %s") % _signed_percent(host, float(entry["production_bonus_percent"])))
	var current_effect: String = host._server_text(entry.get("effect_current", ""))
	var next_effect: String = host._server_text(entry.get("effect_next", "")) if level < max_level else ""
	if resource_icons:
		current_effect = resource_effect(host, entry, false, current_effect)
		if not next_effect.is_empty():
			next_effect = resource_effect(host, entry, true, next_effect)
	if not current_effect.is_empty():
		sections.append(_pair(level, current_effect, next_effect))
	var detail: Dictionary = entry.get("details", {})
	if detail.is_empty():
		detail = _legacy_details(host, entry, kind)
	if detailed:
		for metric: Dictionary in detail.get("metrics", []):
			var key: String = str(metric.get("key", ""))
			if not METRIC_LABELS.has(key):
				continue
			var current: String = _value(host, float(metric.get("current", 0)), str(metric.get("unit", "number")))
			var following: String = _value(host, float(metric["next"]), str(metric.get("unit", "number"))) if metric.get("next") != null and level < max_level else ""
			var metric_label: String = I18n.t(str(METRIC_LABELS[key]))
			var resource: String = key.get_slice("_", 1)
			if resource_icons and resource in ResourceInfo.KEYS and (key.begins_with("mine_") or key.begins_with("colony_")):
				metric_label = I18n.t("Wydobycie budynku") if key.begins_with("mine_") else I18n.t("Produkcja kolonii")
				current = ResourceInfo.token(resource) + "\u00A0" + current
				if not following.is_empty():
					following = ResourceInfo.token(resource) + "\u00A0" + following
			sections.append(metric_label + "\n" + _pair(level, current, following))
		for example: Dictionary in detail.get("time_examples", []):
			var current_time: String = host._duration(float(example["current_seconds"])) if example.get("current_seconds") != null else I18n.t("Niedostępne")
			var next_time: String = ""
			if bool(example.get("has_next", false)) and level < max_level:
				next_time = host._duration(float(example["next_seconds"])) if example.get("next_seconds") != null else I18n.t("Niedostępne")
			sections.append(I18n.t("Czas projektu: %s") % host._server_text(example.get("name", "")) + "\n" + _pair(level, current_time, next_time))
		for note: String in detail.get("notes", []):
			if note == "next_local_only" and level >= max_level:
				continue
			if NOTES.has(note):
				sections.append(I18n.t(str(NOTES[note])))
		if detail.has("available_now"):
			var names: PackedStringArray = PackedStringArray()
			for name in detail["available_now"]:
				names.append(host._server_text(name))
			sections.append(I18n.t("Dostępne teraz: %s") % (", ".join(names) if not names.is_empty() else I18n.t("Brak")))
			if level < max_level:
				names.clear()
				for name in detail.get("unlocks_next", []):
					names.append(host._server_text(name))
				sections.append(I18n.t("Następny poziom odblokuje: %s") % ", ".join(names) if not names.is_empty() else I18n.t("Następny poziom nie odblokuje nowych projektów przy obecnych pozostałych wymaganiach."))
			var milestones: PackedStringArray = PackedStringArray()
			for milestone: Dictionary in detail.get("milestones", []):
				if int(milestone.get("level", 0)) > level:
					var line: String = I18n.t("Poziom %d — %s") % [int(milestone["level"]), host._server_text(milestone["name"])]
					if not bool(milestone.get("other_requirements_met", true)):
						line += I18n.t(" (wymaga też innych ulepszeń)")
					milestones.append(line)
			if not milestones.is_empty():
				sections.append(I18n.t("Progi odblokowania") + "\n" + "\n".join(milestones))
		elif kind == "build" and str(entry.get("key", "")) in ["shipyard", "lab"]:
			sections.append(I18n.t("Pełne porównanie projektów wymaga aktualizacji serwera."))
	else:
		sections.append_array(_brief_metrics(host, entry, kind, detail, resource_icons))
	if units:
		var stats: PackedStringArray = PackedStringArray()
		for key: String in ["attack_stat", "hull_stat", "capacity_stat"]:
			if controls[key].visible:
				stats.append(str(controls[key].text))
		stats.append_array(unit_traits(host, entry, resource_icons))
		if kind == "defense":
			stats.append(I18n.t("Obrona stacjonarna — pozostaje na planecie."))
		if not stats.is_empty():
			sections.append("\n".join(stats))
	if detailed or units:
		for key: String in ["batch_effect", "production_effect"]:
			if controls[key].visible and not str(controls[key].text).is_empty():
				sections.append(str(controls[key].text))
		if controls["refund"].visible:
			var refund: PackedStringArray = PackedStringArray()
			for resource: String in host.RESOURCE_KEYS:
				var item: Dictionary = controls["refund_costs"][resource]
				if item["row"].visible:
					refund.append((ResourceInfo.token(resource) if resource_icons else I18n.t(str(host.RESOURCE_NAMES[resource]))) + "\u00A0" + str(item["amount"].text))
			if not refund.is_empty():
				sections.append(I18n.t("Recykling · zwrot po ukończeniu") + "\n" + " · ".join(refund))
	# A requirement is rendered ONCE at the end, never repeated in the reason.
	var requirement_lines: PackedStringArray = PackedStringArray()
	var seen: Dictionary = {}
	for requirement: Dictionary in entry.get("requirements", []):
		var identity: String = str(requirement.get("group", "")) + ":" + str(requirement.get("key", ""))
		if seen.has(identity):
			continue
		seen[identity] = true
		requirement_lines.append(I18n.t("%s %s · poz. %d") % ["✓" if bool(requirement.get("met", false)) else "•", host._server_text(requirement.get("name", requirement.get("key", ""))), int(requirement.get("level", 0))])
	if include_requirements and not requirement_lines.is_empty():
		sections.append(I18n.t("Wymagania") + "\n" + "\n".join(requirement_lines))
	var reason: String = host._server_text(entry.get("reason", ""))
	if not reason.is_empty() and not reason.begins_with(I18n.t("Wymaga:")) and not (not units and level >= max_level):
		sections.append(reason)
	return sections
