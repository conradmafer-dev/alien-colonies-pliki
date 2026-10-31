extends SceneTree
## OFFLINE ONLY: all HTTP requests intercepted; no saved sessions are loaded.
## python tests/make_galaxies_ui_fixture.py
## godot --headless --path . --editor --import --quit
## godot --headless --path . --script tests/run_localized_test.gd -- tests/test_galaxies_ui.gd tests/fixtures/galaxies_060.json

const Smoke = preload("res://tests/test_mobile_ui.gd")
var failures: int = 0

func _initialize() -> void:
	_run.call_deferred()

func _expect(value: bool, message: String) -> void:
	if not value:
		failures += 1
		push_error(message)

func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	var file: String = args[0] if not args.is_empty() else "res://tests/fixtures/galaxies_060.json"
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(file))
	if not parsed is Dictionary:
		push_error("Generate the local JSON fixture first.")
		quit(2)
		return
	var fixture: Dictionary = parsed
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	var client = Smoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	client.session_token = "offline-fixture-not-a-real-session"
	client._apply_state(fixture["pre_race"])
	var count: int = client.intercepted_requests.size()
	client._poll()
	_expect(client.intercepted_requests.size() == count, "Race selector must not be rebuilt by automatic polling")
	client._poll(true)
	_expect(client.intercepted_requests.size() == count + 1, "Manual retry remains available at race selection")
	client._apply_state(fixture["state"])
	await process_frame
	_expect(client.galaxy_picker.item_count == 6, "Six galaxy choices")
	var home: String = client.selected_planet
	count = client.intercepted_requests.size()
	for index: int in range(6):
		client._select_galaxy(index)
		_expect(client.selected_galaxy == "g" + str(index + 1), "Galaxy choice changes the map")
		_expect(client._visible_systems().size() == 30, "Only selected galaxy's 30 systems shown")
		_expect(client.system_picker.item_count == 30, "System selector filtered")
		_expect(client.galaxy_map.get("_galaxy_art") is Texture2D, "Galaxy texture imports and loads")
		_expect(client.selected_planet == home, "Browsing never teleports the active colony")
	_expect(client.intercepted_requests.size() == count, "Browsing never sends a paid mission")
	client._select_galaxy(1)
	_expect(client.selected_system == "s31", "Eclipse begins with its own system ID")
	client._apply_state(fixture["state"])
	_expect(client.selected_galaxy == "g2", "Polling preserves selected remote galaxy")
	client._prepare_planet_mission("s31p1", 0)
	client.fleet_inputs["scout"].value = 1
	client._preview_fleet()
	var request: Dictionary = client.intercepted_requests.back()
	_expect(request["path"] == "/api/preview", "Route preview does not dispatch fleet")
	_expect(bool(request["payload"].get("allow_unaffordable", false)), "Preview asks for unaffordable prices")
	client.request_kind = "preview"
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify(fixture["quote"]).to_utf8_buffer())
	_expect(not client.quote_ready and client.send_button.disabled, "Unaffordable jump cannot be sent")
	_expect(client.quote_label.text.contains("Eclipse"), "Quote identifies the destination galaxy")
	_expect(client.quote_label.text.contains(client._exact_integer(int(fixture["quote"]["fuel_cost"]))), "Exact server price visible")
	count = client.intercepted_requests.size()
	client._send_fleet()
	_expect(client.intercepted_requests.size() == count, "No action request when quote is unaffordable")
	client.free()
	print("GALAXIES_UI failures=", failures)
	quit(0 if failures == 0 else 1)
