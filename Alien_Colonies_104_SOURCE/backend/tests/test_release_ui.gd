extends SceneTree
## Release surfaces, sensitive-operation dispatch, and account-scoped unread state.
## All requests intercepted locally. Optional second arg writes real-render PNGs.
const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
const TouchScroll = preload("res://client/scripts/touch_scroll.gd")
var client: MobileSmoke.OfflineClient
var checks: int = 0
var failures: Array[String] = []
var screenshots: String = ""

func _initialize() -> void:
	_run.call_deferred()

func _expect(condition: bool, caption: String) -> void:
	checks += 1
	if not condition:
		failures.append(caption)
		push_error(caption)

func _settle() -> void:
	for _frame: int in range(9):
		await process_frame

func _bounds(node: Node, area: Rect2, issues: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var rect: Rect2 = child.get_global_rect()
			if rect.position.x < area.position.x - 1 or rect.end.x > area.end.x + 1:
				issues.append(str(child.name) + " " + str(rect))
			_bounds(child, area, issues)

func _capture(name_value: String) -> void:
	if screenshots.is_empty():
		return
	await _settle()
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(screenshots.path_join(name_value + ".png"))

func _response(action: String, code: int, response: Dictionary, result: int = HTTPRequest.RESULT_SUCCESS) -> void:
	client._on_account_response(action, result, code, JSON.stringify(response).to_utf8_buffer())

func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Pass local release fixture JSON")
		quit(2)
		return
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if args.size() > 1:
		screenshots = args[1]
		DirAccess.make_dir_recursive_absolute(screenshots)
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.report_store_path = "user://qa_release_report_reads.cfg"
	DirAccess.remove_absolute(client.report_store_path)
	client.session_token = "offline-test-token"
	client._apply_state(fixture["attack"])
	await _settle()
	_expect(client.CLIENT_VERSION_CODE == 28 and client.CLIENT_VERSION_NAME == "0.6.1", "Release version and Android code")
	_expect(client.onboarding_card.visible and client.onboarding_card.get_index() == 0, "One current goal appears at top of Planeta")
	_expect(client.onboarding_title.text.contains("0/5"), "Real server first-step count")
	_expect(client.incoming_banner.visible and client.incoming_summary.text.begins_with("ATAK"), "Incoming PvP alarm is global and names its destination")
	client.intercepted_requests.clear()
	client._open_onboarding_target()
	await _settle()
	_expect(client.current_tab == 0 and client.intercepted_requests.is_empty(), "Building goal navigates without buying")
	client._open_tab(0)
	await _settle()
	_expect(client.tabs[0].scroll_vertical == 0, "Repeated Planeta goes to top")
	for width: int in [720, 600]:
		root.content_scale_size = Vector2i(width, 1280)
		root.size = Vector2i(width, 1280)
		await _settle()
		var issues: Array[String] = []
		_bounds(client.onboarding_card, client.tabs[0].get_global_rect(), issues)
		_bounds(client.incoming_banner, client.app_screen.get_global_rect(), issues)
		_expect(issues.is_empty(), "Goal/alarm fit %d px: %s" % [width, issues])
		_expect(client.incoming_summary.size.x > 160 and client.incoming_summary.size.y >= 48 and client.incoming_summary.get_line_count() == 2 and not client.incoming_summary.text.is_empty(), "Alarm text has real two-line area at " + str(width))
		_expect(client.onboarding_button.size.y >= 64 and client.incoming_button.size.y >= 64, "Release actions remain touch targets at " + str(width))
		for mode: String in ["account", "help", "attacks"]:
			client._open_release_panel(mode)
			await _settle()
			issues.clear()
			_bounds(client.release_panel.content, client.release_panel.scroll.get_global_rect(), issues)
			_expect(issues.is_empty(), mode + " content fits " + str(width) + ": " + str(issues))
			_expect(client.release_panel.scroll.get_script() == TouchScroll and client.release_panel.scroll.follow_focus, mode + " uses touch + focus-following scroll")
			_expect(not client.app_screen.visible and client.release_panel.visible and not get_tree_back_quit(), "Modal prevents background input / Android Back quit")
			client._close_release_panel()
			await _settle()
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client._open_tab(0)
	await _capture("release_planet_goal_attack")
	client._open_release_panel("attacks")
	_expect(client.release_panel.attack_rows.size() == fixture["attack"]["incoming_attacks"].size(), "Every incoming attack has detail and ETA")
	await _capture("release_attack_details")
	client._close_release_panel()
	# Navigation for each objective, including a missing target, never performs an action.
	for action: String in ["scout", "hunt", "colonize", "skills"]:
		var altered: Dictionary = fixture["attack"].duplicate(true)
		var step: Dictionary = altered["onboarding"]["current"]
		step["action"] = action
		step["target_id"] = str(altered["alien"].get("recommended_target_id", ""))
		client._apply_state(altered)
		client.intercepted_requests.clear()
		client._open_onboarding_target()
		_expect(client.intercepted_requests.is_empty(), action + " objective never dispatches a purchase or flight")
		if action == "skills":
			_expect(client.skill_open, "Skill objective opens existing skill wheel")
			client._close_skill_wheel()
		elif action == "hunt":
			_expect(client.current_tab == 1 and client.galaxy_overview.visible, "Crystal objective opens the hive location in the galaxy")
		else:
			_expect(client.current_tab == 2 and client.mission_picker.selected == (1 if action == "colonize" else 0), action + " prefills correct mission")
	var waiting: Dictionary = fixture["attack"].duplicate(true)
	waiting["onboarding"]["current"]["action"] = "scout"
	waiting["onboarding"]["current"]["target_id"] = ""
	client._apply_state(waiting)
	_expect(client.onboarding_button.disabled, "Waiting for target disables navigation honestly")
	var legacy: Dictionary = fixture["attack"].duplicate(true)
	legacy.erase("onboarding")
	legacy.erase("incoming_attacks")
	client._apply_state(legacy)
	_expect(not client.onboarding_card.visible and not client.incoming_banner.visible, "Old server without release fields stays usable")
	client._apply_state(fixture["attack"])
	client._open_tab(0)
	# Read markers are scoped to both authenticated player and server origin.
	_expect(client.unread_reports > 0, "New account reports have an unread badge")
	client._open_tab(4)
	_expect(client.unread_reports == 0, "Opening Reports marks current reports read")
	var first_scope: String = client.report_scope
	client._open_tab(0)
	client._apply_state(fixture["other"])
	_expect(client.report_scope != first_scope and client.unread_reports > 0, "Switching accounts never shares read markers")
	client._apply_state(fixture["attack"])
	_expect(client.unread_reports == 0, "Returning to original account reloads its own read markers")
	client.server_url = "http://127.0.0.1:2"
	client._apply_state(fixture["attack"])
	_expect(client.report_scope != first_scope and client.unread_reports > 0, "Same player ID on another origin has separate markers")
	client.server_url = "http://127.0.0.1:1"
	client._apply_state(fixture["attack"])
	# Account operations dispatch only on explicit submission; secrets clear immediately.
	client._open_release_panel("account")
	await _capture("release_account")
	client.intercepted_requests.clear()
	client.release_panel.fields["password"].text = "offline-current-password"
	client.release_panel._submit("recovery-code")
	_expect(client.intercepted_requests.size() == 1 and client.intercepted_requests[0]["path"] == "/api/account/recovery-code", "Recovery code rotation uses authenticated endpoint")
	_expect(client.release_panel.fields["password"].text.is_empty() and client.uncertain_action.is_empty(), "Secret fields clear and no sensitive operation becomes auto-retry")
	_response("recovery-code", 200, {"ok": true, "recovery_code": "OFFLINE-ONE-TIME-CODE"})
	_expect(client.release_panel.code_box.visible and client.release_panel.code_field.text == "OFFLINE-ONE-TIME-CODE", "Recovery code is shown only after success")
	client._close_release_panel()
	_expect(client.release_panel.code_field.text.is_empty(), "Closing wipes one-time recovery code")
	client._open_release_panel("account")
	client.release_panel.fields["password"].text = "offline-current-password"
	client.release_panel.fields["confirmation"].text = " USUŃ KONTO"
	client.intercepted_requests.clear()
	client.release_panel._submit("delete")
	_expect(client.intercepted_requests.is_empty(), "Deletion requires exact phrase without leading whitespace")
	client.release_panel.fields["confirmation"].text = "USUŃ KONTO"
	client.release_panel._submit("delete")
	_expect(client.intercepted_requests.size() == 1 and client.intercepted_requests[0]["payload"]["confirmation"] == "USUŃ KONTO", "Deletion sends exact user confirmation and password")
	_response("delete", 403, {"ok": false, "error": "Nieprawidłowe hasło."})
	_expect(client.session_token == "offline-test-token" and client.release_open, "Incorrect password keeps authenticated account and useful error")
	client.release_panel.fields["password"].text = "old-password"
	client.release_panel.fields["new_password"].text = "new-password"
	client.release_panel.fields["repeat_password"].text = "different-password"
	client.intercepted_requests.clear()
	client.release_panel._submit("password")
	_expect(client.intercepted_requests.is_empty(), "Password mismatch never dispatches")
	client.release_panel.fields["repeat_password"].text = "new-password"
	client.release_panel._submit("password")
	_expect(client.intercepted_requests[0]["path"] == "/api/account/password", "Password update explicit dispatch")
	_response("password", 200, {"ok": true, "token": "new-token", "state": fixture["attack"]})
	_expect(client.session_token == "new-token" and client.release_panel.status.text.contains("nowy kod"), "Password rotation accepts new token and explains recovery-code invalidation")
	client.release_panel.fields["password"].text = "new-password"
	client.release_panel._submit("logout-others")
	_response("logout-others", 200, {"ok": true, "message": "Wylogowano pozostałe urządzenia."})
	_expect(client.session_token == "new-token" and client.release_panel.status.text.contains("pozostałe"), "Logout-others preserves current session")
	_response("password", 0, {}, HTTPRequest.RESULT_TIMEOUT)
	_expect(client.release_panel.status.text.contains("nie zostanie ponowiona") and not client.release_panel.busy, "Uncertain account result explains no automatic retry and permits conscious retry")
	client._close_release_panel()
	client._open_release_panel("help")
	await _capture("release_help")
	client._close_release_panel()
	# Public recovery works without a token; invalid code must not trigger session-expiry routing.
	client.session_token = ""
	client._show_login()
	client._open_release_panel("recover")
	await _settle()
	_expect(client.release_panel.visible and not client.login_screen.visible, "Recovery panel replaces login without input behind it")
	client.release_panel.fields["name"].text = "QA zetans"
	client.release_panel.fields["recovery_code"].text = "offline-code"
	client.release_panel.fields["new_password"].text = "new-password"
	client.release_panel.fields["repeat_password"].text = "new-password"
	client.intercepted_requests.clear()
	client.release_panel._submit("recover")
	_expect(client.intercepted_requests.size() == 1 and client.intercepted_requests[0]["path"] == "/api/recover", "Public recover path matches server contract")
	_response("recover", 401, {"ok": false, "error": "Nieprawidłowa nazwa lub kod."})
	_expect(client.release_open and client.release_panel.status.text.contains("kod"), "Invalid recovery code leaves public form open")
	_response("recover", 200, {"ok": true, "token": "recovered-token", "state": fixture["attack"]})
	_expect(client.session_token == "recovered-token" and not client.release_open and not client.showing_login, "Successful recovery opens restored empire with new session")
	client._open_release_panel("account")
	_response("delete", 200, {"ok": true, "deleted": true, "message": "Usunięto konto."})
	_expect(client.session_token.is_empty() and client.state.is_empty() and client.showing_login and client.name_field.text.is_empty(), "Confirmed deletion clears local token and world")
	DirAccess.remove_absolute(client.report_store_path)
	client.queue_free()
	await process_frame
	print("Public release UI: %d checks, %d failures; offline transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)

func get_tree_back_quit() -> bool:
	return quit_on_go_back
