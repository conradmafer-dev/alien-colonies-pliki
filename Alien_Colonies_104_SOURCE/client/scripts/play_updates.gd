extends Node
## All executable updates stay inside the official Google Play update flow.
signal changed
var native
var status: Dictionary = {"state": "unsupported", "downloaded": 0, "total": 0}
var _last_json: String = ""
var _timer: float = 0.0


func _ready() -> void:
	if OS.get_name() == "Android" and Engine.has_singleton("AlienUpdates"):
		native = Engine.get_singleton("AlienUpdates")
		status["state"] = "checking"
		check()


func _process(delta: float) -> void:
	if native == null:
		return
	_timer += delta
	if _timer < 0.15:
		return
	_timer = 0
	var raw: String = str(native.getStatus())
	if raw == _last_json:
		return
	_last_json = raw
	var decoded: Variant = JSON.parse_string(raw)
	if decoded is Dictionary:
		status = decoded
		changed.emit()


func check() -> void:
	if native != null:
		native.checkUpdate()


func start() -> void:
	if native != null:
		native.startUpdate()


func install() -> void:
	if native != null:
		native.completeUpdate()


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_RESUMED and is_node_ready():
		check()
