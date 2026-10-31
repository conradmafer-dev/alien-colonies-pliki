extends RefCounted
## Optional invitation. Server eligibility and all three choices are unchanged.
## A full-screen input barrier lives above the game; decorative controls ignore taps.

class FiveStars:
	extends Control
	const COUNT: int = 5
	func _init() -> void:
		name = "ReviewFiveStars"
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		custom_minimum_size = Vector2(250, 48)
		set_meta("star_count", COUNT)
		resized.connect(queue_redraw)
	func _draw() -> void:
		var radius: float = minf(22.0, size.y * 0.45)
		var spacing: float = radius * 2.0 + 12.0
		for star: int in range(COUNT):
			var center: Vector2 = Vector2(size.x * 0.5 + (star - 2) * spacing, size.y * 0.5)
			var points := PackedVector2Array()
			for tip: int in range(10):
				var angle: float = -PI * 0.5 + tip * TAU / 10.0
				points.append(center + Vector2(cos(angle), sin(angle)) * (radius if tip % 2 == 0 else radius * 0.44))
			draw_colored_polygon(points, Color("f6c468"))

var host
var overlay: Control
var layer: CanvasLayer
var backdrop: ColorRect
var card: PanelContainer
var title: Label
var message: Label
var rate_button: Button
var later_button: Button
var dismiss_button: Button
var active: bool = false
var last_session_dismissed: bool = false
var last_player_id: String = ""
var _closing: bool = false
var _back_saved: bool = false
var _previous_back: bool = true


func setup(owner) -> void:
	host = owner
	layer = CanvasLayer.new()
	layer.name = "ReviewModalLayer"
	layer.layer = 200
	host.add_child(layer)
	overlay = Control.new()
	overlay.name = "OptionalPlayReviewOverlay"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	overlay.hide()
	layer.add_child(overlay)
	backdrop = ColorRect.new()
	backdrop.name = "PlayReviewBackdrop"
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.color = Color(0, 0, 0, 0.68)
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.add_child(backdrop)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_PASS
	overlay.add_child(center)
	card = PanelContainer.new()
	card.name = "PlayReviewInvitation"
	card.mouse_filter = Control.MOUSE_FILTER_STOP
	# Fully opaque: game text and controls cannot show through the invitation.
	card.add_theme_stylebox_override("panel", host._style("101010", "50c8e7", 22, 22))
	center.add_child(card)
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 14)
	stack.mouse_filter = Control.MOUSE_FILTER_PASS
	card.add_child(stack)
	stack.add_child(FiveStars.new())
	title = Label.new()
	title.text = I18n.t("Twoje imperium rośnie!")
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	title.add_theme_font_size_override("font_size", 27)
	title.add_theme_color_override("font_color", Color("eaf6ff"))
	stack.add_child(title)
	message = Label.new()
	message.text = I18n.t("Ukończyłeś już pięć budów. Jeśli masz chwilę, podziel się szczerą opinią o Alien Colonies w Google Play.")
	message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	message.mouse_filter = Control.MOUSE_FILTER_IGNORE
	message.add_theme_font_size_override("font_size", 21)
	message.add_theme_color_override("font_color", Color("bed8e8"))
	var text_scroll := ScrollContainer.new()
	text_scroll.name = "ReviewTextScroll"
	text_scroll.custom_minimum_size.y = 64
	text_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	text_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	text_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	stack.add_child(text_scroll)
	message.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text_scroll.add_child(message)
	rate_button = host._button(I18n.t("Oceń grę"), _rate, true)
	rate_button.name = "ReviewRateButton"
	stack.add_child(rate_button)
	later_button = host._button(I18n.t("Nie teraz"), _later)
	later_button.name = "ReviewLaterButton"
	stack.add_child(later_button)
	dismiss_button = host._button(I18n.t("Nie pokazuj ponownie"), _dismiss)
	dismiss_button.name = "ReviewDismissButton"
	stack.add_child(dismiss_button)
	for button: Button in [rate_button, later_button, dismiss_button]:
		button.custom_minimum_size.y = 64
		button.mouse_filter = Control.MOUSE_FILTER_STOP
		button.action_mode = BaseButton.ACTION_MODE_BUTTON_RELEASE
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


	var buttons: Array[Button] = [rate_button, later_button, dismiss_button]
	for index: int in range(buttons.size()):
		buttons[index].focus_next = buttons[(index + 1) % 3].get_path()
		buttons[index].focus_previous = buttons[(index + 2) % 3].get_path()
		buttons[index].focus_neighbor_bottom = buttons[(index + 1) % 3].get_path()
		buttons[index].focus_neighbor_top = buttons[(index + 2) % 3].get_path()


func is_visible() -> bool:
	return is_instance_valid(overlay) and overlay.visible


func refresh(world_state: Dictionary) -> void:
	if not is_instance_valid(overlay) or not is_instance_valid(host):
		return
	var player_id: String = str(world_state.get("player", {}).get("id", ""))
	if player_id != last_player_id:
		hide()
		last_session_dismissed = false
		last_player_id = player_id
	active = bool(world_state.get("review_prompt", {}).get("eligible", false)) and not last_session_dismissed
	var blocked: bool = host.showing_login or host.update_required or host.release_open or host.skill_open or host.request_pending or host._needs_race_choice()
	for property: String in ["ranking_ui", "communications", "alliance_ui"]:
		var other: Variant = host.get(property)
		if is_instance_valid(other) and bool(other.get("visible")):
			blocked = true
	if not active or blocked:
		hide()
	elif not overlay.visible:
		_open()


func _open() -> void:
	# Cancel the pre-existing drag before the modal gets its own input window.
	var guard: Variant = host.get("interaction_guard")
	if is_instance_valid(guard):
		guard.cancel_interaction()
	host.get_tree().call_group("touch_scroll_surfaces", "cancel_gesture")
	_previous_back = host.get_tree().quit_on_go_back
	_back_saved = true
	host.get_tree().quit_on_go_back = false
	var available: Vector2 = host.get_viewport_rect().size
	card.custom_minimum_size.x = minf(600.0, available.x * 0.9)
	card.custom_minimum_size.y = 600
	overlay.show()
	backdrop.show()
	later_button.grab_focus.call_deferred()


func hide() -> void:
	_closing = true
	if is_instance_valid(overlay):
		overlay.hide()
	if is_instance_valid(backdrop):
		backdrop.hide()
	_restore_back()
	_closing = false


func _restore_back() -> void:
	if _back_saved and is_instance_valid(host) and host.is_inside_tree():
		host.get_tree().quit_on_go_back = _previous_back
	_back_saved = false


func _send_choice(choice: String) -> void:
	last_session_dismissed = true
	hide()
	if host.session_token.is_empty() or host.update_required:
		return
	host._request("/api/action", {"type": "review_prompt", "choice": choice}, "action")


func _rate() -> void:
	var error: Error = ERR_CANT_OPEN
	if OS.get_name() == "Android":
		error = OS.shell_open("market://details?id=com.conradmafer.aliencolonies")
	if error != OK:
		error = OS.shell_open("https://play.google.com/store/apps/details?id=com.conradmafer.aliencolonies")
	if error == OK:
		_send_choice("open_store")
	else:
		_later()


func _later() -> void:
	_send_choice("later")


func _dismiss() -> void:
	_send_choice("dismiss")
