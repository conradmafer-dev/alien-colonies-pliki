extends MarginContainer

const RaceTheme = preload("res://client/scripts/race_theme.gd")


signal closed
signal submitted(action: String, payload: Dictionary)
signal defend_requested(planet_id: String)
signal reauthentication_requested

const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
var mode: String = ""
var host: Control
var scroll: ScrollContainer
var content: VBoxContainer
var status: Label
var fields: Dictionary = {}
var buttons: Array[Button] = []
var code_field: LineEdit
var code_status: Label
var code_box: VBoxContainer
var attack_rows: Array[Dictionary] = []
var busy: bool = false
var password_required: bool = true

func configure(owner_control: Control) -> void :
	host = owner_control
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "top", "right", "bottom"]:
		add_theme_constant_override("margin_" + side, 22)
	var background: ColorRect = ColorRect.new()
	background.color = RaceTheme.color(Color("08110d"))
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(background)
	var shell: VBoxContainer = VBoxContainer.new()
	shell.add_theme_constant_override("separation", 14)
	add_child(shell)
	var close_button: Button = host._button(I18n.t("‹ Wróć do gry"), func() -> void : closed.emit())
	close_button.name = "ClosePanel"
	shell.add_child(close_button)
	scroll = TouchScroll.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	shell.add_child(scroll)
	content = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 16)
	scroll.add_child(content)
	visible = false

func clear_private() -> void :
	for field: LineEdit in fields.values():
		field.text = ""
	if is_instance_valid(code_field):
		code_field.text = ""
	if is_instance_valid(code_box):
		code_box.visible = false

func show_mode(next_mode: String, data: Dictionary = {}) -> void :
	if next_mode not in ["account", "help", "attacks"]:
		return
	clear_private()
	for child: Node in content.get_children():
		content.remove_child(child)
		child.queue_free()
	fields.clear()
	buttons.clear()
	attack_rows.clear()
	code_field = null
	code_box = null
	code_status = null
	mode = next_mode
	busy = false
	password_required = not ((bool(data.get("google_linked", false)) or bool(data.get("email_linked", false))) and not bool(data.get("password_login_enabled", true)))
	var captions: Dictionary = {"account": I18n.t("Konto"), "help": I18n.t("Pomoc dowódcy"), "attacks": I18n.t("Nadchodzące wrogie floty")}
	content.add_child(host._label(str(captions.get(mode, I18n.t("Konto"))), 32, "a4ef77"))
	status = host._label("", 21, "a5d5ac")
	status.name = "PanelStatus"
	content.add_child(status)
	if mode == "account":
		_make_account(data)
	elif mode == "help":
		_make_help()
	elif mode == "attacks":
		_make_attacks(data)
	scroll.scroll_vertical = 0
	visible = true

func _field(key: String, caption: String, secret: bool = true) -> LineEdit:
	var field: LineEdit = host._field(content, caption, "", secret)
	field.name = key
	field.max_length = 256
	fields[key] = field
	return field

func _action(caption: String, action: String) -> void :
	var button: Button = host._button(caption, _submit.bind(action), true)
	button.name = action
	content.add_child(button)
	buttons.append(button)

func _make_account(data: Dictionary) -> void :
	content.add_child(host._label(str(data.get("name", I18n.t("Imperium"))), 25))
	if password_required:
		content.add_child(host._label(I18n.t("Potwierdź hasłem zmianę ustawień konta."), 21, "a0b3a4"))
		_field("password", I18n.t("OBECNE HASŁO"))
	else:
		var instruction: String = I18n.t("Zmiany konta wymagają świeżego potwierdzenia Google. W razie potrzeby użyj przycisku poniżej, a potem ponownie wybierz operację.") if bool(data.get("google_linked", false)) else I18n.t("Zmiany konta wymagają świeżego potwierdzenia adresu e-mail. Użyj przycisku poniżej, a potem ponownie wybierz operację.")
		content.add_child(host._label(instruction, 21, "a0b3a4"))
	if bool(data.get("google_linked", false)) and not password_required:
		var confirm_google: Button = host._button(I18n.t("Potwierdź konto Google"), func() -> void : reauthentication_requested.emit())
		confirm_google.name = "ConfirmGoogleAccount"
		content.add_child(confirm_google)
		buttons.append(confirm_google)
	elif bool(data.get("email_linked", false)) and not password_required:
		var confirm_email: Button = host._button(I18n.t("Potwierdź adres e-mail"), func() -> void : reauthentication_requested.emit())
		confirm_email.name = "ConfirmEmailAccount"
		content.add_child(confirm_email)
		buttons.append(confirm_email)
	_action(I18n.t("Wyloguj inne urządzenia"), "logout-others")
	content.add_child(host._label(I18n.t("Usunięcie konta"), 25, "ff9287"))
	content.add_child(host._label(I18n.t("Trwale usuniesz konto i całe imperium. Tego nie można cofnąć."), 21, "ff9287"))
	_field("confirmation", I18n.t("WPISZ DOKŁADNIE: DELETE ACCOUNT"), false)
	_action(I18n.t("Usuń konto i imperium"), "delete")

func _make_help() -> void :
	for entry: Array in [
		[I18n.t("Pierwsze kroki"), I18n.t("Na Planecie realizuj jeden wskazany cel. Przycisk celu otwiera właściwy ekran; każdy zakup zatwierdzasz sam.")], 
		[I18n.t("Trzy rasy"), I18n.t("Zetanie: szybkie floty. Automatony: recykling materiałów. Symbionci: namnażanie statków. Każda rasa ma własne budynki i badanie.")], 
		[I18n.t("Kryształy Roju"), I18n.t("Zwykły kryształ służy do budowy. Ule Roju odnawiają 1 rzadki kryształ co 18 godzin, gdy mają odbudowaną obronę. Zapas jest wspólny dla wszystkich napastników. Łup otrzymasz po powrocie floty.")], 
		[I18n.t("Specjalizacja"), I18n.t("Każdy zakup w kole podnosi ceny pozostałych umiejętności, także w innych gałęziach. Wybieraj ścieżkę rozwoju — zdobycie całego koła jest skrajnie trudne.")], 
		[I18n.t("Twierdze Roju"), I18n.t("Rój umacnia nieliczne ule. Zrób zwiad i skoordynuj naloty z innymi graczami. Atak na pusty skarbiec nie przyniesie kryształów. Rój może zajmować do 8 planet. Sporadycznie wysyła eskortowane transportowce po zapasy graczy, także gdy są wolne planety.")], 
		[I18n.t("Zwiad przed atakiem"), I18n.t("Sprawdź przeciwnika, ustaw liczbę statków, sprawdź trasę i dotknij Wyślij. Czerwony panel ATAK wskazuje zagrożoną kolonię i czas dotarcia.")], 
		[I18n.t("Kolonie i kolejki"), I18n.t("Każda planeta ma własne zasoby i wspólną kolejkę budowy, statków i badań. Zmień planetę u góry. Powtórne dotknięcie Planeta przewija na początek.")], 
		[I18n.t("Bezpieczny dostęp"), I18n.t("Wracaj do imperium tą samą metodą logowania: kontem Google lub adresem e-mail. Po problemie z połączeniem odśwież stan; nie składaj ponownie rozkazu w ciemno.")]
	]:
		content.add_child(host._label(str(entry[0]), 25, "a4ef77"))
		content.add_child(host._label(str(entry[1]), 22))

func _make_attacks(data: Dictionary) -> void :
	var attacks: Array = data.get("attacks", [])
	if attacks.is_empty():
		content.add_child(host._label(I18n.t("Brak nadchodzących wrogich flot."), 24, "a5d5ac"))
	for attack: Dictionary in attacks:
		var card: VBoxContainer = host._card(content)
		card.add_child(host._label(I18n.t("Przejęcie kolonii") if str(attack.get("mission", "")) == "colonize" else I18n.t("Atak"), 21, "ffc56f"))
		card.add_child(host._label(str(attack.get("attacker_name", I18n.t("Przeciwnik"))) + " → " + str(attack.get("target_name", I18n.t("Kolonia"))), 24, "ff9287"))
		card.add_child(host._label(I18n.t("Z: %s") % str(attack.get("origin_name", I18n.t("Nieznana planeta"))), 21, "a0b3a4"))
		var eta: Label = host._label("", 24)
		card.add_child(eta)
		attack_rows.append({"label": eta, "arrives_at": float(attack.get("arrives_at", 0))})
		card.add_child(host._button(I18n.t("Przejdź do obrony"), func() -> void : defend_requested.emit(str(attack.get("target_id", "")))))
	update_attack_times(float(data.get("now", 0)))

func update_attack_times(now: float) -> void :
	for item: Dictionary in attack_rows:
		var remaining: float = float(item["arrives_at"]) - now
		item["label"].text = I18n.t("Dotarcie za %s") % host._duration(remaining) if remaining > 0 else I18n.t("Rozstrzyganie…")

func set_busy(value: bool) -> void :
	busy = value
	for button: Button in buttons:
		button.disabled = value

func set_status(text_value: String, error: bool = false) -> void :
	status.text = text_value
	status.add_theme_color_override("font_color", Color("ff9287") if error else RaceTheme.color(Color("a5d5ac")))
	_ensure_visible.call_deferred(status)

func show_recovery_code(code: String) -> void :
	if mode != "account" or not is_instance_valid(code_field):
		return
	code_field.text = code
	code_status.text = I18n.t("Kod jest aktywny.")
	code_box.visible = not code.is_empty()
	set_status(I18n.t("Zapisz kod teraz. Po zamknięciu tego ekranu nie będzie już widoczny."))
	_ensure_visible.call_deferred(code_box)

func _submit(action: String) -> void :
	if busy or mode != "account" or action not in ["logout-others", "delete"]:
		return
	var payload: Dictionary = {"password": fields["password"].text if password_required else ""}
	if password_required and str(payload["password"]).is_empty():
		set_status(I18n.t("Wpisz obecne hasło."), true)
		return
	if action == "delete":
		payload["confirmation"] = fields["confirmation"].text
		if payload["confirmation"] != "DELETE ACCOUNT":
			set_status(I18n.t("Potwierdź usunięcie: wpisz dokładnie DELETE ACCOUNT."), true)
			return


		payload["confirmation"] = "USUŃ KONTO"
	clear_private()
	DisplayServer.virtual_keyboard_hide()
	set_status(I18n.t("Łączenie…"))
	set_busy(true)
	submitted.emit(action, payload)

func _ensure_visible(control: Control) -> void :

	if visible and is_instance_valid(control) and scroll.is_ancestor_of(control):
		scroll.ensure_control_visible(control)
