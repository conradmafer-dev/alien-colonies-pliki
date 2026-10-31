extends RefCounted
## Optional compact planet guide. All buttons navigate; they never issue orders.
const Model = preload("res://client/scripts/beginner_guide_model.gd")
var host
var storage_path: String = "user://beginner_guide.cfg"
var container: VBoxContainer
var card: PanelContainer
var heading: Button
var content: VBoxContainer
var title: Label
var description: Label
var project: Label
var status: Label
var action: Button
var parallel: Button
var dismiss_button: Button
var scope: String = ""
var memory: Dictionary = {}
var current: Dictionary = {}
var details_body: VBoxContainer
var details_signature: String = ""


func setup(client, parent: VBoxContainer) -> void:
	host = client
	container = VBoxContainer.new()
	container.name = "BeginnerGuide"
	container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	container.add_theme_constant_override("separation", 4)
	parent.add_child(container)
	parent.move_child(container, 0)
	card = PanelContainer.new()
	card.name = "NextStepCard"
	card.add_theme_stylebox_override("panel", host._style("17271e", "4d6848", 12, 1))
	container.add_child(card)
	var outer: VBoxContainer = VBoxContainer.new()
	outer.add_theme_constant_override("separation", 6)
	card.add_child(outer)
	heading = _button("", _toggle_collapsed)
	heading.name = "ToggleNextStep"
	heading.alignment = HORIZONTAL_ALIGNMENT_LEFT
	heading.custom_minimum_size.y = 56
	heading.autowrap_mode = TextServer.AUTOWRAP_OFF
	heading.clip_text = true
	heading.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	outer.add_child(heading)
	content = VBoxContainer.new()
	content.name = "NextStepContent"
	content.add_theme_constant_override("separation", 6)
	outer.add_child(content)
	title = _label(24, "d9efbb")
	title.name = "NextStepTitle"
	content.add_child(title)
	project = _label(21, "e8efdf")
	project.name = "NextStepProject"
	content.add_child(project)
	description = _label(21, "c5d4c8")
	description.name = "NextStepDescription"
	content.add_child(description)
	status = _label(21, "ebcf8a")
	status.name = "NextStepStatus"
	content.add_child(status)
	var action_row: HBoxContainer = HBoxContainer.new()
	action_row.add_theme_constant_override("separation", 8)
	content.add_child(action_row)
	action = _button("", _go.bind(false))
	action.name = "OpenNextStep"
	action_row.add_child(action)
	parallel = _button("", _go.bind(true))
	parallel.name = "NextStepParallel"
	content.add_child(parallel)
	dismiss_button = _button("", dismiss)
	dismiss_button.name = "DismissNextStep"
	dismiss_button.custom_minimum_size = Vector2(172, 56)
	dismiss_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	dismiss_button.flat = true
	action_row.add_child(dismiss_button)
	refresh()


func _button(text: String, callback: Callable) -> Button:
	var button: Button = host._button(text, callback)
	button.custom_minimum_size = Vector2(0, 56)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.add_theme_font_size_override("font_size", 22)
	button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return button


func _label(font_size: int, color: String) -> Label:
	var label: Label = host._label("", font_size, color)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label


static func account_scope(server: String, player_id: String) -> String:
	if server.strip_edges().is_empty() or player_id.is_empty():
		return ""
	# Store no URLs, account names, IDs, login tokens or passwords in this file.
	return (server.strip_edges().trim_suffix("/").to_lower() + "\n" + player_id).sha256_text()


func reset_account() -> void:
	# Call at logout before a new server/player state arrives.
	scope = ""
	memory = {}
	current = {}
	if is_instance_valid(container):
		container.hide()


func _load_scope(next_scope: String) -> void:
	scope = next_scope
	memory = {"dismissed": false, "collapsed": false, "finished": false, "production_done": false}
	if scope.is_empty():
		return
	var settings: ConfigFile = ConfigFile.new()
	if settings.load(storage_path) == OK and settings.has_section(scope):
		for key: String in memory.keys():
			memory[key] = bool(settings.get_value(scope, key, false))
	elif bool(host.state.get("onboarding", {}).get("skipped", false)):
		# Respect an existing server-side choice without mutating that system.
		memory["dismissed"] = true
	if not settings.has_section(scope):
		# Existing read history can identify a returning player on first use.
		# After this initial snapshot, opening the Reports tab alone is not
		# evidence of reading a scout report: only mark_report_opened completes it.
		for report: Dictionary in host.state.get("reports", []):
			if Model.scout_report(report) and host.report_read_ids.has(host._report_identity(report)):
				memory["finished"] = true
		_save()


func _save() -> void:
	if scope.is_empty():
		return
	var settings: ConfigFile = ConfigFile.new()
	settings.load(storage_path)
	for key: String in ["dismissed", "collapsed", "finished", "production_done"]:
		settings.set_value(scope, key, bool(memory.get(key, false)))
	var error: Error = settings.save(storage_path)
	if error != OK:
		push_warning("Could not save local beginner guide preferences: " + str(error))


func refresh() -> void:
	if not is_instance_valid(container):
		return
	var next_scope: String = account_scope(str(host.server_url), str(host.state.get("player", {}).get("id", "")))
	if next_scope != scope:
		_load_scope(next_scope)
	if scope.is_empty() or host.state.is_empty():
		container.hide()
		current = {}
		return
	var previous: Dictionary = memory.duplicate()
	current = Model.evaluate(host.state, memory)
	if bool(current.get("production_done", false)):
		memory["production_done"] = true
	if bool(current.get("finished", false)):
		memory["finished"] = true
	if memory != previous:
		_save()
	# Cancelled hints leave no launcher or resume row, including preferences
	# saved by versions that used to show a separate Resume hints button.
	container.visible = not current.is_empty() and not bool(memory.get("finished", false)) and not bool(memory.get("dismissed", false))
	if not container.visible:
		if _details_open():
			host.compact_ui.close_details()
		return
	# Detailed help lives in the shared sheet, leaving one compact entry here.
	content.hide()
	heading.text = I18n.t("Następny krok") + " · " + I18n.t(str(current.get("title", ""))) + " ›"
	heading.tooltip_text = I18n.t("Rozwiń wskazówkę")
	dismiss_button.text = I18n.t("Wyłącz wskazówki")
	title.text = I18n.t(str(current.get("title", "")))
	description.text = I18n.t(str(current.get("description", "")))
	project.text = str(current.get("name", ""))
	project.visible = not project.text.is_empty()
	var reason: String = str(current.get("reason", ""))
	status.text = host._server_text(reason) if not reason.is_empty() else ""
	if bool(current.get("queued", false)):
		status.text = I18n.t("Projekt jest już w kolejce. Nie musisz dodawać go ponownie.") if bool(current.get("planned", false)) else I18n.t("Projekt trwa. Możesz zająć się kolejnym zadaniem.")
	elif bool(current.get("waiting", false)) and str(current.get("lane", "")) != "flight":
		status.text = I18n.t("Ta kolejka jest zajęta. W tym czasie możesz wykonać inne zadanie.")
	status.visible = not status.text.is_empty()
	action.text = I18n.t(str(current.get("button", "Pokaż projekt")))
	action.disabled = str(current.get("action", "")).is_empty()
	var suggestion: Dictionary = current.get("parallel", {})
	parallel.visible = not suggestion.is_empty()
	parallel.text = I18n.t(str(suggestion.get("button", "")))
	_refresh_details()


func mark_report_opened(report: Dictionary) -> void:
	refresh()
	if scope.is_empty() or not Model.scout_report(report):
		return
	var identity: String = host._report_identity(report)
	# Confirm the opened report still belongs to the current account's state.
	for current_report: Dictionary in host.state.get("reports", []):
		if Model.scout_report(current_report) and host._report_identity(current_report) == identity:
			memory["finished"] = true
			_save()
			refresh()
			return


func dismiss() -> void:
	refresh()
	if scope.is_empty():
		return
	memory["dismissed"] = true
	_save()
	if _details_open():
		host.compact_ui.close_details()
	refresh()


func _toggle_collapsed() -> void:
	_open_details()


func _details_open() -> bool:
	return is_instance_valid(details_body) and details_body.is_visible_in_tree() and host.compact_ui.details_open()


func _open_details() -> void:
	refresh()
	if scope.is_empty() or current.is_empty() or bool(memory.get("finished", false)) or bool(memory.get("dismissed", false)) or host.update_required:
		return
	host.compact_ui._begin_details(I18n.t("Następny krok"), true)
	details_body = VBoxContainer.new()
	details_body.name = "NextStepDetails"
	details_body.add_theme_constant_override("separation", 16)
	host.compact_ui.modal_body.add_child(details_body)
	details_signature = ""
	_refresh_details()


func _refresh_details() -> void:
	if not _details_open():
		return
	var signature: String = JSON.stringify([scope, current, I18n.locale])
	if signature == details_signature:
		return
	details_signature = signature
	var scroll_y: int = host.compact_ui.modal_scroll.scroll_vertical
	host._clear(details_body)
	for source: Label in [title, project, description, status]:
		if not source.text.is_empty() and source.visible:
			details_body.add_child(host._label(source.text, 24 if source == title else 22))
	var go: Button = _button(action.text, _go.bind(false))
	go.name = "OpenNextStepDetails"
	go.disabled = action.disabled
	details_body.add_child(go)
	if parallel.visible:
		var next: Button = _button(parallel.text, _go.bind(true))
		next.name = "NextStepParallelDetails"
		details_body.add_child(next)
	var cancel: Button = _button(I18n.t("Wyłącz wskazówki"), dismiss)
	cancel.name = "CancelNextStepDetails"
	details_body.add_child(cancel)
	host.compact_ui._restore_details_scroll(scroll_y)


func _go(use_parallel: bool) -> void:
	# Recheck account/state at click time so a stale card cannot navigate another
	# account's object after logout, reconnection, or a selected-colony change.
	var shown_scope: String = scope
	refresh()
	if scope != shown_scope or current.is_empty() or bool(memory.get("finished", false)) or bool(memory.get("dismissed", false)):
		return
	var destination: Dictionary = current.get("parallel", {}) if use_parallel else current
	if not str(destination.get("action", "")).is_empty():
		host._guide_target(str(destination.action), str(destination.get("key", "")))
		refresh()
