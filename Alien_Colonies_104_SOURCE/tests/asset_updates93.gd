extends Node
var checks: int = 0
var failed: Array = []
var fixture: Dictionary
var updater


func expect(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failed.append(text)
		push_error(text)


func manifest(packs: Array) -> Dictionary:
	return {"schema": 1, "min_client": 93, "max_client": 93, "packs": packs}


func write_manifest(value: Dictionary) -> void:
	var file := FileAccess.open(fixture["manifest"], FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()


func requests(path: String) -> int:
	var counts: Variant = JSON.parse_string(FileAccess.get_file_as_string(fixture["counts"]))
	return int(counts.get(path, 0)) if counts is Dictionary else 0


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	fixture = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("AC93_ASSET_FIXTURE")))
	updater = preload("res://client/scripts/asset_updates.gd").new()
	add_child(updater)
	var valid: Dictionary = fixture["packs"]["valid"]
	write_manifest(manifest([valid]))
	var result: Dictionary = await updater.run(fixture["origin"])
	expect(result.get("ok", false), "Downloads and verifies real texture ZIP over HTTP")
	expect(updater.total_bytes == valid["size"] and updater.completed_bytes == valid["size"], "Progress reports actual required byte count")
	var path: String = updater._pack_path(valid)
	expect(updater._verify_pack(path, valid), "Cached pack and every member match SHA-256")
	var first_requests: int = requests("/play/content/valid.zip")
	result = await updater.run(fixture["origin"])
	expect(result.get("ok", false) and updater.total_bytes == 0 and requests("/play/content/valid.zip") == first_requests, "Unchanged pack reused without a download")
	var corrupt := FileAccess.open(path, FileAccess.WRITE)
	corrupt.store_string("corrupt cache")
	corrupt.close()
	result = await updater.run(fixture["origin"])
	expect(result.get("ok", false) and requests("/play/content/valid.zip") == first_requests + 1, "Corrupt cache is downloaded and verified again")
	var saved: String = FileAccess.get_file_as_string(updater.cache + "active.json")
	write_manifest(manifest([valid, fixture["packs"]["extra"]]))
	result = await updater.run(fixture["origin"])
	expect(not result.get("ok", true), "Code smuggled as an extra ZIP member is rejected")
	expect(FileAccess.get_file_as_string(updater.cache + "active.json") == saved and updater.active.get("packs", []).size() == 1, "Failed new release preserves previous complete release")
	expect(not FileAccess.file_exists(updater._pack_path(fixture["packs"]["extra"]) + ".part"), "Incomplete/invalid downloads are removed")
	for unsafe: String in ["client/scripts/unsafe.gd", "../unsafe.png", "client/assets/../../unsafe.png", "/client/assets/unsafe.png", "client/assets/unsafe.svg"]:
		var bad: Dictionary = valid.duplicate(true)
		bad["files"][0]["path"] = unsafe
		expect(not updater._valid_manifest(manifest([bad]), 93), "Rejects non-texture or unsafe member " + unsafe)
	var oversized: Dictionary = valid.duplicate(true)
	oversized["size"] = updater.MAX_PACK_BYTES + 1
	expect(not updater._valid_manifest(manifest([oversized]), 93), "Oversized archive rejected before download")
	var external: Dictionary = valid.duplicate(true)
	external["url"] = "https://other.invalid/play/content/valid.zip"
	expect(not updater._valid_manifest(manifest([external]), 93), "Pack delivery restricted to selected server origin")
	write_manifest(manifest([valid]))
	result = await updater.run(fixture["origin"])
	expect(result.get("ok", false) and updater.total_bytes == 0, "Retry reuses the already verified pack")
	expect(updater.mount_active(), "Mounts only a fully verified texture release")
	var texture: Resource = ResourceLoader.load("res://client/assets/alien_colonies_icon.png", "Texture2D", ResourceLoader.CACHE_MODE_REPLACE)
	expect(texture is Texture2D and texture.get_width() > 0, "Mounted imported texture loads in the actual resource loader")
	var cache93: String = updater.cache
	result = await updater.run(fixture["origin"], 94)
	expect(not result.get("ok", true) and updater.cache != cache93, "Cached patches are isolated by binary version")
	var report := {"result": "PASS" if failed.is_empty() else "FAIL", "checks": checks, "failed": failed}
	var output := FileAccess.open("res://tests/asset_updates93_report.json", FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  "))
	output.close()
	print("AssetUpdates93: %d checks; %d failures" % [checks, failed.size()])
	get_tree().quit(0 if failed.is_empty() else 1)
