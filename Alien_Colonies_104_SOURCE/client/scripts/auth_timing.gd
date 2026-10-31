extends RefCounted
## Local, bounded diagnostics: account contents and connection details are excluded.

const STORE_PATH: String = "user://auth_timings.json"
const MAX_RECORDS: int = 20
const MAX_FILE_BYTES: int = 16 * 1024
const MAX_NUMBER: int = 2147483647
const OPERATIONS: Array[String] = ["login", "register", "logout"]
const STAGES: Array[String] = ["prepare_ms", "network_ms", "apply_ms", "local_ms"]


static func record(operation: String, stages: Dictionary, result: int = -1, status: int = 0) -> void:
	var entry: Dictionary = _clean({"operation": operation, "stages": stages, "result": result, "status": status})
	if entry.is_empty():
		return
	# Keep this useful even when the device cannot write its diagnostic file.
	print("[auth timing] " + JSON.stringify(entry))
	var records: Array[Dictionary] = _read_records()
	records.append(entry)
	while records.size() > MAX_RECORDS:
		records.pop_front()
	var encoded: String = JSON.stringify(records)
	if encoded.to_utf8_buffer().size() > MAX_FILE_BYTES:
		return
	var file: FileAccess = FileAccess.open(STORE_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(encoded)
		file.close()


static func _number(value: Variant, from_disk: bool) -> int:
	if typeof(value) == TYPE_INT and value >= 0 and value <= MAX_NUMBER:
		return int(value)
	# Godot's JSON parser represents every JSON number as float.
	if from_disk and typeof(value) == TYPE_FLOAT and is_finite(value) and value >= 0 and value <= MAX_NUMBER and floor(value) == value:
		return int(value)
	return -1


static func _clean(raw: Variant, from_disk: bool = false) -> Dictionary:
	if not raw is Dictionary or typeof(raw.get("operation")) != TYPE_STRING or raw["operation"] not in OPERATIONS:
		return {}
	var supplied: Variant = raw.get("stages")
	if not supplied is Dictionary:
		return {}
	var stages: Dictionary = {}
	var positive: bool = false
	for key: String in STAGES:
		var duration: int = _number(supplied.get(key), from_disk)
		if duration >= 0:
			stages[key] = duration
			positive = positive or duration > 0
	if not positive:
		return {}
	var entry: Dictionary = {"operation": raw["operation"], "stages": stages}
	for key: String in ["result", "status"]:
		var value: int = _number(raw.get(key), from_disk)
		if value >= 0:
			entry[key] = value
	return entry


static func _read_records() -> Array[Dictionary]:
	var records: Array[Dictionary] = []
	if not FileAccess.file_exists(STORE_PATH):
		return records
	var file: FileAccess = FileAccess.open(STORE_PATH, FileAccess.READ)
	if file == null:
		return records
	if file.get_length() > MAX_FILE_BYTES:
		file.close()
		return records
	var parser: JSON = JSON.new()
	var error: Error = parser.parse(file.get_as_text())
	file.close()
	if error != OK or not parser.data is Array:
		return records
	for candidate: Variant in parser.data:
		var entry: Dictionary = _clean(candidate, true)
		if not entry.is_empty():
			records.append(entry)
			if records.size() > MAX_RECORDS:
				records.pop_front()
	return records
