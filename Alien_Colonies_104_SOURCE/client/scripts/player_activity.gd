extends RefCounted
## A pending real interaction, never a periodic keepalive. Generations preserve
## input that arrives while the previous activity-bearing request is in flight.
const MIN_INTERVAL_MSEC: int = 60000
var foreground: bool = true
var generation: int = 1
var acknowledged_generation: int = 0
var last_attempt_msec: int = -MIN_INTERVAL_MSEC


func set_foreground(value: bool) -> void:
	if value and not foreground:
		generation += 1
	foreground = value


func observe_input(event: InputEvent, recovering: bool = false) -> void:
	if not foreground or recovering or event.device < 0:
		return
	var deliberate: bool = false
	if event is InputEventScreenTouch:
		deliberate = event.pressed and not event.canceled
	elif event is InputEventMouseButton:
		deliberate = event.pressed and not event.canceled
	elif event is InputEventKey:
		deliberate = event.pressed and not event.echo
	elif event is InputEventJoypadButton:
		deliberate = event.pressed
	if deliberate:
		generation += 1


func prepare_request(path: String, authenticated: bool, now_msec: int) -> int:
	# Never send on login, revocation, configuration, or another origin/endpoint.
	if not authenticated or not foreground or path.get_slice("?", 0) != "/api/state":
		return 0
	if generation <= acknowledged_generation or now_msec - last_attempt_msec < MIN_INTERVAL_MSEC:
		return 0
	last_attempt_msec = now_msec
	return generation


func acknowledge(ticket: int, transport_ok: bool, response_code: int, response: Variant) -> void:
	if ticket <= 0 or ticket > generation or not transport_ok or response_code < 200 or response_code >= 300:
		return
	if not response is Dictionary or not bool(response.get("ok", false)):
		return
	acknowledged_generation = maxi(acknowledged_generation, ticket)


func reset_account() -> void:
	# Invalidate old request tickets. A fresh authentication itself is activity.
	generation += 1
	acknowledged_generation = generation
	last_attempt_msec = -MIN_INTERVAL_MSEC


static func production_paused(state: Dictionary) -> bool:
	return bool(state.get("production_status", {}).get("paused", false))


static func production_rate(state: Dictionary, resource: String) -> float:
	return 0.0 if production_paused(state) else float(state.get("production", {}).get(resource, 0))
