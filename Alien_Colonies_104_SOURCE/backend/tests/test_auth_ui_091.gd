extends Node

class AuthClient:
	extends "res://client/scripts/main.gd"
	var test_url: String = "http://127.0.0.1:1"
	var requests: Array[Dictionary] = []
	func _load_session() -> void:
		server_url = test_url
		baked_server_url = test_url
		session_token = ""
	func _save_session() -> void: pass
	func _check_client_version() -> void: pass
	func _poll(_force: bool = false) -> void: pass
	func _refresh_report_scope() -> void: report_scope = ""
	func _request(path: String, payload: Dictionary, kind: String, method: int = HTTPClient.METHOD_POST) -> void:
		requests.append({"path":path,"payload":payload.duplicate(true),"kind":kind})
		super._request(path, payload, kind, method)

var client: AuthClient
var checks: int = 0
var failures: int = 0
var server_url: String
var screenshots: String

func _ready() -> void: run.call_deferred()

func expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)

func settle() -> void:
	for frame: int in range(8): await get_tree().process_frame

func wait_response() -> void:
	var deadline: int = Time.get_ticks_msec() + 20000
	while client.request_pending and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	expect(not client.request_pending, "HTTP response completes")
	await settle()

func fresh(locale: String) -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client)
		client.queue_free()
	get_tree().root.get_node("I18n").set_locale(locale, false)
	client = AuthClient.new()
	client.test_url = server_url
	get_tree().root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.communications.timer.stop()
	await settle()

func shot(name: String) -> void:
	if screenshots.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(screenshots.path_join(name + ".png"))

func error_visible(context: String) -> void:
	expect(client.login_notice.is_visible_in_tree(), context + ": visible notice")
	expect(client.login_message_error and client.login_message_title.visible, context + ": explicit error heading")
	expect(not client.login_message.text.is_empty(), context + ": actual explanation")
	var panel: Rect2 = client.login_notice.get_global_rect()
	var viewport: Rect2 = client.login_scroll.get_global_rect()
	expect(panel.position.y >= viewport.position.y - 1 and panel.end.y <= viewport.end.y + 1, context + ": error scrolled fully into view")
	expect(panel.end.x <= client.size.x + 1, context + ": no horizontal clipping")
	expect(not client.login_submit.disabled, context + ": can correct and retry")

func simulate(code: int, response: Dictionary, transport: int = HTTPRequest.RESULT_SUCCESS) -> void:
	client.request_kind = "auth"
	client.request_pending = true
	client._on_response(transport, code, PackedStringArray(), JSON.stringify(response).to_utf8_buffer())
	await settle()

func run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	server_url = args[0]
	if args.size() > 1:
		screenshots = args[1]
		DirAccess.make_dir_recursive_absolute(screenshots)
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	window.size = Vector2i(720,1280)
	await fresh("pl")
	expect(client.login_mode.is_empty() and not client.login_form.visible, "First choose a mode before entering credentials")
	expect(client.requests.is_empty(), "Opening screen sends no credentials")
	await shot("01_wybor_trybu_pl")
	client.login_mode_buttons[1].pressed.emit()
	await settle()
	expect(client.requests.is_empty(), "Create-empire selector sends no request")
	expect(client.login_mode == "register" and client.login_repeat_row.visible, "Registration mode has confirmation field")
	expect(not client.login_recover_button.visible, "Recovery belongs to login mode")
	client.login_scroll.ensure_control_visible(client.login_submit)
	await settle()
	await shot("02_tworzenie_imperium_pl")
	client.login_submit.pressed.emit()
	await settle()
	expect(client.requests.is_empty(), "Empty name is validated without HTTP")
	error_visible("Empty form")
	await shot("03_puste_dane_pl")
	client.name_field.text = "Existing091"
	client.password_field.text = "bad"
	client.repeat_password_field.text = "bad"
	client.login_submit.pressed.emit()
	await settle()
	expect(client.requests.is_empty() and client.login_message.text.contains("8–128"), "Short password shows precise validation")
	client.password_field.text = "correct-test-password"
	client.repeat_password_field.text = "different-test-password"
	client.login_scroll.scroll_vertical = 9999
	client.login_submit.pressed.emit()
	await settle()
	expect(client.requests.is_empty(), "Mismatched passwords never reach server")
	error_visible("Password mismatch")
	await shot("04_niezgodne_hasla_pl")
	var saved_message: String = client.login_message.text
	client.repeat_password_field.text = "correct-test-password"
	client._notify("background-status")
	expect(client.login_message.text == saved_message, "Editing or background notices do not erase errors")
	client.password_field.text_submitted.emit(client.password_field.text)
	expect(client.requests.is_empty() and client.repeat_password_field.has_focus(), "Registration password Enter advances to confirmation")
	client.repeat_password_field.text_submitted.emit(client.repeat_password_field.text)
	expect(client.request_pending and client.login_submit.disabled, "Submit locks duplicate requests")
	client.login_submit.pressed.emit()
	client.login_mode_buttons[0].pressed.emit()
	expect(client.requests.size() == 1 and client.login_mode == "register", "Busy mode cannot switch or send twice")
	expect(client.requests[0]["path"] == "/api/register", "Registration reaches register endpoint")
	expect(not client.requests[0]["payload"].has("repeat_password"), "Confirmation stays local")
	await wait_response()
	expect(client.login_message.text == "Ta nazwa jest już zajęta.", "Real server duplicate-name error displayed")
	error_visible("Taken name")
	await shot("05_zajeta_nazwa_pl")
	client.login_mode_buttons[0].pressed.emit()
	await settle()
	expect(client.requests.size() == 1 and client.login_mode == "login", "Switching to login only changes form")
	expect(not client.login_repeat_row.visible and client.login_recover_button.visible, "Login uses two fields and offers recovery")
	expect(not client.login_notice.visible, "Explicit mode switch clears previous form error")
	await shot("06_logowanie_pl")
	client.password_field.text = "incorrect-password"
	client.password_field.text_submitted.emit(client.password_field.text)
	await wait_response()
	expect(client.requests[-1]["path"] == "/api/login", "Login password Enter reaches login endpoint")
	expect(client.login_message.text == "Nieprawidłowa nazwa lub hasło.", "Real 401 error remains a credential error")
	expect(client.login_mode == "login" and client.name_field.text == "Existing091", "Wrong password preserves mode and name")
	error_visible("Wrong password")
	await shot("07_bledne_haslo_pl")
	client.password_field.text = "correct-test-password"
	client.login_submit.pressed.emit()
	await wait_response()
	expect(not client.showing_login and not client.session_token.is_empty(), "Real valid login enters the game")
	expect(client.password_field.text.is_empty() and client.repeat_password_field.text.is_empty(), "Successful login clears both password fields")
	await fresh("en")
	client.login_mode_buttons[1].pressed.emit()
	client.name_field.text = "NewEmpire091"
	client.password_field.text = "new-test-password"
	client.repeat_password_field.text = "new-test-password"
	client.login_submit.pressed.emit()
	await wait_response()
	expect(not client.showing_login and client.state["player"]["name"] == "NewEmpire091", "Real registration creates an empire only after submit")
	expect(client.race_screen.visible, "New account reaches race choice")
	await fresh("pl")
	client.login_mode_buttons[0].pressed.emit()
	await simulate(0, {}, HTTPRequest.RESULT_CANT_CONNECT)
	error_visible("Connection failure")
	await shot("08_brak_polaczenia_pl")
	await simulate(503, {})
	error_visible("Server failure")
	await simulate(400, {"ok":false,"error":""})
	error_visible("Empty server error fallback")
	await simulate(200, {"ok":true})
	error_visible("Incomplete success payload")
	client._retry()
	expect(client.requests.is_empty(), "Connection retry cannot log in or register implicitly")
	client._set_login_mode("register")
	client.name_field.text = "N@me"
	client.password_field.text = "new-test-password"
	client.repeat_password_field.text = "new-test-password"
	client.login_submit.pressed.emit()
	await wait_response()
	expect(client.login_message.text.contains("litery, cyfry"), "Server rejects forbidden characters visibly")
	error_visible("Invalid name characters")
	for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520)]:
		window.size = dimensions
		for locale: String in ["en","pl","de","es","fr"]:
			await fresh(locale)
			client.login_mode_buttons[1].pressed.emit()
			client.name_field.text = "NewTest"
			client.password_field.text = "new-test-password"
			client.repeat_password_field.text = "different-password"
			client.login_scroll.scroll_vertical = 9999
			client.login_submit.pressed.emit()
			await settle()
			error_visible(locale + " / " + str(dimensions))
			if locale == "de" and dimensions == Vector2i(720,1280): await shot("09_blad_de")
	window.size = Vector2i(720,1280)
	await fresh("pl")
	client._set_login_mode("register")
	client.login_screen.add_theme_constant_override("margin_bottom", 560)
	client.name_field.text = "NewTest"
	client.password_field.text = "new-test-password"
	client.login_submit.pressed.emit()
	await settle()
	error_visible("Simulated keyboard inset")
	# Language reconstruction restores registration mode and both fields only in memory.
	var resumed: AuthClient = AuthClient.new()
	resumed.test_url = server_url
	resumed.set_meta("language_resume", {"login_mode":"register","name":"InMemory","password":"private-password","repeat_password":"private-password"})
	get_tree().root.add_child(resumed)
	resumed.poll_timer.stop(); resumed.update_timer.stop(); resumed.communications.timer.stop()
	await settle()
	expect(resumed.login_mode == "register" and resumed.login_repeat_row.visible, "Language reconstruction retains chosen mode")
	expect(resumed.password_field.text == "private-password" and resumed.repeat_password_field.text == "private-password", "Language reconstruction preserves both fields in memory")
	expect(not resumed.language_resume.has("password") and not resumed.language_resume.has("repeat_password"), "Passwords removed from resume dictionary")
	print("Auth UI 0.9.1: %d checks, %d failures" % [checks,failures])
	get_tree().quit(1 if failures else 0)
