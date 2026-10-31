extends Node
const Map=preload("res://client/scripts/galaxy_map.gd")
const Routes=preload("res://client/scripts/galaxy_routes.gd")
func _ready() -> void:
	var world: Array=JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/six_ring99.json"))["systems"]
	var map: Control=Map.new()
	add_child(map)
	map.size=Vector2(720,640)
	map.set_data(world,"","s1")
	await get_tree().process_frame
	var outer: Array=[]
	for s: Dictionary in world:
		if int(s["ring_index"])==5:outer.append(s)
	var origin: String=str(outer[0]["id"])
	var fleets: Array=[]
	for i: int in range(8):
		var target: String=str(outer[24+i]["id"])
		var route: Dictionary=Routes.shortest_path(map._graph,origin,target)
		var ids: Array=route["system_ids"]
		var segments: Array=[]
		for index: int in range(1,ids.size()):
			for edge: Dictionary in map._graph[ids[index-1]]:
				if str(edge["system_id"])==str(ids[index]):
					segments.append({"from_system_id":ids[index-1],"to_system_id":ids[index],"kind":edge["kind"],"distance":edge["distance"]})
		fleets.append({"id":str(i),"mission":"scout","origin_system_id":origin,"target_system_id":target,"started_at":1000,"arrives_at":2000,"seconds":1000,"route":{"system_ids":ids,"segments":segments}})
	map.set_fleets(fleets,1500)
	var samples: Array=[]
	for i: int in range(160):
		map._pan=Vector2(i % 40, i % 31)
		var start: int=Time.get_ticks_usec()
		map._fleet_overlay.rebuild()
		samples.append(Time.get_ticks_usec()-start)
	samples.sort()
	var report: Dictionary={"case":"8 actual longest opposite outer-ring routes during pan","median_us":samples[80],"p95_us":samples[152],"max_us":samples[-1],"scope":"Headless desktop CPU, not physical Android"}
	print("FLEET_MAP_BENCH100 ",JSON.stringify(report))
	var args: PackedStringArray=OS.get_cmdline_user_args()
	if not args.is_empty():FileAccess.open(args[0],FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	get_tree().quit()

