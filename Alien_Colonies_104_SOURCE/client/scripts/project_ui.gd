extends RefCounted
## Independent local construction/shipyard and empire-wide research timers.
var host
var panels: Dictionary = {}

func setup(client) -> void:
	host = client
	# Move the former global timer beside the colony's building list.
	host.active_project.reparent(host.tab_bodies[0])
	host.tab_bodies[0].move_child(host.active_project, host.building_heading.get_index())
	panels["build"] = {"panel": host.active_project, "title": host.active_project_title,
		"time": host.active_project_time, "bar": host.active_project_bar, "cancel": host.cancel_project_button}
	_make_panel("ship", host.fleet_build_view, 1)
	_make_panel("research", host.tab_bodies[3], 0)

func _make_panel(lane: String, parent: VBoxContainer, index: int) -> void:
	var body: VBoxContainer = host._card(parent)
	var panel: Control = body.get_parent()
	panel.name = "ActiveProject_" + lane
	panel.hide()
	parent.move_child(panel, index)
	var row: HBoxContainer = host._row(body)
	row.add_child(host._icon("time", 24))
	var title: Label = host._label("", 22)
	title.autowrap_mode = TextServer.AUTOWRAP_OFF
	title.clip_text = true
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(title)
	var time: Label = host._token_label("", 22)
	row.add_child(time)
	var cancel: Button = host._button(I18n.t("Anuluj"), _cancel.bind(lane))
	cancel.custom_minimum_size = Vector2(110, 52)
	cancel.size_flags_horizontal = Control.SIZE_SHRINK_END
	cancel.add_theme_font_size_override("font_size", 20)
	row.add_child(cancel)
	var bar: ProgressBar = host._meter("91c89b")
	bar.custom_minimum_size.y = 14
	body.add_child(bar)
	panels[lane] = {"panel": panel, "title": title, "time": time, "bar": bar, "cancel": cancel}

func _cancel(lane: String) -> void:
	var task: Dictionary = task_for(lane)
	if not task.is_empty(): host._ask_cancel_project(str(task.get("id", "")))

func task_for(lane: String) -> Dictionary:
	if lane == "research" and host.state.get("research_queue") is Dictionary:
		return host.state["research_queue"]
	for task: Dictionary in host.state.get("queue", []):
		var kind: String = str(task.get("kind", ""))
		if kind == lane or (lane == "ship" and kind == "defense"):
			return task
	return {}

func find_task(id: String) -> Dictionary:
	for lane: String in ["build", "ship", "research"]:
		var task: Dictionary = task_for(lane)
		if not task.is_empty() and str(task.get("id", "")) == id: return task
	return {}

func task_name(task: Dictionary) -> String:
	var kind: String = str(task.get("kind", ""))
	var group: String = str({"build": "buildings", "ship": "ships", "defense": "defenses", "research": "research"}.get(kind, ""))
	var result: String = host._server_text(task.get("name", host._catalog_name(str(task.get("key", "")), group)))
	result += " ×%d" % int(task.get("amount", 1)) if kind in ["ship", "defense"] else I18n.t(" · poz. %d") % int(task.get("level", 1))
	if str(task.get("planet_id", host.selected_planet)) != host.selected_planet:
		result += " · " + str(task.get("planet_name", ""))
	return result

func duration(task: Dictionary) -> float:
	var seconds: float = float(task.get("seconds", 0))
	if seconds <= 0 and task.has("started_at"):
		seconds = maxf(0.0, float(task.get("ends_at", 0)) - float(task["started_at"]))
	return seconds

func progress(task: Dictionary) -> float:
	return clampf(100.0 * (1.0 - maxf(0.0, float(task.get("ends_at", 0)) - host._server_now()) / maxf(1.0, duration(task))), 0.0, 100.0)

func tick() -> void:
	var now: float = host._server_now()
	for lane: String in panels:
		var controls: Dictionary = panels[lane]
		var task: Dictionary = task_for(lane)
		controls["panel"].visible = not task.is_empty()
		if task.is_empty(): continue
		var remaining: float = float(task.get("ends_at", 0)) - now
		controls["title"].text = task_name(task)
		controls["title"].tooltip_text = task_name(task)
		controls["time"].text = host._duration(remaining) if remaining > 0 else I18n.t("Kończenie…")
		controls["bar"].visible = duration(task) > 0
		controls["bar"].value = progress(task)
		controls["cancel"].disabled = remaining <= 0 or host.request_pending or not host.uncertain_action.is_empty() or host.update_required
	for rows: Dictionary in [host.building_rows, host.ship_rows, host.defense_rows, host.research_rows]:
		for key: String in rows:
			var controls: Dictionary = rows[key]
			var kind: String = str(controls["kind"])
			var task: Dictionary = task_for("ship" if kind == "defense" else kind)
			var active: bool = str(task.get("kind", "")) == kind and str(task.get("key", "")) == key
			controls["progress_panel"].visible = active
			if not active: continue
			var remaining: float = float(task.get("ends_at", 0)) - now
			controls["progress_bar"].visible = duration(task) > 0
			controls["progress_bar"].value = progress(task)
			controls["progress_label"].text = I18n.t("W toku · %d%% · pozostało %s") % [floori(progress(task)), host._duration(remaining)] if remaining > 0 else I18n.t("Kończenie projektu…")
