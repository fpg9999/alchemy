# -*- coding: utf-8 -*-
extends RefCounted
## ChemLab 世界模拟：方格网格、骨架占格、连续重力、三素非对称力、
## 粘附锁、温度场（分子热值 T=n_L+2n_F + 环境耦合）、resolve 反应。
## 反应通过 kernel_client 异步请求，结果回调到 apply_response。

class_name ChemSim

const DIRS8 := [
	Vector2i(-1, -1), Vector2i(-1, 0), Vector2i(-1, 1),
	Vector2i(0, -1), Vector2i(0, 1),
	Vector2i(1, -1), Vector2i(1, 0), Vector2i(1, 1),
]
const DIRS4 := [Vector2i(-1, 0), Vector2i(1, 0), Vector2i(0, -1), Vector2i(0, 1)]

var W := 200
var H := 140
var grid := PackedInt32Array()
var mols: Array = []          # id -> Dictionary（含 dead 标记）
var next_id := 0
var tick := 0
var rng := RandomNumberGenerator.new()

var client                      # KernelClient
var info_cache := {}            # formula -> info dict

# 参数（全部可调）
var p := {
	"gravity_G": 0.30,
	"KA": 2.5, "KR": 0.5,
	"force_r": 3,
	"lock_w": 1.0, "lock_r": 2,
	"brown": 0.04,
	"mob_gas": 1.0, "mob_liq": 0.60, "mob_solid": 0.25,
	"p_react": 0.02,
	"react_margin": 0.0,
	"cap": 36,
	"T0": 1000.0, "T_end": 10.0, "cool_ticks": 600.0, "plateau": true,
	"env_coupling": 3.0,
	"seed": 20261120,
	"use_match": false,
	"hard_walls": true,
}

# 统计
var stats := {
	"n": 0, "species": 0,
	"complete": 0, "incomplete": 0, "none": 0, "drops": 0, "joins": 0,
	"pairs": 0, "T_env": 0.0, "T_hot": 0.0,
}
var species_count := {}
var pending_res := 0
var max_react_per_tick := 600
var _order := []
var _rng_tick := 0

func setup(w: int, h: int, kernel_client) -> void:
	W = w
	H = h
	client = kernel_client
	grid.resize(W * H)
	reset()

func reset() -> void:
	grid.fill(-1)
	mols.clear()
	next_id = 0
	tick = 0
	rng.seed = int(p["seed"])
	stats = {"n": 0, "species": 0, "complete": 0, "incomplete": 0,
			"none": 0, "drops": 0, "joins": 0, "pairs": 0,
			"T_env": float(p["T0"]), "T_hot": 0.0}
	species_count = {}
	pending_res = 0

func info(f: String) -> Dictionary:
	if info_cache.has(f):
		return info_cache[f]
	var r = client.call_sync("molecule", {"formula": f})
	if r.get("ok", false):
		var d: Dictionary = r["data"]
		d["A"] = float(d.get("A", 0.0))
		d["D"] = float(d.get("D", 0.0))
		d["ratt"] = int(d.get("ratt", 1))
		d["rrep"] = int(d.get("rrep", 1))
		d["k"] = int(d.get("k", 1))
		d["heat"] = int(d.get("heat", 0))
		d["c"] = int(d.get("c", max(1, int(d.get("natoms", 1)) - 1)))
		d["attrs"] = d.get("attrs", {"mass": 2.0, "state": 1.0, "temperature": 1.0})
		info_cache[f] = d
		return d
	return {}

func shape_of(k: int) -> Array:
	if k <= 1:
		return [Vector2i(0, 0)]
	if k == 2:
		return [Vector2i(0, 0), Vector2i(0, 1)]
	if k == 3:
		return [Vector2i(0, 0), Vector2i(1, 0), Vector2i(2, 0)]
	if k == 4:
		return [Vector2i(0, 0), Vector2i(0, 1), Vector2i(1, 0), Vector2i(1, 1)]
	var n := int(ceil(sqrt(float(k))))
	var out: Array = []
	for r in range(n):
		for c in range(n):
			if out.size() < k:
				out.append(Vector2i(r, c))
	return out

func in_bounds(cell: Vector2i) -> bool:
	if not bool(p.get("hard_walls", true)):
		return true
	return cell.x >= 0 and cell.x < H and cell.y >= 0 and cell.y < W

func wrap_cell(cell: Vector2i) -> Vector2i:
	if bool(p.get("hard_walls", true)):
		return cell   # 硬墙：不做环面折返，越界由调用方拒绝
	return Vector2i(posmod(cell.x, H), posmod(cell.y, W))

func _idx(c: Vector2i) -> int:
	return c.x * W + c.y

func _cheb(a: Vector2i, b: Vector2i) -> int:
	var dr: int = abs(a.x - b.x)
	var dc: int = abs(a.y - b.y)
	if not bool(p.get("hard_walls", true)):
		dr = min(dr, H - dr)
		dc = min(dc, W - dc)
	return max(dr, dc)

func footprint_free(shape: Array, anchor: Vector2i, ignore_id: int = -1) -> bool:
	for s in shape:
		var raw: Vector2i = anchor + s
		if not in_bounds(raw):
			return false
		var o := grid[_idx(wrap_cell(raw))]
		if o != -1 and o != ignore_id:
			return false
	return true

func place(f: String, anchor: Vector2i, ignore_id: int = -1) -> int:
	var d := info(f)
	if d.is_empty():
		return -1
	var shape := shape_of(int(d.get("k", 1)))
	if bool(p.get("hard_walls", true)):
		if not in_bounds(anchor):
			return -1
	else:
		anchor = wrap_cell(anchor)
	if not footprint_free(shape, anchor, ignore_id):
		# 在附近找一个空位
		var found := false
		for rad in range(1, 7):
			for dr in range(-rad, rad + 1):
				for dc in range(-rad, rad + 1):
					var a := Vector2i(anchor.x + dr, anchor.y + dc)
					if footprint_free(shape, a, ignore_id):
						anchor = a
						found = true
						break
				if found:
					break
			if found:
				break
		if not found:
			return -1
	var m := {
		"id": next_id, "f": f, "k": int(d.get("k", 1)),
		"shape": shape, "anchor": anchor, "cells": [],
		"mass": float(d["attrs"].get("mass", 2.0)),
		"state": float(d["attrs"].get("state", 1.0)),
		"temp": float(d["attrs"].get("temperature", 1.0)),
		"A": float(d.get("A", 0.0)), "D": float(d.get("D", 0.0)),
		"ratt": int(d.get("ratt", 1)), "rrep": int(d.get("rrep", 1)),
		"heat": int(d.get("heat", 0)), "c": int(d.get("c", 1)),
		"natoms": int(d.get("natoms", 1)),
		"gacc": 0.0, "dead": false, "locks": [],
	}
	for s in shape:
		var c: Vector2i = wrap_cell(anchor + s)
		m["cells"].append(c)
		grid[_idx(c)] = next_id
	mols.append(m)
	next_id += 1
	_count_species(f, 1)
	stats["n"] = _alive_count()
	return m["id"]

func _count_species(f: String, d: int) -> void:
	species_count[f] = int(species_count.get(f, 0)) + d
	if species_count[f] <= 0:
		species_count.erase(f)
	stats["species"] = species_count.size()

func _alive_count() -> int:
	var n := 0
	for m in mols:
		if not m["dead"]:
			n += 1
	return n

func remove(id: int) -> void:
	if id < 0 or id >= mols.size():
		return
	var m = mols[id]
	if m["dead"]:
		return
	m["dead"] = true
	for c in m["cells"]:
		grid[_idx(c)] = -1
	_count_species(m["f"], -1)
	stats["n"] = _alive_count()

func remove_at(cell: Vector2i) -> void:
	var o := grid[_idx(cell)]
	if o >= 0:
		remove(o)

func schedule_T(t: float) -> float:
	var T0 := float(p["T0"])
	var Tend := float(p["T_end"])
	var ct: float = max(1.0, float(p["cool_ticks"]))
	if t < ct:
		return Tend + (T0 - Tend) * exp(-6.0 * t / ct)
	return Tend

func local_T(pair_cells: Array) -> float:
	# 以接触中点为中心、Chebyshev 2 格内的分子热值平均 + 环境耦合
	var mid: Vector2i = pair_cells[0]
	var hsum := 0.0
	var n := 0
	var seen := {}
	for dr in range(-2, 3):
		for dc in range(-2, 3):
			var raw := Vector2i(mid.x + dr, mid.y + dc)
			if not in_bounds(raw):
				continue
			var c := wrap_cell(raw)
			var o := grid[_idx(c)]
			if o >= 0 and not seen.has(o):
				seen[o] = true
				var m = mols[o]
				if not m["dead"]:
					hsum += float(m["heat"])
					n += 1
	var ec := float(p["env_coupling"])
	return (hsum + ec * stats["T_env"]) / (n + ec)

func neighbors_of(id: int, r: int) -> Array:
	var m = mols[id]
	var seen := {}
	var out: Array = []
	var a: Vector2i = m["anchor"]
	for dr in range(-r, r + 1):
		for dc in range(-r, r + 1):
			if dr == 0 and dc == 0:
				continue
			var raw := Vector2i(a.x + dr, a.y + dc)
			if not in_bounds(raw):
				continue
			var c := wrap_cell(raw)
			var o := grid[_idx(c)]
			if o >= 0 and o != id and not seen.has(o):
				seen[o] = true
				var o2 = mols[o]
				if not o2["dead"]:
					out.append(o)
	return out

func decay(d: int, r: int) -> float:
	if d <= 1:
		return 1.0
	if d <= r:
		return (r + 1 - d) / float(r)
	return 0.0

func force_on(id: int) -> Vector2:
	var m = mols[id]
	var a: Vector2i = m["anchor"]
	var f := Vector2.ZERO
	var KA := float(p["KA"])
	var KR := float(p["KR"])
	var fr := int(p["force_r"])
	for oid in neighbors_of(id, fr):
		var o = mols[oid]
		var b: Vector2i = o["anchor"]
		var d: int = _cheb(a, b)
		var att := KA * float(m["A"]) * decay(d, int(m["ratt"]))
		var rep := KR * float(o["D"]) * decay(d, int(o["rrep"]))
		var w := att - rep
		if abs(w) < 0.001:
			continue
		var dir := Vector2(b.x - a.x, b.y - a.y)
		if dir.length_squared() < 0.0001:
			dir = Vector2(0.1, 0.1)
		f += dir.normalized() * w
	return f

func mobility(m) -> float:
	var s := float(m["state"])
	if s < 1.0:
		return float(p["mob_gas"])
	elif s < 2.0:
		return float(p["mob_liq"])
	return float(p["mob_solid"])

func try_move(id: int, step: Vector2i) -> bool:
	var m = mols[id]
	if m["dead"]:
		return false
	var raw_na: Vector2i = m["anchor"] + step
	if not in_bounds(raw_na):
		return false
	var na: Vector2i = wrap_cell(raw_na)
	for lk in m["locks"]:
		var o = mols[lk]
		if o["dead"]:
			continue
		if _cheb(o["anchor"], na) > int(p["lock_r"]):
			return false
	if not footprint_free(m["shape"], na, id):
		# 只能把单格分子挤开一步（重压轻）
		if int(m["k"]) != 1:
			return false
		var oid := grid[_idx(na)]
		if oid < 0 or oid == id:
			return false
		var o = mols[oid]
		if int(o["k"]) != 1 or o["dead"]:
			return false
		if float(m["mass"]) < float(o["mass"]):
			return false
		var raw_back: Vector2i = na - step
		if not in_bounds(raw_back):
			return false
		var back: Vector2i = wrap_cell(raw_back)
		if grid[_idx(back)] != -1 and grid[_idx(back)] != oid:
			return false
		grid[_idx(o["anchor"])] = -1
		o["anchor"] = back
		o["cells"] = [back]
		grid[_idx(back)] = oid
	for cell in m["cells"]:
		grid[_idx(cell)] = -1
	var ncells: Array = []
	for sh in m["shape"]:
		var c: Vector2i = wrap_cell(na + sh)
		grid[_idx(c)] = id
		ncells.append(c)
	m["anchor"] = na
	m["cells"] = ncells
	return true

func rebuild_locks() -> void:
	for m in mols:
		m["locks"] = []
	var KA := float(p["KA"])
	var KR := float(p["KR"])
	var lw := float(p["lock_w"])
	for id in range(mols.size()):
		var m = mols[id]
		if m["dead"]:
			continue
		var a: Vector2i = m["anchor"]
		for oid in neighbors_of(id, 1):
			if oid <= id:
				continue
			var o = mols[oid]
			var b: Vector2i = o["anchor"]
			var d: int = _cheb(a, b)
			if d > 1:
				continue
			var wab := KA * float(m["A"]) * decay(d, int(m["ratt"])) - KR * float(o["D"]) * decay(d, int(o["rrep"]))
			var wba := KA * float(o["A"]) * decay(d, int(o["ratt"])) - KR * float(m["D"]) * decay(d, int(m["rrep"]))
			if min(wab, wba) >= lw:
				m["locks"].append(oid)
				o["locks"].append(id)

func step() -> void:
	tick += 1
	stats["T_env"] = schedule_T(float(tick))
	# 1) 重力：整格下移
	var G := float(p["gravity_G"])
	for id in range(mols.size()):
		var m = mols[id]
		if m["dead"]:
			continue
		m["gacc"] = float(m["gacc"]) + G * float(m["mass"])
		var guard: int = 0
		while float(m["gacc"]) >= 1.0 and guard < 4:
			guard += 1
			if try_move(id, Vector2i(1, 0)):
				m["gacc"] = float(m["gacc"]) - 1.0
			else:
				break
	# 2) 三素力驱动
	_order.clear()
	for id in range(mols.size()):
		if not mols[id]["dead"]:
			_order.append(id)
	_order.shuffle()
	for id in _order:
		if id >= mols.size() or mols[id]["dead"]:
			continue
		var m = mols[id]
		var f := force_on(id)
		var mag := f.length()
		if mag < 0.02:
			# 布朗
			if rng.randf() < float(p["brown"]):
				try_move(id, DIRS8[rng.randi() % 8])
			continue
		var best := Vector2i(0, 0)
		var bestdot: float = -1.0
		for d in DIRS8:
			var dot: float = Vector2(d).normalized().dot(f.normalized())
			if dot > bestdot:
				bestdot = dot
				best = d
		var prob: float = mobility(m) * min(1.0, 0.25 + 0.75 * mag)
		if rng.randf() < prob:
			try_move(id, best)
	# 3) 粘附锁
	rebuild_locks()
	# 4) 反应：相邻对 + 局部温度门控 + 异步 resolve
	_react_phase()

func _react_phase() -> void:
	var sent = 0
	var seen := {}
	for id in range(mols.size()):
		if sent >= max_react_per_tick:
			break
		var m = mols[id]
		if m["dead"]:
			continue
		for cell in m["cells"]:
			for d in DIRS4:
				var raw: Vector2i = cell + d
				if not in_bounds(raw):
					continue
				var c := wrap_cell(raw)
				var oid := grid[_idx(c)]
				if oid < 0 or oid == id:
					continue
				var key: int = min(id, oid) * 100000 + max(id, oid)
				if seen.has(key):
					continue
				seen[key] = true
				var o = mols[oid]
				if o["dead"]:
					continue
				if int(m["natoms"]) + int(o["natoms"]) > int(p["cap"]):
					continue
				var tl := local_T([cell, c])
				var csum := int(m["c"]) + int(o["c"])
				if tl < float(csum) + float(p["react_margin"]):
					continue
				if rng.randf() > float(p["p_react"]):
					continue
				stats["pairs"] = int(stats["pairs"]) + 1
				pending_res += 1
				sent += 1
				var ctx := {"a": id, "b": oid, "cell": cell, "T": tl}
				client.resolve_async([{"formula": m["f"]}, {"formula": o["f"]}], tl, ctx, Callable(self, "on_resolve"))
	stats["T_hot"] = stats["T_env"]

func on_resolve(resp: Dictionary, ctx: Dictionary) -> void:
	pending_res = max(0, pending_res - 1)
	if not resp.get("ok", false):
		return
	var d: Dictionary = resp["data"]
	var typ := String(d.get("type", "none"))
	if typ == "none":
		stats["none"] = int(stats["none"]) + 1
		return
	var a: int = int(ctx["a"])
	var b: int = int(ctx["b"])
	if a >= mols.size() or b >= mols.size():
		return
	if mols[a]["dead"] or mols[b]["dead"]:
		return
	if typ == "complete":
		stats["complete"] = int(stats["complete"]) + 1
	else:
		stats["incomplete"] = int(stats["incomplete"]) + 1
	var mid: Vector2i = mols[a]["anchor"]
	remove(a)
	remove(b)
	for pf in d.get("products", []):
		var f := String(pf)
		var pid := place_near(f, mid)
		if pid >= 0:
			stats["joins"] = int(stats["joins"]) + 1
		else:
			stats["drops"] = int(stats["drops"]) + 1

func place_near(f: String, mid: Vector2i) -> int:
	for rad in range(0, 7):
		for i in range(8):
			if rad == 0:
				var p0 := place(f, mid)
				if p0 >= 0:
					return p0
				continue
			var ang := TAU * float(i) / 8.0
			var off := Vector2i(int(round(sin(ang) * rad)), int(round(cos(ang) * rad)))
			var pid := place(f, mid + off)
			if pid >= 0:
				return pid
	return -1

func rho() -> float:
	return float(_alive_count()) / float(W * H)

func load_feed(feed: Array) -> void:
	reset()
	for item in feed:
		var f := String(item.get("formula", ""))
		var n := int(item.get("count", 0))
		for i in range(n):
			if mols.size() >= W * H:
				return
			var a := Vector2i(rng.randi_range(0, H - 1), rng.randi_range(0, W - 1))
			place(f, a)

func save_json() -> Dictionary:
	var out_mols: Array = []
	for m in mols:
		if m["dead"]:
			continue
		out_mols.append([m["f"], m["anchor"].x, m["anchor"].y])
	return {"W": W, "H": H, "tick": tick, "params": p.duplicate(),
			"mols": out_mols, "stats": stats.duplicate()}

func load_json(d: Dictionary) -> void:
	reset()
	p = d.get("params", p).duplicate()
	tick = int(d.get("tick", 0))
	for item in d.get("mols", []):
		place(String(item[0]), Vector2i(int(item[1]), int(item[2])))
