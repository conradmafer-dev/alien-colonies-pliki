extends VBoxContainer
## Read-only player: every displayed state comes from the server's saved battle.
const ResourceInfo = preload("res://client/scripts/resource_info.gd")
const BoardScript = preload("res://client/scripts/battle_board.gd")
var host
var report_id: String
var request: HTTPRequest
var origin: String
var token: String
var replay: Dictionary = {}
var frames: Array[Dictionary] = []
var round_starts: Array[int] = []
var index: int = 0
var elapsed: float = 0
var playing: bool = false
var loading: bool = false
var speed: float = 1
var stopped: bool = false
var build_generation: int = 0
var build_slice_usec: int = 0
const BUILD_BUDGET_USEC: int = 4000
var status: Label
var phase_label: Label
var detail: RichTextLabel
var board
var pause_button: Button
var skip_button: Button
var previous_button: Button
var next_button: Button
var speed_button: Button
var retry_button: Button
var playback: VBoxContainer
var round_choices: HBoxContainer
var formation_choices: Dictionary = {}
var ledger_scroll: ScrollContainer
var coalition: bool = false
# Five attacking fleets and the host plus five defending fleets, all ship types.
const MAX_SIDE_UNITS: int = 64

func setup(client: Control, report: Dictionary) -> void:
	host = client
	name = "BattleReplay"
	report_id = str(report.get("id", ""))
	origin = str(host.server_url); token = str(host.session_token)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_theme_constant_override("separation",10)
	status = host._label(I18n.t("Wczytywanie bitwy…"),24)
	add_child(status)
	retry_button = host._button(I18n.t("Spróbuj ponownie"), _load)
	retry_button.hide(); add_child(retry_button)
	request = HTTPRequest.new(); request.timeout = 15
	request.use_threads = true
	request.body_size_limit = 2*1024*1024
	request.max_redirects = 0
	request.request_completed.connect(_received)
	add_child(request)
	_load.call_deferred()

func _load() -> void:
	if stopped: return
	status.text = I18n.t("Wczytywanie bitwy…")
	status.modulate = Color.WHITE
	retry_button.hide()
	var headers: PackedStringArray = PackedStringArray(["Accept: application/json", "Accept-Language: " + I18n.locale,
		"X-PGR-Client-Version: " + str(host.CLIENT_VERSION_CODE), "Authorization: Bearer " + token])
	var error: Error = request.request(origin + "/api/battle-replay?report_id=" + report_id.uri_encode(), headers, HTTPClient.METHOD_GET)
	if error != OK: _failed()

func _failed() -> void:
	status.text = I18n.t("Nie udało się wczytać animacji. Raport tekstowy jest poniżej.")
	status.modulate = Color("ffb49c")
	retry_button.show()

func _received(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if stopped or not is_visible_in_tree() or not is_instance_valid(host): return
	if token != str(host.session_token) or origin != str(host.server_url):
		shutdown(); return
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		_failed(); return
	var parser: JSON = JSON.new()
	if parser.parse(body.get_string_from_utf8()) != OK:
		_failed(); return
	var parsed: Variant = parser.data
	if not parsed is Dictionary or not parsed.get("ok",false):
		_failed(); return
	var data: Variant = parsed.get("replay")
	if not _valid(data):
		_failed(); return
	await present(data)

func _valid(data: Variant) -> bool:
	if not data is Dictionary or int(data.get("schema",0)) != 1: return false
	if not data.get("rounds") is Array or data["rounds"].size()>6 or not data.get("final") is Dictionary or not data.get("planet") is Dictionary: return false
	for side: String in ["attacker","defender"]:
		if not data.get(side) is Dictionary or not data[side].get("units") is Array or data[side]["units"].size()>MAX_SIDE_UNITS or not data[side].get("initial") is Dictionary: return false
		if data[side].has("participants") and (not data[side]["participants"] is Array or data[side]["participants"].size() > 6): return false
		var keys: Dictionary = {}
		for unit: Variant in data[side]["units"]:
			if not unit is Dictionary or not unit.get("key") is String or not unit.get("art_key") is String or not unit.get("name") is String or float(unit.get("hull",0)) <= 0: return false
			if keys.has(unit["key"]): return false
			keys[unit["key"]] = true
			if not _valid_state(data[side]["initial"],unit["key"]) or not _valid_state(data["final"].get(side,{}),unit["key"]): return false
	for r: Variant in data["rounds"]:
		if not r is Dictionary or not r.get("salvos") is Dictionary: return false
		for side: String in ["attacker","defender"]:
			for field: String in ["before","after_damage","after"]:
				if not r.get(field) is Dictionary or not r[field].get(side) is Dictionary: return false
				for unit: Dictionary in data[side]["units"]:
					if not _valid_state(r[field][side],unit["key"]): return false
			for field: String in ["hits","heals"]:
				if not r.get(field) is Dictionary or not r[field].get(side) is Array or r[field][side].size()>MAX_SIDE_UNITS: return false
				for event: Variant in r[field][side]:
					if not event is Dictionary or not data[side]["initial"].has(event.get("key","")): return false
					if not _valid_state({event["key"]:event.get("after")},event["key"]): return false
	if data.has("participant_results") and (not data["participant_results"] is Array or data["participant_results"].size() > 12): return false
	return true

func _valid_state(values: Variant, key: String) -> bool:
	return values is Dictionary and values.get(key) is Dictionary and float(values[key].get("count",-1))>=0 and float(values[key].get("wounds",-1))>=0

func present(data: Dictionary) -> void:
	build_generation += 1
	var generation: int = build_generation
	stopped = false; playing = false; loading = true
	# The saved replay and its leaf states are read-only throughout playback.
	replay = data
	if is_instance_valid(playback):
		remove_child(playback); playback.queue_free()
	playback = VBoxContainer.new(); playback.add_theme_constant_override("separation",10)
	add_child(playback)
	playback.hide()
	var controls: HBoxContainer = HBoxContainer.new(); controls.add_theme_constant_override("separation",8)
	playback.add_child(controls)
	pause_button = _control(controls,I18n.t("Pauza"),toggle_pause)
	speed_button = _control(controls,"1×",toggle_speed)
	skip_button = _control(controls,I18n.t("Pomiń"),skip)
	var navigation: HBoxContainer = HBoxContainer.new(); navigation.add_theme_constant_override("separation",6)
	playback.add_child(navigation)
	previous_button = _control(navigation,"‹",previous_round)
	previous_button.size_flags_horizontal = Control.SIZE_FILL; previous_button.custom_minimum_size.x = 54
	round_choices = HBoxContainer.new(); round_choices.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	round_choices.add_theme_constant_override("separation",4); navigation.add_child(round_choices)
	for i: int in range(replay["rounds"].size()):
		var button: Button = _control(round_choices,str(i+1),seek_round.bind(i))
		button.tooltip_text = I18n.t("Runda %d") % (i+1)
	next_button = _control(navigation,"›",next_round)
	next_button.size_flags_horizontal = Control.SIZE_FILL; next_button.custom_minimum_size.x = 54
	phase_label = host._label("",22); phase_label.custom_minimum_size.y = 56
	playback.add_child(phase_label)
	board = BoardScript.new(); board.configure(replay)
	coalition = board.coalition or replay.has("participant_results")
	formation_choices.clear()
	ledger_scroll = null
	if coalition:
		for side: String in ["defender", "attacker"]:
			if board.formations[side].size() <= 1: continue
			var row: HBoxContainer = HBoxContainer.new(); row.add_theme_constant_override("separation",8)
			playback.add_child(row)
			var side_label: Label = host._label(_team(side),20); side_label.custom_minimum_size.x = 128
			row.add_child(side_label)
			var choices: OptionButton = OptionButton.new()
			choices.custom_minimum_size.y = 56
			choices.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			choices.add_theme_font_size_override("font_size",22)
			choices.fit_to_longest_item = false; choices.clip_text = true
			for group: Dictionary in board.formations[side]: choices.add_item(str(group["name"]))
			choices.item_selected.connect(_choose_formation.bind(side))
			row.add_child(choices); formation_choices[side] = choices
		playback.add_child(host._label(I18n.t("Floty zmieniają się automatycznie przy trafieniach. Wybór floty wstrzymuje odtwarzanie."),18))
	playback.add_child(board)
	detail = ResourceInfo.label(host,"",22)
	if coalition:
		ledger_scroll = ScrollContainer.new()
		ledger_scroll.custom_minimum_size.y = 220
		ledger_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		ledger_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		ledger_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
		playback.add_child(ledger_scroll); ledger_scroll.add_child(detail)
		detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		detail.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	else: playback.add_child(detail)
	build_slice_usec = Time.get_ticks_usec()
	if not await _make_frames(generation): return
	if stopped or generation != build_generation: return
	loading = false
	playback.show()
	index = 0; elapsed = 0; playing = true; stopped = false
	_show()
	set_process(true)

func _choose_formation(value: int, side: String) -> void:
	if stopped or loading: return
	playing = false
	board.select_formation(side,value)
	_show(false)

func _scroll_ledger_to_latest() -> void:
	if is_instance_valid(ledger_scroll) and playing:
		ledger_scroll.scroll_vertical = int(ledger_scroll.get_v_scroll_bar().max_value)

func _control(parent: Control, title: String, action: Callable) -> Button:
	var button: Button = host._button(title,action)
	button.custom_minimum_size.y = 56
	button.add_theme_font_size_override("font_size",22)
	parent.add_child(button)
	return button

func _team(side: String) -> String:
	return I18n.t("Atakujący") if side == "attacker" else I18n.t("Obrońca")

func _unit(side: String, key: String) -> String:
	for unit: Dictionary in replay[side]["units"]:
		if unit["key"] == key: return str(unit["name"])
	return key

func _n(value: float) -> String:
	if value == floorf(value): return str(int(value))
	if value > 0 and value < .01: return "<" + I18n.decimal("0.01")
	return I18n.decimal(String.num(value,2))


func _snapshot(state: Dictionary) -> Dictionary:
	# Recorded unit states are immutable. Only the two unit-key maps change as
	# events advance; copy those maps, not every count/wounds dictionary for
	# every animation frame (over 100,000 allocations in a full coalition).
	return {"attacker":state["attacker"].duplicate(), "defender":state["defender"].duplicate()}

func _push(kind: String, round_index: int, state: Dictionary, title: String, text: String, duration: float, events: Dictionary = {}) -> void:
	frames.append({"kind":kind,"round":round_index,"state":_snapshot(state),"title":title,"text":text,"duration":duration,"events":events,"arena_text":title})

func _build_checkpoint(generation: int) -> bool:
	if generation < 0: return true # Standalone deterministic profiling.
	if stopped or generation != build_generation: return false
	if Time.get_ticks_usec() - build_slice_usec < BUILD_BUDGET_USEC: return true
	await get_tree().process_frame
	build_slice_usec = Time.get_ticks_usec()
	return not stopped and generation == build_generation

func _push_log(kind: String, round_index: int, state: Dictionary, title: String, lines: Array[String], duration: float, events: Dictionary = {}) -> void:
	_push(kind, round_index, state, title, "", duration, events)
	# Each round owns one ledger. Frames retain only the reached line count;
	# copying every growing text prefix otherwise costs tens of MB per report.
	frames[-1]["log_lines"] = lines
	frames[-1]["log_count"] = lines.size()

func _make_frames(generation: int = -1) -> bool:
	frames.clear(); round_starts.clear()
	var intro: String = I18n.t("Obie strony strzelają jednocześnie. Potem zniszczenia, na końcu regeneracja.")
	if replay.get("damage_rule", "") == "proportional_effective_hull":
		intro += "\n" + I18n.t("Obrażenia rozdzielają się między floty według ich wytrzymałości. Najpierw uszkadzane są słabsze jednostki każdej floty.")
	_push("intro",-1,{"attacker":replay["attacker"]["initial"],"defender":replay["defender"]["initial"]},I18n.t("Przed bitwą"),intro,.8)
	for ri: int in range(replay["rounds"].size()):
		var r: Dictionary = replay["rounds"][ri]
		round_starts.append(frames.size())
		var log_lines: Array[String] = [I18n.t("Siła salwy · atakujący: %s · obrońca: %s") % [_n(float(r["salvos"]["attacker"])),_n(float(r["salvos"]["defender"]))]]
		if coalition:
			for side: String in ["attacker", "defender"]:
				for participant: Dictionary in replay[side].get("participants", []):
					var formation_id: String = str(participant.get("formation_id", ""))
					var power: float = float(r.get("formation_salvos", {}).get(side, {}).get(formation_id, 0))
					if r.get("formation_salvos", {}).get(side, {}).has(formation_id):
						log_lines.append(I18n.t("Salwa floty %s: %s.") % [str(participant.get("owner_name", "")), _n(power)])
		var firing_formations: Dictionary = {}
		for side: String in ["attacker", "defender"]:
			firing_formations[side] = []
			for group: Dictionary in board.formations[side]:
				var alive: bool = false
				for unit: Dictionary in group["units"]:
					alive = alive or int(r["before"][side][unit["key"]]["count"]) > 0
				if alive: firing_formations[side].append(group)
			if firing_formations[side].is_empty(): firing_formations[side].append(board.formations[side][0])
		var overview_count: int = maxi(firing_formations["attacker"].size(), firing_formations["defender"].size()) if coalition else 1
		for formation_index: int in range(overview_count):
			_push_log("fire",ri,r["before"],I18n.t("Jednoczesne salwy"),log_lines,.6 if coalition else .8)
			if coalition:
				var focus: Dictionary = {}
				for side: String in ["attacker", "defender"]:
					var group: Dictionary = firing_formations[side][mini(formation_index, firing_formations[side].size()-1)]
					if not group["units"].is_empty(): focus[side] = group["units"][0]["key"]
				frames[-1]["focus"] = focus
				frames[-1]["arena_text"] = I18n.t("Przegląd salw · %d / %d") % [formation_index+1, overview_count]
		var state: Dictionary = _snapshot(r["before"])
		var hit_count: int = maxi(r["hits"]["attacker"].size(),r["hits"]["defender"].size())
		for i: int in range(hit_count):
			var events: Dictionary = {}
			for side: String in ["attacker","defender"]:
				if i >= r["hits"][side].size(): continue
				var hit: Dictionary = r["hits"][side][i]; events[side] = hit
				state[side][hit["key"]] = hit["after"]
				log_lines.append(I18n.t("%s · %s: −%s HP, zniszczono %d, pozostało %d.") % [_team(side),_unit(side,hit["key"]),_n(float(hit["damage"])),int(hit["destroyed"]),int(hit["after"]["count"])])
				if float(hit.get("blocked",0)) > .001:
					log_lines[-1] += " " + I18n.t("Pancerz pochłonął %s.") % _n(float(hit["blocked"]))
			_push_log("impact",ri,state,I18n.t("Trafienia i zniszczenia"),log_lines,.8,events)
			if not await _build_checkpoint(generation): return false
		state = _snapshot(r["after_damage"])
		var heal_count: int = maxi(r["heals"]["attacker"].size(),r["heals"]["defender"].size())
		for i: int in range(heal_count):
			var events: Dictionary = {}
			for side: String in ["attacker","defender"]:
				if i >= r["heals"][side].size(): continue
				var heal: Dictionary = r["heals"][side][i]; events[side] = heal
				state[side][heal["key"]] = heal["after"]
				log_lines.append(I18n.t("%s · %s: regeneracja +%s HP.") % [_team(side),_unit(side,heal["key"]),_n(float(heal["healed"]))])
			_push_log("heal",ri,state,I18n.t("Regeneracja ocalałych"),log_lines,.9,events)
			if not await _build_checkpoint(generation): return false
		if heal_count == 0: log_lines.append(I18n.t("Brak regeneracji w tej rundzie."))
		_push_log("round_end",ri,r["after"],I18n.t("Koniec rundy"),log_lines,1.15)
		if not await _build_checkpoint(generation): return false
	var result: String = I18n.t("Odwrót · bitwa nierozstrzygnięta")
	if replay["outcome"] == "attacker_wins": result = I18n.t("Zwycięstwo atakującego")
	elif replay["outcome"] == "attacker_destroyed": result = I18n.t("Flota atakująca zniszczona")
	var summary: String = ""
	if not replay.get("participant_results", []).is_empty():
		for participant: Dictionary in replay["participant_results"]:
			var side: String = str(participant["side"])
			var formation_id: String = str(participant["formation_id"])
			summary += _team(side) + " · " + str(participant["owner_name"]) + "\n"
			for unit: Dictionary in replay[side]["units"]:
				if str(unit.get("formation_id", "")) != formation_id: continue
				var key: String = str(unit.get("unit_key", unit["key"]))
				summary += I18n.t("%s · straty %d · ocalało %d") % [str(unit.get("unit_name", unit["name"])), int(participant.get("losses", {}).get(key,0)), int(participant.get("survivors", {}).get(key,0))] + "\n"
			var cargo: Dictionary = participant.get("cargo", {})
			if side == "attacker":
				summary += I18n.t("Łupy: %s") % ResourceInfo.cost(host,cargo,true,true) + "\n"
			if int(participant.get("swarm_crystals",0)) > 0:
				summary += I18n.t("Kryształy Roju: %d.") % int(participant["swarm_crystals"]) + "\n"
			if float(participant.get("recovered_metal",0)) > 0:
				summary += I18n.t("Odzyskano: %s") % ResourceInfo.cost(host,{"metal":participant["recovered_metal"]}) + "\n"
			summary += "\n"
	else:
		for side: String in ["attacker","defender"]:
			summary += _team(side) + "\n"
			for unit: Dictionary in replay[side]["units"]:
				var key: String = unit["key"]
				summary += I18n.t("%s · straty %d · ocalało %d") % [str(unit["name"]),int(replay[side]["losses"].get(key,0)),int(replay["final"][side][key]["count"])] + "\n"
	_push("result",replay["rounds"].size(),replay["final"],result,summary,0)
	return true

func _process(delta: float) -> void:
	if stopped or frames.is_empty() or not playing or not is_visible_in_tree(): return
	elapsed += minf(delta,.15) * speed
	if elapsed >= float(frames[index]["duration"]):
		index = mini(index+1,frames.size()-1); elapsed = 0
		_show()
	if playing:
		board.show_frame(frames[index],elapsed/maxf(.01,float(frames[index]["duration"])))

func _show(focus_events: bool = true) -> void:
	if stopped or frames.is_empty(): return
	var frame: Dictionary = frames[index]
	var ri: int = int(frame["round"])
	status.text = I18n.t("Runda %d / %d") % [ri+1,replay["rounds"].size()] if ri >= 0 and ri < replay["rounds"].size() else I18n.t("Wynik bitwy") if frame["kind"] == "result" else I18n.t("Rozmieszczenie flot")
	phase_label.text = str(frame["title"])
	var text: String = str(frame["text"])
	if frame.has("log_lines"):
		text = "\n".join(frame["log_lines"].slice(0, int(frame["log_count"])))
	ResourceInfo.set_text(detail,host,text)
	if focus_events: board.focus_frame(frame)
	for side: String in formation_choices: formation_choices[side].select(board.selected[side])
	board.show_frame(frame,0)
	if focus_events and is_instance_valid(ledger_scroll):
		if playing: _scroll_ledger_to_latest.call_deferred()
		else: ledger_scroll.scroll_vertical = 0
	if frame["kind"] == "result": playing = false
	pause_button.text = I18n.t("Odtwórz ponownie") if frame["kind"] == "result" else I18n.t("Pauza") if playing else I18n.t("Wznów")
	previous_button.disabled = round_starts.is_empty() or ri < 0
	next_button.disabled = frame["kind"] == "result"
	skip_button.disabled = frame["kind"] == "result"
	for i: int in range(round_choices.get_child_count()):
		var button: Button = round_choices.get_child(i)
		button.modulate = Color("8cdbff") if ri == i else Color.WHITE

func toggle_pause() -> void:
	if stopped or loading or frames.is_empty(): return
	if frames[index]["kind"] == "result":
		index = 0; elapsed = 0; playing = true
	else: playing = not playing
	_show(false)

func toggle_speed() -> void:
	if stopped or loading: return
	speed = 2.0 if speed == 1.0 else 1.0
	speed_button.text = "2×" if speed == 2.0 else "1×"

func seek_round(ri: int) -> void:
	if stopped or loading: return
	if ri < 0 or ri >= round_starts.size(): return
	# Jump to the completed round for immediate, inspectable results and log.
	index = (round_starts[ri+1]-1) if ri+1 < round_starts.size() else frames.size()-2
	elapsed = 0; playing = false; _show()

func previous_round() -> void:
	if stopped or loading or frames.is_empty(): return
	seek_round(maxi(0,int(frames[index]["round"])-1))

func next_round() -> void:
	if stopped or loading or frames.is_empty(): return
	var ri: int = int(frames[index]["round"])+1
	if ri >= round_starts.size(): skip()
	else: seek_round(ri)

func skip() -> void:
	if stopped or loading or frames.is_empty(): return
	index = frames.size()-1; elapsed = 0; playing = false; _show()

func shutdown() -> void:
	build_generation += 1
	stopped = true; playing = false; loading = false; set_process(false)
	if is_instance_valid(board): board.shutdown()
	frames.clear(); round_starts.clear()
	# Drop our reference without clearing the caller's immutable Dictionary.
	replay = {}
	if is_instance_valid(request): request.cancel_request()

func _exit_tree() -> void:
	shutdown()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_PAUSED and playing:
		playing = false
		if not frames.is_empty(): _show()
