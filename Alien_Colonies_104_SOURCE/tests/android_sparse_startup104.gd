extends SceneTree
## Run against the extracted Android assets and their actual assets.sparsepck:
## godot --headless --path ASSETS --main-pack ASSETS/assets.sparsepck --script /absolute/path/to/this.gd
var checks: int = 0
var failed: Array[String] = []


func expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failed.append(message)
		push_error(message)


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var i18n: Node = root.get_node("I18n")
	i18n.set_locale("en", false)
	expect(i18n.t("Właściciel: %s") == "Owner: %s", "Full English dictionary loads through Android index")
	expect(i18n.t("Zbadaj cały układ") == "Survey the whole system", "Restored Android-only translation is complete")
	expect(i18n.t("Chroniona") == "Protected", "Protection badge retains English translation")
	var scene: PackedScene = load("res://client/scenes/boot.tscn")
	expect(scene != null, "Android boot scene resolves its remap")
	if scene == null:
		quit(1)
		return
	var boot: Control = scene.instantiate()
	root.add_child(boot)
	current_scene = boot
	expect(boot.status != null and not boot.status.text.is_empty(), "Update checking label is created before network work")
	expect(not boot.meter.visible and not boot.bytes.visible, "Checking screen shows branding and status without a 0% progress bar")
	expect(boot.checking and boot.checking_tween != null and boot.checking_tween.is_running(), "Checking status has a live gentle pulse")
	expect(boot.CHECK_BUDGET_MS == 3000, "Availability check remains bounded to 3 seconds")
	var started: int = Time.get_ticks_msec()
	while current_scene == boot and Time.get_ticks_msec() - started < 8000:
		await process_frame
	expect(current_scene != null and current_scene != boot, "Actual Android boot reaches the main login scene")
	if current_scene == null or current_scene == boot:
		quit(1)
		return
	var main: Control = current_scene
	expect(main.get_script().get_script_constant_map().get("CLIENT_VERSION_CODE") == 104, "Compiled binary controller is version 104")
	expect(main.get_script().get_script_constant_map().get("CLIENT_VERSION_NAME") == "0.12.37", "Compiled controller version name matches the Android manifest")
	expect(main.login_screen.visible, "Fresh installation reaches a visible login screen")
	var prompt = main.review_prompt
	expect(prompt != null and prompt.layer.layer >= 200, "Corrected review modal loads from the real Android pack")
	expect(prompt.card.get_theme_stylebox("panel").bg_color.a == 1.0, "Review modal remains opaque")
	var stars: Control = prompt.card.find_child("ReviewFiveStars", true, false)
	expect(stars != null and stars.get_meta("star_count") == 5, "Five-star modal bytecode is complete")
	var report := {"result":"PASS" if failed.is_empty() else "FAIL", "checks":checks, "failed":failed,
		"boot_to_login_ms":Time.get_ticks_msec() - started,
		"scope":"Actual Android AAB assets and sparse index under Godot 4.5.1; headless desktop, no physical Android or Play Store installation"}
	var file := FileAccess.open("user://android_sparse_startup104_report.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	file.close()
	print("Android sparse startup104: ", JSON.stringify(report))
	quit(0 if failed.is_empty() else 1)
