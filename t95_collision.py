# -*- coding: utf-8 -*-
"""T95 碰撞/推挤引擎：在 T94 试验场上实现 P1（单格链推挤）与 P2（团簇速度/动量）。

设计见 docs/T95_COLLISION_DESIGN.md；参数全部来自 t95_config.params()。

与 T94 的差异（只做动力学，不改化学/环境/放置）：
  * 每分子新增 vx, vy（格/拍）、px, py（累积位移，>1 格才真正移动）；
  * 重写 _try_move：目标被占时按「质量 + 受力 + 动量」判定是否推挤；
    整条链先检查后统一提交，任何一格非法即整链回滚 → 元素/占格守恒；
  * 重写 _gravity_step：多格团簇被下方阻挡时按推挤规则处理下落；
  * step：速度积分替代 T87 的「每拍按力方向随机走/不走」；
  * 无布朗（布朗已由总工程删除；本文件也不含任何随机游走）。
阶段：
  stage=0  基线 v0：完全沿用 T94.LifeWorld.step（仅用于 A/B 对照）
  stage=1  P1：单格分子可推链；多格团簇只做自由移动，不参与推挤
  stage=2  P2：锁连通分量作为刚体参与移动/推挤（不做锁断裂）

实现口径（报告中“实现差异”一节会写清）：
  * M_eff = max(0.05, mass)：mass=0 的分子（如 W2）仍有惯性下限，避免除零；
  * 受力→速度：dv = (F / M_eff) * F2V，F2V 是实现标定常数（非用户参数）；
  * 重力仍沿用 T94 的 gacc 累积位移（便于与 v0 同口径对照），速度场只承载
    三素力驱动的水平运动与碰撞动量；
  * 一维冲量严格按设计稿 §2.6（恢复系数 e、沿 n 的标量速度）；
  * J_A = M_A·max(0, v_A·n) + max(0, F_A·n)·dt（重力推挤时再加 M_A·grav）；
  * J_B = M_B·max(0, -v_B·n) + J_stick(B) + J_floor(B)。
"""

import math

import t83_env_axes as T83
import t87_env_asym as T87
import t94_life as T94
from t95_config import params

# 实现标定：三素力 → 速度增量。不是设计稿里的用户参数（params() 不接受它）。
F2V = 0.02          # (格/拍) / (力/质量)，每拍
M_EPS = 0.05        # 有效质量下限（mass=0 分子的惰性下限）
CLUSTER_V_EPS = 0.02
FLOOR_MARGIN = 0.0
# T87 的物态迁移率（与 v0 的随机移动同口径）
STATE_MOB = T83.STATE_MOB


def _eff_mass(mass):
    return max(M_EPS, float(mass))


class PushWorld(T94.LifeWorld):
    """T94 世界的推挤动力学版本。"""

    def __init__(self, *a, stage=1, outer_membrane=None, outer_n=0,
                 outer_ring=(12.6, 15.6), push_params=None, **kw):
        self.stage = int(stage)
        if self.stage not in (0, 1, 2):
            raise ValueError("stage must be 0/1/2")
        self.P = params(**(push_params or {}))
        self.outer_membrane = outer_membrane
        self.outer_n = int(outer_n) if outer_membrane else 0
        self.outer_ring = tuple(outer_ring)
        self.env_min = (self.outer_ring[1] + 1.5) if outer_membrane else T94.R_ENV_MIN
        # P2 缓存
        self._clusters = []
        self._cluster_of = {}
        self._cluster_mass = {}
        self._cluster_vel = {}
        # 统计
        self.n_push = 0
        self.n_push_fail = 0
        self.n_grav_push = 0
        self.n_cluster_moves = 0
        self.chain_hist = {}
        self.body_cells0 = None
        super().__init__(*a, **kw)
        for m in self.mols:
            m.setdefault("vx", 0.0)
            m.setdefault("vy", 0.0)
            m.setdefault("px", 0.0)
            m.setdefault("py", 0.0)
        self.body_cells0 = {i: tuple(self.mols[i]["cells"])
                            for i in self.body_set}

    # -------------------------------------------------------------- 放置
    def _place_all(self):
        """与 T94 相同，多一个外膜环（双层臂）。"""
        self._place_body()
        self._place_ring(self.food_formula, self.food_n, T94.FOOD_RING, "food")
        if self.membrane:
            self._place_ring(self.membrane, self.n_mem, T94.MEM_RING, "membrane")
        if self.outer_membrane:
            self._place_ring(self.outer_membrane, self.outer_n,
                             self.outer_ring, "membrane")
        self._place_env()
        self.env_lineage = set(self.env_ids)
        self.food_lineage = set(self.food_ids)
        self.body_set = set(self.body_ids)

    def _place_env(self):
        """与 T94 相同，但环境最小半径按外膜外缘自适应。"""
        placed = 0
        for f in self.env_feed:
            if placed >= len(self.env_feed):
                break
            done = False
            for _ in range(40):
                r = self.rng.randrange(self.H)
                c = self.rng.randrange(self.W)
                d = math.hypot(r - self.center[0], c - self.center[1])
                if d < self.env_min:
                    continue
                cells = self._free_footprint(r, c, f)
                if not cells:
                    continue
                if self._place_cells(f, cells, "env") is not None:
                    placed += 1
                    done = True
                    break
            if not done:
                continue
        self._env_placed = placed

    # -------------------------------------------------------------- 角色
    def _membrane_mols(self):
        if not self.membrane_ids:
            return []
        return [m for m in self._live() if m["id"] in self.membrane_ids]

    def _tick_contacts(self):
        body_cells = set()
        mem_cells = set()
        for mid, m in enumerate(self.mols):
            if m["dead"]:
                continue
            if mid in self.body_set:
                for (r, c) in m["cells"]:
                    body_cells.add((r, c))
            elif mid in self.membrane_ids:
                for (r, c) in m["cells"]:
                    mem_cells.add((r, c))
        for mid in self.env_lineage:
            if mid >= len(self.mols):
                continue
            m = self.mols[mid]
            if m["dead"]:
                continue
            for (r, c) in m["cells"]:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        if (r + dr, c + dc) in body_cells:
                            self.c_contacts_env_body += 1
                        if (r + dr, c + dc) in mem_cells:
                            self.c_contacts_env_mem += 1

    def final_state(self):
        live = self._live()
        return {
            "mols": [[m["r"], m["c"], m["f"],
                      ("body" if m["id"] in self.body_set else
                       "membrane" if m["id"] in self.membrane_ids else
                       "food" if m["id"] in self.food_lineage else
                       "env" if m["id"] in self.env_lineage else "other")]
                     for m in live],
            "center": list(self.center),
            "W": self.W, "H": self.H,
        }

    # -------------------------------------------------------------- 刚体
    def _rebuild_clusters(self):
        live = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        parent = {i: i for i in live}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i in live:
            for j in self.locks.get(i, ()):
                if j not in parent or j == i:
                    continue
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb
        groups = {}
        for i in live:
            groups.setdefault(find(i), []).append(i)
        self._clusters = list(groups.values())
        self._cluster_of = {}
        self._cluster_mass = {}
        self._cluster_vel = {}
        for gi, g in enumerate(self._clusters):
            M = 0.0
            vx = vy = 0.0
            for i in g:
                mm = _eff_mass(self.types[self.mols[i]["f"]]["mass"])
                M += mm
                vx += mm * self.mols[i].get("vx", 0.0)
                vy += mm * self.mols[i].get("vy", 0.0)
                self._cluster_of[i] = gi
            if M > 1e-12:
                vx /= M
                vy /= M
            else:
                vx = sum(self.mols[i].get("vx", 0.0) for i in g) / len(g)
                vy = sum(self.mols[i].get("vy", 0.0) for i in g) / len(g)
            self._cluster_mass[gi] = M
            self._cluster_vel[gi] = (vx, vy)

    def _unit(self, mid):
        if self.stage >= 2:
            gi = self._cluster_of.get(mid)
            if gi is not None:
                return list(self._clusters[gi])
        return [mid]

    # -------------------------------------------------------------- 提交
    def _commit_shift(self, ids, dr, dc):
        """整链统一提交；调用方已保证目标格全空/合法。"""
        for mid in ids:
            for (r, c) in self.mols[mid]["cells"]:
                if self.cell.get((r, c)) == mid:
                    del self.cell[(r, c)]
        for mid in ids:
            m = self.mols[mid]
            newc = [(r + dr, c + dc) for (r, c) in m["cells"]]
            m["cells"] = newc
            m["r"], m["c"] = newc[0]
            for cell in newc:
                if cell in self.cell:
                    raise AssertionError("T95 commit collision at %r" % (cell,))
                self.cell[cell] = mid
        for mid in ids:
            m = self.mols[mid]
            m["px"] = m.get("px", 0.0) - dc
            m["py"] = m.get("py", 0.0) - dr

    # -------------------------------------------------------------- 推挤
    def _unit_stats(self, ids, dr, dc, gravity):
        nx, ny = float(dc), float(dr)
        nrm = math.hypot(nx, ny)
        nx /= nrm
        ny /= nrm
        M = 0.0
        vx = vy = 0.0
        for i in ids:
            m = self.mols[i]
            mm = _eff_mass(self.types[m["f"]]["mass"])
            M += mm
            vx += mm * m.get("vx", 0.0)
            vy += mm * m.get("vy", 0.0)
        if M > 1e-12:
            vx /= M
            vy /= M
        fx = fy = 0.0
        for i in ids:
            sx, sy = self.force_on(i)
            fx += sx
            fy += sy
        u = vx * nx + vy * ny
        f_n = fx * nx + fy * ny
        return M, vx, vy, u, f_n, nx, ny

    def _j_stick(self, ids, chain_ids):
        """B 与锁邻居（链外）的净吸引力之和。"""
        s = 0.0
        seen = set()
        for i in ids:
            fi = self.mols[i]["f"]
            for p in self.locks.get(i, ()):
                if p in chain_ids or p == i or p >= len(self.mols):
                    continue
                pm = self.mols[p]
                if pm["dead"]:
                    continue
                key = (min(i, p), max(i, p))
                if key in seen:
                    continue
                seen.add(key)
                d = max(abs(pm["r"] - self.mols[i]["r"]),
                        abs(pm["c"] - self.mols[i]["c"]))
                w = self.pair_w(fi, pm["f"], max(1, d))
                if w > 0:
                    s += w
        return s

    def _j_floor(self, ids, chain_ids):
        """静摩擦：任一格下方是地面或被非链分子支撑。"""
        M = sum(_eff_mass(self.types[self.mols[i]["f"]]["mass"]) for i in ids)
        supported = False
        for i in ids:
            for (r, c) in self.mols[i]["cells"]:
                if r + 1 >= self.H:
                    supported = True
                    break
                o = self.cell.get((r + 1, c))
                if o is not None and o not in chain_ids:
                    supported = True
                    break
            if supported:
                break
        if not supported:
            return 0.0
        return self.P["mu"] * M * self.grav

    def _locks_ok_after(self, ids, dr, dc):
        """链整体平移 1 格后，链上分子与链外锁伙伴的距离仍需 ≤ lock_r。"""
        idset = set(ids)
        for i in ids:
            m = self.mols[i]
            nr, nc = m["r"] + dr, m["c"] + dc
            for p in self.locks.get(i, ()):
                if p in idset or p >= len(self.mols):
                    continue
                pm = self.mols[p]
                if pm["dead"]:
                    continue
                if max(abs(pm["r"] - nr), abs(pm["c"] - nc)) > self.lock_r:
                    return False
        return True

    def _try_push_chain(self, mid, dr, dc, gravity=False):
        """尝试把 mid 及其前方受阻的链整体推 1 格；成功返回 True。

        先整链构造并检查（边界/碰撞/粘附/动量），全部通过才统一提交。
        任何一格非法 → 返回 False（整链未动，天然回滚）。
        """
        P = self.P
        # P1：只有单格分子能推动/被推入链
        if self.stage == 1:
            if len(self.mols[mid]["cells"]) > 1:
                self.n_push_fail += 1
                return False
        chain = []
        chain_ids = set()
        cur = self._unit(mid)
        # 起推单元本身也要计入 Kmax：stage2 的 mover 可能是整个锁团簇，
        # 若它已超过 Kmax 个分子，就直接拒绝（否则 chain_hist 会出现
        # 远超 Kmax 的链长，违反「同拍最多 Kmax 个分子参与链」的设计）。
        if len(cur) > int(P["Kmax"]):
            self.n_push_fail += 1
            return False
        while True:
            if self.stage == 1:
                for i in cur:
                    if len(self.mols[i]["cells"]) > 1:
                        self.n_push_fail += 1
                        return False
            for i in cur:
                for (r, c) in self.mols[i]["cells"]:
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < self.H and 0 <= cc < self.W):
                        self.n_push_fail += 1
                        return False
            chain.append(list(cur))
            chain_ids.update(cur)
            blockers = set()
            for i in cur:
                for (r, c) in self.mols[i]["cells"]:
                    o = self.cell.get((r + dr, c + dc))
                    if o is not None and o not in chain_ids:
                        blockers.add(o)
            if not blockers:
                break
            units = set()
            for o in blockers:
                if self.stage >= 2 and o in self._cluster_of:
                    units.add(("c", self._cluster_of[o]))
                else:
                    units.add(("m", o))
            if len(units) > 1:
                self.n_push_fail += 1
                return False
            kind, nxt = units.pop()
            next_ids = list(self._clusters[nxt]) if kind == "c" else [nxt]
            if len(chain_ids) + len(next_ids) > int(P["Kmax"]):
                self.n_push_fail += 1
                return False
            cur = next_ids
        if any(i in self.body_set for i in chain_ids):
            self.n_push_fail += 1
            return False
        total_mols = len(chain_ids)
        # 统一占格检查（防止链内新格与链外分子冲突/重复）
        occ = {}
        for ids in chain:
            for i in ids:
                for (r, c) in self.mols[i]["cells"]:
                    cell = (r + dr, c + dc)
                    if cell in occ:
                        self.n_push_fail += 1
                        return False
                    occ[cell] = i
        for cell in occ:
            o = self.cell.get(cell)
            if o is not None and o not in chain_ids:
                self.n_push_fail += 1
                return False
        if not self._locks_ok_after(chain_ids, dr, dc):
            self.n_push_fail += 1
            return False
        # 逐对动量判据 + 一维冲量
        stats = [self._unit_stats(ids, dr, dc, gravity) for ids in chain]
        chain_list = list(chain_ids)
        for k in range(len(chain) - 1):
            MA, vxA, vyA, uA, fA, nx, ny = stats[k]
            MB, vxB, vyB, uB, fB, _, _ = stats[k + 1]
            JA = MA * max(0.0, uA) + max(0.0, fA) * P["dt"]
            if gravity:
                JA += MA * self.grav
            jb = MB * max(0.0, -uB) + self._j_stick(chain[k + 1], chain_ids)
            jb += self._j_floor(chain[k + 1], chain_ids)
            if MA < P["M_min_ratio"] * MB or JA <= jb:
                self.n_push_fail += 1
                return False
            e = float(P["e"])
            uA2 = (MA * uA + MB * uB - MB * e * (uA - uB)) / (MA + MB)
            uB2 = (MA * uA + MB * uB + MA * e * (uA - uB)) / (MA + MB)
            vmax = float(P["Vmax"])
            for i in chain[k]:
                m = self.mols[i]
                vx2 = m.get("vx", 0.0) + (uA2 - uA) * nx
                vy2 = m.get("vy", 0.0) + (uA2 - uA) * ny
                if math.hypot(vx2, vy2) > vmax:
                    sc = vmax / math.hypot(vx2, vy2)
                    vx2, vy2 = vx2 * sc, vy2 * sc
                m["vx"], m["vy"] = vx2, vy2
            for i in chain[k + 1]:
                m = self.mols[i]
                vx2 = m.get("vx", 0.0) + (uB2 - uB) * nx
                vy2 = m.get("vy", 0.0) + (uB2 - uB) * ny
                if math.hypot(vx2, vy2) > vmax:
                    sc = vmax / math.hypot(vx2, vy2)
                    vx2, vy2 = vx2 * sc, vy2 * sc
                m["vx"], m["vy"] = vx2, vy2
            stats[k + 1] = (MB, vxB + (uB2 - uB) * nx, vyB + (uB2 - uB) * ny,
                            uB2, fB, nx, ny)
        # 统一提交
        self._commit_shift(chain_list, dr, dc)
        self.n_push += 1
        self.chain_hist[total_mols] = self.chain_hist.get(total_mols, 0) + 1
        if gravity:
            self.n_grav_push += 1
        return True

    # -------------------------------------------------------------- 移动
    def _try_move(self, mid, dr, dc):
        if dr == 0 and dc == 0:
            return False
        m = self.mols[mid]
        nr, nc = m["r"] + dr, m["c"] + dc
        if not (0 <= nr < self.H and 0 <= nc < self.W):
            self.n_blocked += 1
            return False
        newc = [(r + dr, c + dc) for (r, c) in m["cells"]]
        if any(not (0 <= r < self.H and 0 <= c < self.W) for r, c in newc):
            self.n_blocked += 1
            return False
        blocked = False
        for (r, c) in newc:
            o = self.cell.get((r, c))
            if o is not None and o != mid:
                blocked = True
                break
        if not blocked:
            if not self._lock_ok(mid, nr, nc):
                self.n_blocked += 1
                return False
            self._commit_shift([mid], dr, dc)
            return True
        if self.stage == 0:
            self.n_blocked += 1
            return False
        return self._try_push_chain(mid, dr, dc, gravity=False)

    def _gravity_step(self, mid):
        m = self.mols[mid]
        if self.stage == 0:
            return T94.LifeWorld._gravity_step(self, mid)
        newc = [(r + 1, c) for (r, c) in m["cells"]]
        if any(r >= self.H for r, c in newc):
            return False
        blocked = False
        for (r, c) in newc:
            o = self.cell.get((r, c))
            if o is not None and o != mid:
                blocked = True
                break
        if not blocked:
            self._commit_shift([mid], 1, 0)
            return True
        if self.stage == 1 and len(m["cells"]) > 1:
            return False
        return self._try_push_chain(mid, 1, 0, gravity=True)

    # -------------------------------------------------------------- 速度
    def _integrate(self, mid):
        m = self.mols[mid]
        step = 0
        while m.get("px", 0.0) >= 1.0 and step < int(self.P["Vmax"]):
            if self._try_move(mid, 0, 1):
                self.n_moves += 1
            else:
                m["px"] = 0.0
                break
            step += 1
        while m.get("px", 0.0) <= -1.0 and step < int(self.P["Vmax"]):
            if self._try_move(mid, 0, -1):
                self.n_moves += 1
            else:
                m["px"] = 0.0
                break
            step += 1
        step = 0
        while m.get("py", 0.0) >= 1.0 and step < int(self.P["Vmax"]):
            if self._try_move(mid, 1, 0):
                self.n_moves += 1
            else:
                m["py"] = 0.0
                break
            step += 1
        while m.get("py", 0.0) <= -1.0 and step < int(self.P["Vmax"]):
            if self._try_move(mid, -1, 0):
                self.n_moves += 1
            else:
                m["py"] = 0.0
                break
            step += 1

    def _velocity_update(self, mid):
        m = self.mols[mid]
        t = self.types[m["f"]]
        M = _eff_mass(t["mass"])
        sx, sy = self.force_on(mid)
        g = 1.0 - float(self.P["gamma"])
        vx = g * m.get("vx", 0.0) + (sx / M) * F2V
        vy = g * m.get("vy", 0.0) + (sy / M) * F2V
        nrm = math.hypot(vx, vy)
        vmax = float(self.P["Vmax"])
        if nrm > vmax and nrm > 1e-12:
            vx *= vmax / nrm
            vy *= vmax / nrm
        m["vx"], m["vy"] = vx, vy

    # -------------------------------------------------------------- 团簇
    def _cluster_pass(self):
        """P2：锁连通分量按质心速度整体移动（1 格/次）。"""
        self._rebuild_clusters()
        for g in self._clusters:
            if len(g) < 2:
                continue
            if any(i in self.body_set for i in g):
                continue
            n_before = len(self._live())
            n_cluster_moves = self.n_cluster_moves
            gi = self._cluster_of[g[0]]
            M = self._cluster_mass[gi]
            if M > 1e-9:
                fsx = fsy = 0.0
                for i in g:
                    fx, fy = self.force_on(i)
                    fsx += fx
                    fsy += fy
                gd = 1.0 - float(self.P["gamma"])
                vmax = float(self.P["Vmax"])
                for i in g:
                    mm = self.mols[i]
                    vx2 = gd * mm.get("vx", 0.0) + (fsx / M) * F2V
                    vy2 = gd * mm.get("vy", 0.0) + (fsy / M) * F2V
                    n2 = math.hypot(vx2, vy2)
                    if n2 > vmax and n2 > 1e-12:
                        vx2 *= vmax / n2
                        vy2 *= vmax / n2
                    mm["vx"], mm["vy"] = vx2, vy2
                vx = sum(self.mols[i].get("vx", 0.0) for i in g) / len(g)
                vy = sum(self.mols[i].get("vy", 0.0) for i in g) / len(g)
                self._cluster_vel[gi] = (vx, vy)
            vx, vy = self._cluster_vel[gi]
            if math.hypot(vx, vy) < CLUSTER_V_EPS:
                continue
            for i in g:
                m = self.mols[i]
                m["px"] = m.get("px", 0.0) + vx
                m["py"] = m.get("py", 0.0) + vy
            px = sum(self.mols[i].get("px", 0.0) for i in g) / len(g)
            py = sum(self.mols[i].get("py", 0.0) for i in g) / len(g)
            dr = 0
            dc = 0
            if abs(px) >= 1.0 and abs(px) >= abs(py):
                dc = 1 if px > 0 else -1
            elif abs(py) >= 1.0:
                dr = 1 if py > 0 else -1
            if dr == 0 and dc == 0:
                continue
            ok = True
            for i in g:
                for (r, c) in self.mols[i]["cells"]:
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < self.H and 0 <= cc < self.W):
                        ok = False
                        break
                    o = self.cell.get((rr, cc))
                    if o is not None and o not in g:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                for i in g:
                    self.mols[i]["px"] = 0.0
                    self.mols[i]["py"] = 0.0
                continue
            if not self._locks_ok_after(g, dr, dc):
                for i in g:
                    self.mols[i]["px"] = 0.0
                    self.mols[i]["py"] = 0.0
                continue
            self._commit_shift(g, dr, dc)
            self.n_cluster_moves += 1
            if self.n_moves is not None:
                pass
            assert len(self._live()) == n_before

    # -------------------------------------------------------------- 一拍
    def step(self):
        """v1/v2 的拍：与 v0 同口径的「三素力驱动随机尝试」，区别只在
        blocked 时走链式推挤；v2 额外在拍首做团簇动量整体位移。"""
        if self.stage == 0:
            return T94.LifeWorld.step(self)
        self.Tamb = self.ambient_T(self.t)
        self.update_rho()
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        # 1) P2：团簇动量 + 整体位移（每拍首）
        if self.stage >= 2:
            self._cluster_pass()
        # 2) 逐分子：重力 + 三素力驱动的随机移动（与 v0 完全同口径）
        for mid in ids:
            m = self.mols[mid]
            if m["dead"] or mid in self.body_set:
                continue
            t = self.types[m["f"]]
            gacc = m.get("gacc", 0.0) + self.grav * t["mass"]
            gsteps = int(gacc)
            m["gacc"] = gacc - gsteps
            for _ in range(min(gsteps, T94.GRAVITY_MAX_STEPS)):
                if not self._gravity_step(mid):
                    break
            sx, sy = self.force_on(mid)
            norm = math.hypot(sx, sy)
            if norm <= 1e-9:
                continue
            k = int(round(math.atan2(sy, sx) / (math.pi / 4.0))) % 8
            dr, dc = T83.DIRS[k]
            st = int(t["tiers"]["state"])
            p = STATE_MOB[st] * min(1.0, 0.20 + 0.80 * norm)
            if self.rng.random() < p:
                self._try_move(mid, dr, dc)
        self._tick_contacts()
        self.react_phase()
        self.rebuild_locks()

    # -------------------------------------------------------------- 度量
    def measure(self, t, every=10):
        rec = T94.LifeWorld.measure(self, t, every)
        live = self._live()
        movers = [m for m in live if m["id"] not in self.body_set]
        speeds = [math.hypot(m.get("vx", 0.0), m.get("vy", 0.0))
                  for m in movers]
        body = [m for m in live if m["id"] in self.body_set]
        mem = [m for m in live if m["id"] in self.membrane_ids]
        rec["mean_abs_v"] = round(sum(speeds) / len(speeds), 4) if speeds else 0.0
        rec["max_abs_v"] = round(max(speeds), 4) if speeds else 0.0
        rec["n_push_cum"] = self.n_push
        rec["n_push_fail_cum"] = self.n_push_fail
        rec["n_grav_push_cum"] = self.n_grav_push
        rec["n_cluster_moves_cum"] = self.n_cluster_moves
        rec["chain_hist"] = dict(self.chain_hist)
        rec["body_cy"] = round(sum(m["r"] for m in body) / len(body), 2) if body else None
        rec["mem_cy"] = round(sum(m["r"] for m in mem) / len(mem), 2) if mem else None
        rec["membrane_inner_n"] = sum(
            1 for m in mem if self.membrane and m["f"] == self.membrane)
        rec["membrane_outer_n"] = len(mem) - rec["membrane_inner_n"]
        rec["vmax"] = float(self.P["Vmax"])
        return rec
