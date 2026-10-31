extends RefCounted
## Presentation only; survives client updates, logout and language changes.
const SETTINGS_PATH: String = "user://interface.cfg"
const SECTION: String = "interface"
const DETAIL_KEY: String = "detailed_descriptions"
const RESEARCH_ROWS_KEY: String = "research_three_rows"
const RESEARCH_ROWS_DEFAULT_REVISION_KEY: String = "research_rows_default_revision"
const RESEARCH_ROWS_DEFAULT_REVISION: int = 1


static func load_detailed_descriptions(path: String = SETTINGS_PATH) -> bool:
	var config: ConfigFile = ConfigFile.new()
	if config.load(path) != OK:
		return false
	var value: Variant = config.get_value(SECTION, DETAIL_KEY, false)
	# Reject corrupt/string values; the first-run default is ALWAYS brief.
	return value if value is bool else false


static func save_detailed_descriptions(enabled: bool, path: String = SETTINGS_PATH) -> Error:
	var config: ConfigFile = ConfigFile.new()
	config.load(path)
	config.set_value(SECTION, DETAIL_KEY, enabled)
	return config.save(path)


static func load_research_three_rows(_path: String = SETTINGS_PATH) -> bool:
	# Release 73 removes the alternate layout, including saved opt-outs.
	return true


static func save_research_three_rows(_enabled: bool, path: String = SETTINGS_PATH) -> Error:
	var config: ConfigFile = ConfigFile.new()
	config.load(path)
	config.set_value(SECTION, RESEARCH_ROWS_KEY, true)
	config.set_value(SECTION, RESEARCH_ROWS_DEFAULT_REVISION_KEY, RESEARCH_ROWS_DEFAULT_REVISION)
	return config.save(path)
