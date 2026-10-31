extends Node
## Native notifications are optional. Desktop and web never request permission.
var host: Node
var native: Object
var player_owner: String = ""
var seen: Dictionary = {}
var registered_token: String = ""
var registered_session: String = ""
var busy: bool = false
var config_attempt: int = -600000
var push_config: Dictionary = {}

func setup(value: Node) -> void:
    host = value
    if OS.get_name() == "Android" and Engine.has_singleton("AlienNotifications"):
        native = Engine.get_singleton("AlienNotifications")

func clear() -> void:
    player_owner = ""
    seen.clear()
    registered_token = ""
    registered_session = ""
    if native != null:
        native.setActivePlayer("")

func sync(snapshot: Dictionary) -> void:
    if native == null:
        return
    var player: Dictionary = snapshot.get("player", {})
    var player_id: String = str(player.get("id", ""))
    if player_id.is_empty() or str(player.get("race_id", "")).is_empty():
        return
    var first: bool = player_id != player_owner
    if first:
        player_owner = player_id
        seen.clear()
        registered_token = ""
        registered_session = ""
        native.setActivePlayer(player_owner)
    native.requestPermission()
    var reports: Array = snapshot.get("reports", [])
    for index: int in range(reports.size() - 1, -1, -1):
        var report: Dictionary = reports[index]
        var id: String = str(report.get("id", ""))
        if not id.is_empty() and not seen.has(id) and not first:
            var title: String = str(report.get("title", "Alien Colonies"))
            var kind: String = "attack" if "atak" in title.to_lower() or "attack" in title.to_lower() else "report"
            native.showReport(player_owner, id, title, str(report.get("text", "")).left(300), kind)
        seen[id] = true
    var current_ids: Dictionary = {}
    for report: Dictionary in reports:
        current_ids[str(report.get("id", ""))] = true
    seen = current_ids
    if bool(native.isAllowed()) and not busy:
        _configure_and_register.call_deferred()
    var pending: String = str(native.consumeReport())
    if not pending.is_empty():
        host._open_tab.call_deferred(4)

func _configure_and_register() -> void:
    if busy or player_owner.is_empty() or not bool(native.isAllowed()):
        return
    busy = true
    var request_owner: String = player_owner
    var request_session: String = str(host.session_token)
    if Time.get_ticks_msec() - config_attempt >= 600000:
        config_attempt = Time.get_ticks_msec()
        var config: Dictionary = await _json_request("/api/notifications/config", {}, HTTPClient.METHOD_GET)
        if request_owner != player_owner or request_session != str(host.session_token):
            busy = false
            return
        push_config = config
        if bool(config.get("configured", false)):
            native.configure(JSON.stringify(config))
    var token: String = str(native.getToken())
    if not token.is_empty() and (token != registered_token or request_session != registered_session):
        var result: Dictionary = await _json_request("/api/notifications/register", {"token":token, "language":I18n.locale})
        if request_owner == player_owner and request_session == str(host.session_token) and bool(result.get("registered", false)):
            registered_token = token
            registered_session = request_session
    busy = false

func _json_request(path: String, payload: Dictionary, method: int = HTTPClient.METHOD_POST) -> Dictionary:
    if str(host.session_token).is_empty():
        return {}
    var request: HTTPRequest = HTTPRequest.new()
    request.timeout = 12.0
    request.max_redirects = 0
    add_child(request)
    var headers: PackedStringArray = PackedStringArray(["Content-Type: application/json", "Accept: application/json",
        "Authorization: Bearer " + str(host.session_token), "Accept-Language: " + I18n.locale,
        "X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE)])
    var body: String = "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
    if request.request(str(host.server_url) + path, headers, method, body) != OK:
        request.queue_free()
        return {}
    var response: Array = await request.request_completed
    request.queue_free()
    if int(response[0]) != HTTPRequest.RESULT_SUCCESS or int(response[1]) != 200:
        return {}
    var value: Variant = JSON.parse_string((response[3] as PackedByteArray).get_string_from_utf8())
    return value if value is Dictionary else {}


var intent_elapsed: float = 0.0

func _process(delta: float) -> void:
    intent_elapsed += delta
    if intent_elapsed < 0.25 or native == null or player_owner.is_empty():
        return
    intent_elapsed = 0.0
    var pending: String = str(native.consumeReport())
    if not pending.is_empty():
        host._open_tab.call_deferred(4)
