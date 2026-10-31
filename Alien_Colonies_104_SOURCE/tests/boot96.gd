extends Node

class TestBoot:
	extends "res://client/scripts/update_boot.gd"
	var test_origin: String
	var mounted: bool = false
	func _server_origin() -> String:
		return test_origin
	func _enter_game() -> void:
		if not entered:
			mounted = assets.mount_active()
			entered = true

class ManualBoot:
	extends TestBoot
	func _check_content() -> void:
		pass

var checks: int = 0
var failed: Array[String] = []
var timings: Dictionary = {}
var fixture: Dictionary
var boot: TestBoot


func expect(value: bool, message: String) -> void:
	checks += 1
	if not value:
		failed.append(message)
		push_error(message)


func _ready() -> void:
	_run.call_deferred()


func create_boot(mode: String, phase: String, manual: bool = false) -> void:
	if is_instance_valid(boot):
		remove_child(boot)
		boot.queue_free()
	var control := FileAccess.open(fixture["mode"], FileAccess.WRITE)
	control.store_string(mode)
	control.close()
	PlayUpdates.status = {"state":phase,"downloaded":25,"total":100}
	boot = ManualBoot.new() if manual else TestBoot.new()
	boot.test_origin = fixture["origin"]
	add_child(boot)
	await get_tree().process_frame


func wait_for_entry(limit_ms: int = 3600) -> int:
	var start: int = Time.get_ticks_msec()
	while not boot.entered and Time.get_ticks_msec() - start < limit_ms:
		await get_tree().process_frame
	return Time.get_ticks_msec() - boot.started_at


func _run() -> void:
	fixture = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("AC95_BOOT_FIXTURE")))
	await create_boot("empty", "unavailable")
	expect(not boot.meter.visible and not boot.bytes.visible, "Initial availability check has no 0% indicator")
	timings["no_update_ms"] = await wait_for_entry()
	expect(boot.entered and timings["no_update_ms"] < 900, "No-update response enters immediately, without 1.2s minimum")
	expect(boot.mounted and not boot.content_failed, "No-update boot uses complete local content")
	await create_boot("invalid", "unsupported")
	timings["check_error_ms"] = await wait_for_entry()
	expect(boot.entered and timings["check_error_ms"] < 900 and not boot.content_failed, "Unavailable optional manifest never blocks login with an error screen")
	await create_boot("slow", "unavailable")
	timings["stalled_manifest_ms"] = await wait_for_entry()
	expect(boot.entered and timings["stalled_manifest_ms"] >= 2900 and timings["stalled_manifest_ms"] < 3400, "Stalled HTTP check releases boot within the 3s budget")
	expect(boot.assets.active.get("packs", [1]).is_empty() and boot.mounted, "Slow check retains previous complete active manifest")
	await create_boot("empty", "checking", true)
	boot.content_ready = true
	timings["stalled_play_ms"] = await wait_for_entry()
	expect(boot.entered and timings["stalled_play_ms"] < 3400, "Stalled Play availability query has the same bounded wait")
	await create_boot("empty", "checking", true)
	boot.content_ready = true
	boot._render()
	expect(not boot.entered and not boot.primary.visible and boot.status.text == I18n.t("Sprawdzanie aktualizacji…"), "Checking state does not falsely claim an available update")
	expect(not boot.meter.visible and not boot.bytes.visible, "Pending Play check shows only branding and localized status")
	expect(boot.checking and boot.checking_tween != null and boot.checking_tween.is_running(), "Checking label has an active pulse")
	var same_tween: Tween = boot.checking_tween
	await get_tree().create_timer(0.45).timeout
	expect(boot.status.modulate.a >= 0.64 and boot.status.modulate.a < 0.99, "Checking text gently changes opacity while staying readable")
	boot._render()
	expect(boot.checking_tween == same_tween, "Repeated status rendering does not restart the pulse")
	boot._progress(25, 100, I18n.t("Pobieranie aktualizacji…"))
	expect(not boot.checking and boot.checking_tween == null and is_equal_approx(boot.status.modulate.a, 1.0) and boot.meter.visible, "Real download stops pulsing and shows progress")
	PlayUpdates.status["state"] = "unavailable"
	PlayUpdates.changed.emit()
	expect(boot.entered, "Native no-update signal ends waiting immediately")
	for phase: String in ["available", "pending", "downloading", "downloaded", "consent", "installing"]:
		await create_boot("empty", phase, true)
		boot.content_ready = true
		boot.started_at -= 4000
		boot._render()
		expect(not boot.entered and boot.primary.visible, "Real update state remains actionable beyond availability budget: " + phase)
		expect(boot.secondary.visible == (phase not in ["consent", "installing"]), "Only permitted update stages allow Later: " + phase)
	await create_boot("download", "unavailable")
	await get_tree().create_timer(3.15).timeout
	expect(boot.meter.visible and boot.bytes.visible and not boot.bytes.text.is_empty(), "Real texture download shows measurable progress and bytes")
	expect(not boot.entered and boot.assets.downloading, "Actual texture download is not cut off by availability deadline")
	timings["slow_download_ms"] = await wait_for_entry(3000)
	expect(boot.entered and boot.mounted and boot.assets.completed_bytes > 0, "Download completes and all texture hashes verify before entry")
	remove_child(boot)
	boot.queue_free()
	await get_tree().process_frame
	var report := {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,"timings":timings,"scope":"Real local HTTP with delayed responses; native Play states simulated; no physical Android"}
	var file := FileAccess.open("res://tests/boot96_report.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("Boot96: %d checks; %d failures; %s" % [checks,failed.size(),timings])
	get_tree().quit(0 if failed.is_empty() else 1)
