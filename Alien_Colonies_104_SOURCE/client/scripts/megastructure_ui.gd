extends RefCounted
## Megaprojects and a temporary, destination-specific transport window.

var host
var fleet_box: VBoxContainer
var fleet_status: Label
var travel_mode: CheckButton
var open_button: Button
var close_button: Button
var building_cards: Dictionary = {}
var building_parent: BoxContainer
var wormhole_target: String = ""


func setup(client) -> void:
	host = client


func make_fleet_controls(parent: VBoxContainer) -> void:
	fleet_box = VBoxContainer.new()
	fleet_box.name = "WormholeControls"
	fleet_box.visible = false
	parent.add_child(fleet_box)
	fleet_status = host._label("", 21, "edc77a")
	fleet_box.add_child(fleet_status)
	travel_mode = CheckButton.new()
	travel_mode.name = "UseWormhole"
	travel_mode.text = I18n.t("Podróż przez tunel")
	travel_mode.custom_minimum_size.y = 70
	travel_mode.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	travel_mode.toggled.connect(func(_pressed: bool) -> void: host._invalidate_quote(); host._update_mission_hint())
	fleet_box.add_child(travel_mode)
	open_button = host._button(I18n.t("Otwórz tunel do celu · 5 min"), _open_tunnel)
	fleet_box.add_child(open_button)
	close_button = host._button(I18n.t("Zamknij tunel"), _act.bind({"type": "tunnel_close"}))
	fleet_box.add_child(close_button)


func using_tunnel() -> bool:
	return is_instance_valid(travel_mode) and travel_mode.button_pressed and not travel_mode.disabled and fleet_box.visible


func refresh() -> void:
	if is_instance_valid(building_parent):
		refresh_building_cards(building_parent)
	tick()


func tick() -> void:
	if host.state.is_empty():
		return
	_tick_building_cards()
	if not is_instance_valid(fleet_box):
		return
	var info: Dictionary = host.state.get("megastructures", {})
	var now: float = host._server_now()
	var window: Dictionary = info.get("window", {}) if info.get("window") is Dictionary else {}
	var active: bool = not window.is_empty() and now < float(window.get("closes_at", 0))
	var ready: bool = active and now >= float(window.get("ready_at", 0))
	var matches: bool = active and str(window.get("target_id", "")) == host.selected_target
	var origin: bool = str(info.get("origin_id", "")) == host.selected_planet
	fleet_box.visible = int(info.get("gate_level", 0)) > 0
	var was_usable: bool = travel_mode.button_pressed and not travel_mode.disabled
	travel_mode.disabled = not (origin and ready and matches)
	if was_usable and travel_mode.disabled:
		# Never silently turn a quoted tunnel transfer into a costly normal flight.
		host._invalidate_quote()
	if not active and travel_mode.button_pressed:
		travel_mode.set_pressed_no_signal(false)
	var status: String = I18n.t("Tunel zamknięty")
	if active:
		status = I18n.t("Stabilizacja: %s") % host._duration(float(window.get("ready_at", 0)) - now) if not ready else I18n.t("Okno transportowe: %s") % host._duration(float(window.get("closes_at", 0)) - now)
		status += "\n" + str(window.get("target_name", ""))
	if not origin:
		status = I18n.t("Centrum projektu: %s") % str(info.get("origin_name", ""))
	var energy: float = _estimated_energy(info, now)
	status += "\n" + I18n.t("Energia: %s / %s") % [host._number(energy), host._number(float(info.get("capacity", 0)))]
	fleet_status.text = status
	open_button.visible = not active
	open_button.disabled = not origin or host.selected_target.is_empty() or host.selected_target == host.selected_planet or energy < float(info.get("opening_required", 0)) or host.request_pending or host.update_required
	close_button.visible = active
	close_button.disabled = not origin or host.request_pending or host.update_required


func _estimated_energy(info: Dictionary, now: float) -> float:
	var start: float = float(host.state.get("server_time", now))
	var elapsed: float = maxf(0.0, now - start)
	var energy: float = float(info.get("energy", 0))
	var charge: float = float(info.get("charge_per_second", 0))
	var window: Dictionary = info.get("window", {}) if info.get("window") is Dictionary else {}
	var active_seconds: float = maxf(0.0, minf(now, float(window.get("closes_at", start))) - start) if not window.is_empty() else 0.0
	energy += charge * elapsed - float(window.get("upkeep_per_second", 0)) * active_seconds
	return clampf(energy, 0.0, float(info.get("capacity", 0)))


func refresh_building_cards(parent: BoxContainer) -> void:
	building_parent = parent
	var info: Dictionary = host.state.get("megastructures", {})
	var present: Dictionary = {}
	for project: Dictionary in info.get("projects", []):
		var key: String = str(project.get("key", ""))
		if not key in ["dyson", "wormhole"]:
			continue
		present[key] = true
		if not building_cards.has(key) or not is_instance_valid(building_cards[key]["panel"]):
			_make_building_card(parent, key)
		var controls: Dictionary = building_cards[key]
		parent.move_child(controls["panel"], parent.get_child_count() - 1)
		controls["project"] = project
		_refresh_building_card(key, controls, project, info)
	for key: String in building_cards.keys():
		if not present.has(key):
			var obsolete: Control = building_cards[key]["panel"]
			if is_instance_valid(obsolete):
				obsolete.get_parent().remove_child(obsolete)
				obsolete.queue_free()
			building_cards.erase(key)
	_tick_building_cards()


func _make_building_card(parent: BoxContainer, key: String) -> void:
	var card: VBoxContainer = host._card(parent)
	var panel: PanelContainer = card.get_parent()
	panel.name = "MegastructureCard_" + key
	var layout_script: GDScript = load("res://client/scripts/catalog_card_layout.gd")
	var layout: Dictionary = layout_script.create(host, panel, card)
	var content: VBoxContainer = layout["content"]
	var footer: VBoxContainer = layout["footer"]
	var art: TextureRect = TextureRect.new()
	art.name = "MegastructureIllustration"
	art.texture = host.ArtLibrary.texture("megastructure_" + key)
	art.custom_minimum_size.y = 210
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(art)
	layout_script.fit_art(panel, art)
	content.add_child(host._label(I18n.t("Sfera Dysona") if key == "dyson" else I18n.t("Tunel czasoprzestrzenny"), 28))
	var level: Label = host._label("", 22, "91c89b")
	content.add_child(level)
	var description: String = "Zbiera energię gwiazdy. Rozbudowa zasila kolonię, umożliwia budowę tytanów i ładuje tunel czasoprzestrzenny." if key == "dyson" else "Łączy centrum projektu z wybraną planetą. Po stabilizacji otwiera krótkie okno szybkiego transportu flot. Korzysta z energii Sfery Dysona."
	content.add_child(host._label(I18n.t(description), 22, "c9d9cb"))
	var location: Label = host._label("", 21, "a0b3a4")
	content.add_child(location)
	var energy: Label = host._label("", 22, "edc77a")
	content.add_child(energy)
	var requirements: Label = host._label("", 21, "edc77a")
	requirements.name = "MegastructureRequirements"
	content.add_child(requirements)
	var target_picker: OptionButton = OptionButton.new()
	target_picker.name = "WormholeDestination"
	target_picker.custom_minimum_size.y = 62
	target_picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	target_picker.fit_to_longest_item = false
	target_picker.clip_text = true
	target_picker.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	target_picker.item_selected.connect(_select_wormhole_target)
	content.add_child(target_picker)
	var cost: VBoxContainer = VBoxContainer.new()
	cost.name = "MegastructureCosts"
	footer.add_child(cost)
	var costs: Dictionary = host._cost_icons(cost)
	var status: Label = host._label("", 21, "a0b3a4")
	footer.add_child(status)
	var action: Button = host._button("", _building_action.bind(key), true)
	action.name = "MegastructureAction_" + key
	footer.add_child(action)
	var cancel: Button = host._button(I18n.t("Anuluj budowę · zwrot surowców"), _cancel_building.bind(key))
	cancel.custom_minimum_size.y = 54
	footer.add_child(cancel)
	var go_origin: Button = host._button(I18n.t("Przejdź do centrum projektu"), _go_origin)
	go_origin.custom_minimum_size.y = 54
	footer.add_child(go_origin)
	building_cards[key] = {"panel": panel, "level": level, "location": location, "energy": energy, "requirements": requirements, "target": target_picker, "cost": cost, "costs": costs, "status": status, "action": action, "cancel": cancel, "go_origin": go_origin, "project": {}}


func _refresh_building_card(key: String, controls: Dictionary, project: Dictionary, info: Dictionary) -> void:
	var level: int = int(project.get("level", 0))
	var complete: bool = level >= int(project.get("max_level", 1))
	controls["level"].text = I18n.t("Etap %d / %d") % [level, int(project.get("max_level", 1))] if key == "dyson" else I18n.t("Projekt ukończony.") if complete else I18n.t("Nie zbudowano")
	var origin_id: String = str(info.get("origin_id", ""))
	controls["location"].text = I18n.t("Centrum projektu: %s") % str(info.get("origin_name", "")) if not origin_id.is_empty() else I18n.t("Centrum projektu: %s") % str(host.state.get("planet_name", ""))
	controls["go_origin"].visible = not origin_id.is_empty() and not bool(info.get("is_origin", false)) and not bool(info.get("suspended", false))
	var requirements: Array[String] = []
	for requirement: Dictionary in project.get("requirements", []):
		requirements.append(("✓ " if bool(requirement.get("met", false)) else "○ ") + host._server_text(requirement.get("name", "")) + " %d/%d" % [int(requirement.get("current", 0)), int(requirement.get("level", 0))])
	controls["requirements"].text = I18n.t("Wymagania") + ": " + " · ".join(requirements)
	controls["requirements"].visible = not complete and not requirements.is_empty()
	controls["cost"].visible = not complete
	var picker: OptionButton = controls["target"]
	picker.visible = key == "wormhole" and complete
	if picker.visible:
		_refresh_wormhole_targets(picker)


func _refresh_wormhole_targets(picker: OptionButton) -> void:
	var signature: String = JSON.stringify([host.selected_planet, host.state.get("galaxy", []), I18n.locale])
	if str(picker.get_meta("targets_signature", "")) == signature:
		return
	picker.set_meta("targets_signature", signature)
	picker.clear()
	picker.add_item(I18n.t("Wybierz planetę docelową"))
	picker.set_item_metadata(0, "")
	var selected: int = 0
	for system: Dictionary in host.state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			var id: String = str(planet.get("id", ""))
			if id.is_empty() or id == host.selected_planet:
				continue
			picker.add_item(str(system.get("name", "")) + " · " + str(planet.get("name", "")))
			var index: int = picker.item_count - 1
			picker.set_item_metadata(index, id)
			if id == wormhole_target:
				selected = index
	picker.select(selected)
	if selected == 0:
		wormhole_target = ""


func _select_wormhole_target(index: int) -> void:
	if not building_cards.has("wormhole"):
		return
	var picker: OptionButton = building_cards["wormhole"]["target"]
	wormhole_target = str(picker.get_item_metadata(index))
	_tick_building_cards()


func _tick_building_cards() -> void:
	var info: Dictionary = host.state.get("megastructures", {})
	var now: float = host._server_now()
	var energy: float = _estimated_energy(info, now)
	var queue: Dictionary = info.get("queue", {}) if info.get("queue") is Dictionary else {}
	var window: Dictionary = info.get("window", {}) if info.get("window") is Dictionary else {}
	var active: bool = not window.is_empty() and now < float(window.get("closes_at", 0))
	var origin: bool = bool(info.get("is_origin", false))
	var busy: bool = host.request_pending or host.update_required
	for key: String in building_cards:
		var controls: Dictionary = building_cards[key]
		if not is_instance_valid(controls["panel"]):
			continue
		var project: Dictionary = controls.get("project", {})
		var complete: bool = int(project.get("level", 0)) >= int(project.get("max_level", 1))
		var building: bool = str(queue.get("key", "")) == key
		# Use the same per-resource affordability colours as ordinary buildings.
		# Refresh on every state/tick so changing planets or spending resources
		# cannot leave a stale white price on either megaproject.
		for resource: String in host.RESOURCE_KEYS:
			var amount: float = float(project.get("cost", {}).get(resource, 0))
			var owned: float = float(host.state.get("resources", {}).get(resource, 0))
			var item: Dictionary = controls["costs"][resource]
			item["row"].visible = amount > 0
			var caption: Label = item["amount"]
			caption.text = host._stat_number(amount)
			var tint: Color = host._ui_color(Color("ff9287") if amount > owned else Color("c9d9cb"))
			if not caption.has_theme_color_override("font_color") or caption.get_theme_color("font_color") != tint:
				caption.add_theme_color_override("font_color", tint)
		controls["energy"].text = I18n.t("Energia: %s / %s") % [host._number(energy), host._number(float(info.get("capacity", 0)))]
		controls["energy"].visible = int(info.get("dyson_stage", 0)) > 0
		if key == "dyson":
			controls["energy"].text += " · " + I18n.t("Ładowanie: %s / s") % host._number(float(info.get("charge_per_second", 0)))
		elif complete:
			controls["energy"].text += "\n" + I18n.t("Energia na otwarcie: %s") % host._number(float(info.get("opening_required", 0)))
		var action: Button = controls["action"]
		action.text = I18n.t("Ulepsz") if int(project.get("level", 0)) > 0 else I18n.t("Buduj")
		action.disabled = not bool(project.get("enabled", false)) or busy
		action.visible = not complete or key == "wormhole"
		controls["status"].text = I18n.t("Czas: ") + host._duration(float(project.get("seconds", 0)))
		if building:
			controls["status"].text = host._server_text(queue.get("name", "")) + " · " + host._duration(float(queue.get("ends_at", 0)) - now)
		elif complete:
			controls["status"].text = I18n.t("Projekt ukończony.")
		elif not bool(project.get("enabled", false)):
			var reason: String = host._server_text(project.get("reason", ""))
			# Requirements are already listed once on the card.
			if reason != I18n.t("Nie spełniono wymagań projektu.") and not reason.is_empty():
				controls["status"].text += "\n" + reason
		controls["cancel"].visible = building
		controls["cancel"].disabled = not origin or busy or float(queue.get("ends_at", 0)) <= now
		if key == "wormhole" and complete:
			action.text = I18n.t("Zamknij tunel") if active else I18n.t("Otwórz tunel")
			action.disabled = busy or not origin or bool(info.get("suspended", false)) or (not active and (wormhole_target.is_empty() or energy < float(info.get("opening_required", 0))))
			controls["target"].disabled = active or not origin or busy
			if active:
				controls["status"].text = str(window.get("target_name", "")) + " · " + (I18n.t("Stabilizacja: %s") % host._duration(float(window.get("ready_at", 0)) - now) if now < float(window.get("ready_at", 0)) else I18n.t("Okno transportowe: %s") % host._duration(float(window.get("closes_at", 0)) - now))
			else:
				controls["status"].text = I18n.t("Tunel zamknięty")


func _building_action(key: String) -> void:
	if key == "wormhole" and int(host.state.get("megastructures", {}).get("gate_level", 0)) > 0:
		var window: Dictionary = host.state.get("megastructures", {}).get("window", {}) if host.state.get("megastructures", {}).get("window") is Dictionary else {}
		if not window.is_empty() and host._server_now() < float(window.get("closes_at", 0)):
			_act({"type": "tunnel_close"})
		elif not wormhole_target.is_empty():
			_act({"type": "tunnel_open", "target_id": wormhole_target})
		return
	_act({"type": "megabuild", "key": key})


func _cancel_building(key: String) -> void:
	var queue: Dictionary = host.state.get("megastructures", {}).get("queue", {}) if host.state.get("megastructures", {}).get("queue") is Dictionary else {}
	if str(queue.get("key", "")) == key:
		_act({"type": "megacancel", "queue_id": queue.get("id", "")})


func open_projects() -> void:
	# Research unlock links land on the same building cards as ordinary browsing.
	host.compact_ui.close_details()
	host._open_tab(0)
	if is_instance_valid(building_parent):
		for index: int in range(building_parent.get_child_count()):
			if building_parent.get_child(index).name == "MegastructureCard_dyson":
				host.building_carousel._scroll_to.call_deferred(index)
				return


func _go_origin() -> void:
	var origin_id: String = str(host.state.get("megastructures", {}).get("origin_id", ""))
	host.compact_ui.close_details()
	for index: int in range(host.planet_picker.item_count):
		if str(host.planet_picker.get_item_metadata(index)) == origin_id:
			host._select_owned_planet(index)
			return


func _open_tunnel() -> void:
	_act({"type": "tunnel_open", "target_id": host.selected_target})


func _act(payload: Dictionary) -> void:
	if host.request_pending or host.update_required:
		return
	var action: Dictionary = payload.duplicate(true)
	action["planet_id"] = host.selected_planet
	action["request_id"] = host._new_request_id()
	host._request("/api/action", action, "action")
