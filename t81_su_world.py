# -*- coding: utf-8 -*-
"""T81 三素相互作用：动态世界验证（方阵环面，8 邻域）
=====================================================
只读 alchemy/three_su.py 的公式，不碰内核。

世界：L×L 方阵环面，每格至多 1 个分子（点粒子），每拍：
  1) 每个分子按周围 3 格内的吸引/排斥净力决定是否跳 1 格（8 方向之一）；
  2) d=1 且 w≥1 的分子对形成**粘附锁**（只锁相对位置，不生成化学键、不改分子式、
     不占价键位点；代码里的 bonds 即"粘附锁登记表"）。锁住的分子受"不拆散"约束：
     若某一步会与锁住的伙伴拉开到 d>1，则这一步不移动；
  3) 可选反应（生长实验）：贴近体的两种食物相邻时按 p_react 合成 A，
     新 A 放到体旁，若与体分子 w≥1 则粘附并入（同样是"粘附锁"，不是化学键）。

实验：
  E1 同种聚集：每种分子 40 个，看最大团/键数/平均团大小
  E1c 对照：关掉力（纯布朗）同配置
  E2 异种混合：6 种各 20 个，看同性键占比 vs 随机配对期望
  E3 体生长：6 个 A 的种子体 + 食物 A/B，反应→新 A→并入；四臂对照

用法：
  python t81_su_world.py --quick          # 小规模自检（约 1 分钟）
  python t81_su_world.py --full           # 正式（后台跑）
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import random
import sys
import time

from alchemy import three_su as TS
from alchemy.core.elements import ORDER as ELEM_ORDER
from natural_engine import complete_products

BASE = os.path.dirname(os.path.abspath(__file__))

DIRS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]
DS = {p: 1.0 for p in DIRS}
DS[(1, 1)] = DS[(1, -1)] = DS[(-1, 1)] = DS[(-1, -1)] = 1.0

P_BROWN = 0.05
P_MOVE_WEAK = 1.0     # |S|≥1 一定走一步
REACT_P = 0.5


def torus_delta(a, b, L):
    d = a - b
    if d > L // 2:
        d -= L
    elif d < -L // 2:
        d += L
    return d


class World(object):
    def __init__(self, L, seed, use_force=True):
        self.L = L
        self.rng = random.Random(seed)
        self.use_force = use_force
        self.mols = []          # list of Mol
        self.grid = {}          # (r,c) -> mol id
        self.types = []         # list of formula
        self.tidx = {}          # formula -> type idx
        self.comp = []          # type -> comp dict
        self.sc = []            # type -> scores
        self.jac = {}           # (ti,tj) -> J
        self.bonds = {}         # frozenset(id_i,id_j) -> w
        self.next_id = 0
        self.n_encounters = 0

    # ---------- 分子 ----------
    def add_type(self, formula):
        if formula in self.tidx:
            return self.tidx[formula]
        ti = len(self.types)
        self.types.append(formula)
        self.tidx[formula] = ti
        c = TS.parse_formula(formula)
        self.comp.append(c)
        self.sc.append(TS.scores(c))
        return ti

    def add_mol(self, formula, pos=None):
        ti = self.add_type(formula)
        free = None
        if pos is not None and pos not in self.grid:
            free = pos
        if free is None:
            free = self.random_free_cell()
            if free is None:
                return None
        mid = self.next_id
        self.next_id += 1
        self.mols.append({"id": mid, "ti": ti, "pos": free, "dead": False})
        self.grid[free] = mid
        return mid

    def random_free_cell(self):
        L = self.L
        for _ in range(200):
            p = (self.rng.randrange(L), self.rng.randrange(L))
            if p not in self.grid:
                return p
        for r in range(L):
            for c in range(L):
                if (r, c) not in self.grid:
                    return (r, c)
        return None

    def neighbours(self, pos, rmax=3):
        """返回 [(mid, d)]：切比雪夫距离 d（环面）。"""
        L = self.L
        r0, c0 = pos
        out = []
        for dr in range(-rmax, rmax + 1):
            for dc in range(-rmax, rmax + 1):
                if dr == 0 and dc == 0:
                    continue
                p = ((r0 + dr) % L, (c0 + dc) % L)
                mid = self.grid.get(p)
                if mid is None:
                    continue
                out.append((mid, p, max(abs(dr), abs(dc))))
        return out

    def _force(self, i, j, d):
        si = self.sc[self.mols[i]["ti"]]
        sj = self.sc[self.mols[j]["ti"]]
        ratt = max(si["r_att"], sj["r_att"])
        rrep = max(si["r_rep"], sj["r_rep"])
        if d > ratt:
            return 0.0
        key = (self.mols[i]["ti"], self.mols[j]["ti"])
        jj = self.jac.get(key)
        if jj is None:
            jj = TS.overlap(self.comp[self.mols[i]["ti"]], self.comp[self.mols[j]["ti"]])[0]
            self.jac[key] = jj
            self.jac[(key[1], key[0])] = jj
        att = TS.K_A * math.sqrt(si["A"] * sj["A"]) / 3.0 * jj * TS.decay(d, ratt)
        rep = 0.0
        if d <= rrep:
            rep = TS.K_R * math.sqrt(si["D"] * sj["D"]) / 3.0 * jj * TS.decay(d, rrep)
        return att - rep

    def _bonds_of(self, i):
        return [k for k in self.bonds if i in k]

    def _adjacent_pairs(self):
        out = set()
        for i in range(len(self.mols)):
            if self.mols[i]["dead"]:
                continue
            for (j, p, d) in self.neighbours(self.mols[i]["pos"], rmax=1):
                if d == 1 and j > i and not self.mols[j]["dead"]:
                    out.add((i, j))
        return out

    def _comp_of(self, seed_ids, thr=None):
        thr = TS.W_STRONG if thr is None else thr
        adj = {}
        for k, w in self.bonds.items():
            if w < thr:
                continue
            a, b = tuple(k)
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        for s in seed_ids:
            if s not in adj:
                continue
            seen = {s}
            stack = [s]
            while stack:
                u = stack.pop()
                for v in adj[u]:
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            return seen
        return set()

    def step(self, react=None):
        L = self.L
        prev_adj = self._adjacent_pairs()
        order = list(range(len(self.mols)))
        self.rng.shuffle(order)
        moved = 0
        for i in order:
            m = self.mols[i]
            if m["dead"]:
                continue
            pos = m["pos"]
            nbrs = self.neighbours(pos)
            sx = sy = 0.0
            for (j, p, d) in nbrs:
                w = self._force(i, j, d)
                if abs(w) < TS.W_WEAK:
                    continue
                dr = torus_delta(p[0], pos[0], L)
                dc = torus_delta(p[1], pos[1], L)
                n = math.hypot(dr, dc) or 1.0
                sx += w * dr / n
                sy += w * dc / n
            mag = math.hypot(sx, sy)
            dpos = None
            if self.use_force and mag >= TS.W_WEAK:
                # 选与合力夹角最小的 8 方向
                best = None
                for (dr, dc) in DIRS:
                    dot = (sx * dr + sy * dc) / math.hypot(dr, dc)
                    if best is None or dot > best[0]:
                        best = (dot, dr, dc)
                p = 0.95 if mag >= P_MOVE_WEAK else max(0.1, mag)
                if self.rng.random() < p:
                    dpos = (best[1], best[2])
            if dpos is None and self.rng.random() < P_BROWN:
                dpos = DIRS[self.rng.randrange(8)]
            if dpos is None:
                continue
            np = ((pos[0] + dpos[0]) % L, (pos[1] + dpos[1]) % L)
            if np in self.grid:
                continue
            # 不拆散约束：移动后必须仍与所有强键合伙伴贴邻（弱接触可断）
            ok = True
            for k in self._bonds_of(i):
                if self.bonds[k] < TS.W_STRONG:
                    continue
                uniq = list(k)
                oj = uniq[0] if uniq[1] == i else uniq[1]
                op = self.mols[oj]["pos"]
                nd = max(abs(torus_delta(np[0], op[0], L)), abs(torus_delta(np[1], op[1], L)))
                if nd > 1:
                    ok = False
                    break
            if not ok:
                continue
            del self.grid[pos]
            m["pos"] = np
            self.grid[np] = i
            moved += 1

        # 键更新
        newbonds = {}
        for i in range(len(self.mols)):
            mi = self.mols[i]
            if mi["dead"]:
                continue
            for (j, p, d) in self.neighbours(mi["pos"], rmax=1):
                if j <= i or d != 1 or self.mols[j]["dead"]:
                    continue
                w = self._force(i, j, 1)
                if w >= TS.W_WEAK:
                    newbonds[frozenset((i, j))] = w
        self.bonds = newbonds
        self.n_encounters += len(self._adjacent_pairs() - prev_adj)

        # 反应
        nreact = 0
        if react is not None:
            nreact = react(self)
        return moved, nreact

    # ---------- 统计 ----------
    def _components(self, thr):
        adj = {}
        for k, w in self.bonds.items():
            if w < thr:
                continue
            a, b = tuple(k)
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        comps = []
        seen = set()
        for i in adj:
            if i in seen:
                continue
            stack = [i]
            seen.add(i)
            sz = 0
            while stack:
                u = stack.pop()
                sz += 1
                for v in adj[u]:
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            comps.append(sz)
        comps.sort(reverse=True)
        return comps

    def stats(self, body_ids=None):
        n_live = sum(1 for m in self.mols if not m["dead"])
        comps = self._components(TS.W_WEAK)
        comps_s = self._components(TS.W_STRONG)
        bonds_strong = sum(1 for v in self.bonds.values() if v >= TS.W_STRONG)
        out = {
            "n": n_live,
            "bonds": len(self.bonds),
            "bonds_strong": bonds_strong,
            "n_comp": len(comps),
            "max_comp": comps[0] if comps else 0,
            "max_comp_strong": comps_s[0] if comps_s else 0,
            "mean_comp": sum(comps) / len(comps) if comps else 0.0,
            "top_comps": comps[:10],
            "top_comps_strong": comps_s[:10],
            "bond_ratio": (2.0 * len(self.bonds) / n_live) if n_live else 0.0,
        }
        if body_ids is not None:
            out["body_n"] = sum(1 for b in body_ids if b < len(self.mols) and not self.mols[b]["dead"])
        return out

    def body_set(self, ids):
        return [i for i in ids if i < len(self.mols)]

    def same_bond_fraction(self):
        """同性键（同 type）占比 vs 随机配对期望。"""
        same = total = 0
        for k in self.bonds:
            a, b = tuple(k)
            total += 1
            if self.mols[a]["ti"] == self.mols[b]["ti"]:
                same += 1
        cnt = {}
        n = 0
        for m in self.mols:
            if m["dead"]:
                continue
            cnt[m["ti"]] = cnt.get(m["ti"], 0) + 1
            n += 1
        exp = sum(c * (c - 1) for c in cnt.values()) / (n * (n - 1)) if n > 1 else 0.0
        return {"same": same, "total": total, "frac": (same / total if total else 0.0), "expected": exp}


# ---------------- 实验 ----------------

def run_e1(formula, n, L, ticks, seed, use_force=True, sample=20):
    w = World(L, seed, use_force=use_force)
    for _ in range(n):
        w.add_mol(formula)
    series = []
    for t in range(ticks):
        w.step()
        if t % sample == 0 or t == ticks - 1:
            s = w.stats()
            s["encounters"] = w.n_encounters
            series.append({"t": t, **s})
    ti = w.tidx[formula]
    sc = w.sc[ti]
    pf = TS.pair_force(w.comp[ti], w.comp[ti], 1)
    return {
        "formula": formula, "n": n, "L": L, "ticks": ticks, "seed": seed,
        "use_force": use_force, "attrs": sc,
        "self": {"att": pf["att"], "rep": pf["rep"], "w": pf["w"]},
        "final": series[-1], "series": series,
    }


def run_e2(formulas, n_each, L, ticks, seed, sample=20):
    w = World(L, seed)
    for f in formulas:
        for _ in range(n_each):
            w.add_mol(f)
    series = []
    for t in range(ticks):
        w.step()
        if t % sample == 0 or t == ticks - 1:
            series.append({"t": t, **w.stats(), "encounters": w.n_encounters,
                           "same_bond": w.same_bond_fraction()})
    return {"formulas": formulas, "n_each": n_each, "L": L, "ticks": ticks, "seed": seed,
            "final": series[-1], "series": series}


def run_e3(A_formula, n_mon, L, ticks, seed, use_force=True, sample=10):
    """体生长：6 个 A 的种子体 + n_mon 个 A 单体；看体是否靠吸引继续长大。"""
    w = World(L, seed, use_force=use_force)
    tiA = w.add_type(A_formula)
    base_r, base_c = L // 2, L // 2
    seed_ids = []
    for dr, dc in [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]:
        mid = w.add_mol(A_formula, (base_r + dr, base_c + dc))
        if mid is not None:
            seed_ids.append(mid)
    for _ in range(n_mon):
        w.add_mol(A_formula)
    series = []
    for t in range(ticks):
        w.step()
        if t % sample == 0 or t == ticks - 1:
            s = w.stats()
            comp = w._comp_of(seed_ids)
            s["body_n"] = len(comp)
            s["body_A"] = sum(1 for i in comp if w.mols[i]["ti"] == tiA)
            s["encounters"] = w.n_encounters
            s["t"] = t
            series.append(s)
    s = w.stats()
    comp = w._comp_of(seed_ids)
    pf = TS.pair_force(w.comp[tiA], w.comp[tiA], 1)
    return {"A": A_formula, "n_mon": n_mon, "L": L, "ticks": ticks, "seed": seed,
            "use_force": use_force, "self_w": pf["w"], "self_att": pf["att"],
            "series": series, "final": series[-1],
            "body": sorted(comp)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--out", default="t81_world.json")
    args = ap.parse_args()
    quick = args.quick or not args.full

    species = ["O2K2A2", "O2K6A2", "O2K3A2F2", "O2", "X2", "C2", "K2", "A2", "F2", "P2", "W2", "L2", "XA", "WA", "LF"]
    t0 = time.time()
    out = {"meta": {"model": "three_su v1", "k_a": TS.K_A, "k_r": TS.K_R,
                    "w_strong": TS.W_STRONG, "w_weak": TS.W_WEAK,
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S")}, "e1": [], "e1c": [], "e2": [], "e3": []}

    if quick:
        ticks = 200
        seeds = [1]
        e1_n, e1_L = 20, 24
        e2_n, e2_L = 10, 24
    else:
        ticks = 1500
        seeds = [11, 12, 13, 14]
        e1_n, e1_L = 40, 40
        e2_n, e2_L = 20, 40

    for f in species:
        for sd in seeds:
            r = run_e1(f, e1_n, e1_L, ticks, sd)
            out["e1"].append(r)
            print("E1 %-3s seed%d max_comp=%d bonds=%d" % (f, sd, r["final"]["max_comp"], r["final"]["bonds"]))
    if not quick:
        for f in ["O2K2A2", "O2", "C2", "XA", "WA"]:
            r = run_e1(f, e1_n, e1_L, ticks, 99, use_force=False)
            out["e1c"].append(r)
            print("E1c %-3s max_comp=%d bonds=%d" % (f, r["final"]["max_comp"], r["final"]["bonds"]))

    mix = [["O2", "X2", "C2", "K2", "A2", "F2"],
           ["OXC", "WCK", "LAF", "XA", "WK", "CL"],
           ["O2", "X3", "C2", "O3X2", "X2C3", "OC3"]]
    for idx, fs in enumerate(mix):
        for sd in seeds:
            r = run_e2(fs, e2_n, e2_L, ticks, sd)
            out["e2"].append({"mix": idx, "seed": sd, "formulas": fs, "result": r})
            sb = r["final"]["same_bond"]
            print("E2 mix%d seed%d bonds=%d same=%.3f exp=%.3f" % (idx, sd, sb["total"], sb["frac"], sb["expected"]))

    acc = [("O2K2A2", 2.5), ("O2K3A2F2", 2.5), ("O2", 2.5), ("C2", 0.83), ("WA", -0.11), ("L2", -0.17)]
    for (A, _sw) in acc:
        for uf in (True, False):
            for sd in (seeds[:2] if not quick else seeds):
                r = run_e3(A, 15 if not quick else 12, 48 if not quick else 24,
                           2500 if not quick else 200, sd, use_force=uf)
                out["e3"].append(r)
                print("E3 %-6s force=%-5s seed%d body=%d self_w=%.2f" % (
                    A, uf, sd, r["final"]["body_n"], r["self_w"]))

    out["meta"]["elapsed_s"] = round(time.time() - t0, 2)
    with io.open(os.path.join(BASE, args.out), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False)
    print("saved", args.out, "elapsed %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
