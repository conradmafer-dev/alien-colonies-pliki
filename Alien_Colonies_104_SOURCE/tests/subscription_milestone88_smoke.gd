extends "res://tests/android_fleet87_regression.gd"
## Full main.tscn, actual main.gd hierarchy, and offline command/Play fixtures.
## godot --headless --path . tests/subscription_milestone88_smoke.tscn
## A rendering display and -- --capture save the real 450×800 game + popup.

const BillingFixture = preload("res://backend/tests/test_subscription_milestone_prompt.gd")

class OfflineBilling:
	extends BillingFixture.FakeBilling
	func apply_server_state(next_state: Dictionary) -> void:
		available = not bool(next_state.get("premium", {}).get("queue_planning_active", false))
		changed.emit()
	func sign_out() -> void:
		cancel_trial_subscription_purchase()
		available = false
		changed.emit()


func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720, 1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	window.size = Vector2i(450, 800)
	I18n.set_locale("pl", false)
	var packed: PackedScene = load("res://client/scenes/main.tscn")
	var scene_client: Control = packed.instantiate()
	# Preserve the actual scene child/order; override only existing offline seams.
	scene_client.set_script(OfflineClient)
	client = scene_client as OfflineClient
	expect(client != null, "Real scene uses offline main.gd subclass")
	get_tree().root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop()
	client.update_timer.stop()
	client.communications.timer.stop()
	var original_billing = client.queue_billing
	var billing = OfflineBilling.new()
	client.add_child(billing)
	client.queue_billing = billing
	billing.changed.connect(client.planned_queue_ui.refresh_offer)
	original_billing.queue_free()
	var initial: Dictionary = sample("pl")
	initial["premium"] = {"queue_planning_active": false}
	initial["review_prompt"] = {"eligible": false}
	initial["subscription_prompt"] = {"eligible": false, "completed_builds": 5, "shown": false}
	client._apply_state_now(initial, Time.get_ticks_msec())
	client.session_token = "OFFLINE-TEST-ONLY"
	await settle(12)
	var prompt = client.get_node("SubscriptionMilestonePrompt")
	prompt.set_process(false)
	prompt._tick()
	expect(prompt._billing == billing, "Deferred scene setup binds the ready billing service")
	expect(not prompt._other_ui_open(), "Real planet hierarchy is recognized as a safe screen")
	expect(prompt._safe_to_present(), "Actual client session and planet permit the invitation")
	client.compact_ui._begin_details("Offline details")
	expect(prompt._other_ui_open(), "Real details modal blocks the invitation")
	client.compact_ui.close_details()
	client.review_prompt.overlay.show()
	expect(prompt._other_ui_open(), "Real review overlay blocks the invitation")
	client.review_prompt.overlay.hide()
	# The production dialog is created lazily only when an active job is cancelled.
	client.cancel_project_dialog = ConfirmationDialog.new()
	client.add_child(client.cancel_project_dialog)
	client.cancel_project_dialog.popup_centered()
	expect(prompt._other_ui_open(), "Native ConfirmationDialog blocks the invitation")
	client.cancel_project_dialog.hide()
	client._start_new_mission()
	await settle()
	expect(prompt._other_ui_open(), "Actual fleet destination map blocks the invitation")
	client.compact_ui.close_details()
	client._open_tab(0)
	await settle()
	var eligible: Dictionary = client.state.duplicate(true)
	eligible["subscription_prompt"] = {"eligible": true, "completed_builds": 6, "milestone": 6, "shown": false, "claim_request_id": ""}
	client._apply_state_now(eligible, Time.get_ticks_msec())
	await settle()
	prompt._tick()
	expect(client.captured.size() == 1 and client.captured[-1]["payload"]["type"] == "subscription_prompt", "Real command pipeline receives one milestone claim")
	expect(not prompt.is_open(), "Real client waits for authoritative claim response")
	var acknowledged: Dictionary = client.state.duplicate(true)
	acknowledged["subscription_prompt"] = {
		"eligible": false, "completed_builds": 6, "milestone": 6, "shown": true,
		"claim_request_id": client.captured[-1]["payload"]["request_id"],
	}
	await settle()
	client._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"ok": true, "state": acknowledged, "message": ""}).to_utf8_buffer())
	await settle()
	prompt._tick()
	await settle(12)
	expect(prompt.is_open(), "Real server response opens the scene-integrated invitation")
	expect(client.app_screen.is_visible_in_tree(), "Game remains visibly behind the modal")
	expect(prompt.overlay.get_parent() == client, "Modal is attached to the actual game root")
	expect(client.get_global_rect().encloses(prompt.card.get_global_rect()), "Real 450×800 game keeps the full card inside its safe area")
	expect(prompt.card.get_global_rect().encloses(prompt.later_button.get_global_rect()), "Real 450×800 game shows Maybe later without scrolling")
	if "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		var folder: String = "res://tests/subscription_milestone88_screenshots"
		DirAccess.make_dir_recursive_absolute(folder)
		var image: Image = get_viewport().get_texture().get_image()
		expect(image.save_png(folder.path_join("pl_game_450x800.png")) == OK, "Screenshot of actual game and popup saved")
	client.notification(NOTIFICATION_WM_GO_BACK_REQUEST)
	await settle()
	expect(not prompt.is_open() and client.current_tab == 0, "Main Android Back closes only the invitation")
	var claims: int = client.captured.size()
	prompt._tick()
	expect(client.captured.size() == claims, "Real client never repeats the acknowledged invitation")
	print("Subscription scene smoke: %d checks, %d failures" % [checks, failed.size()])
	client.queue_free()
	await settle()
	get_tree().quit(1 if not failed.is_empty() else 0)
