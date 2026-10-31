extends Node
## Run as test_communications_078.tscn so autoloads exist before script compilation.
## First start serve_communications_fixture.py and pass its JSON path after --.

class OfflineClient:
	extends "res://client/scripts/main.gd"
	func _load_session() -> void:
		server_url = "http://127.0.0.1:1"
		baked_server_url = server_url
		session_token = ""
	func _save_session() -> void:
		pass
	func _poll(_force: bool = false) -> void:
		pass
	func _check_client_version() -> void:
		pass
	func _refresh_report_scope() -> void:
		report_scope = ""

var checks: int = 0
var failures: int = 0
var client: OfflineClient
var chat

func _ready() -> void:
	_run.call_deferred()

func expect(value: bool, text: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(text)

func settle() -> void:
	for _frame: int in range(6):
		await get_tree().process_frame

func wait_network() -> void:
	for _tick: int in range(160):
		await get_tree().create_timer(0.05).timeout
		if not chat.read_busy and not chat.action_busy:
			await settle()
			if not chat.read_busy and not chat.action_busy:
				return
	expect(false, "Local chat requests complete within eight seconds")

func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty():
		get_tree().quit(2)
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[-1]))
	var root: Window = get_tree().root
	root.get_node("I18n").set_locale("en", false)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720,1280)
	root.size = Vector2i(720,1280)
	client = OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.server_url = data["server_url"]
	client.baked_server_url = client.server_url
	client.session_token = data["token"]
	client._apply_state(data["state"])
	chat = client.communications
	chat.timer.stop()
	await settle()
	expect(chat.available, "Server advertises chat capability")
	expect(chat.entry_button.is_visible_in_tree(), "Chat button is reachable from gameplay")
	expect(chat.badge.visible and chat.badge.text == "2", "Public and private unread badge")
	chat.open_global()
	await wait_network()
	expect(chat.visible and not client.app_screen.visible, "Chat has a dedicated full screen")
	expect(chat.rows.size() == 1 and chat.rows[0]["text"] == "Hello, galaxy!", "Global channel loads public messages only")
	expect(int(chat.summary.get("private_unread",0)) == 1, "Opening global does not read private messages")
	expect(int(chat.summary.get("global_unread",0)) == 0, "Displayed global messages are marked read")
	expect(not get_tree().quit_on_go_back, "Android Back cannot quit from open chat")
	chat.editor.text = "Unsent public draft"
	chat.open_private(data["peer_id"],data["peer_name"])
	await wait_network()
	expect(chat.rows.size() == 1 and chat.rows[0]["text"] == "Private trade proposal", "Private channel loads counterpart messages")
	expect(int(chat.summary.get("unread",-1)) == 0, "Reading direct messages clears badge")
	chat.editor.text = "Trade accepted 👽 [b]plain text[/b]"
	chat._send()
	await wait_network()
	expect(chat.editor.text.is_empty(), "Confirmed send clears draft")
	expect(chat.rows.size() == 2 and chat.rows[-1]["text"] == "Trade accepted 👽 [b]plain text[/b]", "Godot sends and receives text through HTTP")
	expect(not chat.rows.is_empty() and chat.rows[-1]["sender_id"] == data["state"]["player"]["id"], "Sender comes from authenticated account")
	chat._toggle_block()
	await wait_network()
	expect(chat.blocked_by_you and not chat.can_send, "Blocking changes sender permissions")
	chat.editor.text = "Blocked draft"
	expect(chat.send_button.disabled, "Blocked conversations cannot send")
	chat._toggle_block()
	await wait_network()
	expect(not chat.blocked_by_you and chat.can_send, "Unblocking restores communication")
	if chat.rows.is_empty():
		get_tree().quit(1)
		return
	chat._ask_report(int(chat.rows[0]["id"]))
	expect(chat.report_dialog.visible, "Reporting has an explicit confirmation")
	chat.report_dialog.hide()
	chat._report_confirmed()
	await wait_network()
	expect(chat.status.text == "The message has been reported.", "Report is accepted by local server")
	chat.editor.text = "x".repeat(501)
	await settle()
	expect(chat.send_button.disabled, "Oversize messages cannot be submitted")
	chat.editor.text = "Private draft"
	chat.open_global()
	await wait_network()
	expect(chat.editor.text == "Unsent public draft", "Drafts are isolated by channel")
	chat.open_inbox()
	await wait_network()
	expect(chat.messages_box.get_child_count() == 1 and chat.messages_box.get_child(0) is Button, "Inbox includes a saved conversation")
	chat.open_private(data["peer_id"],data["peer_name"])
	await wait_network()
	expect(chat.editor.text == "Private draft", "Returning to a conversation restores its draft")
	for width: int in [360,450,720,1080]:
		root.size = Vector2i(width, roundi(width*16.0/9.0))
		await settle()
		expect(chat.margin.get_global_rect().end.x <= client.size.x+1, "Chat remains within viewport")
		expect(chat.editor.size.x > 200, "Composer remains usable at phone widths")
		expect(chat.send_button.get_global_rect().end.x <= chat.margin.get_global_rect().end.x+1, "Send button stays on screen")
	root.size = Vector2i(720,1280)
	chat.margin.add_theme_constant_override("margin_bottom",480)
	await settle()
	expect(chat.composer.get_global_rect().end.y <= 801, "Composer fits above a simulated keyboard")
	chat.margin.add_theme_constant_override("margin_bottom",22)
	chat.close()
	expect(not get_tree().quit_on_go_back, "Back guard is held until the notification completes")
	await settle()
	expect(client.app_screen.visible and not chat.visible, "Closing chat restores gameplay")
	expect(get_tree().quit_on_go_back, "Closing chat restores Android Back behavior")
	# The colony link must open a conversation with that colony's actual owner.
	var planet_id: String = ""
	for system: Dictionary in client.state["galaxy"]:
		for planet: Dictionary in system["planets"]:
			if planet.get("owner_id") == data["peer_id"]:
				planet_id = planet["id"]
	client.compact_ui._open_planet(planet_id)
	await settle()
	var contact: Button
	for child: Node in client.compact_ui.modal_body.get_children():
		if child is Button and child.text == "Send a message":
			contact = child
	expect(contact != null, "Foreign colony contains contact button")
	if contact != null:
		contact.pressed.emit()
		await wait_network()
		expect(chat.peer_id == data["peer_id"], "Colony contact selects the right account")
		expect(not client.compact_ui.details_open() and not get_tree().quit_on_go_back, "Details and chat Back handlers do not conflict")
	chat.close()
	client._reset_world()
	await settle()
	expect(chat.drafts.is_empty() and chat.rows.is_empty() and not chat.badge.visible, "Logout clears conversation data")
	print("Communications 078: %d checks, %d failures" % [checks,failures])
	client.queue_free()
	await settle()
	get_tree().quit(1 if failures else 0)
