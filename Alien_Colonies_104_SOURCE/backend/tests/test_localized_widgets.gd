extends SceneTree
## Offline multilingual UI regression. No server requests or account mutations.
var Choice: GDScript
var Quantity: GDScript
var ReleasePanel: GDScript
var Address: GDScript
var Installer: GDScript

class PanelHost:
	extends Control
	func _label(value: String, font_size: int = 22, color: String = "ffffff") -> Label:
		var label: Label = Label.new()
		label.text = value
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		label.add_theme_font_size_override("font_size", font_size)
		label.add_theme_color_override("font_color", Color(color))
		return label
	func _button(caption: String, action: Callable, _primary: bool = false) -> Button:
		var button: Button = Button.new()
		button.text = caption
		button.custom_minimum_size = Vector2(0, 72)
		button.pressed.connect(action)
		return button
	func _field(parent: Node, caption: String, value: String, secret: bool) -> LineEdit:
		parent.add_child(_label(caption))
		var field: LineEdit = LineEdit.new()
		field.text = value
		field.secret = secret
		field.custom_minimum_size.y = 72
		parent.add_child(field)
		return field
	func _card(parent: Node) -> VBoxContainer:
		var card: VBoxContainer = VBoxContainer.new()
		parent.add_child(card)
		return card
	func _duration(value: float) -> String:
		return "%ds" % int(value)

var checks: int = 0
var failures: int = 0
var submissions: Array[Dictionary] = []
var editing_started: int = 0
var selection_events: int = 0
var locale_service: Node

func _initialize() -> void:
	_run.call_deferred()

func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func _settle() -> void:
	for _frame: int in range(4):
		await process_frame

func _locale(value: String) -> void:
	locale_service.call("set_locale", value, false)

func _all_text(node: Node) -> String:
	var result: String = ""
	if node is Label or node is Button:
		result += node.text + "\n"
	for child: Node in node.get_children():
		result += _all_text(child)
	return result

func _run() -> void:
	# --script compiles before autoload registration: load UI dependencies only
	# after the deferred startup, when the real I18n singleton is available.
	Choice = load("res://client/scripts/mobile_choice.gd")
	Quantity = load("res://client/scripts/mobile_quantity.gd")
	ReleasePanel = load("res://client/scripts/release_panel.gd")
	Address = load("res://client/scripts/server_address.gd")
	Installer = load("res://client/scripts/android_apk_install.gd")
	locale_service = root.get_node("I18n")
	var initial_locale: String = str(locale_service.get("locale"))
	_locale("en")
	root.size = Vector2i(600, 1000)
	root.content_scale_size = Vector2i(600, 1000)
	var host: PanelHost = PanelHost.new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var choice: Button = Choice.new()
	choice.position = Vector2(24, 24)
	choice.custom_minimum_size = Vector2(520, 80)
	host.add_child(choice)
	for index: int in range(25):
		choice.add_item("Wybierz %d" % index)
		choice.set_item_metadata(index, "planet_%d" % index)
	choice.select(3)
	choice.item_selected.connect(func(_value: int) -> void: selection_events += 1)
	choice.open()
	await _settle()
	var title: Label = choice._panel.find_child("ChoiceTitle", true, false)
	var close: Button = choice._panel.find_child("CloseChoice", true, false)
	_expect(title.text == "Choose", "Default English chooser heading")
	_expect(close.text == "Close" and choice._search.placeholder_text == "Search…", "English modal controls")
	_expect(choice.text == "Wybierz 3", "User-authored captions stay unchanged")
	_expect(choice.get_selected_metadata() == "planet_3", "Stable metadata is not translated")
	_expect(choice._list.size.y < choice._rows.size.y, "Translated long list remains scrollable")
	_expect(root.get_visible_rect().encloses(choice._panel.get_global_rect()), "Localized modal fits a narrow phone viewport")
	choice._search.text = "not-present"
	choice._refresh_rows()
	await _settle()
	_expect(choice._rows.get_child_count() == 1 and choice._rows.get_child(0).text == "No results", "English empty search state")
	_locale("pl")
	await _settle()
	_expect(title.text == "Wybierz" and close.text == "Zamknij", "Open modal chrome updates after language change")
	_expect(choice._search.text == "not-present", "Language change preserves search input")
	_expect(choice._rows.get_child(0).text == "Brak wyników", "Empty state redraws in Polish")
	_expect(choice.selected == 3 and selection_events == 0, "Language change never selects a planet or emits gameplay actions")
	choice._search.text = ""
	choice._refresh_rows()
	for code: String in ["en", "pl", "de", "es", "fr"]:
		_locale(code)
		await _settle()
		_expect(root.get_visible_rect().encloses(choice._panel.get_global_rect()), "%s chooser fits the phone viewport" % code)
		_expect(close.get_global_rect().end.x <= choice._panel.get_global_rect().end.x, "%s close control stays inside dialog" % code)
		_expect(close.get_theme_font("font").get_string_size(close.text, HORIZONTAL_ALIGNMENT_LEFT, -1, close.get_theme_font_size("font_size")).x <= close.size.x, "%s close label remains readable" % code)
		_expect(choice.selected == 3 and choice.get_selected_metadata() == "planet_3", "%s language change preserves destination" % code)
	choice.close()
	choice.queue_free()
	_locale("en")
	var quantity: HBoxContainer = Quantity.new()
	quantity.position = Vector2(24, 120)
	host.add_child(quantity)
	quantity.max_value = 999999
	quantity.value = 12345
	await _settle()
	_expect(quantity.editor.text == "12345", "Numbers remain intact in English")
	_expect(quantity.minus_button.tooltip_text == "Decrease quantity", "Quantity help is translated")
	quantity.editor.text = "87654"
	_locale("pl")
	await _settle()
	_expect(quantity.editor.text == "87654", "Language change preserves uncommitted number input")
	_expect(quantity.plus_button.tooltip_text == "Zwiększ ilość", "Live quantity help follows locale")
	quantity.edit_gate.edit_requested.connect(func() -> void: editing_started += 1)
	quantity.edit_gate._begin_tap()
	quantity.edit_gate.notification(Control.NOTIFICATION_SCROLL_BEGIN)
	quantity.edit_gate._complete_tap()
	_expect(editing_started == 0, "Scroll cancellation still prevents numeric keyboard activation")
	_expect(quantity.editor.mouse_filter == Control.MOUSE_FILTER_IGNORE and quantity.edit_gate.mouse_filter == Control.MOUSE_FILTER_PASS, "Quantity continues passing touch drags to its scroller")
	quantity.queue_free()
	_locale("en")
	_expect(str(Address.parse_input("bad address").get("error", "")).begins_with("Enter an http://"), "Static address validation uses English")
	_expect(str(Installer._identity_failure("package_mismatch")["message"]).begins_with("The downloaded file belongs"), "APK identity error is translated")
	_expect(str(Installer._identity_failure("unreadable")["message"]).contains("(unreadable)"), "APK diagnostic parameter survives template translation")
	var panel: MarginContainer = ReleasePanel.new()
	host.add_child(panel)
	panel.configure(host)
	panel.submitted.connect(func(action: String, payload: Dictionary) -> void: submissions.append({"action": action, "payload": payload.duplicate(true)}))
	panel.show_mode("account", {"name": "Konto"})
	await _settle()
	var visible_text: String = _all_text(panel)
	_expect(visible_text.contains("Account recovery"), "Account panel is translated")
	_expect(visible_text.contains("TYPE EXACTLY: DELETE ACCOUNT"), "Deletion instructions use one explicit confirmation token")
	_expect(visible_text.contains("\nKonto\n"), "Account name equal to a source key remains unchanged")
	panel.fields["password"].text = "test-password"
	panel.fields["confirmation"].text = "USUŃ KONTO"
	panel._submit("delete")
	_expect(submissions.is_empty(), "Unprompted old-language confirmation is rejected")
	_expect(panel.status.text == "Confirm deletion: type DELETE ACCOUNT exactly.", "Deletion error explains the exact visible token")
	panel.fields["confirmation"].text = "DELETE ACCOUNT"
	panel._submit("delete")
	_expect(submissions.size() == 1, "Exact displayed confirmation permits one request")
	if submissions.size() == 1:
		_expect(submissions[0]["payload"]["confirmation"] == "USUŃ KONTO", "Validated confirmation maps to unchanged server protocol")
		_expect(submissions[0]["payload"]["password"] == "test-password", "Password remains untouched")
	panel.show_mode("attacks", {"now": 10, "attacks": [{"attacker_name": "Rój", "target_name": "Konto", "origin_name": "Wybierz", "arrives_at": 70}]})
	await _settle()
	visible_text = _all_text(panel)
	_expect(visible_text.contains("Rój → Konto"), "Incoming fleet player and colony names are never translated")
	_expect(visible_text.contains("From: Wybierz") and visible_text.contains("Arrives in 60s"), "Attack templates format before adding unchanged dynamic names")
	_locale(initial_locale)
	host.queue_free()
	await _settle()
	print("Localized widgets: %d checks, %d failures" % [checks, failures])
	quit(0 if failures == 0 else 1)
