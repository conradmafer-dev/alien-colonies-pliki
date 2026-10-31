extends RefCounted

static func user_args() -> PackedStringArray:
	var arguments: PackedStringArray = OS.get_cmdline_user_args()
	if not arguments.is_empty() and arguments[0].ends_with(".gd"):
		arguments.remove_at(0)
	return arguments
