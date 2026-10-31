extends "res://tests/android_fleet87_regression.gd"
func _run() -> void:
	fixtures=JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	new_client("en")
	await settle(15)
	client.interaction_guard.touches[0]=Vector2.ZERO
	var clocks:Array=[]
	for i:int in range(40):
		var before:int=Time.get_ticks_usec()
		client._update_clock()
		clocks.append((Time.get_ticks_usec()-before)/1000.0)
		await settle(1)
	var next:Dictionary=sample("en")
	var extra:Array=[]
	for i:int in range(3000):extra.append({"id":i,"text":"Representative timing-only payload ".repeat(5)})
	next["scroll_test_payload"]=extra
	var body:=JSON.stringify({"ok":true,"state":next}).to_utf8_buffer()
	var callbacks:Array=[]
	for i:int in range(5):
		client._cancel_state_request()
		client.state_request_pending=true
		var before:int=Time.get_ticks_usec()
		client._on_state_response(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),body,client.state_request_generation)
		callbacks.append((Time.get_ticks_usec()-before)/1000.0)
		await settle(3)
	var report:Dictionary={"code":client.CLIENT_VERSION_CODE,"payload_bytes":body.size(),"clock_while_touch_ms":clocks,"callback_ms":callbacks,
		"scope":"Same headless desktop and fixture through actual Android indices. CPU callback/tick time, not physical Android FPS."}
	FileAccess.open("user://scroll_benchmark98.json",FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("SCROLL_BENCH ",JSON.stringify(report))
	get_tree().quit()
