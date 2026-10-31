extends RefCounted


## Accept only a server origin. Credentials, paths and redirect targets are not configuration.
## Never include the supplied text in an error or a log message.
static func parse_input(input: String) -> Dictionary:
	var text: String = input.strip_edges()
	if input.length() > 2048 or _has_control_characters(text):
		return {"error": I18n.t("Adres serwera jest niepoprawny. Wklej adres w jednej linii.")}
	return _parse_origin(text)


static func _parse_origin(value: String) -> Dictionary:
	if value.length() > 2048 or _has_control_characters(value):
		return {"error": I18n.t("Adres serwera jest niepoprawny.")}
	var expression: RegEx = RegEx.new()
	expression.compile("^(https?)://(\\[[A-Fa-f0-9:]+\\]|[A-Za-z0-9.-]+)(?::([0-9]{1,5}))?/?$")
	var matched: RegExMatch = expression.search(value)
	if matched == null:
		return {"error": I18n.t("Wpisz adres http:// lub https://, bez ścieżki, loginu i parametrów.")}
	var scheme: String = matched.get_string(1)
	var host: String = matched.get_string(2).to_lower()
	var port: String = matched.get_string(3)
	if not port.is_empty() and (port.to_int() < 1 or port.to_int() > 65535):
		return {"error": I18n.t("Port serwera musi mieć wartość od 1 do 65535.")}
	var bare_host: String = host.trim_prefix("[").trim_suffix("]")
	if host.begins_with("["):
		if not bare_host.is_valid_ip_address():
			return {"error": I18n.t("Adres serwera jest niepoprawny.")}
	else:
		if host.length() > 253:
			return {"error": I18n.t("Nazwa serwera jest zbyt długa.")}
		for label: String in host.split("."):
			if label.is_empty() or label.length() > 63 or not _matches("^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$", label):
				return {"error": I18n.t("Nazwa serwera jest niepoprawna.")}
		if _matches("^[0-9.]+$", host) and not host.is_valid_ip_address():
			return {"error": I18n.t("Adres serwera jest niepoprawny.")}
	if scheme == "http" and not _is_local_host(bare_host):
		return {"error": I18n.t("Połączenie przez internet wymaga adresu HTTPS. Poproś gospodarza o adres serwera.")}
	return {"url": scheme + "://" + host + (":" + str(port.to_int()) if not port.is_empty() else "")}


static func _is_local_host(host: String) -> bool:
	if host == "localhost" or host.ends_with(".localhost") or host.ends_with(".local"):
		return true
	if not host.is_valid_ip_address():
		return false
	if host.contains(":"):
		# Loopback, unique-local and link-local IPv6 only. Reject public HTTP.
		var first_group: int = host.get_slice(":", 0).hex_to_int()
		return host == "::1" or (first_group & 0xfe00) == 0xfc00 or (first_group & 0xffc0) == 0xfe80
	var octets: PackedStringArray = host.split(".")
	if octets.size() != 4:
		return false
	var first: int = octets[0].to_int()
	var second: int = octets[1].to_int()
	return first == 127 or first == 10 or (first == 192 and second == 168) or (first == 172 and second >= 16 and second <= 31) or (first == 169 and second == 254)


static func _matches(pattern: String, value: String) -> bool:
	var expression: RegEx = RegEx.new()
	expression.compile(pattern)
	return expression.search(value) != null


static func _has_control_characters(value: String) -> bool:
	for index: int in range(value.length()):
		var codepoint: int = value.unicode_at(index)
		if codepoint < 32 or codepoint == 127:
			return true
	return false
