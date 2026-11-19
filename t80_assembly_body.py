# -*- coding: utf-8 -*-
"""T80：组装体生长实验（"主体 A + 食物 → 合成新 A → 并入体" 的最小模型）。

问题（用户 m01077）：一种以物质 A 为主体、B/C/D 为辅的"生命"，能抓取周围小型
物质，经一次或几次反应合成新的 A，并把新 A 连接到自身（生命体 = 很多 A 分子
自发连接成的组装体），从而长大。这种生命在本宇宙是否存在？

模型（不改内核 alchemy/，只调用其组装层 emergence.py）：
  * 主体 A = C3K3F2（8 原子、5 个位点、自界面能 w=2.5，能自发形成稳定组装体；
    cell=中·气·温）。5 个位点保证体表分子成键饱和后仍有余位点，新 A 可连上。
  * 食物 = C2K2（4 原子）+ CKF2（4 原子）；F(C2K2+CKF2) = [C3K3F2]（规则 1~11，
    一次反应合成 1 个 A，元素守恒）。
  * 体 = 初始 6~7 个 A 的紧凑圆盘（中心 + 一圈邻格）；emergence 的 S3 让它们
    成键成组装体（实测 150 拍稳定，E>10）。
  * 每拍：①抓取——体表 GRAB_R 格内的食物按 P_CAP 概率吸附进 buffer（脚本近似
    的表面黏附/吞噬）；②反应——buffer 中两种食物各 1 份经 complete_products
    合成 1 个 A；③并入——新 A 放在体表空闲相邻格，由 emergence 的 S3/S6 自然
    成键连到体上；④em.step_world 推进物理。
  * 闭合系统：食物一次性投放（各 36 个），之后不补充，便于元素守恒校验。
  * 对照臂：full（全开）、nochem（抓取但不合成，buffer 累积）、farspawn
    （合成但新 A 随机投放到远处，考验"必须连到体上"）、bare（无食物）。

输出：t80_assembly_<arm>.json（config/summary/elements/time_series）。
用法：python t80_assembly_body.py --arm full --steps 600
"""
import argparse
import io
import json
import os
import random
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import alchemy.emergence as em          # noqa: E402
import natural_engine as E              # noqa: E402
from alchemy.core.elements import ORDER as ELEM_ORDER  # noqa: E402

A_FORMULA = "C3K3F2"
FOOD_A = "C2K2"
FOOD_B = "CKF2"
BODY_N0 = 7
GRAB_R = 2
P_CAP = 0.5
FOOD_TARGET_A = 48
FOOD_TARGET_B = 48
SNAP_EVERY = 10
WARMUP = 120
NB = [(1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)]
DISK = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def load_catalog():
    path = os.path.join(BASE, "t4_catalog_all_validated.json")
    cat = json.load(io.open(path, encoding="utf-8"))
    idx = {}
    for r in cat:
        idx.setdefault(r["formula"], r)
    return idx


IDX = load_catalog()


def vec_of(formula):
    v = [0] * 9
    for a in IDX[formula]["atoms"]:
        v[ELEM_ORDER.index(a)] += 1
    return v


V_A = vec_of(A_FORMULA)
V_FA = vec_of(FOOD_A)
V_FB = vec_of(FOOD_B)
assert [V_FA[i] + V_FB[i] for i in range(9)] == V_A, "food pair must sum to A"
PRODUCTS = E.complete_products(V_A)
assert PRODUCTS and [p["formula"] for p in PRODUCTS] == [A_FORMULA], PRODUCTS


def addv(a, b):
    return [a[i] + b[i] for i in range(9)]


class Env:
    def __init__(self, L=32, seed=20261119):
        P = dict(em.load_params())
        if "M_eff" not in P:
            P["M"], P["M_eff"], P["M_dir"] = em.build_matrices()
        P["L"] = L
        self.P = P
        self.rng = random.Random(seed)
        self.world = em.init_world([], self.rng, P)
        self.body_seed = None
        self.body = []
        self.body_cells = []
        self.react = 0
        self.captured = 0
        self.spawned = 0
        self.buffer = {FOOD_A: 0, FOOD_B: 0}
        self.buffer_vec = [0] * 9
        self.t = 0

    def _touch_body(self, cs):
        """cs（分子实际占用的格集合）是否有任一格与体分子相邻。"""
        L = self.world.env.L
        body = set(self.body)
        for c in cs:
            for d in NB:
                for uid in self.world.occupancy.get(((c[0] + d[0]) % L, (c[1] + d[1]) % L), ()):
                    if uid in body:
                        return True
        return False

    # ---------- 摆放 ----------
    def _place(self, formula, prefer_cells=None, near_body=False):
        rec = IDX[formula]
        cands = list(prefer_cells or [])
        self.rng.shuffle(cands)
        cells_seq = cands + [(None, None)] * (0 if near_body else 3)
        for cell in cells_seq:
            if cell == (None, None):
                L = self.world.env.L
                cell = (self.rng.randrange(L), self.rng.randrange(L))
            for _ in range(4):
                rot = self.rng.randrange(6)
                mol = em.make_molecule(dict(rec), self.world.next_uid, self.P)
                cs = em._wrap_cells_mol(self.world, mol, cell, rot)
                if near_body and not self._touch_body(cs):
                    continue
                if em._can_place(self.world, cs, mol.uid):
                    mol.pos, mol.rot = cell, rot
                    mol.body_cells = [em._rot(c, rot) for c in mol.local_cells]
                    mol.cells = list(cs)
                    self.world.molecules[mol.uid] = mol
                    em._occupy(self.world, mol)
                    self.world.next_uid += 1
                    return mol
        return None

    def _free_cells_near(self, cells):
        L = self.world.env.L
        occ = self.world.occupancy
        out, seen = [], set()
        for c in cells:
            for d in NB:
                q = ((c[0] + d[0]) % L, (c[1] + d[1]) % L)
                if q in seen:
                    continue
                seen.add(q)
                if q not in occ:
                    out.append(q)
        return out

    # ---------- 初始化 ----------
    def seed_body(self):
        rec = IDX[A_FORMULA]
        mols = []
        for d in DISK[:BODY_N0]:
            placed = False
            for _ in range(12):
                prot = self.rng.randrange(6)
                mol = em.make_molecule(dict(rec), self.world.next_uid, self.P)
                pos = (16 + d[0], 16 + d[1])
                cs = em._wrap_cells_mol(self.world, mol, pos, prot)
                if em._can_place(self.world, cs, mol.uid):
                    mol.pos, mol.rot = pos, prot
                    mol.body_cells = [em._rot(c, prot) for c in mol.local_cells]
                    mol.cells = list(cs)
                    self.world.molecules[mol.uid] = mol
                    em._occupy(self.world, mol)
                    self.world.next_uid += 1
                    mols.append(mol)
                    placed = True
                    break
            if not placed:
                break
        self.body = [m.uid for m in mols]
        self.body_seed = self.body[0]
        self._refresh_body()

    def _refresh_body(self):
        mols = [self.world.molecules[u] for u in self.body if u in self.world.molecules]
        cells = []
        for m in mols:
            cells.extend(em.world_mol_cells(self.world, m))
        self.body_cells = cells

    # ---------- 食物 ----------
    def _feeding_cells(self):
        """食物投放：体周围半径 4~7 的环形区域（营养物培养基），避免全箱随机太稀疏。"""
        L = self.world.env.L
        out = []
        for c in self.body_cells:
            for dist in range(4, 8):
                for q in range(-dist, dist + 1):
                    r1 = max(-dist, -q - dist)
                    r2 = min(dist, -q + dist)
                    for r in range(r1, r2 + 1):
                        if abs(q) + abs(r) + abs(q + r) != dist:
                            continue
                        out.append(((c[0] + q) % L, (c[1] + r) % L))
        seen, uniq = set(), []
        for c in out:
            if c not in seen and c not in self.world.occupancy:
                seen.add(c)
                uniq.append(c)
        self.rng.shuffle(uniq)
        return uniq

    def initial_food(self):
        pool = self._feeding_cells()
        k = 0
        for formula, target in ((FOOD_A, FOOD_TARGET_A), (FOOD_B, FOOD_TARGET_B)):
            for _ in range(target):
                cells = pool[k:k + 12]
                if not self._place(formula, cells):
                    self._place(formula)
                k += 12

    # ---------- 抓取 / 反应 / 并入 ----------
    def _remove_mol(self, mol):
        for key in [k for k in self.world.bonds if mol.uid in k]:
            em._remove_bond(self.world, key, "absorb")
        em._release(self.world, mol)
        self.world.molecules.pop(mol.uid, None)

    def _grab_cells(self):
        L = self.world.env.L
        grab = set()
        for c in self.body_cells:
            for dq in range(-GRAB_R, GRAB_R + 1):
                for dr in range(-GRAB_R, GRAB_R + 1):
                    if abs(dq) + abs(dr) + abs(dq + dr) <= 2 * GRAB_R:
                        grab.add(((c[0] + dq) % L, (c[1] + dr) % L))
        return grab

    def capture(self):
        if not self.body_cells:
            return 0
        grab = self._grab_cells()
        got = 0
        for mol in list(self.world.molecules.values()):
            if mol.formula not in (FOOD_A, FOOD_B):
                continue
            if not any(cc in grab for cc in em.world_mol_cells(self.world, mol)):
                continue
            if self.rng.random() >= P_CAP:
                continue
            self.buffer[mol.formula] += 1
            self.buffer_vec = addv(self.buffer_vec, list(mol.elem_vec))
            self._remove_mol(mol)
            got += 1
        self.captured += got
        return got

    def _adjacent_body_mols(self, mol):
        w = self.world
        body = set(self.body)
        nb = set()
        cells = set(em.world_mol_cells(w, mol))
        for c in cells:
            for off in ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)):
                for uid in w.occupancy.get(((c[0] + off[0]) % w.env.L, (c[1] + off[1]) % w.env.L), ()):
                    if uid in body and uid != mol.uid:
                        nb.add(uid)
        return [w.molecules[u] for u in nb]

    def assimilate(self, mol):
        """并入：新合成的 A 在体表，尝试与相邻体分子建立 1 条界面键（主动并入步骤）。

        只尝试能量/位点都允许的第一条键；成败仍由 emergence 的 _add_bond 判定，
        之后的维持/断裂也交给 step_world。
        """
        w = self.world
        for b in self._adjacent_body_mols(mol):
            free_a = [i for i in range(len(mol.sites)) if (mol.uid, i) not in w.site_use]
            free_b = [i for i in range(len(b.sites)) if (b.uid, i) not in w.site_use]
            if not free_a or not free_b:
                continue
            if len(em._bonds_of(w, mol.uid)) >= em._max_contacts(mol):
                continue
            if len(em._bonds_of(w, b.uid)) >= em._max_contacts(b):
                continue
            sa = max(free_a, key=lambda i: mol.sites[i].sigma)
            sb = max(free_b, key=lambda i: b.sites[i].sigma)
            wgt = em.interface_energy(mol, b, mol.sites[sa], b.sites[sb], w.env, self.P)
            if wgt < float(self.P.get("W_MIN", 0.15)):
                continue
            if em._add_bond(w, mol, b, sa, sb, wgt, contacts=[(sa, sb, wgt)]):
                return True
        return False

    def react_and_join(self, arm):
        while self.buffer[FOOD_A] >= 1 and self.buffer[FOOD_B] >= 1:
            self.buffer[FOOD_A] -= 1
            self.buffer[FOOD_B] -= 1
            self.buffer_vec = [self.buffer_vec[i] - V_FA[i] - V_FB[i] for i in range(9)]
            self.react += 1
            self.spawned += 1
            if arm == "farspawn":
                self._place(A_FORMULA)
            else:
                mol = self._place(A_FORMULA, self._free_cells_near(self.body_cells), near_body=True)
                if mol is not None and arm == "full":
                    mol.energy = max(mol.energy, 2.0)
                    if self.assimilate(mol):
                        self.body.append(mol.uid)
                        self._refresh_body()

    # ---------- 统计 ----------
    def elements(self):
        v = [0] * 9
        for m in self.world.molecules.values():
            v = addv(v, list(m.elem_vec))
        return addv(v, self.buffer_vec)

    def stats(self):
        em.rebuild_assemblies(self.world)
        body = None
        for a in self.world.assemblies.values():
            if self.body_seed in a.mols:
                body = a
                break
        if body is not None:
            self.body = list(body.mols)
        in_body = [self.world.molecules[u] for u in self.body if u in self.world.molecules]
        body_a = sum(1 for m in in_body if m.formula == A_FORMULA)
        total_a = sum(1 for m in self.world.molecules.values() if m.formula == A_FORMULA)
        self._refresh_body()
        return {
            "t": self.t,
            "N": len(self.world.molecules),
            "body_n": len(in_body),
            "body_molA": body_a,
            "body_bonds": len(body.bonds) if body is not None else 0,
            "body_E": round(body.E, 3) if body is not None else 0.0,
            "body_shape": body.shape if body is not None else "",
            "body_cells": len(self.body_cells),
            "free_A": total_a - body_a,
            "total_A": total_a,
            "in_assemblies": sum(len(a.mols) for a in self.world.assemblies.values()),
            "n_assemblies": len(self.world.assemblies),
            "buffer_A": self.buffer[FOOD_A],
            "buffer_B": self.buffer[FOOD_B],
            "captured": self.captured,
            "react": self.react,
            "spawned": self.spawned,
            "world_bonds": len(self.world.bonds),
        }


def run_arm(arm, steps, seed):
    env = Env(L=32, seed=seed)
    env.seed_body()
    n_seed = len(env.body)
    for _ in range(WARMUP):  # 预热：让种子组装体先成键稳定，再投放食物
        em.step_world(env.world)
        env.t += 1
    em.rebuild_assemblies(env.world)
    if arm != "bare":
        env.initial_food()
    series = [env.stats()]
    baseline = {"body_n": series[0]["body_n"], "body_molA": series[0]["body_molA"],
                "body_E": series[0]["body_E"], "seed_n": n_seed}
    v0 = env.elements()
    conserve = True
    for _ in range(steps):
        if arm != "bare":
            env.capture()
            if arm != "nochem":
                env.react_and_join(arm)
        em.step_world(env.world)
        env.t += 1
        if env.t % SNAP_EVERY == 0:
            series.append(env.stats())
            if env.elements() != v0:
                conserve = False
    st = env.stats()
    st["conservation_ok"] = conserve
    st["baseline"] = baseline
    return {"config": {"arm": arm, "steps": steps, "seed": seed, "L": 32,
                       "A": A_FORMULA, "food": [FOOD_A, FOOD_B],
                       "body_N0": BODY_N0, "grab_r": GRAB_R, "p_cap": P_CAP,
                       "warmup": WARMUP,
                       "food_total": [FOOD_TARGET_A, FOOD_TARGET_B]},
            "summary": st,
            "elements": env.elements(),
            "time_series": series}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="full", choices=["full", "nochem", "farspawn", "bare"])
    ap.add_argument("--steps", type=int, default=600)
    ap.add_argument("--seed", type=int, default=20261119)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    t0 = time.time()
    res = run_arm(args.arm, args.steps, args.seed)
    s = res["summary"]
    print("[t80] arm=%s steps=%d body=%d molA=%d bonds=%d E=%.1f react=%d cap=%d freeA=%d totA=%d conserve=%s (%.1fs)" % (
        args.arm, args.steps, s["body_n"], s["body_molA"], s["body_bonds"], s["body_E"], s["react"],
        s["captured"], s["free_A"], s["total_A"], s["conservation_ok"], time.time() - t0), flush=True)
    out = args.out or os.path.join(BASE, "t80_assembly_%s.json" % args.arm)
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print("[t80] wrote", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
