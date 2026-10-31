extends "res://tests/android_fleet87_regression.gd"


func payload(position: int = 57, many: bool = false) -> Dictionary:
	var items: Array = []
	var sample_rows: Array = [
		[1, "megobari", "automatons", 49],
		[2, "Wollle", "zetans", 25],
		[3, "Demo", "symbionts", 21],
		[4, "A very long empire name that must leave space for points and race", "automatons", 1234567890],
		[57, "My empire", "symbionts", 0]]
	if many:
		sample_rows.clear()
		var first: int = int((position - 1) / 50) * 50 + 1
		for index: int in range(first, first + 50):
			sample_rows.append([index, "Empire %d" % index, ["zetans", "automatons", "symbionts"][index % 3], 10000-index])
	for row: Array in sample_rows:
		items.append({"position":row[0], "player_id":"rank-%d" % row[0], "name":row[1], "race_id":row[2], "score":row[3], "is_self":row[0] == position})
	return {"ok":true, "schema":1, "page":int((position - 1) / 50) + 1, "pages":5, "players_total":223, "items":items,
		"self":{"player_id":"rank-%d" % position, "position":position, "score":0, "scores":{"total":0,"buildings":0,"research":0,"fleet":0,"defense":0}}}


func show_ranking(value: Dictionary, around: bool = false) -> void:
	var ui = client.ranking_ui
	ui.show()
	ui._received(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify(value).to_utf8_buffer(), ui.serial, client.session_token, client.server_url, around)
	await settle(10)


func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["en", "pl", "de", "es", "fr"]:
		for dimensions: Vector2i in [Vector2i(320,568), Vector2i(360,800), Vector2i(450,1000), Vector2i(900,600)]:
			window.size = dimensions
			new_client(locale)
			await settle(8)
			await show_ranking(payload())
			var ui = client.ranking_ui
			for row: Control in ui.rows.get_children():
				var race: Label = row.find_child("RankedRace", true, false)
				var score: Label = row.find_child("RankedScore", true, false)
				var player: Label = row.find_child("RankedPlayerName", true, false)
				var standing: VBoxContainer = row.find_child("RankedStanding", true, false)
				expect(race != null and score != null and standing != null, "Race and points share a right-side column")
				if race == null or score == null or standing == null:
					continue
				expect(race.get_global_rect().position.y >= score.get_global_rect().end.y, "Race is below points")
				expect(absf(race.get_global_rect().end.x-score.get_global_rect().end.x) <= 1.0, "Race aligns with the right edge of points")
				expect(race.horizontal_alignment == HORIZONTAL_ALIGNMENT_RIGHT and score.horizontal_alignment == HORIZONTAL_ALIGNMENT_RIGHT, "Both labels align their text right")
				expect(race.get_line_count() == 1 and score.get_line_count() == 1, "Race names and scores never wrap into vertical letters")
				expect(race.size.x + 1 >= race.get_minimum_size().x, "Entire race name fits its allocated width")
				expect(player.get_global_rect().end.x <= standing.get_global_rect().position.x + 1, "Empire name does not overlap the points column")
				expect(standing.get_global_rect().end.x <= ui.scroll.get_global_rect().end.x + 1, "Points and race stay within the visible scroll viewport")
				expect(row.size.y <= 130, "Ranking entry remains compact on " + locale + str(dimensions))
				var id: String = "automatons" if str(row.get_meta("player_id")) in ["rank-1", "rank-4"] else "zetans" if str(row.get_meta("player_id")) == "rank-2" else "symbionts"
				expect(race.text == I18n.t(ui.RACES[id][0]) and race.get_theme_color("font_color").is_equal_approx(Color(ui.RACES[id][1])), "Localized race retains exact faction color")
			ui.close()
			await settle(2)
	# My position must still use the new settled row heights and correct page.
	for position: int in [13, 57]:
		await show_ranking(payload(position, true), true)
		var ui = client.ranking_ui
		var own: Control = null
		for candidate: Control in ui.rows.get_children():
			if str(candidate.get_meta("player_id", "")) == "rank-%d" % position:
				own = candidate
		expect(own != null and ui.scroll.get_global_rect().intersects(own.get_global_rect()), "My position shows the correct compact row %d" % position)
		ui.close()
	var report := {"result":"PASS" if failed.is_empty() else "FAIL", "checks":checks, "failed":failed,
		"scope":"Actual ranking controller, all3 races,5 languages,4 window sizes, long empire names and large scores. No physical Android."}
	var file := FileAccess.open("user://ranking97_report.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("Ranking97: ",JSON.stringify(report))
	get_tree().quit(0 if failed.is_empty() else 1)
