extends "res://tests/android_fleet87_regression.gd"

var fixture: Dictionary
var layout_samples: Array = []

func wait_ranking() -> void:
	for _frame: int in range(1800):
		if not client.ranking_ui.busy:
			return
		await get_tree().process_frame
	expect(false, "Ranking request completed within test timeout")

func capture(stage: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args():
		return
	await RenderingServer.frame_post_draw
	var image: Image = get_viewport().get_texture().get_image()
	image.save_png("res://tests/ranking92_%s.png" % stage)

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	fixture = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ranking92.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["pl", "en", "de", "es", "fr"]:
		for dimensions: Vector2i in [Vector2i(360,640),Vector2i(450,800),Vector2i(720,1600)]:
			window.size = dimensions
			new_client(locale)
			client._apply_state_now(fixture["state"].duplicate(true),Time.get_ticks_msec())
			client.session_token = str(fixture["token"])
			client.server_url = str(fixture["url"])
			client.planet_picker.text = "Very Long Colony Name For Header Fit"
			await settle(12)
			var header: HBoxContainer = client.planet_picker.get_parent()
			var header_rect: Rect2 = header.get_global_rect()
			var end: float = header_rect.position.x
			for control: Node in header.get_children():
				if control is Control and control.is_visible_in_tree():
					var rect: Rect2 = control.get_global_rect()
					expect(rect.position.x >= end - 1, locale + " header items do not overlap")
					expect(rect.end.x <= client.size.x + 1, locale + " header item stays within viewport")
					end = rect.end.x
			var entry: Button = client.ranking_ui.entry
			expect(entry.is_visible_in_tree(), locale + " trophy visible in actual main header")
			expect(entry.size.x >= 64 and entry.size.y >= 64, "Trophy retains settings-sized touch target")
			if locale == "pl" and dimensions == Vector2i(450,800): await capture("header_pl")
			entry.pressed.emit()
			await wait_ranking()
			await settle(8)
			var ui = client.ranking_ui
			expect(ui.visible and not client.app_screen.visible, "Trophy opens dedicated ranking screen")
			expect(ui.snapshot.get("players_total",0) == 62, "Actual authenticated HTTP returns every empire")
			expect(ui.rows.get_child_count() == 50, "Rankings are paged at 50 players")
			expect(str(ui.own_title.text).contains("#62"), "Own position pinned even on another page")
			expect(ui.scroll.size.y > 180, locale + " ranking leaves usable list area")
			expect(ui.margin.get_global_rect().end.x <= client.size.x + 1, locale + " ranking fits screen width")
			layout_samples.append({"locale":locale,"window":[dimensions.x,dimensions.y],"header_width":header_rect.size.x,"trophy_rect":[entry.position.x,entry.size.x,entry.size.y],"ranking_list_height":ui.scroll.size.y})
			if locale == "pl" and dimensions == Vector2i(450,800): await capture("list_pl")
			ui.mine.pressed.emit()
			await wait_ranking()
			await settle(10)
			expect(ui.page == 2, "My position fetches the correct server page")
			var self_rows: int = 0
			for row: Node in ui.rows.get_children():
				if bool(row.get_meta("is_self",false)):
					self_rows += 1
					expect(row.has_theme_stylebox_override("panel"), "Own row highlighted")
			expect(self_rows == 1, "Exactly one own row on own page")
			if locale == "en" and dimensions == Vector2i(450,800): await capture("own_en")
			ui.category.select(3)
			ui.category.item_selected.emit(3)
			await wait_ranking()
			expect(ui.snapshot.get("category","") == "fleet", "Category calls the matching server valuation")
			ui.close()
			await settle()
			expect(client.app_screen.visible, "Back restores the same game view")
			expect(client.session_token == fixture["token"], "Ranking does not alter session")
	# A delayed response from the previous account must never repaint new state.
	var ui = client.ranking_ui
	ui.open()
	ui._cancel()
	ui.snapshot.clear()
	var generation: int = ui.serial
	client.session_token = "different-test-session"
	ui._received(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"ok":true,"schema":1,"items":[]}).to_utf8_buffer(),generation,str(fixture["token"]),str(fixture["url"]),false)
	expect(ui.snapshot.is_empty(), "Previous-account response is ignored")
	ui.reset()
	expect(not ui.visible and ui.rows.get_child_count() == 0, "Logout reset clears ranking content")
	var report := {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,"layouts":layout_samples,"scope":"Actual native scene and authenticated local HTTP, 62 synthetic empires; no physical Android"}
	var file := FileAccess.open("res://tests/ranking92_report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("Ranking92: %d checks, %d failures" % [checks,failed.size()])
	get_tree().quit(0 if failed.is_empty() else 1)
