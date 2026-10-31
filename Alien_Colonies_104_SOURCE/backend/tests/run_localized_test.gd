extends SceneTree
## --script compiles preloads before autoloads; defer suite loading until ready.
## Run: godot --headless --path . --script tests/run_localized_test.gd -- tests/test_foo.gd [fixture]

func _initialize() -> void:
	_start_suite.call_deferred()

func _start_suite() -> void:
	var arguments: PackedStringArray = OS.get_cmdline_user_args()
	if arguments.is_empty():
		push_error("Pass a test script after --")
		quit(2)
		return
	var target: GDScript = load(arguments[0])
	if target == null:
		quit(2)
		return
	# Existing suites read their arguments after --. They accept the suite path
	# at index zero through the common helper in test_arguments.gd.
	set_script(target)
	call("_initialize")
