# -*- coding: utf-8 -*-
extends Node
## 与 Python 内核服务（kernel_server.py）的 TCP 客户端。
## 同步调用：molecule / feed / 初始化用；异步：resolve_async 热路径。

var host := "127.0.0.1"
var port := 8765

var _peer: StreamPeerTCP = null
var _buf := PackedByteArray()
var _next_id := 1
var _pending := {}          # id -> {ctx: Dictionary, cb: Callable}
var _timeout_ms := 6000

signal kernel_ready(ok: bool)
signal async_result(id: int, data: Dictionary, ctx: Dictionary)

func _ready() -> void:
	connect_to_kernel()

func connect_to_kernel() -> bool:
	_peer = StreamPeerTCP.new()
	var err := _peer.connect_to_host(host, port)
	if err != OK:
		_peer = null
		kernel_ready.emit(false)
		return false
	var waited := 0
	while _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED and waited < _timeout_ms:
		_peer.poll()
		OS.delay_msec(5)
		waited += 5
	var ok := _peer != null and _peer.get_status() == StreamPeerTCP.STATUS_CONNECTED
	kernel_ready.emit(ok)
	if not ok:
		push_error("无法连接内核服务 %s:%d，请先运行 run_lab.bat 或 kernel_server.py" % [host, port])
	return ok

func is_kernel_connected() -> bool:
	return _peer != null and _peer.get_status() == StreamPeerTCP.STATUS_CONNECTED

func _send(req: Dictionary) -> void:
	if not req.has("id"):
		req["id"] = _next_id
		_next_id += 1
	else:
		_next_id = max(_next_id, int(req["id"]) + 1)
	var line: String = JSON.stringify(req) + "\n"
	_peer.put_data(line.to_utf8_buffer())

func _pump() -> void:
	if _peer == null:
		return
	_peer.poll()
	var avail := _peer.get_available_bytes()
	if avail > 0:
		var chunk = _peer.get_data(avail)[1]
		_buf.append_array(chunk)

func call_sync(op: String, params: Dictionary) -> Dictionary:
	if not is_kernel_connected():
		if not connect_to_kernel():
			return {"ok": false, "error": "not connected"}
	var my_id := _next_id
	_send({"op": op, "args": params, "id": my_id})
	var waited := 0
	while waited < _timeout_ms:
		_pump()
		var parsed := _try_take_line()
		if parsed.size() > 0:
			var rid := int(parsed.get("id", -1))
			if rid == my_id:
				return parsed
			# 不是本次同步调用的回复：多半是在途的异步 resolve，交给它的回调
			if _pending.has(rid):
				var item = _pending[rid]
				_pending.erase(rid)
				if item["cb"].is_valid():
					item["cb"].call(parsed, item["ctx"])
			continue
		OS.delay_msec(2)
		waited += 2
	return {}

func _try_take_line() -> Dictionary:
	var idx := -1
	for i in range(_buf.size()):
		if _buf[i] == 10:
			idx = i
			break
	if idx < 0:
		return {}
	var line := _buf.slice(0, idx).get_string_from_utf8()
	_buf = _buf.slice(idx + 1)
	line = line.strip_edges()
	if line == "":
		return {}
	var v = JSON.parse_string(line)
	if v is Dictionary:
		return v
	return {}

## 异步 resolve：不阻塞，回调通过 async_result 信号返回。
func resolve_async(mols: Array, T: float, ctx: Dictionary, cb: Callable) -> void:
	if not is_kernel_connected():
		return
	var id := _next_id
	_pending[id] = {"ctx": ctx, "cb": cb}
	_send({"op": "resolve", "mols": mols, "T": T, "id": id})

func pending_count() -> int:
	return _pending.size()

## 每帧调用：取回所有已到达的异步结果。
func poll() -> void:
	if is_kernel_connected():
		_pump()
	var guard: int = 0
	while guard < 4000:
		guard += 1
		var r := _try_take_line()
		if r.is_empty():
			break
		var rid := int(r.get("id", -1))
		if _pending.has(rid):
			var item = _pending[rid]
			_pending.erase(rid)
			if item["cb"].is_valid():
				item["cb"].call(r, item["ctx"])
