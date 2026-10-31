extends Node
const Bridge = preload("res://client/scripts/report_notifications.gd")
class FakeNative extends RefCounted:
	var active: String = ""
	var reports: Array = []
	var pending: String = ""
	func isAllowed() -> bool: return false
	func requestPermission() -> void: pass
	func setActivePlayer(value: String) -> void: active=value
	func showReport(player: String,id: String,title: String,body: String,kind: String) -> void:
		reports.append({"player":player,"id":id,"title":title,"body":body,"kind":kind})
	func consumeReport() -> String:
		var value: String=pending
		pending=""
		return value
var session_token: String = "offline"
var opened_tab: int = -1
var failed: Array = []
var checks: int = 0
func _open_tab(tab: int) -> void: opened_tab=tab
func expect(ok: bool,message: String) -> void:
	checks+=1
	if not ok: failed.append(message);push_error(message)
func snapshot(player: String,ids: Array) -> Dictionary:
	var reports: Array=[]
	for id: String in ids: reports.append({"id":id,"title":"Atak na kolonię","text":"Raport testowy"})
	return {"player":{"id":player,"race_id":"zetans"},"reports":reports}
func _ready() -> void:
	var native=FakeNative.new()
	var bridge=Bridge.new()
	bridge.setup(self)
	bridge.native=native
	add_child(bridge)
	bridge.sync(snapshot("a",["old"]))
	expect(native.reports.is_empty(),"Login does not notify historical reports")
	bridge.sync(snapshot("a",["new","old"]))
	expect(native.reports.size()==1 and native.reports[0]["id"]=="new","New report notified exactly once")
	expect(native.reports[0]["kind"]=="attack","Attack uses priority notification channel")
	bridge.sync(snapshot("a",["new","old"]))
	expect(native.reports.size()==1,"Polling same report never duplicates notification")
	bridge.sync(snapshot("b",["other"]))
	expect(native.active=="b" and native.reports.size()==1,"Account switch establishes fresh report baseline")
	native.pending="other"
	bridge._process(0.3)
	await get_tree().process_frame
	expect(opened_tab==4,"Notification tap opens actual reports tab")
	bridge.clear()
	expect(native.active.is_empty() and bridge.player_owner.is_empty(),"Logout unlinks native notifications")
	var file=FileAccess.open("res://tests/report_notifications90_report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify({"result":"PASS" if failed.is_empty() else "FAIL","checks":checks,"failed":failed,
		"scope":"Native bridge logic with fake Android receiver; no OS notification or Firebase delivery test"},"  "))
	file.close()
	print("Notifications 90: %d checks; %d failures" % [checks,failed.size()])
	get_tree().quit(1 if not failed.is_empty() else 0)
