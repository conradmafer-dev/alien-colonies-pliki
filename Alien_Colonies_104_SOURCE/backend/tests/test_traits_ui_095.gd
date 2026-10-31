extends Node

class OfflineClient:
	extends "res://client/scripts/main.gd"
	func _load_session() -> void:
		server_url = "http://127.0.0.1:1"; baked_server_url = server_url; session_token = ""
	func _save_session() -> void: pass
	func _poll(_force: bool = false) -> void: pass
	func _check_client_version() -> void: pass
	func _refresh_report_scope() -> void: report_scope = ""
	func _server_now() -> float: return float(state.get("server_time", 1900000000))

var client: OfflineClient
var fixture: Dictionary
var locale: String
var checks: int = 0
var failures: int = 0
var shots: String = ""

func _ready() -> void: run.call_deferred()
func expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failures += 1; push_error(message)
func settle() -> void:
	for i: int in range(8): await get_tree().process_frame
func labels(node: Node) -> String:
	var text: String = str(node.text) + "\n" if node is Label or node is Button else ""
	for child: Node in node.get_children(): text += labels(child)
	return text
func shot(name: String) -> void:
	if shots.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(shots.path_join(name+".png"))
func fresh() -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client); client.queue_free()
	get_tree().root.get_node("I18n").set_locale(locale, false)
	client = OfflineClient.new(); get_tree().root.add_child(client)
	client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop(); client.update_timer.stop(); client.communications.timer.stop()
func apply(case: String) -> void:
	client.compact_ui.close_details()
	client._apply_state(fixture["states"][case][locale].duplicate(true))
	await settle()
func click(control: Control) -> void:
	var point: Vector2 = control.get_global_rect().get_center()
	var motion: InputEventMouseMotion = InputEventMouseMotion.new(); motion.position=point; motion.global_position=point
	Input.parse_input_event(motion)
	for down: bool in [true, false]:
		var event: InputEventMouseButton = InputEventMouseButton.new()
		event.position=point; event.global_position=point; event.button_index=MOUSE_BUTTON_LEFT; event.pressed=down
		Input.parse_input_event(event)
	await settle()
func geometry(node: Node) -> void:
	if node is Label or node is PanelContainer:
		var control: Control = node
		if control.is_visible_in_tree():
			expect(control.get_global_rect().position.x >= -1, "Left edge fits: "+str(node.name))
			expect(control.get_global_rect().end.x <= client.size.x+1, "Right edge fits: "+str(node.name))
	for child: Node in node.get_children(): geometry(child)
func report_open() -> void:
	client._open_tab(4); await settle()
	var row: Button
	for child: Node in client.report_list.get_children():
		if child is Button and child.has_meta("title_label") and str(child.get_meta("title_label").text)==I18n.t("Raport zwiadu"):
			row = child; break
	expect(is_instance_valid(row), "Actual scout report row exists")
	if is_instance_valid(row): await click(row)

func run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	print("Starting trait UI checks")
	fixture = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	shots = args[1] if args.size()>1 else ""
	if not shots.is_empty(): DirAccess.make_dir_recursive_absolute(shots)
	var root: Window = get_tree().root
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_size = Vector2i(720,1280)
	root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for language: String in ["pl", "en", "de", "es", "fr"]:
		print("Trait UI locale: "+language)
		locale = language; root.size=Vector2i(720,1600); fresh(); await apply("fresh")
		expect(client.planetary_ui.summary.text.begins_with("✦"), "Panorama marks own rare planet")
		# Tap the real panorama surface, preserving the compact home screen.
		await click(client.planetary_ui.panorama_hit)
		expect(client.compact_ui.details_open(), "Panorama opens planet details")
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Pradawne archiwa")), "Home trait localized")
		if locale=="pl": await shot("archives_home_pl")
		for case: String in ["metal_veins", "crystal_geodes", "fuel_reservoirs", "geothermal_sources", "ancient_archives"]:
			await apply(case); client.compact_ui._open_planet(fixture["home_id"]); await settle()
			var feature: Dictionary = client.state["environment"]["trait"]
			expect(labels(client.compact_ui.modal_body).contains(feature["name"]), "All five trait names appear: "+locale)
			expect(labels(client.compact_ui.modal_body).contains(feature["description"]), "Exact bonus description appears")
			geometry(client.compact_ui.modal_body)
		await apply("scouted")
		client.compact_ui._open_planet(fixture["neighbour_id"]); await settle()
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Rzadka cecha: niezbadana. Wyślij zwiad na tę planetę lub obejmij ją obserwatorium.")), "Unvisited neighbour clearly unknown")
		expect(not labels(client.compact_ui.modal_body).contains(I18n.t("Złoża węglowodorów")), "Hidden trait not rendered")
		if locale=="pl": await shot("unexamined_planet_pl")
		client.compact_ui.close_details(); client._open_tab(1); client._choose_system(fixture["system_id"])
		client.galaxy_overview.hide(); client.compact_ui.sync_galaxy(); client._refresh_system_planets(); await settle()
		expect(labels(client.planet_list).contains("✦ "+I18n.t("Kryształowe geody")), "Planet list marks discovered rarity")
		for row: Node in client.planet_list.get_children():
			if row is Button and row.has_meta("title_label"):
				for key: String in ["title_label", "subtitle_label"]:
					var label: Label = row.get_meta(key)
					expect(label.size.x > 150 and label.size.y > 15, "Planet row text has visible dimensions")
					expect(label.get_visible_line_count() > 0, "Planet row text has visible lines")
					expect(row.get_global_rect().encloses(label.get_global_rect()), "Planet row text remains inside its button")
		if locale=="pl": await shot("planet_list_pl")
		await report_open()
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Kryształowe geody")), "Opening actual report displays discovered trait")
		if locale=="pl": await shot("scout_report_pl")
		await apply("observed"); client.compact_ui._open_planet(fixture["neighbour_id"]); await settle()
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Złoża węglowodorów")), "Observation reveals trait")
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Obserwatorium · dane na żywo")), "Live source identified")
		await apply("remembered"); client.compact_ui._open_planet(fixture["neighbour_id"]); await settle()
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Złoża węglowodorów")), "Trait remains known")
		expect(not labels(client.compact_ui.modal_body).contains(I18n.t("Obserwatorium · dane na żywo")), "Memory not described as live")
		if locale=="pl": await shot("remembered_planet_pl")
		await apply("ordinary"); client.compact_ui._open_planet(fixture["neighbour_id"]); await settle()
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Nie wykryto rzadkiej cechy.")), "Confirmed absence differs from unknown")
		await apply("legacy"); await report_open()
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Rzadka cecha: niezbadana. Wyślij zwiad na tę planetę lub obejmij ją obserwatorium.")), "Old reports are honest about missing observations")
		await apply("fresh"); client._open_tab(3); await settle()
		client.compact_ui._open_catalog(client.research_rows["propulsion"]); await settle()
		expect(labels(client.compact_ui.modal_body).contains(I18n.t("Pradawne archiwa")), "Research details explain local time bonus")
		if locale=="pl": await shot("research_bonus_pl")
		for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520)]:
			root.size=dimensions; await apply("observed")
			client.compact_ui._open_planet(fixture["target_id"]); await settle()
			geometry(client.compact_ui.modal_body)
			for button: Button in client.nav_buttons:
				expect(button.get_global_rect().end.y <= client.size.y+1, "Navigation remains inside screen")
			if locale=="pl": await shot("rare_planet_%dx%d_pl" % [dimensions.x,dimensions.y])
			if locale=="de" and dimensions==Vector2i(720,1280): await shot("rare_planet_de_small")
	print("Planet traits UI 0.9.5: %d checks, %d failures" % [checks,failures])
	get_tree().quit(1 if failures else 0)
