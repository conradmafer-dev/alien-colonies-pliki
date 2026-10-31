extends "res://tests/android_fleet87_regression.gd"


func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	get_tree().root.size = Vector2i(720, 1280)
	for locale: String in ["en", "pl", "de", "es", "fr"]:
		new_client(locale)
		await settle()
		var target: Dictionary = Model.target(client.state, source_id)["planet"].duplicate(true)
		target["owner_name"] = "Dynastia xyarufida"
		var summary := VBoxContainer.new()
		client.add_child(summary)
		client.planetary_ui.galaxy_guidance.add_summary(summary, target)
		var owner: Label = summary.find_child("TargetOwnerSummary", true, false)
		var intel: Label = summary.find_child("TargetIntelSummary", true, false)
		expect(owner.text == I18n.t("Właściciel: %s") % I18n.t("● Twoja kolonia"), locale + " owner prefix and own-colony label")
		expect(intel.text == I18n.t("Dane własnej kolonii są aktualizowane na żywo."), locale + " live colony explanation")
		target["owner_id"] = "another-player"
		target["owner_type"] = "player"
		var foreign := VBoxContainer.new()
		client.add_child(foreign)
		client.planetary_ui.galaxy_guidance.add_summary(foreign, target)
		var foreign_owner: Label = foreign.find_child("TargetOwnerSummary", true, false)
		expect(foreign_owner.text == I18n.t("Właściciel: %s") % "Dynastia xyarufida", "Player-authored empire name preserved in " + locale)
		var system_actions := VBoxContainer.new()
		client.add_child(system_actions)
		client.planetary_ui.galaxy_guidance.add_system_action(system_actions, client.state["galaxy"][0])
		var survey: Button = system_actions.find_child("SurveyWholeSystem", true, false)
		expect(survey != null and survey.text == I18n.t("Zbadaj cały układ"), locale + " whole-system scouting button")
		var explanation: Label = system_actions.find_child("SystemSurveyExplanation", true, false)
		expect(explanation != null and explanation.text == I18n.t("Odśwież wolne planety i właścicieli w całym układzie. Szczegóły zasobów i obrony wymagają osobnego zwiadu planety."), locale + " system scouting explanation")
		if locale == "en":
			expect(owner.text == "Owner: ● Your colony", "Screenshot owner label is entirely English")
			expect(intel.text == "Your colony data is updated live.", "Screenshot live-colony note is English")
			expect(survey.text == "Survey the whole system", "Screenshot survey action is English")
			expect(client.planet_status.energy_summary.text.begins_with("Energy ") and client.planet_status.energy_summary.text.contains("Production "), "Screenshot energy and production summary is English")
			expect(I18n.t("Chroniona") == "Protected", "Screenshot protection badge is English")
			expect(I18n.t("Misja") == "Mission", "Mission label does not fall back to Polish")
	# Rebuilding after a saved language change must retain the client-only catalog.
	new_client("pl")
	await settle()
	new_client("en")
	await settle()
	expect(client.planet_status.energy_summary.text.begins_with("Energy "), "Polish-to-English language change refreshes live UI")
	var report := {"result":"PASS" if failed.is_empty() else "FAIL", "checks":checks, "failed":failed}
	var file := FileAccess.open("res://tests/localization95_report.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	file.close()
	print("Localization95: %d checks; %d failures" % [checks, failed.size()])
	get_tree().quit(0 if failed.is_empty() else 1)
