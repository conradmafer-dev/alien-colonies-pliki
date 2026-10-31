extends Node

class TestClient:
	extends "res://client/scripts/main.gd"
	var url: String
	var commands: Array[Dictionary] = []
	func _load_session() -> void:
		server_url = url
		baked_server_url = url
		session_token = ""
	func _save_session() -> void: pass
	func _poll(_force: bool = false) -> void: pass
	func _check_client_version() -> void: pass
	func _refresh_report_scope() -> void: report_scope = ""
	func _request(path: String, payload: Dictionary, kind: String, method: int = HTTPClient.METHOD_POST) -> void:
		commands.append(payload.duplicate(true))
		super._request(path, payload, kind, method)

var client: TestClient
var checks: int = 0
var failures: int = 0
var url: String
var shots: String = ""

func _ready() -> void:
	print("Colony UI test ready")
	run.call_deferred()
func expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(message)
func settle() -> void:
	for frame: int in range(8): await get_tree().process_frame
func response() -> void:
	# Physical input is dispatched on the next frame before the request starts.
	await settle()
	var end: int = Time.get_ticks_msec() + 15000
	while client.request_pending and Time.get_ticks_msec() < end: await get_tree().process_frame
	expect(not client.request_pending, "HTTP completes")
	await settle()
func shot(name: String) -> void:
	if shots.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(shots.path_join(name + ".png"))
func labels(node: Node) -> String:
	var text: String = str(node.text) + "\n" if node is Label or node is Button else ""
	for child: Node in node.get_children(): text += labels(child)
	return text
func fresh(locale: String, data: Dictionary) -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client)
		client.queue_free()
	get_tree().root.get_node("I18n").set_locale(locale, false)
	client = TestClient.new()
	client.url = url
	get_tree().root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop(); client.update_timer.stop(); client.communications.timer.stop()
	client.session_token = str(data["token"])
	client._apply_state(data["states"][locale].duplicate(true))
	await settle()
func click(point: Vector2) -> void:
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.position = point; motion.global_position = point
	Input.parse_input_event(motion)
	for down: bool in [true, false]:
		var event: InputEventMouseButton = InputEventMouseButton.new()
		event.position = point; event.global_position = point
		event.button_index = MOUSE_BUTTON_LEFT; event.pressed = down
		Input.parse_input_event(event)

func run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	url = args[1]
	if args.size() > 2:
		shots = args[2]; DirAccess.make_dir_recursive_absolute(shots)
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["pl", "en", "de", "es", "fr"]:
		for race: String in ["zetans", "automatons", "symbionts"]:
			if OS.get_environment("ALIEN_UI_QUICK") == "1" and (locale != "pl" or race != "zetans"): continue
			if locale not in ["pl", "en"] and race != "zetans": continue
			print("Checking colony UI: ", locale, " / ", race)
			window.size = Vector2i(720,1600)
			await fresh(locale, fixture[race])
			expect(client.colony_panorama.is_ancestor_of(client.planetary_ui.summary), "Planet stats over panorama")
			expect(client.colony_panorama.is_ancestor_of(client.compact_ui.race_button), "Portrait in panorama")
			expect(client.compact_ui.race_button.icon == client.race_portrait.texture and client.compact_ui.race_button.icon != null, "Correct race portrait: " + race)
			expect(client.onboarding_card.get_parent() == client.tab_bodies[4], "Tutorial belongs to Reports")
			expect(not client.onboarding_card.is_visible_in_tree(), "Tutorial absent on Planet")
			expect(client.active_project.get_parent() == client.tab_bodies[0], "Build timer scrolls with colony")
			expect(client.project_ui.task_for("research").get("kind") == "research", "Research found behind other lanes")
			for lane: String in ["build", "ship", "research"]:
				expect(client.project_ui.panels[lane]["panel"].visible, "Independent active timer: " + lane)
			for size: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520)]:
				window.size = size
				await settle()
				var panorama: Rect2 = client.colony_panorama.get_global_rect()
				expect(panorama.position.y < client.size.y * 0.25, "Panorama starts near top")
				expect(panorama.encloses(client.compact_ui.race_button.get_global_rect()), "Portrait fits panorama")
				expect(panorama.encloses(client.planetary_ui.summary.get_global_rect()), "Summary fits panorama: " + locale)
				for button: Button in client.nav_buttons:
					expect(button.get_global_rect().end.y <= client.size.y + 1, "Navigation fits tall phone")
				for controls: Dictionary in client.building_rows.values():
					expect(controls["panel"].get_global_rect().end.x <= client.size.x + 1, "Building card fits width")
					expect(controls["heading"].get_theme_font_size("font_size") == 23, "Building title size preserved")
					expect(controls["art"].get_parent().custom_minimum_size == Vector2(224,261), "Building image uses fleet height")
				for controls: Dictionary in client.ship_rows.values():
					expect(controls["heading"].get_theme_font_size("font_size") == 23, "Fleet title size preserved")
					expect(controls["art"].get_parent().custom_minimum_size == Vector2(224,188), "Fleet image size preserved")
			window.size = Vector2i(720,1600)
			await settle()
			if locale in ["pl", "en"]: await shot("planet_" + race + "_" + locale)
			click(client.compact_ui.race_button.get_global_rect().get_center())
			await settle()
			expect(client.compact_ui.details_open() and labels(client.compact_ui.modal_body).contains(client.race_name.text), "Portrait opens race details only")
			client.compact_ui.close_details(); await settle()
			click(client.colony_panorama.get_global_rect().position + Vector2(40,40))
			await settle()
			expect(client.compact_ui.details_open(), "Panorama tap opens planet")
			var details: String = labels(client.compact_ui.modal_body)
			expect(not details.contains(get_tree().root.get_node("I18n").t("Każdy poziom budynku zajmuje 1 slot. Badania, statki i obrona nie zajmują slotów.")), "No verbose slot rule")
			expect(not details.contains(get_tree().root.get_node("I18n").t("100% oznacza zwykłe wydobycie przed premiami rasy, badań i budynków.")), "No verbose yield rule")
			if locale == "pl" and race == "zetans": await shot("planet_details_pl")
			client.compact_ui.close_details(); await settle()
	# A dragged panorama must scroll without opening planet details.
	var hit: Control = client.planetary_ui.panorama_hit
	var down: InputEventMouseButton = InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT; down.pressed = true; down.position = Vector2(40,40)
	hit._gui_input(down)
	var drag: InputEventMouseMotion = InputEventMouseMotion.new()
	drag.relative = Vector2(0,60)
	hit._input(drag)
	var up: InputEventMouseButton = InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT; up.pressed = false; up.position = Vector2(40,100)
	hit._gui_input(up)
	expect(not client.compact_ui.details_open(), "Dragging the panorama does not open details")
	# HTTP integration checks use real client commands and the isolated game server.
	window.size = Vector2i(720,1600)
	await fresh("pl", fixture["zetans"])
	client._open_tab(2); client._set_fleet_mode(1); await settle()
	expect(client.project_ui.panels["ship"]["panel"].is_visible_in_tree(), "Ship timer in shipyard")
	for row: Dictionary in [client.building_rows["metal_mine"], client.ship_rows["scout"], client.ship_rows["frigate"]]:
		print("TILE HEIGHT ", row["kind"], " ", row["heading"].text, ": art=", row["art"].size, " card=", row["panel"].size)
	await shot("shipyard_pl")
	client._open_tab(3); await settle()
	expect(client.project_ui.panels["research"]["panel"].is_visible_in_tree(), "Research timer in Research")
	await shot("research_pl")
	var research: Dictionary = client.project_ui.task_for("research")
	client.project_ui.panels["research"]["cancel"].pressed.emit()
	expect(client.cancel_project_payload.get("queue_id") == research.get("id"), "Cancel selects research, not first queue item")
	client.cancel_project_dialog.hide(); client._confirm_cancel_project(); await response()
	expect(client.state.get("queue", []).size() == 2, "Only research removed")
	expect(client.project_ui.task_for("research").is_empty(), "Research timer cleared")
	expect(not client.project_ui.task_for("ship").is_empty() and not client.project_ui.task_for("build").is_empty(), "Build and ship continue")
	client._open_tab(4); await settle()
	expect(client.onboarding_card.is_visible_in_tree() and client.onboarding_description.is_visible_in_tree(), "Full tutorial visible in Reports")
	for row: Node in client.report_list.get_children():
		if row is Button and row.has_meta("title_label"):
			var heading: Label = row.get_meta("title_label")
			var date: Label = row.get_meta("subtitle_label")
			expect(heading.size.y >= 29 and not heading.text.is_empty(), "Report title has readable height")
			expect(date.size.y >= 24 and not date.text.is_empty(), "Report date has readable height")
	await shot("reports_tutorial_pl")
	expect(not client.onboarding_skip.disabled, "Skip usable immediately after an action response")
	click(client.onboarding_skip.get_global_rect().get_center()); await response()
	expect(not client.onboarding_card.visible and client.onboarding_resume.is_visible_in_tree(), "Skip hides tutorial with resume available")
	expect(bool(client.state.get("onboarding", {}).get("skipped", false)), "Skip persisted by server")
	expect(not client.onboarding_resume.disabled, "Resume usable immediately after skip")
	click(client.onboarding_resume.get_global_rect().get_center()); await response()
	expect(client.onboarding_card.is_visible_in_tree() and not client.onboarding_resume.visible, "Resume restores current goal")
	print("Colony UI 0.9.2: %d checks, %d failures" % [checks, failures])
	get_tree().quit(1 if failures else 0)
