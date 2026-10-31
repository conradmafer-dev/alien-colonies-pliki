extends Node
## Google Play is the source of displayed prices. The server is the only source
## of queue privileges. Purchase tokens are kept in memory and never logged.

signal changed
## Reports only the trial checkout launch, not a granted subscription.
signal trial_purchase_result(status: String, message: String)

const PlayBilling = preload("res://addons/GodotGooglePlayBilling/BillingClient.gd")
const Offer = preload("res://client/scripts/queue_subscription_offer.gd")
const PRODUCT_ID: String = "queue_planner"
const BASE_PLAN_ID: String = "weekly"
const PACKAGE_NAME: String = "com.conradmafer.aliencolonies"
const TRIAL_REFRESH_TIMEOUT: float = 20.0

var host: Node
var _billing: Node
var _verification: HTTPRequest
var _retry_timer: Timer
var _trial_refresh_timer: Timer
var _trial_purchase_pending: bool = false
var _trial_purchase_epoch: int = -1
var _trial_purchase_session: String = ""
var _price: String = ""
var _trial_price: String = ""
var _offer_id: String = ""
var _has_trial: bool = false
var _status: String = ""
var _offer_ready: bool = false
var _purchase_busy: bool = false
var _verification_busy: bool = false
var _provider_ready: bool = false
var _weekly_supported: bool = false
var _premium_active: bool = false
var _offer_epoch: int = 0
var _query_epoch: int = -1
var _details_in_flight: bool = false
var _details_refresh_pending: bool = false
var _account_id: String = ""
var _player_id: String = ""
var _verification_session: String = ""
var _pending_tokens: Array[String] = []
var _verified_tokens: Dictionary = {}
var _current_token: String = ""


func setup(owner_node: Node) -> void:
	host = owner_node
	host.add_child(self)
	_verification = HTTPRequest.new()
	_verification.timeout = 25.0
	_verification.max_redirects = 0
	add_child(_verification)
	_verification.request_completed.connect(_on_verification_response)
	_retry_timer = Timer.new()
	_retry_timer.one_shot = true
	_retry_timer.wait_time = 20.0
	add_child(_retry_timer)
	_retry_timer.timeout.connect(_retry)
	_trial_refresh_timer = Timer.new()
	_trial_refresh_timer.one_shot = true
	_trial_refresh_timer.wait_time = TRIAL_REFRESH_TIMEOUT
	add_child(_trial_refresh_timer)
	_trial_refresh_timer.timeout.connect(_on_trial_refresh_timeout)
	if not OS.has_feature("android") or not Engine.has_singleton("GodotGooglePlayBilling"):
		_status = "Subskrypcję możesz kupić w aplikacji z Google Play."
		return
	_billing = PlayBilling.new()
	add_child(_billing)
	_billing.connected.connect(_on_connected)
	_billing.disconnected.connect(_on_disconnected)
	_billing.connect_error.connect(_on_connect_error)
	_billing.query_product_details_response.connect(_on_product_details)
	_billing.query_purchases_response.connect(_on_purchases)
	_billing.on_purchase_updated.connect(_on_purchase_updated)
	_status = "Łączenie z Google Play…"
	_billing.start_connection()


func is_available() -> bool:
	return _billing != null and _billing.is_ready() and _offer_ready and _provider_ready and _weekly_supported and not _premium_active and not _account_id.is_empty() and not _player_id.is_empty() and not _purchase_busy and not _verification_busy and not _trial_purchase_pending


func formatted_price() -> String:
	# Always the nonzero recurring weekly price, never the free trial phase.
	return _price


func has_trial_offer() -> bool:
	return _offer_ready and _has_trial


func formatted_trial_price() -> String:
	return _trial_price if has_trial_offer() else ""


func offer_terms() -> String:
	if _premium_active:
		return I18n.t("Plan i cenę sprawdzisz w Google Play.")
	if _price.is_empty():
		return ""
	if has_trial_offer():
		return I18n.t("Automatyczne odnowienie co tydzień. Anuluj w Google Play przed końcem pierwszego tygodnia lub kolejnym odnowieniem, aby uniknąć opłaty.")
	return I18n.t("Pierwsza opłata przy zakupie, potem automatycznie co tydzień. Anuluj w Google Play przed kolejnym odnowieniem, aby uniknąć opłaty.")


func status_text() -> String:
	if _verification_busy:
		return I18n.t("Potwierdzanie subskrypcji na serwerze…")
	if not _provider_ready and not _player_id.is_empty():
		return I18n.t("Płatności oczekują na konfigurację Google Play.")
	if not _weekly_supported and not _player_id.is_empty() and not _premium_active:
		return I18n.t("Plan tygodniowy oczekuje na aktualizację serwera. Przywracanie obecnych zakupów pozostaje dostępne.")
	return I18n.t(_status)


func apply_server_state(next_state: Dictionary) -> void:
	var premium: Dictionary = next_state.get("premium", {})
	var player: Dictionary = next_state.get("player", {})
	var new_player: String = str(player.get("id", ""))
	var new_account: String = str(premium.get("billing_account_id", ""))
	var changed_account: bool = new_player != _player_id or new_account != _account_id
	if changed_account:
		_clear_account()
	_player_id = new_player
	_account_id = new_account
	_provider_ready = bool(premium.get("provider_ready", false))
	var plans: Variant = premium.get("supported_base_plan_ids", [])
	_weekly_supported = plans is Array and BASE_PLAN_ID in plans
	_premium_active = bool(premium.get("queue_planning_active", false))
	if _trial_purchase_pending and (not _provider_ready or not _weekly_supported or _premium_active):
		_finish_trial_refresh("unavailable", "Oferta 7 dni za darmo nie jest już dostępna.")
	if _billing != null:
		_billing.set_obfuscated_account_id(_account_id)
		if changed_account and not _player_id.is_empty() and _billing.is_ready():
			_request_product_details()
			_billing.query_purchases(PlayBilling.ProductType.SUBS, true)
	if _premium_active:
		_purchase_busy = false
		_status = "Subskrypcja kolejek jest aktywna."
	_verify_next.call_deferred()
	changed.emit()


func sign_out() -> void:
	_clear_account()
	if _billing != null:
		_billing.set_obfuscated_account_id("")
	changed.emit()


func _clear_account() -> void:
	_player_id = ""
	_account_id = ""
	_provider_ready = false
	_weekly_supported = false
	_premium_active = false
	_offer_epoch += 1
	_details_refresh_pending = false
	_clear_offer()
	_verification_session = ""
	_pending_tokens.clear()
	_verified_tokens.clear()
	_current_token = ""
	_purchase_busy = false
	_verification_busy = false
	if _verification != null:
		_verification.cancel_request()
	if _retry_timer != null:
		_retry_timer.stop()
	cancel_trial_subscription_purchase()


func purchase_subscription() -> void:
	if not is_available():
		changed.emit()
		return
	_billing.set_obfuscated_account_id(_account_id)
	_purchase_busy = true
	_status = "Otwieranie płatności Google Play…"
	changed.emit()
	# Pass the exact validated eligible offer ID; an empty ID selects only
	# the standard weekly plan. Never replace an existing monthly purchase.
	var result: Dictionary = _billing.purchase_subscription(PRODUCT_ID, BASE_PLAN_ID, _offer_id, false)
	var code: int = int(result.get("response_code", PlayBilling.BillingResponseCode.ERROR))
	if code != PlayBilling.BillingResponseCode.OK:
		_purchase_busy = false
		if code == PlayBilling.BillingResponseCode.ITEM_ALREADY_OWNED:
			restore_purchases()
		else:
			_status = "Nie udało się otworzyć płatności Google Play. Spróbuj ponownie."
		changed.emit()


func is_trial_purchase_pending() -> bool:
	return _trial_purchase_pending


func purchase_trial_subscription() -> void:
	# This entry point belongs to the seven-day CTA only. The regular
	# subscription screen keeps its existing purchase_subscription() behavior.
	if _trial_purchase_pending:
		return
	if not is_available() or not has_trial_offer() or not is_instance_valid(host) or str(host.session_token).is_empty():
		_status = "Oferta 7 dni za darmo nie jest już dostępna."
		trial_purchase_result.emit("unavailable", I18n.t(_status))
		changed.emit()
		return
	_trial_purchase_pending = true
	_trial_purchase_epoch = _offer_epoch
	_trial_purchase_session = str(host.session_token)
	_purchase_busy = true
	_status = "Wczytywanie ceny z Google Play…"
	_trial_refresh_timer.start()
	# This always clears the cached offer. If an earlier query is outstanding,
	# its response is drained first and a fresh query is then issued in order.
	_request_product_details()
	changed.emit()


func cancel_trial_subscription_purchase() -> void:
	# Cancels only the outstanding refresh. An already opened Google Play
	# purchase sheet is owned by Play and uses the normal purchase callbacks.
	_finish_trial_refresh("cancelled", "")


func _finish_trial_refresh(outcome: String, message: String, launched: bool = false) -> void:
	if not _trial_purchase_pending:
		return
	_trial_purchase_pending = false
	_trial_purchase_epoch = -1
	_trial_purchase_session = ""
	_purchase_busy = launched
	if _trial_refresh_timer != null:
		_trial_refresh_timer.stop()
	if not message.is_empty():
		_status = message
	trial_purchase_result.emit(outcome, I18n.t(message))
	changed.emit()


func _on_trial_refresh_timeout() -> void:
	if not _trial_purchase_pending:
		return
	_clear_offer()
	# Do not reset _details_in_flight: native replies have no request ID.
	# A late reply must be drained, never mistaken for a later checkout query.
	_finish_trial_refresh("error", "Nie udało się odświeżyć oferty. Spróbuj ponownie.")


func _complete_trial_refresh(response: Dictionary) -> void:
	if not _trial_purchase_pending:
		return
	if _trial_purchase_epoch != _offer_epoch or not is_instance_valid(host) or _trial_purchase_session != str(host.session_token) or _player_id.is_empty() or _account_id.is_empty():
		_finish_trial_refresh("cancelled", "")
		return
	if not _provider_ready or not _weekly_supported or _premium_active or _verification_busy:
		_finish_trial_refresh("unavailable", "Oferta 7 dni za darmo nie jest już dostępna.")
		return
	if int(response.get("response_code", -1)) != PlayBilling.BillingResponseCode.OK or _billing == null or not _billing.is_ready():
		_finish_trial_refresh("error", "Nie udało się odświeżyć oferty. Spróbuj ponownie.")
		return
	if not has_trial_offer() or _offer_id != Offer.TRIAL_OFFER_ID:
		# Offer.select may return the paid base plan. It is never a fallback
		# for this CTA, even when an earlier query did contain a valid trial.
		_finish_trial_refresh("unavailable", "Oferta 7 dni za darmo nie jest już dostępna.")
		return
	_billing.set_obfuscated_account_id(_account_id)
	var result: Dictionary = _billing.purchase_subscription(PRODUCT_ID, BASE_PLAN_ID, Offer.TRIAL_OFFER_ID, false)
	var code: int = int(result.get("response_code", PlayBilling.BillingResponseCode.ERROR))
	if code == PlayBilling.BillingResponseCode.OK:
		_finish_trial_refresh("started", "Otwieranie płatności Google Play…", true)
	elif code == PlayBilling.BillingResponseCode.ITEM_ALREADY_OWNED:
		_finish_trial_refresh("unavailable", "Oferta 7 dni za darmo nie jest już dostępna.")
		restore_purchases()
	else:
		_finish_trial_refresh("error", "Nie udało się otworzyć płatności Google Play. Spróbuj ponownie.")


func restore_purchases() -> void:
	# Restore also polls the authoritative server, including on non-Android.
	_verified_tokens.clear()
	if host != null and not str(host.session_token).is_empty():
		host._poll(true)
	if _billing == null:
		changed.emit()
		return
	if not _billing.is_ready():
		_billing.start_connection()
		_status = "Łączenie z Google Play…"
	else:
		_status = "Sprawdzanie zakupów w Google Play…"
		_request_product_details()
		_billing.query_purchases(PlayBilling.ProductType.SUBS, true)
	changed.emit()


func manage_subscription() -> void:
	if _billing != null:
		_billing.open_subscriptions_page(PRODUCT_ID)
	else:
		OS.shell_open("https://play.google.com/store/account/subscriptions?sku=%s&package=%s" % [PRODUCT_ID.uri_encode(), PACKAGE_NAME.uri_encode()])


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_RESUMED and _billing != null:
		restore_purchases.call_deferred()


func _on_connected() -> void:
	_status = "Wczytywanie ceny z Google Play…"
	_request_product_details()
	_billing.query_purchases(PlayBilling.ProductType.SUBS, true)
	changed.emit()


func _on_disconnected() -> void:
	_clear_offer()
	_purchase_busy = false
	_status = "Brak połączenia z Google Play. Spróbuj ponownie."
	_finish_trial_refresh("error", _status)
	_retry_timer.start()
	changed.emit()


func _on_connect_error(_code: int, _message: String) -> void:
	_on_disconnected()


func _clear_offer() -> void:
	_offer_ready = false
	_price = ""
	_trial_price = ""
	_offer_id = ""
	_has_trial = false


func _request_product_details() -> void:
	_clear_offer()
	if _billing == null or not _billing.is_ready() or _player_id.is_empty() or _account_id.is_empty():
		return
	# Native responses have no request/account ID. Serialize requests so a
	# response initiated for a previous game account cannot enable a purchase.
	if _details_in_flight:
		_details_refresh_pending = true
		return
	_details_in_flight = true
	_details_refresh_pending = false
	_query_epoch = _offer_epoch
	_billing.query_product_details(PackedStringArray([PRODUCT_ID]), PlayBilling.ProductType.SUBS)


func _on_product_details(response: Dictionary) -> void:
	var was_current: bool = _details_in_flight and _query_epoch == _offer_epoch
	_details_in_flight = false
	_clear_offer()
	if _details_refresh_pending:
		_request_product_details()
		changed.emit()
		return
	if not was_current or _player_id.is_empty() or _account_id.is_empty():
		cancel_trial_subscription_purchase()
		changed.emit()
		return
	if int(response.get("response_code", -1)) == PlayBilling.BillingResponseCode.OK:
		var selected: Dictionary = Offer.select(response.get("product_details", []))
		_price = str(selected.get("price", ""))
		_trial_price = str(selected.get("trial_price", ""))
		_offer_id = str(selected.get("offer_id", ""))
		_has_trial = bool(selected.get("trial", false))
		_offer_ready = not selected.is_empty()
	_status = "" if _offer_ready else "Subskrypcja nie jest jeszcze dostępna w Google Play."
	_complete_trial_refresh(response)
	changed.emit()


func _on_purchase_updated(response: Dictionary) -> void:
	_purchase_busy = false
	var code: int = int(response.get("response_code", -1))
	if code == PlayBilling.BillingResponseCode.USER_CANCELED:
		_status = "Zakup anulowany."
		changed.emit()
		return
	if code == PlayBilling.BillingResponseCode.ITEM_ALREADY_OWNED:
		restore_purchases()
		return
	_on_purchases(response)


func _on_purchases(response: Dictionary) -> void:
	if int(response.get("response_code", -1)) != PlayBilling.BillingResponseCode.OK:
		_status = "Nie udało się sprawdzić zakupów. Spróbuj ponownie."
		changed.emit()
		return
	var purchases: Variant = response.get("purchases", [])
	if not purchases is Array:
		return
	var found: bool = false
	for purchase: Variant in purchases:
		if not purchase is Dictionary:
			continue
		var ids: Variant = purchase.get("product_ids", [])
		if not ids is Array and not ids is PackedStringArray:
			continue
		if PRODUCT_ID not in ids:
			continue
		found = true
		_finish_trial_refresh("unavailable", "Oferta 7 dni za darmo nie jest już dostępna.")
		if int(purchase.get("purchase_state", 0)) != PlayBilling.PurchaseState.PURCHASED:
			_status = "Płatność oczekuje na zakończenie. Kolejki nie zostały odblokowane."
			continue
		if bool(purchase.get("is_suspended", false)):
			_status = "Subskrypcja jest wstrzymana. Sprawdź płatność w Google Play."
			continue
		var token: String = str(purchase.get("purchase_token", ""))
		if not token.is_empty() and not _verified_tokens.has(token) and token not in _pending_tokens and token != _current_token:
			_pending_tokens.append(token)
	if not found and _pending_tokens.is_empty() and not _verification_busy:
		_status = "Brak zakupionej subskrypcji na tym koncie Google Play."
	_verify_next()
	changed.emit()


func _verify_next() -> void:
	if _verification_busy or _pending_tokens.is_empty() or _player_id.is_empty() or not _provider_ready or str(host.session_token).is_empty():
		return
	_current_token = _pending_tokens.pop_front()
	_verification_session = str(host.session_token)
	_verification_busy = true
	var headers: PackedStringArray = PackedStringArray(["Content-Type: application/json", "Accept: application/json", "Accept-Language: " + I18n.locale, "Authorization: Bearer " + _verification_session, "X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE)])
	var payload: Dictionary = {"type": "verify_subscription", "product_id": PRODUCT_ID, "purchase_token": _current_token, "planet_id": host.selected_planet, "request_id": host._new_request_id()}
	var error: Error = _verification.request(str(host.server_url) + "/api/action", headers, HTTPClient.METHOD_POST, JSON.stringify(payload))
	if error != OK:
		_verification_busy = false
		_pending_tokens.push_front(_current_token)
		_current_token = ""
		_status = "Nie udało się potwierdzić zakupu. Użyj „Przywróć zakupy”."
		_retry_timer.start()
	changed.emit()


func _on_verification_response(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_verification_busy = false
	if _verification_session.is_empty() or _verification_session != str(host.session_token) or _player_id.is_empty():
		_current_token = ""
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if result != HTTPRequest.RESULT_SUCCESS or code >= 500 or not parsed is Dictionary:
		_pending_tokens.push_front(_current_token)
		_current_token = ""
		_status = "Nie udało się potwierdzić zakupu. Użyj „Przywróć zakupy”."
		_retry_timer.start()
		changed.emit()
		return
	var response: Dictionary = parsed
	if code >= 200 and code < 300 and bool(response.get("ok", false)):
		_verified_tokens[_current_token] = true
		_status = "Subskrypcja została sprawdzona na serwerze."
		# A purchase request may finish after a colony switch or another command.
		# Fetch the currently selected colony instead of applying its older snapshot.
		host._poll(true)
	else:
		_status = str(response.get("error", I18n.t("Nie udało się potwierdzić zakupu. Użyj „Przywróć zakupy”.")))
	_current_token = ""
	changed.emit()
	_verify_next.call_deferred()
	# Acknowledgement is intentionally performed ONLY by the verification server.


func _retry() -> void:
	if _billing != null and not _billing.is_ready():
		_billing.start_connection()
	_verify_next()
