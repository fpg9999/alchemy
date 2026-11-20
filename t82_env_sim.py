"""T82: 九元素环境模拟（方格世界 + 三素力 + 规则 1~11 反应）

设计
----
* 环境 = 方格环面世界，W x H 个格子，每格最多 1 个分子（点粒子）；
* 每个分子占据一个格子，但它的"骨架"会跨越若干格子（渲染时画成方块图）；
* 分子间相互作用 = 三素层（alchemy/three_su.py）：
    聚素 -> 吸引力，散素 -> 覆盖半径，动素 -> 排斥力；
    净力 w = Att - Rep；w >= 1 强粘 = 粘附锁（只锁相对位置，不成化学键）；
* 相邻（棋盘距离 1）的两个分子每拍以 p_react 概率按规则 1~11 反应：
    prods = complete_products(vec_i + vec_j)（元素计数向量决定，确定性）；
    产物替换原来的两个分子（1 个产物则合并，2 个产物则各占一格）；
* 投料 = T62 batchA（9 元素各约 1/9、三/二/一价各约 1/3）缩放；
* 输出 = 快照（每个分子的格子坐标 + 分子式）+ 统计 + 元素守恒校验，
         供 t82_render.py 画"环境切片"。

只读内核，不修改 alchemy/ 包内代码。
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

ELEMS = list(ELEM_ORDER)          # ['O','X','C','P','W','L','K','A','F']
ELEM_SET = set(ELEMS)

BASE = os.path.dirname(os.path.abspath(__file__))
LOAD_FILE = os.path.join(BASE, "t62_loads.json")
CATALOG_FILE = os.path.join(BASE, "t4_catalog_all_validated.json")

DIRS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]


# ----------------------------------------------------------------------------
# 元素/分子式工具
# ----------------------------------------------------------------------------

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


def formula_of(comp):
    return "".join(e * comp[e] for e in ELEMS if comp.get(e))


def catalog_index():
    """formula -> rec（含 atoms/edges/place）；只读一次。"""
    cat = json.load(io.open(CATALOG_FILE, encoding="utf-8"))
    idx = {}
    for rec in cat:
        idx[rec["formula"]] = rec
    return idx


def load_feed(target=1000, path=LOAD_FILE):
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


# ----------------------------------------------------------------------------
# 世界
# ----------------------------------------------------------------------------

class World:
    def __init__(self, W, H, seed, feed, recs, cap=26, p_react=0.006,
                 force_r=3, move_p=0.7, brown_p=0.04, lock_r=2,
                 lock_w=1.0):
        self.W, self.H = W, H
        self.rng = random.Random(seed)
        self.cap = cap
        self.p_react = p_react
        self.force_r = force_r
        self.move_p = move_p
        self.brown_p = brown_p
        self.lock_r = lock_r
        self.lock_w = lock_w
        self.recs = recs                  # formula -> catalog rec
        self.catalog_set = set(recs)
        self.types = {}                   # formula -> {"comp","vec","natoms"}
        self.mols = []                    # list of dict(id,f,r,c,dead)
        self.cell = {}                    # (r,c) -> mid
        self.locks = {}                   # mid -> set(mid)
        self.next_id = 0
        self.t = 0
        self.force_cache = {}
        self.f_cache = {}
        self.n_react = 0
        self.n_react_fail = 0
        self.new_species = {}             # formula -> {"first_t","atoms"}
        self.n_moves = 0
        self.n_blocked = 0
        self.n_brown = 0
        self._place_feed(feed)

    # -- types ---------------------------------------------------------
    def ensure_type(self, formula):
        if formula in self.types:
            return self.types[formula]
        comp = comp_of(formula)
        t = {"comp": comp, "vec": vec_of(comp), "natoms": natoms_of(comp)}
        self.types[formula] = t
        if formula not in self.catalog_set:
            self.new_species.setdefault(formula, {"first_t": self.t, "atoms": t["natoms"]})
        return t

    # -- placement -----------------------------------------------------
    def _place_feed(self, feed):
        cells = self.rng.sample(range(self.W * self.H), len(feed))
        for formula, idx in zip(feed, cells):
            r, c = divmod(idx, self.W)
            self.add_mol(formula, r, c)

    def add_mol(self, formula, r, c):
        mid = self.next_id
        self.next_id += 1
        self.ensure_type(formula)
        self.mols.append({"id": mid, "f": formula, "r": r, "c": c, "dead": False})
        self.cell[(r, c)] = mid
        return mid

    def _kill(self, mid):
        m = self.mols[mid]
        if m["dead"]:
            return
        m["dead"] = True
        self.cell.pop((m["r"], m["c"]), None)
        for p in self.locks.get(mid, ()):        # 解锁
            self.locks.get(p, set()).discard(mid)
        self.locks.pop(mid, None)

    def _set(self, mid, formula):
        self.mols[mid]["f"] = formula
        self.ensure_type(formula)

    # -- force ---------------------------------------------------------
    def pair_w(self, f_i, f_j, d):
        key = (f_i, f_j, d) if f_i <= f_j else (f_j, f_i, d)
        w = self.force_cache.get(key)
        if w is None:
            ci = self.types[f_i]["comp"]
            cj = self.types[f_j]["comp"]
            w = TS.pair_force(ci, cj, d)["w"]
            self.force_cache[key] = w
        return w

    def force_on(self, mid):
        m = self.mols[mid]
        r, c = m["r"], m["c"]
        sx = sy = 0.0
        fr = self.force_r
        for dr in range(-fr, fr + 1):
            for dc in range(-fr, fr + 1):
                if dr == 0 and dc == 0:
                    continue
                d = max(abs(dr), abs(dc))
                nb = self.cell.get(((r + dr) % self.H, (c + dc) % self.W))
                if nb is None or nb == mid or self.mols[nb]["dead"]:
                    continue
                w = self.pair_w(m["f"], self.mols[nb]["f"], d)
                if w == 0.0:
                    continue
                sx += w * dr / d
                sy += w * dc / d
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
        nr = (m["r"] + dr) % self.H
        nc = (m["c"] + dc) % self.W
        if (nr, nc) in self.cell:
            return False
        if not self._lock_ok(mid, nr, nc):
            self.n_blocked += 1
            return False
        self.cell.pop((m["r"], m["c"]), None)
        m["r"], m["c"] = nr, nc
        self.cell[(nr, nc)] = mid
        return True

    # -- reaction ------------------------------------------------------
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

    def _try_react(self, i, j):
        mi, mj = self.mols[i], self.mols[j]
        vi = self.types[mi["f"]]["vec"]
        vj = self.types[mj["f"]]["vec"]
        total = tuple(a + b for a, b in zip(vi, vj))
        if sum(total) > self.cap:
            self.n_react_fail += 1
            return False
        prods = self._products(total)
        if not prods:
            self.n_react_fail += 1
            return False
        if len(prods) > 2:
            self.n_react_fail += 1
            return False
        pf = [p["formula"] for p in prods]
        if len(pf) == 2 and pf[0] == mi["f"] and pf[1] == mj["f"]:
            return False
        if len(pf) == 1 and pf[0] == mi["f"] and self.types[mi["f"]]["natoms"] == sum(total):
            return False
        # apply
        self._set(i, pf[0])
        if len(pf) == 2:
            self._set(j, pf[1])
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
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                nb = self.cell.get(((r + dr) % self.H, (c + dc) % self.W))
                if nb is None or nb in handled or self.mols[nb]["dead"]:
                    continue
                if self.rng.random() >= self.p_react:
                    continue
                handled.add(i)
                handled.add(nb)
                self._try_react(i, nb)
                break

    # -- adhesion locks ------------------------------------------------
    def rebuild_locks(self):
        locks = {}
        for (r, c), mid in list(self.cell.items()):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                nb = self.cell.get(((r + dr) % self.H, (c + dc) % self.W))
                if nb is None:
                    continue
                w = self.pair_w(self.mols[mid]["f"], self.mols[nb]["f"], 1)
                if w >= self.lock_w:
                    locks.setdefault(mid, set()).add(nb)
                    locks.setdefault(nb, set()).add(mid)
        self.locks = locks

    # -- one tick ------------------------------------------------------
    def step(self):
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        for mid in ids:
            if self.mols[mid]["dead"]:
                continue
            sx, sy = self.force_on(mid)
            dr = dc = 0
            norm = math.hypot(sx, sy)
            if norm > 1e-9:
                ang = math.atan2(sy, sx)
                k = int(round(ang / (math.pi / 4.0))) % 8
                dr, dc = DIRS[k]
                p = min(1.0, 0.20 + 0.80 * norm)
            else:
                p = 0.0
            if self.rng.random() < p:
                if self._try_move(mid, dr, dc):
                    self.n_moves += 1
            elif self.rng.random() < self.brown_p:
                dr, dc = self.rng.choice(DIRS)
                if self._try_move(mid, dr, dc):
                    self.n_moves += 1
                    self.n_brown += 1
        self.react_phase()
        self.rebuild_locks()

    # -- stats ---------------------------------------------------------
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

    def clusters(self):
        """8 邻域连通分量。"""
        live = {m["id"]: m for m in self.live_mols()}
        seen = set()
        comps = []
        for mid in live:
            if mid in seen:
                continue
            stack = [mid]
            seen.add(mid)
            size = 0
            cells = []
            while stack:
                u = stack.pop()
                size += 1
                mu = self.mols[u]
                cells.append((mu["r"], mu["c"]))
                r, c = mu["r"], mu["c"]
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nb = self.cell.get(((r + dr) % self.H, (c + dc) % self.W))
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
        return {
            "t": t,
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
            "n_react": self.n_react,
            "n_react_fail": self.n_react_fail,
            "n_new_species": len(self.new_species),
        }


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------

def run(W=150, H=110, seed=20261120, target=1000, ticks=800,
        cap=26, p_react=0.006, force_r=3, snap_every=100,
        out="t82_env_result.json", quick=False):
    t0 = time.time()
    res = json.loads(json.dumps({}))  # noop
    recs = catalog_index()
    feed, feed_meta = load_feed(target=target)
    if quick:
        feed = feed[:120]
        ticks = min(ticks, 200)
        W, H = 80, 60
    w = World(W, H, seed, feed, recs, cap=cap, p_react=p_react,
              force_r=force_r)
    print("world %dx%d  N=%d  cap=%d  p_react=%g  force_r=%d  ticks=%d"
          % (W, H, len(w.live_mols()), cap, p_react, force_r, ticks))
    snaps = [w.snapshot(0)]
    el0 = w.elements()
    for t in range(1, ticks + 1):
        w.t = t
        w.step()
        if t % snap_every == 0 or t == ticks:
            snap = w.snapshot(t)
            snaps.append(snap)
            print("t=%4d N=%5d distinct=%4d react=%6d new=%4d max_cl=%3d  "
                  "elapsed=%.1fs"
                  % (t, snap["n"], snap["n_distinct"], snap["n_react"],
                     snap["n_new_species"], snap["clusters"]["max"],
                     time.time() - t0))
    el1 = w.elements()
    ok = el0 == el1
    comp = w.composition()
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
    result = {
        "config": {
            "engine": "T82 方格环境：三素力 + 规则1~11 反应 + 粘附锁",
            "W": W, "H": H, "seed": seed, "ticks": ticks, "cap": cap,
            "p_react": p_react, "force_r": force_r,
            "lock_w": w.lock_w, "lock_r": w.lock_r,
            "snap_every": snap_every, "quick": quick,
            "feed": feed_meta, "feed_file": "t62_loads.json",
            "runtime_s": round(time.time() - t0, 2),
        },
        "summary": {
            "n0": snaps[0]["n"], "n_final": snaps[-1]["n"],
            "n_react": w.n_react, "n_react_fail": w.n_react_fail,
            "n_new_species": len(w.new_species),
            "n_moves": w.n_moves, "n_blocked": w.n_blocked,
            "n_brown": w.n_brown,
            "elements0": el0, "elements1": el1, "conservation_ok": ok,
            "clusters": snaps[-1]["clusters"],
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
    print("saved %s  (%.1fs)" % (out, time.time() - t0))
    print("conservation_ok =", ok, " N0=%d N=%d react=%d new=%d"
          % (snaps[0]["n"], snaps[-1]["n"], w.n_react, len(w.new_species)))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--W", type=int, default=150)
    ap.add_argument("--H", type=int, default=110)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--ticks", type=int, default=800)
    ap.add_argument("--cap", type=int, default=26)
    ap.add_argument("--p-react", type=float, default=0.008)
    ap.add_argument("--snap-every", type=int, default=100)
    ap.add_argument("--out", default="t82_env_result.json")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    run(W=a.W, H=a.H, seed=a.seed, target=a.target, ticks=a.ticks,
        cap=a.cap, p_react=a.p_react, snap_every=a.snap_every,
        out=a.out, quick=a.quick)


if __name__ == "__main__":
    main()
