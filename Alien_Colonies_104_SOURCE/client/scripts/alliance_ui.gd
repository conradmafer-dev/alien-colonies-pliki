extends Control
## Alliance operations use isolated HTTP requests. Polling never replaces a form.
const QuantityScript = preload("res://client/scripts/mobile_quantity.gd")
const ResourceInfo = preload("res://client/scripts/resource_info.gd")

var host
var margin: MarginContainer
var timer: Timer
var status: Label
var retry_button: Button
var title: Label
var body: VBoxContainer
var scroll: ScrollContainer
var tabs: Array[Button] = []
var composer: VBoxContainer
var editor: TextEdit
var chat_send: Button
var chat_counter: Label
var member_http: HTTPRequest
var operation_http: HTTPRequest
var action_http: HTTPRequest
var member_busy: bool = false
var operation_busy: bool = false
var action_busy: bool = false
var data: Dictionary = {}
var operations: Dictionary = {}
var contexts: Dictionary = {}
var read_serial: int = 0
var request_ids: Dictionary = {}
var retry_context: Dictionary = {}
var tab: int = 0
var form: String = ""
var form_context: Dictionary = {}
var fields: Dictionary = {}
var quantities: Dictionary = {}
var pickers: Array = []
var previous_back: bool = true
var render_signature: String = ""
var launch_target: Dictionary = {}
var selected_origin: String = ""
var session_identity: String = ""
var directory_search: HBoxContainer
var search_field: LineEdit
var directory_filter: String = ""
var chat_draft: String = ""
var countdowns: Dictionary = {}

func setup(client: Control) -> void:
	host = client
	name = "AllianceUI"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	z_index = 125
	hide()
	var backdrop: ColorRect = ColorRect.new()
	backdrop.color = host._ui_color(Color("08110d"))
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)
	margin = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 20)
	add_child(margin)
	var layout: VBoxContainer = VBoxContainer.new()
	layout.add_theme_constant_override("separation", 10)
	margin.add_child(layout)
	var heading: HBoxContainer = host._row(layout)
	var back: Button = _button(heading, I18n.t("Wstecz"), go_back)
	back.custom_minimum_size.x = 120
	back.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	title = host._label(I18n.t("Sojusze"), 28)
	heading.add_child(title)
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	layout.add_child(grid)
	for i: int in range(4):
		var captions: Array[String] = [I18n.t("Sojusz"), I18n.t("Członkowie"), I18n.t("Operacje"), I18n.t("Czat sojuszu")]
		var button: Button = _button(grid, captions[i], _select_tab.bind(i))
		button.name = "AllianceTab%d" % i
		tabs.append(button)
	directory_search = host._row(layout)
	search_field = LineEdit.new()
	search_field.name = "AllianceSearch"
	search_field.placeholder_text = I18n.t("Szukaj sojuszu")
	search_field.custom_minimum_size.y = 60
	search_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	search_field.max_length = 64
	search_field.add_theme_font_size_override("font_size", 23)
	search_field.text_submitted.connect(func(_value: String) -> void: _search())
	directory_search.add_child(search_field)
	var search_button: Button = _button(directory_search, I18n.t("Szukaj"), _search)
	search_button.custom_minimum_size.x = 140
	search_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	directory_search.hide()
	var notice: PanelContainer = PanelContainer.new()
	notice.name = "AllianceStatusPanel"
	notice.add_theme_stylebox_override("panel", host._style("241816", "d77965", 12, 12))
	layout.add_child(notice)
	var notice_rows: VBoxContainer = VBoxContainer.new()
	notice.add_child(notice_rows)
	status = host._label("", 22, "ffd0bf")
	status.name = "AllianceStatus"
	notice_rows.add_child(status)
	retry_button = _button(notice_rows, I18n.t("Spróbuj ponownie"), _retry)
	retry_button.hide()
	notice.hide()
	scroll = host.TouchScrollScript.new()
	scroll.name = "AllianceScroll"
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(scroll)
	body = VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 12)
	scroll.add_child(body)
	composer = VBoxContainer.new()
	layout.add_child(composer)
	editor = TextEdit.new()
	editor.name = "AllianceChatEditor"
	editor.custom_minimum_size.y = 100
	editor.placeholder_text = I18n.t("Wiadomość dla sojuszu…")
	editor.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	editor.add_theme_font_size_override("font_size", 23)
	editor.add_theme_stylebox_override("normal", host._style("0b1a12", "36533e", 12, 12))
	editor.add_theme_stylebox_override("focus", host._style("11291b", "91c89b", 12, 12))
	editor.text_changed.connect(_chat_changed)
	composer.add_child(editor)
	var chat_row: HBoxContainer = host._row(composer)
	chat_counter = host._label("0 / 500", 20, "a0b3a4")
	chat_row.add_child(chat_counter)
	chat_send = _button(chat_row, I18n.t("Wyślij"), _send_chat, true)
	chat_send.custom_minimum_size.x = 160
	chat_send.size_flags_horizontal = Control.SIZE_SHRINK_END
	composer.hide()
	member_http = _request_node(_member_received)
	operation_http = _request_node(_operations_received)
	action_http = _request_node(_action_received)
	timer = Timer.new()
	timer.wait_time = 5
	timer.timeout.connect(_poll)
	add_child(timer)
	timer.start()

func _request_node(callback: Callable) -> HTTPRequest:
	var request: HTTPRequest = HTTPRequest.new()
	request.use_threads = true
	request.timeout = 15
	request.max_redirects = 0
	request.body_size_limit = 1024 * 1024
	request.request_completed.connect(callback)
	add_child(request)
	return request

func _button(parent: Node, caption: String, callback: Callable, primary: bool = false) -> Button:
	var button: Button = host._button(caption, func() -> void:
		if not action_busy: callback.call()
	, primary)
	button.custom_minimum_size.y = 60
	button.add_theme_font_size_override("font_size", 22)
	parent.add_child(button)
	return button

func _text(parent: Node, text: String, color: String = "e7eee4", font_size: int = 22) -> Label:
	var label: Label = host._label(text, font_size, color)
	parent.add_child(label)
	return label

func _card() -> VBoxContainer:
	var card: VBoxContainer = host._card(body)
	card.add_theme_constant_override("separation", 10)
	return card

func _two(parent: Node) -> GridContainer:
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	parent.add_child(grid)
	return grid

func _line(parent: Node, key: String, caption: String, value: String = "", limit: int = 80) -> LineEdit:
	_text(parent, caption, "a0b3a4")
	var field: LineEdit = LineEdit.new()
	field.name = "AllianceField_" + key
	field.text = value
	field.max_length = limit
	field.custom_minimum_size.y = 62
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.add_theme_font_size_override("font_size", 23)
	parent.add_child(field)
	fields[key] = field
	return field

func _editor(parent: Node, key: String, caption: String, value: String = "") -> TextEdit:
	_text(parent, caption, "a0b3a4")
	var field: TextEdit = TextEdit.new()
	field.name = "AllianceField_" + key
	field.text = value
	field.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	field.custom_minimum_size.y = 120
	field.add_theme_font_size_override("font_size", 23)
	parent.add_child(field)
	fields[key] = field
	return field

func _choice(parent: Node, caption: String):
	_text(parent, caption, "a0b3a4")
	var choice = host._choice(caption, 64)
	parent.add_child(choice)
	pickers.append(choice)
	return choice

func open() -> void:
	if host.showing_login or host.update_required or str(host.session_token).is_empty(): return
	if not visible:
		previous_back = get_tree().quit_on_go_back
		if host.communications.visible:
			previous_back = host.communications.previous_back
			host.communications.close()
		if host.compact_ui.details_open():
			previous_back = host.compact_ui.previous_back
			host.compact_ui.close_details()
		show()
		get_tree().quit_on_go_back = false
		host._sync_screen_visibility()
	session_identity = str(host.server_url) + "|" + str(host.session_token)
	_render(true)
	_fetch_members()

func open_target(planet: Dictionary) -> void:
	launch_target = planet.duplicate(true)
	tab = 2
	form = ""
	open()

func close() -> void:
	if not visible: return
	chat_draft = editor.text
	for picker in pickers:
		if is_instance_valid(picker): picker.close()
	hide()
	editor.release_focus()
	if OS.get_name() == "Android": DisplayServer.virtual_keyboard_hide()
	member_http.cancel_request(); member_busy = false
	operation_http.cancel_request(); operation_busy = false
	form = ""
	form_context.clear()
	launch_target.clear()
	host._sync_screen_visibility()
	_restore_back.call_deferred()

func _restore_back() -> void:
	if not visible and not host.compact_ui.details_open() and not host.communications.visible and not host.skill_open and not host.release_open:
		get_tree().quit_on_go_back = previous_back

func go_back() -> void:
	for picker in pickers:
		if is_instance_valid(picker) and picker.is_open():
			picker.close.call_deferred()
			return
	if OS.get_name() == "Android" and DisplayServer.virtual_keyboard_get_height() > 0:
		get_viewport().gui_release_focus()
		DisplayServer.virtual_keyboard_hide()
	elif not form.is_empty():
		if action_busy: return
		if form == "preview" and form_context.has("draft"):
			_restore_fleet_draft(form_context["draft"].duplicate(true))
			return
		form = ""; form_context.clear(); _render(true)
	else: close()

func reset() -> void:
	close()
	action_http.cancel_request(); action_busy = false
	data.clear(); operations.clear(); contexts.clear(); request_ids.clear(); retry_context.clear()
	fields.clear(); quantities.clear(); selected_origin = ""; session_identity = ""
	editor.text = ""; chat_draft = ""; render_signature = ""
	directory_filter = ""; search_field.text = ""
	_set_status("")

func sync_state() -> void:
	if visible and (host.showing_login or host.update_required): close()
	if not session_identity.is_empty() and session_identity != str(host.server_url) + "|" + str(host.session_token): reset()

func _headers() -> PackedStringArray:
	return PackedStringArray(["Content-Type: application/json", "Accept: application/json", "Accept-Language: " + I18n.locale,
		"X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE), "Authorization: Bearer " + str(host.session_token)])

func _identity() -> Dictionary:
	return {"token": str(host.session_token), "server": str(host.server_url)}

func _current(context: Dictionary) -> bool:
	return str(context.get("token", "")) == str(host.session_token) and str(context.get("server", "")) == str(host.server_url)

func _poll() -> void:
	if not visible: return
	for label in countdowns:
		if is_instance_valid(label): label.text = I18n.t("Do uderzenia: %s") % host._duration(maxf(0, float(countdowns[label]) - host._server_now()))
	_fetch_members()
	if tab == 2: _fetch_operations()

func _search() -> void:
	directory_filter = search_field.text.strip_edges()
	member_http.cancel_request(); member_busy = false
	_fetch_members()

func _fetch_members() -> void:
	if not visible or member_busy: return
	read_serial += 1
	member_busy = true; contexts["members"] = _identity().merged({"serial": read_serial})
	if member_http.request(str(host.server_url) + "/api/alliance?search=" + directory_filter.uri_encode(), _headers(), HTTPClient.METHOD_GET) != OK:
		member_busy = false; _set_status(I18n.t("Nie udało się odświeżyć sojuszu. Spróbujemy ponownie."))

func _fetch_operations() -> void:
	if not visible or operation_busy or _alliance().is_empty(): return
	read_serial += 1
	operation_busy = true; contexts["operations"] = _identity().merged({"serial": read_serial, "alliance_id": str(_alliance().get("id", "")), "role": _role()})
	if operation_http.request(str(host.server_url) + "/api/alliance/operations", _headers(), HTTPClient.METHOD_GET) != OK:
		operation_busy = false; _set_status(I18n.t("Nie udało się odświeżyć operacji. Spróbujemy ponownie."))

func _decode(bytes: PackedByteArray) -> Dictionary:
	var parser: JSON = JSON.new()
	if parser.parse(bytes.get_string_from_utf8()) == OK and parser.data is Dictionary: return parser.data
	return {}

func _response_ok(result: int, code: int, value: Dictionary) -> bool:
	if code == 426:
		close(); host._handle_required_update(value)
		return false
	return result == HTTPRequest.RESULT_SUCCESS and code == 200 and bool(value.get("ok", false))

func _member_received(result: int, code: int, _headers_value: PackedStringArray, bytes: PackedByteArray, expected: Dictionary = {}) -> void:
	var context: Dictionary = contexts.get("members", {}).duplicate() if expected.is_empty() else expected
	if context != contexts.get("members", {}): return
	if not visible or not _current(contexts.get("members", {})): return
	if host.has_method("_defer_ui_refresh") and host._defer_ui_refresh("alliance-members:%d" % get_instance_id(),
		_member_received.bind(result, code, _headers_value, bytes, context)): return
	member_busy = false
	var value: Dictionary = _decode(bytes)
	if not _response_ok(result, code, value):
		_set_status(str(value.get("error", I18n.t("Nie udało się odświeżyć sojuszu. Spróbujemy ponownie."))))
		return
	_adopt_membership(value.get("view", value))
	_render()
	if not _alliance().is_empty() and operations.is_empty(): _fetch_operations()

func _operations_received(result: int, code: int, _headers_value: PackedStringArray, bytes: PackedByteArray, expected: Dictionary = {}) -> void:
	var context: Dictionary = contexts.get("operations", {}).duplicate() if expected.is_empty() else expected
	if context != contexts.get("operations", {}): return
	if not visible or not _current(contexts.get("operations", {})): return
	if str(contexts["operations"].get("alliance_id", "")) != str(_alliance().get("id", "")) or str(contexts["operations"].get("role", "")) != _role(): return
	if host.has_method("_defer_ui_refresh") and host._defer_ui_refresh("alliance-operations:%d" % get_instance_id(),
		_operations_received.bind(result, code, _headers_value, bytes, context)): return
	operation_busy = false
	var value: Dictionary = _decode(bytes)
	if not _response_ok(result, code, value):
		if not _alliance().is_empty(): _set_status(str(value.get("error", I18n.t("Nie udało się odświeżyć operacji. Spróbujemy ponownie."))))
		return
	operations = value.get("view", value)
	_render()

func _post(payload: Dictionary, operation: bool = false, preview: bool = false) -> void:
	if action_busy or str(host.session_token).is_empty() or host.update_required: return
	var path: String = "/api/alliance/operation/preview" if preview else "/api/alliance/operation" if operation else "/api/alliance"
	var fingerprint: String = path + JSON.stringify(payload)
	if not retry_context.is_empty() and not bool(retry_context.get("preview", false)) and fingerprint != str(retry_context.get("fingerprint", "")):
		retry_button.show()
		return
	var body_value: Dictionary = payload.duplicate(true)
	if not preview:
		if not request_ids.has(fingerprint): request_ids[fingerprint] = host._new_request_id()
		body_value["request_id"] = request_ids[fingerprint]
	contexts["action"] = _identity().merged({"payload": body_value, "original": payload.duplicate(true), "path": path, "fingerprint": fingerprint, "preview": preview, "operation": operation})
	if preview: contexts["action"]["draft"] = _fleet_draft(payload)
	action_busy = true
	_set_status(I18n.t("Sprawdzanie trasy…") if preview else I18n.t("Zapisywanie…"))
	_chat_changed()
	if action_http.request(str(host.server_url) + path, _headers(), HTTPClient.METHOD_POST, JSON.stringify(body_value)) != OK:
		action_busy = false
		_action_failed({}, contexts["action"])

func _action_failed(value: Dictionary, context: Dictionary, can_retry: bool = true) -> void:
	retry_context = context.duplicate(true) if can_retry else {}
	_set_status(str(value.get("error", I18n.t("Nie udało się potwierdzić operacji. Spróbuj ponownie. Dane formularza zostały zachowane."))), true)
	retry_button.visible = can_retry
	_chat_changed()

func _retry() -> void:
	if retry_context.is_empty() or not _current(retry_context): return
	_post(retry_context.get("original", {}), bool(retry_context.get("operation", false)), bool(retry_context.get("preview", false)))

func _action_received(result: int, code: int, _headers_value: PackedStringArray, bytes: PackedByteArray) -> void:
	action_busy = false
	var context: Dictionary = contexts.get("action", {})
	if not _current(context): return
	var value: Dictionary = _decode(bytes)
	if not _response_ok(result, code, value):
		_action_failed(value, context, result != HTTPRequest.RESULT_SUCCESS or code >= 500 or code == 0)
		return
	retry_context.clear(); retry_button.hide()
	if bool(context.get("preview", false)):
		if visible: _show_preview(value.get("preview", value), context.get("original", {}), context.get("draft", {}))
		return
	request_ids.erase(str(context.get("fingerprint", "")))
	var payload: Dictionary = context.get("original", {})
	if str(payload.get("action", "")) == "chat_send":
		if editor.text.strip_edges() == str(payload.get("text", "")): editor.text = ""
		chat_draft = editor.text
	elif visible:
		form = ""; form_context.clear()
	if not bool(context.get("operation", false)) and value.has("alliance"): _adopt_membership(value)
	_set_status(str(value.get("message", I18n.t("Operacja zakończona."))))
	_chat_changed()
	if visible:
		member_http.cancel_request(); member_busy = false
		operation_http.cancel_request(); operation_busy = false
		_fetch_members(); _fetch_operations()
		_render(true)

func _set_status(text: String, force: bool = false) -> void:
	if not force and not action_busy and not retry_context.is_empty() and not bool(retry_context.get("preview", false)): return
	status.text = text
	status.get_parent().get_parent().visible = not text.is_empty()
	retry_button.hide()

func _adopt_membership(value: Dictionary) -> void:
	var old_id: String = str(_alliance().get("id", ""))
	var old_role: String = _role()
	data = value
	var changed: bool = old_id != str(_alliance().get("id", "")) or old_role != _role()
	if changed:
		operation_http.cancel_request(); operation_busy = false
		operations.clear()
		form = ""; form_context.clear()
		if not old_id.is_empty(): launch_target.clear()
		render_signature = ""
		if _alliance().is_empty(): tab = 0

func _alliance() -> Dictionary:
	var value: Variant = data.get("alliance", data.get("own_alliance", {}))
	return value if value is Dictionary else {}

func _own_id() -> String:
	return str(host.state.get("player", {}).get("id", ""))

func _role() -> String:
	return str(_alliance().get("role", data.get("role", "member")))

func _role_title(role: String) -> String:
	match role:
		"leader": return I18n.t("Przywódca")
		"officer": return I18n.t("Oficer")
	return I18n.t("Członek")

func _select_tab(value: int) -> void:
	if action_busy: return
	form = ""; form_context.clear(); launch_target.clear()
	_clear_resolved_status()
	tab = value; _render(true)
	if tab == 2: _fetch_operations()

func _clear_body() -> void:
	for picker in pickers:
		if is_instance_valid(picker): picker.close()
	pickers.clear(); fields.clear(); quantities.clear(); countdowns.clear()
	host._clear(body)

func _render(force: bool = false) -> void:
	if not visible or (not form.is_empty() and not force): return
	var alliance: Dictionary = _alliance()
	title.text = "[%s] %s" % [alliance.get("tag", ""), alliance.get("name", "")] if not alliance.is_empty() else I18n.t("Sojusze")
	for i: int in range(tabs.size()):
		tabs[i].disabled = (i > 0 and alliance.is_empty()) or i == tab
		if i == tab: tabs[i].add_theme_stylebox_override("normal", host._style("2b4f36", "91c89b", 12, 10))
		else: tabs[i].remove_theme_stylebox_override("normal")
	if alliance.is_empty(): tab = 0
	composer.visible = tab == 3 and form.is_empty() and not alliance.is_empty()
	directory_search.visible = alliance.is_empty() and form.is_empty()
	var stable_view: Dictionary = (operations if tab == 2 else data).duplicate(true)
	stable_view.erase("server_time")
	var signature: String = str(tab) + JSON.stringify(stable_view)
	if not force and signature == render_signature: return
	render_signature = signature
	var old_scroll: int = scroll.scroll_vertical
	var bottom: bool = scroll.get_v_scroll_bar().value >= scroll.get_v_scroll_bar().max_value - scroll.get_v_scroll_bar().page - 32
	_clear_body()
	if data.is_empty(): _text(body, I18n.t("Wczytywanie sojuszy…"), "a0b3a4")
	elif alliance.is_empty(): _directory()
	elif tab == 0: _overview(alliance)
	elif tab == 1: _members(alliance)
	elif tab == 2: _operation_list()
	elif tab == 3: _chat()
	if force: scroll.set_deferred("scroll_vertical", 0)
	elif tab == 3 and bottom: scroll.set_deferred("scroll_vertical", 1000000)
	else: scroll.set_deferred("scroll_vertical", old_scroll)
	_chat_changed()

func _clear_resolved_status() -> void:
	if not retry_context.is_empty() and not bool(retry_context.get("preview", false)): return
	retry_context.clear(); _set_status("")

func _begin_form(kind: String, context: Dictionary = {}) -> VBoxContainer:
	_clear_resolved_status()
	form = kind; form_context = context.duplicate(true)
	_clear_body(); composer.hide(); directory_search.hide(); scroll.scroll_vertical = 0
	return _card()

func _directory() -> void:
	_text(body, I18n.t("Wspólne ataki, obrona kolonii i prywatny czat."), "a0b3a4")
	_button(body, I18n.t("Załóż sojusz"), _edit_alliance.bind(true), true)
	var cooldown: float = float(data.get("cooldown_until", 0)) - host._server_now()
	if cooldown > 0: _text(body, I18n.t("Dołączenie do kolejnego sojuszu za %s.") % host._duration(cooldown), "ffc56f")
	for invitation: Dictionary in data.get("invitations", []):
		var card: VBoxContainer = _card()
		var alliance: Dictionary = invitation.get("alliance", invitation)
		_text(card, I18n.t("Zaproszenie: [%s] %s") % [alliance.get("tag", ""), alliance.get("name", "")], "ffc56f")
		var buttons: GridContainer = _two(card)
		var id: String = str(invitation.get("alliance_id", alliance.get("id", "")))
		_button(buttons, I18n.t("Przyjmij"), _post.bind({"action": "accept_invite", "alliance_id": id}), true)
		_button(buttons, I18n.t("Odrzuć"), _post.bind({"action": "decline_invite", "alliance_id": id}))
	for application: Dictionary in data.get("applications", []):
		var card: VBoxContainer = _card()
		_text(card, I18n.t("Oczekujące podanie: %s") % str(application.get("alliance_name", application.get("name", ""))))
		_button(card, I18n.t("Wycofaj podanie"), _post.bind({"action": "withdraw_application", "alliance_id": str(application.get("alliance_id", ""))}))
	_text(body, I18n.t("Dostępne sojusze"), "ffc56f", 26)
	var directory: Array = data.get("directory", [])
	if directory.is_empty(): _text(body, I18n.t("Nie ma jeszcze sojuszy. Możesz założyć pierwszy."), "a0b3a4")
	for alliance: Dictionary in directory:
		var card: VBoxContainer = _card()
		_text(card, "[%s] %s" % [alliance.get("tag", ""), alliance.get("name", "")], "e7eee4", 26)
		_text(card, I18n.t("Członkowie: %d / %d") % [int(alliance.get("members_count", 0)), int(alliance.get("max_members", 20))], "a0b3a4")
		if not str(alliance.get("description", "")).is_empty(): _text(card, str(alliance["description"]))
		_button(card, I18n.t("Złóż podanie"), _apply_form.bind(alliance))

func _overview(alliance: Dictionary) -> void:
	var card: VBoxContainer = _card()
	_text(card, I18n.t("Członkowie: %d / %d") % [int(alliance.get("members_count", 0)), int(alliance.get("max_members", 20))], "ffc56f", 26)
	_text(card, _role_title(_role()), "a0b3a4")
	_text(card, str(alliance.get("description", "")))
	_text(card, I18n.t("Sojusz nie odsłania automatycznie galaktyki. Informacje o celu pochodzą z rozpoznania."), "a0b3a4")
	_button(card, I18n.t("Otwórz operacje bojowe"), _select_tab.bind(2), true)
	if _role() in ["leader", "officer"]:
		_button(card, I18n.t("Zaproś gracza"), _invite_form)
	if _role() == "leader":
		_button(card, I18n.t("Edytuj sojusz"), _edit_alliance.bind(false))
		_button(card, I18n.t("Rozwiąż sojusz"), _disband_form)
	else:
		_button(card, I18n.t("Opuść sojusz"), _confirm.bind(I18n.t("Opuścić sojusz? Przez pewien czas nie będzie można dołączyć do innego."), {"action": "leave"}))

func _edit_alliance(create: bool) -> void:
	var alliance: Dictionary = {} if create else _alliance()
	var card: VBoxContainer = _begin_form("edit")
	_text(card, I18n.t("Załóż sojusz") if create else I18n.t("Edytuj sojusz"), "ffc56f", 26)
	_line(card, "name", I18n.t("Nazwa sojuszu"), str(alliance.get("name", "")), 40)
	_line(card, "tag", I18n.t("Skrót sojuszu"), str(alliance.get("tag", "")), 6)
	_editor(card, "description", I18n.t("Opis sojuszu"), str(alliance.get("description", "")))
	_button(card, I18n.t("Utwórz") if create else I18n.t("Zapisz"), _save_alliance.bind(create), true)

func _save_alliance(create: bool) -> void:
	_post({"action": "create" if create else "edit", "name": fields["name"].text.strip_edges(), "tag": fields["tag"].text.strip_edges(), "description": fields["description"].text.strip_edges()})

func _apply_form(alliance: Dictionary) -> void:
	var card: VBoxContainer = _begin_form("apply", alliance)
	_text(card, I18n.t("Podanie do: [%s] %s") % [alliance.get("tag", ""), alliance.get("name", "")], "ffc56f", 26)
	_editor(card, "text", I18n.t("Wiadomość do przywódcy"))
	_button(card, I18n.t("Wyślij podanie"), func() -> void: _post({"action": "apply", "alliance_id": str(alliance.get("id", "")), "text": fields["text"].text.strip_edges()}), true)

func _invite_form() -> void:
	var card: VBoxContainer = _begin_form("invite")
	_text(card, I18n.t("Zaproś gracza"), "ffc56f", 26)
	_line(card, "player_name", I18n.t("Dokładna nazwa gracza"), "", 40)
	_button(card, I18n.t("Wyślij zaproszenie"), func() -> void: _post({"action": "invite", "player_name": fields["player_name"].text.strip_edges()}), true)

func _members(alliance: Dictionary) -> void:
	var manage: bool = _role() in ["leader", "officer"]
	if manage: _button(body, I18n.t("Zaproś gracza"), _invite_form, true)
	for member: Dictionary in alliance.get("members", data.get("members", [])):
		var card: VBoxContainer = _card()
		var id: String = str(member.get("id", member.get("player_id", "")))
		var role: String = str(member.get("role", "member"))
		_text(card, str(member.get("name", "")), "e7eee4", 25)
		_text(card, _role_title(role), "ffc56f")
		if float(member.get("joined_at", 0)) > 0: _text(card, I18n.t("W sojuszu od %s") % host._date(float(member["joined_at"])), "a0b3a4")
		if _role() == "leader" and id != _own_id():
			var buttons: GridContainer = _two(card)
			_button(buttons, I18n.t("Mianuj oficerem") if role == "member" else I18n.t("Odbierz rangę"), _post.bind({"action": "set_role", "player_id": id, "role": "officer" if role == "member" else "member"}))
			_button(buttons, I18n.t("Przekaż dowództwo"), _confirm.bind(I18n.t("Przekazać dowództwo graczowi %s?") % str(member.get("name", "")), {"action": "transfer_leader", "player_id": id}))
		if manage and id != _own_id() and role == "member" or _role() == "leader" and id != _own_id():
			_button(card, I18n.t("Usuń z sojuszu"), _confirm.bind(I18n.t("Usunąć gracza %s z sojuszu?") % str(member.get("name", "")), {"action": "kick", "player_id": id}))
	if manage:
		for application: Dictionary in alliance.get("applications", data.get("applications", [])):
			var card: VBoxContainer = _card()
			_text(card, I18n.t("Podanie: %s") % str(application.get("player_name", application.get("name", ""))), "ffc56f", 25)
			_text(card, str(application.get("text", "")))
			var id: String = str(application.get("player_id", application.get("id", "")))
			var buttons: GridContainer = _two(card)
			_button(buttons, I18n.t("Przyjmij"), _post.bind({"action": "approve_application", "player_id": id}), true)
			_button(buttons, I18n.t("Odrzuć"), _post.bind({"action": "reject_application", "player_id": id}))
		for invitation: Dictionary in alliance.get("invitations", []):
			var card: VBoxContainer = _card()
			_text(card, I18n.t("Zaproszono: %s") % str(invitation.get("player_name", invitation.get("name", ""))), "a0b3a4")
			_button(card, I18n.t("Wycofaj zaproszenie"), _post.bind({"action": "cancel_invite", "player_id": str(invitation.get("player_id", ""))}))

func _confirm(question: String, payload: Dictionary, operation: bool = false) -> void:
	var card: VBoxContainer = _begin_form("confirm")
	_text(card, question, "ffc56f", 26)
	var buttons: GridContainer = _two(card)
	_button(buttons, I18n.t("Potwierdź"), _post.bind(payload, operation), true)
	_button(buttons, I18n.t("Anuluj"), go_back)

func _disband_form() -> void:
	var card: VBoxContainer = _begin_form("disband")
	_text(card, I18n.t("Rozwiązać sojusz? Ta operacja usuwa sojusz i jego członkostwa."), "ffc56f", 26)
	_line(card, "confirmation", I18n.t("Aby potwierdzić, wpisz skrót: %s") % str(_alliance().get("tag", "")))
	_button(card, I18n.t("Rozwiąż sojusz"), func() -> void: _post({"action": "disband", "confirmation": fields["confirmation"].text}), true)

func _chat() -> void:
	var messages: Array = data.get("messages", _alliance().get("chat", _alliance().get("messages", data.get("chat", []))))
	if messages.is_empty(): _text(body, I18n.t("Zaplanujcie następny atak. Wiadomości widzą tylko członkowie sojuszu."), "a0b3a4")
	for message: Dictionary in messages:
		var card: VBoxContainer = _card()
		_text(card, str(message.get("sender_name", message.get("player_name", ""))), "ffc56f")
		_text(card, host._date(float(message.get("at", message.get("created_at", 0)))), "a0b3a4", 20)
		_text(card, str(message.get("text", "")))

func _chat_changed() -> void:
	if not is_instance_valid(chat_send): return
	chat_draft = editor.text
	chat_counter.text = "%d / 500" % editor.text.length()
	chat_send.disabled = action_busy or editor.text.strip_edges().is_empty() or editor.text.length() > 500 or _alliance().is_empty()

func _send_chat() -> void:
	if editor.text.length() <= 500 and not editor.text.strip_edges().is_empty(): _post({"action": "chat_send", "text": editor.text.strip_edges()})

func _operation_status(value: String) -> String:
	match value:
		"planning", "gathering", "open", "forming", "scheduled": return I18n.t("Zbiórka flot")
		"locked", "incoming": return I18n.t("Floty w drodze")
		"resolved", "completed", "finished": return I18n.t("Zakończona")
		"cancelled", "canceled": return I18n.t("Anulowana")
		"holding": return I18n.t("Obrona na orbicie")
		"outbound", "traveling": return I18n.t("W drodze do celu")
		"returning", "return": return I18n.t("Powrót do kolonii")
	return value

func _fleet_text(ships: Dictionary, specs: Array = []) -> String:
	var names: Dictionary = {}
	for origin: Dictionary in operations.get("origins", []):
		for spec: Dictionary in origin.get("ship_specs", []): names[str(spec.get("key", ""))] = str(spec.get("name", ""))
	for spec: Dictionary in specs: names[str(spec.get("key", ""))] = str(spec.get("name", ""))
	var lines: PackedStringArray = []
	for key: String in ships:
		if int(ships[key]) > 0: lines.append("%s ×%d" % [names.get(key, host._server_text(key)), int(ships[key])])
	return ", ".join(lines)

func _operation_list() -> void:
	var start: VBoxContainer = _card()
	_text(start, I18n.t("Wspólna siła przeciw Rojowi i graczom"), "ffc56f", 26)
	_text(start, I18n.t("Maksymalnie 5 graczy w ataku. Każdy wysyła jedną flotę. Wszystkie uderzą o ustalonej porze."), "a0b3a4")
	var buttons: GridContainer = _two(start)
	var plan: Button = _button(buttons, I18n.t("Zaplanuj atak"), _create_operation, true)
	plan.disabled = _role() not in ["leader", "officer"]
	_button(buttons, I18n.t("Wesprzyj obronę"), _defense_form)
	if not launch_target.is_empty():
		_text(start, I18n.t("Wybrany cel: %s") % str(launch_target.get("name", "")), "ffc56f")
	var list: Array = operations.get("operations", [])
	if list.is_empty(): _text(body, I18n.t("Brak operacji bojowych. Zaplanujcie pierwszą wyprawę."), "a0b3a4")
	for operation: Dictionary in list:
		var card: VBoxContainer = _card()
		var target: Dictionary = operation.get("target", {})
		_text(card, str(target.get("name", "")), "e7eee4", 26)
		_text(card, str(target.get("owner_name", "")) + " · " + _operation_status(str(operation.get("status", ""))), "ffc56f")
		var impact: float = float(operation.get("impact_at", 0))
		_text(card, I18n.t("Wspólne uderzenie: %s") % host._date(impact), "a0b3a4")
		if impact > host._server_now():
			var countdown: Label = _text(card, I18n.t("Do uderzenia: %s") % host._duration(impact - host._server_now()), "ffc56f")
			countdowns[countdown] = impact
		var participants: Array = operation.get("participants", [])
		_text(card, I18n.t("Uczestnicy: %d / 5") % participants.size())
		var own_participant: bool = false
		for participant: Dictionary in participants:
			own_participant = own_participant or str(participant.get("owner_id", "")) == _own_id()
			_text(card, str(participant.get("owner_name", "")) + " · " + str(participant.get("origin_name", "")), "a0b3a4")
			_text(card, _fleet_text(participant.get("ships", {}), participant.get("ship_specs", [])))
		var controls: GridContainer = _two(card)
		if bool(operation.get("can_join", false)):
			_button(controls, I18n.t("Dołącz flotą"), _join_form.bind(operation), true)
		if bool(operation.get("can_withdraw", own_participant and impact > host._server_now() + 30 and str(operation.get("status", "")) not in ["resolved", "cancelled", "completed"])):
			_button(controls, I18n.t("Wycofaj flotę"), _confirm.bind(I18n.t("Wycofać swoją flotę z operacji? Statki wrócą lotem powrotnym."), {"action": "withdraw", "operation_id": str(operation.get("id", ""))}, true))
		if bool(operation.get("can_cancel", false)):
			_button(controls, I18n.t("Anuluj operację"), _confirm.bind(I18n.t("Anulować operację? Wysłane floty rozpoczną powrót."), {"action": "cancel", "operation_id": str(operation.get("id", ""))}, true))
	var supports: Array = operations.get("supports", [])
	if not supports.is_empty(): _text(body, I18n.t("Wsparcie obrony"), "ffc56f", 26)
	for support: Dictionary in supports:
		var card: VBoxContainer = _card()
		_text(card, str(support.get("target_name", "")), "e7eee4", 26)
		_text(card, str(support.get("owner_name", "")) + " · " + _operation_status(str(support.get("status", ""))), "ffc56f")
		_text(card, _fleet_text(support.get("ships", {}), support.get("ship_specs", [])))
		_text(card, I18n.t("Przylot: %s") % host._date(float(support.get("arrives_at", 0))), "a0b3a4")
		if float(support.get("hold_until", 0)) > 0: _text(card, I18n.t("Obrona do: %s") % host._date(float(support.get("hold_until", 0))), "a0b3a4")
		if bool(support.get("can_recall", false)):
			_button(card, I18n.t("Odwołaj wsparcie"), _confirm.bind(I18n.t("Odwołać wsparcie? Flota rozpocznie powrót do swojej kolonii."), {"action": "recall", "fleet_id": str(support.get("fleet_id", ""))}, true))

func _add_target(parent: Node, defense: bool):
	var picker = _choice(parent, I18n.t("Broniona kolonia") if defense else I18n.t("Cel ataku"))
	var choices: Array = operations.get("defense_targets" if defense else "attack_targets", [])
	for target: Dictionary in choices:
		picker.add_item(str(target.get("name", "")) + " · " + str(target.get("owner_name", "")))
		picker.set_item_metadata(picker.item_count - 1, str(target.get("id", "")))
		if str(target.get("id", "")) == str(launch_target.get("id", "")): picker.select(picker.item_count - 1)
	if choices.is_empty(): _text(parent, I18n.t("Brak dostępnych celów. Atak wymaga rozpoznanej planety, a obrona kolonii członka sojuszu."), "ffc56f")
	fields["target"] = picker
	return picker

func _create_operation() -> void:
	var card: VBoxContainer = _begin_form("create_operation")
	_text(card, I18n.t("Zaplanuj wspólny atak"), "ffc56f", 26)
	_add_target(card, false)
	var time_picker = _choice(card, I18n.t("Uderzenie za"))
	for minutes: int in [5, 15, 30, 60, 120, 240, 480, 720, 1440]:
		time_picker.add_item(host._duration(minutes * 60))
		time_picker.set_item_metadata(time_picker.item_count - 1, minutes * 60)
		if minutes == 30: time_picker.select(time_picker.item_count - 1)
	fields["delay"] = time_picker
	_text(card, I18n.t("Utworzenie planu nie wysyła statków. Następnie wybierz „Dołącz flotą”. Czas musi wystarczyć każdemu na dolot."), "a0b3a4")
	_text(card, I18n.t("Plan celu jest zapisem rozpoznania. Nie ujawnia na żywo wrogich flot, budynków ani surowców."), "a0b3a4")
	_button(card, I18n.t("Utwórz operację"), _submit_operation, true)

func _submit_operation() -> void:
	var id: Variant = fields["target"].get_selected_metadata()
	if id == null:
		_set_status(I18n.t("Wybierz cel operacji.")); return
	_post({"action": "create", "target_id": str(id), "delay_seconds": int(fields["delay"].get_selected_metadata())}, true)

func _join_form(operation: Dictionary) -> void:
	var card: VBoxContainer = _begin_form("join", {"operation": operation})
	_text(card, I18n.t("Dołącz flotą"), "ffc56f", 26)
	_text(card, str(operation.get("target", {}).get("name", "")))
	_text(card, I18n.t("Wspólne uderzenie: %s") % host._date(float(operation.get("impact_at", 0))), "ffc56f")
	_add_origin(card)
	_text(card, I18n.t("Po sprawdzeniu trasy zobaczysz koszt paliwa i potwierdzisz wysłanie."), "a0b3a4")
	_button(card, I18n.t("Sprawdź trasę"), _preview_join, true)

func _defense_form() -> void:
	var card: VBoxContainer = _begin_form("defend")
	_text(card, I18n.t("Wesprzyj obronę"), "ffc56f", 26)
	_add_target(card, true)
	var hold = _choice(card, I18n.t("Czas obrony po przylocie"))
	for hours: int in [1, 4, 8]:
		hold.add_item(I18n.t("%d godz.") % hours)
		hold.set_item_metadata(hold.item_count - 1, hours)
	fields["hold"] = hold
	_add_origin(card)
	_text(card, I18n.t("Wsparcie walczy u boku obrońcy po przylocie. Po służbie ocalałe statki wrócą do swojej kolonii."), "a0b3a4")
	_button(card, I18n.t("Sprawdź trasę"), _preview_defense, true)

func _add_origin(parent: Node) -> void:
	var picker = _choice(parent, I18n.t("Kolonia startowa"))
	var origins: Array = operations.get("origins", [])
	for origin: Dictionary in origins:
		picker.add_item(str(origin.get("name", "")))
		picker.set_item_metadata(picker.item_count - 1, str(origin.get("id", "")))
		if str(origin.get("id", "")) == selected_origin or selected_origin.is_empty() and str(origin.get("id", "")) == str(host.selected_planet): picker.select(picker.item_count - 1)
	fields["origin"] = picker
	var ship_box: VBoxContainer = VBoxContainer.new()
	ship_box.name = "AllianceShipSelection"
	parent.add_child(ship_box)
	fields["ship_box"] = ship_box
	picker.item_selected.connect(func(_index: int) -> void: _origin_changed())
	_origin_changed()

func _origin_changed() -> void:
	var picker = fields["origin"]
	selected_origin = str(picker.get_selected_metadata()) if picker.selected >= 0 else ""
	var ship_box: VBoxContainer = fields["ship_box"]
	host._clear(ship_box); quantities.clear()
	var origin: Dictionary = {}
	for candidate: Dictionary in operations.get("origins", []):
		if str(candidate.get("id", "")) == selected_origin: origin = candidate
	var available: Dictionary = origin.get("ships", {})
	for spec: Dictionary in origin.get("ship_specs", []):
		var key: String = str(spec.get("key", ""))
		var count: int = int(available.get(key, 0))
		if count <= 0: continue
		var row: VBoxContainer = VBoxContainer.new()
		ship_box.add_child(row)
		_text(row, I18n.t("%s · dostępne: %d") % [str(spec.get("name", key)), count])
		var controls: HBoxContainer = host._row(row)
		var quantity = QuantityScript.new()
		quantity.name = "AllianceQuantity_" + key
		quantity.min_value = 0; quantity.max_value = count; quantity.step = 1; quantity.value = 0
		controls.add_child(quantity)
		quantities[key] = quantity
		var all: Button = _button(controls, I18n.t("Wszystkie"), func() -> void: quantity.value = count)
		all.custom_minimum_size.x = 126
	if quantities.is_empty(): _text(ship_box, I18n.t("Brak dostępnych statków w tej kolonii."), "ffc56f")

func _ships() -> Dictionary:
	var result: Dictionary = {}
	for key: String in quantities:
		quantities[key].apply()
		var count: int = int(quantities[key].value)
		if count > 0: result[key] = count
	return result

func _preview_join() -> void:
	var ships: Dictionary = _ships()
	if ships.is_empty(): _set_status(I18n.t("Wybierz co najmniej jeden statek.")); return
	_post({"action": "join", "operation_id": str(form_context.get("operation", {}).get("id", "")), "planet_id": selected_origin, "ships": ships}, true, true)

func _preview_defense() -> void:
	var target: Variant = fields["target"].get_selected_metadata()
	if target == null: _set_status(I18n.t("Wybierz cel operacji.")); return
	var ships: Dictionary = _ships()
	if ships.is_empty(): _set_status(I18n.t("Wybierz co najmniej jeden statek.")); return
	_post({"action": "defend", "target_id": str(target), "planet_id": selected_origin, "ships": ships, "hold_hours": int(fields["hold"].get_selected_metadata())}, true, true)

func _show_preview(preview: Dictionary, payload: Dictionary, draft: Dictionary = {}) -> void:
	var card: VBoxContainer = _begin_form("preview", {"payload": payload, "preview": preview, "draft": draft})
	_text(card, I18n.t("Potwierdź wysłanie floty"), "ffc56f", 26)
	_text(card, _fleet_text(payload.get("ships", {})))
	_text(card, I18n.t("Czas lotu: %s") % host._duration(float(preview.get("seconds", 0))))
	if float(preview.get("impact_at", 0)) > 0:
		_text(card, (I18n.t("Wspólne uderzenie: %s") if str(payload.get("action", "")) == "join" else I18n.t("Przylot: %s")) % host._date(float(preview["impact_at"])))
	if int(preview.get("hold_hours", 0)) > 0:
		_text(card, I18n.t("Obrona po przylocie: %d godz.") % int(preview["hold_hours"]))
	card.add_child(ResourceInfo.label(host, I18n.t("Koszt: %s") % (ResourceInfo.token("fuel") + "\u00A0" + host._exact_integer(int(preview.get("fuel_cost", 0)))), 28, "ffc56f"))
	_text(card, I18n.t("Koszt obejmuje podróż w obie strony i ewentualne utrzymanie wsparcia."), "a0b3a4")
	var warning: Variant = preview.get("protection_warning", false)
	if (warning is bool and warning) or (warning is String and not str(warning).is_empty()):
		_text(card, str(warning) if warning is String else I18n.t("Ta misja wyłączy Twoją ochronę początkową. Potwierdź tylko, jeśli jesteś gotowy na PvP."), "ffb49c", 24)
	if not str(preview.get("message", "")).is_empty(): _text(card, str(preview["message"]), "ffc56f")
	if not bool(preview.get("affordable", false)):
		card.add_child(ResourceInfo.label(host, I18n.t("Za mało paliwa. Brakuje: %s") % (ResourceInfo.token("fuel") + "\u00A0" + host._exact_integer(int(preview.get("shortfall", {}).get("fuel", 0)))), 22, "ffb49c"))
	else:
		_button(card, I18n.t("Wyślij flotę"), _post.bind(payload, true), true)
	_button(card, I18n.t("Anuluj"), go_back)
	_set_status("")


func _fleet_draft(payload: Dictionary) -> Dictionary:
	return {"kind": form, "operation": form_context.get("operation", {}).duplicate(true), "payload": payload.duplicate(true)}

func _restore_fleet_draft(draft: Dictionary) -> void:
	var payload: Dictionary = draft.get("payload", {})
	selected_origin = str(payload.get("planet_id", ""))
	if str(draft.get("kind", "")) == "join": _join_form(draft.get("operation", {}))
	else:
		_defense_form()
		for key: String in ["target", "hold"]:
			var picker = fields[key]
			var wanted: Variant = payload.get("target_id" if key == "target" else "hold_hours")
			for index: int in range(picker.item_count):
				if str(picker.get_item_metadata(index)) == str(wanted): picker.select(index)
	for key: String in payload.get("ships", {}):
		if quantities.has(key): quantities[key].value = int(payload["ships"][key])
