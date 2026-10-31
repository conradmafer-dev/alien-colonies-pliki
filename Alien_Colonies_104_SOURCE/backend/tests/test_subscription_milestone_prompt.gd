extends SceneTree
## Offline integration test: no sessions, HTTP requests, or real Play purchases.
## godot --headless --path . --script backend/tests/test_subscription_milestone_prompt.gd
## Optional PNG directory after -- requires a display renderer, e.g. xvfb-run.

class FakeBilling:
	extends Node
	signal changed
	signal trial_purchase_result(status: String, message: String)
	var available: bool = true
	var trial: bool = true
	var price: String = "4,99 zł"
	var pending: bool = false
	var trial_calls: int = 0
	var paid_calls: int = 0
	var cancel_calls: int = 0
	func is_available() -> bool:
		return available and not pending
	func has_trial_offer() -> bool:
		return trial and not pending
	func formatted_price() -> String:
		return price
	func is_trial_purchase_pending() -> bool:
		return pending
	func status_text() -> String:
		return "Refreshing eligible offer…" if pending else ""
	func purchase_trial_subscription() -> void:
		trial_calls += 1
		pending = true
		changed.emit()
	func purchase_subscription() -> void:
		paid_calls += 1
	func cancel_trial_subscription_purchase() -> void:
		if pending:
			pending = false
			cancel_calls += 1
			trial_purchase_result.emit("cancelled", "")
	func finish(result: String, message: String = "") -> void:
		pending = false
		trial_purchase_result.emit(result, message)
		changed.emit()


class FakeDetails:
	extends RefCounted
	var opened: bool = false
	func details_open() -> bool:
		return opened


class FakePicker:
	extends Control
	var opened: bool = false
	func is_open() -> bool:
		return opened


class FakeHost:
	extends Control
	var queue_billing = FakeBilling.new()
	var compact_ui = FakeDetails.new()
	var planet_picker = FakePicker.new()
	var player_activity: Dictionary = {"foreground": true}
	var state: Dictionary = {}
	var session_token: String = "offline-test-session"
	var server_url: String = "http://127.0.0.1:1"
	var selected_planet: String = "planet-test"
	var requested_planet: String = ""
	var request_pending: bool = false
	var uncertain_action: Dictionary = {}
	var received_at_msec: int = 100
	var showing_login: bool = false
	var update_required: bool = false
	var release_open: bool = false
	var skill_open: bool = false
	var current_tab: int = 0
	var connection_editing: bool = false
	var refreshing: bool = false
	var pending_language: String = ""
	var mobile_insets: Vector4i = Vector4i(18, 18, 18, 18)
	var interacting: bool = false
	var needs_race: bool = false
	var update_overlay: Control
	var race_screen: Control
	var communications: Control
	var alliance_ui: Control
	var cancel_project_dialog: Control
	var google_reauth_dialog: Control
	var email_reauth_dialog: Control
	var options_panel: VBoxContainer
	var review_prompt: Dictionary = {}
	var login_announcement: Dictionary = {}
	var requests: Array[Dictionary] = []
	var next_id: int = 0
	func _ready() -> void:
		add_child(queue_billing)
		add_child(planet_picker)
		update_overlay = _hidden_control()
		race_screen = _hidden_control()
		communications = _hidden_control()
		alliance_ui = _hidden_control()
		cancel_project_dialog = _hidden_control()
		google_reauth_dialog = _hidden_control()
		email_reauth_dialog = _hidden_control()
		review_prompt = {"overlay": _hidden_control()}
		login_announcement = {"panel": _hidden_control()}
		var options: Control = _hidden_control()
		options_panel = VBoxContainer.new()
		options.add_child(options_panel)
	func _hidden_control() -> Control:
		var result: Control = Control.new()
		add_child(result)
		result.hide()
		return result
	func _needs_race_choice() -> bool:
		return needs_race
	func _ui_interacting() -> bool:
		return interacting
	func _new_request_id() -> String:
		next_id += 1
		return "offline-claim-%d" % next_id
	func _request(path: String, payload: Dictionary, kind: String) -> void:
		requests.append({"path": path, "payload": payload.duplicate(true), "kind": kind})
	func _button(text: String, callback: Callable, _primary: bool = false) -> Button:
		var result: Button = Button.new()
		result.text = text
		result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		result.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		result.pressed.connect(callback)
		return result


var failures: Array[String] = []
var checks: int = 0
var host: FakeHost
var prompt
var session_index: int = 0


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures.append(description)
		push_error(description)


func _settle() -> void:
	for _frame: int in range(8):
		await process_frame


func _eligible() -> Dictionary:
	return {"eligible": true, "completed_builds": 6, "milestone": 6, "shown": false, "claim_request_id": ""}


func _new_session() -> void:
	session_index += 1
	host.session_token = "offline-session-%d" % session_index
	host.state = {"player": {"id": "offline-player"}, "premium": {"queue_planning_active": false}, "subscription_prompt": _eligible()}
	host.showing_login = false
	host.current_tab = 0
	host.queue_billing.available = true
	host.queue_billing.trial = true
	host.received_at_msec += 10
	prompt._tick()


func _acknowledge(fresh: bool = true) -> void:
	host.state["subscription_prompt"] = {
		"eligible": false, "completed_builds": 6, "milestone": 6,
		"shown": true, "claim_request_id": prompt._pending_request_id,
	}
	if fresh:
		host.received_at_msec += 1
	prompt._tick()


func _open_fresh() -> void:
	_new_session()
	_acknowledge()
	_expect(prompt.is_open(), "Fresh server claim opens the trial invitation")


func _run() -> void:
	root.size = Vector2i(450, 800)
	root.content_scale_size = Vector2i(450, 800)
	root.get_node("I18n").set_locale("pl", false)
	host = FakeHost.new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	host.state = {"player": {"id": "offline-player"}, "premium": {}, "subscription_prompt": {"eligible": false, "completed_builds": 5}}
	# Load after autoload startup; --script preloads run before I18n is registered.
	var prompt_script: GDScript = load("res://client/scripts/subscription_milestone_prompt.gd")
	prompt = prompt_script.new()
	prompt.name = "SubscriptionMilestonePrompt"
	host.add_child(prompt)
	await _settle()
	prompt.set_process(false)
	prompt._tick()
	_expect(host.requests.is_empty(), "Five completed construction jobs do not trigger a claim")
	host.state["subscription_prompt"] = _eligible()
	host.current_tab = 2
	prompt._tick()
	_expect(host.requests.is_empty(), "Fleet screen is not interrupted")
	host.current_tab = 0
	host.compact_ui.opened = true
	prompt._tick()
	_expect(host.requests.is_empty(), "Details and fleet destination dialogs postpone the invitation")
	host.compact_ui.opened = false
	host.review_prompt.overlay.show()
	prompt._tick()
	_expect(host.requests.is_empty(), "Review invitation has priority over subscription invitation")
	host.review_prompt.overlay.hide()
	host.planet_picker.opened = true
	prompt._tick()
	_expect(host.requests.is_empty(), "Planet picker postpones the invitation")
	host.planet_picker.opened = false
	host.interacting = true
	prompt._tick()
	_expect(host.requests.is_empty(), "A live touch/scroll gesture is not interrupted")
	host.interacting = false
	host.queue_billing.trial = false
	prompt._tick()
	_expect(host.requests.is_empty(), "Paid-only Play offer never triggers a free-trial invitation")
	host.queue_billing.trial = true
	host.queue_billing.price = ""
	prompt._tick()
	_expect(host.requests.is_empty(), "Missing recurring price blocks the invitation")
	host.queue_billing.price = "4,99 zł"
	host.request_pending = true
	prompt._tick()
	_expect(host.requests.is_empty(), "Existing command is not interrupted by the claim")
	host.request_pending = false
	host.player_activity.foreground = false
	prompt._tick()
	_expect(host.requests.is_empty(), "Background application cannot claim an invitation")
	host.player_activity.foreground = true
	prompt._tick()
	prompt._tick()
	_expect(host.requests.size() == 1, "Six completed jobs send only one claim while waiting")
	_expect(host.requests[0].payload.type == "subscription_prompt" and host.requests[0].payload.choice == "show", "Claim uses the existing signed action command pipeline")
	_expect(not prompt.is_open(), "Local eligibility never displays before server acknowledgement")
	host.state["subscription_prompt"] = {"shown": true, "claim_request_id": "other-device-won"}
	host.received_at_msec += 1
	prompt._tick()
	_expect(not prompt.is_open(), "Another device's successful claim is not shown here")
	_new_session()
	_acknowledge(false)
	_expect(not prompt.is_open(), "Matching claim in a stale snapshot is insufficient")
	host.received_at_msec += 1
	host.review_prompt.overlay.show()
	prompt._tick()
	_expect(not prompt.is_open(), "A review shown during claim remains uninterrupted")
	host.review_prompt.overlay.hide()
	prompt._tick()
	await _settle()
	_expect(prompt.is_open(), "Eligible claim waits for the planet screen to be safe")
	_expect(prompt.terms.text.contains("4,99 zł"), "Recurring price comes from Play, including its localized currency")
	_expect(prompt.trial_button.text == root.get_node("I18n").t("Wypróbuj 7 dni za darmo"), "Primary CTA uses the exact localized seven-day-trial wording")
	_expect(not quit_on_go_back, "Android Back cannot quit the app while the invitation is open")
	var bounds: Rect2 = Rect2(Vector2.ZERO, host.size)
	_expect(bounds.encloses(prompt.card.get_global_rect()), "Invitation card fits within the 450×800 viewport")
	_expect(prompt.card.get_global_rect().encloses(prompt.trial_button.get_global_rect()), "Trial CTA remains fully visible at 450×800")
	_expect(prompt.card.get_global_rect().encloses(prompt.later_button.get_global_rect()), "Maybe later remains fully visible at 450×800")
	_expect(prompt.card.get_global_rect().encloses(prompt.terms.get_global_rect()), "Recurring terms remain fully visible at 450×800")
	_expect(prompt.artwork.texture != null and prompt.artwork.texture.get_width() == 1536, "Real premium artwork is used")
	var screenshots: PackedStringArray = OS.get_cmdline_user_args()
	if not screenshots.is_empty() and DisplayServer.get_name() != "headless":
		DirAccess.make_dir_recursive_absolute(screenshots[0])
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(screenshots[0].path_join("subscription_prompt_450x800.png"))
	_expect(prompt.handle_back(), "Back closes the invitation")
	await _settle()
	_expect(not prompt.is_open() and quit_on_go_back, "Closing restores the prior Back behavior")
	var count_after_dismiss: int = host.requests.size()
	prompt._tick()
	_expect(host.requests.size() == count_after_dismiss and not prompt.is_open(), "Dismissed invitation is not repeated in the session")

	_new_session()
	host.queue_billing.trial = false
	_acknowledge()
	_expect(not prompt.is_open(), "Trial eligibility lost during the claim prevents display")
	_new_session()
	host.state["premium"]["queue_planning_active"] = true
	_acknowledge()
	_expect(not prompt.is_open(), "Newly active premium suppresses a pending invitation")

	_open_fresh()
	prompt.trial_button.pressed.emit()
	_expect(host.queue_billing.trial_calls == 1 and host.queue_billing.paid_calls == 0, "Click calls the trial-only billing method, never the paid checkout")
	_expect(prompt.is_open() and prompt.trial_button.disabled, "Popup stays visible while fresh Play eligibility is checked")
	prompt._tick()
	_expect(prompt.is_open(), "Temporary has_trial_offer=false during refresh does not dismiss the popup")
	prompt.later_button.pressed.emit()
	_expect(not prompt.is_open() and not host.queue_billing.pending and host.queue_billing.cancel_calls == 1, "Maybe later cancels a delayed billing launch")
	host.queue_billing.finish("started")
	_expect(not prompt.is_open(), "Late billing result cannot reopen a dismissed invitation")

	_open_fresh()
	prompt.trial_button.pressed.emit()
	host.queue_billing.finish("unavailable", "The seven-day trial is no longer available.")
	_expect(prompt.is_open() and not prompt.trial_button.visible, "Lost eligibility presents an explanation without a false free-trial CTA")
	_expect(prompt.status.visible and not prompt.terms.visible and host.queue_billing.paid_calls == 0, "Unavailable trial never falls back to a paid offer")
	prompt.close_button.pressed.emit()
	_open_fresh()
	prompt.trial_button.pressed.emit()
	host.queue_billing.finish("started")
	_expect(not prompt.is_open(), "Opening the Play purchase sheet dismisses the invitation")

	_open_fresh()
	prompt.trial_button.pressed.emit()
	host.session_token = ""
	host.showing_login = true
	prompt._process(0.01)
	_expect(not prompt.is_open() and not host.queue_billing.pending, "Logout immediately cancels the popup and pending checkout")
	_new_session()
	var obsolete_id: String = prompt._pending_request_id
	host.session_token = "different-session-with-stale-claim"
	host.state["subscription_prompt"] = {"shown": true, "claim_request_id": obsolete_id}
	host.received_at_msec += 1
	prompt._tick()
	_expect(not prompt.is_open(), "Acknowledgement from a previous login is ignored")
	_open_fresh()
	host.state["premium"]["queue_planning_active"] = true
	prompt._process(0.01)
	_expect(not prompt.is_open(), "Subscription activation closes an already visible invitation immediately")
	await _settle()
	host.free()
	await _settle()
	print("Subscription milestone prompt: %d checks, %d failures" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
