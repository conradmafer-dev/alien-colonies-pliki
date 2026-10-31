extends SceneTree

const Manifest = preload("res://client/scripts/apk_manifest.gd")
const Installer = preload("res://client/scripts/android_apk_install.gd")
const PACKAGE: String = "com.conradmafer.aliencolonies"
const FIXTURE: String = "user://apk_manifest_parser_test.zip"
# AndroidManifest.xml only, extracted from the user's working0.1.6 Godot4.7
# export. This is not an APK, a signature fixture, or an installation test.
const REAL_016_MANIFEST: String = "res://tests/fixtures/apk_016_manifest.bin"
var checks: int = 0
var failures: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for utf8: bool in [false, true]:
		for code: int in [1, 7, 8, 2147483647]:
			var xml: PackedByteArray = _xml(utf8, code)
			var result: Dictionary = Manifest.parse_binary_xml(xml)
			_expect(bool(result.get("ok", false)), "Parse UTF-8/UTF-16 binary manifest: " + str(result))
			_expect(result.get("package") == PACKAGE and result.get("version_code") == code, "Exact package and version are retained")
			_expect(bool(Manifest.validate_identity(result, PACKAGE, code).get("ok", false)), "Correct identity accepted")
			_expect(Manifest.validate_identity(result, "other.game", code).get("reason") == "package_mismatch", "Wrong package remains blocked")
			_expect(Manifest.validate_identity(result, PACKAGE, 9).get("reason") == "version_mismatch", "Wrong version remains blocked")
			_write_zip(xml)
			_expect(Manifest.read_apk(FIXTURE) == result, "ZIPReader identity matches binary XML identity")
		# Non-ASCII + supplementary characters verify UTF-16 code-unit lengths.
		for extra: String in ["świat 🚀", "x".repeat(130), "x".repeat(32768) if not utf8 else "x".repeat(1000)]:
			_expect(bool(Manifest.parse_binary_xml(_xml(utf8, 8, PACKAGE, extra)).get("ok", false)), "Variable-length string prefix accepted")
		var good: PackedByteArray = _xml(utf8, 8)
		for length: int in range(good.size()):
			_expect(not bool(Manifest.parse_binary_xml(good.slice(0, length)).get("ok", false)), "All truncations fail closed")
		var pool_pos: int = 8
		var root_pos: int = pool_pos + int(good.decode_u32(pool_pos + 4))
		var attribute: int = root_pos + 36
		for mutation: Array in [
			[0, 2, 1], [2, 2, 4], [4, 4, good.size() + 4],
			[pool_pos + 2, 2, 12], [pool_pos + 4, 4, 0], [pool_pos + 4, 4, good.size() * 4],
			[pool_pos + 8, 4, 0xffffffff], [pool_pos + 20, 4, 0xffffffff], [pool_pos + 28, 4, 0xffffffff],
			[root_pos + 2, 2, 8], [root_pos + 4, 4, 0], [root_pos + 20, 4, 0xfffffffe],
			[root_pos + 24, 2, 0], [root_pos + 26, 2, 0], [root_pos + 28, 2, 65535],
			[attribute + 4, 4, 0xfffffffe], [attribute + 8, 4, 0xfffffffe], [attribute + 12, 2, 0],
			[attribute + 16, 4, 0xfffffffe], [attribute + 20 + 16, 4, 0], [attribute + 20 + 16, 4, 0xffffffff],
			[good.size() - 4, 4, 0xfffffffe]
		]:
			var broken: PackedByteArray = good.duplicate()
			if int(mutation[1]) == 2:
				broken.encode_u16(int(mutation[0]), int(mutation[2]))
			else:
				broken.encode_u32(int(mutation[0]), int(mutation[2]))
			_expect(not bool(Manifest.parse_binary_xml(broken).get("ok", false)), "Malformed chunk / offsets / references fail closed: " + str(mutation))
		var invalid_utf: PackedByteArray = good.duplicate()
		var string_start: int = 8 + int(good.decode_u32(28))
		invalid_utf[string_start + (2 if utf8 else 2)] = 0
		_expect(not bool(Manifest.parse_binary_xml(invalid_utf).get("ok", false)), "Embedded NUL cannot become an accepted string")
		var duplicated: PackedByteArray = good.slice(0, root_pos + 76)
		duplicated.append_array(good.slice(attribute, attribute + 20))
		duplicated.append_array(good.slice(root_pos + 76))
		duplicated.encode_u32(4, duplicated.size())
		duplicated.encode_u32(root_pos + 4, 96)
		duplicated.encode_u16(root_pos + 28, 3)
		_expect(Manifest.parse_binary_xml(duplicated).get("reason") == "duplicate_attribute", "Duplicated identity attribute rejected")
		var major: PackedByteArray = _xml(utf8, 8, PACKAGE, "versionCodeMajor", true)
		_expect(Manifest.parse_binary_xml(major).get("reason") == "unsupported_version_major", "Unsupported high version code never compares equal to its low32 bits")
	for bad_package: String in ["", "game", ".game", "game.", "com.1game", "com.hello-world", "com.świecie"]:
		_expect(not bool(Manifest.parse_binary_xml(_xml(false, 8, bad_package)).get("ok", false)), "Invalid package is unreadable metadata, not accepted")
	for code: int in [0, -1, 2147483648]:
		_expect(not bool(Manifest.validate_identity({"ok": true, "package": PACKAGE, "version_code": code}, PACKAGE, code).get("ok", false)), "Invalid announced code remains blocked")
	_expect(not bool(Manifest.parse_binary_xml("<manifest package='com.fake'/>".to_utf8_buffer()).get("ok", false)), "Text/HTML not mistaken for Android binary XML")
	_expect(Installer._identity_failure("xml_header")["message"] != Installer._identity_failure("package_mismatch")["message"], "Unreadable metadata and actual mismatch have distinct errors")
	_expect(not bool(Installer.request_install(FIXTURE, 8).get("ok", false)), "Desktop cannot launch an APK installer")
	_test_zip_limits()
	_test_real_manifest()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(FIXTURE))
	print("APK manifest / install guard: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)


func _test_zip_limits() -> void:
	_write_zip(_xml(true, 8))
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(FIXTURE)
	var end: int = bytes.size() - 22
	var central: int = bytes.decode_u32(end + 16)
	for mutation: Array in [[end, 4, 0], [end + 4, 2, 1], [end + 16, 4, 0xffffffff], [central + 24, 4, Manifest.MAX_MANIFEST_BYTES + 1], [central + 20, 4, Manifest.MAX_MANIFEST_BYTES + 1], [central + 8, 2, 1], [central + 10, 2, 99], [central + 42, 4, 0xffffffff], [central + 46, 2, 0], [0, 4, 0]]:
		var broken: PackedByteArray = bytes.duplicate()
		if int(mutation[1]) == 2:
			broken.encode_u16(int(mutation[0]), int(mutation[2]))
		else:
			broken.encode_u32(int(mutation[0]), int(mutation[2]))
		var file: FileAccess = FileAccess.open(FIXTURE, FileAccess.WRITE)
		file.store_buffer(broken)
		file.close()
		_expect(not bool(Manifest.read_apk(FIXTURE).get("ok", false)), "Invalid / oversized / encrypted ZIP rejected before extraction")
	_write_zip(_xml(true, 8), true)
	_expect(Manifest.read_apk(FIXTURE).get("reason") == "zip_duplicate_manifest", "Duplicate manifest ZIP entry rejected")
	_expect(Manifest._safe_zip_extra(PackedByteArray([0x35, 0xd9, 2, 0, 0, 0])), "Android alignment ZIP extra allowed")
	_expect(not Manifest._safe_zip_extra(PackedByteArray([1, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0])), "ZIP64 override blocked")
	_expect(not Manifest._safe_zip_extra(PackedByteArray([1, 2, 3])), "Truncated ZIP extra blocked")
	_expect(not Manifest._safe_zip_extra(PackedByteArray([2, 0, 8, 0, 0])), "Out-of-bounds ZIP extra blocked")


func _test_real_manifest() -> void:
	var real_data: PackedByteArray = FileAccess.get_file_as_bytes(REAL_016_MANIFEST)
	var real_result: Dictionary = Manifest.parse_binary_xml(real_data)
	_expect(real_result == {"ok": true, "package": PACKAGE, "version_code": 7}, "Bundled actual Godot4.7 export0.1.6 manifest: " + str(real_result))
	_write_zip(real_data)
	_expect(Manifest.read_apk(FIXTURE) == real_result, "Actual manifest survives bounded ZIPReader extraction")
	# Optional device-export regression, without bundling APK or claiming a full
	# signature/install test. Pass -- --manifest-base64=<actual AndroidManifest.xml>.
	for argument: String in load("res://tests/test_arguments.gd").user_args():
		if argument.begins_with("--manifest-base64="):
			var data: PackedByteArray = Marshalls.base64_to_raw(argument.trim_prefix("--manifest-base64="))
			var result: Dictionary = Manifest.parse_binary_xml(data)
			_expect(result == {"ok": true, "package": PACKAGE, "version_code": 7}, "Actual user's Godot4.7 export0.1.6 manifest: " + str(result))
			_write_zip(data)
			_expect(Manifest.read_apk(FIXTURE) == result, "Actual manifest also survives bounded ZIPReader extraction")


func _xml(utf8: bool, code: int, package_name: String = PACKAGE, extra: String = "padding", major: bool = false) -> PackedByteArray:
	var strings: Array[String] = ["manifest", "package", package_name, Manifest.ANDROID_NS, "versionCode", extra]
	var pool: PackedByteArray = _pool(strings, utf8)
	var attrs: PackedByteArray = _attribute(0xffffffff, 1, 2, 3, 2)
	attrs.append_array(_attribute(3, 4, 0xffffffff, 0x10, code))
	if major:
		attrs.append_array(_attribute(3, 5, 0xffffffff, 0x10, 1))
	var element: PackedByteArray = _node(0x0102, 36 + attrs.size())
	element.append_array(_u32(0xffffffff))
	element.append_array(_u32(0))
	element.append_array(_u16(20))
	element.append_array(_u16(20))
	element.append_array(_u16(3 if major else 2))
	element.resize(36)
	element.append_array(attrs)
	var closing: PackedByteArray = _node(0x0103, 24)
	closing.append_array(_u32(0xffffffff))
	closing.append_array(_u32(0))
	var xml: PackedByteArray = _u16(3)
	xml.append_array(_u16(8))
	xml.append_array(_u32(8 + pool.size() + element.size() + closing.size()))
	xml.append_array(pool)
	xml.append_array(element)
	xml.append_array(closing)
	return xml


func _pool(strings: Array[String], utf8: bool) -> PackedByteArray:
	var content: PackedByteArray = PackedByteArray()
	var offsets: PackedByteArray = PackedByteArray()
	for string: String in strings:
		offsets.append_array(_u32(content.size()))
		var encoded: PackedByteArray = string.to_utf8_buffer() if utf8 else string.to_utf16_buffer()
		content.append_array(_encoded_length(string.to_utf16_buffer().size() / 2, utf8))
		if utf8:
			content.append_array(_encoded_length(encoded.size(), true))
		content.append_array(encoded)
		content.append(0)
		if not utf8:
			content.append(0)
	while content.size() % 4:
		content.append(0)
	var pool: PackedByteArray = _u16(1)
	pool.append_array(_u16(28))
	pool.append_array(_u32(28 + offsets.size() + content.size()))
	pool.append_array(_u32(strings.size()))
	pool.append_array(_u32(0))
	pool.append_array(_u32(0x100 if utf8 else 0))
	pool.append_array(_u32(28 + offsets.size()))
	pool.append_array(_u32(0))
	pool.append_array(offsets)
	pool.append_array(content)
	return pool


func _attribute(ns: int, name: int, raw: int, kind: int, value: int) -> PackedByteArray:
	var bytes: PackedByteArray = _u32(ns)
	bytes.append_array(_u32(name))
	bytes.append_array(_u32(raw))
	bytes.append_array(_u16(8))
	bytes.append(0)
	bytes.append(kind)
	bytes.append_array(_u32(value))
	return bytes


func _node(kind: int, size: int) -> PackedByteArray:
	var bytes: PackedByteArray = _u16(kind)
	bytes.append_array(_u16(16))
	bytes.append_array(_u32(size))
	bytes.append_array(_u32(1))
	bytes.append_array(_u32(0xffffffff))
	return bytes


func _encoded_length(length: int, utf8: bool) -> PackedByteArray:
	if utf8:
		return PackedByteArray([length]) if length < 0x80 else PackedByteArray([0x80 | (length >> 8), length & 255])
	if length < 0x8000:
		return _u16(length)
	var value: PackedByteArray = _u16(0x8000 | (length >> 16))
	value.append_array(_u16(length & 65535))
	return value


func _u16(value: int) -> PackedByteArray:
	var bytes: PackedByteArray = PackedByteArray()
	bytes.resize(2)
	bytes.encode_u16(0, value)
	return bytes


func _u32(value: int) -> PackedByteArray:
	var bytes: PackedByteArray = PackedByteArray()
	bytes.resize(4)
	bytes.encode_u32(0, value)
	return bytes


func _write_zip(manifest: PackedByteArray, duplicate_manifest: bool = false) -> void:
	var zip: ZIPPacker = ZIPPacker.new()
	_expect(zip.open(FIXTURE) == OK, "Open test ZIP")
	zip.start_file("AndroidManifest.xml")
	zip.write_file(manifest)
	zip.close_file()
	if duplicate_manifest:
		zip.start_file("AndroidManifest.xml")
		zip.write_file(manifest)
		zip.close_file()
	zip.close()


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
