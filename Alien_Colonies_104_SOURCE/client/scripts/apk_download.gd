extends Node

## A separate, unauthenticated download channel. The release identity belongs to
## one game origin; changing that identity invalidates both requests and files.
const Policy = preload("res://client/scripts/update_policy.gd")
const UPDATE_DIR: String = "user://updates"
const PART_PATH: String = "user://updates/pogranicze.part"
const APK_PATH: String = "user://updates/pogranicze.apk"
const MAX_REDIRECTS: int = 5
const TIMEOUT_SECONDS: float = 300.0
const HASH_CHUNK_BYTES: int = 262144

signal changed

var phase: String = "idle"
var message: String = ""
var downloaded_bytes: int = 0
var expected_bytes: int = 0
var snapshot: String = ""
var _release: Dictionary = {}
var _http: HTTPRequest
var _generation: int = 0
var _current_url: String = ""
var _redirects: int = 0
var _started_msec: int = 0
var _verify_file: FileAccess
var _hasher: HashingContext
var _hashed_bytes: int = 0
var _progress_elapsed: float = 0.0


static func fingerprint(origin: String, manifest: Dictionary) -> String:
	var link: String = Policy.public_download_url(manifest.get("download_url", ""))
	var digest: String = Policy.valid_apk_sha256(manifest.get("apk_sha256", ""))
	var size: int = Policy.valid_apk_size(manifest.get("apk_size_bytes", 0))
	if origin.is_empty() or link.is_empty() or digest.is_empty() or size == 0:
		return ""
	return JSON.stringify([origin, manifest.get("latest_version_code", 0), link, digest, size])


## Relative redirects are restricted to a root-relative path or query on the
## same HTTPS origin. An ambiguous path is rejected, never silently normalized.
static func redirect_target(current_url: String, location: String) -> String:
	if location.begins_with("https://"):
		return Policy.public_download_url(location)
	if location.begins_with("//"):
		return Policy.public_download_url("https:" + location)
	if not location.begins_with("/") and not location.begins_with("?"):
		return ""
	var expression: RegEx = RegEx.new()
	expression.compile("^(https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?)([^?]*)")
	var base: RegExMatch = expression.search(current_url)
	if base == null:
		return ""
	var target: String = base.get_string(1) + location
	if location.begins_with("?"):
		var path: String = base.get_string(2)
		target = base.get_string(1) + ("/" if path.is_empty() else path) + location
	return Policy.public_download_url(target)


func _ready() -> void:
	# No persisted auto-resume or automatic installation. Old files may belong to
	# a different account/server or the installed release itself.
	_remove_file(PART_PATH)
	_remove_file(APK_PATH)


func begin(origin: String, manifest: Dictionary) -> void:
	var identity: String = fingerprint(origin, manifest)
	if identity.is_empty():
		message = I18n.t("Plik aktualizacji nie jest jeszcze dostępny. Sprawdź ponownie.")
		changed.emit()
		return
	clear()
	snapshot = identity
	_release = manifest.duplicate(true)
	expected_bytes = Policy.valid_apk_size(_release.get("apk_size_bytes", 0))
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(UPDATE_DIR)) != OK:
		_fail(I18n.t("Nie można zapisać aktualizacji. Sprawdź wolne miejsce w telefonie."))
		return
	phase = "downloading"
	message = I18n.t("Łączenie z pobieraniem…")
	_redirects = 0
	_started_msec = Time.get_ticks_msec()
	_request_url(str(_release["download_url"]))
	changed.emit()


func reconcile(origin: String, manifest: Dictionary) -> void:
	if not snapshot.is_empty() and snapshot != fingerprint(origin, manifest):
		clear()
		message = I18n.t("Dostępna wersja zmieniła się. Pobierz aktualny plik.")
		changed.emit()


func ready_path(origin: String, manifest: Dictionary) -> String:
	if phase != "ready" or snapshot.is_empty() or snapshot != fingerprint(origin, manifest):
		return ""
	var file: FileAccess = FileAccess.open(APK_PATH, FileAccess.READ)
	if file == null:
		return ""
	var valid_size: bool = file.get_length() == expected_bytes
	file.close()
	return APK_PATH if valid_size else ""


func cancel() -> void:
	if phase != "downloading" and phase != "verifying":
		return
	clear()
	message = I18n.t("Pobieranie anulowane. Możesz rozpocząć je ponownie.")
	changed.emit()


func clear() -> void:
	_generation += 1
	_release_request()
	_close_verification()
	_remove_file(PART_PATH)
	_remove_file(APK_PATH)
	phase = "idle"
	message = ""
	downloaded_bytes = 0
	expected_bytes = 0
	snapshot = ""
	_release.clear()
	changed.emit()


func _exit_tree() -> void:
	_generation += 1
	_release_request()
	_close_verification()
	_remove_file(PART_PATH)
	# Android's installer may still be reading the verified file after the game
	# closes. Keep it until the next launch, when _ready removes stale downloads.


func _process(delta: float) -> void:
	if phase == "downloading" and is_instance_valid(_http):
		downloaded_bytes = _http.get_downloaded_bytes()
		if downloaded_bytes > expected_bytes:
			_fail(I18n.t("Pobrany plik ma nieprawidłowy rozmiar. Sprawdź aktualizację ponownie."))
			return
		if Time.get_ticks_msec() - _started_msec > int(TIMEOUT_SECONDS * 1000.0):
			_fail(I18n.t("Pobieranie trwało zbyt długo. Sprawdź internet i spróbuj ponownie."))
			return
		_progress_elapsed += delta
		if _progress_elapsed >= 0.15:
			_progress_elapsed = 0.0
			changed.emit()
	elif phase == "verifying":
		_hash_next_chunks()


func _request_url(url: String) -> void:
	var checked_url: String = Policy.public_download_url(url)
	if checked_url.is_empty():
		_fail(I18n.t("Serwer pobierania podał niepoprawny adres. Sprawdź aktualizację ponownie."))
		return
	_release_request()
	_remove_file(PART_PATH)
	_current_url = checked_url
	_generation += 1
	_http = HTTPRequest.new()
	_http.max_redirects = 0
	_http.accept_gzip = false
	_http.body_size_limit = expected_bytes
	_http.download_chunk_size = 65536
	_http.download_file = PART_PATH
	_http.timeout = TIMEOUT_SECONDS
	_http.use_threads = true
	add_child(_http)
	_http.request_completed.connect(_on_response.bind(_generation))
	# Never copy game headers, a bearer token, cookies or API credentials here.
	var headers: PackedStringArray = PackedStringArray(["Accept: application/vnd.android.package-archive, application/octet-stream", "Accept-Encoding: identity"])
	if _http.request(checked_url, headers, HTTPClient.METHOD_GET) != OK:
		_fail(I18n.t("Nie udało się rozpocząć pobierania. Sprawdź internet i spróbuj ponownie."))


func _on_response(result: int, response_code: int, headers: PackedStringArray, _body: PackedByteArray, generation: int) -> void:
	if generation != _generation or phase != "downloading":
		return
	_release_request()
	if response_code in [301, 302, 303, 307, 308] and result in [HTTPRequest.RESULT_SUCCESS, HTTPRequest.RESULT_REDIRECT_LIMIT_REACHED]:
		var location: String = ""
		var location_count: int = 0
		for header: String in headers:
			var colon: int = header.find(":")
			if colon > 0 and header.substr(0, colon).to_lower() == "location":
				location_count += 1
				location = header.substr(colon + 1).strip_edges()
		var target: String = redirect_target(_current_url, location)
		if location_count != 1 or target.is_empty() or _redirects >= MAX_REDIRECTS:
			_fail(I18n.t("Nie można pobrać pliku z tego przekierowania. Sprawdź aktualizację ponownie."))
			return
		_redirects += 1
		_request_url(target)
		return
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		if result in [HTTPRequest.RESULT_DOWNLOAD_FILE_CANT_OPEN, HTTPRequest.RESULT_DOWNLOAD_FILE_WRITE_ERROR]:
			_fail(I18n.t("Nie można zapisać aktualizacji. Sprawdź wolne miejsce w telefonie."))
		else:
			_fail(I18n.t("Pobieranie nie powiodło się. Sprawdź internet i spróbuj ponownie."))
		return
	for header: String in headers:
		if header.to_lower().begins_with("content-encoding:") and header.get_slice(":", 1).strip_edges().to_lower() != "identity":
			_fail(I18n.t("Serwer zwrócił nieprawidłowy plik. Sprawdź aktualizację ponownie."))
			return
	_verify_file = FileAccess.open(PART_PATH, FileAccess.READ)
	if _verify_file == null or _verify_file.get_length() != expected_bytes:
		_fail(I18n.t("Pobrany plik jest niekompletny. Pobierz aktualizację ponownie."))
		return
	_hasher = HashingContext.new()
	if _hasher.start(HashingContext.HASH_SHA256) != OK:
		_fail(I18n.t("Nie udało się sprawdzić pliku. Pobierz aktualizację ponownie."))
		return
	_hashed_bytes = 0
	downloaded_bytes = expected_bytes
	phase = "verifying"
	message = I18n.t("Sprawdzanie pobranego pliku…")
	changed.emit()


func _hash_next_chunks() -> void:
	# At most 1 MiB per frame: the cancel button and UI remain responsive.
	for chunk_index: int in range(4):
		if _verify_file == null or _hasher == null:
			_fail(I18n.t("Nie udało się sprawdzić pliku. Pobierz aktualizację ponownie."))
			return
		var remaining: int = expected_bytes - _hashed_bytes
		if remaining <= 0:
			_finish_verification()
			return
		var count: int = mini(HASH_CHUNK_BYTES, remaining)
		var bytes: PackedByteArray = _verify_file.get_buffer(count)
		if bytes.size() != count or _hasher.update(bytes) != OK:
			_fail(I18n.t("Nie można odczytać pobranego pliku. Pobierz aktualizację ponownie."))
			return
		_hashed_bytes += count


func _finish_verification() -> void:
	var digest: String = _hasher.finish().hex_encode()
	_close_verification()
	if digest != Policy.valid_apk_sha256(_release.get("apk_sha256", "")):
		_fail(I18n.t("Pobrany plik nie zgadza się z aktualizacją. Pobierz go ponownie."))
		return
	var archive: ZIPReader = ZIPReader.new()
	if archive.open(PART_PATH) != OK:
		_fail(I18n.t("Pobrany plik nie jest instalatorem gry. Sprawdź aktualizację ponownie."))
		return
	var has_manifest: bool = archive.file_exists("AndroidManifest.xml")
	archive.close()
	if not has_manifest:
		_fail(I18n.t("Pobrany plik nie jest instalatorem gry. Sprawdź aktualizację ponownie."))
		return
	_remove_file(APK_PATH)
	if DirAccess.rename_absolute(ProjectSettings.globalize_path(PART_PATH), ProjectSettings.globalize_path(APK_PATH)) != OK:
		_fail(I18n.t("Nie można zapisać aktualizacji. Sprawdź wolne miejsce w telefonie."))
		return
	phase = "ready"
	message = I18n.t("Aktualizacja pobrana. Możesz ją zainstalować.")
	changed.emit()


func _release_request() -> void:
	if is_instance_valid(_http):
		_http.cancel_request()
		_http.queue_free()
	_http = null


func _close_verification() -> void:
	if _verify_file != null:
		_verify_file.close()
	_verify_file = null
	_hasher = null


func _fail(reason: String) -> void:
	_generation += 1
	_release_request()
	_close_verification()
	_remove_file(PART_PATH)
	_remove_file(APK_PATH)
	phase = "error"
	message = reason
	changed.emit()


func _remove_file(path: String) -> void:
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
