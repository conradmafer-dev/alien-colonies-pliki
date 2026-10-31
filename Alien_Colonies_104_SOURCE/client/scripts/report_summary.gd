extends RefCounted
## Small factual report header. Legacy text is parsed only against complete,
## authored templates; names are matched exactly and never treated as markup.
const ResourceText = preload("res://client/scripts/report_resource_text.gd")
const Resources = preload("res://client/scripts/resource_info.gd")
const FleetModel = preload("res://client/scripts/fleet_navigation_model.gd")

static func _named_planet(world: Dictionary, name: String) -> String:
	if name.is_empty():
		return ""
	var matches: Dictionary = {}
	for system: Dictionary in world.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			if str(planet.get("name", "")) == name:
				matches[str(planet.get("id", ""))] = true
	for planet: Dictionary in world.get("own_planets", []):
		if str(planet.get("name", "")) == name:
			matches[str(planet.get("id", ""))] = true
	return str(matches.keys()[0]) if matches.size() == 1 else ""

static func _title_is(title: String, source: String, locale: String) -> bool:
	return title == ResourceText._localized(source, locale)

static func resources_text(host, values: Dictionary) -> String:
	var parts: PackedStringArray = PackedStringArray()
	for resource: String in Resources.KEYS:
		if values.has(resource) and FleetModel.finite_number(values[resource]) >= 0.0:
			parts.append(Resources.token(resource) + "\u00A0" + host._stat_number(float(values[resource])))
	return " · ".join(parts)

static func describe(host, report: Dictionary) -> Dictionary:
	var result: Dictionary = {"outcome": "", "resources": {}, "resource_caption": "", "planet_id": ""}
	var system_scout: Variant = report.get("system_scout", {})
	if system_scout is Dictionary and not system_scout.is_empty():
		result["outcome"] = I18n.t("Zwiad całego układu zakończony")
		result["system_scout"] = system_scout
		return result
	var scout: Variant = report.get("planet_scout", report.get("scout", {}))
	if scout is Dictionary and not scout.is_empty():
		result["outcome"] = I18n.t("Zwiad zakończony")
		result["resources"] = scout.get("resources", {})
		result["resource_caption"] = I18n.t("Zaobserwowane zapasy")
		var planet_id: String = str(scout.get("id", ""))
		result["planet_id"] = planet_id if not FleetModel.target(host.state, planet_id).is_empty() else _named_planet(host.state, str(scout.get("name", "")))
		return result
	var title: String = str(report.get("title", ""))
	var raw: String = host._report_display_text(report)
	for locale: String in [I18n.locale, "pl", "en", "de", "es", "fr"]:
		if _title_is(title, "Raport bitwy", locale) or _title_is(title, "Twoja kolonia została zaatakowana", locale):
			var battle: Dictionary = ResourceText._match(raw, ResourceText._localized(ResourceText.BATTLE, locale), [2, 5, 6, 7])
			if not battle.is_empty():
				var args: Dictionary = battle["args"]
				# Legacy battle text is always from the attacker's perspective,
				# including the copy delivered to the defender.
				result["outcome"] = I18n.t("Atakujący") + ": " + str(args[1])
				result["planet_id"] = _named_planet(host.state, str(args[0]))
				result["resource_caption"] = I18n.t("Zdobycz atakującego")
				for pair: Array in [["metal", 5], ["crystal", 6], ["fuel", 7]]:
					result["resources"][pair[0]] = float(str(args[pair[1]]).replace(",", "."))
				return result
		var templates: Dictionary = {
			"Dostarczono transport": "Zapasy dotarły na {0}. Statki wracają.",
			"Kolonizacja przerwana": "{0} nie jest już dostępna lub osiągnięto limit kolonii. Flota wraca.",
			"Nowa kolonia": "Założono kolonię {0}. Kolonizator rozebrano na bazę; pozostałe statki i zapasy zostały na miejscu."
		}
		for source: String in templates:
			if _title_is(title, source, locale):
				var found: Dictionary = ResourceText._match(raw, ResourceText._localized(templates[source], locale), [], source != "Nowa kolonia")
				if not found.is_empty():
					result["outcome"] = I18n.t(source)
					result["planet_id"] = _named_planet(host.state, str(found["args"][0]))
					return result
	return result

static func add_to(host, body: VBoxContainer, report: Dictionary) -> void:
	var summary: Dictionary = describe(host, report)
	if str(summary["outcome"]).is_empty():
		return
	var card: VBoxContainer = host._card(body)
	card.name = "MissionReportSummary"
	card.add_child(host._label(I18n.t("Wynik misji") + ": " + str(summary["outcome"]), 24))
	if summary.has("system_scout"):
		_add_system_scout(host, card, summary["system_scout"])
		return
	if summary["resources"] is Dictionary and not summary["resources"].is_empty():
		card.add_child(host._label(str(summary["resource_caption"]), 19))
		card.add_child(Resources.label(host, resources_text(host, summary["resources"]), 22))
	var planet_id: String = str(summary["planet_id"])
	if not planet_id.is_empty():
		var button: Button = host._button(I18n.t("Przejdź do planety"), host.compact_ui._open_planet.bind(planet_id))
		button.name = "ReportPlanetLink"
		card.add_child(button)


static func _add_system_scout(host, card: VBoxContainer, snapshot: Dictionary) -> void:
	card.name = "SystemScoutReportSummary"
	card.add_child(host._label(str(snapshot.get("system_name", snapshot.get("system_id", ""))), 26))
	var timestamp: float = FleetModel.finite_number(snapshot.get("scouted_at"), 0.0)
	if timestamp > 0.0:
		var date: Label = host._label(I18n.t("Stan z chwili zwiadu: %s") % host._date(timestamp), 21, "edc77a")
		date.name = "SystemScoutSnapshotTime"
		card.add_child(date)
	card.add_child(host._label(I18n.t("Wolne planety i właściciele w całym układzie. Ten raport nie zawiera szczegółów zasobów, floty ani obrony planet."), 21))
	var planets: Array = snapshot.get("planets", []).duplicate()
	planets.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.get("slot", 0)) < int(b.get("slot", 0)))
	for planet: Dictionary in planets:
		var owner: String = str(planet.get("owner_name", ""))
		var color: String = "d9e7dc"
		match str(planet.get("owner_type", "")):
			"empty":
				owner = I18n.t("○ Wolna planeta")
			"alien":
				owner = I18n.t("Rój") + (" · " + owner if not owner.is_empty() else "")
				color = "ff9287"
			"player":
				if str(planet.get("owner_id", "")) == str(host.state.get("player", {}).get("id", "")):
					owner = I18n.t("● Twoja kolonia")
					color = "91c89b"
				elif owner.is_empty():
					owner = I18n.t("Inny gracz")
			_:
				owner = I18n.t("Właściciel nieznany")
		var row: Label = host._label(I18n.t("POZYCJA %s") % str(int(planet.get("slot", 0))) + " · " + str(planet.get("name", planet.get("id", ""))) + "\n" + I18n.t("Właściciel: %s") % owner, 22, color)
		row.name = "SystemScoutPlanet_" + str(planet.get("id", ""))
		card.add_child(row)
	var system_id: String = str(snapshot.get("system_id", ""))
	if not system_id.is_empty():
		var button: Button = host._button(I18n.t("Przejdź do układu"), _open_system.bind(host, system_id))
		button.name = "ReportSystemLink"
		card.add_child(button)


static func _open_system(host, system_id: String) -> void:
	host.compact_ui.close_details()
	host._open_tab(1)
	host._system_from_overview(system_id)

const ICON_PATHS: Dictionary = {
	"ranking": '<path d="m12 2 7 6-2 11-5 3-5-3L5 8l7-6ZM5 8h14M12 2l-3 6 3 14 3-14-3-6Z"/>',
	"scout": "<circle cx=\"11\" cy=\"11\" r=\"7\"/><path d=\"m16 16 5 5M11 7v4l3-3\"/>",
	"battle": "<path d=\"m3 3 8 5 10 13-4-1L6 9 3 3Zm18 0-8 5M18 9l-7 8M3 21l4-1M4 16l4 4M16 20l4-4\"/>",
	"warning": "<path d=\"m12 3 10 18H2L12 3ZM12 9v5M12 18h.01\"/>",
	"transport": "<path d=\"m3 7 8-4 8 4-8 4-8-4ZM3 7v10l8 4V11M11 21l4-2M18 11v9m-3-3 3 3 3-3\"/>",
	"return": "<path d=\"M9 5H4v5M4 5l6 6M6 16a8 8 0 1 0 2-12\"/><path d=\"m9 16 3-3 3 3v5H9v-5Z\"/>",
	"colonization": "<circle cx=\"10\" cy=\"14\" r=\"7\"/><path d=\"M14 14V2l7 3-7 3M4 12l5 2 2 6\"/>",
	"research": "<path d=\"M9 3h6M10 3v6L4 19a1.3 1.3 0 0 0 1.1 2h13.8a1.3 1.3 0 0 0 1.1-2L14 9V3M8 14h8\"/>",
	"construction": "<path d=\"M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6M9 10h.01M15 10h.01\"/>",
	"defense": "<path d=\"m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3ZM8 12l3 3 5-6\"/>",
	"shipyard": "<path d=\"m12 3 7 14-7-3-7 3 7-14ZM12 14v7M8 20l-2 1M16 20l2 1\"/>",
	"skill": "<path d=\"m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z\"/>",
	"protection": "<path d=\"m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4ZM9 11V8a3 3 0 0 1 6 0v3M8 11h8v6H8v-6Z\"/>",
	"empire": "<path d=\"M4 20h16M4 17 2 5l6 5 4-7 4 7 6-5-2 12H4Z\"/>",
	"expedition": '<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6 6-2Z"/>',
	"recycling": "<path d=\"m8 5 4-3 4 7M12 2l-4 7M20 11l2 5-8 1M22 16l-4-7M12 21H6l1-8M6 21l-4-7\"/>"
}
static var _kind_icons: Dictionary = {}

static func icon_kind(report: Dictionary) -> String:
	var value: String = str(report.get("kind", ""))
	if ICON_PATHS.has(value):
		return value
	if bool(report.get("battle_replay_available", false)):
		return "battle"
	if report.has("scout") or report.has("planet_scout") or report.has("system_scout"):
		return "scout"
	return "empire"

static func icon_texture(report: Dictionary) -> Texture2D:
	var kind_value: String = icon_kind(report)
	if _kind_icons.has(kind_value):
		return _kind_icons[kind_value]
	var colors: Dictionary = {"battle": "#ff9295", "warning": "#ffc879", "return": "#b6bdc8", "colonization": "#9be4ad", "research": "#bcabff", "skill": "#e4c17a"}
	var color: String = str(colors.get(kind_value, "#99c9ec"))
	var svg: String = '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">%s</svg>' % [color, ICON_PATHS[kind_value]]
	var pixels: Image = Image.new()
	if pixels.load_svg_from_string(svg) != OK:
		return null
	var texture: ImageTexture = ImageTexture.create_from_image(pixels)
	_kind_icons[kind_value] = texture
	return texture
