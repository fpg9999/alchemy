"""T84 九元素环境：三轴（质量/物态/温度）+ 三素力，**每个中间态骨架占 1 格**。

在 T83 的基础上改两件事（用户 m02648）：
1) 分子不再只占 1 格：一个分子由 k 个"中间态骨架块"组成，就占 k 个格子
   （k = len(attrs.skeleton_units(...))，无三价骨架的分子算 1 块；
   目录外产物按 平均 8.08 原子/骨架 估算）；格子占用、移动、接触、反应都按 footprint 处理。
2) 自然降温到 ~20°C：Tamb(t) = 10 + 990·exp(−4.5·t/(ticks−1))，1200 拍后 ≈ 21.1°C。

复用 t83_env_axes 的物理（三素力、重力、物态迁移、规则 1~11 反应、恒素场）。
"""

from __future__ import annotations

import argparse
import io
import json
import math
import random
import time

from alchemy import attrs as A
import t83_env_axes as T83
from t83_env_axes import (
    World as BaseWorld,
    MODE_MULT, GRAV, STATE_MOB, DIRS,
    comp_of, vec_of, natoms_of, atoms_from_comp,
    catalog_index, load_feed, ELEMS,
)

ATOMS_PER_SKEL = 8.08


def skel_shape(k):
    """k 个骨架格的紧凑 footprint：1→1x1, 2→1x2, 3→1x3, 4→2x2, 其余取近似方阵。"""
    k = max(1, int(k))
    if k == 1:
        return [(0, 0)]
    if k == 2:
        return [(0, 0), (1, 0)]
    if k == 3:
        return [(0, 0), (1, 0), (2, 0)]
    if k == 4:
        return [(0, 0), (0, 1), (1, 0), (1, 1)]
    cols = int(math.ceil(math.sqrt(k)))
    rows = int(math.ceil(k / float(cols)))
    return [(r, c) for r in range(rows) for c in range(cols)][:k]


class SkelWorld(BaseWorld):
    def __init__(self, W, H, seed, feed, recs, cap=26, p_react=0.01,
                 force_r=2, lock_r=2, lock_w=1.0,
                 e_cells=(10, 20), t0=1000.0, t_end=10.0, cool_k=4.5):
        self.n_skel_cache = {}
        self.n_cells_used = 0
        super().__init__(W, H, seed, feed, recs, cap=cap, p_react=p_react,
                         force_r=force_r, lock_r=lock_r,
                         lock_w=lock_w, e_cells=e_cells, t0=t0,
                         t_end=t_end, cool_k=cool_k)

    # ------------------------------------------------------------------
    def ensure_type(self, formula):
        t = self.types.get(formula)
        if t is not None:
            return t
        t = super().ensure_type(formula)
        if "k" not in t:
            rec = self.recs.get(formula)
            if rec:
                atoms = tuple(rec["atoms"])
                edges = [tuple(e) for e in rec["edges"]]
                k = len(A.skeleton_units(atoms, edges))
            else:
                k = 0
            if k <= 0:
                k = max(1, int(round(t["natoms"] / ATOMS_PER_SKEL)))
            t["k"] = k
            t["shape"] = skel_shape(k)
        return t

    # ------------------------------------------------------------------
    def _free_footprint(self, r, c, formula, rmax=3):
        """在 (r,c) 附近找一个 footprint 全空的放置点；返回 cells 或 None。"""
        self.ensure_type(formula)
        shp = self.types[formula]["shape"]
        r0, r1 = max(0, r - rmax), min(self.H, r + rmax + 1)
        c0, c1 = max(0, c - rmax), min(self.W, c + rmax + 1)
        for rr in range(r0, r1):
            for cc in range(c0, c1):
                cells = [(rr + dr, cc + dc) for dr, dc in shp]
                if all(0 <= x < self.H and 0 <= y < self.W
                       and (x, y) not in self.cell for x, y in cells):
                    return cells
        return None

    def _carve(self, r, c, formula, rmax=6):
        """在 (r,c) 附近占位为分子 formula 的 footprint（调用方保证空闲）。"""
        self.ensure_type(formula)
        shp = self.types[formula]["shape"]
        cells = [(r + dr, c + dc) for dr, dc in shp]
        return cells

    def add_mol(self, formula, r, c, cells=None):
        mid = self.next_id
        self.next_id += 1
        self.ensure_type(formula)
        if cells is None:
            cells = self._free_footprint(r, c, formula)
            if cells is None:
                return None
        self.mols.append({"id": mid, "f": formula, "r": cells[0][0],
                          "c": cells[0][1], "cells": list(cells), "dead": False})
        for (rr, cc) in cells:
            self.cell[(rr, cc)] = mid
        self.n_cells_used += len(cells)
        return mid

    def _place_feed(self, feed):
        for formula in feed:
            placed = False
            for _ in range(60):
                r = self.rng.randrange(self.H)
                c = self.rng.randrange(self.W)
                cells = self._free_footprint(r, c, formula)
                if cells:
                    self.add_mol(formula, r, c, cells=cells)
                    placed = True
                    break
            if not placed:
                raise RuntimeError("cannot place feed molecule " + formula)

    def _kill(self, mid):
        m = self.mols[mid]
        if m["dead"]:
            return
        m["dead"] = True
        for (r, c) in m["cells"]:
            if self.cell.get((r, c)) == mid:
                self.cell.pop((r, c), None)
        self.n_cells_used -= len(m["cells"])
        for p in list(self.locks.get(mid, ())):
            other = self.locks.get(p)
            if other is not None:
                other.discard(mid)
        self.locks.pop(mid, None)

    # ------------------------------------------------------------------
    def _try_move(self, mid, dr, dc):
        m = self.mols[mid]
        nr, nc = m["r"] + dr, m["c"] + dc
        if not self._lock_ok(mid, nr, nc):
            self.n_blocked += 1
            return False
        new = [(r + dr, c + dc) for (r, c) in m["cells"]]
        for (r, c) in new:
            if not (0 <= r < self.H and 0 <= c < self.W):
                self.n_blocked += 1
                return False
            other = self.cell.get((r, c))
            if other is not None and other != mid:
                self.n_blocked += 1
                return False
        for (r, c) in m["cells"]:
            if self.cell.get((r, c)) == mid:
                self.cell.pop((r, c), None)
        m["cells"] = new
        m["r"], m["c"] = nr, nc
        for (r, c) in new:
            self.cell[(r, c)] = mid
        return True

    # ------------------------------------------------------------------
    def _cells_of(self, mid):
        return self.mols[mid]["cells"]

    def _fit_near(self, center, formula, free_ids):
        """在 center 附近为 formula 找 footprint；临时把 free_ids 的格子视为空。"""
        self.ensure_type(formula)
        saved = {}
        for mid in free_ids:
            for (r, c) in self.mols[mid]["cells"]:
                if self.cell.get((r, c)) == mid:
                    saved[(r, c)] = self.cell.pop((r, c))
        try:
            cells = self._free_footprint(center[0], center[1], formula, rmax=8)
        finally:
            for (r, c), v in saved.items():
                self.cell[(r, c)] = v
        return cells

    def _assign(self, mid, formula, cells):
        m = self.mols[mid]
        for (r, c) in m["cells"]:
            if self.cell.get((r, c)) == mid:
                self.cell.pop((r, c), None)
        m["f"] = formula
        m["cells"] = list(cells)
        m["r"], m["c"] = cells[0]
        for (r, c) in cells:
            self.cell[(r, c)] = mid

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
        # 取两个分子的格集中心作为放置参考
        cells_all = list(mi["cells"]) + list(mj["cells"])
        cr = sum(r for r, c in cells_all) // len(cells_all)
        cc = sum(c for r, c in cells_all) // len(cells_all)
        # 先找 products 的落点（把 i、j 的格子临时视为空）
        c1 = self._fit_near((cr, cc), pf[0], {i, j})
        if c1 is None:
            self.n_react_fail += 1
            return False
        c2 = None
        if len(pf) == 2:
            # 需要另一个 footprint：临时把 i、j 与 c1 视为占用
            c2 = self._fit_near((cr, cc), pf[1], {i, j})
            if c2 is None:
                self.n_react_fail += 1
                return False
            if set(c2) & set(c1):
                self.n_react_fail += 1
                return False
        # 应用
        si, sj = ti["tiers"]["state"], tj["tiers"]["state"]
        key = ("气-气" if si == sj == 0 else
               ("液-液" if si == sj == 1 else
                ("固-固" if si == sj == 2 else
                 ("气-液" if {si, sj} <= {0, 1} else "含固"))))
        self.mode_counts[key] = self.mode_counts.get(key, 0) + 1
        band = 0 if mi["r"] > 2 * self.H // 3 else (
            2 if mi["r"] < self.H // 3 else 1)
        self.band_react[band] += 1
        self._kill(j)
        self._assign(i, pf[0], c1)
        if len(pf) == 2:
            # 新分子 id 追加
            mid = self.next_id
            self.next_id += 1
            self.ensure_type(pf[1])
            self.mols.append({"id": mid, "f": pf[1], "r": c2[0][0],
                              "c": c2[0][1], "cells": list(c2), "dead": False})
            for (r, c) in c2:
                self.cell[(r, c)] = mid
            self.n_cells_used += len(c2)
        self.ensure_type(pf[0])
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
            gate = 0.15 + 0.85 * self.rho_at(m["r"], m["c"])
            cands = set()
            for (r, c) in m["cells"]:
                for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                    nb = self.cell.get((r + dr, c + dc))
                    if (nb is not None and nb != i and nb not in handled
                            and not self.mols[nb]["dead"]):
                        cands.add(nb)
            if not cands:
                continue
            nb = self.rng.choice(sorted(cands))
            ti = self.types[m["f"]]
            tj = self.types[self.mols[nb]["f"]]
            p = (self.p_react * MODE_MULT[(ti["tiers"]["state"],
                                          tj["tiers"]["state"])] * gate)
            if self.rng.random() >= p:
                continue
            handled.add(i)
            handled.add(nb)
            self._try_react(i, nb, p)

    # ------------------------------------------------------------------
    def snapshot(self, t):
        s = super().snapshot(t)
        s["mols"] = [[m["r"], m["c"], m["f"], self.types[m["f"]]["k"]]
                     for m in self.live_mols()]
        used = sum(len(m["cells"]) for m in self.live_mols())
        s["cells_used"] = used
        s["cells_total"] = self.W * self.H
        return s


def run(W=320, H=220, seed=20261120, target=7000, ticks=1200,
        cap=26, p_react=0.01, force_r=2, snap_every=200,
        out="t84_env_skel_result.json", quick=False):
    t_start = time.time()
    recs = catalog_index()
    feed, feed_meta = load_feed(target=target)
    if quick:
        step = max(1, len(feed) // 300)
        feed = feed[::step][:300]
        ticks = min(ticks, 60)
        W, H = 140, 100
    w = SkelWorld(W, H, seed, feed, recs, cap=cap, p_react=p_react,
                  force_r=force_r, t_end=10.0, cool_k=4.5)
    w.ticks_total = ticks
    n0 = len(w.live_mols())
    print("world %dx%d  molecules=%d  footprint_cells=%d  cap=%d  "
          "p_react=%g  ticks=%d  T0=%.0f -> ~20C"
          % (W, H, n0, w.n_cells_used, cap, p_react, ticks, w.t0))
    snaps = [w.snapshot(0)]
    el0 = w.elements()
    for t in range(1, ticks + 1):
        w.t = t
        w.step()
        if t % snap_every == 0 or t == ticks:
            s = w.snapshot(t)
            snaps.append(s)
            print("t=%4d T=%6.1f N=%5d cells=%6d dist=%4d react=%6d new=%4d "
                  "max_cl=%3d rho=%.2f y=%s  %.1fs"
                  % (t, s["T"], s["n"], s["cells_used"], s["n_distinct"],
                     s["n_react"], s["n_new_species"], s["clusters"]["max"],
                     s["rho"]["mean"], s["y_mean_mass"], time.time() - t_start))
    el1 = w.elements()
    ok = el0 == el1
    comp = w.composition()
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
    result = {
        "config": {
            "engine": "T84 方格环境：三轴 + 三素力 + 中间态骨架占格（每骨架 1 格）",
            "W": W, "H": H, "seed": seed, "ticks": ticks, "cap": cap,
            "p_react": p_react, "force_r": force_r,
            "lock_w": w.lock_w, "lock_r": w.lock_r,
            "T0": w.t0, "T_end": w.t_end, "cool_k": w.cool_k,
            "e_cells": [w.EW, w.EH], "snap_every": snap_every, "quick": quick,
            "footprint": "k = len(skeleton_units)，无三价骨架=1；目录外产物按 8.08 原子/骨架估算",
            "feed": feed_meta, "feed_file": "t62_loads.json",
            "runtime_s": round(time.time() - t_start, 2),
        },
        "summary": {
            "n0": snaps[0]["n"], "n_final": snaps[-1]["n"],
            "cells_used_final": snaps[-1]["cells_used"],
            "cells_total": W * H,
            "n_react": w.n_react, "n_react_fail": w.n_react_fail,
            "n_new_species": len(w.new_species),
            "n_moves": w.n_moves, "n_blocked": w.n_blocked,
            "n_brown": w.n_brown, "n_swap": w.n_swap,
            "elements0": el0, "elements1": el1, "conservation_ok": ok,
            "clusters": snaps[-1]["clusters"],
            "tiers": snaps[-1]["tiers"],
            "y_mean_mass": snaps[-1]["y_mean_mass"],
            "rho": snaps[-1]["rho"],
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
    print("conservation_ok=%s N0=%d N=%d react=%d new=%d"
          % (ok, snaps[0]["n"], snaps[-1]["n"], w.n_react,
             len(w.new_species)))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--W", type=int, default=320)
    ap.add_argument("--H", type=int, default=220)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--target", type=int, default=7000)
    ap.add_argument("--ticks", type=int, default=1200)
    ap.add_argument("--cap", type=int, default=26)
    ap.add_argument("--p-react", type=float, default=0.01)
    ap.add_argument("--force-r", type=int, default=2)
    ap.add_argument("--snap-every", type=int, default=200)
    ap.add_argument("--out", default="t84_env_skel_result.json")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    run(W=a.W, H=a.H, seed=a.seed, target=a.target, ticks=a.ticks,
        cap=a.cap, p_react=a.p_react, force_r=a.force_r,
        snap_every=a.snap_every, out=a.out, quick=a.quick)


if __name__ == "__main__":
    main()
