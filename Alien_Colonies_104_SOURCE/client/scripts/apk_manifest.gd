extends RefCounted

## Minimal, bounded Android binary-XML identity reader, not a signature verifier.
## Layout reference: AOSP androidfw/ResourceTypes.h (ResStringPool/ResXMLTree).
## The Android package installer remains responsible for signatures and installability.
const MAX_APK_BYTES: int = 256 * 1024 * 1024
const MAX_MANIFEST_BYTES: int = 4 * 1024 * 1024
const MAX_STRINGS: int = 32768
const MAX_STRING_BYTES: int = 65536
const NO_INDEX: int = 0xffffffff
const ANDROID_NS: String = "http://schemas.android.com/apk/res/android"
const MANIFEST_NAME: String = "AndroidManifest.xml"


static func read_apk(path: String) -> Dictionary:
	# ZIPReader allocates using the central directory's uncompressed size. Bound
	# and disambiguate that exact entry before invoking it (no whole-APK read).
	var declared: Dictionary = _manifest_zip_entry(path)
	if not bool(declared.get("ok", false)):
		return declared
	var archive: ZIPReader = ZIPReader.new()
	if archive.open(path) != OK:
		return _bad("zip_open")
	var data: PackedByteArray = archive.read_file(MANIFEST_NAME, true)
	archive.close()
	if data.size() != int(declared["size"]):
		return _bad("zip_manifest_size")
	return parse_binary_xml(data)


static func validate_identity(identity: Dictionary, expected_package: String, expected_code: int) -> Dictionary:
	if not bool(identity.get("ok", false)):
		return _bad(str(identity.get("reason", "manifest_unreadable")))
	if expected_package.is_empty() or expected_code <= 0 or expected_code > 2147483647:
		return _bad("expected_identity_invalid")
	if str(identity.get("package", "")) != expected_package:
		return {"ok": false, "reason": "package_mismatch"}
	if int(identity.get("version_code", 0)) != expected_code:
		return {"ok": false, "reason": "version_mismatch"}
	return {"ok": true}


static func parse_binary_xml(data: PackedByteArray) -> Dictionary:
	if data.size() < 8 or data.size() > MAX_MANIFEST_BYTES:
		return _bad("xml_size")
	if data.decode_u16(0) != 0x0003 or data.decode_u16(2) != 8 or data.decode_u32(4) != data.size():
		return _bad("xml_header")
	var pool: Dictionary = {}
	var resources: PackedInt64Array = PackedInt64Array()
	var seen_resources: bool = false
	var stack: Array[Vector2i] = []
	var namespaces: Array[Vector2i] = []
	var identity: Dictionary = {}
	var pos: int = 8
	while pos < data.size():
		if data.size() - pos < 8:
			return _bad("chunk_header")
		var kind: int = data.decode_u16(pos)
		var header: int = data.decode_u16(pos + 2)
		var size: int = data.decode_u32(pos + 4)
		if header < 8 or size < header or size > data.size() - pos or size % 4 != 0:
			return _bad("chunk_bounds")
		var end: int = pos + size
		if kind == 0x0001:
			if not pool.is_empty() or not identity.is_empty():
				return _bad("duplicate_string_pool")
			pool = _read_pool(data, pos, header, size)
			if not bool(pool.get("ok", false)):
				return pool
		elif kind == 0x0180:
			if pool.is_empty() or seen_resources or not identity.is_empty() or header != 8 or (size - header) / 4 > MAX_STRINGS:
				return _bad("resource_map")
			seen_resources = true
			for offset: int in range(pos + header, end, 4):
				resources.append(data.decode_u32(offset))
		elif kind >= 0x0100 and kind <= 0x0104:
			if pool.is_empty() or header < 16:
				return _bad("xml_node_header")
			var strings: Array = pool["strings"]
			var ext: int = pos + header
			if kind == 0x0100 or kind == 0x0101:
				if end - ext < 8 or not _valid_ref(data.decode_u32(ext), strings, true) or not _valid_ref(data.decode_u32(ext + 4), strings):
					return _bad("namespace_bounds")
				var namespace_pair: Vector2i = Vector2i(data.decode_s32(ext), data.decode_s32(ext + 4))
				if kind == 0x0100:
					if namespaces.size() >= 128:
						return _bad("namespace_depth")
					namespaces.append(namespace_pair)
				elif namespaces.is_empty() or namespaces.pop_back() != namespace_pair:
					return _bad("namespace_end")
			elif kind == 0x0102:
				if end - ext < 20:
					return _bad("element_bounds")
				var ns: int = data.decode_u32(ext)
				var name: int = data.decode_u32(ext + 4)
				if not _valid_ref(ns, strings, true) or not _valid_ref(name, strings):
					return _bad("element_name")
				var attribute_start: int = data.decode_u16(ext + 8)
				var attribute_size: int = data.decode_u16(ext + 10)
				var count: int = data.decode_u16(ext + 12)
				if attribute_start < 20 or attribute_size < 20 or ext + attribute_start + count * attribute_size > end:
					return _bad("attribute_bounds")
				if stack.is_empty():
					if not identity.is_empty() or ns != NO_INDEX or str(strings[name]) != "manifest":
						return _bad("manifest_root")
					identity = _read_identity(data, ext + attribute_start, attribute_size, count, strings, resources)
					if not bool(identity.get("ok", false)):
						return identity
				if stack.size() >= 128:
					return _bad("element_depth")
				stack.append(Vector2i(data.decode_s32(ext), data.decode_s32(ext + 4)))
			elif kind == 0x0103:
				if end - ext < 8 or stack.is_empty() or stack.pop_back() != Vector2i(data.decode_s32(ext), data.decode_s32(ext + 4)):
					return _bad("element_end")
			elif kind == 0x0104:
				if end - ext < 12 or stack.is_empty() or not _valid_ref(data.decode_u32(ext), strings):
					return _bad("cdata_bounds")
		else:
			return _bad("unsupported_xml_chunk")
		pos = end
	if identity.is_empty() or not stack.is_empty() or not namespaces.is_empty():
		return _bad("xml_incomplete")
	return identity


static func _read_identity(data: PackedByteArray, start: int, stride: int, count: int, strings: Array, resources: PackedInt64Array) -> Dictionary:
	var package_name: String = ""
	var code: int = 0
	var found_code: bool = false
	var attributes: Dictionary = {}
	for index: int in range(count):
		var pos: int = start + index * stride
		var ns: int = data.decode_u32(pos)
		var name: int = data.decode_u32(pos + 4)
		var raw: int = data.decode_u32(pos + 8)
		var value_kind: int = data[pos + 15]
		var value: int = data.decode_u32(pos + 16)
		if not _valid_ref(ns, strings, true) or not _valid_ref(name, strings) or not _valid_ref(raw, strings, true) or data.decode_u16(pos + 12) != 8 or data[pos + 14] != 0:
			return _bad("attribute_value")
		var attr_name: String = str(strings[name])
		var namespace_name: String = "" if ns == NO_INDEX else str(strings[ns])
		var key: String = namespace_name + "\n" + attr_name
		if attributes.has(key):
			return _bad("duplicate_attribute")
		attributes[key] = true
		if ns == NO_INDEX and attr_name == "package":
			if value_kind != 0x03 or not _valid_ref(value, strings):
				return _bad("package_value")
			package_name = str(strings[value])
			if raw != NO_INDEX and str(strings[raw]) != package_name:
				return _bad("package_raw_value")
		elif namespace_name == ANDROID_NS and attr_name in ["versionCode", "versionCodeMajor"]:
			var wanted_resource: int = 0x0101021b if attr_name == "versionCode" else 0x01010576
			if name < resources.size() and resources[name] != wanted_resource:
				return _bad("version_resource")
			if value_kind != 0x10 and value_kind != 0x11:
				return _bad("version_type")
			if attr_name == "versionCode":
				found_code = true
				code = value
			else:
				if value != 0:
					return _bad("unsupported_version_major")
	# This project's release protocol uses a positive Android 32-bit versionCode.
	if not _valid_package(package_name) or not found_code or code <= 0 or code > 2147483647:
		return _bad("manifest_identity_missing")
	return {"ok": true, "package": package_name, "version_code": code}


static func _read_pool(data: PackedByteArray, start: int, header: int, size: int) -> Dictionary:
	if header < 28:
		return _bad("pool_header")
	var count: int = data.decode_u32(start + 8)
	var style_count: int = data.decode_u32(start + 12)
	var flags: int = data.decode_u32(start + 16)
	var string_start: int = data.decode_u32(start + 20)
	var style_start: int = data.decode_u32(start + 24)
	if count > MAX_STRINGS or style_count > MAX_STRINGS or header + (count + style_count) * 4 > string_start or string_start > size:
		return _bad("pool_bounds")
	if (style_count > 0 and (style_start < string_start or style_start > size)) or (style_count == 0 and style_start != 0):
		return _bad("pool_styles")
	var limit: int = start + (style_start if style_start > 0 else size)
	var strings: Array[String] = []
	var decoded_budget: int = 0
	for index: int in range(count):
		var pos: int = start + string_start + data.decode_u32(start + header + index * 4)
		var utf8: bool = (flags & 0x100) != 0
		var units: Vector2i = _length(data, pos, limit, utf8)
		if units.x < 0:
			return _bad("string_length")
		pos = units.y
		var byte_length: int = units.x * 2
		if utf8:
			var encoded: Vector2i = _length(data, pos, limit, true)
			if encoded.x < 0:
				return _bad("string_length")
			byte_length = encoded.x
			pos = encoded.y
		var terminator_size: int = 1 if utf8 else 2
		decoded_budget += byte_length
		if byte_length > MAX_STRING_BYTES or decoded_budget > MAX_MANIFEST_BYTES * 2 or pos + byte_length + terminator_size > limit:
			return _bad("string_bounds")
		if data[pos + byte_length] != 0 or (not utf8 and data[pos + byte_length + 1] != 0):
			return _bad("string_terminator")
		var bytes: PackedByteArray = data.slice(pos, pos + byte_length)
		var value: String = bytes.get_string_from_utf8() if utf8 else bytes.get_string_from_utf16()
		# Reject encoding errors, embedded NULs and inaccurate UTF-16 length prefixes.
		if (value.to_utf8_buffer() if utf8 else value.to_utf16_buffer()) != bytes or value.to_utf16_buffer().size() != units.x * 2:
			return _bad("string_encoding")
		strings.append(value)
	return {"ok": true, "strings": strings}


static func _length(data: PackedByteArray, pos: int, limit: int, utf8: bool) -> Vector2i:
	var width: int = 1 if utf8 else 2
	if pos < 0 or pos + width > limit:
		return Vector2i(-1, pos)
	var first: int = data[pos] if utf8 else data.decode_u16(pos)
	pos += width
	var high: int = 0x80 if utf8 else 0x8000
	if first & high:
		if pos + width > limit:
			return Vector2i(-1, pos)
		var second: int = data[pos] if utf8 else data.decode_u16(pos)
		return Vector2i(((first & (high - 1)) << (8 if utf8 else 16)) | second, pos + width)
	return Vector2i(first, pos)


static func _valid_ref(index: int, strings: Array, nullable: bool = false) -> bool:
	return (nullable and index == NO_INDEX) or (index >= 0 and index < strings.size())


static func _valid_package(package_name: String) -> bool:
	if package_name.length() > 255 or package_name.split(".").size() < 2:
		return false
	for part: String in package_name.split("."):
		if part.is_empty():
			return false
		for index: int in range(part.length()):
			var character: int = part.unicode_at(index)
			var letter: bool = (character >= 65 and character <= 90) or (character >= 97 and character <= 122)
			if not letter and not (index > 0 and (character == 95 or (character >= 48 and character <= 57))):
				return false
	return true


static func _manifest_zip_entry(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _bad("zip_missing")
	var length: int = file.get_length()
	if length < 22 or length > MAX_APK_BYTES:
		return _bad("zip_size")
	var tail_size: int = mini(length, 65535 + 22)
	file.seek(length - tail_size)
	var tail: PackedByteArray = file.get_buffer(tail_size)
	var eocd: int = -1
	for pos: int in range(tail.size() - 22, -1, -1):
		if tail.decode_u32(pos) == 0x06054b50 and pos + 22 + tail.decode_u16(pos + 20) == tail.size():
			eocd = pos
			break
	if eocd < 0 or tail.decode_u16(eocd + 4) != 0 or tail.decode_u16(eocd + 6) != 0:
		return _bad("zip_directory")
	var entries: int = tail.decode_u16(eocd + 10)
	var directory_size: int = tail.decode_u32(eocd + 12)
	var directory: int = tail.decode_u32(eocd + 16)
	var directory_start: int = directory
	var directory_end: int = directory + directory_size
	if entries == 65535 or entries != tail.decode_u16(eocd + 8) or directory_end != length - tail_size + eocd:
		return _bad("zip_directory_bounds")
	var manifest: Dictionary = {}
	for index: int in range(entries):
		if directory_end - directory < 46:
			return _bad("zip_entry_bounds")
		file.seek(directory)
		var header: PackedByteArray = file.get_buffer(46)
		if header.size() != 46 or header.decode_u32(0) != 0x02014b50:
			return _bad("zip_entry_header")
		var name_size: int = header.decode_u16(28)
		var extra_size: int = header.decode_u16(30)
		var comment_size: int = header.decode_u16(32)
		var next: int = directory + 46 + name_size + extra_size + comment_size
		if next > directory_end:
			return _bad("zip_entry_bounds")
		var filename: PackedByteArray = file.get_buffer(name_size)
		# minizip uses C-string names. Reject NUL aliases before its lookup so an
		# unchecked "AndroidManifest.xml\0suffix" cannot shadow the bounded entry.
		if filename.has(0):
			return _bad("zip_filename_nul")
		if filename == MANIFEST_NAME.to_utf8_buffer():
			if not manifest.is_empty():
				return _bad("zip_duplicate_manifest")
			var compressed: int = header.decode_u32(20)
			var unpacked: int = header.decode_u32(24)
			var local: int = header.decode_u32(42)
			var method: int = header.decode_u16(10)
			if unpacked < 8 or unpacked > MAX_MANIFEST_BYTES or compressed > MAX_MANIFEST_BYTES or header.decode_u16(8) & 1 or header.decode_u16(34) != 0 or method not in [0, 8] or local + 30 > directory_start:
				return _bad("zip_manifest_limits")
			if not _safe_zip_extra(file.get_buffer(extra_size)):
				return _bad("zip_manifest_extra")
			file.seek(local)
			var local_header: PackedByteArray = file.get_buffer(30)
			if local_header.size() != 30 or local_header.decode_u32(0) != 0x04034b50 or local_header.decode_u16(8) != method or local_header.decode_u16(26) != name_size:
				return _bad("zip_local_header")
			if file.get_buffer(name_size) != filename or local + 30 + name_size + local_header.decode_u16(28) + compressed > directory_start:
				return _bad("zip_local_bounds")
			manifest = {"ok": true, "size": unpacked}
		directory = next
	file.close()
	if directory != directory_end or manifest.is_empty():
		return _bad("zip_manifest_missing")
	return manifest


static func _safe_zip_extra(extra: PackedByteArray) -> bool:
	var pos: int = 0
	while pos < extra.size():
		if extra.size() - pos < 4:
			return false
		var kind: int = extra.decode_u16(pos)
		var size: int = extra.decode_u16(pos + 2)
		if kind == 1 or size > extra.size() - pos - 4:
			# APKs are bounded to256MiB; ZIP64 size/offset overrides are unnecessary.
			return false
		pos += 4 + size
	return true


static func _bad(reason: String) -> Dictionary:
	return {"ok": false, "reason": reason}
