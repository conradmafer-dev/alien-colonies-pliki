extends RefCounted
## Validate the exact phases returned as eligible by Google Play. Never infer
## trial eligibility from local history or manufacture a price/offer token.

const PRODUCT_ID: String = "queue_planner"
const BASE_PLAN_ID: String = "weekly"
const TRIAL_OFFER_ID: String = "trial-7d"


static func select(products: Variant) -> Dictionary:
	if not products is Array:
		return {}
	var matches: Array = []
	for product: Variant in products:
		if product is Dictionary and str(product.get("product_id", "")) == PRODUCT_ID:
			matches.append(product)
	if matches.size() != 1:
		return {}
	var offers: Variant = matches[0].get("subscription_offer_details", [])
	if not offers is Array:
		return {}
	var selected: Dictionary = {}
	var base: Dictionary = {}
	var seen_ids: Dictionary = {}
	for offer: Variant in offers:
		if not offer is Dictionary or str(offer.get("base_plan_id", "")) != BASE_PLAN_ID:
			continue
		var raw_id: Variant = offer.get("offer_id")
		var offer_id: String = "" if raw_id == null else str(raw_id)
		if offer_id not in ["", TRIAL_OFFER_ID]:
			continue
		# The native bridge also selects by ID. Ambiguous duplicate IDs could
		# otherwise make it purchase a different offer than the one displayed.
		if seen_ids.has(offer_id):
			return {}
		seen_ids[offer_id] = true
		var candidate: Dictionary = _validate_offer(offer, offer_id)
		if candidate.is_empty():
			continue
		if offer_id == TRIAL_OFFER_ID:
			selected = candidate
		else:
			base = candidate
	return selected if not selected.is_empty() else base


static func _validate_offer(offer: Dictionary, offer_id: String) -> Dictionary:
	if not offer.get("offer_token") is String or str(offer.get("offer_token")).strip_edges().is_empty():
		return {}
	var phases: Variant = offer.get("pricing_phases", [])
	var trial: bool = offer_id == TRIAL_OFFER_ID
	if not phases is Array or phases.size() != (2 if trial else 1):
		return {}
	var paid: Variant = phases[-1]
	if not paid is Dictionary:
		return {}
	var price: Variant = paid.get("formatted_price")
	var currency: Variant = paid.get("price_currency_code")
	if not price is String or str(price).strip_edges().is_empty() or not currency is String or str(currency).length() != 3:
		return {}
	for letter: String in str(currency):
		if letter < "A" or letter > "Z":
			return {}
	if str(paid.get("billing_period", "")) != "P1W" or _integer(paid.get("recurrence_mode")) != 1 or _integer(paid.get("billing_cycle_count")) != 0 or _integer(paid.get("price_amount_micros")) <= 0:
		return {}
	if trial:
		var free: Variant = phases[0]
		if not free is Dictionary:
			return {}
		if str(free.get("billing_period", "")) not in ["P1W", "P7D"] or _integer(free.get("recurrence_mode")) != 2 or _integer(free.get("billing_cycle_count")) != 1 or _integer(free.get("price_amount_micros")) != 0 or free.get("price_currency_code") != currency:
			return {}
	var recurring_price: String = str(price).strip_edges()
	return {"base_plan_id": BASE_PLAN_ID, "offer_id": offer_id, "trial": trial, "price": recurring_price, "currency": currency, "trial_price": _zero_price(recurring_price, str(currency)) if trial else ""}


static func _zero_price(recurring_price: String, currency: String) -> String:
	# This is called only after Google Play's exact free phase was validated.
	# Keep its real currency symbol, position and spacing, while showing a clean
	# zero instead of a hard-coded currency or Google's word-only "Free" label.
	var digits: RegEx = RegEx.new()
	digits.compile("\\p{Nd}")
	var matches: Array[RegExMatch] = digits.search_all(recurring_price)
	if matches.is_empty():
		return "0 " + currency
	var prefix: String = recurring_price.substr(0, matches[0].get_start())
	var suffix: String = recurring_price.substr(matches[-1].get_end())
	if prefix.strip_edges().is_empty() and suffix.strip_edges().is_empty():
		return "0 " + currency
	return prefix + "0" + suffix


static func _integer(value: Variant) -> int:
	if value is int:
		return value
	if value is float and is_finite(value) and value == floor(value):
		return int(value)
	if value is String and value.is_valid_int():
		return int(value)
	return -1
