extends Node
## Dense coalition presentation and compatibility, using immutable recorded events.
class Host:
	extends Control
	const CLIENT_VERSION_CODE: int = 45
	var server_url: String = "http://127.0.0.1:1"
	var session_token: String = "fixture"
	func _label(text: String, font_size: int = 22) -> Label:
		var result: Label = Label.new(); result.text = text
		result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		result.add_theme_font_size_override("font_size",font_size)
		result.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		return result
	func _button(text: String, action: Callable) -> Button:
		var result: Button = Button.new(); result.text = text
		result.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		result.pressed.connect(action)
		return result
class Viewer:
	extends "res://client/scripts/battle_replay.gd"
	func _load() -> void: pass
var checks: int = 0
var failures: int = 0
var host: Host
var view: Viewer
var root_box: VBoxContainer
var fixture: Dictionary
var shots: String = ""

func _ready() -> void: run.call_deferred()
func expect(value: bool, description: String) -> void:
	checks += 1
	if not value: failures += 1; push_error(description)
func settle() -> void:
	for i: int in range(5): await get_tree().process_frame
func fresh(data: Dictionary) -> void:
	if is_instance_valid(view):
		view.shutdown(); root_box.remove_child(view); view.queue_free()
	view = Viewer.new(); root_box.add_child(view)
	view.setup(host,{"id":"coalition-fixture"})
	expect(view._valid(data),"Valid complete coalition/solo replay accepted")
	view._received(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"ok":true,"replay":data},"",true,true).to_utf8_buffer())
	view.set_process(false)
	expect(view.playing,"Replay begins automatically when loaded")
	await settle()
func shot(filename: String) -> void:
	if shots.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(shots.path_join(filename+".png"))
func geometry() -> void:
	expect(view.board.custom_minimum_size.y <= 772,"Coalition arena height is bounded to two 3-row formations")
	expect(view.board.size.y <= 773,"Arena actual height does not grow with participant count")
	expect(view.board.size.x <= view.size.x+1,"Arena fits narrow viewport")
	expect(view.ledger_scroll.size.y <= 221,"Complete combat ledger stays in fixed scroll viewport")
	expect(view.board.cards.size() <= 18,"Only visible formations draw cards")
	for rect: Rect2 in view.board.cards.values():
		expect(Rect2(Vector2.ZERO,view.board.size).encloses(rect),"Each visible card fits inside the arena")
	for choice: OptionButton in view.formation_choices.values():
		expect(choice.size.y >= 56,"Participant selectors remain finger-sized")
		expect(choice.get_global_rect().end.x <= get_viewport().get_visible_rect().end.x+1,"Long player names cannot widen viewport")
	for side: String in ["attacker","defender"]:
		for unit: Dictionary in view.replay[side]["units"]:
			expect(view.board.textures[side+":"+unit["key"]] != null,"Every faction retains its original artwork")
			expect(view.board.color_for(side,unit) == view.board.COLORS[unit["race"]],"Unit color belongs to its own faction")
func run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	fixture = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	shots = args[1] if args.size()>1 else ""
	if not shots.is_empty(): DirAccess.make_dir_recursive_absolute(shots)
	var window: Window = get_tree().root
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_size = Vector2i(720,1280)
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
	window.size = Vector2i(720,1600)
	host = Host.new(); add_child(host); host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var background: ColorRect = ColorRect.new(); background.color = Color("0b1018"); host.add_child(background)
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var scroll: ScrollContainer = ScrollContainer.new(); host.add_child(scroll)
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.offset_left=20;scroll.offset_top=20;scroll.offset_right=-20;scroll.offset_bottom=-20
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	root_box = VBoxContainer.new(); scroll.add_child(root_box)
	root_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	for locale: String in ["pl","en","de","es","fr"]:
		get_tree().root.get_node("I18n").set_locale(locale,false)
		await fresh(fixture["dense"])
		var before: String = JSON.stringify(fixture["dense"])
		expect(view.coalition and view.formation_choices.size()==2,"Both sides have participant selectors")
		expect(view.board.formations["attacker"].size()==5,"All five attacking formations are selectable")
		expect(view.board.formations["defender"].size()==6,"Defending planet and five supports are selectable")
		var hits: Dictionary = {"attacker":0,"defender":0}
		var heals: Dictionary = {"attacker":0,"defender":0}
		var firing: Dictionary = {"attacker":{},"defender":{}}
		var first_impact: int = -1
		for i: int in range(view.frames.size()):
			view.index=i;view._show()
			var frame: Dictionary = view.frames[i]
			for side: String in ["attacker","defender"]:
				if frame["kind"] == "fire":
					firing[side][view.board.selected[side]]=true
				if not frame.get("events",{}).has(side): continue
				var event: Dictionary = frame["events"][side]
				var visible: Array = view.board.visible_units(side).map(func(unit: Dictionary) -> String: return unit["key"])
				expect(event["key"] in visible,"Every recorded impact/heal focuses the correct participant")
				if frame["kind"]=="impact": hits[side]+=1;first_impact=i if first_impact<0 else first_impact
				if frame["kind"]=="heal": heals[side]+=1
				expect(frame["state"][side][event["key"]]==event["after"],"Displayed event uses exact recorded counts and hull damage")
		for side: String in ["attacker","defender"]:
			var expected_hits: int = 0; var expected_heals: int = 0
			for round: Dictionary in view.replay["rounds"]:
				expected_hits += round["hits"][side].size(); expected_heals += round["heals"][side].size()
			expect(hits[side]==expected_hits and heals[side]==expected_heals,"No dense coalition events are discarded")
			expect(firing[side].size()==view.board.formations[side].size(),"Every participant's salvo is animated")
		view.skip()
		for participant: Dictionary in view.replay["participant_results"]:
			expect(str(participant["owner_name"]) in view.detail.text,"Final ledger names each participant")
			if participant["side"]=="attacker":
				expect(str(int(participant["cargo"]["metal"])) in view.detail.text,"Final ledger retains each player's own loot")
		if locale=="pl": await shot("coalition_result_pl")
		view.index=first_impact;view._show()
		view.formation_choices["attacker"].item_selected.emit(4)
		expect(not view.playing and view.board.selected["attacker"]==4,"Manual selector pauses and retains chosen formation")
		view.toggle_pause()
		expect(view.playing and view.board.selected["attacker"]==4,"Resume preserves inspection until next event")
		view.playing=false
		view.index=first_impact+1;view._show();view.board.show_frame(view.frames[view.index],.42)
		for dimensions: Vector2i in [Vector2i(720,1280),Vector2i(720,1600),Vector2i(1080,2520)]:
			window.size=dimensions;await settle();geometry()
			if locale=="pl": await shot("coalition_impact_"+str(dimensions.x)+"x"+str(dimensions.y)+"_pl")
		view.index=0;view.elapsed=0;view.playing=true;view.speed=1000;view._show()
		for i: int in range(view.frames.size()+1): view._process(.15)
		expect(not view.playing and view.frames[view.index]["kind"]=="result","Autoplay completes all coalition frames and stops at result")
		expect(JSON.stringify(fixture["dense"])==before,"Playback cannot mutate source battle or gameplay state")
		for ri: int in range(view.replay["rounds"].size()):
			view.seek_round(ri)
			expect(view.frames[view.index]["state"]==view.replay["rounds"][ri]["after"],"Round picker preserves exact completed state")
		var rejected: Dictionary = fixture["dense"].duplicate(true)
		rejected["attacker"]["units"].append(rejected["attacker"]["units"][0].duplicate(true))
		expect(not view._valid(rejected),"Duplicate formation-unit keys are rejected")
		rejected=fixture["dense"].duplicate(true)
		rejected["rounds"][0]["hits"]["attacker"][0]["key"]="unknown-formation:scout"
		expect(not view._valid(rejected),"Unknown event units are rejected")
		rejected=fixture["dense"].duplicate(true)
		while rejected["attacker"]["units"].size()<=view.MAX_SIDE_UNITS:
			rejected["attacker"]["units"].append(rejected["attacker"]["units"][0].duplicate(true))
		expect(not view._valid(rejected),"Unit bound remains enforced")
		await fresh(fixture["solo"])
		expect(not view.coalition and view.formation_choices.is_empty(),"Historical solo replay keeps original layout")
		expect(not is_instance_valid(view.ledger_scroll),"Historical solo log remains unchanged")
		view.skip();expect(view.frames[view.index]["state"]==fixture["solo"]["final"],"Solo result retains exact final state")
		await fresh(fixture["actual"][locale])
		expect(view.coalition and view.board.formations["attacker"].size()==3,"Actual paid three-player coalition battle is presentable")
		for side: String in ["attacker","defender"]:
			for unit: Dictionary in view.replay[side]["units"]:
				expect(unit.has("unit_name") and unit.has("owner_name"),"Actual server provides short localized ship label and owner")
				expect(view.board.unit_formations[side].has(unit["key"]),"Actual formation keys map to their own UI formation")
		view.skip()
		expect(view.frames[view.index]["state"]==fixture["actual"][locale]["final"],"Actual server coalition results are shown unchanged")
		expect("Coalition" in view.detail.text and "MetalAlly" in view.detail.text and "GreenAlly" in view.detail.text,"Actual final ledger retains every coalition owner")
		if locale=="pl":
			view.seek_round(0); await settle(); await shot("actual_coalition_round_1_pl")
	view.shutdown()
	print("Alliance replay UI 0.10.0: ",checks," checks; ",failures," failures")
	get_tree().quit(1 if failures else 0)
