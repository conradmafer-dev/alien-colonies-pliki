extends "res://tests/android_fleet87_regression.gd"

class LocalPrompt:
	extends "res://client/scripts/review_prompt.gd"
	func _rate() -> void:
		_send_choice("open_store")

var expected_back: bool = true


func click_at(point: Vector2) -> void:
	for pressed: bool in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		event.position = get_tree().root.get_final_transform() * point
		event.global_position = event.position
		Input.parse_input_event(event)
		await settle(2)


func click_popup(button: Button, _popup: Control) -> void:
	await click_at(button.get_global_rect().get_center())


func reset_prompt() -> void:
	client.request_pending = false
	client.uncertain_action.clear()
	client.captured.clear()
	client.review_prompt.last_session_dismissed = false
	expected_back = get_tree().quit_on_go_back
	client.state["review_prompt"] = {"eligible": true}
	client.review_prompt.refresh(client.state)
	await settle(8)


func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	var window: Window = get_tree().root
	window.gui_embed_subwindows = true
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	for locale: String in ["en", "pl", "de", "es", "fr"]:
		for dimensions: Vector2i in [Vector2i(360,640), Vector2i(450,800), Vector2i(900,600)]:
			window.size = dimensions
			new_client(locale)
			client.review_prompt.hide()
			client.review_prompt.layer.queue_free()
			client.review_prompt = LocalPrompt.new()
			client.review_prompt.setup(client)
			await reset_prompt()
			var prompt = client.review_prompt
			expect(prompt.is_visible() and prompt.layer.layer >= 200 and prompt.overlay.mouse_filter == Control.MOUSE_FILTER_STOP, "Review invitation owns the top input barrier")
			expect(prompt.card.get_theme_stylebox("panel").bg_color.a == 1.0, "Review card is fully opaque")
			var stars: Control = prompt.card.find_child("ReviewFiveStars", true, false)
			expect(stars != null and stars.get_meta("star_count") == 5, "Five real five-point stars, independent of font glyphs")
			expect(prompt.backdrop.visible and prompt.overlay.mouse_filter == Control.MOUSE_FILTER_STOP, "Outside modal surface blocks game input")
			expect(not get_tree().quit_on_go_back, "Android Back does not quit while invitation is open")
			expect(prompt.card.get_global_rect().position.x >= 0 and prompt.card.get_global_rect().position.y >= 0 and prompt.card.get_global_rect().end.x <= client.size.x + 1 and prompt.card.get_global_rect().end.y <= client.size.y + 1, "Scaled modal fits physical screen bounds")
			await click_at(Vector2(10,10))
			expect(prompt.is_visible() and client.captured.is_empty(), "Tap outside invitation does not click through or dismiss it")
			for pair: Array in [[prompt.later_button,"later"],[prompt.dismiss_button,"dismiss"],[prompt.rate_button,"open_store"]]:
				await click_popup(pair[0], prompt.overlay)
				expect(not prompt.is_visible(), locale + " actual button closes popup at " + str(dimensions))
				expect(client.captured.size() == 1 and client.captured[0]["payload"].get("type") == "review_prompt" and client.captured[0]["payload"].get("choice") == pair[1], "Exactly the selected review choice is sent; no background order")
				expect(not prompt.backdrop.visible and get_tree().quit_on_go_back == expected_back, "Dismissal restores game input and original Back behavior")
				await reset_prompt()
			var before: int = client.captured.size()
			client._notification(NOTIFICATION_WM_GO_BACK_REQUEST)
			expect(not prompt.is_visible() and client.captured.size() == before + 1 and client.captured[-1]["payload"].get("choice") == "later", "Native Android Back dismisses invitation once")
			await reset_prompt()
			client.review_prompt.refresh({"player":{"id": "another-account"},"review_prompt":{"eligible":false}})
			expect(not prompt.is_visible() and not prompt.last_session_dismissed, "Another account gets its own server eligibility")
	var report := {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,"scope":"Actual native controller and modal input barrier, injected pointer input, 5 languages and 3 screen sizes; no physical Android"}
	var file := FileAccess.open("res://tests/review94_report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("Review94: %d checks; %d failures" % [checks, failed.size()])
	get_tree().quit(0 if failed.is_empty() else 1)
