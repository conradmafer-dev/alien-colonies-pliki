extends RefCounted
## Server-authoritative waiting orders. A purchase never grants local access.

var host
var panels: Dictionary = {}
var order_buttons: Array[Button] = []
var signatures: Dictionary = {}
var offer_body: VBoxContainer
var offer_status: Label
var offer_price: RichTextLabel
var offer_terms: Label
var offer_buy: Button
var offer_restore: Button
var offer_manage: Button
var queue_body: VBoxContainer
var open_lane: String = ""
var queue_view_signature: String = ""


func setup(client) -> void:
	host = client
	_make_panel("build", host.tab_bodies[0], host.building_heading.get_index())
	_make_panel("ship", host.fleet_build_view, 2)
	_make_panel("research", host.tab_bodies[3], 1)


func _make_panel(lane: String, parent: VBoxContainer, index: int) -> void:
	var button: Button = host._button("", _open_orders.bind(lane))
	button.name = "PlannedQueue_" + lane
	button.custom_minimum_size.y = 56
	button.add_theme_font_size_override("font_size", 21)
	button.autowrap_mode = TextServer.AUTOWRAP_OFF
	button.clip_text = true
	button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	button.hide()
	parent.add_child(button)
	parent.move_child(button, mini(index, parent.get_child_count() - 1))
	panels[lane] = {"panel": button, "title": button}


func _lane_title(lane: String) -> String:
	return str({"build": I18n.t("Kolejka budowy"), "ship": I18n.t("Kolejka stoczni"), "research": I18n.t("Kolejka badań imperium")}.get(lane, I18n.t("Planowanie kolejek")))


func _open_orders(lane: String) -> void:
	if host.update_required or host.compact_ui == null:
		return
	open_lane = lane
	host.compact_ui._begin_details(_lane_title(lane), true)
	queue_body = VBoxContainer.new()
	queue_body.name = "PlannedQueueDetails"
	queue_body.add_theme_constant_override("separation", 16)
	host.compact_ui.modal_body.add_child(queue_body)
	queue_view_signature = ""
	_refresh_queue_details()


func _refresh_queue_details() -> void:
	if not is_instance_valid(queue_body) or not host.compact_ui.details_open() or not queue_body.is_visible_in_tree():
		return
	var orders: Array[Dictionary] = orders_for(open_lane)
	var signature: String = JSON.stringify([orders, active(), host.selected_planet, I18n.locale])
	if signature == queue_view_signature:
		return
	var scroll_y: int = host.compact_ui.modal_scroll.scroll_vertical
	queue_view_signature = signature
	host._clear(queue_body)
	order_buttons.clear()
	var limit: int = int(host.state.get("limits", {}).get("queue_waiting", 10))
	queue_body.add_child(host._label(_lane_title(open_lane) + " · %d/%d" % [orders.size(), limit], 23))
	if not orders.is_empty() and not active():
		queue_body.add_child(host._label(I18n.t("Kolejka wstrzymana: subskrypcja jest nieaktywna."), 22, "edc77a"))
	for index: int in range(orders.size()):
		_make_order(queue_body, orders[index], str(orders[index - 1].get("id", "")) if index > 0 else "")
	for row: Node in queue_body.get_children():
		for node: Node in row.get_children():
			if node is Button:
				order_buttons.append(node)
	host.compact_ui._restore_details_scroll(scroll_y)


func active() -> bool:
	return bool(host.state.get("premium", {}).get("queue_planning_active", false))


func busy() -> bool:
	return host.request_pending or not host.uncertain_action.is_empty() or host.update_required or not host.requested_planet.is_empty()


func can_plan(entry: Dictionary, kind: String = "") -> bool:
	# Busy lanes and a temporary resource shortage must not block planning.
	# Eligibility excludes entitlement so a free account can open the offer.
	# Mutation permission is still enforced by the server after a purchase.
	if entry.has("planning_eligible"):
		return bool(entry["planning_eligible"]) and (not active() or bool(entry.get("planning_enabled", true)))
	if entry.has("planning_enabled") and (active() or bool(entry["planning_enabled"])):
		return bool(entry["planning_enabled"])
	# Older servers mask all free-account reasons with "premium required".
	# Preserve their authored hard requirements before presenting an offer.
	if entry.has("requirements_met") and not bool(entry["requirements_met"]):
		return false
	for requirement: Dictionary in entry.get("requirements", []):
		if not bool(requirement.get("met", false)):
			return false
	if kind == "build" and int(entry.get("building_fields", {}).get("free", 1)) < 1:
		return false
	var lane: String = "ship" if kind == "defense" else kind
	if not lane.is_empty() and orders_for(lane).size() >= int(host.state.get("limits", {}).get("queue_waiting", 10)):
		return false
	if kind in ["build", "research"] and int(entry.get("max_level", 0)) > 0:
		var key: String = str(entry.get("key", ""))
		var future_level: int = int(entry.get("level", 0))
		var task: Dictionary = host.project_ui.task_for(kind) if host.project_ui != null else {}
		if str(task.get("key", "")) == key:
			future_level += 1
		for order: Dictionary in orders_for(lane):
			if str(order.get("key", "")) == key:
				future_level += 1
		if future_level >= int(entry["max_level"]):
			return false
	if kind == "ship" and str(host.state.get("player", {}).get("race_id", "")).is_empty() and (str(entry.get("key", "")) in ["interceptor", "siege", "freighter"] or bool(entry.get("capital", false))):
		return false
	return true


func planning_reason(entry: Dictionary) -> String:
	return host._server_text(entry.get("planning_eligibility_reason", entry.get("planning_reason", entry.get("reason", ""))))


func lane_busy(kind: String) -> bool:
	# Research is empire-wide; ships and defenses share the local shipyard.
	var lane: String = "ship" if kind == "defense" else kind
	return not orders_for(lane).is_empty() or (host.project_ui != null and not host.project_ui.task_for(lane).is_empty())


func has_resources(entry: Dictionary, amount: int = 1) -> bool:
	for resource: String in host.RESOURCE_KEYS:
		if float(entry.get("cost", {}).get(resource, 0)) * amount > float(host.state.get("resources", {}).get(resource, 0)):
			return false
	return true


func refresh_action_button(button: Button, entry: Dictionary, kind: String, amount: int = 1) -> void:
	var maximum: bool = kind not in ["ship", "defense"] and int(entry.get("max_level", 0)) > 0 and int(entry.get("level", 0)) >= int(entry["max_level"])
	var planning: bool = lane_busy(kind)
	button.text = I18n.t("Maksimum") if maximum else I18n.t("Do kolejki") if planning else I18n.t("Badaj") if kind == "research" else I18n.t("Buduj") if kind in ["ship", "defense"] or int(entry.get("level", 0)) == 0 else I18n.t("Ulepsz")
	button.tooltip_text = I18n.t("Dodaj do kolejki planowanych projektów") if planning else ""
	button.disabled = busy() or maximum or (not can_plan(entry, kind) if planning else not bool(entry.get("enabled", false)) or not has_resources(entry, amount))
	if planning and not can_plan(entry, kind):
		button.tooltip_text = planning_reason(entry)


func add(kind: String, key: String) -> void:
	if busy():
		return
	var group: String = str({"build": "buildings", "research": "research", "ship": "ships", "defense": "defenses"}.get(kind, ""))
	var entry: Dictionary = host._catalog_entry(key, group)
	if entry.is_empty() or not can_plan(entry, kind):
		var reason: String = planning_reason(entry)
		host._notify(reason if not reason.is_empty() else I18n.t("Wymagania projektu nie są spełnione."), true)
		return
	if not active():
		open_offer()
		return
	var amount: int = 1
	if kind in ["ship", "defense"]:
		var rows: Dictionary = host.defense_rows if kind == "defense" else host.ship_rows
		if rows.has(key) and rows[key].get("amount") != null:
			rows[key]["amount"].apply()
			amount = clampi(int(rows[key]["amount"].value), 1, 20)
	host._request("/api/action", {"type": "plan_project", "planet_id": host.selected_planet, "kind": kind, "key": key, "amount": amount, "request_id": host._new_request_id()}, "action")
	host.compact_ui.close_details()


func orders_for(lane: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for value: Variant in host.state.get("planned_orders", []):
		if not value is Dictionary:
			continue
		var order: Dictionary = value
		var kind: String = str(order.get("kind", ""))
		if lane == "research" and kind == "research":
			result.append(order)
		elif lane == "build" and kind == "build" and str(order.get("planet_id", "")) == host.selected_planet:
			result.append(order)
		elif lane == "ship" and kind in ["ship", "defense"] and str(order.get("planet_id", "")) == host.selected_planet:
			result.append(order)
	return result


func refresh() -> void:
	for lane: String in panels:
		var controls: Dictionary = panels[lane]
		var orders: Array[Dictionary] = orders_for(lane)
		controls["panel"].visible = not orders.is_empty()
		var limit: int = int(host.state.get("limits", {}).get("queue_waiting", 10))
		controls["title"].text = _lane_title(lane) + " · %d/%d ›" % [orders.size(), limit]
		controls["title"].tooltip_text = I18n.t("Kolejka wstrzymana: subskrypcja jest nieaktywna.") if not orders.is_empty() and not active() else _lane_title(lane)
	_refresh_queue_details()
	refresh_offer()
	tick()


func _make_order(parent: VBoxContainer, order: Dictionary, previous_id: String) -> void:
	var row: HBoxContainer = host._row(parent)
	var text: VBoxContainer = VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(text)
	var kind: String = str(order.get("kind", ""))
	var group: String = str({"build": "buildings", "research": "research", "ship": "ships", "defense": "defenses"}.get(kind, ""))
	var caption: String = host._server_text(order.get("name", host._catalog_name(str(order.get("key", "")), group)))
	if kind in ["ship", "defense"]:
		caption += " ×%d" % int(order.get("amount", 1))
	elif int(order.get("level", 0)) > 0:
		caption += I18n.t(" · poz. %d") % int(order["level"])
	if kind == "research":
		caption += " · " + str(order.get("planet_name", ""))
	text.add_child(host._label(caption, 20))
	var reason: String = str(order.get("reason", ""))
	var codes: Dictionary = {"resources": "Oczekuje na surowce", "lane_busy": "Oczekuje na ukończenie projektu", "requirements": "Oczekuje na wymagania", "premium_inactive": "Subskrypcja jest nieaktywna", "subscription_inactive": "Subskrypcja jest nieaktywna"}
	if not active():
		reason = I18n.t("Subskrypcja jest nieaktywna")
	elif codes.has(reason):
		reason = I18n.t(str(codes[reason]))
	elif reason.is_empty():
		reason = I18n.t("Oczekuje na uruchomienie")
	else:
		reason = host._server_text(reason)
	text.add_child(host._label(reason, 18, "a0b3a4"))
	var id: String = str(order.get("id", ""))
	if not previous_id.is_empty():
		var up: Button = host._button("↑", _reorder.bind(id, previous_id))
		up.name = "MovePlannedOrderUp"
		up.tooltip_text = I18n.t("Przesuń wcześniej")
		up.custom_minimum_size = Vector2(54, 54)
		up.size_flags_horizontal = Control.SIZE_SHRINK_END
		row.add_child(up)
	var remove: Button = host._button("×", _remove.bind(id))
	remove.name = "RemovePlannedOrder"
	remove.tooltip_text = I18n.t("Usuń z kolejki")
	remove.custom_minimum_size = Vector2(54, 54)
	remove.size_flags_horizontal = Control.SIZE_SHRINK_END
	row.add_child(remove)


func _remove(id: String) -> void:
	if busy() or id.is_empty():
		return
	host._request("/api/action", {"type": "remove_planned_project", "planet_id": host.selected_planet, "order_id": id, "request_id": host._new_request_id()}, "action")


func _reorder(id: String, previous_id: String) -> void:
	if busy() or id.is_empty() or previous_id.is_empty():
		return
	host._request("/api/action", {"type": "reorder_planned_project", "planet_id": host.selected_planet, "order_id": id, "before_order_id": previous_id, "request_id": host._new_request_id()}, "action")


func tick() -> void:
	for button: Button in order_buttons:
		if is_instance_valid(button):
			button.disabled = busy()
	for rows: Dictionary in [host.building_rows, host.ship_rows, host.defense_rows, host.research_rows]:
		for controls: Dictionary in rows.values():
			var amount: int = int(controls["amount"].value) if controls.get("amount") != null else 1
			refresh_action_button(controls["action"], controls.get("entry", {}), str(controls["kind"]), amount)
	if host.compact_ui != null:
		host.compact_ui.refresh_catalog_action()
	if is_instance_valid(host.research_tree):
		host.research_tree.refresh_detail_action()


func open_offer() -> void:
	if host.update_required or host.compact_ui == null:
		return
	host.compact_ui._begin_details(I18n.t("Planowanie kolejek"))
	offer_body = VBoxContainer.new()
	offer_body.name = "QueueSubscriptionOffer"
	offer_body.add_theme_constant_override("separation", 14)
	host.compact_ui.modal_body.add_child(offer_body)
	_add_offer_art()
	var limit: int = int(host.state.get("limits", {}).get("queue_waiting", 10))
	var summary: Label = host._label(I18n.t("Automatyczne kolejki budowy, stoczni i badań — do %d oczekujących projektów każda.") % limit, 22)
	summary.name = "QueueSubscriptionSummary"
	offer_body.add_child(summary)
	offer_status = host._label("", 22, "edc77a")
	offer_body.add_child(offer_status)
	offer_price = RichTextLabel.new()
	offer_price.name = "QueueSubscriptionPrice"
	offer_price.fit_content = true
	offer_price.scroll_active = false
	offer_price.mouse_filter = Control.MOUSE_FILTER_IGNORE
	offer_price.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	offer_price.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	offer_price.add_theme_font_size_override("normal_font_size", 26)
	offer_price.add_theme_color_override("default_color", host._ui_color(Color("e7eee4")))
	offer_body.add_child(offer_price)
	offer_terms = host._label("", 21, "d4ebd6")
	offer_terms.name = "QueueSubscriptionTerms"
	offer_body.add_child(offer_terms)
	offer_buy = host._button("", _purchase, true)
	offer_buy.name = "BuyQueueSubscription"
	_style_offer_button(offer_buy, true)
	offer_body.add_child(offer_buy)
	offer_restore = host._button("↻  " + I18n.t("Przywróć zakupy"), _restore)
	offer_restore.name = "RestoreQueueSubscription"
	_style_offer_button(offer_restore)
	offer_body.add_child(offer_restore)
	offer_manage = host._button("↗  " + I18n.t("Zarządzaj w Google Play"), _manage)
	offer_manage.name = "ManageQueueSubscription"
	_style_offer_button(offer_manage)
	offer_body.add_child(offer_manage)
	refresh_offer()


func _add_offer_art() -> void:
	const path: String = "res://client/assets/art/premium_queue_banner.webp"
	if not ResourceLoader.exists(path):
		return
	var texture: Texture2D = load(path) as Texture2D
	if texture == null or texture.get_width() <= 0 or texture.get_height() <= 0:
		return
	var frame: PanelContainer = PanelContainer.new()
	frame.name = "QueueSubscriptionArt"
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	frame.add_theme_stylebox_override("panel", host._style("070c0c", "edc77a", 14, 4))
	offer_body.add_child(frame)
	var picture: TextureRect = TextureRect.new()
	picture.name = "PremiumQueueBanner"
	picture.texture = texture
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(picture)
	offer_body.resized.connect(_fit_offer_art.bind(frame, texture))
	_fit_offer_art(frame, texture)


func _fit_offer_art(frame: PanelContainer, texture: Texture2D) -> void:
	if not is_instance_valid(frame):
		return
	var ratio: float = float(texture.get_width()) / texture.get_height()
	var picture_height: float = minf(190.0, maxf(offer_body.size.x - 8.0, 0.0) / ratio)
	frame.custom_minimum_size = Vector2(0, picture_height + 8.0)


func _style_offer_button(button: Button, primary: bool = false) -> void:
	button.custom_minimum_size.y = 68 if primary else 56
	button.add_theme_font_size_override("font_size", 24 if primary else 22)
	var normal: StyleBoxFlat = host._style("91c89b" if primary else "13251b", "d4ebd6" if primary else "45654c", 14, 12)
	normal.content_margin_left = 18
	normal.content_margin_right = 18
	if primary:
		normal.shadow_color = Color(0, 0, 0, 0.22)
		normal.shadow_size = 4
		normal.shadow_offset = Vector2(0, 2)
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", host._style("b7e3bd" if primary else "1d3326", "e7eee4" if primary else "91c89b", 14, 12))
	button.add_theme_stylebox_override("pressed", host._style("66896d" if primary else "2b4f36", "91c89b", 14, 12))
	button.add_theme_stylebox_override("disabled", host._style("142219", "293c2d", 14, 12))
	for key: String in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		button.add_theme_color_override(key, host._ui_color(Color("08110d" if primary else "d4ebd6")))
	button.add_theme_color_override("font_disabled_color", host._ui_color(Color("7f9384")))


func refresh_offer() -> void:
	if not is_instance_valid(offer_body) or not host.compact_ui.details_open() or not offer_body.is_visible_in_tree():
		return
	var service = host.queue_billing
	var price: String = service.formatted_price() if service != null else ""
	var available: bool = service != null and service.is_available()
	var message: String = service.status_text() if service != null else I18n.t("Płatności Google Play są niedostępne.")
	if active():
		message = I18n.t("Planowanie kolejek jest aktywne.")
		var expires: float = float(host.state.get("premium", {}).get("expires_at", 0))
		if expires > 0:
			message += "\n" + I18n.t("Dostęp do: %s") % host._date(expires)
	offer_status.text = message
	offer_status.visible = not message.is_empty()
	offer_terms.text = service.offer_terms() if service != null else ""
	offer_terms.visible = not offer_terms.text.is_empty()
	_refresh_offer_price(service, price)
	if price.is_empty():
		offer_buy.text = I18n.t("Wczytywanie ceny z Google Play…")
	elif service.has_trial_offer():
		offer_buy.text = I18n.t("Rozpocznij za %s") % service.formatted_trial_price()
	else:
		offer_buy.text = I18n.t("Subskrybuj")
	offer_buy.tooltip_text = offer_price.get_parsed_text() if not price.is_empty() else offer_buy.text
	offer_buy.visible = not active()
	offer_buy.disabled = busy() or not available or price.is_empty()
	offer_restore.disabled = busy() or service == null
	offer_manage.visible = active()
	offer_manage.disabled = service == null


func _refresh_offer_price(service, price: String) -> void:
	offer_price.clear()
	offer_price.visible = not active() and not price.is_empty()
	if not offer_price.visible:
		return
	if service.has_trial_offer():
		# Push plain text through the rich label so store-provided symbols are
		# never interpreted as markup. The crossed price applies to week one;
		# the full recurring weekly price stays readable on the following line.
		offer_price.push_color(host._ui_color(Color("a0b3a4")))
		offer_price.push_strikethrough()
		offer_price.add_text(price)
		offer_price.pop()
		offer_price.pop()
		offer_price.add_text("  ")
		offer_price.push_font_size(36)
		offer_price.push_color(host._ui_color(Color("b7e3bd")))
		offer_price.add_text(service.formatted_trial_price())
		offer_price.pop()
		offer_price.pop()
		offer_price.add_text(" " + I18n.t("przez pierwszy tydzień") + "\n")
		offer_price.add_text(I18n.t("następnie %s / tydzień") % price)
	else:
		offer_price.add_text(I18n.t("%s / tydzień") % price)


func _purchase() -> void:
	if host.queue_billing != null and not busy():
		host.queue_billing.purchase_subscription()


func _restore() -> void:
	if host.queue_billing != null and not busy():
		host.queue_billing.restore_purchases()


func _manage() -> void:
	if host.queue_billing != null:
		host.queue_billing.manage_subscription()


func reset() -> void:
	signatures.clear()
	order_buttons.clear()
	for controls: Dictionary in panels.values():
		controls["panel"].hide()
	if is_instance_valid(queue_body) and queue_body.is_visible_in_tree() and host.compact_ui.details_open():
		host.compact_ui.close_details()
	open_lane = ""
	queue_view_signature = ""
