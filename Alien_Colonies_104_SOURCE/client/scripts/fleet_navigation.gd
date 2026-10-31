extends RefCounted
## Visual native fleet composer. All dispatches still use main.gd's authenticated
## preview/action flow, quote fingerprint and idempotent request_id.

const Model = preload("res://client/scripts/fleet_navigation_model.gd")
const Route = preload("res://client/scripts/fleet_route.gd")
const GalaxyMap = preload("res://client/scripts/galaxy_map.gd")
const ResourceInfo = preload("res://client/scripts/resource_info.gd")
const MissionTimeline = preload("res://client/scripts/fleet_mission_timeline.gd")
const DESTINATION_MAP_ZOOM: float = GalaxyMap.DEFAULT_FOCUS_ZOOM

var host
var expedition_hours: int = 1
var expedition_box: VBoxContainer
var expedition_choice
var expedition_info: Label
var ready: bool = false
var route_view: Route
var destination_name: Label
var destination_owner: Label
var destination_facts: RichTextLabel
var destination_visibility: Label
var choose_button: Button
var details_button: Button
var mission_buttons: Array[Button] = []
var mission_titles: Array[Label] = []
var fleet_totals: Label
var required_button: Button
var requirements_label: Label
var route_metrics: RichTextLabel
var route_metrics_text: String = ""
var quote_details: RichTextLabel
var quote_details_text: String = ""
var draft_feedback_card: Control
var dock_target: Label
var dock_summary: RichTextLabel
var last_quote: Dictionary = {}
var last_quote_fingerprint: String = ""
var map_marker: Control
var picker_map: GalaxyMap
var picker_galaxy
var picker_systems
var picker_planets: GridContainer
var picker_status: Label
var picker_heading: Label
var picker_system_scout: Button
var picker_map_panel: VBoxContainer
var picker_planet_panel: VBoxContainer
var picker_change_system: Button
var filter_buttons: Array[Button] = []
var browse_galaxy: String = ""
var browse_system: String = ""
var filter_index: int = 0
var map_signature: String = ""
var auto_quote_timer: Timer
var auto_quote_fingerprint: String = ""
var attempted_quote_fingerprint: String = ""
var quote_error: String = ""
var quote_resources: Dictionary = {}
var quote_received_msec: int = 0
var quote_energy: float = 0.0
var dispatch_busy: bool = false
var committing_fields: bool = false
var quantity_text_pending: bool = false
var dock_warning: Label
var before_dispatch_ids: Array = []
var receipt_fleet_id: String = ""
var receipt_marker: Control
var receipt_timeline: Control

func setup(client) -> void:
	host = client
	var form: VBoxContainer = host.target_picker.get_parent() as VBoxContainer
	form.name = "VisualFleetComposer"
	form.add_theme_constant_override("separation", 14)
	# Keep the original pickers as the single mission/target selection model;
	# they are no longer the primary, text-only user interface.
	for child: Node in form.get_children():
		if child is Label or child == host.target_picker or child == host.mission_picker:
			child.hide()
	route_view = Route.new()
	route_view.name = "FleetOriginDestination"
	form.add_child(route_view)
	var destination: VBoxContainer = _section(form, "FleetDestinationCard")
	destination_name = _label("", 29)
	destination.add_child(destination_name)
	destination_owner = _label("", 22)
	destination.add_child(destination_owner)
	destination_facts = ResourceInfo.label(host, "", 20)
	destination.add_child(destination_facts)
	destination_visibility = _label("", 18)
	destination_visibility.add_theme_color_override("font_color", Color("b0bacc"))
	destination.add_child(destination_visibility)
	var destination_actions: HBoxContainer = host._row(destination)
	choose_button = host._button(I18n.t("Wybierz cel na mapie"), open_destination_map, true)
	choose_button.name = "ChooseVisualDestination"
	choose_button.custom_minimum_size.y = 66
	choose_button.add_theme_font_size_override("font_size", 21)
	choose_button.icon = host._texture("galaxy")
	choose_button.expand_icon = true
	choose_button.add_theme_constant_override("icon_max_width", 28)
	destination_actions.add_child(choose_button)
	details_button = host._button(I18n.t("Szczegóły planety"), _open_target_details)
	details_button.name = "FleetTargetDetails"
	details_button.custom_minimum_size = Vector2(140, 66)
	details_button.add_theme_font_size_override("font_size", 20)
	destination_actions.add_child(details_button)
	form.add_child(_label(I18n.t("Rodzaj misji"), 25))
	var missions: GridContainer = GridContainer.new()
	missions.name = "VisualMissionTypes"
	missions.columns = 2
	missions.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	missions.add_theme_constant_override("h_separation", 10)
	missions.add_theme_constant_override("v_separation", 10)
	form.add_child(missions)
	for index: int in range(host.MISSION_KEYS.size()):
		_make_mission_tile(missions, index)
	expedition_box = _section(form,"ExpeditionOptions")
	expedition_box.add_child(_label(I18n.t("Czas poszukiwań"),24))
	expedition_choice = host._choice(I18n.t("Czas poszukiwań"),64)
	expedition_choice.name = "ExpeditionDuration"
	for hours: int in [1,3,6]:
		expedition_choice.add_item("%d h" % hours)
		expedition_choice.set_item_metadata(expedition_choice.item_count-1,hours)
	expedition_choice.item_selected.connect(func(index: int) -> void:
		expedition_hours = int(expedition_choice.get_item_metadata(index))
		host._invalidate_quote()
		refresh())
	expedition_box.add_child(expedition_choice)
	expedition_info = _label("",19)
	expedition_box.add_child(expedition_info)
	_append(host.mission_hint, form)
	host.mission_hint.hide()
	host.mission_hint.add_theme_font_size_override("font_size", 19)
	_append(host.megastructure_ui.fleet_box, form)
	var fleet_head: HBoxContainer = host._row(form)
	fleet_head.add_child(_label(I18n.t("Wybierz flotę"), 25))
	required_button = host._button(I18n.t("Dodaj wymagany statek"), _add_required_ship)
	required_button.name = "AddRequiredMissionShip"
	required_button.add_theme_font_size_override("font_size", 19)
	required_button.custom_minimum_size.y = 58
	fleet_head.add_child(required_button)
	var quick_selection: HBoxContainer = host._row(form)
	var all_ships: Button = host._button(I18n.t("Cała flota"), _select_all_ships)
	all_ships.name = "SelectAllAvailableShips"
	all_ships.custom_minimum_size.y = 58
	quick_selection.add_child(all_ships)
	var clear_ships: Button = host._button(I18n.t("Wyczyść"), _clear_ships)
	clear_ships.name = "ClearSelectedShips"
	clear_ships.custom_minimum_size.y = 58
	quick_selection.add_child(clear_ships)
	_append(host.fleet_selection_list, form)
	host.fleet_selection_list.add_theme_constant_override("separation", 12)
	fleet_totals = _label("", 20)
	form.add_child(fleet_totals)
	_append(host.cargo_box, form)
	var summary: VBoxContainer = _section(form, "VisualRouteSummary")
	draft_feedback_card = summary.get_parent() as Control
	# Exact route metrics and consequential warnings remain beside the one send
	# action. The body only contains optional detail, never a required next step.
	route_metrics = ResourceInfo.label(host, "", 24)
	summary.add_child(route_metrics)
	route_metrics.hide()
	requirements_label = _label("", 20)
	requirements_label.add_theme_color_override("font_color", Color("ffc782"))
	summary.add_child(requirements_label)
	# Long server explanations live in the scrollable summary, not over the
	# bottom navigation. The dock always shows an unambiguous origin and target.
	var dock_body: VBoxContainer = host.quote_label.get_parent() as VBoxContainer
	host.quote_label.reparent(summary)
	host.quote_label.hide()
	quote_details = ResourceInfo.label(host, "", 19)
	summary.add_child(quote_details)
	dock_target = _label("", 20)
	dock_target.max_lines_visible = 2
	dock_target.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	dock_body.add_child(dock_target)
	dock_body.move_child(dock_target, 0)
	dock_summary = ResourceInfo.label(host, "", 19)
	dock_summary.name = "FleetLiveQuote"
	dock_summary.fit_content = true
	dock_summary.custom_minimum_size.y = 50
	dock_body.add_child(dock_summary)
	dock_body.move_child(dock_summary, 1)
	dock_warning = _label("", 18)
	dock_warning.name = "FleetDepartureWarning"
	dock_warning.add_theme_color_override("font_color", Color("ffc56f"))
	dock_body.add_child(dock_warning)
	dock_body.move_child(dock_warning, 2)
	host.preview_button.hide()
	host.preview_button.text = I18n.t("Ponów wycenę")
	if host.preview_button.pressed.is_connected(host._preview_fleet):
		host.preview_button.pressed.disconnect(host._preview_fleet)
	host.preview_button.pressed.connect(retry_quote)
	if host.send_button.pressed.is_connected(host._send_fleet):
		host.send_button.pressed.disconnect(host._send_fleet)
	host.send_button.pressed.connect(dispatch_departure)
	auto_quote_timer = Timer.new()
	auto_quote_timer.name = "FleetAutoQuoteDebounce"
	auto_quote_timer.one_shot = true
	auto_quote_timer.wait_time = 0.4
	host.add_child(auto_quote_timer)
	auto_quote_timer.timeout.connect(_auto_quote_timeout)
	for quantities: Dictionary in [host.fleet_inputs, host.cargo_inputs]:
		for quantity: Variant in quantities.values():
			quantity.editor.text_changed.connect(_quantity_text_changed)
	ready = true
	refresh()

func _append(node: Control, parent: Node) -> void:
	if node.get_parent() != parent:
		node.reparent(parent)
	parent.move_child(node, parent.get_child_count() - 1)

func _label(text: String, font_size: int) -> Label:
	var label: Label = host._label(text, font_size)
	label.add_theme_font_size_override("font_size", font_size)
	return label

func _section(parent: Node, title: String) -> VBoxContainer:
	var body: VBoxContainer = host._card(parent)
	body.get_parent().name = title
	body.add_theme_constant_override("separation", 8)
	return body

func _make_mission_tile(parent: GridContainer, index: int) -> void:
	var button: Button = host._button("", _choose_mission.bind(index))
	button.name = "MissionTile_" + host.MISSION_KEYS[index]
	button.custom_minimum_size.y = 108
	button.toggle_mode = true
	parent.add_child(button)
	var margin: MarginContainer = _button_margin(button, 12)
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(row)
	row.add_child(host._icon(["scout", "colonizer", "weapons", "cargo", "galaxy"][index], 40))
	var text: VBoxContainer = VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(text)
	var title: Label = _label(I18n.t(host.MISSION_NAMES[index]), 22)
	text.add_child(title)
	var subtitle: Label = _label(I18n.t(["Poznaj nieznany cel", "Załóż nową kolonię", "Uderz na obcą flotę", "Przewieź surowce", "Zbadaj nieznany sektor"][index]), 17)
	text.add_child(subtitle)
	margin.minimum_size_changed.connect(_fit_button.bind(button, margin, 108.0))
	mission_buttons.append(button)
	mission_titles.append(title)

func _button_margin(button: Button, padding: int) -> MarginContainer:
	var margin: MarginContainer = MarginContainer.new()
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(margin)
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, padding)
	return margin

func _fit_button(button: Button, margin: MarginContainer, minimum: float) -> void:
	if is_instance_valid(button) and is_instance_valid(margin):
		button.custom_minimum_size.y = maxf(minimum, margin.get_combined_minimum_size().y)

func reset_draft() -> void:
	last_quote = {}
	last_quote_fingerprint = ""
	auto_quote_timer.stop()
	auto_quote_fingerprint = ""
	attempted_quote_fingerprint = ""
	quote_error = ""
	dispatch_busy = false
	quantity_text_pending = false
	before_dispatch_ids = []
	receipt_fleet_id = ""
	map_signature = ""
	browse_galaxy = ""
	browse_system = ""
	filter_index = 0


func composer_opened() -> void:
	if not ready:
		return
	refresh()
	if host.selected_target.is_empty():
		open_destination_map()
	elif Model.ship_total(host._fleet_payload().get("ships", {})) == 0:
		_add_required_ship()

func open_expedition() -> void:
	host.selected_scout_system = ""
	host.mission_picker.select(4)
	host._mission_changed(4)
	host.compact_ui.open_composer()
	_add_required_ship()

func _choose_mission(index: int) -> void:
	host.mission_picker.select(index)
	host._mission_changed(index)
	if index != 4 and host.selected_target.is_empty():
		open_destination_map()
	_add_required_ship()
	refresh()

func _add_required_ship() -> void:
	var key: String = Model.required_ship(host.state, int(host.mission_picker.selected))
	if not key.is_empty() and host.fleet_inputs.has(key) and int(host.state.get("ships", {}).get(key, 0)) > 0:
		# Never remove escort, cargo ships or the user's already-entered quantities.
		if int(host.fleet_inputs[key].value) < 1:
			host.fleet_inputs[key].value = 1
			host._invalidate_quote()
	refresh()

func _art(record: Dictionary) -> Texture2D:
	if record.is_empty() or not bool(record.get("known", false)):
		return null
	return host.ArtLibrary.planet_texture(str(record.get("id", "")))

func _background(record: Dictionary) -> Texture2D:
	var id: String = str(record.get("galaxy_id", host.state.get("planet_galaxy_id", "g1")))
	for galaxy: Dictionary in host._galaxy_catalog():
		if str(galaxy.get("id", "")) == id:
			return host.ArtLibrary.texture(str(galaxy.get("art_key", "galaxies/aurora")))
	return host.ArtLibrary.texture("galaxies/aurora")

func _configure_route(view: Route, destination: Dictionary) -> void:
	var start: Dictionary = Model.origin(host.state)
	view.set_route(str(start.get("name", "")), str(destination.get("name", I18n.t("Wybierz cel"))), _art(start), _art(destination), _background(start), host._ui_color(Color("91c89b")))

func _selected_destination() -> Dictionary:
	return Model.target(host.state, host.selected_target, host.selected_scout_system if host.mission_picker.selected == 0 else "")


func _owner_caption(record: Dictionary) -> String:
	if bool(record.get("expedition",false)):
		return I18n.t("Strefa ekspedycyjna")
	if str(record.get("scout_scope", "")) == "system":
		return I18n.t("Zwiad całego układu")
	if not bool(record.get("known", false)):
		return I18n.t("Nieznany cel · tylko zwiad")
	var planet: Dictionary = record.get("planet", {})
	if Model.owned(host.state, record):
		return I18n.t("● Twoja kolonia")
	if Model.allied(host.state, record):
		return I18n.t("Sojusznik: %s") % str(planet.get("owner_name", ""))
	match str(planet.get("owner_type", "")):
		"empty": return I18n.t("○ Wolna planeta")
		"alien": return I18n.t("Rój") + " · " + str(planet.get("owner_name", ""))
	return str(planet.get("owner_name", I18n.t("Inny gracz")))

func _facts(record: Dictionary) -> String:
	if bool(record.get("expedition",false)):
		return I18n.t("Zwiadowca prowadzi poszukiwania. Transportowce zabierają znaleziska, a okręty bojowe chronią przed patrolem Roju.")
	var system: Dictionary = record.get("system", {})
	var text: String = host._galaxy_name(str(record.get("galaxy_id", "g1"))) + " / " + str(system.get("name", system.get("id", "")))
	if str(record.get("scout_scope", "")) == "system":
		return text + "\n" + I18n.t("Odśwież wolne planety i właścicieli w całym układzie. Szczegóły zasobów i obrony wymagają osobnego zwiadu planety.")
	if not bool(record.get("known", false)):
		return text + "\n" + I18n.t("Wyślij zwiad, aby odkryć planety tego układu.")
	var environment: Dictionary = record.get("planet", {}).get("environment", {})
	if not environment.is_empty():
		text += "\n" + host._server_text(environment.get("type_name", ""))
		if environment.has("fields"):
			text += " · " + I18n.t("%d slotów") % int(environment["fields"])
		var multipliers: Dictionary = environment.get("multipliers", {})
		if not multipliers.is_empty():
			var parts: Array[String] = []
			for key: String in host.RESOURCE_KEYS:
				if multipliers.has(key):
					parts.append(ResourceInfo.token(key) + " ×" + I18n.decimal("%.2f" % float(multipliers[key])))
			text += "\n" + " · ".join(parts)
	return text

func draft_reason() -> String:
	return Model.draft_reason(host.state, host._fleet_payload(), host._server_now())

func _composer_active() -> bool:
	return ready and host.is_inside_tree() and not host.session_token.is_empty() and not host.showing_login and not host.connection_editing and not host.update_required and host.current_tab == 2 and host.fleet_mode == 0 and host.compact_ui.composing and not host.compact_ui.details_open() and host.requested_planet.is_empty() and host.uncertain_action.is_empty() and not dispatch_busy

func _quote_key() -> String:
	return JSON.stringify([host._fleet_fingerprint(), host._quote_world_signature(host.state), host.fleet_draft_generation, host.state.get("world_epoch", ""), host.state.get("player", {}).get("id", "")])

func tick() -> void:
	if ready and not _composer_active():
		auto_quote_timer.stop()
		auto_quote_fingerprint = ""

func _quantity_text_changed(_text: String) -> void:
	if not ready or committing_fields or host.refreshing:
		return
	# Numeric text is committed at the debounce boundary, including edits whose
	# field still has focus. Quoting never relies on an old spinner value.
	attempted_quote_fingerprint = ""
	quote_error = ""
	quantity_text_pending = true
	host._invalidate_quote()
	if _composer_active():
		auto_quote_fingerprint = _quote_key()
		auto_quote_timer.start(0.4)

func _schedule_quote() -> void:
	if not _composer_active():
		auto_quote_timer.stop()
		return
	if committing_fields:
		return
	if not quantity_text_pending and not draft_reason().is_empty():
		auto_quote_timer.stop()
		return
	var fingerprint: String = _quote_key()
	if not quantity_text_pending and ((not last_quote.is_empty() and last_quote_fingerprint == host._fleet_fingerprint()) or attempted_quote_fingerprint == fingerprint):
		auto_quote_timer.stop()
		return
	if auto_quote_fingerprint == fingerprint and not auto_quote_timer.is_stopped():
		return
	auto_quote_fingerprint = fingerprint
	auto_quote_timer.start(0.4)

func _auto_quote_timeout() -> void:
	if not _composer_active():
		return
	if host.request_pending:
		# The shared command request finishes first; only the latest draft will be
		# quoted. An unresolved action is excluded by _composer_active().
		auto_quote_timer.start(0.15)
		return
	for quantities: Dictionary in [host.fleet_inputs, host.cargo_inputs]:
		for quantity: Variant in quantities.values():
			if quantity.editor.has_focus() and not quantity.editor.text.strip_edges().is_valid_int():
				return
	committing_fields = true
	host._commit_fleet_inputs()
	committing_fields = false
	quantity_text_pending = false
	auto_quote_timer.stop()
	if not draft_reason().is_empty():
		refresh()
		return
	if not last_quote.is_empty() and last_quote_fingerprint == host._fleet_fingerprint():
		return
	attempted_quote_fingerprint = _quote_key()
	quote_error = ""
	host._preview_fleet()
	if not host.request_pending:
		quote_error = I18n.t("Nie udało się wycenić trasy. Ponów wycenę.")
	refresh()

func retry_quote() -> void:
	attempted_quote_fingerprint = ""
	quote_error = ""
	refresh()

func preview_finished(result: int, response_code: int, response: Variant) -> void:
	if host.preview_requested_fingerprint != host._fleet_fingerprint() or host.preview_requested_world_signature != host._quote_world_signature(host.state) or host.preview_requested_generation != host.fleet_draft_generation:
		return
	if last_quote_fingerprint != host._fleet_fingerprint() or last_quote.is_empty():
		quote_error = host._server_text(response.get("error", "")) if response is Dictionary and response_code >= 400 and response_code < 500 else ""
		if quote_error.is_empty():
			quote_error = I18n.t("Nie udało się wycenić trasy. Ponów wycenę.")
		if result != HTTPRequest.RESULT_SUCCESS:
			quote_error = I18n.t("Brak połączenia. Ponów wycenę trasy.")
	refresh()

func _select_all_ships() -> void:
	for key: String in host.fleet_inputs:
		host.fleet_inputs[key].value = mini(int(host.state.get("ships", {}).get(key, 0)), 10000)
	refresh()

func _clear_ships() -> void:
	for quantity: Variant in host.fleet_inputs.values():
		quantity.value = 0
	refresh()

func invalidate() -> void:
	last_quote.clear()
	last_quote_fingerprint = ""
	if _quote_key() != attempted_quote_fingerprint:
		quote_error = ""
	if ready:
		refresh()

func accept_quote(response: Dictionary) -> void:
	if host.preview_fingerprint != host._fleet_fingerprint():
		return
	if not Model.valid_quote(response):
		host.quote_ready = false
		last_quote.clear()
		last_quote_fingerprint = ""
		host.quote_label.text = I18n.t("Niepełne dane trasy. Sprawdź trasę ponownie.")
		host._notify(host.quote_label.text, true)
		refresh()
		return
	last_quote = response.duplicate(true)
	last_quote_fingerprint = host.preview_fingerprint
	quote_resources = host.state.get("resources", {}).duplicate(true)
	quote_energy = float(host.state.get("megastructures", {}).get("energy", 0))
	quote_received_msec = Time.get_ticks_msec()
	quote_error = ""
	refresh()
	# The fixed action dock shows the exact server result without moving the form.

func _quoted_details() -> String:
	var lines: PackedStringArray = PackedStringArray()
	var route: Dictionary = last_quote.get("route", {})
	if bool(route.get("intergalactic", false)):
		lines.append(str(route.get("origin_galaxy_name", "")) + " → " + str(route.get("target_galaxy_name", "")))
	lines.append(I18n.t("Koszt zostanie pobrany przy starcie."))
	var message: String = host._server_text(last_quote.get("message", "")).strip_edges()
	var colony_warning: String = str(last_quote.get("colonization_warning", ""))
	if not colony_warning.is_empty():
		message = message.replace(colony_warning, "").strip_edges()
	if not message.is_empty():
		lines.append(message)
	if not host.quote_ready:
		lines.append(I18n.t("Brakujące zasoby: %s") % ResourceInfo.cost(host, last_quote.get("shortfall", {})))
		if last_quote.has("tunnel"):
			lines.append(I18n.t("Brakująca energia: %s") % host._number(float(last_quote["tunnel"].get("energy_shortfall", 0))))
	return "\n".join(lines)

func refresh() -> void:
	if not ready:
		return
	var destination: Dictionary = _selected_destination()
	var start: Dictionary = Model.origin(host.state)
	_configure_route(route_view, destination)
	destination_name.text = str(destination.get("name", I18n.t("Dokąd ma polecieć flota?")))
	destination_owner.text = _owner_caption(destination) if not destination.is_empty() else I18n.t("Dotknij mapy i wybierz konkretną planetę.")
	ResourceInfo.set_text(destination_facts, host, _facts(destination) if not destination.is_empty() else "")
	destination_facts.visible = not destination.is_empty()
	destination_visibility.text = host.planetary_ui.visibility_text(destination.get("planet", {})) if bool(destination.get("known", false)) else ""
	destination_visibility.visible = not destination_visibility.text.is_empty()
	details_button.visible = bool(destination.get("known", false))
	choose_button.text = I18n.t("Wybierz cel na mapie") if destination.is_empty() else I18n.t("Zmień cel na mapie")
	var mission: int = int(host.mission_picker.selected)
	choose_button.visible = mission != 4
	expedition_box.get_parent().visible = mission == 4
	if mission == 4:
		host.megastructure_ui.fleet_box.hide()
	var info: Dictionary = host.state.get("expeditions",{})
	expedition_info.text = I18n.t("Baza: poz. %d · znaleziska +%d%% · ekspedycje %d/%d") % [int(info.get("level",0)),int(info.get("reward_bonus_percent",0)),int(info.get("active",0)),int(info.get("max_active",0))]
	expedition_info.text += "\n" + I18n.t("Surowce 50% · statki 10% · pusto 20% · patrol 10% · opóźnienie 10%.")
	expedition_info.text += "\n" + I18n.t("Zwycięstwo nad patrolem: 25% szansy na 1 Kryształ Roju. Znaleziska otrzymasz po powrocie.")
	for index: int in range(mission_buttons.size()):
		var button: Button = mission_buttons[index]
		var selected: bool = index == mission
		var validation_target: Dictionary = Model.target(host.state,str(info.get("zone",{}).get("id",""))) if index == 4 else {} if bool(destination.get("expedition",false)) else destination
		var reason: String = Model.mission_reason(host.state,validation_target,index,host._server_now())
		# The player may choose an intention before opening the map.
		button.disabled = host.update_required or (index == 4 and not reason.is_empty()) or (index != 4 and not bool(destination.get("expedition",false)) and not destination.is_empty() and not reason.is_empty())
		button.set_pressed_no_signal(selected)
		button.add_theme_stylebox_override("normal", host._style("284b33" if selected else "152a1d", "91c89b" if selected else "314b39", 13, 12))
		mission_titles[index].text = ("✓ " if selected else "") + I18n.t("Zwiad całego układu" if index == 0 and not host.selected_scout_system.is_empty() else host.MISSION_NAMES[index])
		button.tooltip_text = I18n.t(reason) if not reason.is_empty() else I18n.t(host.MISSION_NAMES[index])
	var payload: Dictionary = host._fleet_payload()
	var total: int = Model.ship_total(payload.get("ships", {}))
	var capacity: int = Model.capacity(host.state, payload.get("ships", {}))
	fleet_totals.text = I18n.t("Wybrane statki: %d · Ładowność: %s") % [total, host._exact_integer(capacity)]
	var required: String = Model.required_ship(host.state, mission)
	required_button.visible = mission in [0, 1, 2, 4]
	required_button.disabled = required.is_empty() or not host.fleet_inputs.has(required) or int(host.state.get("ships", {}).get(required, 0)) < 1
	if not required.is_empty():
		required_button.text = I18n.t("Dodaj: %s") % host._catalog_name(required, "ships")
	else:
		required_button.text = I18n.t("Brak wymaganego statku")
	for key: String in host.fleet_names:
		host.fleet_names[key].text = ("✓ " if key == required and mission in [0, 1, 4] else "") + host._catalog_name(key, "ships")
	var problem: String = draft_reason()
	requirements_label.text = I18n.t(problem)
	requirements_label.visible = not problem.is_empty()
	host.preview_button.visible = not quote_error.is_empty()
	host.preview_button.disabled = not problem.is_empty() or host.request_pending or host.update_required or not host.requested_planet.is_empty() or not host.uncertain_action.is_empty()
	if not last_quote.is_empty() and not host.quote_ready and last_quote_fingerprint == host._fleet_fingerprint():
		for key: String in last_quote.get("shortfall", {}):
			var growth: float = float(host.state.get("resources", {}).get(key, 0)) - float(quote_resources.get(key, 0))
			var needed: float = float(last_quote.get("shortfall", {}).get(key, 0))
			if needed > 0 and growth > 0 and (growth >= needed or Time.get_ticks_msec() - quote_received_msec >= 3000):
				host._invalidate_quote()
				return
		var energy_needed: float = float(last_quote.get("tunnel", {}).get("energy_shortfall", 0))
		var energy_growth: float = float(host.state.get("megastructures", {}).get("energy", 0)) - quote_energy
		if energy_needed > 0 and energy_growth > 0 and (energy_growth >= energy_needed or Time.get_ticks_msec() - quote_received_msec >= 3000):
			host._invalidate_quote()
			return
	var quoted: bool = not last_quote.is_empty() and last_quote_fingerprint == host._fleet_fingerprint()
	var can_send: bool = _composer_active() and quoted and host.quote_ready and problem.is_empty() and not host.request_pending
	host.send_button.disabled = not can_send
	host.send_button.text = I18n.t("Wyślij zwiad układu" if str(payload.get("scout_scope", "")) == "system" else Model.dispatch_caption(str(payload.get("mission", ""))))
	if dispatch_busy or not host.uncertain_action.is_empty():
		host.send_button.text = I18n.t("Wysyłanie rozkazu…")
	if quoted:
		route_metrics_text = I18n.t("Czas lotu: %s") % host._duration(float(last_quote.get("seconds", 0)))
		if last_quote.has("tunnel"):
			route_metrics_text += "\n" + I18n.t("Energia tunelu: %s · rezerwa powrotu: %s") % [host._exact_integer(int(last_quote["tunnel"].get("energy_cost", 0))), host._exact_integer(int(last_quote["tunnel"].get("return_reserved", 0)))]
		else:
			route_metrics_text += " · " + ResourceInfo.token("fuel") + "\u00A0" + host._exact_integer(int(last_quote.get("fuel_cost", 0)))
		route_metrics_text += "\n" + I18n.t("Ładunek: %s / %s") % [host._exact_integer(Model.ship_total(payload.get("cargo", {}))), host._exact_integer(int(last_quote.get("capacity", capacity)))]
		if last_quote.has("expedition"):
			route_metrics_text += "\n" + I18n.t("Poszukiwania: %d h") % expedition_hours
		var return_quote: Dictionary = Model.quoted_return(last_quote)
		if return_quote.has("at"):
			route_metrics_text += "\n" + I18n.t("Przewidywany powrót: %s") % host._date(float(return_quote["at"]))
		elif return_quote.has("seconds"):
			route_metrics_text += "\n" + I18n.t("Przewidywany czas lotu powrotnego: %s") % host._duration(float(return_quote["seconds"]))
	else:
		route_metrics_text = I18n.t(problem) if not problem.is_empty() else quote_error if not quote_error.is_empty() else I18n.t("Obliczanie czasu i paliwa…")
	ResourceInfo.set_text(route_metrics, host, route_metrics_text)
	quote_details_text = _quoted_details() if quoted else host.quote_label.text
	ResourceInfo.set_text(quote_details, host, quote_details_text)
	# Complete cost notes appear once, in the final summary. Failed quotes retain
	# their exact shortfalls in the editor so the player can correct the draft.
	quote_details.visible = false
	draft_feedback_card.hide()
	quote_details.add_theme_color_override("default_color", host._ui_color(Color("91c89b" if host.quote_ready else "ff9287")))
	dock_target.text = str(start.get("name", "")) + " → " + str(destination.get("name", I18n.t("Wybierz cel")))
	var dock_text: String = route_metrics_text
	if quoted and not host.quote_ready:
		dock_text += "\n" + I18n.t("Brakujące zasoby: %s") % ResourceInfo.cost(host, last_quote.get("shortfall", {}))
		if float(last_quote.get("tunnel", {}).get("energy_shortfall", 0)) > 0:
			dock_text += "\n" + I18n.t("Brakująca energia: %s") % host._number(float(last_quote["tunnel"]["energy_shortfall"]))
	ResourceInfo.set_text(dock_summary, host, dock_text)
	dock_summary.add_theme_color_override("default_color", host._ui_color(Color("91c89b" if can_send else "ffc56f")))
	var warnings: PackedStringArray = []
	if mission == 1:
		warnings.append(I18n.t("Kolonizacja: statki i ładunek pozostaną na planecie."))
		warnings.append(I18n.t("Niebroniona kolonia może zostać przejęta."))
	elif mission == 2 and str(destination.get("planet", {}).get("owner_type", "")) == "player":
		warnings.append(I18n.t("Atak na gracza kończy twoją ochronę startową."))
	if quoted and bool(last_quote.get("route", {}).get("intergalactic", false)):
		warnings.append(I18n.t("Lot międzygalaktyczny") + " · " + str(last_quote.get("route", {}).get("target_galaxy_name", "")))
	dock_warning.text = "\n".join(warnings)
	dock_warning.visible = not warnings.is_empty()
	if _map_open():
		_refresh_map()
	_schedule_quote()

func _open_target_details() -> void:
	if not host.selected_target.is_empty():
		host.compact_ui._open_planet(host.selected_target)

func _map_open() -> bool:
	return is_instance_valid(map_marker) and map_marker.is_inside_tree() and host.compact_ui.details_open()

func open_destination_map() -> void:
	if host.update_required or host.state.is_empty():
		return
	host._commit_fleet_inputs()
	var destination: Dictionary = _selected_destination()
	var focus: Dictionary = destination if not destination.is_empty() else Model.origin(host.state)
	browse_galaxy = str(focus.get("galaxy_id", "g1"))
	browse_system = str(focus.get("system", {}).get("id", ""))
	filter_index = 0
	map_signature = ""
	host.compact_ui._begin_details("", true, true)
	host.compact_ui.modal_back_handler = _destination_back
	var body: VBoxContainer = host.compact_ui.modal_body
	map_marker = Control.new()
	map_marker.name = "FleetDestinationMapMarker"
	map_marker.hide()
	body.add_child(map_marker)
	picker_map_panel = VBoxContainer.new()
	picker_map_panel.name = "FleetChooseSystem"
	picker_map_panel.add_theme_constant_override("separation", 10)
	body.add_child(picker_map_panel)
	var header: HBoxContainer = host._row(picker_map_panel)
	var previous: Button = host._button("‹", _change_galaxy.bind(-1))
	previous.custom_minimum_size = Vector2(58, 64)
	previous.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	header.add_child(previous)
	picker_galaxy = host._choice(I18n.t("Galaktyka"), 64)
	header.add_child(picker_galaxy)
	for galaxy: Dictionary in host._galaxy_catalog():
		picker_galaxy.add_item(str(galaxy.get("name", "")))
		picker_galaxy.set_item_metadata(picker_galaxy.item_count - 1, str(galaxy.get("id", "g1")))
		if str(galaxy.get("id", "")) == browse_galaxy:
			picker_galaxy.select(picker_galaxy.item_count - 1)
	picker_galaxy.item_selected.connect(_select_galaxy)
	var next: Button = host._button("›", _change_galaxy.bind(1))
	next.custom_minimum_size = Vector2(58, 64)
	next.size_flags_horizontal = Control.SIZE_SHRINK_END
	header.add_child(next)
	picker_map = GalaxyMap.new()
	picker_map.name = "FleetDestinationGalaxyMap"
	picker_map_panel.add_child(picker_map)
	picker_map.custom_minimum_size.y = 320.0
	picker_map.set_race_palette(host.RaceTheme.palette())
	picker_map.system_selected.connect(_select_system)
	var controls: HBoxContainer = host._row(picker_map_panel)
	for item: Array in [["−", picker_map.zoom_out], ["+", picker_map.zoom_in], [I18n.t("Cała galaktyka"), picker_map.reset_view]]:
		var button: Button = host._button(str(item[0]), item[1])
		button.custom_minimum_size.y = 52
		button.add_theme_font_size_override("font_size", 20)
		controls.add_child(button)
	picker_systems = host._choice(I18n.t("Wybierz układ"), 62)
	picker_systems.name = "FleetSystemFallback"
	picker_systems.item_selected.connect(_system_from_list)
	picker_map_panel.add_child(picker_systems)
	picker_planet_panel = VBoxContainer.new()
	picker_planet_panel.name = "FleetChoosePlanet"
	picker_planet_panel.add_theme_constant_override("separation", 10)
	body.add_child(picker_planet_panel)
	picker_heading = _label("", 25)
	picker_planet_panel.add_child(picker_heading)
	picker_change_system = host._button(I18n.t("Wybierz inny układ"), _show_system_map)
	picker_change_system.name = "ChangeDestinationSystem"
	picker_change_system.custom_minimum_size.y = 58
	picker_planet_panel.add_child(picker_change_system)
	picker_system_scout = host._button(I18n.t("Zbadaj cały układ"), _select_system_scout, true)
	picker_system_scout.name = "FleetSurveyWholeSystem"
	picker_system_scout.custom_minimum_size.y = 62
	picker_planet_panel.add_child(picker_system_scout)
	var filters: GridContainer = GridContainer.new()
	filters.columns = 4
	filters.add_theme_constant_override("h_separation", 6)
	picker_planet_panel.add_child(filters)
	filter_buttons.clear()
	for index: int in range(4):
		var button: Button = host._button(I18n.t(["Wszystkie", "Wolne", "Moje", "Obce"][index]), _set_filter.bind(index))
		button.toggle_mode = true
		button.custom_minimum_size.y = 58
		button.add_theme_font_size_override("font_size", 19)
		filters.add_child(button)
		filter_buttons.append(button)
	picker_status = _label("", 20)
	picker_planet_panel.add_child(picker_status)
	picker_planets = GridContainer.new()
	picker_planets.name = "VisualDestinationPlanets"
	picker_planets.columns = 1
	picker_planets.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	picker_planets.add_theme_constant_override("h_separation", 10)
	picker_planets.add_theme_constant_override("v_separation", 10)
	picker_planet_panel.add_child(picker_planets)
	picker_planet_panel.hide()
	_refresh_map()
	# Let the map use the actual remaining viewport, including after an inset
	# or window resize. Keep the navigation and zoom controls on screen.
	if not host.compact_ui.modal_scroll.resized.is_connected(_fit_destination_map):
		host.compact_ui.modal_scroll.resized.connect(_fit_destination_map)
	_fit_destination_map.call_deferred()
	picker_map.focus_system(browse_system, DESTINATION_MAP_ZOOM)
	# Reopening an existing destination starts on its galaxy map, not its planets.
	refresh()

func _fit_destination_map() -> void:
	if not _map_open() or not is_instance_valid(picker_map) or not picker_map_panel.visible:
		return
	var controls_height: float = 0.0
	var visible_count: int = 0
	for child: Node in picker_map_panel.get_children():
		if child is Control and child.visible:
			visible_count += 1
			if child != picker_map:
				controls_height += child.get_combined_minimum_size().y
	controls_height += picker_map_panel.get_theme_constant("separation") * maxi(0, visible_count - 1)
	var available: float = floorf(host.compact_ui.modal_scroll.size.y - controls_height - 4.0)
	picker_map.custom_minimum_size.y = maxf(260.0, available)

func _destination_back() -> bool:
	# User Back navigates one level. Explicit close_details() still dismisses
	# the picker after choosing a destination or changing the main screen.
	if _map_open() and is_instance_valid(picker_planet_panel) and picker_planet_panel.visible:
		_show_system_map()
		return true
	return false

func _select_galaxy(index: int) -> void:
	browse_galaxy = str(picker_galaxy.get_item_metadata(index))
	browse_system = ""
	picker_map.reset_view()
	_refresh_map()
	picker_map.focus_system(browse_system, DESTINATION_MAP_ZOOM)
	host.compact_ui.modal_scroll.scroll_vertical = 0

func _change_galaxy(direction: int) -> void:
	if not _map_open() or picker_galaxy.item_count < 1:
		return
	var index: int = posmod(picker_galaxy.selected + direction, picker_galaxy.item_count)
	picker_galaxy.select(index)
	_select_galaxy(index)

func _system_from_list(index: int) -> void:
	_select_system(str(picker_systems.get_item_metadata(index)))

func _select_system(id: String) -> void:
	browse_system = id
	_refresh_map()
	# The chosen system opens its planets immediately, without scrolling past
	# the galaxy map and its controls a second time.
	picker_map_panel.hide()
	picker_planet_panel.show()
	host.compact_ui.modal_scroll.scroll_vertical = 0
	host.compact_ui.modal_scroll.set_deferred("scroll_vertical", 0)

func _show_system_map() -> void:
	if not _map_open():
		return
	picker_planet_panel.hide()
	picker_map_panel.show()
	host.compact_ui.modal_scroll.scroll_vertical = 0
	_fit_destination_map.call_deferred()

func _set_filter(index: int) -> void:
	filter_index = index
	_refresh_map()

func _refresh_map() -> void:
	if not _map_open():
		return
	var systems: Array = []
	var active: Dictionary = {}
	for system: Dictionary in host.state.get("galaxy", []):
		if str(system.get("galaxy_id", "g1")) == browse_galaxy:
			systems.append(system)
			if str(system.get("id", "")) == browse_system:
				active = system
	if active.is_empty() and not systems.is_empty():
		active = systems[0]
		browse_system = str(active.get("id", ""))
	var map_route: Dictionary = {"travel_mode": str(host._fleet_payload().get("travel_mode", "normal"))}
	var quoted_target: Dictionary = _selected_destination()
	if not last_quote.is_empty() and last_quote_fingerprint == host._fleet_fingerprint() and str(quoted_target.get("system", {}).get("id", "")) == browse_system:
		map_route = last_quote.get("route", {}).duplicate(true)
		if last_quote.has("tunnel"):
			map_route["travel_mode"] = "tunnel"
	var signature: String = JSON.stringify([systems, browse_system, filter_index, host.selected_planet, host.selected_target, host.state.get("player", {}).get("id", ""), map_route])
	if signature == map_signature:
		return
	map_signature = signature
	picker_map.set_data(systems, str(host.state.get("player", {}).get("id", "")), browse_system)
	picker_map.set_galaxy_art(_background({"galaxy_id": browse_galaxy}))
	var origin_system: String = str(Model.origin(host.state).get("system", {}).get("id", ""))
	picker_map.set_route(origin_system, browse_system, map_route)
	picker_systems.clear()
	for system: Dictionary in systems:
		picker_systems.add_item(str(system.get("name", "")))
		picker_systems.set_item_metadata(picker_systems.item_count - 1, str(system.get("id", "")))
		if str(system.get("id", "")) == browse_system:
			picker_systems.select(picker_systems.item_count - 1)
	picker_heading.text = host._galaxy_name(browse_galaxy) + " / " + str(active.get("name", "")) + "\n" + I18n.t("Wybierz planetę")
	picker_system_scout.visible = not Model.GalaxyGuidance.system_scout_target(active, str(host.selected_planet)).is_empty()
	picker_system_scout.disabled = host.update_required
	for index: int in range(filter_buttons.size()):
		filter_buttons[index].set_pressed_no_signal(index == filter_index)
		filter_buttons[index].add_theme_stylebox_override("normal", host._style("284b33" if index == filter_index else "152a1d", "91c89b" if index == filter_index else "314b39", 10, 8))
	host._clear(picker_planets)
	if active.has("scout_target_id") and not active.has("system_scout_target_id") and filter_index in [0, 3]:
		var unknown: Dictionary = {"id": str(active["scout_target_id"]), "name": I18n.t("Zbadaj układ"), "known": false, "planet": {}, "system": active, "galaxy_id": browse_galaxy}
		_add_planet_button(unknown)
	for planet: Dictionary in active.get("planets", []):
		var record: Dictionary = {"id": str(planet.get("id", "")), "name": str(planet.get("name", "")), "known": true, "planet": planet, "system": active, "galaxy_id": browse_galaxy}
		var is_own: bool = Model.owned(host.state, record)
		var empty: bool = str(planet.get("owner_type", "")) == "empty"
		if filter_index == 1 and not empty:
			continue
		if filter_index == 2 and not is_own:
			continue
		if filter_index == 3 and (empty or is_own):
			continue
		_add_planet_button(record)
	picker_status.text = I18n.t("Lot międzygalaktyczny — sprawdź koszt paliwa dla wybranej floty.") if browse_galaxy != str(host.state.get("planet_galaxy_id", "g1")) else ""
	picker_status.visible = not picker_status.text.is_empty()

func _add_planet_button(record: Dictionary) -> void:
	var id: String = str(record.get("id", ""))
	var caption: String = I18n.t("Baza startowa") if id == host.selected_planet else _owner_caption(record)
	var environment: Dictionary = record.get("planet", {}).get("environment", {})
	if not environment.is_empty():
		caption += "\n" + host._server_text(environment.get("type_name", ""))
		if environment.has("fields"):
			caption += " · " + I18n.t("%d slotów") % int(environment["fields"])
	var title: String = str(record.get("name", id))
	if float(record.get("planet", {}).get("protected_until", 0)) > host._server_now():
		title += " · " + I18n.t("Chroniona")
	var texture: Texture2D = _art(record)
	if texture == null:
		texture = host._texture("scout")
	var button: Button = host.compact_ui._tap_row(picker_planets, title, caption, texture, _select_destination.bind(id))
	button.name = "Destination_" + id
	button.set_meta("target_id", id)
	button.disabled = id == host.selected_planet
	button.toggle_mode = true
	button.set_pressed_no_signal(id == host.selected_target)
	button.tooltip_text = title + "\n" + caption
	# Wrapped labels inside an anchored Button can report zero height on the
	# Android compatibility renderer. Explicit lines reserve reliable space.
	var heading: Label = button.get_meta("title_label")
	var info: Label = button.get_meta("subtitle_label")
	heading.autowrap_mode = TextServer.AUTOWRAP_OFF
	heading.max_lines_visible = 1
	heading.custom_minimum_size.y = 30
	info.autowrap_mode = TextServer.AUTOWRAP_OFF
	info.max_lines_visible = 2
	info.custom_minimum_size.y = 52 if "\n" in caption else 26
	var content: MarginContainer = button.get_child(0)
	content.minimum_size_changed.connect(_fit_button.bind(button, content, 108.0))
	_fit_button.call_deferred(button, content, 108.0)

func _select_system_scout() -> void:
	host._prepare_system_scout(browse_system)
	_add_required_ship()
	refresh()


func _select_destination(id: String) -> void:
	var record: Dictionary = Model.target(host.state, id)
	if record.is_empty() or id == host.selected_planet:
		return
	if id == host.selected_target and host.selected_scout_system.is_empty():
		# Browsing the map and keeping the same destination preserves the quote.
		host.compact_ui.close_details()
		refresh()
		return
	var was_unset: bool = host.selected_target.is_empty()
	host.selected_scout_system = ""
	host.selected_target = id
	host._sync_target()
	# Preserve a compatible chosen mission; otherwise suggest a safe one.
	var mission: int = int(host.mission_picker.selected)
	if not Model.mission_reason(host.state, record, mission, host._server_now()).is_empty():
		mission = Model.default_mission(host.state, record)
	elif was_unset and mission == 0:
		mission = Model.default_mission(host.state, record)
	host.mission_picker.select(mission)
	host._mission_changed(mission)
	_add_required_ship()
	host.compact_ui.close_details()
	host.tabs[2].scroll_vertical = 0
	refresh()

func dispatch_departure() -> void:
	# A single explicit activation sends exactly the quote currently on screen.
	# Committing a pending edit may invalidate it; that only starts a new quote.
	host._commit_fleet_inputs()
	refresh()
	if dispatch_busy or not _composer_active() or host.send_button.disabled or host.request_pending or not host.uncertain_action.is_empty() or not host.quote_ready or not Model.valid_quote(last_quote) or last_quote_fingerprint != host._fleet_fingerprint() or host.preview_requested_world_signature != host._quote_world_signature(host.state) or host.preview_requested_generation != host.fleet_draft_generation or not draft_reason().is_empty():
		return
	dispatch_busy = true
	auto_quote_timer.stop()
	host.send_button.disabled = true
	before_dispatch_ids.clear()
	for fleet: Dictionary in host.state.get("fleets", []):
		before_dispatch_ids.append(str(fleet.get("id", "")))
	host._send_fleet()
	refresh()

func dispatch_result(action: Dictionary, result: int, response_code: int, response: Variant) -> void:
	# Called after the existing action handler, using its pre-response action.
	# Network failure is an uncertain order, never a dispatched success. The
	# existing retry path reuses its request_id and remains the sole writer.
	if str(action.get("type", "")) != "fleet" or host.session_token.is_empty() or host.connection_editing or host.update_required:
		return
	dispatch_busy = false
	refresh()
	var confirmed: bool = result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300 and response is Dictionary and bool(response.get("ok", false))
	if not confirmed:
		if result != HTTPRequest.RESULT_SUCCESS or response_code >= 500 or not response is Dictionary or (response_code >= 200 and response_code < 300):
			host._notify(I18n.t("Wysłanie niepotwierdzone. Łączymy ponownie z tym samym rozkazem; nie wysyłaj drugiej floty."), true)
		return
	var fleet: Dictionary = Model.dispatched_fleet(action, response, before_dispatch_ids)
	receipt_fleet_id = str(fleet.get("id", ""))
	receipt_timeline = null
	host.compact_ui.close_details()
	host.compact_ui.close_composer()
	# Confirmed launch is an explicit navigation; apply its received snapshot once.
	if not host.deferred_state.is_empty():
		var next_state: Dictionary = host.deferred_state
		var received_at: int = host.deferred_state_received_at
		host.deferred_state = {}
		host._apply_state_now(next_state, received_at)
	var origin_id: String = str(action.get("planet_id", host.selected_planet))
	for system: Dictionary in host.state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			if str(planet.get("id", "")) == origin_id:
				host.selected_system = str(system.get("id", ""))
				host.selected_galaxy = str(system.get("galaxy_id", ""))
	host._open_tab(1)
	host._refresh_galaxy()
	host._show_full_galaxy_map(false)

func open_dispatched_mission() -> void:
	host.compact_ui.close_details()
	host.compact_ui.close_composer()
	host._open_tab(2)
	for fleet: Dictionary in host.state.get("fleets", []):
		if not receipt_fleet_id.is_empty() and str(fleet.get("id", "")) == receipt_fleet_id:
			host.compact_ui._open_fleet_details(fleet.duplicate(true))
			return

func _return_to_colony() -> void:
	host.compact_ui.close_details()
	host._open_tab(0)
