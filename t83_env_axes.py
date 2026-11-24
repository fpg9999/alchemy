"""T83: 九元素环境（三轴 + 三素力）——质量/物态/温度 + 吸引/覆盖/排斥

相对 T82 的变化
----------------
1) 同时打开物质三轴（alchemy/attrs.py，按层平均）：
   * 质量轴  -> 重力：轻 / 中 / 重 -> 上升 / 悬浮 / 下沉（竖直方向，有上下边界）；
   * 物态轴  -> 碰撞：气（穿过，可交换）/ 液（游泳，减速，可与气交换）/ 固（阻挡，不可进入）；
   * 温度轴  -> 恒素场 rho：热分子富集、冷分子稀薄；环境初始温度 1000°C，随拍数冷却到 25°C。
2) 三素力（alchemy/three_su.py）：吸引力 / 覆盖半径 / 排斥力 -> 位移向量 + 粘附锁（w>=1）。
3) 反应：相邻对以 p = p0 * 物态模式倍率 * 恒素门控(0.15+0.85*rho) 触发规则 1~11 完全反应。
4) 世界为方格，每格最多 1 个分子；上下左右均为硬边界（重物沉底、轻物浮顶）。
5) 分子数大幅增加（默认 240x160 世界、7,000 个分子）。

只读内核（attrs / three_su / natural_engine），不修改 alchemy/ 包内代码。
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import random
import time

from alchemy import attrs as A
from alchemy import three_su as TS
from alchemy.core.elements import ORDER as ELEM_ORDER
from natural_engine import complete_products

ELEMS = list(ELEM_ORDER)
ELEM_SET = set(ELEMS)

BASE = os.path.dirname(os.path.abspath(__file__))
LOAD_FILE = os.path.join(BASE, "t62_loads.json")
CATALOG_FILE = os.path.join(BASE, "t4_catalog_all_validated.json")

DIRS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]

# 物态对（0=气,1=液,2=固）的反应模式倍率（沿用 T78 表）
MODE_MULT = {
    (0, 0): 0.18, (0, 1): 0.45, (1, 0): 0.45,
    (1, 1): 0.60, (0, 2): 0.80, (2, 0): 0.80,
    (1, 2): 0.90, (2, 1): 0.90, (2, 2): 1.00,
}
# 物态 -> 迁移率乘子（气最轻快、固最黏滞）
STATE_MOB = {0: 1.00, 1: 0.60, 2: 0.25}
# 质量档 -> 竖直重力项（负=上升，正=下沉）
GRAV = {0: -0.55, 1: 0.0, 2: 0.60}
TIER_NAMES = {
    "mass": ("轻", "中", "重"),
    "state": ("气", "液", "固"),
    "temperature": ("冷", "温", "热"),
}


# ---------------------------------------------------------------------------
# 分子式 / 投料
# ---------------------------------------------------------------------------

def comp_of(formula):
    d = {}
    i = 0
    n = len(formula)
    while i < n:
        ch = formula[i]
        if ch not in ELEM_SET:
            raise ValueError("bad formula %r" % formula)
        i += 1
        num = ""
        while i < n and formula[i].isdigit():
            num += formula[i]
            i += 1
        k = int(num) if num else 1
        d[ch] = d.get(ch, 0) + k
    return d


def vec_of(comp):
    return tuple(comp.get(e, 0) for e in ELEMS)


def natoms_of(comp):
    return sum(comp.values())


def atoms_from_comp(comp):
    out = []
    for e in ELEMS:
        out.extend([e] * comp.get(e, 0))
    return out


def catalog_index():
    cat = json.load(io.open(CATALOG_FILE, encoding="utf-8"))
    return {r["formula"]: r for r in cat}


def load_feed(target=7000, path=LOAD_FILE):
    d = json.load(io.open(path, encoding="utf-8"))
    rows = d["batchA"]["rows"]
    total = sum(r["count"] for r in rows)
    scale = float(target) / total
    out = []
    for r in rows:
        n = max(1, int(round(r["count"] * scale)))
        out.extend([r["formula"]] * n)
    return out, {"target": target, "batch_total": total, "scale": scale,
                 "n_molecules": len(out)}


# ---------------------------------------------------------------------------
# 世界
# ---------------------------------------------------------------------------

class World:
    def __init__(self, W, H, seed, feed, recs, cap=26, p_react=0.01,
                 force_r=2, lock_r=2, lock_w=1.0,
                 e_cells=(10, 20), t0=1000.0, t_end=25.0, cool_k=3.0):
        self.W, self.H = W, H
        self.rng = random.Random(seed)
        self.cap = cap
        self.p_react = p_react
        self.force_r = force_r
        self.lock_r = lock_r
        self.lock_w = lock_w
        self.recs = recs
        self.catalog_set = set(recs)
        # 恒素场
        self.EW, self.EH = e_cells
        self.rho = [[0.5] * self.EW for _ in range(self.EH)]
        self.t0, self.t_end, self.cool_k = t0, t_end, cool_k
        self.Tamb = t0
        self.ticks_total = 1
        # 分子
        self.types = {}
        self.mols = []
        self.cell = {}
        self.locks = {}
        self.next_id = 0
        self.t = 0
        self.force_cache = {}
        self.f_cache = {}
        self.n_react = 0
        self.n_react_fail = 0
        self.new_species = {}
        self.n_moves = 0
        self.n_blocked = 0
        self.n_brown = 0
        self.n_swap = 0
        self.band_react = [0, 0, 0]      # 底/中/上（按世界高度三等分）
        self.mode_counts = {}
        self._place_feed(feed)

    # -- 类型/属性 ------------------------------------------------------
    def ensure_type(self, formula):
        t = self.types.get(formula)
        if t is not None:
            return t
        rec = self.recs.get(formula)
        if rec:
            atoms = tuple(rec["atoms"])
            edges = [tuple(e) for e in rec["edges"]]
        else:
            comp = comp_of(formula)
            atoms = atoms_from_comp(comp)
            edges = []
        comp = comp_of(formula)
        at = A.molecule_attrs(atoms, edges)
        prop = A.property_of(at)
        _g2i = {"低": 0, "中": 1, "高": 2}
        tiers = {k: _g2i[v] for k, v in prop["grades"].items()}
        t = {
            "comp": comp, "vec": vec_of(comp), "natoms": natoms_of(comp),
            "mass": at["mass"], "state": at["state"], "temp": at["temperature"],
            "tiers": tiers, "cell": prop["cell"],
        }
        self.types[formula] = t
        if formula not in self.catalog_set:
            self.new_species.setdefault(formula, {"first_t": self.t,
                                                  "atoms": t["natoms"]})
        return t

    # -- 放置 -----------------------------------------------------------
    def add_mol(self, formula, r, c):
        mid = self.next_id
        self.next_id += 1
        self.ensure_type(formula)
        self.mols.append({"id": mid, "f": formula, "r": r, "c": c, "dead": False})
        self.cell[(r, c)] = mid
        return mid

    def _place_feed(self, feed):
        n = self.W * self.H
        cells = self.rng.sample(range(n), len(feed))
        for formula, idx in zip(feed, cells):
            r, c = divmod(idx, self.W)
            self.add_mol(formula, r, c)

    def _kill(self, mid):
        m = self.mols[mid]
        if m["dead"]:
            return
        m["dead"] = True
        self.cell.pop((m["r"], m["c"]), None)
        for p in self.locks.get(mid, ()):
            self.locks.get(p, set()).discard(mid)
        self.locks.pop(mid, None)

    # -- 温度 / 恒素场 ---------------------------------------------------
    def ambient_T(self, t):
        return self.t_end + (self.t0 - self.t_end) * math.exp(
            -self.cool_k * t / max(1, self.ticks_total - 1))

    def _e_cell(self, r, c):
        return (min(self.EH - 1, r * self.EH // self.H),
                min(self.EW - 1, c * self.EW // self.W))

    def update_rho(self):
        eh, ew = self.EH, self.EW
        hot = [[0] * ew for _ in range(eh)]
        cold = [[0] * ew for _ in range(eh)]
        cnt = [[0] * ew for _ in range(eh)]
        for m in self.mols:
            if m["dead"]:
                continue
            t = self.types[m["f"]]
            a, b = self._e_cell(m["r"], m["c"])
            cnt[a][b] += 1
            if t["tiers"]["temperature"] == 2:
                hot[a][b] += 1
            elif t["tiers"]["temperature"] == 0:
                cold[a][b] += 1
        ambient_bonus = 0.20 * (self.Tamb - self.t_end) / max(1.0, self.t0 - self.t_end)
        new = [[0.0] * ew for _ in range(eh)]
        for i in range(eh):
            for j in range(ew):
                if cnt[i][j]:
                    target = 0.5 + 0.30 * (hot[i][j] - cold[i][j]) / cnt[i][j]
                    target += ambient_bonus
                    target = min(1.0, max(0.0, target))
                else:
                    target = 0.5 + ambient_bonus
                # 邻域平均（环面）
                s = 0.0
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        s += self.rho[(i + di) % eh][(j + dj) % ew]
                nb = s / 9.0
                new[i][j] = min(1.0, max(0.0, self.rho[i][j]
                                       + 0.15 * (nb - self.rho[i][j])
                                       + 0.35 * (target - self.rho[i][j])))
        self.rho = new

    def rho_at(self, r, c):
        a, b = self._e_cell(r, c)
        return self.rho[a][b]

    # -- 力 -------------------------------------------------------------
    def pair_w(self, f_i, f_j, d):
        key = (f_i, f_j, d) if f_i <= f_j else (f_j, f_i, d)
        w = self.force_cache.get(key)
        if w is None:
            w = TS.pair_force(self.types[f_i]["comp"],
                              self.types[f_j]["comp"], d)["w"]
            self.force_cache[key] = w
        return w

    def force_on(self, mid):
        m = self.mols[mid]
        r, c = m["r"], m["c"]
        sx = sy = 0.0
        fr = self.force_r
        H, W = self.H, self.W
        for dr in range(-fr, fr + 1):
            nr = r + dr
            if nr < 0 or nr >= H:
                continue
            for dc in range(-fr, fr + 1):
                nc = c + dc
                if nc < 0 or nc >= W or (dr == 0 and dc == 0):
                    continue
                d = max(abs(dr), abs(dc))
                nb = self.cell.get((nr, nc))
                if nb is None or nb == mid:
                    continue
                w = self.pair_w(m["f"], self.mols[nb]["f"], d)
                if w == 0.0:
                    continue
                sx += w * dc / d
                sy += w * dr / d
        return sx, sy

    def _lock_ok(self, mid, nr, nc):
        for p in self.locks.get(mid, ()):
            pm = self.mols[p]
            if pm["dead"]:
                continue
            if max(abs(pm["r"] - nr), abs(pm["c"] - nc)) > self.lock_r:
                return False
        return True

    def _try_move(self, mid, dr, dc):
        m = self.mols[mid]
        nr = m["r"] + dr
        nc = m["c"] + dc
        if nr < 0 or nr >= self.H or nc < 0 or nc >= self.W:
            self.n_blocked += 1
            return False
        other = self.cell.get((nr, nc))
        ti = self.types[m["f"]]["tiers"]["state"]
        if other is not None:
            # 气态可被挤开：移动者不是固、被挤者也是气 -> 交换
            to = self.types[self.mols[other]["f"]]["tiers"]["state"]
            if ti != 2 and to == 0 and self.rng.random() < 0.5:
                om = self.mols[other]
                self.cell[(nr, nc)] = mid
                self.cell[(m["r"], m["c"])] = other
                m["r"], m["c"], om["r"], om["c"] = nr, nc, m["r"], m["c"]
                self.n_swap += 1
                return True
            self.n_blocked += 1
            return False
        if not self._lock_ok(mid, nr, nc):
            self.n_blocked += 1
            return False
        self.cell.pop((m["r"], m["c"]), None)
        m["r"], m["c"] = nr, nc
        self.cell[(nr, nc)] = mid
        return True

    # -- 反应 -----------------------------------------------------------
    def _products(self, vec):
        v = tuple(vec)
        if v in self.f_cache:
            return self.f_cache[v]
        prods = None
        if sum(v) <= self.cap:
            try:
                prods = complete_products(list(v))
            except Exception:
                prods = None
        self.f_cache[v] = prods
        return prods

    def _try_react(self, i, j, mult):
        mi, mj = self.mols[i], self.mols[j]
        ti, tj = self.types[mi["f"]], self.types[mj["f"]]
        total = tuple(a + b for a, b in zip(ti["vec"], tj["vec"]))
        if sum(total) > self.cap:
            self.n_react_fail += 1
            return False
        prods = self._products(total)
        if not prods or len(prods) > 2:
            self.n_react_fail += 1
            return False
        pf = [p["formula"] for p in prods]
        if len(pf) == 2 and pf[0] == mi["f"] and pf[1] == mj["f"]:
            return False
        if len(pf) == 1 and pf[0] == mi["f"] and ti["natoms"] == sum(total):
            return False
        # 统计：模式 + 反应高度
        si, sj = ti["tiers"]["state"], tj["tiers"]["state"]
        key = "气-气" if si == sj == 0 else (
            "液-液" if si == sj == 1 else (
                "固-固" if si == sj == 2 else "气-液" if {si, sj} <= {0, 1} else "含固"))
        self.mode_counts[key] = self.mode_counts.get(key, 0) + 1
        band = 0 if mi["r"] > 2 * self.H // 3 else (
            2 if mi["r"] < self.H // 3 else 1)
        self.band_react[band] += 1
        # 应用
        self.mols[i]["f"] = pf[0]
        self.ensure_type(pf[0])
        if len(pf) == 2:
            self.mols[j]["f"] = pf[1]
            self.ensure_type(pf[1])
        else:
            self._kill(j)
        self.n_react += 1
        return True

    def react_phase(self):
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        handled = set()
        for i in ids:
            if self.mols[i]["dead"] or i in handled:
                continue
            m = self.mols[i]
            r, c = m["r"], m["c"]
            ti = self.types[m["f"]]
            rho = self.rho_at(r, c)
            gate = 0.15 + 0.85 * rho
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                nr, nc = r + dr, c + dc
                if nr < 0 or nr >= self.H or nc < 0 or nc >= self.W:
                    continue
                nb = self.cell.get((nr, nc))
                if nb is None or nb in handled or self.mols[nb]["dead"]:
                    continue
                tj = self.types[self.mols[nb]["f"]]
                p = (self.p_react * MODE_MULT[(ti["tiers"]["state"],
                                              tj["tiers"]["state"])] * gate)
                if self.rng.random() >= p:
                    continue
                handled.add(i)
                handled.add(nb)
                self._try_react(i, nb, p)
                break

    # -- 粘附锁 ---------------------------------------------------------
    def rebuild_locks(self):
        locks = {}
        for (r, c), mid in list(self.cell.items()):
            for dr, dc in ((0, 1), (1, 0)):
                nr, nc = r + dr, c + dc
                if nr >= self.H or nc >= self.W:
                    continue
                nb = self.cell.get((nr, nc))
                if nb is None:
                    continue
                w = self.pair_w(self.mols[mid]["f"], self.mols[nb]["f"], 1)
                if w >= self.lock_w:
                    locks.setdefault(mid, set()).add(nb)
                    locks.setdefault(nb, set()).add(mid)
        self.locks = locks

    # -- 一拍 -----------------------------------------------------------
    def step(self):
        self.Tamb = self.ambient_T(self.t)
        self.update_rho()
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        for mid in ids:
            m = self.mols[mid]
            if m["dead"]:
                continue
            t = self.types[m["f"]]
            st = t["tiers"]["state"]
            mt = t["tiers"]["mass"]
            sx, sy = self.force_on(mid)
            sy += GRAV[mt]                      # 重力项（行号增大=向下）
            norm = math.hypot(sx, sy)
            dr = dc = 0
            if norm > 1e-9:
                ang = math.atan2(sy, sx)
                k = int(round(ang / (math.pi / 4.0))) % 8
                dr, dc = DIRS[k]
                p = STATE_MOB[st] * min(1.0, 0.25 + 0.75 * norm)
            else:
                p = 0.0
            if self.rng.random() < p:
                if self._try_move(mid, dr, dc):
                    self.n_moves += 1
                    continue
        self.react_phase()
        self.rebuild_locks()

    # -- 统计 -----------------------------------------------------------
    def live_mols(self):
        return [m for m in self.mols if not m["dead"]]

    def composition(self):
        cnt = {}
        for m in self.live_mols():
            cnt[m["f"]] = cnt.get(m["f"], 0) + 1
        return cnt

    def elements(self):
        tot = {e: 0 for e in ELEMS}
        for m in self.live_mols():
            for e, n in self.types[m["f"]]["comp"].items():
                tot[e] += n
        return tot

    def tier_share(self, axis):
        cnt = [0, 0, 0]
        for m in self.live_mols():
            cnt[self.types[m["f"]]["tiers"][axis]] += 1
        n = max(1, sum(cnt))
        return [round(x / n, 4) for x in cnt]

    def y_mean_by_mass(self):
        s = [0.0, 0.0, 0.0]
        n = [0, 0, 0]
        for m in self.live_mols():
            k = self.types[m["f"]]["tiers"]["mass"]
            s[k] += m["r"]
            n[k] += 1
        return [round(s[k] / n[k], 1) if n[k] else None for k in range(3)]

    def clusters(self):
        live = {m["id"]: m for m in self.live_mols()}
        seen = set()
        comps = []
        for mid in live:
            if mid in seen:
                continue
            stack = [mid]
            seen.add(mid)
            size = 0
            while stack:
                u = stack.pop()
                size += 1
                mu = self.mols[u]
                r, c = mu["r"], mu["c"]
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if nr < 0 or nr >= self.H or nc < 0 or nc >= self.W:
                            continue
                        nb = self.cell.get((nr, nc))
                        if nb is not None and nb in live and nb not in seen:
                            seen.add(nb)
                            stack.append(nb)
            comps.append(size)
        comps.sort(reverse=True)
        return comps

    def snapshot(self, t):
        comp = self.composition()
        top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:16]
        comps = self.clusters()
        rho_flat = [v for row in self.rho for v in row]
        mean = sum(rho_flat) / len(rho_flat)
        var = sum((v - mean) ** 2 for v in rho_flat) / len(rho_flat)
        return {
            "t": t,
            "T": round(self.Tamb, 2),
            "n": len(self.live_mols()),
            "n_distinct": len(comp),
            "mols": [[m["r"], m["c"], m["f"]] for m in self.live_mols()],
            "composition": comp,
            "top": top,
            "clusters": {
                "n_components": len(comps),
                "max": comps[0] if comps else 0,
                "mean": round(sum(comps) / len(comps), 3) if comps else 0.0,
                "size_hist": {str(s): comps.count(s) for s in sorted(set(comps))},
                "in_big": sum(s for s in comps if s >= 3),
            },
            "elements": self.elements(),
            "tiers": {
                "mass": self.tier_share("mass"),
                "state": self.tier_share("state"),
                "temperature": self.tier_share("temperature"),
            },
            "y_mean_mass": self.y_mean_by_mass(),
            "rho": {"mean": round(mean, 4), "std": round(math.sqrt(var), 4),
                    "grid": [[round(v, 3) for v in row] for row in self.rho]},
            "n_react": self.n_react,
            "n_react_fail": self.n_react_fail,
            "n_new_species": len(self.new_species),
            "band_react": list(self.band_react),
            "mode_counts": dict(self.mode_counts),
        }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run(W=240, H=160, seed=20261120, target=7000, ticks=900,
        cap=26, p_react=0.01, force_r=2, snap_every=150,
        out="t83_env_result.json", quick=False):
    t_start = time.time()
    recs = catalog_index()
    feed, feed_meta = load_feed(target=target)
    if quick:
        feed = feed[:400]
        ticks = min(ticks, 120)
        W, H = 120, 80
    w = World(W, H, seed, feed, recs, cap=cap, p_react=p_react,
              force_r=force_r)
    w.ticks_total = ticks
    print("world %dx%d  N=%d  cap=%d  p_react=%g  force_r=%d  ticks=%d  T0=%.0f"
          % (W, H, len(w.live_mols()), cap, p_react, force_r, ticks, w.t0))
    snaps = [w.snapshot(0)]
    el0 = w.elements()
    for t in range(1, ticks + 1):
        w.t = t
        w.step()
        if t % snap_every == 0 or t == ticks:
            s = w.snapshot(t)
            snaps.append(s)
            print("t=%4d T=%7.1f N=%5d dist=%4d react=%6d new=%4d "
                  "max_cl=%3d rho=%.2f  y(轻/中/重)=%s  %.1fs"
                  % (t, s["T"], s["n"], s["n_distinct"], s["n_react"],
                     s["n_new_species"], s["clusters"]["max"],
                     s["rho"]["mean"], s["y_mean_mass"],
                     time.time() - t_start))
    el1 = w.elements()
    ok = el0 == el1
    comp = w.composition()
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
    result = {
        "config": {
            "engine": "T83 方格环境：三轴（质量/物态/温度）+ 三素力 + 规则1~11 反应",
            "W": W, "H": H, "seed": seed, "ticks": ticks, "cap": cap,
            "p_react": p_react, "force_r": force_r,
            "lock_w": w.lock_w, "lock_r": w.lock_r,
            "T0": w.t0, "T_end": w.t_end, "cool_k": w.cool_k,
            "e_cells": [w.EW, w.EH],
            "snap_every": snap_every, "quick": quick,
            "feed": feed_meta, "feed_file": "t62_loads.json",
            "runtime_s": round(time.time() - t_start, 2),
        },
        "summary": {
            "n0": snaps[0]["n"], "n_final": snaps[-1]["n"],
            "n_react": w.n_react, "n_react_fail": w.n_react_fail,
            "n_new_species": len(w.new_species),
            "n_moves": w.n_moves, "n_blocked": w.n_blocked,
            "n_brown": w.n_brown, "n_swap": w.n_swap,
            "elements0": el0, "elements1": el1, "conservation_ok": ok,
            "clusters": snaps[-1]["clusters"],
            "tiers": snaps[-1]["tiers"],
            "y_mean_mass": snaps[-1]["y_mean_mass"],
            "rho": {"mean": snaps[-1]["rho"]["mean"],
                    "std": snaps[-1]["rho"]["std"],
                    "grid": snaps[-1]["rho"]["grid"]},
            "band_react": snaps[-1]["band_react"],
            "mode_counts": snaps[-1]["mode_counts"],
            "top": top,
            "new_species": [{"formula": f, "atoms": v["atoms"],
                             "first_t": v["first_t"]}
                            for f, v in sorted(w.new_species.items(),
                                               key=lambda kv: kv[1]["first_t"])],
        },
        "snapshots": snaps,
    }
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)
    print("saved %s  (%.1fs)" % (out, time.time() - t_start))
    print("conservation_ok = %s  N0=%d N=%d react=%d new=%d"
          % (ok, snaps[0]["n"], snaps[-1]["n"], w.n_react, len(w.new_species)))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--W", type=int, default=240)
    ap.add_argument("--H", type=int, default=160)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--target", type=int, default=7000)
    ap.add_argument("--ticks", type=int, default=900)
    ap.add_argument("--cap", type=int, default=26)
    ap.add_argument("--p-react", type=float, default=0.01)
    ap.add_argument("--force-r", type=int, default=2)
    ap.add_argument("--snap-every", type=int, default=150)
    ap.add_argument("--out", default="t83_env_result.json")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    run(W=a.W, H=a.H, seed=a.seed, target=a.target, ticks=a.ticks,
        cap=a.cap, p_react=a.p_react, force_r=a.force_r,
        snap_every=a.snap_every, out=a.out, quick=a.quick)


if __name__ == "__main__":
    main()
