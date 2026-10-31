extends Node
## One optional, server-claimed invitation after six completed construction jobs.
## A claim only records this invitation; Google Play and the server grant access.

const BANNER_PATH: String = "res://client/assets/art/premium_queue_banner.webp"
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
const CHECK_INTERVAL: float = 0.5

var host
var overlay: Control
var card: PanelContainer
var heading: Label
var close_button: Button
var artwork: TextureRect
var description: Label
var trial_button: Button
var terms: Label
var cancellation: Label
var later_button: Button
var status: Label
var body: VBoxContainer
var scroll: ScrollContainer
var header: HBoxContainer
var layout: VBoxContainer

var _billing
var _elapsed: float = 0.0
var _session: String = ""
var _player: String = ""
var _server: String = ""
var _pending_request_id: String = ""
var _claim_after_msec: int = 0
var _display_request_id: String = ""
var _attempted_this_session: bool = false
var _displayed_this_session: bool = false
var _purchase_requested: bool = false
var _failure_message: String = ""
var _display_price: String = ""
var _previous_back_quit: bool = true
var _back_restore_pending: bool = false
var _layout_queued: bool = false


func _ready() -> void:
	# This node is a scene child: the parent's _ready creates the billing service.
	set_process(false)
	_setup.call_deferred()


func _setup() -> void:
	host = get_parent()
	if not is_instance_valid(host) or not host.is_inside_tree():
		return
	_billing = host.queue_billing
	if _billing == null:
		return
	_make_overlay()
	_billing.changed.connect(_on_billing_changed)
	_billing.trial_purchase_result.connect(_on_trial_purchase_result)
	host.resized.connect(_queue_layout)
	I18n.language_changed.connect(_translate)
	set_process(true)


func _process(delta: float) -> void:
	if not is_instance_valid(host):
		return
	# Logout/account changes cancel a pending store launch without waiting 0.5 s.
	if not _context_matches() and (not _session.is_empty() or is_open()):
		_reset_session()
	if is_open() and (host.update_required or host.showing_login or _premium_active()):
		_hide()
	_elapsed += delta
	if _elapsed < CHECK_INTERVAL:
		return
	_elapsed = 0.0
	_tick()


func _tick() -> void:
	if not is_instance_valid(host) or not is_instance_valid(overlay):
		return
	_restore_back()
	var player_id: String = str(host.state.get("player", {}).get("id", ""))
	if host.showing_login or host.session_token.is_empty() or player_id.is_empty():
		_reset_session()
		return
	if not _context_matches():
		_reset_session()
		_session = host.session_token
		_player = player_id
		_server = host.server_url
	var hint: Dictionary = host.state.get("subscription_prompt", {})
	if is_open():
		if not _owns_claim(hint, _display_request_id) or _other_ui_open():
			_hide()
		elif not _trial_ready() and not _purchase_requested and _failure_message.is_empty():
			# An expired/revoked offer must never retain a working free-trial CTA.
			_hide()
		else:
			_refresh_offer()
		return
	if not _pending_request_id.is_empty():
		if _premium_active() or (bool(hint.get("shown", false)) and str(hint.get("claim_request_id", "")) != _pending_request_id):
			_pending_request_id = ""
			return
		# The unique request ID must be acknowledged by a newer server snapshot.
		# eligible becomes false after a successful claim, because shown is true.
		if int(host.received_at_msec) <= _claim_after_msec or not _owns_claim(hint, _pending_request_id):
			return
		if not _trial_ready():
			_pending_request_id = ""
			return
		if _safe_to_present():
			_display_request_id = _pending_request_id
			_pending_request_id = ""
			_show()
		return
	if _attempted_this_session or _displayed_this_session or not bool(hint.get("eligible", false)) or bool(hint.get("shown", false)):
		return
	if _premium_active() or not _trial_ready() or not _safe_to_present():
		return
	_pending_request_id = host._new_request_id()
	_claim_after_msec = int(host.received_at_msec)
	_attempted_this_session = true
	host._request("/api/action", {
		"type": "subscription_prompt", "choice": "show", "planet_id": host.selected_planet,
		"request_id": _pending_request_id,
	}, "action")


func _context_matches() -> bool:
	return is_instance_valid(host) and not _session.is_empty() and not host.showing_login and host.session_token == _session and host.server_url == _server and str(host.state.get("player", {}).get("id", "")) == _player


func _premium_active() -> bool:
	return bool(host.state.get("premium", {}).get("queue_planning_active", false))


func _owns_claim(hint: Dictionary, request_id: String) -> bool:
	return not request_id.is_empty() and bool(hint.get("shown", false)) and str(hint.get("claim_request_id", "")) == request_id and not _premium_active()


func _trial_ready() -> bool:
	return is_instance_valid(_billing) and _billing.is_available() and _billing.has_trial_offer() and not _billing.formatted_price().strip_edges().is_empty()


func _command_busy() -> bool:
	return host.request_pending or not host.uncertain_action.is_empty() or not host.requested_planet.is_empty() or host.refreshing


func _safe_to_present() -> bool:
	return _context_matches() and not _other_ui_open() and not _command_busy() and not host.selected_planet.is_empty() and not host._ui_interacting() and host.pending_language.is_empty() and host.player_activity.foreground


func _visible(control) -> bool:
	if not is_instance_valid(control):
		return false
	# Godot 4 dialogs are Windows/Viewports, not CanvasItems.
	return control.visible if control is Window else control.is_visible_in_tree()


func _other_back_owner() -> bool:
	return (host.compact_ui != null and host.compact_ui.details_open()) or _visible(host.communications) or _visible(host.alliance_ui) or host.release_open or host.skill_open or (is_instance_valid(host.planet_picker) and host.planet_picker.is_open()) or _visible(host.cancel_project_dialog) or _visible(host.google_reauth_dialog) or _visible(host.email_reauth_dialog)


func _other_ui_open() -> bool:
	if host.current_tab != 0 or host.showing_login or host.update_required or host.connection_editing or host._needs_race_choice():
		return true
	if _visible(host.update_overlay) or _visible(host.race_screen) or _other_back_owner():
		return true
	if is_instance_valid(host.options_panel) and _visible(host.options_panel.get_parent()):
		return true
	if host.review_prompt != null and _visible(host.review_prompt.overlay):
		return true
	return host.login_announcement != null and _visible(host.login_announcement.panel)


func _reset_session() -> void:
	_hide()
	_session = ""
	_player = ""
	_server = ""
	_pending_request_id = ""
	_display_request_id = ""
	_attempted_this_session = false
	_displayed_this_session = false


func is_open() -> bool:
	return is_instance_valid(overlay) and overlay.visible


func handle_back() -> bool:
	if not is_open():
		return false
	_hide()
	return true


func _input(event: InputEvent) -> void:
	if is_open() and event.is_action_pressed("ui_cancel"):
		handle_back()
		get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_GO_BACK_REQUEST:
		handle_back()
	elif what in [NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_APPLICATION_FOCUS_OUT] and is_open() and _purchase_requested:
		# Do not launch a delayed billing sheet after the player leaves the app.
		_hide()


func _show() -> void:
	if _displayed_this_session or not _trial_ready() or not _safe_to_present():
		return
	_displayed_this_session = true
	_failure_message = ""
	_purchase_requested = false
	_display_price = _billing.formatted_price()
	_previous_back_quit = get_tree().quit_on_go_back
	_back_restore_pending = false
	get_tree().quit_on_go_back = false
	var focused: Control = get_viewport().gui_get_focus_owner()
	if focused != null:
		focused.release_focus()
	DisplayServer.virtual_keyboard_hide()
	_translate()
	overlay.show()
	_queue_layout()
	# Neutral focus avoids accidental purchase from an already-held confirm key.
	close_button.grab_focus()


func _hide() -> void:
	var was_open: bool = is_open()
	if is_instance_valid(overlay):
		overlay.hide()
	_purchase_requested = false
	if is_instance_valid(_billing) and _billing.is_trial_purchase_pending():
		_billing.cancel_trial_subscription_purchase()
	if was_open:
		_back_restore_pending = true
		_restore_back.call_deferred()


func _restore_back() -> void:
	if _back_restore_pending and is_inside_tree() and is_instance_valid(host) and not is_open() and not _other_back_owner():
		get_tree().quit_on_go_back = _previous_back_quit
		_back_restore_pending = false


func _purchase() -> void:
	if not is_open() or _purchase_requested:
		return
	if not _context_matches() or not _owns_claim(host.state.get("subscription_prompt", {}), _display_request_id) or _other_ui_open():
		_hide()
		return
	if _command_busy():
		return
	if not _trial_ready():
		_failure_message = I18n.t("Oferta 7 dni za darmo nie jest już dostępna.")
		_refresh_offer()
		return
	_purchase_requested = true
	_refresh_offer()
	# This API refreshes eligibility and cannot fall back to the paid base plan.
	_billing.purchase_trial_subscription()
	_refresh_offer()


func _on_trial_purchase_result(result: String, message: String) -> void:
	if not is_open():
		return
	_purchase_requested = false
	if result in ["started", "cancelled"] or not _context_matches():
		_hide()
		return
	_failure_message = message if not message.is_empty() else I18n.t("Oferta 7 dni za darmo nie jest już dostępna.")
	_refresh_offer()


func _on_billing_changed() -> void:
	if not is_open():
		return
	if not _context_matches() or _premium_active():
		_hide()
		return
	_refresh_offer()


func _refresh_offer() -> void:
	if not is_instance_valid(trial_button):
		return
	var pending: bool = _purchase_requested or _billing.is_trial_purchase_pending()
	if not pending and _trial_ready():
		_display_price = _billing.formatted_price()
	var failed: bool = not _failure_message.is_empty()
	trial_button.text = I18n.t("Wypróbuj 7 dni za darmo")
	trial_button.visible = not failed
	trial_button.disabled = pending or not _trial_ready() or _command_busy()
	terms.text = I18n.t("Potem %s / tydzień. Odnawia się automatycznie.") % _display_price
	terms.visible = not failed and not _display_price.is_empty()
	cancellation.visible = terms.visible
	status.text = _failure_message if failed else _billing.status_text() if pending else ""
	status.visible = not status.text.is_empty()
	_update_focus_loop()
	_queue_layout()


func _translate() -> void:
	if not is_instance_valid(heading):
		return
	heading.text = I18n.t("Planer kolejek")
	description.text = I18n.t("Planuj budowę, flotę i badania.")
	close_button.tooltip_text = I18n.t("Zamknij")
	later_button.text = I18n.t("Może później")
	cancellation.text = I18n.t("Anuluj w Google Play przed końcem okresu próbnego, aby uniknąć opłaty.")
	_refresh_offer()


func _style(background: String, border: String, padding: int = 14) -> StyleBoxFlat:
	var result: StyleBoxFlat = StyleBoxFlat.new()
	result.bg_color = Color(background)
	result.border_color = Color(border)
	result.set_border_width_all(1)
	result.set_corner_radius_all(18)
	result.set_content_margin_all(padding)
	return result


func _make_label(font_size: int, color: String) -> Label:
	var result: Label = Label.new()
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	result.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	result.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	result.mouse_filter = Control.MOUSE_FILTER_IGNORE
	result.add_theme_font_size_override("font_size", font_size)
	result.add_theme_color_override("font_color", Color(color))
	return result


func _make_button(callback: Callable, primary: bool = false) -> Button:
	var result: Button = host._button("", callback)
	result.mouse_filter = Control.MOUSE_FILTER_STOP
	result.custom_minimum_size.y = 80 if primary else 72
	result.add_theme_stylebox_override("normal", _style("e6c180" if primary else "151515", "f4d9a5" if primary else "262626"))
	result.add_theme_stylebox_override("hover", _style("f3d6a0" if primary else "262626", "f4d9a5" if primary else "454545"))
	result.add_theme_stylebox_override("pressed", _style("c5a26a" if primary else "101010", "f4d9a5" if primary else "454545"))
	result.add_theme_stylebox_override("disabled", _style("262626", "353535"))
	result.add_theme_stylebox_override("focus", _style("00000000", "f4d9a5", 0))
	for key: String in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		result.add_theme_color_override(key, Color("151515" if primary else "ededed"))
	result.add_theme_color_override("font_disabled_color", Color("b6b6b6"))
	return result


func _make_overlay() -> void:
	overlay = Control.new()
	overlay.name = "SubscriptionMilestoneOverlay"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	overlay.z_index = 110
	overlay.hide()
	host.add_child(overlay)
	var shade: ColorRect = ColorRect.new()
	shade.color = Color(0, 0, 0, 0.76)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.add_child(shade)
	card = PanelContainer.new()
	card.name = "SubscriptionMilestoneCard"
	card.mouse_filter = Control.MOUSE_FILTER_STOP
	card.add_theme_stylebox_override("panel", _style("101010", "262626", 22))
	overlay.add_child(card)
	layout = VBoxContainer.new()
	layout.add_theme_constant_override("separation", 14)
	card.add_child(layout)
	header = HBoxContainer.new()
	header.add_theme_constant_override("separation", 12)
	layout.add_child(header)
	heading = _make_label(32, "f4e4c7")
	heading.name = "SubscriptionMilestoneTitle"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	header.add_child(heading)
	close_button = _make_button(_hide)
	close_button.name = "CloseSubscriptionMilestone"
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(72, 72)
	close_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	close_button.add_theme_font_size_override("font_size", 32)
	header.add_child(close_button)
	scroll = TouchScroll.new()
	scroll.name = "SubscriptionMilestoneScroll"
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	layout.add_child(scroll)
	body = VBoxContainer.new()
	body.name = "SubscriptionMilestoneBody"
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 14)
	scroll.add_child(body)
	artwork = TextureRect.new()
	artwork.name = "SubscriptionMilestoneBanner"
	artwork.texture = load(BANNER_PATH) as Texture2D
	artwork.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	artwork.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	artwork.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(artwork)
	description = _make_label(26, "eeeeee")
	body.add_child(description)
	trial_button = _make_button(_purchase, true)
	trial_button.name = "StartSubscriptionTrial"
	body.add_child(trial_button)
	terms = _make_label(22, "dedede")
	terms.name = "SubscriptionMilestoneTerms"
	body.add_child(terms)
	cancellation = _make_label(22, "bdbdbd")
	body.add_child(cancellation)
	status = _make_label(22, "e6c180")
	status.name = "SubscriptionMilestoneStatus"
	status.hide()
	body.add_child(status)
	later_button = _make_button(_hide)
	later_button.name = "DismissSubscriptionMilestone"
	body.add_child(later_button)
	body.minimum_size_changed.connect(_queue_layout)
	_translate()
	_queue_layout()


func _update_focus_loop() -> void:
	var buttons: Array[Button] = [close_button]
	if trial_button.visible and not trial_button.disabled:
		buttons.append(trial_button)
	buttons.append(later_button)
	for index: int in range(buttons.size()):
		var previous: Button = buttons[posmod(index - 1, buttons.size())]
		var following: Button = buttons[(index + 1) % buttons.size()]
		buttons[index].focus_previous = buttons[index].get_path_to(previous)
		buttons[index].focus_next = buttons[index].get_path_to(following)
		buttons[index].focus_neighbor_top = buttons[index].get_path_to(previous)
		buttons[index].focus_neighbor_bottom = buttons[index].get_path_to(following)
		buttons[index].focus_neighbor_left = buttons[index].get_path_to(previous)
		buttons[index].focus_neighbor_right = buttons[index].get_path_to(following)


func _queue_layout() -> void:
	if _layout_queued or not is_instance_valid(card):
		return
	_layout_queued = true
	_fit_layout.call_deferred()


func _font_size(control: Control, value: int) -> void:
	if control.get_theme_font_size("font_size") != value:
		control.add_theme_font_size_override("font_size", value)


func _fit_layout() -> void:
	_layout_queued = false
	if not is_instance_valid(card) or not is_instance_valid(host):
		return
	var insets: Vector4i = host.mobile_insets
	var left: float = maxf(18.0, insets.x)
	var top: float = maxf(18.0, insets.y)
	var right: float = maxf(18.0, insets.z)
	var bottom: float = maxf(18.0, insets.w)
	var available: Vector2 = host.size - Vector2(left + right, top + bottom)
	var width: float = maxf(1.0, minf(656.0, available.x))
	var compact: bool = width < 500.0
	_font_size(heading, 26 if compact else 32)
	_font_size(description, 22 if compact else 26)
	_font_size(trial_button, 22 if compact else 27)
	_font_size(later_button, 22 if compact else 26)
	_font_size(terms, 20 if compact else 22)
	_font_size(cancellation, 20 if compact else 22)
	_font_size(status, 20 if compact else 22)
	trial_button.custom_minimum_size.y = 72 if compact else 80
	artwork.custom_minimum_size.y = maxf(0.0, width - 44.0) / 3.0
	var desired_height: float = 44.0 + header.get_combined_minimum_size().y + 14.0 + body.get_combined_minimum_size().y
	card.size = Vector2(width, minf(maxf(1.0, available.y), desired_height))
	card.position = Vector2(left, top) + (available - card.size) * 0.5


func _exit_tree() -> void:
	if is_instance_valid(_billing) and _billing.is_trial_purchase_pending():
		_billing.cancel_trial_subscription_purchase()
	if is_open() or _back_restore_pending:
		get_tree().quit_on_go_back = _previous_back_quit
	if is_instance_valid(overlay):
		overlay.queue_free()
