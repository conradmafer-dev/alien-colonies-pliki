extends SceneTree

const Download = preload("res://client/scripts/apk_download.gd")
const Policy = preload("res://client/scripts/update_policy.gd")
const ORIGIN: String = "https://game.pogranicze.net"
const LINK: String = "https://github.com/studio/game/releases/download/v0.1.6/game.apk"
var failures: int = 0
var checks: int = 0


func _initialize() -> void:
	# No network or installer is used. This only exercises the downloader state,
	# redirect policy and file integrity with a synthetic ZIP, not a signed APK.
	call_deferred("_run")


func _run() -> void:
	_expect(Download.redirect_target(LINK, "https://release-assets.githubusercontent.com/file.apk?token=abc") == "https://release-assets.githubusercontent.com/file.apk?token=abc", "GitHub's HTTPS asset redirect is accepted")
	_expect(Download.redirect_target(LINK, "/new.apk") == "https://github.com/new.apk", "Root-relative redirect stays on origin")
	_expect(Download.redirect_target(LINK, "?download=1") == LINK + "?download=1", "Query redirect preserves the APK path")
	_expect(Download.redirect_target(LINK, "//cdn.pogranicze.net/game.apk") == "https://cdn.pogranicze.net/game.apk", "Scheme-relative CDN redirect retains HTTPS")
	for unsafe: String in ["http://cdn.pogranicze.net/a.apk", "https://127.0.0.1/a.apk", "//localhost/a.apk", "https://user:secret@cdn.pogranicze.net/a.apk", "../a.apk", "a.apk", "javascript:alert(1)", "/%5csecret", "https://cdn.pogranicze.net/a.apk#fragment"]:
		_expect(Download.redirect_target(LINK, unsafe).is_empty(), "Reject unsupported or unsafe redirect")
	for bad_size: Variant in [0, -1, "1", true, 1.5, Policy.MAX_APK_BYTES + 1, INF]:
		_expect(Policy.valid_apk_size(bad_size) == 0, "Reject invalid download size")
	_expect(Policy.valid_apk_size(Policy.MAX_APK_BYTES) == Policy.MAX_APK_BYTES, "Accept maximum bounded download size")
	_expect(Policy.valid_apk_sha256("A".repeat(64)) == "a".repeat(64), "Normalize valid SHA256")
	for bad_hash: Variant in [null, 1, "a".repeat(63), "g".repeat(64), "a".repeat(65)]:
		_expect(Policy.valid_apk_sha256(bad_hash).is_empty(), "Reject invalid SHA256")
	var downloader: Download = Download.new()
	root.add_child(downloader)
	var dir_error: Error = DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(Download.UPDATE_DIR))
	_expect(dir_error == OK, "Create private test download directory")
	var manifest: Dictionary = _write_fixture(true)
	var identity: String = Download.fingerprint(ORIGIN, manifest)
	_expect(not identity.is_empty(), "Complete metadata defines a release identity")
	_expect(identity != Download.fingerprint("https://other.pogranicze.net", manifest), "Identity binds the game server")
	var alternate: Dictionary = manifest.duplicate(true)
	alternate["latest_version_code"] = 8
	_expect(identity != Download.fingerprint(ORIGIN, alternate), "Identity binds the APK version")
	alternate = manifest.duplicate(true)
	alternate["apk_sha256"] = "b".repeat(64)
	_expect(identity != Download.fingerprint(ORIGIN, alternate), "Identity binds the file digest")
	_prepare_response(downloader, manifest)
	downloader._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), PackedByteArray(), 41)
	_expect(downloader.phase == "downloading", "Old HTTP callback cannot change the active request")
	downloader._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), PackedByteArray(), 42)
	_expect(downloader.phase == "verifying", "Completed download enters verification before install is enabled")
	downloader._hash_next_chunks()
	_expect(downloader.phase == "ready", "Exact size, digest and manifest make the synthetic ZIP ready")
	_expect(downloader.ready_path(ORIGIN, manifest) == Download.APK_PATH, "Ready file is available only for its bound release")
	downloader.reconcile(ORIGIN, manifest.duplicate(true))
	_expect(downloader.phase == "ready" and FileAccess.file_exists(Download.APK_PATH), "Repeated identical manifest preserves verified file")
	_expect(downloader.ready_path("https://other.pogranicze.net", manifest).is_empty(), "Cannot install for another game server")
	downloader.reconcile(ORIGIN, alternate)
	_expect(downloader.phase == "idle" and not FileAccess.file_exists(Download.APK_PATH), "Changed release invalidates verified file")
	manifest = _write_fixture(true)
	manifest["apk_sha256"] = "0".repeat(64)
	_prepare_response(downloader, manifest)
	downloader._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), PackedByteArray(), 42)
	downloader._hash_next_chunks()
	_expect(downloader.phase == "error" and not FileAccess.file_exists(Download.PART_PATH), "Digest mismatch deletes the partial file and cannot be installed")
	manifest = _write_fixture(true)
	manifest["apk_size_bytes"] = int(manifest["apk_size_bytes"]) + 1
	_prepare_response(downloader, manifest)
	downloader._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), PackedByteArray(), 42)
	_expect(downloader.phase == "error" and not FileAccess.file_exists(Download.APK_PATH), "Truncated response cannot become installable")
	manifest = _write_fixture(false)
	_prepare_response(downloader, manifest)
	downloader._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), PackedByteArray(), 42)
	downloader._hash_next_chunks()
	_expect(downloader.phase == "error", "A ZIP without AndroidManifest.xml is rejected")
	manifest = _write_fixture(true)
	_prepare_response(downloader, manifest)
	downloader.cancel()
	_expect(downloader.phase == "idle" and not FileAccess.file_exists(Download.PART_PATH), "Cancellation removes incomplete data")
	downloader._on_response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), PackedByteArray(), 42)
	_expect(downloader.phase == "idle", "Late completion after cancel is ignored")
	downloader.free()
	print("APK download: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)


func _write_fixture(has_manifest: bool) -> Dictionary:
	var archive: ZIPPacker = ZIPPacker.new()
	var opened: Error = archive.open(Download.PART_PATH)
	_expect(opened == OK, "Open synthetic test ZIP")
	if opened == OK:
		archive.start_file("AndroidManifest.xml" if has_manifest else "website.html")
		archive.write_file("synthetic fixture, not an installable APK".to_utf8_buffer())
		archive.close_file()
		archive.close()
	var file: FileAccess = FileAccess.open(Download.PART_PATH, FileAccess.READ)
	var size: int = file.get_length() if file != null else 0
	if file != null:
		file.close()
	return {"latest_version_code": 7, "download_url": LINK, "apk_sha256": FileAccess.get_sha256(Download.PART_PATH), "apk_size_bytes": size}


func _prepare_response(downloader: Download, manifest: Dictionary) -> void:
	downloader._generation = 42
	downloader._release = manifest.duplicate(true)
	downloader.snapshot = Download.fingerprint(ORIGIN, manifest)
	downloader.expected_bytes = int(manifest["apk_size_bytes"])
	downloader.phase = "downloading"


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
