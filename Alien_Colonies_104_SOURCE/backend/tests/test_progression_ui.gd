extends SceneTree
## Real progression snapshots, real UI, intercepted local transport only.
## godot --headless --path . --script tests/test_progression_ui.gd -- /tmp/progression.json
const RaceSmoke = preload("res://tests/test_race_ui.gd")
const ArtLibrary = preload("res://client/scripts/art_library.gd")
var client: RaceSmoke.RaceOfflineClient
var checks: int = 0
var failures: Array[String] = []


func _initialize() -> void:
	_run.call_deferred()


func _expect(value: bool, text: String) -> void:
	checks += 1
	if not value:
		failures.append(text)
		push_error(text)


func _settle() -> void:
	for _i: int in range(10):
		await process_frame


func _reply(state: Dictionary, message: String = "Umiejętność odblokowana.") -> void:
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"ok": true, "message": message, "state": state}).to_utf8_buffer())


func _labels(node: Node) -> String:
	var result: String = node.text + "\n" if node is Label or node is Button else ""
	for child: Node in node.get_children():
		result += _labels(child)
	return result


func _fit(node: Node, bounds: Rect2, errors: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var rect: Rect2 = child.get_global_rect()
			if rect.position.x < bounds.position.x - 1 or rect.end.x > bounds.end.x + 1 or rect.position.y < bounds.position.y - 1 or rect.end.y > bounds.end.y + 1:
				errors.append(child.name + " " + str(rect))
			if not child is ScrollContainer:
				_fit(child, bounds, errors)


func _test_race(race_id: String, samples: Dictionary) -> void:
	client.request_pending = false
	client.uncertain_action.clear()
	client.session_token = "offline-progression"
	client._apply_state(samples["chosen"])
	await _settle()
	_expect(client.skill_wallet_button.visible and client.nav_buttons.size() == 5, race_id + ": wheel is discoverable without shrinking bottom navigation")
	_expect(int(client.state.player.swarm_crystals) == 0, race_id + ": scarce wallet starts empty")
	client._open_skill_wheel()
	await _settle()
	_expect(client.skill_overlay.visible and not client.app_screen.visible and not client.login_screen.visible, race_id + ": wheel is a modal gameplay screen")
	_expect(not quit_on_go_back, race_id + ": Android Back does not quit while the wheel is open")
	_expect(client.skill_selected_id == race_id + "_root" and client.skill_unlock_button.disabled, race_id + ": the free signature is selected and cannot be bought again")
	var first_node: String = str(samples["selected_node_id"])
	client._select_skill_node(first_node)
	_expect(client.skill_unlock_button.disabled and client.skill_detail_status.text.contains("Brakuje"), race_id + ": insufficient rare crystals are explained before purchase")
	var before: int = client.intercepted_requests.size()
	client._unlock_selected_skill()
	_expect(client.intercepted_requests.size() == before, race_id + ": an unaffordable skill cannot emit an order")
	var other_race: String = "automatons" if race_id == "zetans" else "zetans"
	client._focus_skill_race(other_race)
	_expect(client.skill_selected_id == other_race + "_root" and client.skill_unlock_button.disabled and client.skill_detail_status.text.contains("sąsiednią"), race_id + ": foreign signature requires the connected long path")
	client._apply_state(samples["returning"])
	_expect(int(client.state.player.swarm_crystals) == 0, race_id + ": crystals in transit do not appear in the spendable wallet")
	_expect(_labels(client.fleet_list).contains("kryształów Roju"), race_id + ": return convoy clearly carries scarce loot")
	var has_progress: bool = false
	for entry: Dictionary in client.fleet_countdowns:
		if float(entry.get("seconds", 0)) > 0 and entry.has("bar"):
			has_progress = true
	_expect(has_progress, race_id + ": fleet flight has a duration-based progress bar")
	client._apply_state(samples["earned"])
	client._select_skill_node(first_node)
	_expect(not client.skill_unlock_button.disabled, race_id + ": a returned raid unlocks an affordable adjacent purchase")
	var wallet_before: int = int(client.state.player.swarm_crystals)
	before = client.intercepted_requests.size()
	client._unlock_selected_skill()
	_expect(client.intercepted_requests.size() == before + 1 and client.skill_unlock_button.disabled, race_id + ": one explicit tap starts one authenticated purchase")
	var order: Dictionary = client.intercepted_requests.back().payload.duplicate(true)
	_expect(order.type == "unlock_skill" and order.node_id == first_node and not str(order.request_id).is_empty(), race_id + ": skill orders carry the canonical node and idempotency key")
	_expect(int(client.state.player.swarm_crystals) == wallet_before, race_id + ": purchase does not optimistically spend wallet before server confirmation")
	client._unlock_selected_skill()
	_expect(client.intercepted_requests.size() == before + 1, race_id + ": rapid double tap cannot submit another purchase")
	client._on_response(HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray())
	_expect(client.skill_retry_button.visible and client.skill_unlock_button.disabled and not client.uncertain_action.is_empty(), race_id + ": uncertain purchases retain their order and expose retry")
	client._retry()
	_expect(client.intercepted_requests.back().payload == order, race_id + ": retry repeats exactly the same purchase key and payload")
	_reply(samples["purchased"])
	await _settle()
	_expect(client.uncertain_action.is_empty() and bool(client._skill_node(first_node).unlocked), race_id + ": confirmed purchase refreshes unlocked graph state")
	_expect(int(client.state.player.swarm_crystals) == int(samples.purchased.player.swarm_crystals) and client.skill_unlock_button.disabled, race_id + ": confirmed wallet is the server value and the bought node is disabled")
	_expect(client.skill_detail_icon.get("icon") == client._skill_node(first_node).icon, race_id + ": selected skill uses the same mini illustration as its node")
	for logical: Vector2i in [Vector2i(720, 1280), Vector2i(600, 1000)]:
		root.content_scale_size = logical
		root.size = logical
		await _settle()
		var issues: Array[String] = []
		_fit(client.skill_overlay, client.get_global_rect(), issues)
		_expect(issues.is_empty(), race_id + ": wheel/detail/controls fit %s: %s" % [logical, "; ".join(issues)])
		_expect(client.skill_wheel.size.y >= 280, race_id + ": wheel keeps at least 280 logical pixels of usable height at %s" % logical)
		_expect(client.skill_unlock_button.size.y >= 76, race_id + ": unlock remains a large mobile target")
	root.content_scale_size = Vector2i(600, 1000)
	root.size = Vector2i(600, 1000)
	for node: Dictionary in client._skill_nodes():
		client._select_skill_node(str(node.id))
		if str(node.kind) == "root":
			client.skill_message = "Brak połączenia. Serwer jest chwilowo niedostępny. Odśwież ponawia ten sam zakup."
			client._refresh_skill_controls()
		for _i: int in range(3):
			await process_frame
		var node_issues: Array[String] = []
		_fit(client.skill_overlay, client.get_global_rect(), node_issues)
		_expect(node_issues.is_empty() and client.skill_wheel.size.y >= 280 and client.skill_unlock_button.get_global_rect().end.y <= 978, race_id + ": all-node detail and retry fit short viewport: " + str(node.id) + " " + "; ".join(node_issues))
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client.update_overlay.visible = true
	client._sync_screen_visibility()
	_expect(not client.skill_overlay.visible and not client.app_screen.visible, race_id + ": updater covers and blocks the open skill wheel")
	_expect(client.update_overlay.get_index() > client.skill_overlay.get_index(), race_id + ": updater renders above lazily created wheel")
	client.update_overlay.visible = false
	client._sync_screen_visibility()
	client._apply_state(samples.chosen)
	before = client.intercepted_requests.size()
	client._hunt_swarm()
	_expect(not client.skill_open and client.current_tab == 1 and client.intercepted_requests.size() == before, race_id + ": crystal hunt opens a real target without launching ships")
	_expect(_labels(client.planet_list).contains("Roju"), race_id + ": hunt exposes the Swarm faction and its buildings")
	await _settle()
	_expect(quit_on_go_back, race_id + ": leaving wheel restores the prior native Back behavior")
	client._open_skill_wheel()
	client._end_skill_navigation()
	await _settle()
	_expect(not client.skill_open and quit_on_go_back, race_id + ": the Back close restores navigation after the event")
	client._sync_screen_visibility()


func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Pass the generated progression fixture path")
		quit(2)
		return
	var fixtures: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not fixtures is Dictionary:
		push_error("Invalid fixture JSON")
		quit(2)
		return
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client = RaceSmoke.RaceOfflineClient.new()
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(client)
	await _settle()
	for race_id: String in ["zetans", "automatons", "symbionts"]:
		await _test_race(race_id, fixtures.races[race_id])
	var running: Dictionary = fixtures.races.zetans.earned.duplicate(true)
	var timestamp: float = float(running.server_time)
	running.queue = [{"kind": "build", "key": "metal_mine", "level": 2, "seconds": 120, "started_at": timestamp - 60, "ends_at": timestamp + 60}]
	client._apply_state(running)
	_expect(is_equal_approx(client.queue_duration, 120.0) and client.queue_bar.value > 49 and client.queue_bar.value < 51, "Ongoing projects use their original server duration")
	for entry: Dictionary in running.catalog.buildings:
		entry.seconds = 1
	client._apply_state(running)
	_expect(is_equal_approx(client.queue_duration, 120.0) and client.queue_bar.value > 49 and client.queue_bar.value < 51, "A newly purchased construction speed bonus cannot reset an ongoing project progress bar")
	for asset: String in ArtLibrary.SWARM_ASSETS:
		var picture: Texture2D = ArtLibrary.texture("swarm/" + asset)
		_expect(picture != null, "Swarm gameplay illustration is available: " + asset)
	_expect(ArtLibrary.swarm_cache_keys.size() <= ArtLibrary.MAX_CACHED_SWARM_ART, "Swarm texture cache stays bounded when browsing its building and fleet atlas")
	client._open_skill_wheel()
	client.request_kind = "state"
	client._on_response(HTTPRequest.RESULT_SUCCESS, 401, PackedStringArray(), JSON.stringify({"ok": false, "error": "Sesja wygasła"}).to_utf8_buffer())
	await _settle()
	_expect(client.session_token.is_empty() and client.showing_login and not client.skill_open and not client.skill_overlay.visible, "Expired sessions close the wheel and clear progression state")
	_expect(client._stat_number(0.92) == "0,92" and client._stat_number(80.56) == "80,56" and client._stat_number(12.0) == "12", "Fractional skill-adjusted stats preserve decimals while whole stats stay compact")
	var base_quote: Dictionary = fixtures.races.zetans.chosen.duplicate(true)
	var improved_quote: Dictionary = base_quote.duplicate(true)
	improved_quote.catalog.ships[0].fuel = float(improved_quote.catalog.ships[0].fuel) * 0.92
	_expect(client._quote_world_signature(base_quote) != client._quote_world_signature(improved_quote), "Skill-adjusted navigation stats invalidate an older fleet quote even after a remote purchase")
	_expect(ArtLibrary.texture("swarm/../../server/main") == null, "Swarm asset keys cannot escape their whitelist")
	client.queue_free()
	await _settle()
	print("Progression UI: %d checks, %d failures; intercepted local transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
