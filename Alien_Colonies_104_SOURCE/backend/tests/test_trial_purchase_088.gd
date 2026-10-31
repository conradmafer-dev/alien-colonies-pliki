extends SceneTree
## Headless integration tests for the trial-only checkout entry point.
## Uses the production offer validator and billing controller, a fake native
## bridge, and a fake game host. No game scene, network or real purchases.
## Run with a disposable XDG_DATA_HOME containing "alien-trial-".

var billing_script: Script

class FakeHost extends Node:
	var session_token: String = "fake-session-a"
	var polls: int = 0
	func _poll(_force: bool) -> void:
		polls += 1

class FakeBilling extends Node:
	var provider_ready: bool = true
	var queries: int = 0
	var account: String = ""
	var launches: Array[Dictionary] = []
	var launch_code: int = 0
	func is_ready() -> bool:
		return provider_ready
	func set_obfuscated_account_id(value: String) -> void:
		account = value
	func query_product_details(_ids: PackedStringArray, _type: int) -> void:
		queries += 1
	func query_purchases(_type: int, _include_suspended: bool) -> void:
		pass
	func purchase_subscription(product: String, plan: String, offer: String, _personalized: bool) -> Dictionary:
		launches.append({"product": product, "plan": plan, "offer": offer, "account": account})
		return {"response_code": launch_code}

var checks: int = 0
var failures: int = 0

func _initialize() -> void:
	_run.call_deferred()

func _expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(message)

func _state(account: String = "a", active: bool = false) -> Dictionary:
	return {
		"player": {"id": "player-" + account},
		"premium": {
			"billing_account_id": "billing-" + account,
			"provider_ready": true,
			"supported_base_plan_ids": ["monthly", "weekly"],
			"queue_planning_active": active,
		},
	}

func _details(trial: bool = true, free_period: String = "P7D") -> Dictionary:
	var paid: Dictionary = {
		"billing_period": "P1W", "recurrence_mode": 1,
		"billing_cycle_count": 0, "price_amount_micros": 4990000,
		"formatted_price": "4,99 zł", "price_currency_code": "PLN",
	}
	var offers: Array[Dictionary] = [{
		"base_plan_id": "weekly", "offer_id": null,
		"offer_token": "fake-base-token", "pricing_phases": [paid],
	}]
	if trial:
		offers.append({
			"base_plan_id": "weekly", "offer_id": "trial-7d",
			"offer_token": "fake-trial-token",
			"pricing_phases": [{
				"billing_period": free_period, "recurrence_mode": 2,
				"billing_cycle_count": 1, "price_amount_micros": 0,
				"formatted_price": "Bezpłatnie", "price_currency_code": "PLN",
			}, paid],
		})
	return {"response_code": 0, "product_details": [{
		"product_id": "queue_planner", "subscription_offer_details": offers,
	}]}

func _fixture() -> Dictionary:
	var host: FakeHost = FakeHost.new()
	root.add_child(host)
	var service: Node = billing_script.new()
	service.setup(host)
	var bridge: FakeBilling = FakeBilling.new()
	service.add_child(bridge)
	service._billing = bridge
	service.apply_server_state(_state())
	service._on_product_details(_details())
	var outcomes: Array[String] = []
	service.trial_purchase_result.connect(func(status: String, _message: String) -> void: outcomes.append(status))
	return {"host": host, "service": service, "bridge": bridge, "outcomes": outcomes}

func _happy_path() -> void:
	var f: Dictionary = _fixture()
	var service: Node = f.service
	_expect(service.is_available() and service.has_trial_offer(), "Valid current trial is available")
	_expect(service.formatted_price() == "4,99 zł", "Displayed price is the paid weekly renewal")
	service.purchase_trial_subscription()
	_expect(f.bridge.queries == 2 and f.bridge.launches.is_empty(), "Click always refreshes before opening checkout")
	_expect(service.is_trial_purchase_pending() and not service.is_available(), "Refresh disables repeat purchase")
	_expect(not service.has_trial_offer(), "Old cached trial is cleared during refresh")
	service.purchase_trial_subscription()
	_expect(f.bridge.queries == 2, "Double click does not create another refresh")
	service._on_product_details(_details(true, "P1W"))
	_expect(f.bridge.launches == [{"product": "queue_planner", "plan": "weekly", "offer": "trial-7d", "account": "billing-a"}], "Only the exact refreshed trial is passed to the native bridge")
	_expect(f.outcomes == ["started"] and not service.is_trial_purchase_pending(), "Reports checkout launch once")
	_expect(service._purchase_busy, "Checkout remains busy until existing purchase callback")
	service.cancel_trial_subscription_purchase()
	_expect(f.outcomes == ["started"] and service._purchase_busy, "Closing popup cannot cancel an opened Play sheet")
	service._on_purchase_updated({"response_code": 1})
	_expect(not service._purchase_busy, "Existing Play cancellation callback releases checkout")
	f.host.free()

func _trial_disappears() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service._on_product_details(_details(false))
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["unavailable"], "Paid base plan never replaces a disappeared trial")
	_expect(not f.service.is_trial_purchase_pending(), "Unavailable trial releases refresh state")
	f.service.purchase_subscription()
	_expect(f.bridge.launches.size() == 1 and f.bridge.launches[0].offer == "", "Existing standard subscription purchase remains available independently")
	f.host.free()

func _failed_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service._on_product_details({"response_code": 12, "product_details": _details().product_details})
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["error"], "Refresh error cannot reuse either cached or error-response trial data")
	_expect(not f.service.has_trial_offer() and not f.service.is_trial_purchase_pending(), "Refresh error clears trial availability and busy state")
	f.host.free()

func _wrong_trial_duration() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service._on_product_details(_details(true, "P14D"))
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["unavailable"], "Trial with changed duration cannot satisfy seven-day CTA")
	f.host.free()

func _cancel_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service.cancel_trial_subscription_purchase()
	f.service.cancel_trial_subscription_purchase()
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["cancelled"], "Closing popup cancels once and late valid details do not purchase")
	_expect(not f.service.is_trial_purchase_pending(), "Cancelled refresh is no longer pending")
	f.host.free()

func _logout_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.host.session_token = ""
	f.service.sign_out()
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["cancelled"], "Logout revokes a queued trial purchase")
	_expect(not f.service.has_trial_offer() and f.bridge.account.is_empty(), "Old account offer remains unavailable after logout")
	f.host.free()

func _switch_account_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.host.session_token = "fake-session-b"
	f.service.apply_server_state(_state("b"))
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and not f.service.has_trial_offer(), "Old account reply is drained without enabling the new account")
	_expect(f.bridge.queries == 3, "New account query waits for the untagged old response")
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["cancelled"], "New account offer never revives previous account checkout")
	f.host.free()

func _changed_session_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.host.session_token = "fake-replacement-session"
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["cancelled"], "Session change cancels checkout even before server-state update")
	f.host.free()

func _timeout_and_late_reply() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service._on_trial_refresh_timeout()
	_expect(f.service._details_in_flight and not f.service.is_trial_purchase_pending(), "Timeout cancels checkout but preserves untagged request serialization")
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["error"], "Late success after timeout never opens Play")
	f.service.purchase_trial_subscription()
	_expect(f.bridge.queries == 3 and f.bridge.launches.is_empty(), "Explicit retry requires a new query after draining late reply")
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.size() == 1 and f.outcomes == ["error", "started"], "Only newly authorized retry launches after its own response")
	f.host.free()

func _refresh_requested_again() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service.restore_purchases()
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.bridge.queries == 3, "Pending background refresh drains older valid response without purchasing")
	f.service._on_product_details(_details(false))
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["unavailable"], "Newest serialized response controls trial eligibility")
	f.host.free()

func _disconnect_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.bridge.provider_ready = false
	f.service._on_disconnected()
	f.bridge.provider_ready = true
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["error"], "Disconnect cancels checkout even if a valid reply arrives later")
	f.host.free()

func _premium_during_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service.apply_server_state(_state("a", true))
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["unavailable"], "Authoritative premium activation cancels queued trial")
	f.host.free()

func _native_launch_failure() -> void:
	var f: Dictionary = _fixture()
	f.bridge.launch_code = 6
	f.service.purchase_trial_subscription()
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.size() == 1 and f.bridge.launches[0].offer == "trial-7d", "Native error does not trigger another launch or a paid fallback")
	_expect(f.outcomes == ["error"] and not f.service._purchase_busy, "Native launch error releases pending state")
	f.host.free()

func _purchase_appears_during_refresh() -> void:
	var f: Dictionary = _fixture()
	f.service.purchase_trial_subscription()
	f.service._on_purchases({"response_code": 0, "purchases": [{
		"product_ids": ["queue_planner"], "purchase_state": 2,
	}]})
	f.service._on_product_details(_details())
	_expect(f.bridge.launches.is_empty() and f.outcomes == ["unavailable"], "An existing pending purchase cancels new trial checkout")
	f.host.free()

func _run() -> void:
	if not OS.get_environment("XDG_DATA_HOME").contains("alien-trial-"):
		push_error("Use a disposable XDG_DATA_HOME containing alien-trial-")
		quit(2)
		return
	billing_script = load("res://client/scripts/queue_billing.gd")
	if billing_script == null or not billing_script.can_instantiate():
		push_error("Production billing controller could not be loaded")
		quit(2)
		return
	_happy_path()
	_trial_disappears()
	_failed_refresh()
	_wrong_trial_duration()
	_cancel_refresh()
	_logout_refresh()
	_switch_account_refresh()
	_changed_session_refresh()
	_timeout_and_late_reply()
	_refresh_requested_again()
	_disconnect_refresh()
	_premium_during_refresh()
	_native_launch_failure()
	_purchase_appears_during_refresh()
	print("Trial-only billing: %d checks, %d failures" % [checks, failures])
	quit(0 if failures == 0 and checks > 0 else 1)
