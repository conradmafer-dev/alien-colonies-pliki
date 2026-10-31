extends SceneTree
## OFFLINE ONLY: run after import, through tests/run_localized_test.gd.
## Does not access saved credentials, a live server or gameplay state.
const Art = preload("res://client/scripts/art_library.gd")
const MapScript = preload("res://client/scripts/galaxy_map.gd")
var failures: int = 0

func _initialize() -> void:
	_run.call_deferred()

func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func _run() -> void:
	var galaxy_map: Control = MapScript.new()
	root.add_child(galaxy_map)
	galaxy_map.size = Vector2(720, 640)
	await process_frame
	_expect(galaxy_map.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS, "Map uses mipmap filtering")
	for name: String in Art.GALAXIES:
		var key: String = "galaxies/" + name
		var texture: Texture2D = Art.texture(key)
		_expect(texture != null, "Texture imports: " + name)
		if texture == null:
			continue
		_expect(texture.get_size() == Vector2(1536, 1024), "Full native dimensions: " + name)
		galaxy_map.call("set_galaxy_art", texture)
		for width: int in [450, 720, 1080]:
			galaxy_map.size = Vector2(width, 640)
			galaxy_map.call("reset_view")
			var rect: Rect2 = galaxy_map.call("_galaxy_art_rect")
			_expect(is_equal_approx(rect.size.x / rect.size.y, 1.5), "Native aspect ratio")
			var initial_size: Vector2 = rect.size
			galaxy_map.call("zoom_in")
			rect = galaxy_map.call("_galaxy_art_rect")
			_expect(rect.size.is_equal_approx(initial_size * 1.4), "Zoom preserves aspect ratio")
		_expect(Art.galaxy_cache_keys.size() <= 2, "At most two galaxy textures in explicit library cache")
		var cached: int = 0
		for cached_key: String in Art.textures:
			if cached_key.begins_with("galaxies/"):
				cached += 1
		_expect(cached <= 2, "Expired explicit cache entries removed")
		await process_frame
	_expect(Art.texture("galaxies/not_a_galaxy") == null, "Invalid galaxy key rejected")
	galaxy_map.free()
	print("GALAXY_ART_HD failures=", failures)
	quit(0 if failures == 0 else 1)
