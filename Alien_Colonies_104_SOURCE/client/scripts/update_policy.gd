extends RefCounted

const ServerAddressScript = preload("res://client/scripts/server_address.gd")
const MAX_VERSION_CODE: int = 2100000000
# Kept for compatibility with the legacy direct-APK downloader scripts that are
# still present in the source tree. Google Play builds do not export or invoke
# those scripts; Play remains the only application-delivery mechanism.
const MAX_APK_BYTES: int = 268435456


## JSON numbers arrive as floats. Accept only exact integers, never strings or booleans.
static func valid_version_code(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	var number: float = float(value)
	return is_finite(number) and number >= 0.0 and number <= MAX_VERSION_CODE and floor(number) == number


## Google Play owns application delivery. Railway only announces the newest supported
## client version and can require a minimum version after an incompatible server change.
static func parse_manifest(value: Variant, current_code: int) -> Dictionary:
	if not value is Dictionary:
		return {}
	var data: Dictionary = value
	if not valid_version_code(data.get("latest_version_code")) or not valid_version_code(data.get("min_version_code")):
		return {}
	var latest: int = int(data["latest_version_code"])
	var minimum: int = int(data["min_version_code"])
	if minimum > latest:
		return {}
	if not _valid_text(data.get("latest_version"), 40) or not _valid_text(data.get("message"), 300):
		return {}
	return {
		"latest_version_code": latest,
		"latest_version": str(data["latest_version"]),
		"min_version_code": minimum,
		"message": str(data["message"]),
		"required": current_code < minimum,
		"available": latest > current_code,
	}


## Legacy direct-APK validation helpers are intentionally retained only so old
## source files and tests still parse cleanly in the Godot editor. The Google
## Play build excludes apk_download.gd/android_apk_install.gd/apk_manifest.gd.
static func valid_apk_sha256(value: Variant) -> String:
	if not value is String:
		return ""
	var digest: String = str(value).to_lower()
	if digest.length() != 64:
		return ""
	for index: int in range(digest.length()):
		if not "0123456789abcdef".contains(digest.substr(index, 1)):
			return ""
	return digest


static func valid_apk_size(value: Variant) -> int:
	if not valid_version_code(value):
		return 0
	var size: int = int(value)
	return size if size > 0 and size <= MAX_APK_BYTES else 0


static func public_download_url(value: Variant) -> String:
	if not value is String:
		return ""
	var link: String = value
	if link.is_empty() or link.length() > 2048 or link.contains("\\") or link.contains("#"):
		return ""
	for index: int in range(link.length()):
		var codepoint: int = link.unicode_at(index)
		if codepoint <= 32 or codepoint >= 127:
			return ""
	var expression: RegEx = RegEx.new()
	expression.compile("^https://([A-Za-z0-9.-]+)(?::([0-9]{1,5}))?([/?].*)?$")
	var matched: RegExMatch = expression.search(link)
	if matched == null:
		return ""
	var host: String = matched.get_string(1).to_lower()
	var port: String = matched.get_string(2)
	var origin: String = "https://" + host + (":" + port if not port.is_empty() else "")
	if ServerAddressScript.parse_input(origin).has("error") or host.is_valid_ip_address() or not host.contains("."):
		return ""
	expression.compile("^[a-z][a-z0-9-]*$")
	if expression.search(host.get_slice(".", host.get_slice_count(".") - 1)) == null:
		return ""
	for suffix: String in ["localhost", "local", "internal", "home", "lan", "test", "invalid", "example", "onion", "home.arpa"]:
		if host == suffix or host.ends_with("." + suffix):
			return ""
	expression.compile("(?i)%(?:0[0-9a-f]|1[0-9a-f]|7f|5c)")
	if expression.search(link) != null:
		return ""
	return link


static func _valid_text(value: Variant, maximum: int) -> bool:
	if not value is String or str(value).length() > maximum:
		return false
	var text: String = value
	for index: int in range(text.length()):
		var codepoint: int = text.unicode_at(index)
		if codepoint < 32 or codepoint == 127:
			return false
	return true
