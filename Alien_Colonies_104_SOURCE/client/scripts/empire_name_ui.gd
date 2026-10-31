extends Node
## Empire identity is owned by the authenticated server account, never a new ID.
var host
var dialog: ConfirmationDialog
var field: LineEdit
var message: Label
var request: HTTPRequest
var busy: bool = false
var generation: int = 0


func setup(client) -> void:
	host = client
	name = "EmpireNameSettings"
	var button: Button = host._button(I18n.t("Zmień nazwę imperium"), open)
	button.name = "RenameEmpireButton"
	host.options_panel.add_child(button)
	dialog = ConfirmationDialog.new()
	dialog.name = "RenameEmpireDialog"
	dialog.title = I18n.t("Zmień nazwę imperium")
	dialog.dialog_hide_on_ok = false
	dialog.get_ok_button().text = I18n.t("Zapisz")
	dialog.get_cancel_button().text = I18n.t("Wstecz")
	dialog.confirmed.connect(_save)
	add_child(dialog)
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 16)
	dialog.add_child(stack)
	stack.add_child(host._label(I18n.t("Nowa nazwa imperium"), 24))
	field = LineEdit.new()
	field.name = "NewEmpireName"
	field.max_length = 20
	field.custom_minimum_size = Vector2(0, 64)
	field.add_theme_font_size_override("font_size", 24)
	field.text_submitted.connect(func(_text: String) -> void: _save())
	stack.add_child(field)
	message = host._label(I18n.t("3–20 znaków"), 21)
	stack.add_child(message)
	stack.add_child(host._label(I18n.t("Po zmianie nazwy używaj jej przy logowaniu hasłem."), 21))
	dialog.visibility_changed.connect(func() -> void:
		if not dialog.visible:
			DisplayServer.virtual_keyboard_hide())


func open() -> void:
	if host.showing_login or host.session_token.is_empty() or host.update_required:
		return
	field.text = str(host.state.get("player", {}).get("name", ""))
	message.text = I18n.t("3–20 znaków")
	_set_busy(busy)
	dialog.popup_centered_clamped(Vector2i(570, 330), 0.9)
	field.grab_focus.call_deferred()
	field.select_all.call_deferred()


func _set_busy(value: bool) -> void:
	busy = value
	field.editable = not value
	dialog.get_ok_button().disabled = value


func _save() -> void:
	if busy or host.request_pending or host.update_required or host.session_token.is_empty():
		return
	var empire_name: String = field.text.strip_edges()
	if empire_name.length() < 3 or empire_name.length() > 20:
		message.text = I18n.t("3–20 znaków")
		return
	generation += 1
	_set_busy(true)
	message.text = I18n.t("Łączenie…")
	if is_instance_valid(request):
		request.cancel_request()
		request.queue_free()
	request = HTTPRequest.new()
	request.timeout = 20
	request.max_redirects = 0
	request.body_size_limit = 4194304
	add_child(request)
	request.request_completed.connect(_received.bind(generation, str(host.session_token), str(host.server_url)))
	var headers := PackedStringArray(["Content-Type: application/json", "Accept: application/json",
		"Accept-Language: " + I18n.locale, "X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE),
		"Authorization: Bearer " + str(host.session_token)])
	var body: String = JSON.stringify({"name": empire_name, "planet_id": host.selected_planet})
	if request.request(str(host.server_url) + "/api/account/rename", headers, HTTPClient.METHOD_POST, body) != OK:
		_set_busy(false)
		message.text = I18n.t("Nie udało się potwierdzić zmiany. Odśwież grę, aby sprawdzić nazwę imperium.")


func _received(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, serial: int, token: String, origin: String) -> void:
	if serial != generation:
		return
	_set_busy(false)
	if is_instance_valid(request):
		request.queue_free()
	request = null
	if token != host.session_token or origin != host.server_url or host.showing_login:
		dialog.hide()
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if code == 426 and parsed is Dictionary:
		dialog.hide()
		host._handle_required_update(parsed.get("update"))
		return
	if result != HTTPRequest.RESULT_SUCCESS or code != 200 or not parsed is Dictionary or not bool(parsed.get("ok", false)) or not parsed.get("state") is Dictionary:
		message.text = host._server_text(parsed.get("error", "")) if parsed is Dictionary else ""
		if message.text.is_empty():
			message.text = I18n.t("Nie udało się potwierdzić zmiany. Odśwież grę, aby sprawdzić nazwę imperium.")
		return
	# Discard any in-flight snapshot captured before the rename.
	host._cancel_state_request()
	host.name_field.text = str(parsed["state"].get("player", {}).get("name", empire_name_from(parsed)))
	host._save_session()
	host._apply_state(parsed["state"])
	if host.ranking_ui != null:
		host.ranking_ui.snapshot.clear()
	dialog.hide()
	host._notify(I18n.t("Zmieniono nazwę imperium."))


func empire_name_from(response: Dictionary) -> String:
	return str(response.get("name", field.text.strip_edges()))
