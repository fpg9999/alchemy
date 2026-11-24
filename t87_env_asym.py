"""T87 九元素环境：取消质量阈值（连续重力）+ 非对称分子间作用力 + 自主动力学观察。

相对 T86 的改动（用户 m03149）：
1) 取消质量档位：不再用 GRAV={轻,中,重}，改为"只要有质量就受重力"：
   每拍竖直速度累加 `gacc += G_GRAV * mass`（mass 为 0~3 连续值），
   整数部分化为向下位移；质量越大每拍下沉越多（mass=3 → 约 0.9 格/拍，
   mass=2 → 0.6，mass=1 → 0.3，mass=0 不动）。被占格时只与"更轻"的分子
   交换（质量比 <0.75 且概率 0.65），固/液/气都可被更重的压下去。
2) 分子间作用力改为**非对称**、且不使用匹配度 J：
     作用在 B 上的力 F_B = K_A·A_A·F(d, r_att_A) − K_R·R_B·F(d, r_rep_B)
     作用在 A 上的力 F_A = K_A·A_B·F(d, r_att_B) − K_R·R_A·F(d, r_rep_A)
   其中 A=聚素平均吸引力、R=动素平均排斥力、r_att/r_rep=散素覆盖半径。
   于是 A 吸引 B 的同时 B 可以排斥 A（净力不对称、不守恒动量）——这正是
   多分子团产生"自主移动"的来源。
3) 温度降到 10°C 后维持 800 拍（cool_ticks=600, ticks=1400），
   期间每 25 拍做一次团簇跟踪（大小/质心/包围盒/平均质量/平均 A、R），
   每 200 拍存一次全环境快照，供多时间切片与运动轨迹分析。

输出：t87_env_asym_result.json（投影 + 快照 + 团簇跟踪帧）。
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time

from alchemy import three_su as TS

import t83_env_axes as T83
import t84_env_skel as T84
import t85_env_resolve as T85
import t86_env_tri as T86
from t83_env_axes import (
    comp_of, vec_of, natoms_of, catalog_index,
)

# 连续重力：每拍竖直速度增量（单位：格/拍）
G_GRAV = 0.30
# 非对称力系数
K_A = TS.K_A      # 2.5
K_R = TS.K_R      # 0.5
# 交换阈值
SWAP_MASS_RATIO = 0.75
SWAP_P = 0.65


class AsymWorld(T86.TriWorld):
    """连续重力 + 非对称作用力 + 团簇跟踪。"""

    def __init__(self, *a, track_every=25, **kw):
        self.track_every = track_every
        self.frames = []
        self._pair_cache = {}
        super().__init__(*a, **kw)

    # ------------------------------------------------------------------
    def ensure_type(self, formula):
        t = super().ensure_type(formula)
        if "A" not in t:
            # T96：半径封顶 == 力扫描窗口（force_r），与 pair_force/force_on 口径一致
            sc = TS.scores(t["comp"], r_max=int(self.force_r))
            t["A"] = sc["A"]
            t["R"] = sc["D"]
            t["r_att"] = sc["r_att"]
            t["r_rep"] = sc["r_rep"]
        return t

    # -- 非对称力 --------------------------------------------------------
    def pair_asym(self, fi, fj, d):
        """返回 (作用在 j 上的力, 作用在 i 上的力)。"""
        key = (fi, fj, d)
        v = self._pair_cache.get(key)
        if v is not None:
            return v
        ti, tj = self.types[fi], self.types[fj]
        f_ij = (K_A * ti["A"] * TS.decay(d, ti["r_att"])
                - K_R * tj["R"] * TS.decay(d, tj["r_rep"]))
        f_ji = (K_A * tj["A"] * TS.decay(d, tj["r_att"])
                - K_R * ti["R"] * TS.decay(d, ti["r_rep"]))
        v = (f_ij, f_ji)
        self._pair_cache[key] = v
        return v

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
                f_on_me, _ = self.pair_asym(self.mols[nb]["f"], m["f"], d)
                if f_on_me == 0.0:
                    continue
                sx += f_on_me * dc / d
                sy += f_on_me * dr / d
        return sx, sy

    # -- 重力（连续）-----------------------------------------------------
    def _gravity_step(self, mid):
        m = self.mols[mid]
        cells = m["cells"]
        newc = [(r + 1, c) for (r, c) in cells]
        if any(r >= self.H for r, c in newc):
            return False
        blocking = set()
        for (r, c) in newc:
            o = self.cell.get((r, c))
            if o is not None and o != mid:
                blocking.add(o)
        if not blocking:
            for (r, c) in cells:
                if self.cell.get((r, c)) == mid:
                    self.cell.pop((r, c), None)
            for (r, c) in newc:
                self.cell[(r, c)] = mid
            m["cells"] = newc
            m["r"] = newc[0][0]
            m["c"] = newc[0][1]
            return True
        # 只有单格分子之间才允许"重压轻"交换
        if len(blocking) == 1 and len(cells) == 1:
            oid = next(iter(blocking))
            om = self.mols[oid]
            if om["dead"] or len(om["cells"]) != 1:
                return False
            mi = self.types[m["f"]]["mass"]
            mo = self.types[om["f"]]["mass"]
            if mo < mi * SWAP_MASS_RATIO and self.rng.random() < SWAP_P:
                r, c = cells[0]
                nr = r + 1
                self.cell[(nr, c)] = mid
                self.cell[(r, c)] = oid
                m["cells"] = [(nr, c)]
                m["r"], m["c"] = nr, c
                om["cells"] = [(r, c)]
                om["r"], om["c"] = r, c
                self.n_swap += 1
                return True
        return False

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
            # 1) 重力：连续累积
            gacc = m.get("gacc", 0.0) + G_GRAV * t["mass"]
            gsteps = int(gacc)
            m["gacc"] = gacc - gsteps
            for _ in range(min(gsteps, 3)):
                if not self._gravity_step(mid):
                    break
            # 2) 非对称力驱动的横向/方向运动
            sx, sy = self.force_on(mid)
            norm = math.hypot(sx, sy)
            if norm > 1e-9:
                ang = math.atan2(sy, sx)
                k = int(round(ang / (math.pi / 4.0))) % 8
                dr, dc = T83.DIRS[k]
                p = T83.STATE_MOB[st] * min(1.0, 0.20 + 0.80 * norm)
                if self.rng.random() < p:
                    if self._try_move(mid, dr, dc):
                        self.n_moves += 1
                        continue
        self.react_phase()
        self.rebuild_locks()
        if self.track_every and self.t % self.track_every == 0:
            self.track_clusters()

    # -- 团簇跟踪 --------------------------------------------------------
    def _cluster_of_mols(self):
        seen = set()
        clusters = []
        for (r, c), mid in self.cell.items():
            if mid in seen or self.mols[mid]["dead"]:
                continue
            stack = [(r, c)]
            seen.add(mid)
            cells = []
            mids = []
            while stack:
                rr, cc = stack.pop()
                mm = self.cell.get((rr, cc))
                if mm is None or mm in mids:
                    continue
                mids.append(mm)
                cells.append((rr, cc))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        x, y = rr + dr, cc + dc
                        if 0 <= x < self.H and 0 <= y < self.W:
                            nb = self.cell.get((x, y))
                            if nb is not None and nb not in seen:
                                seen.add(nb)
                                stack.append((x, y))
            if len(mids) >= 3:
                cells_all = []
                for mm in mids:
                    cells_all.extend(self.mols[mm]["cells"])
                rs = [x for x, y in cells_all]
                cs = [y for x, y in cells_all]
                masses = [self.types[self.mols[mm]["f"]]["mass"] for mm in mids]
                As = [self.types[self.mols[mm]["f"]]["A"] for mm in mids]
                Rs = [self.types[self.mols[mm]["f"]]["R"] for mm in mids]
                clusters.append({
                    "n": len(mids),
                    "cr": round(sum(rs) / len(rs), 2),
                    "cc": round(sum(cs) / len(cs), 2),
                    "r0": min(rs), "r1": max(rs),
                    "c0": min(cs), "c1": max(cs),
                    "mass": round(sum(masses) / len(masses), 2),
                    "A": round(sum(As) / len(As), 2),
                    "R": round(sum(Rs) / len(Rs), 2),
                    "top": sorted(
                        ((self.mols[mm]["f"] for mm in mids)),
                        key=lambda f: -sum(1 for mm in mids
                                           if self.mols[mm]["f"] == f))[:3],
                })
        return clusters

    def track_clusters(self):
        cl = self._cluster_of_mols()
        self.frames.append({"t": self.t, "n_live": len(self.live_mols()),
                            "clusters": cl})

    def snapshot(self, t):
        s = super().snapshot(t)
        return s


def run(W=320, H=220, seed=20261120, target=7000, ticks=1400,
        cool_ticks=600, cap=36, p_react=0.012, force_r=2, snap_every=200,
        track_every=25, out="t87_env_asym_result.json", quick=False):
    t_start = time.time()
    recs = catalog_index()
    feed, feed_meta = T86.load_feed_tri(target=target)
    if quick:
        step = max(1, len(feed) // 300)
        feed = feed[::step][:300]
        ticks = min(ticks, 80)
        cool_ticks = min(cool_ticks, 40)
        W, H = 140, 100
    w = AsymWorld(W, H, seed, feed, recs, cap=cap, p_react=p_react,
                  force_r=force_r, t_end=10.0, cool_k=10.0,
                  cool_ticks=cool_ticks, track_every=track_every)
    w.ticks_total = ticks
    n0 = len(w.live_mols())
    print("world %dx%d  molecules=%d  cells=%d  mass=continuous(G=%.2f)  "
          "asym force KA=%.1f KR=%.1f  cap=%d  ticks=%d cool_ticks=%d  T0=%.0f -> %.0fC"
          % (W, H, n0, w.n_cells_used, G_GRAV, K_A, K_R, w.cap, ticks,
             cool_ticks, w.t0, w.t_end), flush=True)
    snaps = [w.snapshot(0)]
    el0 = w.elements()
    for t in range(1, ticks + 1):
        w.t = t
        w.step()
        if t % snap_every == 0 or t == ticks:
            s = w.snapshot(t)
            snaps.append(s)
            print("t=%4d T=%6.1f N=%5d cells=%6d dist=%4d react=%6d "
                  "[C%d I%d N%d D%d] new=%4d max_cl=%4d y=%s  %.1fs"
                  % (t, s["T"], s["n"], s["cells_used"], s["n_distinct"],
                     s["n_react"], s["n_complete"], s["n_incomplete"],
                     s["n_none"], s["n_decomp"], s["n_new_species"],
                     s["clusters"]["max"], s["y_mean_mass"],
                     time.time() - t_start), flush=True)
    el1 = w.elements()
    ok = el0 == el1
    comp = w.composition()
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
    result = {
        "config": {
            "engine": "T87 方格环境：连续重力（质量阈值取消）+ 非对称分子间作用力（无匹配度）+ 团簇跟踪",
            "W": W, "H": H, "seed": seed, "ticks": ticks,
            "cool_ticks": cool_ticks, "T_end": w.t_end,
            "gravity": {"mode": "continuous", "G": G_GRAV,
                        "note": "gacc += G*mass；int 部分下沉；质量越大下沉越快"},
            "force": {"mode": "asymmetric", "K_A": K_A, "K_R": K_R,
                      "matching": "none (no J)",
                      "F_B_from_A": "K_A*A_A*F(d,ratt_A) - K_R*R_B*F(d,rrep_B)",
                      "F_A_from_B": "K_A*A_B*F(d,ratt_B) - K_R*R_A*F(d,rrep_A)"},
            "cap": cap, "max_group": w.max_group, "p_react": p_react,
            "force_r": force_r, "lock_w": w.lock_w, "lock_r": w.lock_r,
            "e_cells": [w.EW, w.EH], "snap_every": snap_every,
            "track_every": track_every, "quick": quick, "feed": feed_meta,
            "runtime_s": round(time.time() - t_start, 2),
        },
        "summary": {
            "n0": snaps[0]["n"], "n_final": snaps[-1]["n"],
            "cells_used_final": snaps[-1]["cells_used"],
            "cells_total": W * H,
            "n_complete": w.n_complete, "n_incomplete": w.n_incomplete,
            "n_none": w.n_none, "n_decomp": w.n_decomp,
            "n_react": w.n_react, "n_react_fail": w.n_react_fail,
            "react_types": dict(w.react_types),
            "n_new_species": len(w.new_species),
            "n_moves": w.n_moves, "n_blocked": w.n_blocked,
            "n_brown": w.n_brown, "n_swap": w.n_swap,
            "elements0": el0, "elements1": el1, "conservation_ok": ok,
            "clusters": snaps[-1]["clusters"],
            "tiers": snaps[-1]["tiers"],
            "y_mean_mass": snaps[-1]["y_mean_mass"],
            "mass_mean": snaps[-1].get("mass_mean"),
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
        "track": w.frames,
    }
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)
    print("saved %s  (%.1fs)" % (out, time.time() - t_start))
    print("conservation_ok=%s N0=%d N=%d complete=%d incomplete=%d none=%d "
          "decomp=%d new=%d frames=%d"
          % (ok, snaps[0]["n"], snaps[-1]["n"], w.n_complete, w.n_incomplete,
             w.n_none, w.n_decomp, len(w.new_species), len(w.frames)))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--W", type=int, default=320)
    ap.add_argument("--H", type=int, default=220)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--target", type=int, default=7000)
    ap.add_argument("--ticks", type=int, default=1400)
    ap.add_argument("--cool-ticks", type=int, default=600)
    ap.add_argument("--cap", type=int, default=36)
    ap.add_argument("--p-react", type=float, default=0.012)
    ap.add_argument("--force-r", type=int, default=2)
    ap.add_argument("--snap-every", type=int, default=200)
    ap.add_argument("--track-every", type=int, default=25)
    ap.add_argument("--out", default="t87_env_asym_result.json")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    run(W=a.W, H=a.H, seed=a.seed, target=a.target, ticks=a.ticks,
        cool_ticks=a.cool_ticks, cap=a.cap, p_react=a.p_react,
        force_r=a.force_r, snap_every=a.snap_every,
        track_every=a.track_every, out=a.out, quick=a.quick)


if __name__ == "__main__":
    main()
