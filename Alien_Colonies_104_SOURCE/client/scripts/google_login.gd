extends Node



signal configuration_changed
signal changed
signal needs_name
signal completed(response: Dictionary, mode: String)
signal failed(message: String)
signal cancelled

const FLOW_LIFETIME_MS: int = 600000
const NATIVE_POLL_SECONDS: float = 0.15

var host: Node
var configured: bool = false
var configuration_loaded: bool = false
var require_google_registration: bool = false
var phase: String = ""
var mode: String = ""
var _native_bridge: Object
var _owns_native_request: bool = false
var _native_verified: bool = false
var _request_node: HTTPRequest
var _request_kind: String = ""
var _request_generation: int = 0
var _timer: Timer
var _deadline: Timer
var _flow_id: String = ""
var _poll_secret: String = ""
var _flow_origin: String = ""
var _flow_session: String = ""
var _flow_player_id: String = ""
var _expires_at_ms: int = 0
var _completing_registration: bool = false


func setup(owner_node: Node) -> void :
	host = owner_node
	host.add_child(self)
	if Engine.has_singleton("AlienGoogleAuth"):
		_native_bridge = Engine.get_singleton("AlienGoogleAuth")
	_timer = Timer.new()
	_timer.one_shot = true
	_timer.wait_time = NATIVE_POLL_SECONDS
	add_child(_timer)
	_timer.timeout.connect(_poll)
	_deadline = Timer.new()
	_deadline.one_shot = true
	add_child(_deadline)
	_deadline.timeout.connect( func() -> void : _fail(I18n.t("Logowanie Google wygasło. Spróbuj ponownie.")))


func load_configuration() -> void :
	if is_active() or is_request_pending() or str(host.server_url).is_empty():
		return
	configured = false
	configuration_loaded = false
	_send("config", "/api/auth/google/config", {}, HTTPClient.METHOD_GET)
	changed.emit()


func is_active() -> bool:
	return not phase.is_empty()


func is_request_pending() -> bool:
	return not _request_kind.is_empty()


func waiting_for_name() -> bool:
	return phase == "needs_name"


func start(next_mode: String = "login", password: String = "", expected_player_id: String = "") -> void :
	if not configured or next_mode not in ["login", "link"]:
		return
	cancel()
	if not _native_sign_in_available():
		_fail(I18n.t("Moduł logowania Google jest niedostępny w aplikacji."))
		return
	mode = next_mode
	_flow_origin = str(host.server_url)
	var bind_current_empire: bool = mode == "link" or not expected_player_id.is_empty()
	_flow_session = str(host.session_token) if bind_current_empire else ""
	_flow_player_id = str(host.state.get("player", {}).get("id", "")) if bind_current_empire else ""
	if bind_current_empire and (_flow_session.is_empty() or _flow_player_id.is_empty() or ( not expected_player_id.is_empty() and expected_player_id != _flow_player_id)):
		_fail(I18n.t("Zaloguj się ponownie przed zmianą ustawień konta."))
		return
	phase = "starting"
	_expires_at_ms = Time.get_ticks_msec() + FLOW_LIFETIME_MS
	_deadline.start(float(FLOW_LIFETIME_MS) / 1000.0)
	var payload: Dictionary = {"mode": mode, "client": "android"}
	if mode == "link":
		payload["password"] = password
	_send("start", "/api/auth/google/native/start", payload)
	changed.emit()


func complete(empire_name: String = "") -> void :
	if not _native_verified or phase not in ["verified", "needs_name"] or is_request_pending() or _flow_id.is_empty() or _expired():
		return
	if mode == "login" and not _flow_player_id.is_empty() and not empire_name.is_empty():
		_fail(I18n.t("Wybrane konto Google nie należy do tego imperium. Wybierz właściwe konto."))
		return
	var payload: Dictionary = _proof()
	_completing_registration = phase == "needs_name"
	if not empire_name.is_empty():
		payload["name"] = empire_name
	phase = "completing"
	_send("complete", "/api/auth/google/complete", payload)
	changed.emit()


func cancel() -> void :
	_stop_transport()
	if _timer != null:
		_timer.stop()
	if _deadline != null:
		_deadline.stop()
	if (_owns_native_request or is_active()) and is_instance_valid(_native_bridge):
		_native_bridge.call("cancelGoogleSignIn")
	_owns_native_request = false
	_native_verified = false
	phase = ""
	mode = ""
	_flow_id = ""
	_poll_secret = ""
	_flow_origin = ""
	_flow_session = ""
	_flow_player_id = ""
	_expires_at_ms = 0
	_completing_registration = false
	changed.emit()


func clear_account_state() -> void :


	cancel()
	if _native_sign_in_available():
		_native_bridge.call("clearGoogleSignInState")


func _exit_tree() -> void :
	cancel()


func _notification(what: int) -> void :
	if what == NOTIFICATION_APPLICATION_RESUMED and phase == "waiting":
		_poll.call_deferred()


func _proof() -> Dictionary:
	return {"flow_id": _flow_id, "poll_secret": _poll_secret}


func _expired() -> bool:
	if _expires_at_ms > 0 and Time.get_ticks_msec() >= _expires_at_ms:
		_fail(I18n.t("Logowanie Google wygasło. Spróbuj ponownie."))
		return true
	return false


func _same_account() -> bool:
	return str(host.session_token) == _flow_session and str(host.state.get("player", {}).get("id", "")) == _flow_player_id


func _poll() -> void :

	if phase != "waiting" or not _owns_native_request or is_request_pending() or _expired():
		return
	if not _same_account() or str(host.server_url) != _flow_origin:
		cancel()
		return
	var raw: String = str(_native_bridge.call("takePendingGoogleSignIn"))
	if not raw.is_empty():
		_accept_native_result(raw)
	if phase == "waiting":
		_timer.start(NATIVE_POLL_SECONDS)


func _accept_native_result(raw: String) -> bool:
	if phase != "waiting" or not _owns_native_request or not _same_account() or str(host.server_url) != _flow_origin or _expired() or raw.length() > 20000:
		return false
	var parser: JSON = JSON.new()
	if parser.parse(raw) != OK or not parser.data is Dictionary:
		return false
	var response: Dictionary = parser.data
	if str(response.get("request_id", "")) != _flow_id:
		return false
	var status: String = str(response.get("status", ""))
	if status == "cancelled":
		cancel()
		cancelled.emit()
		return true
	if status == "error":
		var unavailable: bool = str(response.get("error_code", "")) in ["activity_unavailable", "provider_unavailable", "unsupported"]
		_fail(I18n.t("Usługa logowania Google jest niedostępna na tym urządzeniu.") if unavailable else I18n.t("Nie udało się połączyć z Google. Spróbuj ponownie."))
		return true
	if status != "success" or not response.get("id_token") is String or not _is_id_token(response["id_token"]):
		_fail(I18n.t("Nie udało się połączyć z Google. Spróbuj ponownie."))
		return true
	var payload: Dictionary = _proof()
	payload["id_token"] = response["id_token"]
	phase = "verifying"
	_send("verify", "/api/auth/google/native/verify", payload)
	changed.emit()
	return true


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
	var headers: PackedStringArray = PackedStringArray(["Content-Type: application/json", "Accept: application/json", "Accept-Language: " + I18n.locale, "X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE), "X-PGR-Client-Platform: android"])
	if mode == "link" and not _flow_session.is_empty():
		headers.append("Authorization: Bearer " + _flow_session)
	var origin: String = str(host.server_url) if kind == "config" else _flow_origin
	var body: String = "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
	var error: Error = _request_node.request(origin + path, headers, method, body)
	if error != OK:
		_stop_transport()
		if kind == "config":
			_set_configuration(false, false)
		else:
			_fail(I18n.t("Nie udało się połączyć z Google. Spróbuj ponownie."))


func _stop_transport() -> void :
	_request_generation += 1
	_request_kind = ""
	if is_instance_valid(_request_node):
		_request_node.cancel_request()
		_request_node.queue_free()
	_request_node = null


func _set_configuration(available: bool, required: bool) -> void :
	configured = available
	configuration_loaded = true
	require_google_registration = available and required
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
	var parsed: Variant = parser.data if not body.is_empty() and parser.parse(body.get_string_from_utf8()) == OK else null
	var valid: bool = result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300 and parsed is Dictionary and bool(parsed.get("ok", false))
	if kind == "config":
		_set_configuration(valid and bool(parsed.get("native_configured", false)), valid and bool(parsed.get("require_google_registration", false)))
		return
	if response_code == 426:
		cancel()
		host._handle_required_update(parsed.get("update") if parsed is Dictionary else null)
		return
	if not valid:

		if kind == "complete" and mode == "login" and _completing_registration and parsed is Dictionary and response_code in [400, 409]:
			phase = "needs_name"
			changed.emit()
			failed.emit(host._server_text(parsed.get("error", I18n.t("Wybierz inną nazwę imperium."))))
			return
		_fail(host._server_text(parsed.get("error", I18n.t("Nie udało się połączyć z Google. Spróbuj ponownie."))) if parsed is Dictionary else I18n.t("Nie udało się połączyć z Google. Spróbuj ponownie."))
		return
	var response: Dictionary = parsed
	if kind == "start":
		_flow_id = str(response.get("flow_id", ""))
		_poll_secret = str(response.get("poll_secret", ""))
		var nonce: String = str(response.get("nonce", ""))
		var client_id: String = str(response.get("server_client_id", ""))
		if not _is_flow_token(_flow_id) or not _is_flow_token(_poll_secret) or not _is_flow_token(nonce) or not _is_client_id(client_id):
			_fail(I18n.t("Odpowiedź serwera jest niepełna. Spróbuj ponownie."))
			return
		_expires_at_ms = Time.get_ticks_msec() + mini(FLOW_LIFETIME_MS, maxi(1, int(response.get("expires_in", 600))) * 1000)
		_deadline.start(float(_expires_at_ms - Time.get_ticks_msec()) / 1000.0)
		phase = "waiting"
		_owns_native_request = true
		changed.emit()
		_open_native_after_layout(_flow_id, client_id, nonce)
	elif kind == "verify":
		var status: String = str(response.get("status", ""))
		if phase != "verifying" or status not in ["ready", "needs_name"]:
			_fail(I18n.t("Odpowiedź serwera jest niepełna. Spróbuj ponownie."))
			return
		_native_verified = true
		if status == "needs_name":
			if not _flow_player_id.is_empty():
				_fail(I18n.t("Wybrane konto Google nie należy do tego imperium. Wybierz właściwe konto."))
				return
			phase = "needs_name"
			needs_name.emit()
		else:
			phase = "verified"
			complete()
	elif kind == "complete":
		if not _native_verified or not response.get("state") is Dictionary or str(response.get("token", "")).is_empty():
			_fail(I18n.t("Odpowiedź serwera jest niepełna. Spróbuj ponownie."))
			return
		if not _flow_player_id.is_empty() and str(response["state"].get("player", {}).get("id", "")) != _flow_player_id:
			if host.has_method("_revoke_logged_out_session"):
				host.call("_revoke_logged_out_session", _flow_origin, str(response["token"]))
			_fail(I18n.t("Wybrane konto Google nie należy do tego imperium. Wybierz właściwe konto."))
			return
		var completed_mode: String = "reauthenticate" if mode == "login" and not _flow_player_id.is_empty() else mode
		cancel()
		completed.emit(response, completed_mode)


func _open_native_after_layout(expected_flow: String, client_id: String, nonce: String) -> void :
	await get_tree().process_frame
	await get_tree().process_frame
	if phase != "waiting" or not _owns_native_request or expected_flow != _flow_id or _expired():
		return
	if not _same_account() or str(host.server_url) != _flow_origin:
		cancel()
		return
	_native_bridge.call("beginGoogleSignIn", expected_flow, client_id, nonce)
	_timer.start(NATIVE_POLL_SECONDS)


func _native_sign_in_available() -> bool:

	return is_instance_valid(_native_bridge) and int(_native_bridge.call("getGoogleSignInVersion")) >= 1


func _is_flow_token(value: String) -> bool:
	if value.length() < 16 or value.length() > 256:
		return false
	for character: String in value:
		if not (character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"):
			return false
	return true


func _is_client_id(value: String) -> bool:
	if value.length() > 256 or not value.ends_with(".apps.googleusercontent.com"):
		return false
	for character: String in value:
		if not (character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"):
			return false
	return value.length() > ".apps.googleusercontent.com".length()


func _is_id_token(value: String) -> bool:
	if value.length() < 32 or value.length() > 16384 or value.count(".") != 2:
		return false
	for part: String in value.split("."):
		if part.is_empty():
			return false
		for character: String in part:
			if not (character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"):
				return false
	return true


func _fail(message: String) -> void :
	cancel()
	failed.emit(message)
