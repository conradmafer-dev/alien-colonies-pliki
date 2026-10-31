extends Node
## A short-lived background loader. It outlives a closed replay only long enough
## to collect already-running ResourceLoader jobs; close never waits for them.
const Art = preload("res://client/scripts/art_library.gd")
const MAX_PENDING: int = 2
var receiver: WeakRef
var queued: Array[String] = []
var pending: Dictionary = {}
var requested: Dictionary = {}

func configure(board: Control) -> void:
	receiver = weakref(board)
	process_mode = Node.PROCESS_MODE_ALWAYS

func request_keys(keys: Array[String]) -> void:
	for source: String in keys:
		var key: String = Art.normalized_key(source)
		if key.is_empty() or requested.has(key): continue
		requested[key] = true
		if Art.textures.has(key):
			_deliver(key, Art.textures[key])
		else:
			queued.append(key)

func cancel() -> void:
	receiver = null
	queued.clear()
	# Pending jobs cannot be cancelled in Godot. Poll to completion, then release
	# them with load_threaded_get, without retaining the report or its host.
	if pending.is_empty(): queue_free()

func _deliver(key: String, texture: Texture2D) -> void:
	var board: Object = receiver.get_ref() if receiver != null else null
	if is_instance_valid(board): board.accept_texture(key, texture)

func _process(_delta: float) -> void:
	if receiver != null and receiver.get_ref() == null: cancel()
	# At most one completed texture is attached per frame. Never call get while
	# loading: that would turn the threaded request back into a blocking load.
	for path: String in pending:
		var status: int = ResourceLoader.load_threaded_get_status(path)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS: continue
		var key: String = pending[path]
		pending.erase(path)
		if status == ResourceLoader.THREAD_LOAD_LOADED:
			var texture: Texture2D = ResourceLoader.load_threaded_get(path) as Texture2D
			Art.cache_texture(key, texture)
			_deliver(key, texture)
		elif status == ResourceLoader.THREAD_LOAD_FAILED:
			ResourceLoader.load_threaded_get(path)
		break
	while receiver != null and pending.size() < MAX_PENDING and not queued.is_empty():
		var key: String = queued.pop_front()
		var path: String = Art.texture_path(key)
		if path.is_empty(): continue
		if ResourceLoader.load_threaded_request(path, "Texture2D") == OK:
			pending[path] = key
	if receiver == null and pending.is_empty(): queue_free()
