extends SceneTree
## Offline Godot integration checks. Generate a current fixture with
## python tests/make_localization_fixture.py <temporary.json>
## Run Godot with an isolated user-data directory, then pass fixture after --.
## This script is INCLUDED FOR RUNNING IN GODOT; it was not executed by Python.

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

func _initialize() -> void:
	_run.call_deferred()

func expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(message)

func settle() -> void:
	for _frame: int in range(6):
		await process_frame

func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("Pass an offline make_localization_fixture.py JSON path after --")
		quit(2)
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[-1]))
	if not data is Dictionary or not data.has("locales"):
		push_error("Missing generated offline fixture")
		quit(2)
		return
	var service: Node = root.get_node("I18n")
	service.set_locale("en", false)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720, 1280)
	root.size = Vector2i(720, 1280)
	var client: OfflineClient = OfflineClient.new()
	root.add_child(client)
	current_scene = client
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.set_process(false)
	client._apply_state(data["locales"]["en"]["zetans"]["ready"].duplicate(true))
	await settle()
	expect(client.compact_ui != null, "Compact UI constructed")
	for key: String in client.building_rows:
		var controls: Dictionary = client.building_rows[key]
		expect(controls.get("compact", false), "Compact catalogue card: " + key)
		expect(controls["action"].is_visible_in_tree(), "Purchase action remains on list")
	client._open_galaxy_map()
	await settle()
	expect(client.galaxy_overview.visible and not client.compact_ui.system_view.visible, "Map separates the system list")
	client._system_from_overview(client.selected_system)
	await settle()
	expect(not client.galaxy_overview.visible and client.compact_ui.system_view.visible, "System view selected")
	client._open_tab(2)
	client.compact_ui.close_composer()
	await settle()
	expect(not client.fleet_action_bar.visible, "No send dock on mission overview")
	client.compact_ui.open_composer()
	await settle()
	expect(client.fleet_action_bar.visible, "Send dock in mission composer")
	client.compact_ui._begin_details("Offline detail")
	await settle()
	expect(client.compact_ui.details_open(), "Details open separately")
	client.compact_ui.close_details()
	await settle()
	expect(not client.compact_ui.details_open(), "Details return to existing list")
	client._handle_required_update(null)
	await settle()
	expect(client.update_required and client.update_overlay.visible, "Malformed HTTP 426 still shows required update gate")
	expect(not client.update_later_button.visible, "Required update cannot be postponed")
	expect(not client.app_screen.visible, "Gameplay hidden behind mandatory gate")
	client._dismiss_update()
	expect(client.update_overlay.visible, "Dismiss does not bypass gate")
	client._update_check_failed()
	expect(client.update_required, "Network failure cannot clear gate")
	var accepted: Dictionary = {"ok": true, "latest_version_code": 33, "latest_version": "0.7.4", "min_version_code": 0, "message": ""}
	client._on_update_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify(accepted).to_utf8_buffer(), client.server_url, client.update_request_generation)
	await settle()
	expect(not client.update_required and not client.update_overlay.visible, "Operator rollback clears gate after a valid manifest")
	print("Compact/play UI 074: %d checks, %d failures" % [checks, failures])
	client.queue_free()
	await settle()
	quit(1 if failures else 0)
