extends "res://tests/ranking98.gd"


func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720, 1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["en", "pl", "de", "es", "fr"]:
		for dimensions: Vector2i in [Vector2i(320,568), Vector2i(390,844), Vector2i(900,600)]:
			window.size = dimensions
			new_client(locale)
			await settle(8)
			client.state.erase("ranking_reward")
			for position: int in [1,11,31]:
				var days: int = 3 if position == 1 else 14 if position == 11 else 0
				var value: Dictionary = payload(position)
				value["reward"] = {"schema":1,"category":"total","position":position,"active":days>0,"days_per_crystal":days,"interval_seconds":days*86400,
					"progress":0.6,"remaining_seconds":days*86400*0.4 if days>0 else null,"as_of":client._server_now()}
				await show_ranking(value)
				var ui = client.ranking_ui
				var tag: String = locale + str(dimensions) + " #" + str(position)
				expect(ui.reward_panel.visible, "Reward panel visible: " + tag)
				expect(ui.reward_panel.size.y <= 88.0, "Reward fits two compact lines: " + tag)
				expect(ui.reward_caption.get_line_count() == 1 and ui.reward_status.get_line_count() == 1, "Both reward lines remain single lines: " + tag)
				var right: float = get_viewport().get_visible_rect().end.x - 20
				expect(ui.reward_panel.get_global_rect().end.x <= right, "Reward card fits screen width: " + tag)
				var font: Font = ui.reward_caption.get_theme_font("font")
				var width: float = font.get_string_size(ui.reward_caption.text,HORIZONTAL_ALIGNMENT_LEFT,-1,ui.reward_caption.get_theme_font_size("font_size")).x
				expect(width <= ui.reward_caption.size.x + 1, "Full reward caption fits without clipping: " + tag)
				var crystal: TextureRect = ui.find_child("RankingRewardCrystal",true,false)
				expect(crystal != null and crystal.texture != null and crystal.visible, "Existing Swarm Crystal artwork is visible: " + tag)
				expect(ui.reward_progress.value >= 0.6 and ui.reward_progress.value < 0.601, "Correct fractional progress: " + tag)
				expect(ui.reward_status.text.begins_with("60%"), "Percentage is visible: " + tag)
				expect(ui.scroll.size.y > 180.0, "Player list retains useful scrolling space: " + tag)
				expect(ui.rows.get_child(0).get_global_rect().intersects(ui.scroll.get_global_rect()), "First player remains visible: " + tag)
				if days == 0:
					expect(ui.reward_status.text.contains(I18n.t("Naliczanie wstrzymane")), "Paused state is translated: " + tag)
				else:
					expect(ui.reward_caption.text == I18n.t("Premia · #%s · 1 / %s d") % [str(position),str(days)], "Rate and overall position are correct: " + tag)
				ui.close()
			await show_ranking(payload(11))
			var ui = client.ranking_ui
			ui._show_reward_rules()
			await settle(3)
			expect(ui.reward_rules.visible and ui.reward_rules.dialog_text.contains("11–30") and ui.reward_rules.dialog_text.contains("14"), "Rules include the fourth tier in " + locale)
			ui.reward_rules.hide()
			ui.close()
	var report: Dictionary = {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,"scope":"Real native ranking reward UI, all five languages, 320x568/390x844/900x600, active and paused brackets, crystal art and rules."}
	print("RankingReward104: ",JSON.stringify(report))
	var output := FileAccess.open("user://ranking_reward104_report.json",FileAccess.WRITE)
	output.store_string(JSON.stringify(report,"  "))
	output.close()
	get_tree().quit(0 if failed.is_empty() else 1)
