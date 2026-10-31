extends SceneTree

const Policy = preload("res://client/scripts/update_policy.gd")
var failures: int = 0
var checks: int = 0


func _initialize() -> void:
	# Google Play delivers app bytes. Railway only announces latest/minimum versions.
	var baseline: Dictionary = {
		"ok": true, "latest_version_code": 5, "latest_version": "0.1.4",
		"min_version_code": 0, "download_url": "", "message": "",
	}
	var parsed: Dictionary = Policy.parse_manifest(baseline, 5)
	_expect(not parsed.is_empty() and not parsed["available"] and not parsed["required"], "Current Play version stays playable")
	var release: Dictionary = baseline.duplicate(true)
	release["latest_version_code"] = 6.0
	release["latest_version"] = "0.1.5"
	parsed = Policy.parse_manifest(release, 5)
	_expect(parsed["available"] and not parsed["required"], "Higher Play version is optional even without APK metadata")
	release["min_version_code"] = 6.0
	parsed = Policy.parse_manifest(release, 5)
	_expect(parsed["required"] and parsed["available"], "Higher minimum requires a Play update")
	parsed = Policy.parse_manifest(release, 6)
	_expect(not parsed["required"] and not parsed["available"], "Installing latest satisfies the policy")
	for invalid: Variant in [null, true, false, "6", -1, 1.5, 2100000001.0, INF, NAN]:
		_expect(not Policy.valid_version_code(invalid), "Reject an invalid version code")
	for valid: Variant in [0, 5.0, 2100000000]:
		_expect(Policy.valid_version_code(valid), "Accept bounded integer version codes")
	var broken: Dictionary = baseline.duplicate(true)
	broken["min_version_code"] = 6
	_expect(Policy.parse_manifest(broken, 5).is_empty(), "Minimum cannot exceed latest")
	broken = baseline.duplicate(true)
	broken.erase("latest_version")
	_expect(Policy.parse_manifest(broken, 5).is_empty(), "Require release label")
	broken = baseline.duplicate(true)
	broken["message"] = "first\nsecond"
	_expect(Policy.parse_manifest(broken, 5).is_empty(), "Reject controls in release text")
	broken = baseline.duplicate(true)
	broken["latest_version"] = "x".repeat(41)
	_expect(Policy.parse_manifest(broken, 5).is_empty(), "Bound release labels")
	print("Google Play update policy: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)


func _expect(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)
