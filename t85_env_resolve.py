"""T85 九元素环境：骨架占格 + 更低质量阈值 + 10°C 恒温平台 + 完全/不完全反应。

相对 T84 的三处改动（用户 m02870）：
1) 质量阈值调低：默认 (1.20, 1.85)（原来 (1.67, 2.30)）→ 更多分子进入"重"档下沉。
   只在实验脚本里覆盖阈值，不改内核 alchemy/attrs.py。
2) 温度：1000°C 指数冷却到 10°C，然后恒温 10°C 保持一段（默认 cool_ticks=650，
   total ticks=1200 → 后 550 拍恒温）。
3) 反应改用 natural_engine.resolve(pair, T)：同时出现 complete / incomplete /
   none（以及 self_decomp 分支），统计四类；不再只调 complete_products。
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time

from alchemy import attrs as A
from alchemy.core.elements import ORDER as ELEM_ORDER

import natural_engine as E
import t83_env_axes as T83
import t84_env_skel as T84
from t83_env_axes import (
    comp_of, vec_of, natoms_of, atoms_from_comp,
    catalog_index, load_feed, ELEMS, MODE_MULT,
)

# 降低质量阈值：更多"重"档（默认 1.67/2.30 → 1.20/1.85）
MASS_THRESH = {"mass": (1.20, 1.85),
               "state": (1.70, 2.22),
               "temperature": (1.50, 2.00)}


class ResolveWorld(T84.SkelWorld):
    def __init__(self, *a, cool_ticks=650, **kw):
        self.md_cache = {}
        self.cool_ticks = cool_ticks
        self.n_complete = 0
        self.n_incomplete = 0
        self.n_none = 0
        self.n_decomp = 0
        self.n_react = 0
        self.n_react_fail = 0
        self.react_types = {}
        super().__init__(*a, **kw)

    # ------------------------------------------------------------------
    def _md(self, formula):
        md = self.md_cache.get(formula)
        if md is not None:
            return md
        t = self.ensure_type(formula)
        rec = self.recs.get(formula)
        if rec is not None:
            atoms = tuple(rec["atoms"])
            edges = [tuple(e) for e in rec["edges"]]
        else:
            atoms = tuple(atoms_from_comp(t["comp"]))
            edges = []
        md = {"formula": formula, "atoms": atoms, "edges": edges,
              "vec": t["vec"], "c": max(1, t["natoms"] - 1), "label": formula}
        self.md_cache[formula] = md
        return md

    def ensure_type(self, formula):
        t = self.types.get(formula)
        if t is not None:
            return t
        rec = self.recs.get(formula)
        if rec is not None:
            atoms = tuple(rec["atoms"])
            edges = [tuple(e) for e in rec["edges"]]
        else:
            md = self.md_cache.get(formula)
            if md is not None:
                atoms, edges = tuple(md["atoms"]), [tuple(e) for e in md["edges"]]
            else:
                comp = comp_of(formula)
                atoms = tuple(atoms_from_comp(comp))
                edges = []
        comp = comp_of(formula)
        at = A.molecule_attrs(list(atoms), [list(e) for e in edges])
        prop = A.property_of(at, thresholds=MASS_THRESH)
        _g2i = {"低": 0, "中": 1, "高": 2}
        tiers = {k: _g2i[v] for k, v in prop["grades"].items()}
        k = 0
        try:
            k = len(A.skeleton_units(list(atoms), [tuple(e) for e in edges]))
        except Exception:
            k = 0
        if k <= 0:
            k = max(1, int(round(natoms_of(comp) / T84.ATOMS_PER_SKEL)))
        t = {
            "comp": comp, "vec": vec_of(comp), "natoms": natoms_of(comp),
            "mass": at["mass"], "state": at["state"],
            "temp": at["temperature"], "tiers": tiers, "cell": prop["cell"],
            "k": k, "shape": T84.skel_shape(k),
        }
        self.types[formula] = t
        if formula not in self.catalog_set:
            self.new_species.setdefault(formula, {"first_t": self.t,
                                                  "atoms": t["natoms"]})
        return t

    # ------------------------------------------------------------------
    def ambient_T(self, t):
        """冷却到 t_end 后恒温保持。"""
        if t <= self.cool_ticks:
            return self.t_end + (self.t0 - self.t_end) * math.exp(
                -10.0 * t / max(1, self.cool_ticks))
        return self.t_end

    # ------------------------------------------------------------------
    def _spawn(self, mds, center, free_ids):
        """在 center 附近放置一组产物；成功返回 True。"""
        saved = []
        for mid in free_ids:
            for (r, c) in self.mols[mid]["cells"]:
                if self.cell.get((r, c)) == mid:
                    saved.append(((r, c), self.cell.pop((r, c))))
        try:
            reserved = []
            placed = []
            for md in mds:
                f = md["formula"]
                cells = self._find_footprint(center, f, reserved)
                if cells is None:
                    return False
                reserved.extend(cells)
                placed.append((md, cells))
        finally:
            for (r, c), v in saved:
                self.cell[(r, c)] = v
        return placed

    def _find_footprint(self, center, formula, reserved):
        self.ensure_type(formula)
        shp = self.types[formula]["shape"]
        r0, r1 = max(0, center[0] - 10), min(self.H, center[0] + 11)
        c0, c1 = max(0, center[1] - 10), min(self.W, center[1] + 11)
        for rr in range(r0, r1):
            for cc in range(c0, c1):
                cells = [(rr + dr, cc + dc) for dr, dc in shp]
                if not all(0 <= x < self.H and 0 <= y < self.W
                           for x, y in cells):
                    continue
                if any((x, y) in self.cell or (x, y) in reserved
                       for x, y in cells):
                    continue
                return cells
        return None

    def _add_with(self, md, cells):
        mid = self.next_id
        self.next_id += 1
        self.ensure_type(md["formula"])
        self.mols.append({"id": mid, "f": md["formula"], "r": cells[0][0],
                          "c": cells[0][1], "cells": list(cells),
                          "dead": False})
        for (r, c) in cells:
            self.cell[(r, c)] = mid
        self.n_cells_used += len(cells)
        return mid

    def _md_of(self, mid):
        f = self.mols[mid]["f"]
        return self._md(f)

    def _try_react(self, i, j, mult):
        mi, mj = self.mols[i], self.mols[j]
        mdi, mdj = self._md_of(i), self._md_of(j)
        if mi["f"] == mj["f"] and mdj["c"] == mdi["c"] and mi["f"] == mj["f"]:
            pass
        total_atoms = (self.types[mi["f"]]["natoms"]
                       + self.types[mj["f"]]["natoms"])
        if total_atoms > self.cap:
            self.n_react_fail += 1
            return False
        try:
            res = E.resolve([mdi, mdj], self.Tamb)
        except Exception:
            self.n_react_fail += 1
            return False
        typ = res["type"]
        prods = res.get("products")
        states = res.get("state") or []
        self.react_types[typ] = self.react_types.get(typ, 0) + 1
        if typ == "none":
            if res.get("stages"):
                # 自分解：none 但状态已变
                new = [s for s in states
                       if not (s["formula"] == mi["f"] and len(states) == 2)]
                if len(new) == 2 and {new[0]["formula"], new[1]["formula"]} == {
                        mi["f"], mj["f"]}:
                    self.n_none += 1
                    return False
                self.n_decomp += 1
                return self._apply_products(new, (mi, mj))
            self.n_none += 1
            return False
        if typ == "incomplete":
            self.n_incomplete += 1
        else:
            self.n_complete += 1
        if not prods:
            self.n_react_fail += 1
            return False
        # 若产物与输入完全相同，视为无变化
        pf = sorted(p["formula"] for p in prods)
        if pf == sorted([mi["f"], mj["f"]]):
            return False
        return self._apply_products(prods, (mi, mj))

    def _apply_products(self, prods, pair):
        mi, mj = pair
        cells_all = list(mi["cells"]) + list(mj["cells"])
        cr = sum(r for r, c in cells_all) // len(cells_all)
        cc = sum(c for r, c in cells_all) // len(cells_all)
        placed = self._spawn(prods, (cr, cc), {mi["id"], mj["id"]})
        if not placed:
            self.n_react_fail += 1
            return False
        # 统计模式与高度
        ti = self.types[mi["f"]]
        tj = self.types[mj["f"]]
        si, sj = ti["tiers"]["state"], tj["tiers"]["state"]
        key = ("气-气" if si == sj == 0 else
               ("液-液" if si == sj == 1 else
                ("固-固" if si == sj == 2 else
                 ("气-液" if {si, sj} <= {0, 1} else "含固"))))
        self.mode_counts[key] = self.mode_counts.get(key, 0) + 1
        band = 0 if mi["r"] > 2 * self.H // 3 else (
            2 if mi["r"] < self.H // 3 else 1)
        self.band_react[band] += 1
        # 应用：先移除旧的两个，再放新的
        self._kill(mi["id"])
        self._kill(mj["id"])
        for md, cells in placed:
            self.md_cache[md["formula"]] = md
            self._add_with(md, cells)
        self.n_react += 1
        return True

    # ------------------------------------------------------------------
    def snapshot(self, t):
        s = super().snapshot(t)
        s["react_types"] = dict(self.react_types)
        s["n_complete"] = self.n_complete
        s["n_incomplete"] = self.n_incomplete
        s["n_none"] = self.n_none
        s["n_decomp"] = self.n_decomp
        return s


def run(W=320, H=220, seed=20261120, target=7000, ticks=1200,
        cool_ticks=650, cap=26, p_react=0.012, force_r=2, snap_every=200,
        out="t85_env_resolve_result.json", quick=False):
    t_start = time.time()
    recs = catalog_index()
    feed, feed_meta = load_feed(target=target)
    if quick:
        step = max(1, len(feed) // 300)
        feed = feed[::step][:300]
        ticks = min(ticks, 80)
        cool_ticks = min(cool_ticks, 40)
        W, H = 140, 100
    w = ResolveWorld(W, H, seed, feed, recs, cap=cap, p_react=p_react,
                     force_r=force_r, t_end=10.0, cool_k=10.0,
                     cool_ticks=cool_ticks)
    w.ticks_total = ticks
    n0 = len(w.live_mols())
    print("world %dx%d  molecules=%d  cells=%d  thresholds=%s  "
          "ticks=%d cool_ticks=%d  T0=%.0f -> %.0fC"
          % (W, H, n0, w.n_cells_used, MASS_THRESH["mass"], ticks,
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
            "engine": "T85 方格环境：骨架占格 + 低质量阈值 + 10C恒温平台 + resolve 完全/不完全反应",
            "W": W, "H": H, "seed": seed, "ticks": ticks,
            "cool_ticks": cool_ticks, "T_end": w.t_end,
            "thresholds": {k: list(v) for k, v in MASS_THRESH.items()},
            "cap": cap, "p_react": p_react, "force_r": force_r,
            "lock_w": w.lock_w, "lock_r": w.lock_r,
            "e_cells": [w.EW, w.EH], "snap_every": snap_every,
            "quick": quick, "feed": feed_meta, "feed_file": "t62_loads.json",
            "footprint": "k = len(skeleton_units)，无三价骨架=1；目录外产物按 8.08 原子/骨架估算",
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
    print("conservation_ok=%s N0=%d N=%d complete=%d incomplete=%d none=%d "
          "decomp=%d new=%d"
          % (ok, snaps[0]["n"], snaps[-1]["n"], w.n_complete, w.n_incomplete,
             w.n_none, w.n_decomp, len(w.new_species)))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--W", type=int, default=320)
    ap.add_argument("--H", type=int, default=220)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--target", type=int, default=7000)
    ap.add_argument("--ticks", type=int, default=1200)
    ap.add_argument("--cool-ticks", type=int, default=650)
    ap.add_argument("--cap", type=int, default=26)
    ap.add_argument("--p-react", type=float, default=0.012)
    ap.add_argument("--force-r", type=int, default=2)
    ap.add_argument("--snap-every", type=int, default=200)
    ap.add_argument("--out", default="t85_env_resolve_result.json")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    run(W=a.W, H=a.H, seed=a.seed, target=a.target, ticks=a.ticks,
        cool_ticks=a.cool_ticks, cap=a.cap, p_react=a.p_react,
        force_r=a.force_r, snap_every=a.snap_every, out=a.out,
        quick=a.quick)


if __name__ == "__main__":
    main()
