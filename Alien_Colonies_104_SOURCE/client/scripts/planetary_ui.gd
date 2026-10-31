extends RefCounted
const GalaxyGuidance = preload("res://client/scripts/galaxy_guidance.gd")
const ResourceInfo = preload("res://client/scripts/resource_info.gd")
## Planet environments, finite building fields, and honest observation labels.

var host
var galaxy_guidance
var summary: Label
var panorama_hit: PanelContainer
var detail_marker: Control
var detail_planet_id: String = ""
var detail_signature: String = ""


func setup(client) -> void:
	host = client
	var caption: VBoxContainer = host.planet_title.get_parent()
	caption.get_child(0).hide()
	host.planet_title.add_theme_font_size_override("font_size", 32)
	host.planet_subtitle.add_theme_font_size_override("font_size", 19)
	caption.get_parent().add_theme_constant_override("margin_right", 126)
	summary = host._label("", 21)
	summary.name = "PlanetEnvironmentSummary"
	caption.add_child(summary)
	# A drag-aware passive hit surface keeps scrolling distinct from opening details.
	panorama_hit = preload("res://client/scripts/catalog_card.gd").new()
	panorama_hit.name = "PlanetPanoramaDetails"
	panorama_hit.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	panorama_hit.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	panorama_hit.details_requested.connect(_open_home)
	host.colony_panorama.add_child(panorama_hit)
	host.colony_panorama.move_child(host.compact_ui.race_button, host.colony_panorama.get_child_count() - 1)
	panorama_hit.excluded_controls = [host.compact_ui.race_button]
	galaxy_guidance = GalaxyGuidance.new()
	galaxy_guidance.setup(host)


func find_planet(id: String) -> Dictionary:
	for system: Dictionary in host.state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			if str(planet.get("id", "")) == id:
				return planet
	return {}


func unknown_target(id: String) -> bool:
	if id.is_empty():
		return false
	for system: Dictionary in host.state.get("galaxy", []):
		if str(system.get("scout_target_id", "")) == id:
			return true
	return false


func refresh() -> void:
	galaxy_guidance.refresh()
	var environment: Dictionary = host.state.get("environment", {})
	summary.visible = not environment.is_empty()
	var fields: Dictionary = host.state.get("fields", {})
	summary.text = "%s · %s\n" % [host._server_text(environment.get("type_name", "")), host._server_text(environment.get("size_name", ""))]
	if str(environment.get("trait", {}).get("status", "")) == "rare":
		summary.text = "✦ " + summary.text
	summary.text += I18n.t("Sloty: %d / %d · wolne: %d") % [int(fields.get("used", 0)), int(fields.get("total", 0)), int(fields.get("free", 0))]
	if int(fields.get("reserved", 0)) > 0:
		summary.text += I18n.t(" · w budowie: %d") % int(fields["reserved"])
	if is_instance_valid(detail_marker) and detail_marker.is_inside_tree() and host.compact_ui.details_open():
		var planet: Dictionary = find_planet(detail_planet_id)
		if JSON.stringify(planet) != detail_signature:
			var scroll: int = host.compact_ui.modal_scroll.scroll_vertical
			host.compact_ui._open_planet(detail_planet_id)
			host.compact_ui.modal_scroll.set_deferred("scroll_vertical", scroll)


func _open_home() -> void:
	host.compact_ui._open_planet(host.selected_planet)


func caption(planet: Dictionary) -> String:
	var result: String = I18n.t("○ Wolna planeta") if str(planet.get("owner_type", "")) == "empty" else str(planet.get("owner_name", ""))
	if GalaxyGuidance.Model.is_owned(host.state, planet):
		result = I18n.t("● Twoja kolonia")
	var environment: Dictionary = planet.get("environment", {})
	if not environment.is_empty():
		result += " · " + host._server_text(environment.get("type_name", ""))
		var feature: Dictionary = environment.get("trait", {})
		if str(feature.get("status", "")) == "rare":
			result += "\n✦ " + host._server_text(feature.get("name", ""))
		elif environment.has("fields"):
			result += "\n" + host._server_text(environment.get("size_name", "")) + " · " + I18n.t("%d slotów") % int(environment["fields"])
	if str(planet.get("visibility", "")) == "remembered":
		result += " · " + I18n.t("Dane archiwalne")
	if str(planet.get("visibility", "")) == "scouted":
		result += " · " + I18n.t("Dane ze zwiadu")
	return result


func visibility_text(record: Dictionary) -> String:
	match str(record.get("visibility", "")):
		"observed": return I18n.t("Obserwatorium · dane na żywo")
		"remembered": return I18n.t("Dane archiwalne sprzed %s · właściciel może się zmienić. Odkryta cecha pozostaje znana.") % host._duration(maxf(0.0, host._server_now() - float(record.get("observed_at", 0))))
		"scouted": return I18n.t("Zapis zwiadu sprzed %s · bez aktualizacji na żywo") % host._duration(maxf(0.0, host._server_now() - float(record.get("scouted_at", 0))))
		"colony": return I18n.t("Znane są tylko własne kolonie. Pozostałe planety wymagają odkrycia.")
		"unknown": return I18n.t("Nieznany układ. Wyślij zwiad lub rozbuduj obserwatorium.")
	return ""


func add_trait(parent: VBoxContainer, feature: Dictionary) -> void:
	var status: String = str(feature.get("status", "unknown"))
	if status != "rare":
		var text: String = I18n.t("Nie wykryto rzadkiej cechy.") if status == "none" else I18n.t("Rzadka cecha: niezbadana. Wyślij zwiad na tę planetę lub obejmij ją obserwatorium.")
		var label: Label = host._label(text, 22, "a4b4c8")
		label.name = "PlanetTraitStatus"
		parent.add_child(label)
		return
	var panel: PanelContainer = PanelContainer.new()
	panel.name = "RarePlanetTrait"
	panel.add_theme_stylebox_override("panel", host._style("24251e", "8a7342", 14, 16))
	parent.add_child(panel)
	var body: VBoxContainer = VBoxContainer.new()
	body.add_theme_constant_override("separation", 8)
	panel.add_child(body)
	body.add_child(host._label("✦ " + I18n.t("Rzadka cecha planety"), 22, "edc77a"))
	body.add_child(host._label(host._server_text(feature.get("name", "")), 25, "f5dda6"))
	body.add_child(host._label(host._server_text(feature.get("description", "")), 22))


func add_environment(parent: VBoxContainer, environment: Dictionary, fields: Dictionary = {}) -> void:
	if environment.is_empty():
		return
	add_trait(parent, environment.get("trait", {}))
	parent.add_child(host._label(host._server_text(environment.get("type_name", "")), 26, "edc77a"))
	if environment.has("fields"):
		parent.add_child(host._label("%s · %s" % [host._server_text(environment.get("size_name", "")), I18n.t("%d slotów") % int(environment["fields"])], 23))
		parent.add_child(host._label(I18n.t("Średnica: %s km · temperatura: %d°C") % [host._number(float(environment.get("diameter_km", 0))), int(environment.get("temperature_c", 0))], 22))
		parent.add_child(host._label(I18n.t("Odległość od gwiazdy: %s AU") % host._stat_number(float(environment.get("orbit_au", 0))), 22))
		var multipliers: Dictionary = environment.get("multipliers", {})
		for resource: String in host.RESOURCE_KEYS:
			var percent: int = roundi(100.0 * float(multipliers.get(resource, 1)))
			parent.add_child(ResourceInfo.label(host, I18n.t("Wydobycie: %s") % (ResourceInfo.token(resource) + "\u00A0%d%%" % percent), 23))
	else:
		parent.add_child(host._label(I18n.t("Rozmiar i warunki wydobycia poznasz przez zwiad lub dokładną obserwację."), 22))
	if not fields.is_empty():
		parent.add_child(host._label(I18n.t("Sloty: %d / %d · wolne: %d") % [int(fields.get("used", 0)), int(fields.get("total", 0)), int(fields.get("free", 0))], 24))
		if int(fields.get("reserved", 0)) > 0:
			parent.add_child(host._label(I18n.t("Zarezerwowane przez budowę: %d") % int(fields["reserved"]), 22))


func add_planet_details(parent: VBoxContainer, planet: Dictionary) -> void:
	detail_planet_id = str(planet.get("id", ""))
	detail_signature = JSON.stringify(planet)
	detail_marker = Control.new()
	parent.add_child(detail_marker)
	add_environment(parent, planet.get("environment", {}), planet.get("fields", {}))
	if planet.has("observed_buildings"):
		parent.add_child(host._label(I18n.t("Budynki · podgląd na żywo"), 25))
		add_buildings(parent, planet["observed_buildings"])
	if planet.has("planet_scout") and str(planet.get("owner_type", "")) != "alien":
		parent.add_child(host._button(I18n.t("Otwórz ostatni raport zwiadu"), open_scout.bind(planet["planet_scout"])))


func add_buildings(parent: VBoxContainer, buildings: Array) -> void:
	if buildings.is_empty():
		parent.add_child(host._label(I18n.t("Brak wybudowanych budynków."), 22))
	for building: Dictionary in buildings:
		var caption: String = I18n.t("%s · poziom %d") % [host._server_text(building.get("name", "")), int(building.get("level", 0))]
		if bool(building.get("inactive", false)):
			caption += " " + I18n.t("(nieaktywny)")
		parent.add_child(host._label(caption, 22))


func open_scout(record: Dictionary) -> void:
	host.compact_ui._begin_details(I18n.t("Raport zwiadu"))
	add_scout(host.compact_ui.modal_body, record)


func add_scout(parent: VBoxContainer, record: Dictionary) -> void:
	add_environment(parent, record.get("environment", {}))
	parent.add_child(host._label(I18n.t("Zapis zwiadu sprzed %s · bez aktualizacji na żywo") % host._duration(maxf(0.0, host._server_now() - float(record.get("scouted_at", 0)))), 22, "edc77a"))
	parent.add_child(ResourceInfo.label(host, ResourceInfo.cost(host, record.get("resources", {})), 22))
	parent.add_child(host._label(I18n.t("Budynki według zwiadu"), 25))
	add_buildings(parent, record.get("observed_buildings", []))
	for section: String in ["ships", "defenses"]:
		parent.add_child(host._label(I18n.t("Flota") if section == "ships" else I18n.t("Obrona planetarna"), 25))
		var any_units: bool = false
		for unit: Dictionary in record.get(section + "_display", []):
			parent.add_child(host._label("%s × %d" % [host._server_text(unit.get("name", "")), int(unit.get("count", 0))], 22))
			any_units = true
		if not any_units:
			parent.add_child(host._label(I18n.t("Brak"), 22))


func observation_text(info: Dictionary) -> String:
	var radius: int = int(info.get("range", -1))
	var detail: int = int(info.get("building_range", -1))
	var result: String = I18n.t("Brak stałej obserwacji") if radius < 0 else I18n.t("Właściciele, typy i cechy: do %d układów w każdą stronę") % radius
	result += "\n" + (I18n.t("Podgląd budynków od poziomu 6") if detail < 0 else I18n.t("Budynki na żywo: do %d układów w każdą stronę") % detail)
	return result


func add_observation_help(parent: VBoxContainer) -> void:
	var info: Dictionary = host.state.get("observation", {})
	if info.is_empty():
		return
	parent.add_child(host._label(I18n.t("Obserwatorium · poziom %d") % int(info.get("level", 0)), 26))
	parent.add_child(host._label(observation_text(info), 23))
	parent.add_child(host._label(I18n.t("Zasięg rośnie co 2 poziomy. Obserwatoria łączą zasięgi wyłącznie we własnej galaktyce. Zwiad pozostaje jednorazowym zapisem."), 22))
	for source: Dictionary in info.get("sources", []):
		if str(source.get("galaxy_id", "")) == host.selected_galaxy:
			parent.add_child(host._label("%s · %s" % [str(source.get("name", "")), I18n.t("Obserwatorium · poziom %d") % int(source.get("level", 0))], 22))


func open_first_galaxy_visit() -> bool:
	return galaxy_guidance.open_first_visit()


func add_target_summary(parent: VBoxContainer, planet: Dictionary) -> void:
	galaxy_guidance.add_summary(parent, planet)


func add_target_actions(parent: VBoxContainer, planet: Dictionary) -> void:
	galaxy_guidance.add_actions(parent, planet)
