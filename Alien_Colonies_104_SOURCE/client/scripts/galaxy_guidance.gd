extends RefCounted
## Small additions to the existing galaxy/system view, without changing topology.
const Model = preload("res://client/scripts/galaxy_guidance_model.gd")
const SETTINGS_PATH: String = "user://galaxy_guidance.cfg"

var host
var settings_path: String = SETTINGS_PATH
var _visited: Dictionary = {}
var neighborhood_button: Button


func setup(client) -> void:
	host = client
	var settings: ConfigFile = ConfigFile.new()
	if settings.load(settings_path) == OK:
		_visited = settings.get_value("navigation", "visited", {})
	neighborhood_button = host._button(I18n.t("Moja okolica"), open_home)
	neighborhood_button.name = "GalaxyHomeNeighborhood"
	neighborhood_button.custom_minimum_size.y = 56
	host.compact_ui.system_view.add_child(neighborhood_button)
	host.compact_ui.system_view.move_child(neighborhood_button, 0)
	neighborhood_button.hide()


func _account_key() -> String:
	var player_id: String = str(host.state.get("player", {}).get("id", ""))
	return (str(host.server_url).trim_suffix("/") + "|" + player_id).sha256_text() if not player_id.is_empty() else ""


func open_first_visit() -> bool:
	var account: String = _account_key()
	if account.is_empty() or bool(_visited.get(account, false)):
		return false
	if not open_home():
		return false
	_visited[account] = true
	var settings: ConfigFile = ConfigFile.new()
	settings.set_value("navigation", "visited", _visited)
	settings.save(settings_path)
	return true


func open_home() -> bool:
	var home: Dictionary = Model.home_location(host.state, str(host.selected_planet))
	if home.is_empty():
		return false
	host.selected_galaxy = str(home["system"].get("galaxy_id", "g1"))
	host._system_from_overview(str(home["system"].get("id", "")))
	host.galaxy_toggle.text = I18n.t("Cała galaktyka")
	return true


func refresh() -> void:
	if is_instance_valid(neighborhood_button):
		neighborhood_button.text = I18n.t("Moja okolica")
		neighborhood_button.disabled = Model.home_location(host.state, str(host.selected_planet)).is_empty()


func add_summary(parent: VBoxContainer, target: Dictionary) -> void:
	var owned: bool = Model.is_owned(host.state, target)
	var owner: String = str(target.get("owner_name", ""))
	if owned:
		owner = I18n.t("● Twoja kolonia")
	elif str(target.get("visibility", "")) == "unknown":
		owner = I18n.t("Właściciel nieznany")
	elif str(target.get("owner_type", "")) == "empty":
		owner = I18n.t("○ Wolna planeta")
	elif owner.is_empty():
		owner = I18n.t("Właściciel nieznany")
	var owner_label: Label = host._label(I18n.t("Właściciel: %s") % owner, 25, "91c89b" if owned else "d9e7dc")
	owner_label.name = "TargetOwnerSummary"
	parent.add_child(owner_label)
	if bool(target.get("is_home_planet", false)):
		parent.add_child(host._label(I18n.t("Planeta matka — nie można jej przejąć."), 22, "edc77a"))
	var distance: Dictionary = Model.distance_info(host.state, str(host.selected_planet), target)
	var distance_text: String = I18n.t("Odległość: brak danych")
	match str(distance["kind"]):
		"origin": distance_text = I18n.t("Baza twojej floty")
		"same_system": distance_text = I18n.t("Ten sam układ · pozycja %d → %d") % [int(distance["origin_slot"]), int(distance["target_slot"])]
		"sector": distance_text = I18n.t("Odległość między układami: %s jednostek mapy") % host._stat_number(float(distance["value"]))
		"intergalactic": distance_text = I18n.t("Odległość: %s mln lat świetlnych") % host._stat_number(float(distance["value"]))
	var distance_label: Label = host._label(distance_text, 22)
	distance_label.name = "TargetDistanceSummary"
	parent.add_child(distance_label)
	var intel: Dictionary = Model.intel_info(host.state, target, host._server_now())
	var intel_text: String = I18n.t("Ostatni zwiad: brak danych. Siła obrony jest nieznana.")
	if str(intel["kind"]) == "own":
		intel_text = I18n.t("Dane własnej kolonii są aktualizowane na żywo.")
	elif str(intel["kind"]) == "scout":
		intel_text = I18n.t("Ostatni zwiad: %s temu. Siła obrony mogła się zmienić.") % host._duration(float(intel["age"]))
	var intel_label: Label = host._label(intel_text, 22, "a4b4c8" if owned else "edc77a")
	intel_label.name = "TargetIntelSummary"
	parent.add_child(intel_label)
	var visibility: String = host.planetary_ui.visibility_text(target)
	if not owned and not visibility.is_empty():
		parent.add_child(host._label(visibility, 21, "a4b4c8"))


func add_actions(parent: VBoxContainer, target: Dictionary) -> void:
	var actions: Array[Dictionary] = Model.target_actions(host.state, target, str(host.selected_planet), host._server_now())
	if actions.is_empty():
		return
	var labels: Dictionary = {"scout": I18n.t("Zwiad"), "colonize": I18n.t("Kolonizuj"), "capture": I18n.t("Przejęcie kolonii"), "transport": I18n.t("Transport"), "attack": I18n.t("Najazd") if str(target.get("owner_type", "")) == "alien" else I18n.t("Atak")}
	for action: Dictionary in actions:
		var key: String = str(action["key"])
		var button: Button = host._button(str(labels[key]), host._prepare_planet_mission.bind(str(target["id"]), int(action["mission"])), key != "attack")
		button.name = "TargetAction_" + key
		button.disabled = not bool(action["enabled"])
		parent.add_child(button)
		if key == "attack":
			var protection: Label = host._label(I18n.t("Ochrona startowa · atak niedostępny"), 22, "ffc56f")
			protection.visible = button.disabled
			parent.add_child(protection)
			# The existing protection ticker enables this exact control when it expires.
			host.planet_actions.append({"attack": button, "protection": protection, "until": float(target.get("protected_until", 0)) if str(target.get("owner_type", "")) == "player" else 0.0})
	parent.add_child(host._label(I18n.t("Wybierz działanie, aby przygotować misję. Czas lotu i koszt paliwa zobaczysz przed wysłaniem."), 21, "a4b4c8"))


func add_system_action(parent: VBoxContainer, system: Dictionary) -> void:
	var target: String = Model.system_scout_target(system, str(host.selected_planet))
	if target.is_empty():
		return
	var button: Button = host._button(I18n.t("Zbadaj cały układ"), host._prepare_system_scout.bind(str(system.get("id", ""))), true)
	button.name = "SurveyWholeSystem"
	button.custom_minimum_size.y = 60
	parent.add_child(button)
	var explanation: Label = host._label(I18n.t("Odśwież wolne planety i właścicieli w całym układzie. Szczegóły zasobów i obrony wymagają osobnego zwiadu planety."), 21, "a4b4c8")
	explanation.name = "SystemSurveyExplanation"
	parent.add_child(explanation)
