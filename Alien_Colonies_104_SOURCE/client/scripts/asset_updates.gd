extends Node
## Texture-only content patches. Native/scene/script changes stay in Google Play.
signal progress(downloaded: int, total: int, text: String)
signal fetch_completed(response: Array)
const MAX_PACK_BYTES: int = 33554432
const MAX_MEMBER_BYTES: int = 16777216
const MAX_EXPANDED_BYTES: int = 67108864
const MAX_TOTAL_BYTES: int = 268435456
const CHECK_TIMEOUT_SECONDS: float = 3.0
const DOWNLOAD_TIMEOUT_SECONDS: float = 40.0
var origin: String
var cache: String
var active: Dictionary = {}
var http: HTTPRequest
var completed_bytes: int = 0
var total_bytes: int = 0
var downloading: bool = false


func _process(_delta: float) -> void:
	if downloading and is_instance_valid(http):
		progress.emit(completed_bytes + http.get_downloaded_bytes(), total_bytes, I18n.t("Pobieranie aktualizacji…"))


func _hash(data: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(data)
	return context.finish().hex_encode()


func _matches(pattern: String, value: String) -> bool:
	var regex := RegEx.new()
	regex.compile(pattern)
	return regex.search(value) != null


func _path_ok(path: String) -> bool:
	if path.contains("..") or path.contains("\\") or path.contains(":") or path.contains("//"):
		return false
	if _matches("^\\.godot/imported/[A-Za-z0-9_.-]+\\.ctex$", path):
		return true
	return _matches("^client/assets/[A-Za-z0-9_./-]+\\.(png|webp|jpg|jpeg)(\\.import)?$", path)


func _valid_manifest(value: Variant, client_code: int) -> bool:
	if not value is Dictionary or int(value.get("schema", 0)) != 1 or not value.get("packs") is Array:
		return false
	# An empty release is a no-op for any binary; no incompatible resource
	# can be mounted. Non-empty releases retain the strict binary version gate.
	if not value["packs"].is_empty() and (client_code < int(value.get("min_client", 0)) or client_code > int(value.get("max_client", 2147483647))):
		return false
	if value["packs"].size() > 16:
		return false
	var seen: Dictionary = {}
	var total: int = 0
	for pack: Variant in value["packs"]:
		if not pack is Dictionary:
			return false
		var id: String = str(pack.get("id", ""))
		var url: String = str(pack.get("url", ""))
		var size: int = int(pack.get("size", 0))
		if not _matches("^[a-z0-9_-]{1,64}$", id) or seen.has(id):
			return false
		seen[id] = true
		if not url.begins_with(origin + "/play/content/") or url.contains("..") or not _matches("^/play/content/[A-Za-z0-9_./-]+\\.zip$", url.trim_prefix(origin)):
			return false
		if size < 1 or size > MAX_PACK_BYTES or not _matches("^[a-f0-9]{64}$", str(pack.get("sha256", ""))):
			return false
		total += size
		if total > MAX_TOTAL_BYTES or not pack.get("files") is Array or pack["files"].is_empty() or pack["files"].size() > 512:
			return false
		var paths: Dictionary = {}
		var expanded: int = 0
		for member: Variant in pack["files"]:
			if not member is Dictionary:
				return false
			var path: String = str(member.get("path", ""))
			var length: int = int(member.get("size", -1))
			if not _path_ok(path) or paths.has(path.to_lower()) or length < 0 or length > MAX_MEMBER_BYTES or not _matches("^[a-f0-9]{64}$", str(member.get("sha256", ""))):
				return false
			paths[path.to_lower()] = true
			expanded += length
		if expanded > MAX_EXPANDED_BYTES:
			return false
	return true


func _zip_index_ok(path: String, members: Array) -> bool:
	# Bound the central directory and expanded sizes BEFORE ZIPReader allocates.
	# ZIP64, encryption, links, duplicate paths and extra members are rejected.
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() < 22:
		return false
	var length: int = file.get_length()
	file.seek(maxi(0, length - 65557))
	var tail: PackedByteArray = file.get_buffer(65557)
	var eocd: int = -1
	for offset: int in range(tail.size() - 22, -1, -1):
		if tail.decode_u32(offset) == 0x06054b50 and offset + 22 + tail.decode_u16(offset + 20) == tail.size():
			eocd = offset
			break
	if eocd < 0 or tail.decode_u16(eocd + 4) != 0 or tail.decode_u16(eocd + 6) != 0:
		return false
	var count: int = tail.decode_u16(eocd + 10)
	var central_size: int = tail.decode_u32(eocd + 12)
	var central: int = tail.decode_u32(eocd + 16)
	if count != members.size() or count != tail.decode_u16(eocd + 8) or central_size > 262144 or central + central_size != length - tail.size() + eocd:
		return false
	var expected: Dictionary = {}
	for member: Dictionary in members:
		expected[member["path"]] = int(member["size"])
	file.seek(central)
	for _index: int in range(count):
		var header: PackedByteArray = file.get_buffer(46)
		if header.size() != 46 or header.decode_u32(0) != 0x02014b50:
			return false
		var flags: int = header.decode_u16(8)
		var method: int = header.decode_u16(10)
		var packed: int = header.decode_u32(20)
		var expanded: int = header.decode_u32(24)
		var name_length: int = header.decode_u16(28)
		var extra: int = header.decode_u16(30) + header.decode_u16(32)
		var local: int = header.decode_u32(42)
		var name_bytes: PackedByteArray = file.get_buffer(name_length)
		var name: String = name_bytes.get_string_from_utf8()
		if not expected.has(name) or expected[name] != expanded or not name_bytes == name.to_utf8_buffer():
			return false
		if (flags & 1) != 0 or method not in [0, 8] or expanded > MAX_MEMBER_BYTES or packed > length or header.decode_u16(34) != 0 or ((header.decode_u32(38) >> 16) & 0xf000) == 0xa000:
			return false
		expected.erase(name)
		var next: int = file.get_position() + extra
		if next > central + central_size or local + 30 + packed > central:
			return false
		file.seek(local)
		var local_header: PackedByteArray = file.get_buffer(30)
		if local_header.size() != 30 or local_header.decode_u32(0) != 0x04034b50 or local_header.decode_u16(6) != flags or local_header.decode_u16(8) != method:
			return false
		if file.get_buffer(local_header.decode_u16(26)) != name_bytes or file.get_position() + local_header.decode_u16(28) + packed > central:
			return false
		file.seek(next)
	return expected.is_empty() and file.get_position() == central + central_size


func _verify_pack(path: String, pack: Dictionary) -> bool:
	if not FileAccess.file_exists(path):
		return false
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() != int(pack["size"]):
		return false
	file.close()
	if FileAccess.get_sha256(path) != str(pack["sha256"]) or not _zip_index_ok(path, pack["files"]):
		return false
	var reader := ZIPReader.new()
	if reader.open(path) != OK:
		return false
	var valid: bool = true
	var members: PackedStringArray = reader.get_files()
	for member: Dictionary in pack["files"]:
		var name: String = str(member["path"])
		var bytes: PackedByteArray = reader.read_file(name)
		if bytes.size() != int(member["size"]) or _hash(bytes) != str(member["sha256"]):
			valid = false
			break
		if name.ends_with(".import"):
			var text: String = bytes.get_string_from_utf8()
			if text.contains("Object(") or text.contains("Resource(") or text.contains("ExtResource(") or text.contains("SubResource("):
				valid = false
				break
			var config := ConfigFile.new()
			if config.parse(text) != OK or config.get_value("remap", "type", "") != "CompressedTexture2D" or config.get_value("remap", "importer", "") != "texture":
				valid = false
				break
			for key: String in config.get_section_keys("remap"):
				if key == "path" or key.begins_with("path."):
					var target: String = str(config.get_value("remap", key, "")).trim_prefix("res://")
					if not target.begins_with(".godot/imported/") or not target.ends_with(".ctex") or not members.has(target):
						valid = false
	reader.close()
	return valid


func _fetch(url: String, output: String = "") -> Dictionary:
	http = HTTPRequest.new()
	http.timeout = CHECK_TIMEOUT_SECONDS if output.is_empty() else DOWNLOAD_TIMEOUT_SECONDS
	http.max_redirects = 0
	http.body_size_limit = 1048576 if output.is_empty() else MAX_PACK_BYTES
	http.download_file = output
	add_child(http)
	http.request_completed.connect(_fetch_result)
	if http.request(url, PackedStringArray(["Accept: application/json" if output.is_empty() else "Accept: application/zip"])) != OK:
		http.queue_free()
		http = null
		return {"ok": false}
	var response: Array = await fetch_completed
	http.queue_free()
	http = null
	return {"ok": response[0] == HTTPRequest.RESULT_SUCCESS and response[1] == 200, "body": response[3]}


func _fetch_result(result: int, code: int, headers: PackedStringArray, body: PackedByteArray) -> void:
	fetch_completed.emit([result, code, headers, body])


func _pack_path(pack: Dictionary) -> String:
	return cache + str(pack["sha256"]) + ".zip"


func cancel_check() -> void:
	# Called only as the boot scene exits; leave downloads and verified cache alone.
	if not downloading and is_instance_valid(http):
		http.cancel_request()
		# HTTPRequest.cancel_request does not complete its awaited signal.
		_fetch_result(HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray())


func run(server: String, client_code: int = 93) -> Dictionary:
	origin = server.trim_suffix("/")
	var address: Dictionary = preload("res://client/scripts/server_address.gd").parse_input(origin)
	if address.has("error"):
		return {"ok": false, "check_failed": true}
	cache = "user://content_updates/" + _hash((origin + ":" + str(client_code)).to_utf8_buffer()).substr(0, 24) + "/"
	if DirAccess.make_dir_recursive_absolute(cache) != OK:
		return {"ok": false, "check_failed": true}
	active = {}
	var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string(cache + "active.json")) if FileAccess.file_exists(cache + "active.json") else null
	if _valid_manifest(saved, client_code):
		active = saved
	progress.emit(0, 0, I18n.t("Sprawdzanie aktualizacji…"))
	var response: Dictionary = await _fetch(origin + "/play/content/manifest.json")
	var next: Variant = JSON.parse_string(response.get("body", PackedByteArray()).get_string_from_utf8()) if response.get("ok", false) else null
	if not _valid_manifest(next, client_code):
		return {"ok": false, "check_failed": true}
	completed_bytes = 0
	total_bytes = 0
	for pack: Dictionary in next["packs"]:
		if not _verify_pack(_pack_path(pack), pack):
			total_bytes += int(pack["size"])
	for pack: Dictionary in next["packs"]:
		var path: String = _pack_path(pack)
		if _verify_pack(path, pack):
			continue
		var temporary: String = path + ".part"
		DirAccess.remove_absolute(temporary)
		downloading = true
		var received: Dictionary = await _fetch(str(pack["url"]), temporary)
		downloading = false
		if not received.get("ok", false) or not _verify_pack(temporary, pack):
			DirAccess.remove_absolute(temporary)
			return {"ok": false}
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
		if DirAccess.rename_absolute(temporary, path) != OK:
			DirAccess.remove_absolute(temporary)
			return {"ok": false}
		completed_bytes += int(pack["size"])
		progress.emit(completed_bytes, total_bytes, I18n.t("Pobieranie aktualizacji…"))
		await get_tree().process_frame
	var output := FileAccess.open(cache + "active.json.part", FileAccess.WRITE)
	if output == null:
		return {"ok": false}
	output.store_string(JSON.stringify(next))
	output.close()
	if DirAccess.rename_absolute(cache + "active.json.part", cache + "active.json") != OK:
		return {"ok": false}
	active = next
	return {"ok": true}


func mount_active() -> bool:
	# Check the entire release before mounting any pack; a failed new release
	# retains the last complete manifest. Invalid cache falls back to built-ins.
	if active.is_empty():
		return true
	for pack: Dictionary in active.get("packs", []):
		if not _verify_pack(_pack_path(pack), pack):
			return false
	for pack: Dictionary in active.get("packs", []):
		if not ProjectSettings.load_resource_pack(_pack_path(pack), true):
			return false
	return true
