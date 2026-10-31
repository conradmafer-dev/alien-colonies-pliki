extends Node
class NetworkClient:
	extends "res://client/scripts/main.gd"
	func _load_session() -> void:
		server_url="";baked_server_url="";session_token=""
	func _save_session() -> void: pass
	func _load_ui_preferences() -> void: pass
	func _poll(_force: bool = false) -> void: pass
	func _check_client_version() -> void: pass
	func _notify(_message: String, _error: bool = false) -> void: pass

var checks:int=0
var failed:Array[String]=[]
var client:NetworkClient

func _ready() -> void: _run.call_deferred()
func expect(ok:bool,message:String) -> void:
	checks+=1
	if not ok: failed.append(message);push_error(message)
func wait_for(test:Callable) -> void:
	var until:int=Time.get_ticks_msec()+6000
	while not test.call() and Time.get_ticks_msec()<until: await get_tree().process_frame
	expect(test.call(),"Local HTTP operation completed")

func _run() -> void:
	var origin:String=OS.get_cmdline_user_args()[0]
	expect(origin.begins_with("http://127.0.0.1:"),"Integration server is local only")
	client=NetworkClient.new();get_tree().root.add_child(client)
	client.poll_timer.stop();client.update_timer.stop();client.communications.timer.stop()
	client.connection_editing=false
	client.server_url=origin;client.session_token="LOCAL-NETWORK-FIXTURE-ONLY"
	expect(client.http.use_threads,"Command HTTP transport runs outside the UI thread")
	client._request_state("/api/state")
	expect(client.state_http.use_threads,"State HTTP transport runs outside the UI thread")
	client.interaction_guard.touches[0]=Vector2.ZERO
	await wait_for(func():return not client.response_decode_jobs.is_empty())
	expect(client.state.is_empty(),"Actual HTTP response does not rebuild a held view")
	client.interaction_guard.reset()
	await wait_for(func():return not client.state_request_pending)
	expect(client.state.get("player",{}).get("name","")=="Network state","Actual GET decodes and applies the correct world")
	client._request("/api/action",{"type":"fixture","request_id":"local-98"},"action")
	client.interaction_guard.touches[0]=Vector2.ZERO
	await wait_for(func():return not client.response_decode_jobs.is_empty())
	expect(client.request_pending and not client.uncertain_action.is_empty(),"Actual POST remains one pending identified command while scrolling")
	client.interaction_guard.reset()
	await wait_for(func():return not client.request_pending)
	expect(client.state.get("player",{}).get("name","")=="Network action","Actual POST applies its state after release")
	expect(client.uncertain_action.is_empty(),"Successful POST clears uncertainty without a duplicate send")
	var report:Dictionary={"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,
		"scope":"Real localhost HTTP GET/POST through compiled Android networking and worker decoder; no production traffic"}
	FileAccess.open("user://network98_report.json",FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("NETWORK98 ",JSON.stringify(report))
	get_tree().quit(0 if failed.is_empty() else 1)
