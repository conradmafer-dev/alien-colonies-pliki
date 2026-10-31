extends RefCounted
## The panorama stays open; protection is communicated by reports and planet
## badges. This strip contains only the colony's live energy/production state.

const PlayerActivity = preload("res://client/scripts/player_activity.gd")
var host
var energy_summary: Label
var production_summary: Label
var queues_panel: Control
var queue_buttons: Dictionary = {}
var status_panel: Control


func setup(client) -> void:
	host = client
	var parent: VBoxContainer = host.tab_bodies[0]
	parent.size_flags_vertical = Control.SIZE_EXPAND_FILL
	host.tabs[0].vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	host.colony_panorama.custom_minimum_size.y = 200
	host.colony_panorama.show()
	# Backing labels remain alive for integrations; the legacy panel is hidden.
	var original: Node = host.energy_label
	while original != null and not original is PanelContainer:
		original = original.get_parent()
	if original is Control:
		original.hide()
	var body: VBoxContainer = host._card(parent)
	status_panel = body.get_parent()
	status_panel.name = "ColonyStatus"
	parent.move_child(status_panel, host.colony_panorama.get_index() + 1)
	energy_summary = host._label("", 22, "ffc56f")
	energy_summary.name = "EnergyProductionSummary"
	body.add_child(energy_summary)
	production_summary = host._label("", 21, "ff9287")
	production_summary.name = "ProductionActivitySummary"
	body.add_child(production_summary)
	var queues: VBoxContainer = host._card(parent)
	queues_panel = queues.get_parent()
	queues_panel.name = "ParallelProjectSummary"
	parent.move_child(queues_panel, status_panel.get_index() + 1)
	var queue_links: HBoxContainer = host._row(queues)
	for lane: String in ["ship", "research"]:
		var button: Button = host._button("", _open_queue.bind(lane))
		button.custom_minimum_size.y = 48
		button.add_theme_font_size_override("font_size", 20)
		button.autowrap_mode = TextServer.AUTOWRAP_OFF
		button.clip_text = true
		button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		queue_links.add_child(button)
		queue_buttons[lane] = button
	refresh()


func refresh() -> void:
	host.colony_panorama.show()
	var energy: Dictionary = host.state.get("energy", {})
	var factor: float = clampf(float(energy.get("factor", 1.0)), 0.0, 1.0)
	var paused: bool = PlayerActivity.production_paused(host.state)
	energy_summary.text = I18n.t("Energia %s / %s · Wydobycie %d%%") % [host._stat_number(float(energy.get("used", 0))), host._stat_number(float(energy.get("supply", 0))), 0 if paused else roundi(factor * 100.0)]
	energy_summary.add_theme_color_override("font_color", host._ui_color(Color("ff9287" if factor < 1.0 else "ffc56f")))
	energy_summary.tooltip_text = I18n.t("Pierwsza liczba to zużycie, druga to dostępna energia. Niedobór energii ogranicza wydobycie; rozbuduj źródło energii, aby je przywrócić.")
	production_summary.visible = paused
	production_summary.text = I18n.t("Produkcja wstrzymana — nieaktywność")
	production_summary.tooltip_text = I18n.t("Po 7 dniach bez aktywności produkcja metalu, kryształów i paliwa we wszystkich koloniach spada do zera. Wznawia się po Twoim powrocie, bez wyrównania za okres przerwy. Kolonie, floty i zgromadzone zasoby pozostają w grze; nadal mogą być atakowane.")
	tick()


func tick() -> void:
	if host.state.is_empty():
		queues_panel.hide()
		return
	var active: bool = false
	for lane: String in queue_buttons:
		var task: Dictionary = host.project_ui.task_for(lane) if host.project_ui != null else {}
		var button: Button = queue_buttons[lane]
		button.visible = not task.is_empty()
		if task.is_empty():
			continue
		active = true
		var caption: String = I18n.t("Stocznia") if lane == "ship" else I18n.t("Badania")
		var time: float = float(task.get("ends_at", 0)) - host._server_now()
		button.text = "%s · %s ›" % [caption, host._duration(time) if time > 0 else I18n.t("Kończenie…")]
		button.tooltip_text = host.project_ui.task_name(task)
	queues_panel.visible = active


func _open_queue(lane: String) -> void:
	var task: Dictionary = host.project_ui.task_for(lane)
	if task.is_empty():
		return
	host._guide_target("research" if lane == "research" else "ship", str(task.get("key", "")))
