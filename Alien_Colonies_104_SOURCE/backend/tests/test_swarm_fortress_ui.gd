extends SceneTree
## Use a real chosen-race state (JSON) from the current server. No network calls.
## Verifies remote skill repricing and private, timestamped scout observations.
const MobileSmoke = preload("res://tests/test_mobile_ui.gd")
var checks: int = 0
var failures: Array[String] = []
var client: MobileSmoke.OfflineClient


func _initialize() -> void:
	_run.call_deferred()


func _expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func _settle() -> void:
	for _frame: int in range(8):
		await process_frame


func _labels(node: Node) -> String:
	var result: String = node.text + "\n" if node is Label or node is Button else ""
	for child: Node in node.get_children():
		result += _labels(child)
	return result


func _width_issues(node: Node, area: Rect2, issues: Array[String]) -> void:
	for child: Node in node.get_children():
		if child is Control and child.is_visible_in_tree():
			var rect: Rect2 = child.get_global_rect()
			if rect.position.x < area.position.x - 1.0 or rect.end.x > area.end.x + 1.0:
				issues.append(str(child.name) + " " + str(rect))
			_width_issues(child, area, issues)


func _run() -> void:
	var args: PackedStringArray = load("res://tests/test_arguments.gd").user_args()
	if args.is_empty():
		push_error("Pass a chosen-race server state JSON")
		quit(2)
		return
	var sample: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	client = MobileSmoke.OfflineClient.new()
	root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.session_token = "offline-fortress-ui"
	client._apply_state(sample)
	await _settle()
	_expect(client.skill_entry_summary.text.contains("Każdy zakup"), "Whole-wheel repricing is explained at the entry")
	client._hunt_swarm()
	await _settle()
	_expect(client.current_tab == 1 and client.intercepted_requests.is_empty(), "Finding a hive opens the galaxy without dispatching a fleet")
	_expect(client.find_child("SwarmOverview", true, false) == null, "No redundant global Swarm overview card")
	_expect(_labels(client.planet_list).contains("Brak rozpoznania"), "No live hive details are shown before reconnaissance")
	_expect(not _labels(client.planet_list).contains("Następny za"), "No live rare-crystal countdown leaks through the map")
	for width: int in [720, 600]:
		root.content_scale_size = Vector2i(width, 1280)
		root.size = Vector2i(width, 1280)
		client.galaxy_overview.visible = false
		await _settle()
		var issues: Array[String] = []
		_width_issues(client.planet_list, client.tabs[1].get_global_rect(), issues)
		_expect(issues.is_empty(), "Hive cards fit %d px: %s" % [width, issues])
	var observation: VBoxContainer = VBoxContainer.new()
	root.add_child(observation)
	client._add_scout_summary(observation, {"scouted_at": client._server_now() - (3 * 3600 + 12 * 60), "swarm_activity": "Umacnia planetę"})
	_expect(_labels(observation).contains("Ostatni zwiad: 3 godz. 12 min temu"), "Scout age is shown as hours and minutes")
	_expect(_labels(observation).contains("Umacnia planetę"), "One short observed AI activity is shown")
	_expect(not _labels(observation).contains("poziomu"), "No verbose building-level narrative")
	observation.queue_free()
	var priced: Dictionary = sample.duplicate(true)
	priced.player.swarm_crystals = 10
	var selected: String = ""
	for node: Dictionary in priced.skill_tree.nodes:
		if bool(node.get("available", false)) and not bool(node.get("unlocked", false)):
			selected = str(node.id)
			node.cost = 7
			node.affordable = true
			break
	_expect(not selected.is_empty(), "Current server supplies a real available branch node")
	client._apply_state(priced)
	client._open_skill_wheel()
	client._select_skill_node(selected)
	_expect(client.skill_detail_cost.text.contains("Koszt: 7 ") and not client.skill_unlock_button.disabled, "UI uses the quoted current price")
	var remote_purchase: Dictionary = priced.duplicate(true)
	remote_purchase.skill_tree.purchased_count = int(remote_purchase.skill_tree.purchased_count) + 1
	for node: Dictionary in remote_purchase.skill_tree.nodes:
		if str(node.id) == selected:
			node.cost = 17
			node.affordable = false
	client._apply_state(remote_purchase)
	_expect(client.skill_detail_cost.text.contains("Koszt: 17 ") and client.skill_unlock_button.text.contains("17"), "A poll reprices the selected node after a remote purchase")
	_expect(client.skill_unlock_button.disabled and client.skill_detail_status.text.contains("Brakuje 7"), "Affordability follows the new server price")
	client.intercepted_requests.clear()
	client._unlock_selected_skill()
	_expect(client.intercepted_requests.is_empty(), "The formerly affordable price cannot submit a stale purchase")
	remote_purchase.player.swarm_crystals = 20
	for node: Dictionary in remote_purchase.skill_tree.nodes:
		if str(node.id) == selected:
			node.affordable = true
	client._apply_state(remote_purchase)
	client._unlock_selected_skill()
	_expect(client.intercepted_requests.size() == 1 and client.intercepted_requests[0].payload.node_id == selected, "After wallet refresh the selected purchase uses its canonical node")
	_expect(not client.intercepted_requests[0].payload.has("cost"), "Client never authorizes its own price")
	_expect(client._exact_integer(5347) == "5 347" and client._exact_integer(123456789) == "123 456 789", "Exact prices stay readable without rounding")
	client.queue_free()
	await process_frame
	print("Fortress UI: %d checks, %d failures; offline transport only" % [checks, failures.size()])
	quit(0 if failures.is_empty() else 1)
