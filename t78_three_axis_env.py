# -*- coding: utf-8 -*-
"""t78_three_axis_env.py —— T78：九元素"三轴介质箱"环境实验

把 2026-11-19 定稿的三轴（质量 / 物态 / 温度，见 docs/MATERIAL_AXES.md、
alchemy/attrs.py）第一次接进一个可运行的 2D 环境模拟：

    质量轴 -> 重力/浮力（轻上升 / 中悬浮 / 重下沉，连续质量值驱动）
    物态轴 -> 碰撞判定（气穿过 / 液游泳-黏附 / 固阻挡；决定单次接触的反应倍率）
    温度轴 -> 恒素富集（热->富集、冷->稀薄；恒素浓度 rho_E 门控反应）

与 T55~T67 的关键差别：旧实验用"环境温度 T"直接驱动反应；新口径下
**温度轴不参与反应判定**（反应只由恒素浓度 rho_E 决定）。因此本实验固定
T_REACT=1000 调用 natural_engine.resolve（规则 1~11 + T35），另加
p = 物态倍率 × rho_E 的接触门控。

三组对照（同 seed、同投料）：
    main   三轴全开
    nogate 关恒素门控（p = 物态倍率）-> 均匀化学
    nochem 关反应（只做运动 + 恒素场）-> 纯物理分层基线

用法：
    python t78_three_axis_env.py --quick                 # 冒烟
    python t78_three_axis_env.py --arm main  --minutes 240
    python t78_three_axis_env.py --arm nogate --minutes 240
    python t78_three_axis_env.py --arm nochem --minutes 240

不在本脚本内改动任何内核代码（alchemy/ 只读调用）。
"""
import argparse
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import natural_engine as E
import pot_all as P
from alchemy import attrs as A

# ================================================================== 世界参数
W = 2000.0                  # 世界宽（横向，反射墙）
H = 4000.0                  # 世界高（纵向，反射墙；0=底，H=顶）
MED_MASS = 2.0              # 介质质量轴值（中）
MED_STATE = 1.0             # 介质物态轴值（气）
MED_TEMP = 1.75             # 介质温度轴值（温 -> 恒素中性 0.5）
GRAV = 80.0                 # 浮力/重力标定：v_target = GRAV*(m_med-m_obj)/m_med
K_RELAX = 0.25              # 纵向速度向终端速度松弛
DAMP_X = 0.50               # 横向速度阻尼
SIGMA = {"气": 10.0, "液": 5.0, "固": 1.5}   # 物态 -> 布朗扰动幅度

EX, EY = 10, 20             # 恒素场网格：200 x 200
CX, CY = 8, 16              # 碰撞采样网格：250 x 250
E_CELL_W = W / EX
E_CELL_H = H / EY
C_CELL_W = W / CX
C_CELL_H = H / CY
C_CELL_AREA = C_CELL_W * C_CELL_H

K_RATE = 1600.0             # 碰撞采样系数：每格 lambda = K_RATE*Nc(Nc-1)/2/A
CAP = 20                    # 反应原子数上限（与 T62 一致）
T_REACT = 1000.0            # 反应判定温度（固定高位：温度轴不参与判定）
GATE_EXP = 1.0              # p = mult * rho**GATE_EXP
DT = 1.0

MODE_MULT = {
    ("气", "气"): ("穿过", 0.18),
    ("气", "液"): ("游泳", 0.45),
    ("液", "气"): ("游泳", 0.45),
    ("液", "液"): ("黏附", 0.60),
    ("气", "固"): ("阻挡", 0.80),
    ("固", "气"): ("阻挡", 0.80),
    ("液", "固"): ("阻挡", 0.90),
    ("固", "液"): ("阻挡", 0.90),
    ("固", "固"): ("阻挡", 1.00),
}
MODES = ("穿过", "游泳", "黏附", "阻挡")
TIERS = ("轻", "中", "重")

SNAP_MINUTES = [0, 10, 25, 50, 75, 100, 150, 200, 240]
COMP_SAMPLE_MINUTES = 10
LOG_MINUTES = 20

_ATTR_CACHE = {}


def mol_attrs(mol):
    """三轴数值 + 档名（按分子式缓存；三轴只由元素计数决定）。"""
    f = mol["formula"]
    hit = _ATTR_CACHE.get(f)
    if hit is not None:
        return hit
    d = A.molecule_attrs(list(mol["atoms"]))
    m, s, t = d["mass"], d["state"], d["temperature"]
    hit = (m, s, t,
           A.tier_name(m, "mass"), A.tier_name(s, "state"), A.tier_name(t, "temperature"))
    _ATTR_CACHE[f] = hit
    return hit


def mode_of(st_i, st_j):
    return MODE_MULT.get((st_i, st_j), ("阻挡", 0.80))


def poisson(rng, lam):
    if lam <= 0:
        return 0
    if lam < 30.0:
        Lk = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            p *= rng.random()
            if p <= Lk:
                return k
            k += 1
    v = int(round(rng.gauss(lam, math.sqrt(lam))))
    return max(0, v)


def build_templates(formulas):
    subs = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    byf = {r["formula"]: r for r in subs}
    out = {}
    for f in formulas:
        if f in out:
            continue
        if f in byf:
            out[f] = E.mol_from_record(byf[f])
            continue
        vec = P.parse_formula(f)
        prods = E.complete_products(tuple(vec))
        if not prods:
            raise ValueError("无法为 %s 生成结构" % f)
        mol = next((m for m in prods if m["formula"] == f), None)
        if mol is None:
            raise ValueError("无法重建分子式 %s 的结构" % f)
        out[f] = mol
    return out


def load_feed(target_mol):
    """读 T62 等量价数投料 batchA（三/二/一价原子各 1/3、9 元素各 1/9），按比例缩放。"""
    d = json.load(open(BASE + r"\t62_loads.json", encoding="utf-8"))
    rows = d["batchA"]["rows"]
    total = sum(r["count"] for r in rows)
    scale = float(target_mol) / total
    items = []
    for r in rows:
        n = max(1, int(round(r["count"] * scale)))
        items.append((r["formula"], n))
    return items, scale


def load_catalog_formulas():
    """t4_catalog_index.json 是 list[{formula,natoms,zh,elements,source}]（84,225 条），
    取全部合法分子式作为"新物质"判定基准（与 T55/T62 的 known_formulas 口径一致）。"""
    path = BASE + r"\t4_catalog_index.json"
    if not os.path.exists(path):
        return set()
    rows = json.load(open(path, encoding="utf-8"))
    return {r["formula"] for r in rows}


class Particle:
    __slots__ = ("pid", "mol", "x", "y", "vx", "vy", "origin", "birth_t",
                 "mass", "state", "temp", "mt", "st", "tt", "sigma", "dead")

    def __init__(self, pid, mol, x, y, vx, vy, origin, birth_t):
        self.dead = False
        self.pid = pid
        self.mol = mol
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.origin = origin
        self.birth_t = birth_t
        self.mass, self.state, self.temp, self.mt, self.st, self.tt = mol_attrs(mol)
        self.sigma = SIGMA[self.st]


class ThreeAxisEnv:
    def __init__(self, minutes=240, seed=20261119, target_mol=1800,
                 gate=True, chem=True, snap_minutes=None, known_formulas=None):
        self.minutes = int(minutes)
        self.seed = int(seed)
        self.gate = bool(gate)
        self.chem = bool(chem)
        self.rng = random.Random(self.seed)
        self.snap_minutes = set(snap_minutes or SNAP_MINUTES)
        self.items, self.scale = load_feed(target_mol)
        self.templates = build_templates([f for f, _ in self.items])
        self.known = set(self.templates)
        if known_formulas:
            self.known |= set(known_formulas)
        self.initial_elements = Counter()
        self.initial_molecules = Counter()
        self.next_pid = 0
        self.particles = []
        self._init_particles()

        # 恒素场
        self.rho = [0.5] * (EX * EY)

        # 统计
        self.fcnt = Counter(self.initial_molecules)
        self.events = []
        self.new_substances = {}
        self.counts = Counter()
        self.mode_counts = Counter()
        self.time_series = []
        self.formula_series = []
        self.snapshots = []
        self.band_reaction = {"bottom": 0, "mid": 0, "top": 0}
        self.e_reaction = Counter()   # rho 分桶的反应计数（0.1 一档）
        self.e_attempt = Counter()
        self.react_at_y = []
        self.t_start = time.time()

    # -------------------------------------------------------------- 初始化
    def _init_particles(self):
        rng = self.rng
        for f, n in self.items:
            mol = self.templates[f]
            at = mol["atoms"]
            for _ in range(n):
                m, s, t, mt, st, tt = mol_attrs(mol)
                ang = rng.random() * 2.0 * math.pi
                sp = 20.0 + 10.0 * rng.random()
                self.particles.append(Particle(
                    self.next_pid, mol, rng.random() * W, rng.random() * H,
                    sp * math.cos(ang), sp * math.sin(ang), f, 0))
                self.next_pid += 1
                self.initial_molecules[f] += 1
                for a in at:
                    self.initial_elements[a] += 1
        self.n0 = len(self.particles)
        self.atoms0 = sum(len(p.mol["atoms"]) for p in self.particles)

    # -------------------------------------------------------------- 几何
    def e_cell(self, x, y):
        ex = min(EX - 1, int(x / E_CELL_W))
        ey = min(EY - 1, int(y / E_CELL_H))
        return ey * EX + ex

    def c_cell(self, x, y):
        cx = min(CX - 1, int(x / C_CELL_W))
        cy = min(CY - 1, int(y / C_CELL_H))
        return cy * CX + cx

    # -------------------------------------------------------------- 运动
    def move(self):
        rng = self.rng
        Wl, Hl = W, H
        for p in self.particles:
            vt = GRAV * (MED_MASS - p.mass) / MED_MASS
            sg = p.sigma
            p.vy += (vt - p.vy) * K_RELAX + rng.gauss(0.0, sg)
            p.vx += -DAMP_X * p.vx + rng.gauss(0.0, sg)
            p.x += p.vx * DT
            p.y += p.vy * DT
            if p.x < 0.0:
                p.x = -p.x
                p.vx = -p.vx
            elif p.x > Wl:
                p.x = 2.0 * Wl - p.x
                p.vx = -p.vx
            if p.y < 0.0:
                p.y = -p.y
                p.vy = -p.vy
            elif p.y > Hl:
                p.y = 2.0 * Hl - p.y
                p.vy = -p.vy

    # -------------------------------------------------------------- 恒素场
    def update_rho(self):
        n = len(self.particles)
        hs = [0.0] * (EX * EY)
        cs = [0.0] * (EX * EY)
        cnt = [0] * (EX * EY)
        for p in self.particles:
            i = self.e_cell(p.x, p.y)
            cnt[i] += 1
            t = p.temp
            if t > MED_TEMP:
                hs[i] += min(1.0, (t - MED_TEMP) / (3.0 - MED_TEMP))
            elif t < MED_TEMP:
                cs[i] += min(1.0, (MED_TEMP - t) / MED_TEMP)
        rho = self.rho
        star = [0.0] * (EX * EY)
        for i in range(EX * EY):
            if cnt[i]:
                star[i] = 0.5 + 0.5 * (hs[i] - cs[i]) / cnt[i]
                star[i] = min(1.0, max(0.0, star[i]))
        # 扩散 + 松弛 + 回归中性
        new = [0.0] * (EX * EY)
        for ey in range(EY):
            for ex in range(EX):
                i = ey * EX + ex
                nb = []
                if ex > 0:
                    nb.append(i - 1)
                if ex < EX - 1:
                    nb.append(i + 1)
                if ey > 0:
                    nb.append(i - EX)
                if ey < EY - 1:
                    nb.append(i + EX)
                nb_mean = sum(rho[j] for j in nb) / len(nb)
                v = rho[i] + 0.12 * (nb_mean - rho[i]) + 0.01 * (0.5 - rho[i])
                if cnt[i]:
                    v += 0.30 * (star[i] - v)
                new[i] = min(1.0, max(0.0, v))
        self.rho = new

    # -------------------------------------------------------------- 反应
    def _product_particles(self, prods, x, y, vx, vy, t):
        out = []
        k = len(prods)
        for idx, pr in enumerate(prods):
            jx = x + self.rng.gauss(0.0, 3.0)
            jy = y + self.rng.gauss(0.0, 3.0)
            jx = min(W - 1e-9, max(0.0, jx))
            jy = min(H - 1e-9, max(0.0, jy))
            ang = self.rng.random() * 2.0 * math.pi
            sp = math.hypot(vx, vy) * (0.8 + 0.4 * self.rng.random())
            if sp < 1e-9:
                sp = 1.0
            self.particles.append(Particle(self.next_pid, pr, jx, jy,
                                           sp * math.cos(ang), sp * math.sin(ang),
                                           "R", t))
            out.append(self.particles[-1])
            self.next_pid += 1
            self.fcnt[pr["formula"]] += 1
            if pr["formula"] not in self.known and pr["formula"] not in self.new_substances:
                self.new_substances[pr["formula"]] = {
                    "first_t": t, "formula": pr["formula"],
                    "atoms": list(pr["atoms"]), "edges": [list(e) for e in pr["edges"]]}
        return out

    def contact_step(self, t):
        rng = self.rng
        cells = [[] for _ in range(CX * CY)]
        for p in self.particles:
            cells[self.c_cell(p.x, p.y)].append(p)
        attempts = complete = incomplete = none = inert = capped = 0
        self_skip = chem_off = 0
        for cell in cells:
            nc = len(cell)
            if nc < 2:
                continue
            lam = K_RATE * (nc * (nc - 1) * 0.5) / C_CELL_AREA * DT
            k = poisson(rng, lam)
            for _ in range(k):
                pi = cell[rng.randrange(nc)]
                pj = cell[rng.randrange(nc)]
                if pi is pj or pi.dead or pj.dead:
                    # 采样落空（自碰/本分钟已死）：不计入分类尝试
                    self_skip += 1
                    continue
                attempts += 1
                mi, mj = pi.mol, pj.mol
                mode, mult = mode_of(pi.st, pj.st)
                self.mode_counts[mode] += 1
                xm = 0.5 * (pi.x + pj.x)
                ym = 0.5 * (pi.y + pj.y)
                ei = self.e_cell(pi.x, pi.y)
                rho = self.rho[ei]
                self.e_attempt[int(rho * 10.0)] += 1
                if self.gate:
                    p = mult * (rho ** GATE_EXP)
                else:
                    p = mult
                if rng.random() > p:
                    inert += 1
                    continue
                na = len(mi["atoms"]) + len(mj["atoms"])
                if na > CAP:
                    capped += 1
                    continue
                if not self.chem:
                    chem_off += 1
                    continue
                res = E.resolve([mi, mj], T_REACT)
                typ = res["type"]
                if typ == "none":
                    none += 1
                    continue
                prods = res["products"]
                if prods is None:
                    none += 1
                    continue
                if tuple(sorted(m["label"] for m in prods)) == \
                        tuple(sorted([mi["label"], mj["label"]])):
                    none += 1
                    continue
                # ---- 应用反应：移除 i、j，加入产物
                if typ == "complete":
                    complete += 1
                else:
                    incomplete += 1
                band = min(2, int(ym / (H / 3.0)))
                self.band_reaction[("bottom", "mid", "top")[band]] += 1
                self.e_reaction[int(rho * 10.0)] += 1
                self.react_at_y.append(round(ym, 1))
                vxw = (pi.vx * len(mi["atoms"]) + pj.vx * len(mj["atoms"])) / max(1, na)
                vyw = (pi.vy * len(mi["atoms"]) + pj.vy * len(mj["atoms"])) / max(1, na)
                self.fcnt[mi["formula"]] -= 1
                self.fcnt[mj["formula"]] -= 1
                self._product_particles(prods, xm, ym, vxw, vyw, t)
                # 用产物替换掉 i、j（标记死亡，本步末尾统一清理）
                pi.dead = True
                pj.dead = True
                if len(self.events) < 4000:
                    self.events.append({
                        "t": t, "y": round(ym, 1), "rho": round(rho, 3),
                        "mode": mode, "type": typ,
                        "in": [mi["formula"], mj["formula"]],
                        "out": [pr["formula"] for pr in prods]})
        self.counts["attempts"] += attempts
        self.counts["complete"] += complete
        self.counts["incomplete"] += incomplete
        self.counts["none"] += none
        self.counts["inert"] += inert
        self.counts["capped"] += capped
        self.counts["self_skip"] += self_skip
        self.counts["chem_off"] += chem_off
        # 清理本步死亡的粒子（产物已在列表尾部）
        if complete or incomplete:
            self.particles = [p for p in self.particles if not p.dead]
        return attempts, complete, incomplete, none, inert, capped

    # -------------------------------------------------------------- 统计
    def _snapshot(self, t):
        pts = [[round(p.x, 1), round(p.y, 1), p.mol["formula"]] for p in self.particles]
        self.snapshots.append({"t": t, "n": len(pts), "points": pts,
                               "rho": [round(v, 3) for v in self.rho]})

    def _composition(self, plist=None):
        plist = self.particles if plist is None else plist
        c = Counter(p.mol["formula"] for p in plist)
        return c

    def _row(self, t):
        rng = self.rng
        N = len(self.particles)
        atoms = sum(len(p.mol["atoms"]) for p in self.particles)
        n = max(1, N)
        ys = [p.y for p in self.particles]
        rho = self.rho
        rs = sorted(rho)
        def pct(a, q):
            return round(a[min(len(a) - 1, int(q * len(a)))], 3)
        y_by_mass = {"轻": [], "中": [], "重": []}
        for p in self.particles:
            y_by_mass[p.mt].append(p.y)
        band_cnt = {"bottom": 0, "mid": 0, "top": 0}
        for y in ys:
            band_cnt[("bottom", "mid", "top")[min(2, int(y / (H / 3.0)))]] += 1
        row = {
            "t": t, "N": N, "atoms": atoms,
            "attempts": self._last_counts["attempts"],
            "complete": self._last_counts["complete"],
            "incomplete": self._last_counts["incomplete"],
            "none": self._last_counts["none"],
            "inert": self._last_counts["inert"],
            "capped": self._last_counts["capped"],
            "self_skip": self._last_counts["self_skip"],
            "chem_off": self._last_counts["chem_off"],
            "mode": {m: self._last_modes.get(m, 0) for m in MODES},
            "rho_mean": round(sum(rho) / len(rho), 3),
            "rho_std": round(math.sqrt(sum((v - sum(rho) / len(rho)) ** 2 for v in rho) / len(rho)), 3),
            "rho_p10": pct(rs, 0.10), "rho_p90": pct(rs, 0.90),
            "mass": {"轻": sum(1 for p in self.particles if p.mt == "轻"),
                     "中": sum(1 for p in self.particles if p.mt == "中"),
                     "重": sum(1 for p in self.particles if p.mt == "重")},
            "state": {"气": sum(1 for p in self.particles if p.st == "气"),
                      "液": sum(1 for p in self.particles if p.st == "液"),
                      "固": sum(1 for p in self.particles if p.st == "固")},
            "temp": {"冷": sum(1 for p in self.particles if p.tt == "冷"),
                     "温": sum(1 for p in self.particles if p.tt == "温"),
                     "热": sum(1 for p in self.particles if p.tt == "热")},
            "y_mean": {k: (round(sum(v) / len(v), 1) if v else None)
                       for k, v in y_by_mass.items()},
            "band": band_cnt,
            "mass_mean": round(sum(p.mass for p in self.particles) / n, 3),
            "state_mean": round(sum(p.state for p in self.particles) / n, 3),
            "temp_mean": round(sum(p.temp for p in self.particles) / n, 3),
            "distinct": sum(1 for f, c in self.fcnt.items() if c > 0),
        }
        return row

    # -------------------------------------------------------------- 主循环
    def run(self):
        self._last_counts = Counter()
        self._last_modes = Counter()
        for t in range(self.minutes):
            if t in self.snap_minutes:
                self._snapshot(t)
            self.move()
            self.update_rho()
            before_modes = Counter(self.mode_counts)
            before = Counter(self.counts)
            self.contact_step(t)
            # 每步增量
            for k in ("attempts", "complete", "incomplete", "none", "inert", "capped",
                      "self_skip", "chem_off"):
                self._last_counts[k] = self.counts[k] - before[k]
            self._last_modes = {m: self.mode_counts[m] - before_modes.get(m, 0) for m in MODES}
            # 每秒增长可能使 N 大幅变化，行记录用全局
            self._last_counts["attempts"] = self._last_counts["attempts"]
            self.time_series.append(self._row(t))
            if t % COMP_SAMPLE_MINUTES == 0:
                c = self._composition()
                top = dict(c.most_common(30))
                self.formula_series.append({"t": t, "top": top,
                                            "total": sum(c.values()), "distinct": len(c)})
            if t % LOG_MINUTES == 0 or t == self.minutes - 1:
                print("[%s t=%4d] N=%5d atoms=%6d react=%4d+%d inert=%4d rho=%.3f "
                      "y(light/mid/heavy)=%s.%s.%s  %.0fs" % (
                          self.arm, t, len(self.particles),
                          sum(len(p.mol["atoms"]) for p in self.particles),
                          self._last_counts["complete"], self._last_counts["incomplete"],
                          self._last_counts["inert"], self.time_series[-1]["rho_mean"],
                          self.time_series[-1]["y_mean"]["轻"],
                          self.time_series[-1]["y_mean"]["中"],
                          self.time_series[-1]["y_mean"]["重"],
                          time.time() - self.t_start), flush=True)
        if self.minutes in self.snap_minutes:
            self._snapshot(self.minutes - 1)
        return self._final()

    # -------------------------------------------------------------- 终态
    def _tiers_of(self, p):
        return (p.mt, p.st, p.tt)

    def _final(self):
        rng = self.rng
        parts = self.particles
        # 三带
        bands = {"bottom": [], "mid": [], "top": []}
        for p in parts:
            bands[("bottom", "mid", "top")[min(2, int(p.y / (H / 3.0)))]] .append(p)
        band_comp = {}
        for k, pl in bands.items():
            c = Counter(p.mol["formula"] for p in pl)
            band_comp[k] = {
                "n": len(pl), "atoms": sum(len(p.mol["atoms"]) for p in pl),
                "mass": {"轻": sum(1 for p in pl if p.mt == "轻"),
                         "中": sum(1 for p in pl if p.mt == "中"),
                         "重": sum(1 for p in pl if p.mt == "重")},
                "state": {"气": sum(1 for p in pl if p.st == "气"),
                          "液": sum(1 for p in pl if p.st == "液"),
                          "固": sum(1 for p in pl if p.st == "固")},
                "temp": {"冷": sum(1 for p in pl if p.tt == "冷"),
                         "温": sum(1 for p in pl if p.tt == "温"),
                         "热": sum(1 for p in pl if p.tt == "热")},
                "top": [{"formula": f, "count": c0} for f, c0 in c.most_common(12)],
            }
        # 竖直直方图（40 桶）
        BINS = 40
        hist = {"all": [0] * BINS, "轻": [0] * BINS, "中": [0] * BINS, "重": [0] * BINS}
        for p in parts:
            b = min(BINS - 1, int(p.y / H * BINS))
            hist["all"][b] += 1
            hist[p.mt][b] += 1
        # 27 格
        c27 = Counter("·".join(self._tiers_of(p)) for p in parts)
        # 终态组成
        comp = {}
        for f, c0 in self.fcnt.items():
            if c0 <= 0:
                continue
            mol = next((p.mol for p in parts if p.mol["formula"] == f), None)
            if mol is None:
                continue
            m, s, t, mt, st, tt = mol_attrs(mol)
            comp[f] = {"count": c0, "atoms": len(mol["atoms"]),
                       "mass": m, "state": s, "temperature": t,
                       "cell": "·".join((mt, st, tt))}
        # 守恒
        final_el = Counter()
        for p in parts:
            for a in p.mol["atoms"]:
                final_el[a] += 1
        cons = {}
        for a in sorted(set(self.initial_elements) | set(final_el)):
            cons[a] = {"initial": self.initial_elements.get(a, 0),
                       "final": final_el.get(a, 0)}
        # 反应地理：rho 分桶
        rbins = sorted(self.e_reaction)
        geo = [{"rho_bin": round(i / 10.0, 2), "reactions": self.e_reaction.get(i, 0),
                "attempts": self.e_attempt.get(i, 0)} for i in range(11)]
        summary = {
            "arm": self.arm, "seed": self.seed, "minutes": self.minutes,
            "gate": self.gate, "chem": self.chem,
            "runtime_s": round(time.time() - self.t_start, 1),
            "initial_N": self.n0, "initial_atoms": self.atoms0,
            "final_N": len(parts), "final_atoms": sum(len(p.mol["atoms"]) for p in parts),
            "counts": {k: self.counts[k] for k in
                       ("attempts", "complete", "incomplete", "none", "inert", "capped",
                        "self_skip", "chem_off")},
            "mode_counts": {m: self.mode_counts.get(m, 0) for m in MODES},
            "band_reaction": self.band_reaction,
            "rho_final": {"mean": round(sum(self.rho) / len(self.rho), 3),
                          "std": round(math.sqrt(sum((v - sum(self.rho) / len(self.rho)) ** 2
                                                    for v in self.rho) / len(self.rho)), 3)},
            "conservation": cons,
            "conservation_ok": all(v["initial"] == v["final"] for v in cons.values()),
            "distinct_formulas": len(comp),
            "new_substances": len(self.new_substances),
            "initial_composition": dict(self.initial_molecules),
        }
        cfg = {
            "world": {"W": W, "H": H, "medium": {"mass": MED_MASS, "state": MED_STATE,
                                                 "temperature": MED_TEMP}},
            "gravity": {"GRAV": GRAV, "K_RELAX": K_RELAX, "DAMP_X": DAMP_X, "SIGMA": SIGMA},
            "e_field": {"EX": EX, "EY": EY, "neutral": 0.5, "diff": 0.12,
                        "relax": 0.30, "decay": 0.01},
            "collision": {"CX": CX, "CY": CY, "K_RATE": K_RATE, "CAP": CAP,
                          "T_REACT": T_REACT, "GATE_EXP": GATE_EXP},
            "mode_mult": {"%s-%s" % k: {"mode": v[0], "mult": v[1]}
                          for k, v in MODE_MULT.items()},
            "feed": {"source": "t62_loads.json batchA", "target_mol": self.n0,
                     "scale": round(self.scale, 5),
                     "elements": "三/二/一价原子各1/3、9元素各1/9",
                     "n_species": len(self.items)},
            "snap_minutes": sorted(self.snap_minutes),
        }
        out = {
            "config": cfg,
            "summary": summary,
            "time_series": self.time_series,
            "formula_series": self.formula_series,
            "final_composition": comp,
            "bands": band_comp,
            "vertical_hist": hist,
            "cells27": dict(c27),
            "reaction_geography": geo,
            "reaction_y_hist": self._reaction_y_hist(),
            "snapshots": self.snapshots,
            "new_substances": self.new_substances,
            "events": self.events,
        }
        return out

    def _reaction_y_hist(self):
        BINS = 40
        h = [0] * BINS
        for y in self.react_at_y:
            h[min(BINS - 1, int(y / H * BINS))] += 1
        return h


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=240)
    ap.add_argument("--seed", type=int, default=20261119)
    ap.add_argument("--target-mol", type=int, default=1800)
    ap.add_argument("--arm", default="main", choices=["main", "nogate", "nochem"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)

    E.set_fast(True)
    minutes = 40 if args.quick else args.minutes
    target = 400 if args.quick else args.target_mol
    gate = args.arm != "nogate"
    chem = args.arm != "nochem"
    known = load_catalog_formulas()
    print("catalog formulas:", len(known))
    env = ThreeAxisEnv(minutes=minutes, seed=args.seed, target_mol=target,
                       gate=gate, chem=chem,
                       known_formulas=known,
                       snap_minutes=[0, 10, 20, 30, 40] if args.quick else SNAP_MINUTES)
    env.arm = args.arm
    res = env.run()
    out = args.out or (BASE + "\\t78_%s_result.json" % args.arm)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print("saved", out)
    s = res["summary"]
    print("summary:", json.dumps({k: s[k] for k in
                                  ("arm", "initial_N", "final_N", "counts", "band_reaction",
                                   "conservation_ok", "distinct_formulas", "new_substances",
                                   "runtime_s")}, ensure_ascii=False))
    return res


if __name__ == "__main__":
    main()
