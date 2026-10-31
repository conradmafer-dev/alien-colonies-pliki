extends "res://tests/android_fleet87_regression.gd"
var measurements: Array = []


func ranking_payload(position: int, page: int = 1) -> Dictionary:
	var items: Array = []
	for index: int in range((page - 1) * 50 + 1, mini(151, page * 50 + 1)):
		items.append({"position": index, "player_id": "rank-%d" % index, "name": "Empire %d" % index,
			"score": 30000 - index, "race_id": ["zetans", "automatons", "symbionts"][index % 3], "is_self": index == position})
	return {"ok": true, "schema": 1, "page": page, "pages": 3, "players_total": 150, "items": items,
		"self": {"player_id": "rank-%d" % position, "position": position, "score": 30000-position,
			"scores": {"total": 30000-position, "buildings": 1, "research": 1, "fleet": 1, "defense": 1}}}


func accept_ranking(payload: Dictionary, own: bool = true) -> void:
	var ui = client.ranking_ui
	ui.show()
	ui._received(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify(payload).to_utf8_buffer(),
		ui.serial, client.session_token, client.server_url, own)
	await settle(8)


func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["en", "pl", "de", "es", "fr"]:
		for dimensions: Vector2i in [Vector2i(360,640), Vector2i(450,800), Vector2i(900,600)]:
			window.size = dimensions
			new_client(locale)
			client._apply_state_now(sample(locale), Time.get_ticks_msec())
			client.session_token = "offline-rank-test"
			await settle(12)
			var ui = client.ranking_ui
			for position: int in [1, 13, 30, 50, 51, 113]:
				var page: int = int((position - 1) / 50) + 1
				await accept_ranking(ranking_payload(position, page))
				var own_row: Control
				for candidate: Control in ui.rows.get_children():
					if str(candidate.get_meta("player_id", "")) == "rank-%d" % position:
						own_row = candidate
				expect(own_row != null, "Own row returned in ranking response")
				if own_row == null:
					print("MISSING_OWN_ROW ", ui.rows.get_child_count(), " ", ui.snapshot, " ", ui.visible)
					get_tree().quit(1)
					return
				expect(ui.scroll.get_global_rect().intersects(own_row.get_global_rect()), "My position shows row %d at %s/%s" % [position, locale, dimensions])
				var target: float = clampf(own_row.position.y + own_row.size.y * 0.5 - ui.scroll.size.y * 0.5, 0, ui.scroll.get_v_scroll_bar().max_value - ui.scroll.get_v_scroll_bar().page)
				expect(absf(ui.scroll.scroll_vertical - target) <= 2.0, "My position uses settled content coordinates")
				ui._scroll_to_own(true, ui.serial)
				await settle(5)
				expect(absf(ui.scroll.scroll_vertical - target) <= 2.0, "Repeated jump does not apply previous scroll twice")
				var race: Label = own_row.find_child("RankedRace", true, false)
				var id: String = ["zetans", "automatons", "symbionts"][position % 3]
				expect(race != null and race.text == I18n.t(ui.RACES[id][0]), "Localized race beside empire name")
				expect(race.get_theme_color("font_color").is_equal_approx(Color(ui.RACES[id][1])), "Faction color remains exact")
			ui.close()
			await settle(15)
			expect(client.options_panel.find_child("RenameEmpireButton", true, false) != null, "Rename available in actual settings")
	# Stale layout callback must not move a new category/page.
	var ui = client.ranking_ui
	await accept_ranking(ranking_payload(13))
	ui._scroll_to_own(true, ui.serial)
	ui.serial += 1
	ui.scroll.scroll_vertical = 0
	await settle(6)
	expect(ui.scroll.scroll_vertical == 0, "Cancelled layout callback ignored")
	ui.close()
	# Native scrollbar motion after UP keeps server state pending until settled.
	client.interaction_guard.reset()
	var next: Dictionary = client.state.duplicate(true)
	next["player"]["name"] = "After inertia"
	client.interaction_guard.scroll_motion()
	client._apply_state(next)
	expect(client.state["player"]["name"] != "After inertia" and not client.deferred_state.is_empty(), "Snapshot deferred while inertia moves")
	await get_tree().create_timer(0.21).timeout
	await settle(10)
	expect(client.state["player"]["name"] == "After inertia", "Latest snapshot applied after scrolling settles")
	# A cached unchanged definition must still refresh affordability and queues.
	client._apply_state_now(sample("en"), Time.get_ticks_msec())
	await settle(10)
	var entries: Array = client.state["catalog"]["buildings"]
	var key: String = str(entries[0]["key"])
	var card: Control = client.building_rows[key]["panel"]
	client.state["resources"] = {"metal": 0, "crystal": 0, "fuel": 0}
	client._refresh_catalog(entries, client.building_list, client.building_rows, "build")
	expect(client.building_rows[key]["panel"] == card, "Catalog cache retains controls and scroll position")
	for resource: String in client.RESOURCE_KEYS:
		if float(entries[0].get("cost", {}).get(resource, 0)) > 0:
			expect(client.building_rows[key]["costs"][resource]["amount"].get_theme_color("font_color").is_equal_approx(client._ui_color(Color("ff9287"))), "Affordability invalidates cached costs")
	for index: int in range(30):
		var now: int = Time.get_ticks_usec()
		client._apply_state_now(client.state.duplicate(true), Time.get_ticks_msec())
		measurements.append((Time.get_ticks_usec() - now) / 1000.0)
		await settle(2)
	var report := {"result": "PASS" if failed.is_empty() else "FAIL", "checks": checks, "failed": failed,
		"refresh_ms": measurements, "scope": "Headless Godot actual controller, 5 languages and 3 viewport sizes; no physical Android"}
	var out := FileAccess.open("res://tests/release93_report.json", FileAccess.WRITE)
	out.store_string(JSON.stringify(report, "  "))
	out.close()
	print("Release93: %d checks; %d failures" % [checks, failed.size()])
	get_tree().quit(0 if failed.is_empty() else 1)
