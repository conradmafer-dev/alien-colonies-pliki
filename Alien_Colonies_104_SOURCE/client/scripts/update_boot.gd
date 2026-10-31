extends Control
## This small scene runs before main and its artwork are loaded.
const ContentUpdates = preload("res://client/scripts/asset_updates.gd")
const Address = preload("res://client/scripts/server_address.gd")
const CHECK_BUDGET_MS: int = 3000
var assets
var status: Label
var bytes: Label
var meter: ProgressBar
var primary: Button
var secondary: Button
var content_ready: bool = false
var content_failed: bool = false
var entered: bool = false
var postponed: bool = false
var origin: String = ""
var started_at: int = 0
var checking: bool = false
var checking_tween: Tween


func _ready() -> void:
	var background := ColorRect.new()
	background.color = Color("080b10")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 32)
	add_child(margin)
	var center := CenterContainer.new()
	margin.add_child(center)
	var panel := VBoxContainer.new()
	panel.custom_minimum_size.x = minf(580, get_viewport_rect().size.x - 64)
	panel.add_theme_constant_override("separation", 22)
	center.add_child(panel)
	var title := Label.new()
	title.text = "Alien Colonies"
	title.add_theme_font_size_override("font_size", 38)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	panel.add_child(title)
	status = _label(I18n.t("Sprawdzanie aktualizacji…"))
	panel.add_child(status)
	meter = ProgressBar.new()
	meter.custom_minimum_size.y = 30
	meter.hide()
	panel.add_child(meter)
	bytes = _label("")
	bytes.hide()
	panel.add_child(bytes)
	primary = _button("", _primary)
	primary.hide()
	panel.add_child(primary)
	secondary = _button(I18n.t("Później"), _continue)
	secondary.hide()
	panel.add_child(secondary)
	assets = ContentUpdates.new()
	add_child(assets)
	assets.progress.connect(_progress)
	PlayUpdates.changed.connect(_render)
	origin = _server_origin()
	started_at = Time.get_ticks_msec()
	_progress(0, 0, I18n.t("Sprawdzanie aktualizacji…"))
	_check_content.call_deferred()


func _label(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 24)
	return label


func _button(text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = 68
	button.add_theme_font_size_override("font_size", 24)
	button.pressed.connect(action)
	return button


func _server_origin() -> String:
	var baked: String = "https://aliencolonies.com"
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://client/server_config.json"))
	if parsed is Dictionary:
		baked = str(parsed.get("server_url", baked))
	var saved := ConfigFile.new()
	if saved.load("user://session.cfg") == OK and bool(saved.get_value("connection", "manual_override", false)):
		var old_baked: String = str(saved.get_value("connection", "baked_url", ""))
		if old_baked == "https://pogranicze-serwer-production.up.railway.app":
			old_baked = "https://aliencolonies.com"
		if old_baked == baked:
			var custom: Dictionary = Address.parse_input(str(saved.get_value("connection", "url", baked)))
			if not custom.has("error"):
				return str(custom["url"])
	var connection: Dictionary = Address.parse_input(baked)
	return str(connection.get("url", ""))


func _check_content() -> void:
	primary.hide()
	secondary.hide()
	content_ready = false
	content_failed = false
	var result: Dictionary = await assets.run(origin, 100)
	# An optional availability check must not block login when offline.
	# A failed download still offers Retry, keeping the previous complete pack.
	content_ready = bool(result.get("ok", false)) or bool(result.get("check_failed", false))
	content_failed = not content_ready
	_render()


func _progress(done: int, total: int, text: String) -> void:
	status.text = text
	_set_checking(total <= 0 and text == I18n.t("Sprawdzanie aktualizacji…"))
	# Availability checks have no measurable download progress.
	meter.visible = total > 0
	bytes.visible = total > 0
	meter.value = 100.0 * done / total if total > 0 else 0
	bytes.text = "%.1f / %.1f MB" % [done / 1048576.0, total / 1048576.0] if total > 0 else ""


func _set_checking(active: bool) -> void:
	if checking == active:
		return
	checking = active
	if checking_tween != null:
		checking_tween.kill()
		checking_tween = null
	status.modulate.a = 1.0
	if active:
		checking_tween = create_tween().set_loops()
		checking_tween.tween_property(status, "modulate:a", 0.65, 0.85).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		checking_tween.tween_property(status, "modulate:a", 1.0, 0.85).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


func _process(_delta: float) -> void:
	if entered:
		return
	if not content_ready and not content_failed and not assets.downloading and Time.get_ticks_msec() - started_at >= CHECK_BUDGET_MS:
		assets.cancel_check()
		content_ready = true
	_render()


func _render() -> void:
	if entered:
		return
	var phase: String = str(PlayUpdates.status.get("state", "unsupported"))
	if content_failed:
		_set_checking(false)
		status.text = I18n.t("Nie udało się pobrać aktualizacji. Sprawdź połączenie i spróbuj ponownie.")
		primary.text = I18n.t("Spróbuj ponownie")
		primary.disabled = false
		primary.show()
		secondary.text = I18n.t("Kontynuuj")
		secondary.show()
		return
	if not content_ready:
		return
	if phase in ["idle", "checking"] and not postponed and Time.get_ticks_msec() - started_at < CHECK_BUDGET_MS:
		_progress(0, 0, I18n.t("Sprawdzanie aktualizacji…"))
		return
	if phase in ["available", "consent", "pending", "downloading", "downloaded", "installing"] and not postponed:
		var total: int = int(PlayUpdates.status.get("total", 0))
		var done: int = int(PlayUpdates.status.get("downloaded", 0))
		_progress(done, total, I18n.t("Pobieranie aktualizacji…") if phase in ["pending", "downloading"] else I18n.t("Instalowanie aktualizacji…") if phase == "installing" else I18n.t("Dostępna aktualizacja"))
		primary.text = I18n.t("Zainstaluj i uruchom ponownie") if phase == "downloaded" else I18n.t("Pobierz aktualizację")
		primary.disabled = phase not in ["available", "downloaded"]
		primary.show()
		secondary.text = I18n.t("Później")
		secondary.visible = phase not in ["consent", "installing"]
		return
	# No artificial minimum delay after an actual no-update result.
	_enter_game()


func _primary() -> void:
	if content_failed:
		_check_content()
	elif str(PlayUpdates.status.get("state", "")) == "downloaded":
		PlayUpdates.install()
	else:
		PlayUpdates.start()


func _continue() -> void:
	postponed = true
	_enter_game()


func _enter_game() -> void:
	if entered:
		return
	_set_checking(false)
	assets.mount_active()
	entered = true
	# Load main only after mounting the verified complete texture release.
	get_tree().change_scene_to_file("res://client/scenes/main.tscn")
