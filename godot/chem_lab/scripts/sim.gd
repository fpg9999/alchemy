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
const F2V := 0.02   # T96：力→速度标定（与 alchemy/t95_collision.F2V 一致）

var W := 200
var H := 140
var grid := PackedInt32Array()
var mols: Array = []          # id -> Dictionary（含 dead 标记）
var next_id := 0
var tick := 0
var rng := RandomNumberGenerator.new()

var client                      # KernelClient
var info_cache := {}            # formula -> info dict
var _hash := {}                 # 空间哈希：Vector2i(格x,格y) -> [mol id]
var _hash_cell := 12            # 哈希格边长（= r_cap）

# 参数（全部可调）
var p := {
	"gravity_G": 0.20,
	"KA": 2.5, "KR": 0.5,
	"r_cap": 12,
	"force_scale": 1.00,
	"lock_w": 1.0, "lock_r": 2, "lock_rigid_fall": true,
	"heat_w": {"C": -1.0, "L": 1.0, "F": 2.0},
	"mob_gas": 1.0, "mob_liq": 0.60, "mob_solid": 0.25,
	"p_react": 1.0,
	"react_margin": 0.0,
	"cap": 36,
	"T0": 200.0, "T_end": 0.0, "cool_ticks": 600.0, "plateau": true,
	"env_coupling": 0.5,
	"seed": 20261120,
	"use_match": false, "max_pending": 96,
	"hard_walls": true,
	# T96 碰撞/推挤（默认值按 alchemy/t95_config.py）
	"push_enable": true, "push_e": 0.2, "push_mu": 0.25,
	"push_kmax": 6, "push_vmax": 2.0, "push_gamma": 0.15,
	"push_m_min_ratio": 0.5,
	"group_push_enable": true, "group_push_thresh": 0.5,
}

# 统计
var m_ax := PackedInt32Array()
var m_ay := PackedInt32Array()
var m_A := PackedFloat32Array()
var m_D := PackedFloat32Array()
var m_ra := PackedInt32Array()
var m_rr := PackedInt32Array()
var m_alive := PackedByteArray()
var stats := {
	"n": 0, "species": 0,
	"complete": 0, "incomplete": 0, "none": 0, "drops": 0, "joins": 0,
	"pairs": 0, "T_env": 0.0, "T_hot": 0.0,
	"ms_g": 0.0, "ms_f": 0.0, "ms_l": 0.0, "ms_r": 0.0,
}
var species_count := {}
var pending_res := 0
var max_react_per_tick := 120
var alive := 0
var epoch := 0
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
			"none": 0, "drops": 0, "joins": 0, "pairs": 0, "moves": 0,
			"n_push": 0, "n_push_fail": 0, "chain_hist": {},
			"n_group_push": 0, "n_group_push_fail": 0, "mean_speed": 0.0,
			"T_env": float(p["T0"]), "T_hot": 0.0}
	species_count = {}
	pending_res = 0
	alive = 0
	epoch += 1
	if client and client.has_method("clear_pending"):
		client.clear_pending()

## 解析分子式（元素字母 + 可选数字），失败返回 {}
func _comp_from_formula(f: String) -> Dictionary:
	var comp := {}
	var i := 0
	while i < f.length():
		var ch := f[i]
		if ch < "A" or ch > "Z":
			return {}
		if "OXCPWLKAF".find(ch) < 0:
			return {}
		var j := i + 1
		var num := 1
		var has_digit := false
		while j < f.length() and f[j] >= "0" and f[j] <= "9":
			if not has_digit:
				num = 0
				has_digit = true
			num = num * 10 + int(f[j].to_int())
			j += 1
		comp[ch] = int(comp.get(ch, 0)) + max(1, num)
		i = j
	return comp

## 本地计算分子信息（与内核 molecule_info 同口径），避免热路径同步阻塞
func _local_info(f: String) -> Dictionary:
	var comp := _comp_from_formula(f)
	if comp.is_empty():
		return {}
	var n := 0
	for e in comp.keys():
		n += int(comp[e])
	if n <= 0:
		return {}
	var cO := float(comp.get("O", 0))
	var cX := float(comp.get("X", 0))
	var cC := float(comp.get("C", 0))
	var cK := float(comp.get("K", 0))
	var cA := float(comp.get("A", 0))
	var cF := float(comp.get("F", 0))
	var cP := float(comp.get("P", 0))
	var cW := float(comp.get("W", 0))
	var cL := float(comp.get("L", 0))
	var n_att := cO + cX + cC
	var n_rng := cK + cA + cF
	var n_rep := cP + cW + cL
	var mass := 0.0
	if n_att > 0.0:
		mass = (3.0 * cO + 2.0 * cK + 1.0 * cP) / (n_att + cK + cP)
	var state := 0.0
	if cX + cW + cA > 0.0:
		state = (3.0 * cX + 2.0 * cW + 1.0 * cA) / (cX + cW + cA)
	var temp := 0.0
	if n_rng > 0.0:
		temp = (3.0 * cF + 2.0 * cL + 1.0 * cC) / n_rng
	var att := 0.0
	if n_att > 0.0:
		att = (3.0 * cO + 2.0 * cX + 1.0 * cC) / n_att
	var rep := 0.0
	if n_rep > 0.0:
		rep = (3.0 * cP + 2.0 * cW + 1.0 * cL) / n_rep
	var q := int(3.0 * cK + 2.0 * cA + cF)
	var rr := _radius_of_q(q)
	var kk := maxi(1, int(round(float(n) / 8.08)))
	return {"formula": f, "natoms": n, "comp": comp, "k": kk,
			"attrs": {"mass": mass, "state": state, "temperature": temp},
			"A": att, "D": rep, "Q": q, "ratt": rr[0], "rrep": rr[1],
			"heat": int(-cC + cL + 2.0 * cF), "c": maxi(1, n - 1)}

func info(f: String) -> Dictionary:
	if info_cache.has(f):
		return info_cache[f]
	var li := _local_info(f)
	if not li.is_empty():
		info_cache[f] = li
		return li
	var r = client.call_sync("molecule", {"formula": f})
	if r.get("ok", false):
		var d: Dictionary = r["data"]
		d["A"] = float(d.get("A", 0.0))
		d["D"] = float(d.get("D", 0.0))
		var comp: Dictionary = d.get("comp", {})
		var q: int = 3 * int(comp.get("K", 0)) + 2 * int(comp.get("A", 0)) + int(comp.get("F", 0))
		d["Q"] = q
		var rr := _radius_of_q(q)
		d["ratt"] = rr[0]
		d["rrep"] = rr[1]
		d["k"] = int(d.get("k", 1))
		d["heat"] = _heat_of(d.get("comp", {}), p["heat_w"])
		d["c"] = int(d.get("c", max(1, int(d.get("natoms", 1)) - 1)))
		d["attrs"] = d.get("attrs", {"mass": 2.0, "state": 1.0, "temperature": 1.0})
		info_cache[f] = d
		return d
	return {}

## 温度维度权重：heat = wC·n_C + wL·n_L + wF·n_F（默认 C=-1, L=1, F=2；可调）
func _heat_of(comp: Dictionary, w: Dictionary) -> int:
	return int(round(float(w.get("C", 0.0)) * int(comp.get("C", 0)) +
			float(w.get("L", 0.0)) * int(comp.get("L", 0)) +
			float(w.get("F", 0.0)) * int(comp.get("F", 0))))

## 散素点数 Q -> (吸引半径, 排斥半径)：R_att = Q 格（至少 1），R_rep ≈ 0.7·Q，封顶 r_cap
func _radius_of_q(q: int) -> Array:
	var capr: int = maxi(1, int(p["r_cap"]))
	return [clampi(q, 1, capr), clampi(int(round(0.7 * float(q))), 1, capr)]

## 修改 r_cap 后调用：重算所有类型/分子的半径，并重建空间哈希
func recompute_radii() -> void:
	for f in info_cache.keys():
		var d: Dictionary = info_cache[f]
		var rr := _radius_of_q(int(d.get("Q", 0)))
		d["ratt"] = rr[0]
		d["rrep"] = rr[1]
	for id in range(mols.size()):
		var m = mols[id]
		if m["dead"]:
			continue
		var d2: Dictionary = info_cache.get(m["f"], {})
		if not d2.is_empty():
			m["ratt"] = int(d2["ratt"])
			m["rrep"] = int(d2["rrep"])
			m["Q"] = int(d2.get("Q", 0))
			m_ra[id] = int(d2["ratt"])
			m_rr[id] = int(d2["rrep"])
			m_A[id] = float(m["A"])
			m_D[id] = float(m["D"])
	rebuild_hash()

## 空间哈希：按 r_cap 大小的格子分桶（每拍重建；桶内只存锚点，避免重复）
func rebuild_hash() -> void:
	_hash.clear()
	_hash_cell = maxi(2, int(p["r_cap"]))
	for id in range(mols.size()):
		var m = mols[id]
		if m["dead"]:
			continue
		var a: Vector2i = m["anchor"]
		var key := Vector2i(floori(float(a.x) / _hash_cell), floori(float(a.y) / _hash_cell))
		if _hash.has(key):
			_hash[key].append(id)
		else:
			_hash[key] = [id]

## 取 3x3 哈希桶内的候选分子（哈希格 = r_cap，故可覆盖任意 ≤ r_cap 的作用半径）
func hash_candidates(id: int) -> Array:
	var out: Array = []
	var a: Vector2i = mols[id]["anchor"]
	var kr := floori(float(a.x) / _hash_cell)
	var kc := floori(float(a.y) / _hash_cell)
	for dr in range(-1, 2):
		for dc in range(-1, 2):
			var key := Vector2i(kr + dr, kc + dc)
			if _hash.has(key):
				out.append_array(_hash[key])
	return out

## 修改热值权重后调用：刷新类型缓存与所有分子的 heat（负热值允许）
func recompute_heat() -> void:
	for f in info_cache.keys():
		var d: Dictionary = info_cache[f]
		d["heat"] = _heat_of(d.get("comp", {}), p["heat_w"])
	for m in mols:
		if m["dead"]:
			continue
		var d2: Dictionary = info_cache.get(m["f"], {})
		if not d2.is_empty():
			m["heat"] = int(d2["heat"])

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

## 用内核批量返回的信息预热缓存（投料前调用一次，不在热路径）
func prime_infos(infos: Dictionary) -> void:
	for f in infos.keys():
		var d = infos[f]
		if d == null or not (d is Dictionary) or (d as Dictionary).is_empty():
			continue
		var e: Dictionary = (d as Dictionary).duplicate(true)
		e["A"] = float(e.get("A", 0.0))
		e["D"] = float(e.get("D", 0.0))
		var comp: Dictionary = e.get("comp", {})
		var q2 := int(3 * int(comp.get("K", 0)) + 2 * int(comp.get("A", 0)) + int(comp.get("F", 0)))
		var rr2 := _radius_of_q(q2)
		e["Q"] = q2
		e["ratt"] = rr2[0]
		e["rrep"] = rr2[1]
		info_cache[String(f)] = e

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
		"ratt": int(d.get("ratt", 1)), "rrep": int(d.get("rrep", 1)), "Q": int(d.get("Q", 0)),
		"heat": int(d.get("heat", 0)), "c": int(d.get("c", 1)),
		"natoms": int(d.get("natoms", 1)),
		"gacc": 0.0, "facc": 0.0, "dead": false, "locks": [],
		"vx": 0.0, "vy": 0.0, "px": 0.0, "py": 0.0, "fx": 0.0, "fy": 0.0,
	}
	for s in shape:
		var c: Vector2i = wrap_cell(anchor + s)
		m["cells"].append(c)
		grid[_idx(c)] = next_id
	mols.append(m)
	m_ax.append(anchor.x)
	m_ay.append(anchor.y)
	m_A.append(float(m["A"]))
	m_D.append(float(m["D"]))
	m_ra.append(int(m["ratt"]))
	m_rr.append(int(m["rrep"]))
	m_alive.append(1)
	next_id += 1
	_count_species(f, 1)
	alive += 1
	stats["n"] = alive
	return m["id"]

func _count_species(f: String, d: int) -> void:
	species_count[f] = int(species_count.get(f, 0)) + d
	if species_count[f] <= 0:
		species_count.erase(f)
	stats["species"] = species_count.size()

func _alive_count() -> int:
	return alive

func remove(id: int) -> void:
	if id < 0 or id >= mols.size():
		return
	var m = mols[id]
	if m["dead"]:
		return
	m["dead"] = true
	m_alive[id] = 0
	for c in m["cells"]:
		grid[_idx(c)] = -1
	_count_species(m["f"], -1)
	alive = maxi(0, alive - 1)
	stats["n"] = alive

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
	if bool(p.get("plateau", true)):
		return Tend          # 恒温平台：降到终温后保持不变
	return Tend * exp(-3.0 * (t - ct) / ct)   # 关闭平台：继续降向 0

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
	var ax := m_ax[id]
	var ay := m_ay[id]
	var A := m_A[id]
	var ra: int = maxi(1, m_ra[id])
	var KA := float(p["KA"])
	var KR := float(p["KR"])
	var f := Vector2.ZERO
	for oid in hash_candidates(id):
		if oid == id or m_alive[oid] == 0:
			continue
		var dx: int = m_ax[oid] - ax
		var dy: int = m_ay[oid] - ay
		var d: int = maxi(absi(dx), absi(dy))
		if d <= 0:
			continue
		var rr: int = maxi(1, m_rr[oid])
		if d > maxi(ra, rr):
			continue
		var w: float = KA * A * decay(d, ra) - KR * m_D[oid] * decay(d, rr)
		if abs(w) < 0.001:
			continue
		var len2: float = float(dx * dx + dy * dy)
		if len2 < 0.0001:
			f += Vector2(0.1, 0.1) * w
		else:
			var inv: float = 1.0 / sqrt(len2)
			f += Vector2(dx * inv, dy * inv) * w
	return f

func mobility(m) -> float:
	var s := float(m["state"])
	if s < 1.0:
		return float(p["mob_gas"])
	elif s < 2.0:
		return float(p["mob_liq"])
	return float(p["mob_solid"])

## 锁连通分量（用于"锁团整体下落"：锁住的分子作为一个刚体一起移动）
func lock_component(id: int, cap_n: int = 6000) -> Array:
	var comp: Array = [id]
	var seen := {id: true}
	var i := 0
	while i < comp.size() and comp.size() < cap_n:
		var cur: int = comp[i]
		i += 1
		for nb in mols[cur]["locks"]:
			var nbi := int(nb)
			if nbi < 0 or nbi >= mols.size() or seen.has(nbi):
				continue
			if mols[nbi]["dead"]:
				continue
			seen[nbi] = true
			comp.append(nbi)
	return comp

## 整团平移：所有成员同步移动 step，任何目标格冲突/越界则整团不动
func try_move_group(ids: Array, step: Vector2i) -> bool:
	var own := {}
	for id in ids:
		own[int(id)] = true
	var targets := {}
	for id in ids:
		var m = mols[int(id)]
		for c in m["cells"]:
			var raw: Vector2i = c + step
			if not in_bounds(raw):
				return false
			var nt: Vector2i = wrap_cell(raw)
			if targets.has(nt):
				return false
			targets[nt] = int(id)
	for nt in targets.keys():
		var cur := grid[_idx(nt)]
		if cur != -1 and not own.has(cur):
			return false
	for id in ids:
		for c in mols[int(id)]["cells"]:
			grid[_idx(c)] = -1
	for id in ids:
		var m = mols[int(id)]
		m["anchor"] = wrap_cell(m["anchor"] + step)
		var nc := []
		for c in m["cells"]:
			var t: Vector2i = wrap_cell(c + step)
			nc.append(t)
			grid[_idx(t)] = int(id)
		m["cells"] = nc
		m_ax[int(id)] = m["anchor"].x
		m_ay[int(id)] = m["anchor"].y
	stats["moves"] = int(stats.get("moves", 0)) + ids.size()
	return true

## ---------------- T96：推挤链 / 团簇动量 / 团簇整体平移 ----------------
## 与 alchemy/t95_collision.py 的 v1（P1 链式推挤）/ v2（P2 团簇动量）同口径，
## 但这里逐分子位移改为「速度积分 + 累积位移」（P2），并保留 push_enable=false 的旧行为。

func _push_fail() -> void:
	stats["n_push_fail"] = int(stats.get("n_push_fail", 0)) + 1

func _clamp_vel(vx: float, vy: float) -> Vector2:
	var vmax := float(p["push_vmax"])
	var spd := sqrt(vx * vx + vy * vy)
	if spd > vmax and spd > 0.000001:
		return Vector2(vx / spd * vmax, vy / spd * vmax)
	return Vector2(vx, vy)

func _unit_for(id: int) -> Array:
	# P2：被粘附锁连成一片的分子作为刚体单元参与推挤链
	if not bool(p["push_enable"]):
		return [id]
	if mols[id]["locks"].is_empty():
		return [id]
	var comp := lock_component(id)
	if comp.size() <= 1:
		return [id]
	return comp

func _unit_mass(ids: Array) -> float:
	var mm := 0.0
	for i in ids:
		mm += float(mols[int(i)]["mass"])
	return mm

func _unit_vel(ids: Array) -> Vector2:
	var v := Vector2.ZERO
	for i in ids:
		v += Vector2(float(mols[int(i)]["vx"]), float(mols[int(i)]["vy"]))
	return v / float(maxi(1, ids.size()))

func _unit_force_n(ids: Array, nvec: Vector2) -> float:
	var s := 0.0
	for i in ids:
		var mm = mols[int(i)]
		s += Vector2(float(mm["fx"]), float(mm["fy"])).dot(nvec)
	return s

func _stick_j(ids: Array, own: Dictionary) -> float:
	var j := 0.0
	var KA := float(p["KA"])
	var KR := float(p["KR"])
	for i in ids:
		var m = mols[int(i)]
		for lk in m["locks"]:
			var li := int(lk)
			if own.has(li) or li >= mols.size() or mols[li]["dead"]:
				continue
			var o = mols[li]
			var w := KA * float(m["A"]) * decay(1, int(m["ratt"])) - KR * float(o["D"]) * decay(1, int(o["rrep"]))
			j += max(0.0, w)
	return j

func _floor_j(ids: Array, own: Dictionary) -> float:
	# 下方有边界/非链内分子支撑 → 静摩擦上限 mu·M·g
	var G := float(p["gravity_G"])
	if G <= 0.000001:
		return 0.0
	for i in ids:
		for c in mols[int(i)]["cells"]:
			var below: Vector2i = c + Vector2i(1, 0)
			if not in_bounds(below):
				return float(p["push_mu"]) * _unit_mass(ids) * G
			var oid := grid[_idx(wrap_cell(below))]
			if oid >= 0 and not own.has(oid):
				return float(p["push_mu"]) * _unit_mass(ids) * G
	return 0.0

func _locks_ok_after(own: Dictionary, step: Vector2i) -> bool:
	var lr := int(p["lock_r"])
	for i in own.keys():
		var m = mols[int(i)]
		var na: Vector2i = wrap_cell(m["anchor"] + step)
		for lk in m["locks"]:
			var li := int(lk)
			if own.has(li) or li >= mols.size() or mols[li]["dead"]:
				continue
			if _cheb(mols[li]["anchor"], na) > lr:
				return false
	return true

func _add_impulse(ids: Array, du: float, nvec: Vector2) -> void:
	if absf(du) < 0.000001:
		return
	for i in ids:
		var m = mols[int(i)]
		var v := _clamp_vel(float(m["vx"]) + du * nvec.x, float(m["vy"]) + du * nvec.y)
		m["vx"] = v.x
		m["vy"] = v.y

func _commit_shift(ids: Array, step: Vector2i) -> void:
	for i in ids:
		for c in mols[int(i)]["cells"]:
			grid[_idx(c)] = -1
	for i in ids:
		var m = mols[int(i)]
		m["anchor"] = wrap_cell(m["anchor"] + step)
		var nc := []
		for c in m["cells"]:
			var t: Vector2i = wrap_cell(c + step)
			nc.append(t)
			grid[_idx(t)] = int(i)
		m["cells"] = nc
		m_ax[int(i)] = m["anchor"].x
		m_ay[int(i)] = m["anchor"].y
		m["px"] = float(m["px"]) - float(step.x)
		m["py"] = float(m["py"]) - float(step.y)
	stats["moves"] = int(stats.get("moves", 0)) + ids.size()

func _unit_stats(ids: Array, nvec: Vector2) -> Dictionary:
	var M := _unit_mass(ids)
	var v := _unit_vel(ids)
	return {"ids": ids, "M": M, "u": v.dot(nvec), "fn": _unit_force_n(ids, nvec)}

## P1/P2 链式推挤：先构造整条链（≤push_kmax 个分子），逐对 J_A/J_B 判定，
## 全部检查通过才统一提交；任何一步失败整链不动（元素守恒、footprint 完整）。
func _try_push_chain(id: int, step: Vector2i, gravity_ctx: bool = false) -> bool:
	if step == Vector2i.ZERO:
		return false
	var kmax := int(p["push_kmax"])
	var push_e := float(p["push_e"])
	var nvec := Vector2(float(step.x), float(step.y)).normalized()
	var chain: Array = []
	var own := {}
	var cur: Array = [id]
	own[id] = true
	if cur.size() > kmax:
		_push_fail()
		return false
	while true:
		for cid in cur:
			for c in mols[int(cid)]["cells"]:
				if not in_bounds(c + step):
					_push_fail()
					return false
		chain.append(cur.duplicate())
		var blockers := {}
		for cid in cur:
			for c in mols[int(cid)]["cells"]:
				var nt: Vector2i = wrap_cell(c + step)
				var oid := grid[_idx(nt)]
				if oid >= 0 and not own.has(oid):
					blockers[oid] = true
		if blockers.is_empty():
			break
		var units: Array = []
		for bid in blockers.keys():
			units.append(_unit_for(int(bid)))
		if units.size() > 1:
			_push_fail()
			return false
		var nxt: Array = units[0]
		if own.size() + nxt.size() > kmax:
			_push_fail()
			return false
		for nid in nxt:
			if own.has(int(nid)):
				_push_fail()
				return false
			own[int(nid)] = true
		cur = nxt
		if own.size() > kmax:
			_push_fail()
			return false
	var own_ids: Array = []
	for k in own.keys():
		own_ids.append(int(k))
	var occ := {}
	for grp in chain:
		for gid in grp:
			for c2 in mols[int(gid)]["cells"]:
				var nt2: Vector2i = wrap_cell(c2 + step)
				if occ.has(nt2):
					_push_fail()
					return false
				occ[nt2] = int(gid)
	for nt3 in occ.keys():
		var curid := grid[_idx(nt3)]
		if curid >= 0 and not own.has(curid):
			_push_fail()
			return false
	if not _locks_ok_after(own, step):
		_push_fail()
		return false
	var ustats: Array = []
	for grp in chain:
		ustats.append(_unit_stats(grp, nvec))
	for k in range(chain.size() - 1):
		var A: Dictionary = ustats[k]
		var B: Dictionary = ustats[k + 1]
		var MA: float = float(A["M"])
		var MB: float = float(B["M"])
		var uA: float = float(A["u"])
		var uB: float = float(B["u"])
		if MA < float(p["push_m_min_ratio"]) * MB or MB <= 0.0:
			_push_fail()
			return false
		var JA: float = MA * max(0.0, uA) + max(0.0, float(A["fn"]))
		if gravity_ctx:
			JA += MA * float(p["gravity_G"])
		var JB: float = MB * max(0.0, -uB) + _stick_j(B["ids"], own) + _floor_j(B["ids"], own)
		if JA <= JB:
			_push_fail()
			return false
		var uA2: float = (MA * uA + MB * uB - MB * push_e * (uA - uB)) / (MA + MB)
		var uB2: float = (MA * uA + MB * uB + MA * push_e * (uA - uB)) / (MA + MB)
		_add_impulse(A["ids"], uA2 - uA, nvec)
		_add_impulse(B["ids"], uB2 - uB, nvec)
		ustats[k + 1]["u"] = uB2
	_commit_shift(own_ids, step)
	stats["n_push"] = int(stats.get("n_push", 0)) + 1
	var ch: Dictionary = stats["chain_hist"]
	ch[own_ids.size()] = int(ch.get(own_ids.size(), 0)) + 1
	return true

func try_move(id: int, step: Vector2i, gravity_ctx: bool = false) -> bool:
	var m = mols[id]
	if m["dead"]:
		return false
	var raw_na: Vector2i = m["anchor"] + step
	if not in_bounds(raw_na):
		return false
	var na: Vector2i = wrap_cell(raw_na)
	for lk in m["locks"]:
		var o = mols[int(lk)]
		if o["dead"]:
			continue
		if _cheb(o["anchor"], na) > int(p["lock_r"]):
			return false
	if footprint_free(m["shape"], na, id):
		for cell in m["cells"]:
			grid[_idx(cell)] = -1
		var ncells: Array = []
		for sh in m["shape"]:
			var c: Vector2i = wrap_cell(na + sh)
			grid[_idx(c)] = id
			ncells.append(c)
		m["anchor"] = na
		m["cells"] = ncells
		m_ax[id] = na.x
		m_ay[id] = na.y
		m["px"] = float(m["px"]) - float(step.x)
		m["py"] = float(m["py"]) - float(step.y)
		stats["moves"] = int(stats.get("moves", 0)) + 1
		return true
	if bool(p["push_enable"]):
		return _try_push_chain(id, step, gravity_ctx)
	# 旧行为：只能把单格分子挤开一步（重压轻）
	if int(m["k"]) != 1:
		return false
	var oid := grid[_idx(na)]
	if oid < 0 or oid == id:
		return false
	var o2 = mols[oid]
	if int(o2["k"]) != 1 or o2["dead"]:
		return false
	if float(m["mass"]) < float(o2["mass"]):
		return false
	var raw_back: Vector2i = na - step
	if not in_bounds(raw_back):
		return false
	var back: Vector2i = wrap_cell(raw_back)
	if grid[_idx(back)] != -1 and grid[_idx(back)] != oid:
		return false
	grid[_idx(o2["anchor"])] = -1
	o2["anchor"] = back
	o2["cells"] = [back]
	grid[_idx(back)] = oid
	for cell in m["cells"]:
		grid[_idx(cell)] = -1
	var ncells2: Array = []
	for sh in m["shape"]:
		var c2: Vector2i = wrap_cell(na + sh)
		grid[_idx(c2)] = id
		ncells2.append(c2)
	m["anchor"] = na
	m["cells"] = ncells2
	m_ax[id] = na.x
	m_ay[id] = na.y
	stats["moves"] = int(stats.get("moves", 0)) + 1
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
	var _t0 := Time.get_ticks_usec()
	stats["T_env"] = schedule_T(float(tick))
	# 1) 重力：整格下移（锁团作为刚体整体下落，避免被锁在悬空处）
	var G := float(p["gravity_G"])
	for id in range(mols.size()):
		if not mols[id]["dead"]:
			mols[id]["gacc"] = float(mols[id]["gacc"]) + G * float(mols[id]["mass"])
	var moved := {}
	for id in range(mols.size()):
		if moved.has(id) or mols[id]["dead"]:
			continue
		var guard: int = 0
		while float(mols[id]["gacc"]) >= 1.0 and guard < 4:
			guard += 1
			var ok := false
			if bool(p.get("lock_rigid_fall", true)) and not mols[id]["locks"].is_empty():
				var comp := lock_component(id)
				if comp.size() > 1:
					ok = try_move_group(comp, Vector2i(1, 0))
					if ok:
						for cid in comp:
							moved[int(cid)] = true
							mols[int(cid)]["gacc"] = float(mols[int(cid)]["gacc"]) - 1.0
				else:
					ok = try_move(id, Vector2i(1, 0), true)
					if ok:
						moved[id] = true
						mols[id]["gacc"] = float(mols[id]["gacc"]) - 1.0
			else:
				ok = try_move(id, Vector2i(1, 0), true)
				if ok:
					moved[id] = true
					mols[id]["gacc"] = float(mols[id]["gacc"]) - 1.0
			if not ok:
				break
	rebuild_hash()
	stats["ms_g"] = float(stats.get("ms_g", 0.0)) + float(Time.get_ticks_usec() - _t0) / 1000.0
	var _t1 := Time.get_ticks_usec()
	# 2) 三素力驱动 + T96 P2 速度积分（push_enable=false 时退回旧 facc 位移）
	_order.clear()
	for id in range(mols.size()):
		if not mols[id]["dead"]:
			_order.append(id)
	_order.shuffle()
	if bool(p["push_enable"]):
		var gamma := float(p["push_gamma"])
		for id in _order:
			if id >= mols.size() or mols[id]["dead"]:
				continue
			var m = mols[id]
			var f := force_on(id)
			m["fx"] = f.x
			m["fy"] = f.y
			var Mf: float = max(0.05, float(m["mass"]))
			var nv := _clamp_vel((1.0 - gamma) * float(m["vx"]) + (f.x / Mf) * F2V,
					(1.0 - gamma) * float(m["vy"]) + (f.y / Mf) * F2V)
			m["vx"] = nv.x
			m["vy"] = nv.y
			m["px"] = float(m["px"]) + nv.x
			m["py"] = float(m["py"]) + nv.y
			var fguard: int = 0
			while absf(float(m["px"])) >= 1.0 and fguard < 4:
				fguard += 1
				var sx: int = 1 if float(m["px"]) > 0.0 else -1
				if not try_move(id, Vector2i(sx, 0)):
					m["px"] = 0.0
					break
			fguard = 0
			while absf(float(m["py"])) >= 1.0 and fguard < 4:
				fguard += 1
				var sy: int = 1 if float(m["py"]) > 0.0 else -1
				if not try_move(id, Vector2i(0, sy)):
					m["py"] = 0.0
					break
		# 2b) T96：锁连通分量净力→整团平移（每团每拍最多一次）
		if bool(p["group_push_enable"]):
			var seen := {}
			var gi := 0
			while gi < mols.size():
				if mols[gi]["dead"] or seen.has(gi) or mols[gi]["locks"].is_empty():
					gi += 1
					continue
				var comp := lock_component(gi)
				if comp.size() < 2:
					gi += 1
					continue
				for cid in comp:
					seen[int(cid)] = true
				var Mg := 0.0
				var fsum := Vector2.ZERO
				for cid in comp:
					var cm = mols[int(cid)]
					Mg += float(cm["mass"])
					fsum += Vector2(float(cm["fx"]), float(cm["fy"]))
				if Mg > 0.0 and (fsum / Mg).length() >= float(p["group_push_thresh"]):
					var an := (fsum / Mg).normalized()
					var best := DIRS8[0]
					var bestdot := -2.0
					for d in DIRS8:
						var dot := Vector2(d).normalized().dot(an)
						if dot > bestdot:
							bestdot = dot
							best = d
					if try_move_group(comp, best):
						stats["n_group_push"] = int(stats.get("n_group_push", 0)) + 1
					else:
						stats["n_group_push_fail"] = int(stats.get("n_group_push_fail", 0)) + 1
				gi += 1
		var sp_sum := 0.0
		var sp_n := 0
		for id in range(mols.size()):
			if mols[id]["dead"]:
				continue
			var mm = mols[id]
			sp_sum += sqrt(float(mm["vx"]) * float(mm["vx"]) + float(mm["vy"]) * float(mm["vy"]))
			sp_n += 1
		stats["mean_speed"] = sp_sum / float(maxi(1, sp_n))
	else:
		for id in _order:
			if id >= mols.size() or mols[id]["dead"]:
				continue
			var m = mols[id]
			var f := force_on(id)
			m["fx"] = f.x
			m["fy"] = f.y
			var mag := f.length()
			if mag < 0.02:
				continue
			var best := Vector2i(0, 0)
			var bestdot: float = -1.0
			for d in DIRS8:
				var dot: float = Vector2(d).normalized().dot(f.normalized())
				if dot > bestdot:
					bestdot = dot
					best = d
			var facc: float = min(3.0, float(m["facc"]) + mag * float(p["force_scale"]) * mobility(m))
			var fguard2: int = 0
			while facc >= 1.0 and fguard2 < 4:
				fguard2 += 1
				if try_move(id, best):
					facc -= 1.0
				else:
					facc = min(facc, 0.99)
					break
			m["facc"] = facc
		stats["mean_speed"] = 0.0
	stats["ms_f"] = float(stats.get("ms_f", 0.0)) + float(Time.get_ticks_usec() - _t1) / 1000.0
	var _t2 := Time.get_ticks_usec()
	# 3) 粘附锁
	rebuild_locks()
	stats["ms_l"] = float(stats.get("ms_l", 0.0)) + float(Time.get_ticks_usec() - _t2) / 1000.0
	var _t3 := Time.get_ticks_usec()
	# 4) 反应：相邻对 + 局部温度门控 + 异步 resolve
	_react_phase()
	stats["ms_r"] = float(stats.get("ms_r", 0.0)) + float(Time.get_ticks_usec() - _t3) / 1000.0

func _react_phase() -> void:
	# 背压：内核回复跟不上时先不发起新反应，避免请求雪崩
	if client == null:
		return
	var outstanding: int = int(client.pending_count()) + pending_res
	var budget: int = min(int(max_react_per_tick), int(p.get("max_react", max_react_per_tick)))
	budget -= outstanding
	if budget <= 0:
		return
	var sent = 0
	var seen := {}
	for id in range(mols.size()):
		if sent >= budget:
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
				if rng.randf() > float(p["p_react"]):
					continue
				var tl := local_T([cell, c])
				var csum := int(m["c"]) + int(o["c"])
				if tl < float(csum) + float(p["react_margin"]):
					continue
				stats["pairs"] = int(stats["pairs"]) + 1
				pending_res += 1
				sent += 1
				var ctx := {"a": id, "b": oid, "cell": cell, "T": tl, "gen": epoch}
				client.resolve_async([{"formula": m["f"]}, {"formula": o["f"]}], tl, ctx, Callable(self, "on_resolve"))
	stats["T_hot"] = stats["T_env"]

func on_resolve(resp: Dictionary, ctx: Dictionary) -> void:
	pending_res = max(0, pending_res - 1)
	if not resp.get("ok", false):
		return
	if int(ctx.get("gen", -1)) != epoch:
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
			if _alive_count() >= W * H:
				return
			for attempt in range(12):
				var a := Vector2i(rng.randi_range(0, H - 1), rng.randi_range(0, W - 1))
				if place(f, a) >= 0:
					break

## 叠加投料：不重置世界，按清单逐个放入，返回实际放入个数
func add_feed(items: Array) -> int:
	var placed := 0
	for item in items:
		var f := String(item.get("formula", ""))
		var n := int(item.get("count", 0))
		if f == "" or n <= 0:
			continue
		var done := 0
		for i in range(n):
			if _alive_count() >= W * H:
				return placed
			var ok := false
			for attempt in range(12):
				var a := Vector2i(rng.randi_range(0, H - 1), rng.randi_range(0, W - 1))
				if place(f, a) >= 0:
					ok = true
					break
			if not ok:
				break
			done += 1
			placed += 1
	return placed

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
