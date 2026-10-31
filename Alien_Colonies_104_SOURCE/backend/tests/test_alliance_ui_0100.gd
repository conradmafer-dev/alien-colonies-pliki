extends Node
class TestClient:
	extends "res://client/scripts/main.gd"
	var url: String
	func _load_session() -> void:
		server_url = url; baked_server_url = url; session_token = ""
	func _save_session() -> void: pass
	func _poll(_force: bool = false) -> void: pass
	func _check_client_version() -> void: pass
	func _refresh_report_scope() -> void: report_scope = ""
var client: TestClient
var fixture: Dictionary
var url: String
var shots: String
var checks: int = 0
var failures: int = 0

func _ready() -> void: run.call_deferred()
func expect(ok: bool, text: String) -> void:
	checks += 1
	if not ok: failures += 1; push_error(text)
func settle() -> void:
	for i: int in range(8): await get_tree().process_frame
func wait_requests() -> void:
	var deadline: int = Time.get_ticks_msec() + 14000
	while (client.alliance_ui.action_busy or client.alliance_ui.member_busy or client.alliance_ui.operation_busy) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	await settle()
	expect(not client.alliance_ui.action_busy and not client.alliance_ui.member_busy, "Requests finish")
func fresh(locale: String, account: String) -> void:
	if is_instance_valid(client):
		client.get_parent().remove_child(client); client.queue_free()
	get_tree().root.get_node("I18n").set_locale(locale, false)
	client = TestClient.new(); client.url = url
	get_tree().root.add_child(client); client.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	client.poll_timer.stop(); client.update_timer.stop(); client.communications.timer.stop(); client.alliance_ui.timer.stop()
	client.session_token = fixture["accounts"][account]["token"]
	client._apply_state(fixture["states"][locale][account].duplicate(true))
	await settle()
	client.alliance_ui.open()
	await wait_requests()
	if client.alliance_ui.data.is_empty():
		print("Initial load failed: "+client.alliance_ui.status.text)
		get_tree().quit(1)
func find_button(node: Node, caption: String) -> Button:
	if node is Button and node.text == caption: return node
	for child: Node in node.get_children():
		var button: Button = find_button(child,caption)
		if button != null: return button
	return null
func press(caption: String) -> void:
	var button: Button = find_button(client.alliance_ui,caption)
	expect(button != null, "Button exists: "+caption)
	if button != null: button.pressed.emit()
	await wait_requests()
func all_text(node: Node) -> String:
	var text: String = str(node.text)+"\n" if node is Label or node is Button else ""
	for child: Node in node.get_children(): text += all_text(child)
	return text
func geometry(node: Node) -> void:
	if node is Button and node.is_visible_in_tree() and node.get_parent() is not Window:
		expect(node.size.y >= 56, "Touch height: "+node.name)
		expect(node.get_global_rect().end.x <= get_viewport().get_visible_rect().end.x + 1, "Fits width: "+node.name)
	if node is Label and node.is_visible_in_tree():
		expect(node.get_global_rect().end.x <= get_viewport().get_visible_rect().end.x + 1, "Label fits width")
	for child: Node in node.get_children(): geometry(child)
func shot(name: String) -> void:
	if shots.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(shots.path_join(name+".png"))
func run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	fixture = JSON.parse_string(FileAccess.get_file_as_string(args[0])); url = args[1]
	shots = args[2] if args.size()>2 else ""
	if not shots.is_empty(): DirAccess.make_dir_recursive_absolute(shots)
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	window.size = Vector2i(720,1280)
	if OS.get_environment("ALIEN_UI_PREVIEW_RESIZE_ONLY") == "1":
		await run_preview_resize()
		return
	await fresh("pl","solo")
	var ui = client.alliance_ui
	ui.search_field.text = "Sentinels"; ui._search(); await wait_requests()
	expect(ui.data.get("directory",[]).size() == 1,"Directory search reaches backend")
	expect(ui._alliance().is_empty(),"Nonmember sees directory")
	await press(I18n.t("Załóż sojusz"))
	ui.fields["name"].text = "Sentinels of Orion"; ui.fields["tag"].text = "ORI"
	ui.fields["description"].text = "Retained draft"
	var original_field = ui.fields["name"]
	ui._poll(); await wait_requests()
	expect(ui.fields["name"] == original_field and ui.fields["description"].text == "Retained draft","Polling preserves form and inputs")
	await press(I18n.t("Utwórz"))
	expect(ui.form == "edit" and ui.fields["description"].text == "Retained draft","Server validation preserves form")
	expect(ui.status.is_visible_in_tree() and not ui.status.text.is_empty(),"Validation error visibly displayed")
	var prior_error: String = ui.status.text
	ui._poll(); await wait_requests(); expect(ui.status.text == prior_error,"Polling does not clear validation error")
	await shot("alliance_validation_pl")
	ui.fields["name"].text = "Pathfinders"; ui.fields["tag"].text = "PATH"
	await press(I18n.t("Utwórz"))
	expect(str(ui._alliance().get("tag","")) == "PATH","Create action reaches actual backend")
	for locale: String in ["pl","en","de","es","fr"]:
		await fresh(locale,"leader"); ui = client.alliance_ui
		expect(ui._role() == "leader","Leader permissions loaded")
		ui._select_tab(1); await settle()
		expect(all_text(ui.body).contains("AllianceEngineer"),"Member list uses real alliance")
		await press(I18n.t("Przekaż dowództwo"))
		expect(ui.form == "confirm","Transfer requires separate confirmation")
		ui.go_back(); await settle()
		ui._invite_form(); ui.fields["player_name"].text = "PlayerDoesNotExist"
		await press(I18n.t("Wyślij zaproszenie"))
		expect(ui.status.is_visible_in_tree() and ui.fields["player_name"].text == "PlayerDoesNotExist","Bad invitation visible and preserved")
		ui.go_back(); ui._select_tab(3); await settle()
		ui.editor.text = "Joint operation · " + locale
		ui._chat_changed(); await press(I18n.t("Wyślij"))
		if locale == "pl":
			expect(ui.retry_button.is_visible_in_tree() and not ui.editor.text.is_empty(), "Lost committed response retains draft and offers retry")
			var original_id: String = str(ui.contexts["action"]["payload"]["request_id"])
			var original_error: String = ui.status.text
			ui._set_status("Simulated polling error")
			expect(ui.retry_button.is_visible_in_tree() and ui.status.text == original_error,"Poll error cannot hide unresolved action retry")
			ui._select_tab(0); ui._invite_form()
			expect(str(ui.retry_context.get("payload",{}).get("request_id","")) == original_id,"Tab and form changes retain unresolved request ID")
			ui._post({"action":"invite","player_name":"BlockedNewCommand"})
			expect(not ui.action_busy and str(ui.contexts["action"]["payload"]["request_id"]) == original_id,"New mutation waits for unresolved command")
			await press(I18n.t("Spróbuj ponownie"))
			expect(str(ui.contexts["action"]["payload"]["request_id"]) == original_id,"Network retry reuses same request ID")
			var duplicates: int = 0
			for message: Dictionary in ui._alliance().get("chat",[]):
				if message.get("text","") == "Joint operation · pl": duplicates += 1
			expect(duplicates == 1,"Lost response retry never sends duplicate chat")
			ui._select_tab(3); await settle()
		expect(ui.editor.text.is_empty() and all_text(ui.body).contains("Joint operation · "+locale),"Alliance chat delivered, then draft cleared")
		if locale == "pl": await shot("alliance_chat_pl")
		ui.editor.text = "Preserve this chat draft"; ui._poll(); await wait_requests()
		expect(ui.editor.text == "Preserve this chat draft","Chat polling preserves composition")
		ui.editor.text = ""
		ui._select_tab(2); await wait_requests()
		await press(I18n.t("Zaplanuj atak"))
		var target = ui.fields["target"]
		for i: int in range(target.item_count):
			if str(target.get_item_metadata(i)) == fixture["enemy"]: target.select(i)
		ui.fields["delay"].select(8)
		await press(I18n.t("Utwórz operację"))
		expect(ui.form.is_empty() and not ui.operations.get("operations",[]).is_empty(),"Plan created without dispatch")
		var operation: Dictionary = ui.operations["operations"][0]
		expect(operation.get("participants",[]).is_empty(),"Creating plan dispatches no ships")
		ui._join_form(operation); await settle()
		expect(ui.quantities.has("frigate"),"Available ships use backend origin")
		ui.quantities["frigate"].value = 2
		await press(I18n.t("Sprawdź trasę"))
		expect(ui.form == "preview","Actual server preview opens confirmation")
		if ui.form == "preview":
			expect(float(ui.form_context["preview"].get("fuel_cost",0)) > 0,"Actual fuel cost displayed")
			expect(all_text(ui.body).contains(I18n.t("Łączny koszt paliwa: %s").split("%s")[0]),"Visible fuel summary")
			expect(all_text(ui.body).contains(I18n.t("Ta misja wyłączy Twoją ochronę początkową. Potwierdź tylko, jeśli jesteś gotowy na PvP.")),"PvP warning before dispatch")
			for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520)]:
				window.size = dimensions; await settle(); geometry(ui)
			window.size = Vector2i(720,1280); await settle()
			if locale == "pl":
				await shot("alliance_dispatch_pl")
				ui.go_back(); await settle()
				expect(ui.form == "join" and int(ui.quantities["frigate"].value) == 2,"Back from preview preserves fleet selection")
				await press(I18n.t("Sprawdź trasę"))
			await press(I18n.t("Wyślij flotę"))
			expect(ui.operations["operations"][0].get("participants",[]).size() == 1,"Confirmed dispatch creates exactly one fleet")
			if locale == "pl": await shot("alliance_operations_pl")
			var op: Dictionary = ui.operations["operations"][0]
			ui._confirm(I18n.t("Anulować operację? Wysłane floty rozpoczną powrót."),{"action":"cancel","operation_id":op["id"]},true)
			await press(I18n.t("Potwierdź"))
		ui._defense_form(); await settle(); ui.quantities["cruiser"].value = 1
		await press(I18n.t("Sprawdź trasę"))
		expect(ui.form == "preview" and int(ui.form_context.get("preview",{}).get("hold_hours",0)) == 1,"Defense preview includes chosen holding period")
		ui.go_back()
		expect(ui.form == "defend" and int(ui.quantities["cruiser"].value) == 1,"Back from defense preview restores draft")
		ui.go_back()
		ui._select_tab(0); await settle()
		for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(1080,2520)]:
			window.size = dimensions; await settle(); geometry(ui)
		if locale == "pl": await shot("alliance_overview_pl")
		ui._join_form(operation)
		var saved_view: Dictionary = ui.data.duplicate(true)
		ui._adopt_membership({"alliance":null,"directory":[]})
		expect(ui.form.is_empty() and ui.operations.is_empty(),"Membership revocation invalidates operation form and cache")
		ui._adopt_membership(saved_view)
		ui.close(); await settle(); expect(not ui.visible,"Back closes overlay")
	print("Alliance UI checks: %d; failures: %d" % [checks,failures])
	get_tree().quit(1 if failures else 0)


func run_preview_resize() -> void:
	await fresh("pl", "leader")
	var ui = client.alliance_ui
	ui._select_tab(2); await wait_requests()
	ui._create_operation()
	var picker = ui.fields["target"]
	for index: int in range(picker.item_count):
		if str(picker.get_item_metadata(index)) == fixture["enemy"]: picker.select(index)
	ui.fields["delay"].select(8)
	await press(I18n.t("Utwórz operację"))
	ui._join_form(ui.operations["operations"][0]); await settle()
	ui.quantities["frigate"].value = 2
	await press(I18n.t("Sprawdź trasę"))
	expect(ui.form == "preview", "Preview is actually open")
	for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520),Vector2i(720,1280)]:
		get_tree().root.size = dimensions
		await settle()
		client._update_mobile_margins()
		await settle()
		var back: Button = find_button(ui, I18n.t("Wstecz"))
		expect(back != null and back.get_global_rect().position.y >= 0, "Back header remains within viewport after resize")
		expect(ui.margin.get_global_rect().position.y >= 0, "Margin remains in viewport")
		expect(ui.title.get_global_rect().position.y >= 0, "Alliance title remains in viewport")
		for button: Button in ui.tabs:
			expect(button.get_global_rect().position.y >= 0 and button.get_global_rect().end.y < ui.scroll.get_global_rect().position.y + 1,"Both tab rows remain above content")
		print("Preview resize ", dimensions, " margin=", ui.margin.get_global_rect(), " title=", ui.title.get_global_rect(), " back=", back.get_global_rect(), " first_tab=", ui.tabs[0].get_global_rect(), " second_row=", ui.tabs[2].get_global_rect(), " insets=", client.mobile_insets)
	await shot("alliance_preview_720x1280_final")
	print("Alliance preview resize checks: %d; failures: %d" % [checks, failures])
	get_tree().quit(1 if failures else 0)
