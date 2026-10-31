extends Control
## Bounded 2D presentation of recorded states: one card per unit type.
const ArtLoader = preload("res://client/scripts/replay_art_loader.gd")
const Art = preload("res://client/scripts/art_library.gd")
const COLORS: Dictionary = {"zetans": Color("73caff"), "automatons": Color("ff8475"), "symbionts": Color("92eb96"), "swarm": Color("dbcf70"), "": Color("c9dbea")}
var replay: Dictionary = {}
var frame: Dictionary = {}
var progress: float = 0.0
var cards: Dictionary = {}
var textures: Dictionary = {}
var texture_keys: Dictionary = {}
var art_loader: Node
var fitted_cache: Dictionary = {}
var font: Font
# Each page holds one owner's formation, keeping even large allied battles bounded.
# The complete state is retained: only the presentation is paged.
var formations: Dictionary = {"attacker": [], "defender": []}
var selected: Dictionary = {"attacker": 0, "defender": 0}
var side_rows: Dictionary = {"attacker": 1, "defender": 1}
var unit_formations: Dictionary = {"attacker": {}, "defender": {}}
var coalition: bool = false
const FORMATION_PAGE_SIZE: int = 9

func _owner(unit: Dictionary, side: String) -> String:
	return str(unit.get("owner_id", unit.get("owner", replay[side].get("owner_id", ""))))

func unit_race(side: String, unit: Dictionary = {}) -> String:
	return str(unit.get("race", unit.get("race_id", replay[side].get("race", ""))))

func _formation_name(side: String, unit: Dictionary) -> String:
	var owner: String = _owner(unit, side)
	for participant: Dictionary in replay[side].get("participants", []):
		if str(participant.get("formation_id", participant.get("owner_id", ""))) == str(unit.get("formation_id", owner)):
			return str(participant.get("owner_name", participant.get("name", owner)))
	return str(unit.get("owner_name", replay[side].get("name", owner)))

func _make_formations(side: String) -> void:
	formations[side] = []; unit_formations[side] = {}; selected[side] = 0
	var grouped: Dictionary = {}
	for unit: Dictionary in replay[side]["units"]:
		var formation_id: String = str(unit.get("formation_id", _owner(unit, side)))
		if not grouped.has(formation_id): grouped[formation_id] = []
		grouped[formation_id].append(unit)
	# Historical solo battles preserve their original layout.
	var page_size: int = FORMATION_PAGE_SIZE if grouped.size() > 1 or replay[side]["units"].size() > 12 else 12
	for owner: String in grouped:
		var units: Array = grouped[owner]
		for offset: int in range(0, units.size(), page_size):
			var page: Array = units.slice(offset, mini(offset + page_size, units.size()))
			var title: String = _formation_name(side, page[0])
			if units.size() > page_size: title += " · " + str(offset / page_size + 1)
			var group: Dictionary = {"owner_id": _owner(page[0], side), "formation_id": owner, "name": title, "race": unit_race(side, page[0]), "units": page}
			for unit: Dictionary in page: unit_formations[side][unit["key"]] = formations[side].size()
			formations[side].append(group)
	if formations[side].is_empty():
		formations[side].append({"owner_id": "", "name": replay[side].get("name", ""), "race": replay[side].get("race", ""), "units": []})
	side_rows[side] = 1
	for group: Dictionary in formations[side]:
		side_rows[side] = maxi(side_rows[side], ceili(group["units"].size() / 3.0))
	coalition = coalition or formations[side].size() > 1

func visible_units(side: String) -> Array:
	return formations[side][selected[side]]["units"]

func select_formation(side: String, value: int) -> void:
	selected[side] = clampi(value, 0, formations[side].size()-1)
	_request_visible_art()
	queue_redraw()

func focus_frame(next: Dictionary) -> void:
	for side: String in ["attacker", "defender"]:
		var key: String = str(next.get("events", {}).get(side, {}).get("key", next.get("focus", {}).get(side, "")))
		if unit_formations[side].has(key): selected[side] = unit_formations[side][key]
	_request_visible_art()

func configure(record: Dictionary) -> void:
	replay = record
	font = ThemeDB.fallback_font
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	coalition = false
	textures.clear(); texture_keys.clear(); cards.clear()
	var rows: int = 0
	for side: String in ["defender", "attacker"]:
		_make_formations(side)
		rows += side_rows[side]
		for unit: Dictionary in record[side]["units"]:
			var slot: String = side + ":" + str(unit["key"])
			texture_keys[slot] = Art.normalized_key(Art.catalog_art_key(unit, str(unit.get("unit_key", unit.get("key", ""))), unit_race(side, unit)))
			textures[slot] = Art.textures.get(texture_keys[slot])
	texture_keys["planet"] = Art.normalized_key(str(record["planet"]["art_key"]))
	textures["planet"] = Art.textures.get(texture_keys["planet"])
	custom_minimum_size.y = 100.0 + rows * 112.0
	if not resized.is_connected(queue_redraw): resized.connect(queue_redraw)

func _ready() -> void:
	art_loader = ArtLoader.new()
	art_loader.configure(self)
	get_tree().root.add_child.call_deferred(art_loader)
	_request_visible_art()

func _request_visible_art() -> void:
	if not is_instance_valid(art_loader): return
	var keys: Array[String] = []
	for side: String in ["defender", "attacker"]:
		for unit: Dictionary in visible_units(side):
			keys.append(texture_keys[side + ":" + str(unit["key"])])
	keys.append(texture_keys["planet"])
	art_loader.request_keys(keys)

func accept_texture(key: String, texture: Texture2D) -> void:
	for slot: String in texture_keys:
		if texture_keys[slot] == key: textures[slot] = texture
	queue_redraw()

func shutdown() -> void:
	if is_instance_valid(art_loader): art_loader.cancel()
	art_loader = null
	frame = {}; replay = {}; textures.clear(); texture_keys.clear()

func _exit_tree() -> void:
	shutdown()

func color_for(side: String, unit: Dictionary = {}) -> Color:
	return COLORS.get(unit_race(side, unit), COLORS[""])

func show_frame(next: Dictionary, elapsed: float) -> void:
	frame = next
	progress = clampf(elapsed, 0, 1)
	queue_redraw()

func number(value: float) -> String:
	if value == floorf(value): return str(int(value))
	if value > 0 and value < .01: return "<" + I18n.decimal("0.01")
	return I18n.decimal(String.num(value,2))


func fitted_text(value: String, width: float, font_size: int) -> String:
	if width <= 0: return ""
	var key: String = str(font_size) + ":" + str(width) + ":" + value
	if fitted_cache.has(key): return fitted_cache[key]
	var fitted: String = value
	if font.get_string_size(value, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x > width:
		var low: int = 0
		var high: int = value.length()
		while low < high:
			var middle: int = (low + high + 1) / 2
			if font.get_string_size(value.left(middle) + "…", HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x <= width:
				low = middle
			else: high = middle - 1
		fitted = value.left(low) + "…" if font.get_string_size("…", HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x <= width else ""
	# Counts change during a replay; keep the cache bounded across all rounds.
	if fitted_cache.size() >= 256: fitted_cache.clear()
	fitted_cache[key] = fitted
	return fitted

func _text(value: String, at: Vector2, width: float, font_size: int, color: Color, centered: bool = false) -> void:
	draw_string(font, at, fitted_text(value, width, font_size), HORIZONTAL_ALIGNMENT_CENTER if centered else HORIZONTAL_ALIGNMENT_LEFT, width, font_size, color)

func _draw() -> void:
	if replay.is_empty() or frame.is_empty() or size.x < 20: return
	cards.clear()
	draw_style_box(_box(Color("08111e"), Color("2b4057"), 14), Rect2(Vector2.ZERO, size))
	for i: int in range(47):
		var star: Vector2 = Vector2(fmod(i * 107.3 + 29, size.x), fmod(i * 73.7 + 12, size.y))
		draw_circle(star, 1.1 if i % 5 == 0 else .6, Color(.6,.75,1,.28))
	var planet: Texture2D = textures.get("planet")
	if planet != null:
		draw_texture_rect(planet, Rect2(size.x - 162, 8, 148, 148), false, Color(1,1,1,.13))
	var top_rows: int = side_rows["defender"]
	var center_y: float = 40 + top_rows * 112 + 13
	for side: String in ["defender", "attacker"]:
		var top: float = 36 if side == "defender" else center_y + 49
		var heading: String = I18n.t("Obrońca") if side == "defender" else I18n.t("Atakujący")
		var formation: Dictionary = formations[side][selected[side]]
		var name_text: String = I18n.t("Rój Khar") if formation["race"] == "swarm" else str(formation["name"])
		if formations[side].size() > 1: name_text += " · %d/%d" % [selected[side]+1, formations[side].size()]
		_text(heading + " · " + name_text, Vector2(14, top - 11), size.x - 28, 19, COLORS.get(str(formation["race"]), COLORS[""]))
		var units: Array = visible_units(side)
		if units.is_empty():
			_text(I18n.t("Brak jednostek"), Vector2(14, top + 50), size.x - 28, 22, Color("9daabc"), true)
		for i: int in range(units.size()):
			var unit: Dictionary = units[i]
			var width: float = (size.x - 32) / 3.0
			var rect: Rect2 = Rect2(10 + (i % 3) * (width + 6), top + int(i / 3) * 112, width, 104)
			cards[side + ":" + str(unit["key"])] = rect
			_draw_unit(side, unit, rect)
	var caption: String = str(frame.get("arena_text", ""))
	_text(caption, Vector2(12, center_y + 13), size.x - 24, 20, Color("d8e5f6"), true)
	if frame.get("kind") == "fire": _draw_salvos(center_y)
	elif frame.get("kind") == "impact": _draw_impacts()
	elif frame.get("kind") == "heal": _draw_healing()

func _box(bg: Color, edge: Color, radius: int = 8) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = bg; box.border_color = edge
	box.set_border_width_all(1); box.set_corner_radius_all(radius)
	return box

func _draw_unit(side: String, unit: Dictionary, rect: Rect2) -> void:
	var state: Dictionary = frame["state"][side][unit["key"]]
	var count: int = int(state["count"])
	var wounds: float = float(state["wounds"])
	var color: Color = color_for(side, unit)
	var alpha: float = 1.0 if count > 0 else .32
	draw_style_box(_box(Color("132135"), Color(color, .28)), rect)
	var texture: Texture2D = textures.get(side + ":" + str(unit["key"]))
	if texture != null:
		var area: Rect2 = Rect2(rect.position + Vector2(3,3), Vector2(rect.size.x - 6, 71))
		# Match card aspect without stretching the original art.
		var ts: Vector2 = texture.get_size()
		var scale: float = maxf(area.size.x / ts.x, area.size.y / ts.y)
		var crop: Vector2 = area.size / scale
		draw_texture_rect_region(texture, area, Rect2((ts-crop)/2, crop), Color(1,1,1,alpha))
		draw_rect(Rect2(area.position + Vector2(0,42), Vector2(area.size.x,29)), Color(0.015,.025,.05,.84))
	_text(str(unit.get("unit_name", unit["name"])), rect.position + Vector2(7,62), rect.size.x - 14, 17, Color(1,1,1,alpha))
	var count_text: String = "×" + str(count)
	var label_width: float = minf(rect.size.x - 8, font.get_string_size(count_text, HORIZONTAL_ALIGNMENT_LEFT,-1,24).x + 14)
	draw_style_box(_box(Color(.02,.045,.09,.92), Color(color,.6),5), Rect2(rect.position+Vector2(4,4),Vector2(label_width,30)))
	_text(count_text,rect.position+Vector2(10,28),rect.size.x-20,24,Color.WHITE)
	var hull: float = float(unit["hull"])
	var hp: float = maxf(0, count * hull - wounds)
	var initial: int = int(replay[side]["initial"][unit["key"]]["count"])
	var hp_rect: Rect2 = Rect2(rect.position + Vector2(6,77), Vector2(rect.size.x-12,6))
	draw_rect(hp_rect, Color("050a12"))
	draw_rect(Rect2(hp_rect.position,Vector2(hp_rect.size.x*hp/maxf(1,initial*hull),6)), color if count>0 else Color("794044"))
	var hp_text: String = I18n.t("HP %s") % number(hp)
	_text(hp_text,rect.position+Vector2(7,99),rect.size.x-14,17,Color("c4d2e3"))

func _point(side: String, key: String) -> Vector2:
	return (cards.get(side+":"+key, Rect2(size/2,Vector2.ZERO)) as Rect2).get_center()

func _draw_salvos(_center: float) -> void:
	for side: String in ["attacker", "defender"]:
		var other: String = "defender" if side == "attacker" else "attacker"
		var targets: Array = visible_units(other).filter(func(u: Dictionary) -> bool: return int(frame["state"][other][u["key"]]["count"]) > 0)
		if targets.is_empty(): continue
		for i: int in range(visible_units(side).size()):
			var unit: Dictionary = visible_units(side)[i]
			if int(frame["state"][side][unit["key"]]["count"]) <= 0 or float(unit.get("attack",0)) <= 0: continue
			var start: Vector2 = _point(side, str(unit["key"]))
			var end: Vector2 = _point(other, str(targets[0]["key"]))
			var p: float = clampf(progress * 1.3 - (i % 3)*.10,0,1)
			var pos: Vector2 = start.lerp(end,p)
			var color: Color = color_for(side, unit)
			var race: String = unit_race(side, unit)
			if race == "zetans":
				draw_line(start.lerp(end,maxf(0,p-.2)),pos,Color(color,.22),10,true)
				draw_line(start.lerp(end,maxf(0,p-.2)),pos,color,3,true)
			elif race == "automatons":
				draw_line(start.lerp(end,maxf(0,p-.10)),pos,color,4,true)
				draw_circle(pos,3,Color.WHITE)
			else:
				draw_circle(pos,8,Color(color,.15));draw_circle(pos,4,color)

func _draw_impacts() -> void:
	for side: String in ["attacker","defender"]:
		var hit: Dictionary = frame.get("events",{}).get(side,{})
		if hit.is_empty() or not cards.has(side + ":" + str(hit["key"])): continue
		var center: Vector2 = _point(side,str(hit["key"]))
		var color: Color = Color("ffb566") if int(hit["destroyed"]) > 0 else Color("e5f5ff")
		var fade: float = 1 - progress
		draw_circle(center,12+progress*30,Color(color,fade*.3))
		for i: int in range(8):
			var direction: Vector2 = Vector2.from_angle(i*TAU/8)
			draw_line(center+direction*(4+progress*18),center+direction*(14+progress*37),Color(color,fade),2,true)
		if float(hit.get("blocked",0)) > 0:
			var unit_color: Color = COLORS.get(str(formations[side][selected[side]]["race"]), COLORS[""])
			draw_arc(center,30,0,TAU,24,Color(unit_color,fade*.8),3,true)
		var floating: String = "−"+str(int(hit["destroyed"])) if int(hit["destroyed"])>0 else "−"+number(float(hit["damage"]))+" HP"
		_text(floating,center+Vector2(-84,-20-progress*18),168,24,color,true)

func _draw_healing() -> void:
	for side: String in ["attacker","defender"]:
		var event: Dictionary = frame.get("events",{}).get(side,{})
		if event.is_empty() or not cards.has(side + ":" + str(event["key"])): continue
		var point: Vector2 = _point(side,str(event["key"]))
		var color: Color = Color("a2ffb4")
		draw_arc(point,20+progress*20,0,TAU,32,Color(color,1-progress*.7),2,true)
		draw_line(point+Vector2(-7,0),point+Vector2(7,0),color,3,true)
		draw_line(point+Vector2(0,-7),point+Vector2(0,7),color,3,true)
		_text("+"+number(float(event["healed"]))+" HP",point+Vector2(-84,-18-progress*18),168,23,color,true)
