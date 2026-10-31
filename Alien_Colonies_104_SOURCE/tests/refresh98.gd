extends "res://tests/android_fleet87_regression.gd"
var callback_ms: Array = []

func idle() -> void:
	client.interaction_guard.reset()
	for frame: int in range(1500):
		if client.response_decode_jobs.is_empty(): return
		await get_tree().process_frame
	expect(false,"Background response decoding completes")

func heavy_state(name: String) -> Dictionary:
	var next: Dictionary = sample("en")
	next["player"]["name"] = name
	var extra: Array = []
	for index: int in range(3000):
		extra.append({"id":index,"text":"Timing-only stress data ".repeat(5)})
	next["scroll_test_payload"] = extra
	return next

func _run() -> void:
	fixtures = JSON.parse_string(FileAccess.get_file_as_string("res://backend/tests/fixtures/android_0112.json"))
	get_tree().root.size = Vector2i(450,800)
	new_client("en")
	await settle(12)
	var guard = client.interaction_guard
	guard.touches[0] = Vector2(200,300)
	var original: String = client.state["player"]["name"]
	var body := JSON.stringify({"ok":true,"state":heavy_state("Background state")}).to_utf8_buffer()
	client.state_request_generation += 1
	client.state_request_pending = true
	var before: int = Time.get_ticks_usec()
	client._on_state_response(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),body,client.state_request_generation)
	callback_ms.append((Time.get_ticks_usec()-before)/1000.0)
	expect(client.response_decode_jobs.size()==1,"Large response queued for decoding outside the UI thread")
	var arrived: int = client.response_decode_jobs[0].arrived_msec
	for frame: int in range(300): await get_tree().process_frame
	expect(client.state["player"]["name"]==original,"Network response does not replace UI during touch")
	expect(client.state_request_pending,"No second poll races with a pending snapshot")
	expect(WorkerThreadPool.is_task_completed(client.response_decode_jobs[0].task_id),"JSON is decoded while the finger remains down")
	await idle()
	expect(client.state["player"]["name"]=="Background state","Latest decoded snapshot applies after gesture")
	expect(client.received_at_msec==arrived,"Server clock keeps the real network arrival time")
	expect(not client.state_request_pending,"Pending poll clears after successful delivery")
	# A cancelled generation must never overwrite a later state/session.
	var kept: String = client.state["player"]["name"]
	client.state_request_generation += 1
	client.state_request_pending = true
	client._on_state_response(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"ok":true,"state":heavy_state("Stale state")}).to_utf8_buffer(),client.state_request_generation)
	client._cancel_state_request()
	await idle()
	expect(client.state["player"]["name"]==kept,"Cancelled snapshot generation is discarded")
	# Actions/colony reads carry the same full snapshot: they use the same worker.
	guard.touches[0] = Vector2.ZERO
	client.request_pending = true
	client.request_kind = "colony"
	client.command_request_generation += 1
	client._on_response(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"ok":true,"state":heavy_state("Background command")}).to_utf8_buffer())
	expect(client.request_pending,"Command identity remains reserved until its response is consumed")
	await settle(30)
	expect(client.state["player"]["name"]==kept,"Command response also avoids replacing a moving view")
	await idle()
	expect(client.state["player"]["name"]=="Background command" and not client.request_pending,"Command completes once after scrolling settles")
	client.request_pending=true; client.request_kind="colony"; client.command_request_generation+=1
	client._on_response(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"ok":true,"state":heavy_state("Obsolete command")}).to_utf8_buffer())
	client.command_request_generation+=1
	await idle()
	expect(client.state["player"]["name"]=="Background command" and client.request_pending,"Old command cannot clear or replace a newer request")
	client.request_pending=false;client.request_kind=""
	# Pending panel refreshes coalesce and run one at a time.
	var delivered: Array = []
	guard.touches[0]=Vector2.ZERO
	expect(guard.defer_refresh("a",func():delivered.append("obsolete")),"Busy guard queues a refresh")
	guard.defer_refresh("a",func():delivered.append("latest"))
	guard.defer_refresh("b",func():delivered.append("second"))
	guard.reset();guard._process(0)
	expect(delivered==["latest"],"Only the latest refresh for a panel runs in one frame")
	guard._process(0)
	expect(delivered==["latest","second"],"Other queued panel resumes on a later frame")
	await panel_contexts()
	await settle(4) # Let panel-close focus/back callbacks settle before teardown.
	# Destroying the UI safely joins outstanding pure-data tasks.
	client.state_request_generation+=1;client.state_request_pending=true
	client._on_state_response(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),body,client.state_request_generation)
	client.get_parent().remove_child(client)
	expect(client.response_decode_jobs.is_empty(),"UI teardown reaps background decode jobs")
	client.queue_free()
	var report := {"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,
		"payload_bytes":body.size(),"callback_ms":callback_ms,
		"scope":"Actual compiled Android controller; offline UI and synthetic large snapshots, no production account requests"}
	FileAccess.open("user://refresh98_report.json",FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("REFRESH98 ",JSON.stringify(report))
	get_tree().quit(0 if failed.is_empty() else 1)

func panel_contexts() -> void:
	var guard = client.interaction_guard
	var rank = client.ranking_ui
	rank.show();rank.busy=true
	guard.touches[0]=Vector2.ZERO
	rank._received(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),"{}".to_utf8_buffer(),rank.serial,client.session_token,client.server_url,false)
	expect(guard.idle_refreshes.has("ranking:%d" % rank.get_instance_id()),"Ranking parses/rebuilds only after gesture")
	rank.serial+=1;guard.reset();guard._process(0)
	expect(rank.busy,"Deferred old ranking response cannot change a newer request")
	rank.close()
	var chat = client.communications
	chat.show();chat.read_busy=true
	chat.read_context={"serial":1,"peer":chat.peer_id,"inbox":chat.inbox,"token":client.session_token,"server":client.server_url}
	guard.touches[0]=Vector2.ZERO
	chat._on_read(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),"{}".to_utf8_buffer())
	expect(guard.idle_refreshes.has("chat:%d" % chat.get_instance_id()),"Chat refresh does not interrupt scrolling")
	chat.read_context["serial"]=2
	guard.reset();guard._process(0)
	expect(chat.read_busy,"Old chat response cannot replace a new conversation request")
	chat.close()
	var alliance = client.alliance_ui
	alliance.show();alliance.member_busy=true
	alliance.contexts["members"]=alliance._identity().merged({"serial":1})
	guard.touches[0]=Vector2.ZERO
	alliance._member_received(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),"{}".to_utf8_buffer())
	expect(guard.idle_refreshes.has("alliance-members:%d" % alliance.get_instance_id()),"Alliance refresh shares the same gesture barrier")
	alliance.contexts["members"]["serial"]=2
	guard.reset();guard._process(0)
	expect(alliance.member_busy,"Deferred old alliance response cannot clear a newer request")
	alliance.close()
