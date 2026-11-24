# -*- coding: utf-8 -*-
"""T90：稳定 A 主体团簇 + 抓取营养物 → 体内反应再生 A → 并入生长。

场景（回答用户 m03715）：
- 世界：方阵硬边界 240×160；每格最多 1 个分子；分子占 k 个格（k=骨架块数）。
- 主体 A = C3K3F2（8 原子、5 位点、self w=0.833），初始 24 个 A 组成紧凑团簇。
- 营养物 F1=C2K2、F2=CKF2（各 4 原子、self w=0.833）；F1+F2 经规则 1~11 → 单个 A（已验证）。
- 运动：营养物被 A 的聚素吸引力拉向主体（TS.pair_force 的 att），另有 3% 布朗；A 受重力缓慢下沉 + 对相邻 A 的凝聚。
- 反应：仅在主体表面（距主体 ≤3 格）发生 F1+F2 → A；产物 A 若落在主体邻格则并入主体（连通分量）。
- 对照：full（全开）/ no_attr（营养物不感知主体）/ no_react（不反应）/ no_seed（无主体种子）。
输出 t90_body_growth.json + images/t90_body.png（运行后由 t90_render.py 画）。
"""
import io
import json
import math
import os
import random

from alchemy import three_su as TS
from alchemy import attrs as A
from alchemy.core import elements as ELEM
import natural_engine as E

BASE = r"G:\AI work\deepseek\work1\alchemy"
CAT = os.path.join(BASE, "t4_catalog_all_validated.json")

A_FORMULA = "C3K3F2"
F1 = "C2K2"
F2 = "CKF2"
W, H = 240, 160
N_BODY = 24
N_F1 = 700
N_F2 = 700
GATE_R = 3
P_REACT = 0.03
LOCK_W = 0.6


def comp_of(f):
    c = {}
    i = 0
    while i < len(f):
        e = f[i]
        i += 1
        n = ""
        while i < len(f) and f[i].isdigit():
            n += f[i]
            i += 1
        c[e] = int(n or 1)
    return c


def vec_of(c):
    return [c.get(e, 0) for e in ELEM.ORDER]


def load_catalog():
    recs = json.load(io.open(CAT, encoding="utf-8"))
    return {r["formula"]: r for r in recs}


def shape_of(k):
    if k <= 1:
        return [(0, 0)]
    if k == 2:
        return [(0, 0), (1, 0)]
    if k == 3:
        return [(0, 0), (1, 0), (2, 0)]
    if k == 4:
        return [(0, 0), (0, 1), (1, 0), (1, 1)]
    s = int(math.ceil(math.sqrt(k)))
    return [(i // s, i % s) for i in range(k)]


def k_of(rec):
    try:
        units = A.skeleton_units(list(rec["atoms"]),
                                 [tuple(e) for e in rec["edges"]])
        return max(1, len(units))
    except Exception:
        return 1


class World:
    def __init__(self, seed=20261120, attract=True, react=True, seed_body=True,
                 n_f1=N_F1, n_f2=N_F2, freeze_body=True):
        self.rng = random.Random(seed)
        self.attr_on = attract
        self.freeze_body = freeze_body
        self.n_f1 = n_f1
        self.n_f2 = n_f2
        self.react_on = react
        self.cat = load_catalog()
        self.types = {}
        self.cell = {}
        self.mols = []
        self.next_id = 0
        self.frames = []
        self.series = []
        self.n_react = 0
        self.n_join = 0
        self.n_cap = 0
        self.t = 0
        self.body_seed = set()
        self.body = set()
        self._type(A_FORMULA)
        self._type(F1)
        self._type(F2)
        if seed_body:
            self._seed_body()
        self._seed_food()

    def _type(self, f):
        t = self.types.get(f)
        if t:
            return t
        rec = self.cat.get(f)
        k = k_of(rec) if rec else 1
        c = comp_of(f)
        sc = TS.scores(c, r_max=GATE_R)   # T96：半径封顶 == 力扫描窗口（GATE_R）
        self.types[f] = {"f": f, "k": k, "shape": shape_of(k),
                         "vec": vec_of(c), "natoms": sum(c.values()),
                         "A": sc["A"], "D": sc["D"]}
        return self.types[f]

    def _free(self, cells):
        return all((r, c) not in self.cell for (r, c) in cells) and \
            all(0 <= r < H and 0 <= c < W for (r, c) in cells)

    def _find_footprint(self, f, r0, c0, rad=6):
        t = self._type(f)
        for rad2 in range(rad + 1):
            for dr in range(-rad2, rad2 + 1):
                for dc in range(-rad2, rad2 + 1):
                    r, c = r0 + dr, c0 + dc
                    cells = [(r + a, c + b) for (a, b) in t["shape"]]
                    if self._free(cells):
                        return cells
        return None

    def add_mol(self, f, cells):
        t = self._type(f)
        mid = self.next_id
        self.next_id += 1
        m = {"id": mid, "f": f, "cells": list(cells), "k": t["k"],
             "type": t}
        self.mols.append(m)
        for cs in cells:
            self.cell[cs] = mid
        return m

    def _remove(self, m):
        for cs in m["cells"]:
            if self.cell.get(cs) == m["id"]:
                del self.cell[cs]
        m["dead"] = True

    def _seed_body(self):
        # 紧凑团簇：行 76..90，列 116..124 的中点附近找位
        r0, c0 = 78, 118
        placed = 0
        for rad in (0, 1, 2, 3, 4):
            for dr in range(-rad, rad + 1):
                for dc in range(-rad, rad + 1):
                    if placed >= N_BODY:
                        break
                    cells = self._find_footprint(A_FORMULA, r0 + dr * 2,
                                                 c0 + dc * 2, rad=3)
                    if cells is None:
                        continue
                    m = self.add_mol(A_FORMULA, cells)
                    self.body_seed.add(m["id"])
                    placed += 1
        self.body = set(self.body_seed)

    def _seed_food(self):
        n = 0
        while n < self.n_f1 + self.n_f2:
            f = F1 if n < self.n_f1 else F2
            r = self.rng.randrange(H)
            c = self.rng.randrange(W)
            cells = self._find_footprint(f, r, c, rad=4)
            if cells is None:
                continue
            self.add_mol(f, cells)
            n += 1

    def body_cells(self):
        out = []
        for m in self.mols:
            if m["id"] in self.body and not m.get("dead"):
                out.extend(m["cells"])
        return out

    def _centroid(self):
        cs = self.body_cells()
        if not cs:
            return None
        return (sum(p[0] for p in cs) / len(cs),
                sum(p[1] for p in cs) / len(cs))

    def _dist_to_body(self, cells, bcset):
        best = 99
        for (r, c) in cells:
            for dr in range(-GATE_R, GATE_R + 1):
                for dc in range(-GATE_R, GATE_R + 1):
                    if (r + dr, c + dc) in bcset:
                        d = max(abs(dr), abs(dc))
                        if d < best:
                            best = d
        return best

    def _move(self, m, bcset, centroid):
        t = m["type"]
        cells = m["cells"]
        r, c = cells[0]
        # 候选方向
        if m["id"] in self.body:
            if self.freeze_body:
                return False
            # 主体 A：重力下沉 + 凝聚（找最近 A 邻居方向）
            dirs = []
            if self.rng.random() < 0.10:
                dirs.append((1, 0))
            neigh = None
            bestd = 99
            for om in self.mols:
                if om["id"] == m["id"] or om.get("dead"):
                    continue
                if om["f"] != A_FORMULA:
                    continue
                d = max(abs(om["cells"][0][0] - r),
                        abs(om["cells"][0][1] - c))
                if d < bestd:
                    bestd = d
                    neigh = om
            if neigh and bestd > 1:
                tr, tc = neigh["cells"][0]
                dirs.append((0 if tr == r else (1 if tr > r else -1),
                             0 if tc == c else (1 if tc > c else -1)))
            dirs.append((self.rng.choice([-1, 0, 1]),
                         self.rng.choice([-1, 0, 1])))
        else:
            if self.attr_on and centroid:
                # 朝主体质心的方向（聚素吸引力）；d=1 时衰减恒 1，r_max 仅统一口径
                att = TS.pair_force(comp_of(A_FORMULA), comp_of(m["f"]),
                                    r_max=GATE_R)["att"]
                p = min(0.85, 0.10 + 1.2 * att)
                if self.rng.random() < p:
                    tr, tc = centroid
                    dr = 0 if abs(tr - r) < 1.0 else (1 if tr > r else -1)
                    dc = 0 if abs(tc - c) < 1.0 else (1 if tc > c else -1)
                    dirs = [(dr, dc)]
                else:
                    dirs = [(self.rng.choice([-1, 0, 1]),
                             self.rng.choice([-1, 0, 1]))]
            else:
                dirs = [(self.rng.choice([-1, 0, 1]),
                         self.rng.choice([-1, 0, 1]))]
        for (dr, dc) in dirs:
            if dr == 0 and dc == 0:
                continue
            new = [(rr + dr, cc + dc) for (rr, cc) in cells]
            if not self._free_or_self(new, m):
                continue
            # A 必须保持至少 1 个 A 邻居（凝聚）
            if m["f"] == A_FORMULA:
                if not self._has_A_neighbor(new, m["id"]):
                    continue
            for cs in cells:
                if self.cell.get(cs) == m["id"]:
                    del self.cell[cs]
            m["cells"] = new
            for cs in new:
                self.cell[cs] = m["id"]
            return True
        return False

    def _free_or_self(self, cells, m):
        for cs in cells:
            if cs in self.cell and self.cell[cs] != m["id"]:
                return False
            if not (0 <= cs[0] < H and 0 <= cs[1] < W):
                return False
        return True

    def _has_A_neighbor(self, cells, mid):
        for (r, c) in cells:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    oid = self.cell.get((r + dr, c + dc))
                    if oid is None or oid == mid:
                        continue
                    for om in self.mols:
                        if om["id"] == oid and om["f"] == A_FORMULA:
                            return True
        return False

    def _adjacent(self, m1, m2):
        for (r, c) in m1["cells"]:
            for (rr, cc) in m2["cells"]:
                if max(abs(r - rr), abs(c - cc)) <= 1:
                    return True
        return False

    def react_phase(self):
        if not self.react_on:
            return
        bcset = set(self.body_cells())
        if not bcset:
            return
        foods = [m for m in self.mols if not m.get("dead") and
                 m["f"] in (F1, F2)]
        rng = self.rng
        rng.shuffle(foods)
        used = set()
        for i in range(len(foods)):
            a = foods[i]
            if a["id"] in used:
                continue
            for j in range(i + 1, len(foods)):
                b = foods[j]
                if b["id"] in used or b["f"] == a["f"]:
                    continue
                if not self._adjacent(a, b):
                    continue
                if self._dist_to_body(a["cells"], bcset) > GATE_R:
                    continue
                if rng.random() > P_REACT:
                    continue
                total = [x + y for x, y in zip(a["type"]["vec"],
                                               b["type"]["vec"])]
                if sum(total) > 26:
                    self.n_cap += 1
                    continue
                prods = E.complete_products(list(total))
                if not prods:
                    continue
                pa = dict((p["formula"], p) for p in prods)
                if list(pa.keys()) != [A_FORMULA]:
                    continue
                cells = None
                for (r, c) in a["cells"] + b["cells"]:
                    cells = self._find_footprint(A_FORMULA, r, c, rad=4)
                    if cells:
                        break
                if not cells:
                    continue
                used.add(a["id"])
                used.add(b["id"])
                self._remove(a)
                self._remove(b)
                nm = self.add_mol(A_FORMULA, cells)
                self.n_react += 1
                if self._has_A_neighbor(cells, nm["id"]):
                    self.body.add(nm["id"])
                    self.n_join += 1

    def update_body(self):
        # 主体 = 含种子（或已并入成员）的 A 连通分量
        a_mols = [m for m in self.mols if not m.get("dead") and
                  m["f"] == A_FORMULA]
        id2m = dict((m["id"], m) for m in a_mols)
        adj = dict((m["id"], set()) for m in a_mols)
        for i in range(len(a_mols)):
            for j in range(i + 1, len(a_mols)):
                if self._adjacent(a_mols[i], a_mols[j]):
                    adj[a_mols[i]["id"]].add(a_mols[j]["id"])
                    adj[a_mols[j]["id"]].add(a_mols[i]["id"])
        seen = set()
        stack = [i for i in (self.body_seed | self.body) if i in id2m]
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            stack.extend(adj.get(u, ()))
        self.body = set(seen)

    def stats(self):
        body_cells = self.body_cells()
        n_food1 = sum(1 for m in self.mols if not m.get("dead")
                      and m["f"] == F1)
        n_food2 = sum(1 for m in self.mols if not m.get("dead")
                      and m["f"] == F2)
        n_A = sum(1 for m in self.mols if not m.get("dead")
                  and m["f"] == A_FORMULA)
        if body_cells:
            rs = [p[0] for p in body_cells]
            cs = [p[1] for p in body_cells]
            rad = max(max(rs) - min(rs), max(cs) - min(cs))
        else:
            rad = 0
        return {"t": self.t, "body": len(self.body),
                "body_cells": len(body_cells), "A_free": n_A - len(self.body),
                "food1": n_food1, "food2": n_food2,
                "react": self.n_react, "join": self.n_join,
                "body_radius": rad}

    def step(self):
        bcset = set(self.body_cells())
        centroid = self._centroid()
        for m in self.mols:
            if m.get("dead"):
                continue
            self._move(m, bcset, centroid)
        self.react_phase()
        self.update_body()
        self.t += 1
        if self.t % 20 == 0:
            self.series.append(self.stats())


def run(attract=True, react=True, seed_body=True, ticks=700, seed=20261120,
        out="t90_body_growth.json", n_f1=N_F1, n_f2=N_F2, freeze_body=True):
    w = World(seed=seed, attract=attract, react=react, seed_body=seed_body,
              n_f1=n_f1, n_f2=n_f2, freeze_body=freeze_body)
    w.series.append(w.stats())
    for _ in range(ticks):
        w.step()
    print("%-10s body=%d free_A=%d react=%d join=%d food=%d/%d" % (
        "full" if (attract and react and seed_body) else
        ("noattr" if not attract else ("noreact" if not react else "noseed")),
        len(w.body), w.stats()["A_free"], w.n_react, w.n_join,
        w.stats()["food1"], w.stats()["food2"]))
    body_cells = [list(c) for c in w.body_cells()]
    food_cells = []
    for m in w.mols:
        if not m.get("dead") and m["f"] in (F1, F2):
            food_cells.extend([list(c) for c in m["cells"]])
    res = {"config": {"W": W, "H": H, "A": A_FORMULA, "F1": F1, "F2": F2,
                      "N_BODY": N_BODY, "N_F1": N_F1, "N_F2": N_F2,
                      "GATE_R": GATE_R, "P_REACT": P_REACT,
                      "attract": attract, "react": react,
                      "seed_body": seed_body, "ticks": ticks,
                      "seed": seed},
           "series": w.series, "final_body_cells": body_cells,
           "final_food_cells": food_cells}
    io.open(os.path.join(BASE, out), "w", encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run(n_f1=250, n_f2=250, out="t90_full.json")
    run(n_f1=250, n_f2=250, attract=False, out="t90_noattr.json")
    run(n_f1=250, n_f2=250, react=False, out="t90_noreact.json")
    run(n_f1=250, n_f2=250, seed_body=False, out="t90_noseed.json")
