extends RefCounted
## Compatibility adapter for servers that expose rendered report text only.
## Match complete authored templates and numeric argument spans; never search
## arbitrary prose for translated resource words or alter player-name arguments.
const Resources = preload("res://client/scripts/resource_info.gd")
const RECYCLE: String = "{0}: odzyskano {1} metalu, {2} kryształów i {3} paliwa."
const RECYCLE_ICONS: String = "{0}: odzyskano {1}, {2} i {3}."
const ARCHIVE: String = "{0}: ukończone badanie zwróciło {1} zwykłych kryształów."
const ARCHIVE_ICONS: String = "{0}: ukończone badanie zwróciło {1}."
const BATTLE: String = "{0}: {1}. Rundy: {2}. Straty atakującego: {3}. Straty obrońcy: {4}. Zdobycz: metal {5}, kryształy {6}, paliwo {7}. "
const BATTLE_ICONS: String = "{0}: {1}. Rundy: {2}. Straty atakującego: {3}. Straty obrońcy: {4}. Zdobycz: {5}, {6}, {7}. "
const RECOVERY: String = " Recykler Wraków odzyskał {0} metalu; jest w ładowni i zostanie rozładowany po powrocie."
const RECOVERY_ICONS: String = " Recykler Wraków odzyskał {0}; jest w ładowni i zostanie rozładowany po powrocie."
const COALITION: String = "{0}: {1}. Rundy: {2}. Twoje straty: {3}; ocalałe jednostki: {4}."
const LOOT: String = "Twoja zdobycz: metal {0}, kryształy {1}, paliwo {2}; Kryształy Roju: {3}. Ładunek otrzymasz po powrocie."
const LOOT_ICONS: String = "Twoja zdobycz: {0}, {1}, {2}; Kryształy Roju: {3}. Ładunek otrzymasz po powrocie."
const SCOUT: String = "{0} — {1}. Zapasy: {2}. Flota: {3}."
const MAX_TEMPLATE_TEXT: int = 32768
static var patterns: Dictionary = {}


static func _localized(source: String, locale: String) -> String:
	if locale == "pl":
		return source
	return str(I18n._catalogs.get(locale, {}).get(source, I18n._catalogs.get("en", {}).get(source, source)))


static func _placeholders() -> RegEx:
	var result: RegEx = RegEx.new()
	result.compile("\\{([0-9]+)\\}")
	return result


static func _quote(literal: String) -> String:
	return "\\Q" + literal.replace("\\E", "\\E\\\\E\\Q") + "\\E"


static func _match(raw: String, template: String, numbers: Array, full: bool = false) -> Dictionary:
	if raw.length() > MAX_TEMPLATE_TEXT:
		return {}
	var identity: String = template + str(numbers) + str(full)
	if not patterns.has(identity):
		# PCRE work is bounded even for repetitive lookalike prose. A failed or
		# exhausted match always falls back to the unchanged report body.
		var pattern: String = "(*LIMIT_MATCH=20000)(*LIMIT_DEPTH=100)^"
		var indexes: Array[int] = []
		var offset: int = 0
		for placeholder: RegExMatch in _placeholders().search_all(template):
			pattern += _quote(template.substr(offset, placeholder.get_start() - offset))
			var index: int = int(placeholder.get_string(1))
			indexes.append(index)
			pattern += "([+-]?[0-9]{1,18}(?:[.,][0-9]{1,8})?)" if index in numbers else "([\\s\\S]*)"
			offset = placeholder.get_end()
		pattern += _quote(template.substr(offset)) + ("$" if full else "")
		var regex: RegEx = RegEx.new()
		if regex.compile(pattern) != OK:
			return {}
		patterns[identity] = {"regex": regex, "indexes": indexes}
	var spec: Dictionary = patterns[identity]
	var found: RegExMatch = spec["regex"].search(raw)
	if found == null:
		return {}
	var args: Dictionary = {}
	for group: int in range(spec["indexes"].size()):
		args[spec["indexes"][group]] = found.get_string(group + 1)
	return {"args": args, "end": found.get_end()}


static func _format(template: String, args: Dictionary) -> String:
	var result: String = ""
	var offset: int = 0
	for placeholder: RegExMatch in _placeholders().search_all(template):
		result += template.substr(offset, placeholder.get_start() - offset)
		result += str(args.get(int(placeholder.get_string(1)), placeholder.get_string()))
		offset = placeholder.get_end()
	return result + template.substr(offset)


static func _replace(raw: String, source: String, icon_source: String, numeric: Array, resources: Dictionary, locale: String, full: bool = false) -> String:
	var found: Dictionary = _match(raw, _localized(source, locale), numeric, full)
	if found.is_empty():
		return raw
	var args: Dictionary = found["args"]
	for index: int in resources:
		args[index] = Resources.token(str(resources[index])) + "\u00A0" + str(args[index])
	return _format(_localized(icon_source, locale), args) + raw.substr(int(found["end"]))


static func text(host, report: Dictionary) -> String:
	var raw: String = host._report_display_text(report)
	if raw.length() > MAX_TEMPLATE_TEXT:
		return raw
	var title: String = str(report.get("title", ""))
	for locale: String in [I18n.locale, "pl", "en", "de", "es", "fr"]:
		if title == _localized("Recykling", locale):
			var converted: String = _replace(raw, RECYCLE, RECYCLE_ICONS, [1, 2, 3], {1: "metal", 2: "crystal", 3: "fuel"}, locale, true)
			if converted != raw:
				return converted
		if title == _localized("Archiwum Synaps", locale):
			var converted: String = _replace(raw, ARCHIVE, ARCHIVE_ICONS, [1], {1: "crystal"}, locale, true)
			if converted != raw:
				return converted
		if title in [_localized("Raport bitwy", locale), _localized("Twoja kolonia została zaatakowana", locale)]:
			var found: Dictionary = _match(raw, _localized(BATTLE, locale), [2, 5, 6, 7])
			if not found.is_empty():
				var end: int = int(found["end"])
				var prefix: String = _replace(raw.substr(0, end), BATTLE, BATTLE_ICONS, [2, 5, 6, 7], {5: "metal", 6: "crystal", 7: "fuel"}, locale, true)
				return prefix + _replace(raw.substr(end), RECOVERY, RECOVERY_ICONS, [0], {0: "metal"}, locale)
		if title == _localized("Raport wspólnej bitwy", locale):
			var found: Dictionary = _match(raw, _localized(COALITION, locale), [2, 3, 4])
			if not found.is_empty():
				var end: int = int(found["end"])
				if raw.substr(end, 1) == " ":
					return raw.substr(0, end + 1) + _replace(raw.substr(end + 1), LOOT, LOOT_ICONS, [0, 1, 2, 3], {0: "metal", 1: "crystal", 2: "fuel"}, locale)
		if title == _localized("Raport zwiadu", locale) and report.get("planet_scout") is Dictionary:
			var found: Dictionary = _match(raw, _localized(SCOUT, locale), [])
			if not found.is_empty():
				var amounts: Dictionary = report["planet_scout"].get("resources", {})
				var observed: Dictionary = {}
				var expected: PackedStringArray = PackedStringArray()
				for resource: String in Resources.KEYS:
					observed[resource] = int(amounts.get(resource, 0))
					var name: String = {"metal": "metal", "crystal": "kryształy", "fuel": "paliwo"}[resource]
					expected.append(_format(_localized("{0}: {1}", locale), {0: _localized(name, locale), 1: str(int(amounts.get(resource, 0)))}))
				if str(found["args"][2]) == ", ".join(expected):
					found["args"][2] = Resources.cost(host, observed, true, true)
					return _format(_localized(SCOUT, locale), found["args"]) + raw.substr(int(found["end"]))
	return raw
