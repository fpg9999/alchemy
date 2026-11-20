"""T86 九元素环境：质量阈值回到默认 + 投料偏向三价元素 + 多分子同时反应。

相对 T85 的三处改动（用户 m03027 / m03045）：
1) 质量阈值回到内核默认 (1.67, 2.30)（T85 曾实验内降到 (1.20,1.85)）。
2) 投料改为"三价元素富集"：用 IPF 把 batchA 120 个物种的计数重配平，
   目标元素占比 O/X/F 各 18%（默认各 1/9=11.1%），其余 6 元素各 7.67%。
   总分子数仍 7,000。
3) 反应支持"多分子同时反应"（最多 4 个相邻分子一组，按组成模式倍率与
   恒素门控决定是否触发），cap 26 -> 36；仍用 natural_engine.resolve
   判定 complete/incomplete/none，多产物（>=3）允许。

环境/温度曲线沿用 T85：1000°C 指数冷却到 10°C，650 拍后恒温到 1200 拍。
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time

import natural_engine as E
import t83_env_axes as T83
import t85_env_resolve as T85
from t83_env_axes import (
    comp_of, vec_of, natoms_of, catalog_index, load_feed, MODE_MULT,
)

# 1) 质量阈值回到默认
T85.MASS_THRESH["mass"] = (1.67, 2.30)

# 2) 三价元素富集目标
TRI_ELS = ("O", "X", "F")
OTH_ELS = ("K", "A", "C", "P", "W", "L")
TRI_SHARE = 0.18            # O/X/F 各 18%
OTH_SHARE = (1.0 - 3 * TRI_SHARE) / 6.0   # 其余各 7.667%
TARGET = {e: TRI_SHARE for e in TRI_ELS}
TARGET.update({e: OTH_SHARE for e in OTH_ELS})

VALENCE = {"O": 3, "X": 3, "F": 3, "K": 2, "W": 2, "L": 2,
           "P": 1, "A": 1, "C": 1}


def load_feed_tri(target=7000, path=T83.LOAD_FILE, iters=400):
    """IPF 重配平 batchA 物种计数，使元素占比逼近 TARGET。"""
    d = json.load(io.open(path, encoding="utf-8"))
    rows = d["batchA"]["rows"]
    formulas = [r["formula"] for r in rows]
    base = [float(r["count"]) for r in rows]
    comps = [comp_of(f) for f in formulas]
    nats = [float(sum(c.values())) for c in comps]
    els = list(T83.ELEMS)

    c = base[:]
    total0 = sum(c)
    c = [x * target / total0 for x in c]

    def totals(cs):
        out = {e: 0.0 for e in els}
        for ci, comp in zip(cs, comps):
            for e, n in comp.items():
                out[e] += ci * n
        return out

    for _ in range(iters):
        cur = totals(c)
        tot = sum(cur.values())
        factors = {}
        for e in els:
            want = TARGET[e] * tot
            factors[e] = (want / cur[e]) if cur[e] > 1e-12 else 1.0
        newc = []
        for ci, comp, ni in zip(c, comps, nats):
            mult = 1.0
            for e, n in comp.items():
                mult *= factors[e] ** (n / ni)
            newc.append(ci * mult)
        tot_new = sum(newc)
        if tot_new <= 0:
            break
        c = [x * target / tot_new for x in newc]

    # 取整：最大余数法
    ints = [int(math.floor(x)) for x in c]
    rem = target - sum(ints)
    order = sorted(range(len(c)), key=lambda i: -(c[i] - ints[i]))
    for i in order[:max(0, rem)]:
        ints[i] += 1
    for i, x in enumerate(c):
        if x >= 0.5 and ints[i] == 0:
            ints[i] = 1
    # 若超出目标，从最大的物种里扣
    while sum(ints) > target:
        i = max(range(len(ints)), key=lambda k: ints[k])
        ints[i] -= 1
    feed = []
    for f, n in zip(formulas, ints):
        if n > 0:
            feed.extend([f] * n)

    cur = totals([float(n) for n in ints])
    tot = sum(cur.values())
    share = {e: cur[e] / tot for e in els}
    val = {1: 0.0, 2: 0.0, 3: 0.0}
    for e in els:
        val[VALENCE[e]] += share[e]
    meta = {"target": target, "batch_total": len(feed),
            "n_molecules": len(feed), "atoms": int(round(tot)),
            "share": {e: round(v, 4) for e, v in share.items()},
            "valence_share": {str(k): round(v, 4) for k, v in val.items()},
            "tri_target": TRI_SHARE, "ipf_iters": iters,
            "n_species": sum(1 for n in ints if n > 0),
            "feed_file": "t62_loads.json (IPF 重配平)"}
    return feed, meta


class TriWorld(T85.ResolveWorld):
    """在 T85 世界之上：多分子（2~4）同时反应。"""

    max_group = 4

    def _adj_mids(self, mid):
        out = set()
        for (r, c) in self.mols[mid]["cells"]:
            for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nb = self.cell.get((r + dr, c + dc))
                if nb is not None and nb != mid:
                    out.add(nb)
        return out

    def _mode_key(self, si, sj):
        if si == sj == 0:
            return "气-气"
        if si == sj == 1:
            return "液-液"
        if si == sj == 2:
            return "固-固"
        if {si, sj} <= {0, 1}:
            return "气-液"
        return "含固"

    def react_phase(self):
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        handled = set()
        for i in ids:
            if self.mols[i]["dead"] or i in handled:
                continue
            m = self.mols[i]
            ti = self.types[m["f"]]
            rho = self.rho_at(m["r"], m["c"])
            gate = 0.15 + 0.85 * rho
            nbs = [j for j in self._adj_mids(i)
                   if not self.mols[j]["dead"] and j not in handled]
            if not nbs:
                continue
            self.rng.shuffle(nbs)
            group = [i]
            atoms = ti["natoms"]
            for j in nbs:
                tj = self.types[self.mols[j]["f"]]
                if atoms + tj["natoms"] > self.cap:
                    continue
                group.append(j)
                atoms += tj["natoms"]
                if len(group) >= self.max_group:
                    break
            if len(group) < 2:
                continue
            mults = []
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    sa = self.types[self.mols[group[a]]["f"]]["tiers"]["state"]
                    sb = self.types[self.mols[group[b]]["f"]]["tiers"]["state"]
                    mults.append(MODE_MULT.get((sa, sb),
                                               MODE_MULT.get((sb, sa), 1.0)))
            mult = 1.0
            for x in mults:
                mult *= x
            mult = mult ** (1.0 / max(1, len(mults)))
            p = self.p_react * mult * gate
            if self.rng.random() >= p:
                continue
            if self._try_react_group(group):
                handled.update(group)

    def _try_react_group(self, group):
        mds = [self._md_of(j) for j in group]
        formulas = [self.mols[j]["f"] for j in group]
        atoms = sum(self.types[f]["natoms"] for f in formulas)
        if atoms > self.cap:
            self.n_react_fail += 1
            return False
        try:
            res = E.resolve(mds, self.Tamb)
        except Exception:
            self.n_react_fail += 1
            return False
        typ = res["type"]
        prods = res.get("products")
        states = res.get("state") or []
        self.react_types[typ] = self.react_types.get(typ, 0) + 1
        if typ == "none":
            if res.get("stages"):
                new = [s for s in states
                       if s["formula"] not in formulas or len(states) > len(formulas)]
                if len(new) <= len(formulas):
                    self.n_none += 1
                    return False
                self.n_decomp += 1
                return self._apply_group(new, group, formulas)
            self.n_none += 1
            return False
        if typ == "incomplete":
            self.n_incomplete += 1
        else:
            self.n_complete += 1
        if not prods:
            self.n_react_fail += 1
            return False
        if sorted(p["formula"] for p in prods) == sorted(formulas):
            return False
        return self._apply_group(prods, group, formulas)

    def _apply_group(self, prods, group, formulas):
        cells_all = []
        for j in group:
            cells_all.extend(self.mols[j]["cells"])
        cr = sum(r for r, c in cells_all) // len(cells_all)
        cc = sum(c for r, c in cells_all) // len(cells_all)
        placed = self._spawn(prods, (cr, cc), set(group))
        if not placed:
            self.n_react_fail += 1
            return False
        # 模式统计：组内每一对
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                si = self.types[formulas[a]]["tiers"]["state"]
                sj = self.types[formulas[b]]["tiers"]["state"]
                key = self._mode_key(si, sj)
                self.mode_counts[key] = self.mode_counts.get(key, 0) + 1
        band = 0 if cr > 2 * self.H // 3 else (2 if cr < self.H // 3 else 1)
        self.band_react[band] += 1
        for j in group:
            self._kill(j)
        for md, cells in placed:
            self.md_cache[md["formula"]] = md
            self._add_with(md, cells)
        self.n_react += 1
        return True


def run(W=320, H=220, seed=20261120, target=7000, ticks=1200,
        cool_ticks=650, cap=36, p_react=0.012, force_r=2, snap_every=200,
        out="t86_env_tri_result.json", quick=False):
    t_start = time.time()
    recs = catalog_index()
    feed, feed_meta = load_feed_tri(target=target)
    if quick:
        step = max(1, len(feed) // 300)
        feed = feed[::step][:300]
        ticks = min(ticks, 80)
        cool_ticks = min(cool_ticks, 40)
        W, H = 140, 100
    w = TriWorld(W, H, seed, feed, recs, cap=cap, p_react=p_react,
                 force_r=force_r, t_end=10.0, cool_k=10.0,
                 cool_ticks=cool_ticks)
    w.ticks_total = ticks
    n0 = len(w.live_mols())
    print("world %dx%d  molecules=%d  cells=%d  thresholds=%s  "
          "cap=%d group<=%d  tri_share=%s  ticks=%d cool_ticks=%d  T0=%.0f -> %.0fC"
          % (W, H, n0, w.n_cells_used, T85.MASS_THRESH["mass"], w.cap,
             w.max_group, feed_meta["share"], ticks, cool_ticks,
             w.t0, w.t_end), flush=True)
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
            "engine": "T86 方格环境：默认质量阈值 + 三价元素富集投料 + 多分子(2~4)同时反应",
            "W": W, "H": H, "seed": seed, "ticks": ticks,
            "cool_ticks": cool_ticks, "T_end": w.t_end,
            "thresholds": {k: list(v) for k, v in T85.MASS_THRESH.items()},
            "cap": cap, "max_group": w.max_group, "p_react": p_react,
            "force_r": force_r, "lock_w": w.lock_w, "lock_r": w.lock_r,
            "e_cells": [w.EW, w.EH], "snap_every": snap_every,
            "quick": quick, "feed": feed_meta,
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
    ap.add_argument("--cap", type=int, default=36)
    ap.add_argument("--p-react", type=float, default=0.012)
    ap.add_argument("--force-r", type=int, default=2)
    ap.add_argument("--snap-every", type=int, default=200)
    ap.add_argument("--out", default="t86_env_tri_result.json")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    run(W=a.W, H=a.H, seed=a.seed, target=a.target, ticks=a.ticks,
        cool_ticks=a.cool_ticks, cap=a.cap, p_react=a.p_react,
        force_r=a.force_r, snap_every=a.snap_every, out=a.out, quick=a.quick)


if __name__ == "__main__":
    main()
