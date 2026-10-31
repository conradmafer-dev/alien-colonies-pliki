extends SceneTree
## OFFLINE ONLY. Run after the Godot import step.
const Art = preload("res://client/scripts/art_library.gd")
const Client = preload("res://client/scripts/main.gd")
var failures: int = 0

func _initialize() -> void:
	_run.call_deferred()

func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func _run() -> void:
	# Do not add this client to the tree: _ready() must not load a session or poll.
	var client: Control = Client.new()
	var legacy: Dictionary = {
		"phase_sentinel": "races/zetans/echo_observatory",
		"iron_bastion": "races/automatons/magnetic_citadel",
		"rooted_spore": "races/symbionts/renewal_grove",
		"acid_spire": "swarm/weapon",
	}
	for key: String in legacy:
		var art_key: String = Art.defense_art_key(key)
		_expect(not art_key.is_empty(), "Defense mapped: " + key)
		var texture: Texture2D = Art.texture(art_key)
		_expect(texture != null, "Texture imported: " + key)
		if texture != null:
			_expect(texture.get_size() == Vector2(762, 508), "Actual non-upscaled dimensions: " + key)
		var entry: Dictionary = {"key": key, "art_key": legacy[key]}
		_expect(str(client.call("_entry_art_key", entry, key)) == art_key, "0.7.0 server compatibility: " + key)
		_expect(Art.texture(str(legacy[key])) != null, "Original building art preserved")
	_expect(Art.defense_art_key("scout").is_empty(), "No override for ordinary ship")
	_expect(str(client.call("_entry_art_key", {"key": "scout", "art_key": "swarm/scout"}, "scout")) == "swarm/scout", "Ship art unchanged")
	client.free()
	print("DEFENSE_ART_071 failures=", failures)
	quit(0 if failures == 0 else 1)
