extends Control

const KEYS: Array[String] = ["total", "buildings", "research", "fleet", "defense"]
const TITLES: Array[String] = ["Ogólny", "Budynki", "Badania", "Flota", "Obrona"]
const RACES: Dictionary = {"zetans": ["Zetanie", "72b8f4"], "automatons": ["Automatony", "f18c85"], "symbionts": ["Symbionci", "99d886"]}
var host
var margin: MarginContainer
var entry: Button
var category
var own_title: Label
var own_breakdown: Label
var reward_panel: VBoxContainer
var reward_caption: Label
var reward_progress: ProgressBar
var reward_status: Label
var reward_rules: AcceptDialog
var reward_clock: float = 0.0
var status: Label
var rows: VBoxContainer
var scroll: ScrollContainer
var previous: Button
var following: Button
var mine: Button
var refresh: Button
var page_label: Label
var request: HTTPRequest
var serial: int = 0
var page: int = 1
var pages: int = 1
var busy: bool = false
var snapshot: Dictionary = {}
var previous_back: bool = true


func setup(client: Control) -> void:
	host = client
	name = "PlayerRanking"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	z_index = 130
	hide()
	var background := ColorRect.new()
	background.color = host._ui_color(Color("08110d"))
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)
	margin = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 22)
	add_child(margin)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 12)
	margin.add_child(layout)
	var heading: HBoxContainer = host._row(layout)
	var back: Button = host._button(I18n.t("Wstecz"), close)
	back.name = "RankingBack"
	back.custom_minimum_size = Vector2(120, 64)
	back.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	heading.add_child(back)
	heading.add_child(host._label(I18n.t("Ranking graczy"), 30))
	var own: VBoxContainer = host._card(layout)
	own_title = host._label(I18n.t("Twoja pozycja") + " · —", 28, "edc77a")
	own_title.name = "OwnRankingPosition"
	own.add_child(own_title)
	own_breakdown = host._label("", 22)
	own.add_child(own_breakdown)
	_build_reward(own)
	var toolbar: HBoxContainer = host._row(layout)
	category = host._choice(I18n.t("Kategoria rankingu"), 64)
	category.name = "RankingCategory"
	for title: String in TITLES:
		category.add_item(I18n.t(title))
	category.select(0)
	category.item_selected.connect(_category_changed)
	toolbar.add_child(category)
	refresh = host._button("↻", _load.bind(1, false))
	refresh.name = "RefreshRanking"
	refresh.tooltip_text = I18n.t("Odśwież")
	refresh.custom_minimum_size = Vector2(64, 64)
	refresh.size_flags_horizontal = Control.SIZE_SHRINK_END
	toolbar.add_child(refresh)
	status = host._label("", 22, "a0b3a4")
	layout.add_child(status)
	scroll = host.TouchScrollScript.new()
	scroll.name = "RankingScroll"
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	layout.add_child(scroll)
	rows = VBoxContainer.new()
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rows.add_theme_constant_override("separation", 8)
	scroll.add_child(rows)
	var paging: HBoxContainer = host._row(layout)
	previous = host._button("‹", _step.bind(-1))
	previous.name = "PreviousRankingPage"
	previous.tooltip_text = I18n.t("Poprzednia strona")
	previous.custom_minimum_size = Vector2(64, 64)
	previous.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	paging.add_child(previous)
	page_label = host._label("1 / 1", 22)
	page_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	page_label.custom_minimum_size.x = 90
	page_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	page_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	paging.add_child(page_label)
	mine = host._button(I18n.t("Moja pozycja"), _load.bind(1, true))
	mine.name = "FindOwnRankingPosition"
	mine.custom_minimum_size = Vector2(200, 64)
	mine.size_flags_horizontal = Control.SIZE_SHRINK_END
	paging.add_child(mine)
	following = host._button("›", _step.bind(1))
	following.name = "NextRankingPage"
	following.tooltip_text = I18n.t("Następna strona")
	following.custom_minimum_size = Vector2(64, 64)
	following.size_flags_horizontal = Control.SIZE_SHRINK_END
	paging.add_child(following)
	var rules: Label = host._label(I18n.t("1 punkt = 1000 surowców wartości ukończonych budynków, badań, floty i obrony. Floty w misji również się liczą. Zapasy i Kryształy Roju nie dają punktów."), 22, "a0b3a4")
	layout.add_child(rules)
	entry = host._button("", open)
	entry.name = "RankingButton"
	entry.icon = preload("res://client/assets/ranking.svg")
	entry.expand_icon = true
	entry.add_theme_constant_override("icon_max_width", 32)
	entry.tooltip_text = I18n.t("Ranking graczy")
	entry.custom_minimum_size = Vector2(64, 64)
	entry.size_flags_horizontal = Control.SIZE_SHRINK_END
	var brand: HBoxContainer = host.planet_picker.get_parent()
	brand.add_child(entry)
	brand.move_child(entry, brand.get_node("SettingsButton").get_index())
	host.compact_ui._queue_fit_header()
	_sync_buttons()


func open() -> void:
	if host.update_required or host.showing_login or host.session_token.is_empty():
		return
	if not visible:
		previous_back = get_tree().quit_on_go_back
		show()
		get_tree().quit_on_go_back = false
		host._sync_screen_visibility()
	_load(1, false)


func close() -> void:
	if not visible:
		return
	category.close()
	reward_rules.hide()
	hide()
	_cancel()
	host._sync_screen_visibility()
	get_tree().quit_on_go_back = previous_back


func reset() -> void:
	close()
	_cancel()
	snapshot.clear()
	page = 1
	pages = 1
	category.select(0)
	own_title.text = I18n.t("Twoja pozycja") + " · —"
	own_breakdown.text = ""
	host._clear(rows)


func _cancel() -> void:
	serial += 1
	if is_instance_valid(request):
		request.cancel_request()
		request.queue_free()
	request = null
	busy = false


func _category_changed(_index: int) -> void:
	snapshot.clear()
	host._clear(rows)
	own_title.text = I18n.t("Twoja pozycja") + " · —"
	own_breakdown.text = ""
	_load(1, false)


func _step(delta: int) -> void:
	_load(clampi(page + delta, 1, pages), false)


func _load(next_page: int, around: bool) -> void:
	if not visible or host.session_token.is_empty():
		return
	_cancel()
	busy = true
	status.text = I18n.t("Ładowanie rankingu…")
	_sync_buttons()
	request = HTTPRequest.new()
	request.use_threads = true
	request.timeout = 20.0
	request.body_size_limit = 1048576
	add_child(request)
	request.request_completed.connect(_received.bind(serial, str(host.session_token), str(host.server_url), around))
	var path := "/api/ranking?category=%s&page=%d&around_me=%d" % [KEYS[category.selected], next_page, int(around)]
	var headers := PackedStringArray(["Accept: application/json", "Accept-Language: " + I18n.locale,
		"X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE), "Authorization: Bearer " + str(host.session_token)])
	if request.request(str(host.server_url) + path, headers, HTTPClient.METHOD_GET) != OK:
		_failure()


func _received(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, generation: int, token: String, server: String, around: bool) -> void:
	if generation != serial or not visible or token != host.session_token or server != host.server_url:
		return
	if host.has_method("_defer_ui_refresh") and host._defer_ui_refresh("ranking:%d" % get_instance_id(),
		_received.bind(result, code, _headers, body, generation, token, server, around)):
		return
	busy = false
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if code == 426 and parsed is Dictionary:
		close()
		host._handle_required_update(parsed)
		return
	if result != HTTPRequest.RESULT_SUCCESS or code != 200 or not parsed is Dictionary or not bool(parsed.get("ok", false)) or int(parsed.get("schema", 0)) != 1:
		_failure()
		return
	snapshot = parsed
	page = int(snapshot.get("page", 1))
	pages = int(snapshot.get("pages", 1))
	var own: Dictionary = snapshot.get("self", {})
	own_title.text = I18n.t("Twoja pozycja") + " · #%s · %s %s" % [host._exact_integer(int(own.get("position", 0))), host._exact_integer(int(own.get("score", 0))), I18n.t("pkt")]
	var scores: Dictionary = own.get("scores", {})
	var parts: PackedStringArray = []
	for index: int in range(1, KEYS.size()):
		parts.append(I18n.t(TITLES[index]) + ": " + host._exact_integer(int(scores.get(KEYS[index], 0))))
	own_breakdown.text = " · ".join(parts)
	status.text = I18n.t("Gracze") + ": " + host._exact_integer(int(snapshot.get("players_total", 0)))
	_render_reward()
	host._clear(rows)
	for row: Dictionary in snapshot.get("items", []):
		var card: VBoxContainer = host._card(rows)
		var panel: Control = card.get_parent()
		panel.name = "RankingRow_" + str(row.get("position", 0))
		panel.set_meta("player_id", str(row.get("player_id", "")))
		panel.set_meta("is_self", bool(row.get("is_self", false)))
		if bool(row.get("is_self", false)):
			panel.add_theme_stylebox_override("panel", host._style("17231d", "edc77a", 12, 14))
		var line: HBoxContainer = host._row(card)
		line.custom_minimum_size.y = 64
		var position: Label = host._label("#" + host._exact_integer(int(row.get("position", 0))), 24, "edc77a")
		position.custom_minimum_size.x = 66
		position.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		position.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		line.add_child(position)
		var player: Label = host._label(str(row.get("name", "")), 24)
		player.name = "RankedPlayerName"
		player.autowrap_mode = TextServer.AUTOWRAP_OFF
		player.clip_text = true
		player.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		player.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		line.add_child(player)
		var standing := VBoxContainer.new()
		standing.name = "RankedStanding"
		standing.custom_minimum_size.x = 100
		standing.size_flags_horizontal = Control.SIZE_SHRINK_END
		standing.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		standing.add_theme_constant_override("separation", 2)
		line.add_child(standing)
		var score: Label = host._label(host._exact_integer(int(row.get("score", 0))) + " " + I18n.t("pkt"), 24)
		score.name = "RankedScore"
		score.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		score.autowrap_mode = TextServer.AUTOWRAP_OFF
		standing.add_child(score)
		var race_id: String = str(row.get("race_id", ""))
		if RACES.has(race_id):
			var race: Label = host._label(I18n.t(RACES[race_id][0]), 21)
			race.name = "RankedRace"
			race.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			race.autowrap_mode = TextServer.AUTOWRAP_OFF
			# Identity colors stay independent of the account's UI palette.
			race.add_theme_color_override("font_color", Color(RACES[race_id][1]))
			standing.add_child(race)
	_scroll_to_own.call_deferred(around, serial)
	_sync_buttons()


func _scroll_to_own(around: bool, generation: int = -1) -> void:
	if generation < 0:
		generation = serial
	# Containers settle after the deferred call. Use content coordinates after
	# layout, never the previous scroll transform or a second visibility jump.
	await get_tree().process_frame
	await get_tree().process_frame
	if generation != serial or not visible or not is_instance_valid(scroll):
		return
	if not around:
		scroll.scroll_vertical = 0
		return
	var own_id: String = str(snapshot.get("self", {}).get("player_id", ""))
	for row: Control in rows.get_children():
		if str(row.get_meta("player_id", "")) == own_id and not own_id.is_empty():
			scroll.scroll_vertical = roundi(row.position.y + row.size.y * 0.5 - scroll.size.y * 0.5)
			return


func _failure() -> void:
	busy = false
	status.text = I18n.t("Nie udało się pobrać rankingu. Naciśnij odśwież, aby spróbować ponownie.")
	_sync_buttons()


func _sync_buttons() -> void:
	previous.disabled = busy or page <= 1
	following.disabled = busy or page >= pages
	mine.disabled = busy
	refresh.disabled = busy
	page_label.text = "%d / %d" % [page, pages]


func _build_reward(own: VBoxContainer) -> void:
	reward_panel = VBoxContainer.new()
	reward_panel.name = "RankingReward"
	reward_panel.add_theme_constant_override("separation", 2)
	own.add_child(reward_panel)
	var first := HBoxContainer.new()
	first.add_theme_constant_override("separation", 8)
	reward_panel.add_child(first)
	var crystal: TextureRect = host._raster_icon("swarm/crystal", 32)
	crystal.name = "RankingRewardCrystal"
	crystal.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	first.add_child(crystal)
	reward_caption = host._label("", 22, "edc77a")
	reward_caption.name = "RankingRewardCaption"
	reward_caption.autowrap_mode = TextServer.AUTOWRAP_OFF
	reward_caption.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	first.add_child(reward_caption)
	var help: Button = host._button("?", _show_reward_rules)
	help.name = "RankingRewardRules"
	help.tooltip_text = I18n.t("Zasady nagród")
	help.custom_minimum_size = Vector2(48, 44)
	help.add_theme_font_size_override("font_size", 22)
	for state: String in ["normal", "hover", "pressed", "disabled", "focus"]:
		help.add_theme_stylebox_override(state, host._style("102118", "647745", 8, 4))
	help.size_flags_horizontal = Control.SIZE_SHRINK_END
	first.add_child(help)
	var second := HBoxContainer.new()
	second.add_theme_constant_override("separation", 10)
	reward_panel.add_child(second)
	reward_progress = ProgressBar.new()
	reward_progress.name = "RankingRewardProgress"
	reward_progress.max_value = 1.0
	reward_progress.step = 0.00001
	reward_progress.show_percentage = false
	reward_progress.custom_minimum_size = Vector2(100, 8)
	reward_progress.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	reward_progress.add_theme_stylebox_override("background", host._style("16231e", "34513e", 4, 0))
	reward_progress.add_theme_stylebox_override("fill", host._style("d5b66d", "d5b66d", 4, 0))
	second.add_child(reward_progress)
	reward_status = host._label("", 21)
	reward_status.name = "RankingRewardStatus"
	reward_status.autowrap_mode = TextServer.AUTOWRAP_OFF
	second.add_child(reward_status)
	reward_rules = AcceptDialog.new()
	reward_rules.name = "RankingRewardRulesDialog"
	reward_rules.title = I18n.t("Zasady nagród")
	reward_rules.dialog_autowrap = true
	reward_rules.theme = host.theme
	add_child(reward_rules)
	reward_panel.hide()


func _process(delta: float) -> void:
	if not visible or not is_instance_valid(reward_panel):
		return
	reward_clock += delta
	if reward_clock >= 1.0:
		reward_clock = 0.0
		_render_reward()


func _render_reward() -> void:
	var value: Dictionary = snapshot.get("reward", {})
	var current: Dictionary = host.state.get("ranking_reward", {})
	if float(current.get("as_of", -1.0)) >= float(value.get("as_of", -1.0)):
		value = current
	reward_panel.visible = int(value.get("schema", 0)) == 1
	if not reward_panel.visible:
		return
	var active: bool = bool(value.get("active", false))
	var position: String = host._exact_integer(int(value.get("position", 0)))
	var interval: float = float(value.get("interval_seconds", 0.0))
	var elapsed: float = maxf(0.0, host._server_now() - float(value.get("as_of", 0.0))) if active else 0.0
	var progress: float = clampf(float(value.get("progress", 0.0)) + (elapsed / interval if active and interval > 0.0 else 0.0), 0.0, 1.0)
	reward_progress.value = progress
	var percent: String = str(floori(progress * 100.0)) + "%"
	if active:
		reward_caption.text = I18n.t("Premia · #%s · 1 / %s d") % [position, str(int(value.get("days_per_crystal", 0)))]
		var remaining: float = maxf(0.0, float(value.get("remaining_seconds", 0.0)) - elapsed)
		var minutes: int = ceili(remaining / 60.0)
		var clock: String = I18n.t("%sd %sh") % [str(minutes / 1440), str((minutes / 60) % 24)] if minutes >= 1440 else I18n.t("%sh %smin") % [str(minutes / 60), str(minutes % 60)]
		reward_status.text = percent + " · " + (I18n.t("Następny: %s") % clock if remaining > 0.0 else I18n.t("Sprawdzanie nagrody…"))
	else:
		reward_caption.text = I18n.t("Premia · #%s · poza TOP 30") % position
		reward_status.text = percent + " · " + I18n.t("Naliczanie wstrzymane")


func _show_reward_rules() -> void:
	reward_rules.title = I18n.t("Zasady nagród")
	reward_rules.dialog_text = I18n.t("Premia za ranking ogólny") + "\n\n" + I18n.t("1. miejsce: 1 kryształ / 3 doby\n2–3: 1 / 5 dób\n4–10: 1 / 7 dób\n11–30: 1 / 14 dni") + "\n\n" + I18n.t("Postęp nalicza się za czas utrzymywania pozycji, także poza grą. Zmiana miejsca zmienia tempo. Poza TOP 30 naliczanie jest wstrzymane, a postęp zachowany. Pełne kryształy trafiają automatycznie na konto i do raportów.")
	reward_rules.popup_centered(Vector2i(mini(640, int(get_viewport_rect().size.x) - 44), 400))
