extends Node



signal configuration_changed
signal changed
signal needs_name
signal completed(response: Dictionary)
signal failed(message: String)

const FLOW_LIFETIME_MS: int = 900000
const HANDOFF_METHOD: String = "app_link_v1"
const RETURN_PREFIX: String = "com.conradmafer.aliencolonies://google-auth?"

var host: Node
var configured: bool = false
var configuration_loaded: bool = false
var phase: String = ""
var email_address: String = ""
var _native_bridge: Object
var _owns_native_flow: bool = false
var _request_node: HTTPRequest
var _request_kind: String = ""
var _request_generation: int = 0
var _timer: Timer
var _deadline: Timer
var _flow_id: String = ""
var _poll_secret: String = ""
var _handoff_ticket: String = ""
var _flow_origin: String = ""
var _flow_session: String = ""
var _flow_player_id: String = ""
var _expires_at_ms: int = 0
var _resend_at_ms: int = 0
var _poll_seconds: float = 3.0
var _completing_registration: bool = false


func setup(owner_node: Node) -> void :
	host = owner_node
	host.add_child(self)
	if Engine.has_singleton("AlienGoogleAuth"):
		_native_bridge = Engine.get_singleton("AlienGoogleAuth")
	_timer = Timer.new()
	_timer.one_shot = true
	add_child(_timer)
	_timer.timeout.connect(_poll)
	_deadline = Timer.new()
	_deadline.one_shot = true
	add_child(_deadline)
	_deadline.timeout.connect( func() -> void : _fail(I18n.t("Link do logowania wygasł. Wyślij nowy link.")))


func load_configuration() -> void :
	if is_active() or is_request_pending() or str(host.server_url).is_empty():
		return
	configured = false
	configuration_loaded = false
	_send("config", "/api/auth/email/config", {}, HTTPClient.METHOD_GET)
	changed.emit()


func is_active() -> bool:
	return not phase.is_empty()


func is_request_pending() -> bool:
	return not _request_kind.is_empty()


func waiting_for_name() -> bool:
	return phase == "needs_name"


func resend_wait_seconds() -> int:
	return maxi(0, ceili(float(_resend_at_ms - Time.get_ticks_msec()) / 1000.0))


func start(address: String) -> void :
	if not configured or is_request_pending():
		return
	if is_active() and resend_wait_seconds() > 0:
		return
	var clean: String = address.strip_edges()

	if clean.length() < 3 or clean.length() > 254 or clean.count("@") != 1 or clean.contains(" ") or clean.contains("\n") or clean.contains("\r"):
		failed.emit(I18n.t("Wpisz poprawny adres e-mail."))
		return
	cancel()
	if not is_instance_valid(_native_bridge):
		_fail(I18n.t("Moduł logowania jest niedostępny w aplikacji."))
		return
	email_address = clean
	_flow_origin = str(host.server_url)
	_flow_session = str(host.session_token)
	_flow_player_id = str(host.state.get("player", {}).get("id", ""))
	phase = "sending"
	_expires_at_ms = Time.get_ticks_msec() + FLOW_LIFETIME_MS
	_resend_at_ms = Time.get_ticks_msec() + 60000
	_deadline.start(float(FLOW_LIFETIME_MS) / 1000.0)
	_send("start", "/api/auth/email/start", {"email": email_address, "client": "android", "handoff": HANDOFF_METHOD})
	changed.emit()


func resend() -> void :
	if phase != "waiting" or resend_wait_seconds() > 0 or is_request_pending():
		return
	start(email_address)


func complete(empire_name: String = "") -> void :
	if not is_active() or is_request_pending() or _flow_id.is_empty() or _handoff_ticket.is_empty() or _expired():
		return
	if not _flow_player_id.is_empty() and not empire_name.is_empty():
		_fail(I18n.t("Ten adres e-mail nie jest połączony z tym imperium."))
		return
	var payload: Dictionary = _proof()
	_completing_registration = phase == "needs_name"
	if not empire_name.is_empty():
		payload["name"] = empire_name
	phase = "completing"
	_send("complete", "/api/auth/email/complete", payload)
	changed.emit()


func cancel() -> void :
	_stop_transport()
	if _timer != null:
		_timer.stop()
	if _deadline != null:
		_deadline.stop()

	if _owns_native_flow and is_instance_valid(_native_bridge):
		_native_bridge.call("setExpectedFlow", "")
	_owns_native_flow = false
	phase = ""
	email_address = ""
	_flow_id = ""
	_poll_secret = ""
	_handoff_ticket = ""
	_flow_origin = ""
	_flow_session = ""
	_flow_player_id = ""
	_expires_at_ms = 0
	_resend_at_ms = 0
	_completing_registration = false
	changed.emit()


func _exit_tree() -> void :
	cancel()


func _notification(what: int) -> void :
	if what == NOTIFICATION_APPLICATION_RESUMED and is_active() and phase == "waiting":
		_poll.call_deferred()


func _proof() -> Dictionary:
	var result: Dictionary = {"flow_id": _flow_id, "poll_secret": _poll_secret}
	if not _handoff_ticket.is_empty():
		result["handoff_ticket"] = _handoff_ticket
	return result


func _same_account() -> bool:
	return str(host.session_token) == _flow_session and str(host.state.get("player", {}).get("id", "")) == _flow_player_id


func _expired() -> bool:
	if _expires_at_ms > 0 and Time.get_ticks_msec() >= _expires_at_ms:
		_fail(I18n.t("Link do logowania wygasł. Wyślij nowy link."))
		return true
	return false


func _poll() -> void :

	if phase != "waiting" or is_request_pending() or _expired():
		return
	if not _same_account() or str(host.server_url) != _flow_origin:
		cancel()
		return
	if _owns_native_flow and is_instance_valid(_native_bridge):
		var returned: String = str(_native_bridge.call("takePendingReturn"))
		if not returned.is_empty():
			_accept_native_return(returned)
	_send("status", "/api/auth/email/status", _proof())


func _send(kind: String, path: String, payload: Dictionary, method: int = HTTPClient.METHOD_POST) -> void :
	if is_active() and ( not _same_account() or str(host.server_url) != _flow_origin):
		cancel()
		return
	_stop_transport()
	_request_kind = kind
	_request_node = HTTPRequest.new()
	_request_node.timeout = 15.0
	_request_node.max_redirects = 0
	add_child(_request_node)
	_request_node.request_completed.connect(_on_response.bind(_request_generation, kind))
	var headers: PackedStringArray = PackedStringArray(["Content-Type: application/json", "Accept: application/json", "Accept-Language: " + I18n.locale, "X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE)])
	var origin: String = str(host.server_url) if kind == "config" else _flow_origin
	var body: String = "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
	var error: Error = _request_node.request(origin + path, headers, method, body)
	if error != OK:
		_stop_transport()
		if kind == "config":
			_set_configuration(false)
		else:
			_fail(I18n.t("Nie udało się połączyć. Spróbuj ponownie."))


func _stop_transport() -> void :
	_request_generation += 1
	_request_kind = ""
	if is_instance_valid(_request_node):
		_request_node.cancel_request()
		_request_node.queue_free()
	_request_node = null


func _set_configuration(available: bool) -> void :
	configured = available
	configuration_loaded = true
	configuration_changed.emit()
	changed.emit()


func _on_response(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray, generation: int, kind: String) -> void :
	if generation != _request_generation:
		return
	_stop_transport()
	if kind != "config" and ( not is_active() or not _same_account() or str(host.server_url) != _flow_origin or _expired()):
		cancel()
		return


	var parser: JSON = JSON.new()
	var parsed: Variant = parser.data if parser.parse(body.get_string_from_utf8()) == OK else null
	var valid: bool = result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300 and parsed is Dictionary and bool(parsed.get("ok", false))
	if kind == "config":
		_set_configuration(valid and bool(parsed.get("configured", false)))
		return
	if response_code == 426:
		cancel()
		host._handle_required_update(parsed.get("update") if parsed is Dictionary else null)
		return
	if kind == "status" and not valid and (result != HTTPRequest.RESULT_SUCCESS or response_code >= 500 or response_code in [408, 429]):
		_timer.start(_poll_seconds)
		changed.emit()
		return
	if not valid:
		if kind == "complete" and _completing_registration and parsed is Dictionary and response_code in [400, 409]:
			phase = "needs_name"
			changed.emit()
			failed.emit(host._server_text(parsed.get("error", I18n.t("Wybierz inną nazwę imperium."))))
			return
		_fail(host._server_text(parsed.get("error", I18n.t("Nie udało się połączyć. Spróbuj ponownie."))) if parsed is Dictionary else I18n.t("Nie udało się połączyć. Spróbuj ponownie."))
		return
	var response: Dictionary = parsed
	if kind == "start":
		_flow_id = str(response.get("flow_id", ""))
		_poll_secret = str(response.get("poll_secret", ""))
		if not _is_flow_token(_flow_id) or not _is_flow_token(_poll_secret) or str(response.get("handoff", "")) != HANDOFF_METHOD:
			_fail(I18n.t("Odpowiedź serwera jest niepełna. Spróbuj ponownie."))
			return
		_expires_at_ms = Time.get_ticks_msec() + mini(FLOW_LIFETIME_MS, maxi(1, int(response.get("expires_in", 900))) * 1000)
		_resend_at_ms = Time.get_ticks_msec() + clampi(int(response.get("resend_after", 60)), 60, 900) * 1000
		_poll_seconds = clampf(float(response.get("poll_after", 3.0)), 3.0, 30.0)
		_deadline.start(float(_expires_at_ms - Time.get_ticks_msec()) / 1000.0)
		_native_bridge.call("setExpectedFlow", _flow_id)
		_owns_native_flow = true
		phase = "waiting"
		_timer.start(_poll_seconds)
		changed.emit()
	elif kind == "status":
		var status: String = str(response.get("status", ""))
		if status in ["ready", "needs_name"] and _handoff_ticket.is_empty():
			_fail(I18n.t("Odpowiedź serwera jest niepełna. Spróbuj ponownie."))
			return
		if status == "needs_name":
			if not _flow_player_id.is_empty():
				_fail(I18n.t("Ten adres e-mail nie jest połączony z tym imperium."))
				return
			phase = "needs_name"
			needs_name.emit()
		elif status == "ready":
			complete()
		elif status == "pending":
			_timer.start(_poll_seconds)
			changed.emit()
		else:
			_fail(I18n.t("Link do logowania wygasł. Wyślij nowy link."))
	elif kind == "complete":
		if not response.get("state") is Dictionary or str(response.get("token", "")).is_empty():
			_fail(I18n.t("Odpowiedź serwera jest niepełna. Spróbuj ponownie."))
			return
		if not _flow_player_id.is_empty() and str(response["state"].get("player", {}).get("id", "")) != _flow_player_id:


			if host.has_method("_revoke_logged_out_session"):
				host.call("_revoke_logged_out_session", _flow_origin, str(response["token"]))
			_fail(I18n.t("Ten adres e-mail nie jest połączony z tym imperium."))
			return
		cancel()
		completed.emit(response)


func _is_flow_token(value: String) -> bool:
	if value.length() < 16 or value.length() > 256:
		return false
	for character: String in value:
		if not (character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"):
			return false
	return true


func _accept_native_return(uri: String) -> bool:
	if phase != "waiting" or not _owns_native_flow or not _same_account() or str(host.server_url) != _flow_origin or _expired() or uri.length() > 700 or not uri.begins_with(RETURN_PREFIX):
		return false
	var fields: Dictionary = {}
	for part: String in uri.substr(RETURN_PREFIX.length()).split("&"):
		var pair: PackedStringArray = part.split("=")
		if pair.size() != 2 or pair[0] not in ["flow_id", "handoff_ticket"] or fields.has(pair[0]) or not _is_flow_token(pair[1]):
			return false
		fields[pair[0]] = pair[1]
	if str(fields.get("flow_id", "")) != _flow_id or not fields.has("handoff_ticket"):
		return false
	_handoff_ticket = str(fields["handoff_ticket"])
	return true


func _fail(message: String) -> void :
	cancel()
	failed.emit(message)
