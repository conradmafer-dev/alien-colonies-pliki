extends HTTPRequest
## An old session is revoked independently of the active client/account.
## Owned by the scene root so changing language cannot cancel the revocation.

const AuthTiming = preload("res://client/scripts/auth_timing.gd")
var started_msec: int = 0

func _ready() -> void:
	started_msec = Time.get_ticks_msec()
	name = "SessionRevocation"
	timeout = 15.0
	max_redirects = 0
	# Older servers include a complete state snapshot in their logout response.
	body_size_limit = 1048576
	process_mode = Node.PROCESS_MODE_ALWAYS
	request_completed.connect(_on_revocation_completed)


func _on_revocation_completed(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	# Success, server rejection and timeout all clean up without touching a client.
	AuthTiming.record("logout", {"network_ms": Time.get_ticks_msec() - started_msec}, result, response_code)
	queue_free()
