extends Control
## Chat uses its own requests: gameplay polling and fleet actions stay independent.

var host
var margin: MarginContainer
var entry_button: Button
var badge: Label
var alliance_button: Button
var global_button: Button
var private_button: Button
var player_picker
var conversation_title: Label
var block_button: Button
var history: ScrollContainer
var messages_box: VBoxContainer
var older_button: Button
var composer: VBoxContainer
var editor: TextEdit
var counter: Label
var send_button: Button
var status: Label
var report_dialog: ConfirmationDialog
var report_id: int = 0
var read_http: HTTPRequest
var action_http: HTTPRequest
var timer: Timer
var read_busy: bool = false
var action_busy: bool = false
var read_context: Dictionary = {}
var read_serial: int = 0
var action_context: Dictionary = {}
var peer_id: String = ""
var peer_name: String = ""
var inbox: bool = false
var available: bool = false
var can_send: bool = true
var blocked_by_you: bool = false
var previous_back: bool = true
var rows: Array[Dictionary] = []
var oldest_id: int = 0
var latest_id: int = 0
var read_ack: int = 0
var has_older: bool = false
var drafts: Dictionary = {}
var draft_ids: Dictionary = {}
var summary: Dictionary = {}
var player_signature: String = ""


func setup(client: Control) -> void:
	host = client
	name = "Communications"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	z_index = 120
	hide()
	var background: ColorRect = ColorRect.new()
	background.color = host._ui_color(Color("08110d"))
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)
	margin = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 22)
	add_child(margin)
	var layout: VBoxContainer = VBoxContainer.new()
	layout.add_theme_constant_override("separation", 10)
	margin.add_child(layout)
	var top: HBoxContainer = host._row(layout)
	var back: Button = host._button(I18n.t("Wstecz"), go_back)
	back.custom_minimum_size = Vector2(120, 60)
	back.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	top.add_child(back)
	top.add_child(host._label(I18n.t("Łączność"), 28))
	var channels: HBoxContainer = host._row(layout)
	global_button = host._button(I18n.t("Ogólny"), open_global)
	private_button = host._button(I18n.t("Prywatne"), open_inbox)
	alliance_button = host._button(I18n.t("Sojusz"), _open_alliance)
	for button: Button in [global_button, private_button, alliance_button]:
		button.custom_minimum_size.y = 62
		channels.add_child(button)
	player_picker = host._choice(I18n.t("Wybierz gracza"), 62)
	player_picker.item_selected.connect(_choose_player)
	layout.add_child(player_picker)
	var heading: HBoxContainer = host._row(layout)
	conversation_title = host._label("", 25)
	heading.add_child(conversation_title)
	block_button = host._button(I18n.t("Zablokuj"), _toggle_block)
	block_button.custom_minimum_size = Vector2(150, 54)
	block_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	block_button.add_theme_font_size_override("font_size", 20)
	heading.add_child(block_button)
	status = host._label("", 20, "ffc56f")
	status.hide()
	layout.add_child(status)
	history = host.TouchScrollScript.new()
	history.name = "CommunicationHistory"
	history.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	history.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(history)
	messages_box = VBoxContainer.new()
	messages_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	messages_box.add_theme_constant_override("separation", 12)
	history.add_child(messages_box)
	composer = VBoxContainer.new()
	composer.add_theme_constant_override("separation", 6)
	layout.add_child(composer)
	editor = TextEdit.new()
	editor.name = "MessageEditor"
	editor.custom_minimum_size.y = 106
	editor.placeholder_text = I18n.t("Napisz wiadomość…")
	editor.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	editor.add_theme_font_size_override("font_size", 23)
	editor.add_theme_stylebox_override("normal", host._style("0b1a12", "36533e", 12, 12))
	editor.add_theme_stylebox_override("focus", host._style("11291b", "91c89b", 12, 12))
	editor.add_theme_color_override("font_color", host._ui_color(Color("e7eee4")))
	editor.text_changed.connect(_draft_changed)
	editor.text_set.connect(_draft_changed)
	composer.add_child(editor)
	var send_row: HBoxContainer = host._row(composer)
	counter = host._label("0 / 500", 18, "a0b3a4")
	send_row.add_child(counter)
	send_button = host._button(I18n.t("Wyślij"), _send, true)
	send_button.custom_minimum_size = Vector2(150, 60)
	send_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	send_row.add_child(send_button)
	var note: Label = host._label(I18n.t("Szanuj innych graczy. Nie udostępniaj haseł ani danych osobowych."), 18, "a0b3a4")
	note.add_theme_font_size_override("font_size", 18)
	composer.add_child(note)
	report_dialog = ConfirmationDialog.new()
	report_dialog.title = I18n.t("Zgłoś wiadomość")
	report_dialog.dialog_text = I18n.t("Zgłosić tę wiadomość moderatorowi?")
	report_dialog.get_ok_button().text = I18n.t("Zgłoś")
	report_dialog.get_cancel_button().text = I18n.t("Anuluj")
	report_dialog.confirmed.connect(_report_confirmed)
	add_child(report_dialog)
	read_http = HTTPRequest.new()
	action_http = HTTPRequest.new()
	for request: HTTPRequest in [read_http, action_http]:
		request.use_threads = true
		request.timeout = 12.0
		request.max_redirects = 0
		request.body_size_limit = 262144
		add_child(request)
	read_http.request_completed.connect(_on_read)
	action_http.request_completed.connect(_on_action)
	timer = Timer.new()
	timer.wait_time = 3.0
	timer.timeout.connect(_poll_chat)
	add_child(timer)
	timer.start()
	entry_button = host._button("", open_global)
	entry_button.name = "CommunicationsButton"
	entry_button.tooltip_text = I18n.t("Łączność")
	entry_button.icon = host._texture("chat")
	entry_button.expand_icon = true
	entry_button.add_theme_constant_override("icon_max_width", 30)
	entry_button.custom_minimum_size = Vector2(64, 64)
	entry_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	var brand: HBoxContainer = host.planet_picker.get_parent()
	brand.add_child(entry_button)
	brand.move_child(entry_button, brand.get_child_count() - 2)
	badge = host._label("", 18, "ffc56f")
	badge.add_theme_font_size_override("font_size", 18)
	badge.autowrap_mode = TextServer.AUTOWRAP_OFF
	badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	badge.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	badge.position = Vector2(-44, 1)
	badge.size = Vector2(40, 24)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	entry_button.add_child(badge)
	badge.hide()


func sync_state() -> void:
	_update_summary(host.state.get("communications", {}))
	var players: Dictionary = {}
	var own_id: String = str(host.state.get("player", {}).get("id", ""))
	for system: Dictionary in host.state.get("galaxy", []):
		for planet: Dictionary in system.get("planets", []):
			var owner: String = str(planet.get("owner_id", ""))
			if str(planet.get("owner_type", "")) == "player" and owner != own_id:
				players[owner] = str(planet.get("owner_name", ""))
	var signature: String = JSON.stringify(players)
	if signature != player_signature:
		player_signature = signature
		player_picker.clear()
		player_picker.add_item(I18n.t("Nowa rozmowa…"))
		player_picker.set_item_metadata(0, "")
		var ids: Array = players.keys()
		ids.sort_custom(func(a, b) -> bool: return str(players[a]).naturalnocasecmp_to(str(players[b])) < 0)
		for id: String in ids:
			player_picker.add_item(players[id])
			player_picker.set_item_metadata(player_picker.item_count - 1, id)
		player_picker.select(0)
	if visible and (host.showing_login or host.update_required):
		close()


func _update_summary(value: Dictionary) -> void:
	summary = value
	available = bool(value.get("available", false))
	var unread: int = int(value.get("unread", 0))
	badge.text = "99+" if unread > 99 else str(unread)
	badge.visible = unread > 0
	global_button.text = I18n.t("Ogólny") + (" · %d" % int(value.get("global_unread", 0)) if int(value.get("global_unread", 0)) > 0 else "")
	private_button.text = I18n.t("Prywatne") + (" · %d" % int(value.get("private_unread", 0)) if int(value.get("private_unread", 0)) > 0 else "")


func _begin() -> bool:
	if host.update_required or host.showing_login or host.session_token.is_empty():
		return false
	if not visible:
		previous_back = get_tree().quit_on_go_back
		if host.compact_ui.details_open():
			previous_back = host.compact_ui.previous_back
			host.compact_ui.close_details()
		show()
		get_tree().quit_on_go_back = false
		host._sync_screen_visibility()
	return true


func _open_alliance() -> void:
	close()
	if host.alliance_ui != null:
		host.alliance_ui.open()


func open_global() -> void:
	_open_channel("", "")


func open_private(id: String, title: String) -> void:
	if id.is_empty() or id == str(host.state.get("player", {}).get("id", "")):
		return
	_open_channel(id, title)


func _save_draft() -> void:
	if visible and not inbox:
		drafts[peer_id] = editor.text


func _open_channel(id: String, title: String) -> void:
	_save_draft()
	if not _begin():
		return
	_cancel_read()
	inbox = false
	peer_id = id
	peer_name = title
	rows.clear()
	oldest_id = 0
	latest_id = 0
	read_ack = 0
	has_older = false
	can_send = available
	blocked_by_you = false
	player_picker.hide()
	composer.show()
	conversation_title.text = I18n.t("Czat ogólny") if id.is_empty() else title
	block_button.visible = not id.is_empty()
	editor.text = str(drafts.get(id, ""))
	_draft_changed()
	_set_status(I18n.t("Ładowanie rozmowy…"))
	_render_messages()
	_fetch()


func open_inbox() -> void:
	_save_draft()
	if not _begin():
		return
	_cancel_read()
	inbox = true
	player_picker.show()
	player_picker.select(0)
	composer.hide()
	block_button.hide()
	conversation_title.text = I18n.t("Rozmowy prywatne")
	host._clear(messages_box)
	_set_status(I18n.t("Ładowanie rozmowy…"))
	_fetch()


func _choose_player(index: int) -> void:
	if index <= 0:
		return
	open_private(str(player_picker.get_item_metadata(index)), player_picker.get_item_text(index))


func go_back() -> void:
	if report_dialog.visible:
		report_dialog.hide()
		return
	if player_picker.is_open():
		player_picker.close.call_deferred()
		return
	if OS.get_name() == "Android" and DisplayServer.virtual_keyboard_get_height() > 0:
		editor.release_focus()
		DisplayServer.virtual_keyboard_hide()
	elif not inbox and not peer_id.is_empty():
		open_inbox()
	else:
		close()


func close() -> void:
	if not visible:
		return
	_save_draft()
	player_picker.close()
	hide()
	report_dialog.hide()
	_cancel_read()
	editor.release_focus()
	DisplayServer.virtual_keyboard_hide()
	_restore_back.call_deferred()
	host._sync_screen_visibility()


func _restore_back() -> void:
	if not visible and not host.compact_ui.details_open() and not host.skill_open and not host.release_open:
		get_tree().quit_on_go_back = previous_back


func reset() -> void:
	close()
	_cancel_read()
	action_http.cancel_request()
	action_busy = false
	action_context.clear()
	drafts.clear()
	draft_ids.clear()
	rows.clear()
	peer_id = ""
	peer_name = ""
	editor.text = ""
	player_signature = ""
	host._clear(messages_box)
	_update_summary({})


func _headers() -> PackedStringArray:
	return PackedStringArray(["Content-Type: application/json", "Accept: application/json", "Accept-Language: " + I18n.locale,
		"X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE), "Authorization: Bearer " + str(host.session_token)])


func _cancel_read() -> void:
	read_http.cancel_request()
	read_busy = false
	read_context.clear()


func _fetch(before: int = 0) -> void:
	if not visible or read_busy or host.session_token.is_empty():
		return
	if not available:
		_set_status(I18n.t("Łączność będzie dostępna po aktualizacji serwera."))
		return
	var after: int = latest_id if before == 0 else 0
	var path: String = "/api/chat/inbox" if inbox else "/api/chat?peer_id=" + peer_id.uri_encode() + "&before=%d&after=%d" % [before, after]
	read_serial += 1
	read_context = {"serial": read_serial, "peer": peer_id, "inbox": inbox, "before": before, "after": after, "token": host.session_token, "server": host.server_url}
	read_busy = true
	if read_http.request(host.server_url + path, _headers(), HTTPClient.METHOD_GET) != OK:
		read_busy = false
		_set_status(I18n.t("Nie udało się odświeżyć rozmowy. Spróbujemy ponownie."))


func _poll_chat() -> void:
	if visible:
		_fetch()
		_mark_read()


func _on_read(result: int, code: int, _headers_value: PackedStringArray, body: PackedByteArray, expected: Dictionary = {}) -> void:
	var context: Dictionary = read_context.duplicate() if expected.is_empty() else expected
	if context != read_context:
		return
	if not visible or context.get("token") != host.session_token or context.get("server") != host.server_url:
		read_busy = false
		return
	if bool(context.get("inbox", false)) != inbox or str(context.get("peer", "")) != peer_id:
		read_busy = false
		return
	if host.has_method("_defer_ui_refresh") and host._defer_ui_refresh("chat:%d" % get_instance_id(),
		_on_read.bind(result, code, _headers_value, body, context)):
		return
	read_busy = false
	var data: Dictionary = _decode_json(body)
	if code == 426:
		close()
		host._handle_required_update(data)
		return
	if result != HTTPRequest.RESULT_SUCCESS or code != 200 or not data is Dictionary or not data.get("ok", false):
		_set_status(I18n.t("Nie udało się odświeżyć rozmowy. Spróbujemy ponownie."))
		return
	_update_summary(data.get("summary", {}))
	if inbox:
		_render_inbox(data.get("threads", []))
		_set_status("")
		return
	var permissions: Dictionary = data.get("permissions", {})
	can_send = bool(permissions.get("can_send", false))
	blocked_by_you = bool(permissions.get("blocked_by_you", false))
	block_button.text = I18n.t("Odblokuj") if blocked_by_you else I18n.t("Zablokuj")
	_draft_changed()
	if can_send:
		_set_status("")
	else:
		_set_status(I18n.t("Wysyłanie wiadomości jest obecnie zablokowane."))
	var stick_to_bottom: bool = latest_id == 0 or _at_bottom()
	var before: int = int(context.get("before", 0))
	var prior_scroll: int = history.scroll_vertical
	var prior_height: float = messages_box.size.y
	var new_rows: Array = data.get("messages", [])
	if before > 0 or int(context.get("after", 0)) == 0:
		has_older = bool(data.get("has_older", false))
	var known: Dictionary = {}
	for message: Dictionary in rows:
		known[int(message["id"])] = true
	for message: Dictionary in new_rows:
		var id: int = int(message.get("id", 0))
		if id > 0 and not known.has(id):
			rows.append(message)
			latest_id = maxi(latest_id, id)
			oldest_id = id if oldest_id == 0 else mini(oldest_id, id)
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["id"]) < int(b["id"]))
	if not new_rows.is_empty() or rows.is_empty():
		_render_messages()
		_restore_scroll.call_deferred(before > 0, stick_to_bottom, prior_scroll, prior_height, peer_id)


func _at_bottom() -> bool:
	var bar: VScrollBar = history.get_v_scroll_bar()
	return bar.value >= bar.max_value - bar.page - 32


func _restore_scroll(prepending: bool, bottom: bool, old_scroll: int, old_height: float, channel: String) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	if not visible or inbox or channel != peer_id:
		return
	if prepending:
		history.scroll_vertical = old_scroll + roundi(messages_box.size.y - old_height)
	elif bottom:
		history.scroll_vertical = int(history.get_v_scroll_bar().max_value)
		_mark_read()


func _render_messages() -> void:
	host._clear(messages_box)
	if has_older:
		older_button = host._button(I18n.t("Starsze wiadomości"), func() -> void: _fetch(oldest_id))
		older_button.custom_minimum_size.y = 54
		messages_box.add_child(older_button)
	if rows.is_empty():
		messages_box.add_child(host._label(I18n.t("Brak wiadomości. Rozpocznij rozmowę."), 22, "a0b3a4"))
	for message: Dictionary in rows:
		var card: VBoxContainer = host._card(messages_box)
		card.add_theme_constant_override("separation", 6)
		var heading: HBoxContainer = host._row(card)
		var own: bool = str(message.get("sender_id", "")) == str(host.state.get("player", {}).get("id", ""))
		var author: Button = host._button(str(message.get("sender_name", "")), open_private.bind(str(message.get("sender_id", "")), str(message.get("sender_name", ""))))
		author.custom_minimum_size.y = 48
		author.add_theme_font_size_override("font_size", 20)
		author.disabled = own
		heading.add_child(author)
		if not own:
			var report: Button = host._button(I18n.t("Zgłoś"), _ask_report.bind(int(message.get("id", 0))))
			report.custom_minimum_size = Vector2(112, 48)
			report.size_flags_horizontal = Control.SIZE_SHRINK_END
			report.add_theme_font_size_override("font_size", 18)
			heading.add_child(report)
		var timestamp: Label = host._label(host._date(float(message.get("at", 0))), 18, "a0b3a4")
		timestamp.add_theme_font_size_override("font_size", 18)
		card.add_child(timestamp)
		# Label is plain text. User messages are never translated or parsed as markup.
		card.add_child(host._label(str(message.get("text", "")), 23))


func _render_inbox(threads: Array) -> void:
	host._clear(messages_box)
	if threads.is_empty():
		messages_box.add_child(host._label(I18n.t("Wybierz gracza, aby rozpocząć prywatną rozmowę."), 22, "a0b3a4"))
	for thread: Dictionary in threads:
		var text: String = str(thread.get("name", ""))
		var unread: int = int(thread.get("unread", 0))
		if unread > 0:
			text += " · %d" % unread
		text += "\n" + str(thread.get("preview", ""))
		var button: Button = host._button(text, open_private.bind(str(thread.get("peer_id", "")), str(thread.get("name", ""))))
		button.custom_minimum_size.y = 106
		button.add_theme_font_size_override("font_size", 22)
		messages_box.add_child(button)


func _draft_changed() -> void:
	counter.text = "%d / 500" % editor.text.length()
	counter.add_theme_color_override("font_color", host._ui_color(Color("ff9287" if editor.text.length() > 500 else "a0b3a4")))
	send_button.disabled = action_busy or not available or not can_send or editor.text.strip_edges().is_empty() or editor.text.length() > 500
	block_button.disabled = action_busy or not available


func _send() -> void:
	if action_busy or not can_send or not available or inbox:
		return
	var text: String = editor.text.strip_edges()
	if text.is_empty() or text.length() > 500:
		return
	var previous: Dictionary = draft_ids.get(peer_id, {})
	var request_id: String = str(previous.get("id", "")) if str(previous.get("text", "")) == text else ""
	if request_id.is_empty():
		request_id = host._new_request_id()
	draft_ids[peer_id] = {"text": text, "id": request_id}
	_post("send", {"peer_id": peer_id, "text": text, "request_id": request_id})


func _post(kind: String, payload: Dictionary) -> void:
	if action_busy or host.session_token.is_empty() or host.update_required:
		return
	action_busy = true
	action_context = {"kind": kind, "payload": payload.duplicate(true), "token": host.session_token, "server": host.server_url}
	_draft_changed()
	if action_http.request(host.server_url + "/api/chat/" + kind, _headers(), HTTPClient.METHOD_POST, JSON.stringify(payload)) != OK:
		action_busy = false
		_set_status(I18n.t("Nie udało się potwierdzić operacji. Spróbuj ponownie."))
		_draft_changed()


func _on_action(result: int, code: int, _headers_value: PackedStringArray, body: PackedByteArray) -> void:
	action_busy = false
	var context: Dictionary = action_context
	if context.get("token") != host.session_token or context.get("server") != host.server_url:
		return
	var kind: String = str(context.get("kind", ""))
	var payload: Dictionary = context.get("payload", {})
	var data: Dictionary = _decode_json(body)
	if code == 426:
		close()
		host._handle_required_update(data)
		return
	if result != HTTPRequest.RESULT_SUCCESS or code != 200 or not data is Dictionary or not data.get("ok", false):
		_set_status(str(data.get("error", "")) if data is Dictionary and data.has("error") else I18n.t("Nie udało się potwierdzić operacji. Spróbuj ponownie."))
		_draft_changed()
		return
	if data.has("summary"):
		_update_summary(data["summary"])
	if kind == "send":
		var target: String = str(payload.get("peer_id", ""))
		if str(drafts.get(target, "")).strip_edges() == str(payload.get("text", "")):
			drafts.erase(target)
		draft_ids.erase(target)
		if not inbox and peer_id == target and editor.text.strip_edges() == str(payload.get("text", "")):
			editor.text = ""
		_set_status("")
	elif kind == "read" and str(payload.get("peer_id", "")) == peer_id:
		read_ack = maxi(read_ack, int(payload.get("last_id", 0)))
	elif kind == "block":
		if peer_id == str(payload.get("peer_id", "")) and not inbox:
			blocked_by_you = bool(payload.get("blocked", false))
			can_send = false if blocked_by_you else can_send
	elif kind == "report":
		_set_status(I18n.t("Wiadomość została zgłoszona."))
	_draft_changed()
	if visible and kind != "read" and kind != "report":
		_cancel_read()
		_fetch()


func _mark_read() -> void:
	if visible and not inbox and not action_busy and latest_id > read_ack and _at_bottom():
		_post("read", {"peer_id": peer_id, "last_id": latest_id})


func _toggle_block() -> void:
	if not peer_id.is_empty():
		_post("block", {"peer_id": peer_id, "blocked": not blocked_by_you})


func _ask_report(id: int) -> void:
	if action_busy:
		return
	report_id = id
	report_dialog.popup_centered(Vector2i(500, 220))


func _report_confirmed() -> void:
	_post("report", {"message_id": report_id})


func _set_status(text: String) -> void:
	status.text = text
	status.visible = not text.is_empty()


func _decode_json(body: PackedByteArray) -> Dictionary:
	var decoder: JSON = JSON.new()
	if decoder.parse(body.get_string_from_utf8()) == OK and decoder.data is Dictionary:
		return decoder.data
	return {}
