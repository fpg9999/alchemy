# -*- coding: utf-8 -*-
"""网格分子动力学实验：把 T62B 群系的分子铺到网格上，用聚/散/动推出的力模型演化。

规则
----
- 每个分子占据一个单位格；
- 每个分子的四个值由聚/散/动的元素特征值之和算出（参数与设计稿一致）；
- 分子对之间的力：``A_ij = A_i·A_j/A_max``、``R_ij = R_i·R_j/R_max``，
  范围取两者较大值，力**不随距离衰减**；
- 每个 tick 按净力方向尝试移动一格（目标格为空才移动）；
- 阻尼由所处介质决定，本实验取统一阻尼。

用法
----
    python examples/lattice_sim.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import alchemy  # noqa: E402
from alchemy.core.elements import ORDER, VAL, parse_formula  # noqa: E402

# ---------------------------------------------------------------- 参数（设计稿定稿值）
K = 8.0
A_MAX, R_MAX = 10.0, 10.0
R0, R1 = 1.5, 4.5
FORCE_SCALE = 0.2      # 全局力强度缩放（标定：终端速度≈作用半径的12%）
CROSS_K = 0.0          # 反对称交叉项强度（>0 时力成为真正的配对函数）          # 作用半径下限 / 上限（格子单位）
W_S, W_OWN = 0.4, 0.3      # 半径权重：散素 0.4，自身强度 0.3

GRID = 64
FILL = 0.40
TICKS = 300
SEED = 20261120


def four_values(formula: str) -> tuple[float, float, float, float]:
    """Σ 特征值 → (引力, 斥力, 引力距离, 斥力距离)。"""
    v = parse_formula(formula)
    g = {e: v[ORDER.index(e)] for e in ORDER}
    sp = sum(VAL[e] * g[e] for e in ("O", "X", "C"))
    sm = sum(VAL[e] * g[e] for e in ("P", "W", "L"))
    ss = sum(VAL[e] * g[e] for e in ("K", "A", "F"))
    a = sp / (sp + K)
    m = sm / (sm + K)
    s = ss / (ss + K)
    # ---- 幂次校准 + 温和缩放：让四种组合的分布接近均匀，同时保持力的量级
    att = min(A_MAX, 10.8 * (a ** 2.5)) * FORCE_SCALE
    rep = min(R_MAX, 10.8 * (m ** 3.0)) * FORCE_SCALE
    # 半径**强对比**：散素把"作用距离预算"分给引力，
    # 剩下的（1−散）加上动素分给斥力。于是两者差距明显。
    d_att = R0 + (R1 - R0) * s
    d_rep = R0 + (R1 - R0) * (0.8 * (1.0 - s) + 0.2 * m)
    return att, rep, d_att, d_rep


class Mol:
    __slots__ = ("formula", "att", "rep", "d_att", "d_rep", "x", "y",
                 "mass_val", "state_val", "mass_tier", "coll_tier",
                 "state_simple", "weight", "w_eff", "temp_val", "e_load", "e_rep", "swap_cool", "vx", "vy")

    def __init__(self, formula: str, x: int, y: int):
        self.formula = formula
        self.att, self.rep, self.d_att, self.d_rep = four_values(formula)
        self.x, self.y = x, y
        self.vx = 0.0
        self.vy = 0.0
        # ---- 径向三轴（质量 / 碰撞性）：权重取自 attrs，与设计稿一致
        from alchemy.attrs import MASS_W, STATE_W, THRESHOLDS
        v = parse_formula(formula)
        g = {e: v[ORDER.index(e)] for e in ORDER}
        n3 = sum(g[e] for e in ("O", "K", "P"))
        n2 = sum(g[e] for e in ("X", "A", "W"))
        self.mass_val = (sum(MASS_W[e] * g[e] for e in ("O", "K", "P")) / n3) if n3 else 0.0
        self.state_val = (sum(STATE_W[e] * g[e] for e in ("X", "A", "W")) / n2) if n2 else 0.0
        lo_m, hi_m = THRESHOLDS["mass"]
        lo_s, hi_s = THRESHOLDS["state"]
        self.mass_tier = "轻" if self.mass_val <= lo_m else ("中" if self.mass_val <= hi_m else "重")
        self.coll_tier = "虚体" if self.state_val <= lo_s else ("软体" if self.state_val <= hi_s else "刚体")
        # 暂用固/液/气 的简易标签（仅用于分层权重）
        self.state_simple = "气" if self.state_val <= lo_s else ("液" if self.state_val <= hi_s else "固")
        # **分层权重 = 物态基底 + 连续质量**：固体恒重于液体、液体恒重于气体
        self.weight = STATE_BASE[self.state_simple] + self.mass_val
        self.w_eff = self.weight
        # 温度（一价层平均）与恒素携带量（由恒素场写入）
        n1 = sum(g[e] for e in ("F", "L", "C"))
        self.temp_val = (sum({"F": 3, "L": 2, "C": 1}[e] * g[e]
                             for e in ("F", "L", "C")) / n1) if n1 else 0.0
        self.e_load = 0.0
        self.e_rep = 0.0
        self.swap_cool = 0


#: 质量档 → 重力方向（轻上升 / 中悬浮 / 重下沉）
GRAV_SIGN = {"轻": -1.0, "中": 0.0, "重": 1.0}

#: 碰撞档 → 被穿过的概率（刚体挡死 / 软体偶可穿 / 虚体随便穿）
PASS_PROB = {"刚体": 0.0, "软体": 0.25, "虚体": 1.0}

#: 分层权重里的物态基底：固体恒重于液体，液体恒重于气体
STATE_BASE = {"气": 0.0, "液": 4.0, "固": 8.0}
W_MAX = 11.0            # 8 + 质量上限 3

# ---- 默认规则（2026-11-20 起）：重力常开、力随距离衰减、非对称
DEFAULT_GRAVITY = 1.0
DEFAULT_RADIAL = True
DEFAULT_DECAY = True
DEFAULT_ASYM = True

#: 是否启用"主导力来源"过滤（交换伙伴即主导力来源时不换）
DOM_SOURCE_CHECK = True


def load_composition(limit: int) -> list[str]:
    """读 T62B（t62_phaseA）的物种组成，返回按丰度展开的分子式列表。"""
    path = Path("data/biomes/t62_phaseA.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    species = [s for s in data["species"] if s.get("in_catalog")]
    species.sort(key=lambda s: -s["count"])
    total = sum(s["count"] for s in species)
    out: list[str] = []
    for s in species:
        n = max(1, round(limit * s["count"] / total))
        out.extend([s["formula"]] * n)
    return out[:limit]


def neighbours(cx: int, cy: int, radius: int):
    r = radius
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if dx or dy:
                yield cx + dx, cy + dy


def build(n_mol: int, rng: random.Random) -> tuple[dict, list[Mol]]:
    comp = load_composition(n_mol)
    cells = [(x, y) for x in range(GRID) for y in range(GRID)]
    rng.shuffle(cells)
    chosen = cells[: len(comp)]
    mols = [Mol(f, x, y) for f, (x, y) in zip(comp, chosen)]
    grid = {(m.x, m.y): m for m in mols}
    return grid, mols


#: 按物态上色（快照用）
STATE_COLOR = {
    "固": (140, 95, 60),      # 棕
    "液": (70, 130, 200),     # 蓝
    "气": (200, 215, 230),    # 浅灰蓝
}



def potential(dn: float, att: float, rep: float, beta: float = 0.3) -> float:
    """与 :func:`force_shape` 一致的势能（U(1)=0，力 = -dU/d(dn)）。"""
    if dn >= 1.0:
        return 0.0
    if dn < 0.0:
        dn = 0.0
    a = (1.0 + beta) / 2.0
    if dn >= a:
        integ = att * (1.0 - dn) ** 2 / (1.0 - beta)
    elif dn >= beta:
        integ = att / (1.0 - beta) * (
            (a * a - dn * dn) - 2.0 * beta * (a - dn) + (1.0 - a) ** 2)
    else:
        integ_rep = -rep * ((beta - dn) - (beta * beta - dn * dn) / (2.0 * beta))
        integ_att = att / (1.0 - beta) * (
            (a * a - beta * beta) - 2.0 * beta * (a - beta) + (1.0 - a) ** 2)
        integ = integ_rep + integ_att
    return -integ


def local_energy(m: Mol, grid: dict, beta: float = 0.3) -> float:
    """分子与周围所有分子的势能之和。"""
    e = 0.0
    rmax = max(m.d_att, m.d_rep)
    r = int(math.ceil(rmax))
    for cx, cy in neighbours(m.x, m.y, r):
        o = grid.get((cx, cy))
        if o is None:
            continue
        d = math.hypot(cx - m.x, cy - m.y)
        if d == 0:
            continue
        Dij = max(m.d_att, o.d_att)
        if d > Dij:
            continue
        # 非对称：吸引用自己、排斥用对方
        e += potential(d / Dij, m.att, o.rep, beta)
    return e


def swap_cells(grid: dict, a: tuple[int, int], b: tuple[int, int]) -> None:
    """交换两个格子里的分子。"""
    ma, mb = grid[a], grid[b]
    grid[a], grid[b] = mb, ma
    ma.x, ma.y = b
    mb.x, mb.y = a



def pair_force(m: Mol, o: Mol, decay: bool = True, asym: bool = True,
               beta: float = 0.3) -> float:
    """m 受到 o 的力（正=吸引，负=排斥，0=无作用）。

    非对称：吸引用**自己**的 A 与半径，排斥用**对方**的 R 与半径。
    """
    d = math.hypot(o.x - m.x, o.y - m.y)
    if d == 0:
        return 0.0
    if asym:
        att, rep = m.att, o.rep
        r_att, r_rep = m.d_att, o.d_rep
    else:
        att, rep = m.att * o.att / A_MAX, m.rep * o.rep / R_MAX
        r_att, r_rep = max(m.d_att, o.d_att), max(m.d_rep, o.d_rep)
    r_cross = max(r_att, m.d_rep, o.d_att)
    if d > max(r_att, r_rep, r_cross):
        return 0.0
    if not decay:
        base = (att if d <= r_att else 0.0) - (rep if d <= r_rep else 0.0)
        cross = 0.0
        if CROSS_K > 0 and d <= r_cross:
            cross = CROSS_K * (m.att * o.rep - o.att * m.rep) / (A_MAX * R_MAX)
    else:
        base = force_shape(d, att, rep, r_att, r_rep)
        cross = 0.0
        if CROSS_K > 0 and r_cross > 0:
            cross = (CROSS_K * (m.att * o.rep - o.att * m.rep)
                     / (A_MAX * R_MAX)) * max(0.0, 1.0 - d / r_cross)
    return base + cross


def dominant_source(m: Mol, grid: dict, decay: bool = True,
                    asym: bool = True) -> "Mol | None":
    """对 m 施加最大单对力（绝对值）的邻居。"""
    best, best_mag = None, -1.0
    rmax = max(m.d_att, m.d_rep)
    r = int(math.ceil(rmax))
    for cx, cy in neighbours(m.x, m.y, r):
        o = grid.get((cx, cy))
        if o is None:
            continue
        f = abs(pair_force(m, o, decay, asym))
        if f > best_mag:
            best_mag, best = f, o
    return best


def force_shape(d: float, att: float, rep: float,
                r_att: float, r_rep: float) -> float:
    """净力 = 引力 − 斥力，两项**各自线性衰减**到自己的半径。

    - 引力项：``att × max(0, 1 − d/r_att)``
    - 斥力项：``rep × max(0, 1 − d/r_rep)``

    两个半径独立，所以四种组合都会自然出现：
    引力更强 / 斥力更强 / 引力更远 / 斥力更远。
    """
    f = 0.0
    if r_att > 0.0:
        f += att * max(0.0, 1.0 - d / r_att)
    if r_rep > 0.0:
        f -= rep * max(0.0, 1.0 - d / r_rep)
    return f


def push_chain(grid: dict, start: tuple[int, int], dx: int, dy: int,
               maxlen: int = 4) -> bool:
    """把 ``start`` 处的分子沿 (dx,dy) 推进一格，必要时**推开沿途更轻的分子**。

    这就是"重物把下方的轻物压下去"：只要对方比推动者轻就能挤开，
    遇到比自己重的就推不动。返回是否成功。
    """
    mover = grid.get(start)
    if mover is None:
        return False
    seq = []                       # 沿途要后移的分子，从近到远
    x, y = start
    for _ in range(maxlen):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < GRID and 0 <= ny < GRID):
            return False
        occ = grid.get((nx, ny))
        if occ is None:            # 找到空位 → 整条链后移一格
            for m in seq:
                del grid[(m.x, m.y)]
            del grid[start]
            for m in reversed(seq):
                m.x += dx
                m.y += dy
            mover.x, mover.y = start[0] + dx, start[1] + dy
            for m in seq:
                grid[(m.x, m.y)] = m
            grid[(mover.x, mover.y)] = mover
            return True
        if occ.w_eff >= mover.w_eff:   # 比自己重就推不动
            return False
        seq.append(occ)
        x, y = nx, ny
    return False
    """Particle Life 式的力形状（``dn`` = d / D，归一化距离）。

    - ``dn < beta``：**斥力**，从 ``−rep`` 线性回到 0
    - ``beta ≤ dn < 1``：**引力**，三角峰，在 ``(1+beta)/2`` 达到 ``+att``
    - ``dn ≥ 1``：0

    正值 = 吸引，负值 = 排斥。
    """
    if dn >= 1.0:
        return 0.0
    if dn < beta:
        return -rep * (dn / beta - 1.0)
    return att * (1.0 - abs(2.0 * dn - 1.0 - beta) / (1.0 - beta))


def net_force(m: Mol, grid: dict, gravity: float = 0.0, decay: bool = False,
              asym: bool = False, beta: float = 0.3) -> tuple[float, float]:
    """净力：范围内所有分子求和 + 恒定重力（+y 向下）。

    - ``decay=True``：力随距离衰减（:func:`force_shape`）；否则范围内恒力。
    - ``asym=True``：**非对称**——引力用``自己``的聚素、斥力用``对方``的动素。
    """
    fx = fy = 0.0
    rmax = max(m.d_att, m.d_rep)
    r = int(math.ceil(rmax))
    for cx, cy in neighbours(m.x, m.y, r):
        o = grid.get((cx, cy))
        if o is None:
            continue
        dx, dy = cx - m.x, cy - m.y
        d = math.hypot(dx, dy)
        if d == 0:
            continue
        if asym:
            att, rep = m.att, o.rep
            r_att, r_rep = m.d_att, o.d_rep
        else:
            att, rep = m.att * o.att / A_MAX, m.rep * o.rep / R_MAX
            r_att, r_rep = max(m.d_att, o.d_att), max(m.d_rep, o.d_rep)
        r_cross = max(r_att, r_rep)
        if d > max(r_att, r_rep):
            continue
        ux, uy = dx / d, dy / d
        f = force_shape(d, att, rep, r_att, r_rep) if decay else (
            (att if d <= r_att else 0.0) - (rep if d <= r_rep else 0.0))
        if CROSS_K > 0 and r_cross > 0:
            cross = (CROSS_K * (m.att * o.rep - o.att * m.rep)
                     / (A_MAX * R_MAX)) * (max(0.0, 1.0 - d / r_cross) if decay else 1.0)
            f += cross
        fx += f * ux
        fy += f * uy
    fy += gravity
    return fx, fy


def column_pressure(mols: list[Mol]) -> dict:
    """按列累积重力（水压原理）。

    返 ``{id(mol): 该分子承担的总重量}``：从列顶往下累加，
    最下方的分子承担其上方**所有**分子的重量。
    """
    cols: dict[int, list[Mol]] = {}
    for m in mols:
        cols.setdefault(m.x, []).append(m)
    out = {}
    for x, col in cols.items():
        col.sort(key=lambda m: m.y)          # 上 → 下
        cum = 0.0
        for m in col:
            cum += m.w_eff
            out[id(m)] = cum
    return out


def step(grid: dict, mols: list[Mol], rng: random.Random, threshold: float = 0.05,
         gravity: float | None = None, use_radial: bool | None = None,
         decay: bool | None = None, asym: bool | None = None,
         inertia: bool = False, dt: float = 0.05, damp: float = 0.8,
         max_step: int = 3, pressure: bool = True, settle_priority: bool = True,
         flatten: bool = True, no_self_rise: bool = True,
         stats: dict | None = None, settle_ratio: float = 0.0,
         weight_by: str = "mass", strict_order: bool = False,
         force_threshold: float = 0.0, energy_rule: bool = False,
         swap_cooldown: int = 3,
         flatten_mode: str = "balance"):
    """推进一个 tick。

    ``use_radial=True`` 时接入**质量轴**：重力方向由质量档决定
    （轻上升 / 中悬浮 / 重下沉）。

    ``inertia=True`` 时给分子加**速度**（格子上的惯性）：速度按力累积并衰减，
    每 tick 可沿速度方向移动 0~``max_step`` 格。这是能否出现持续运动的**关键开关**。

    注意：**分子之间永远不穿透**——只能移入空格。刚体/软体/虚体这套碰撞规则
    只对玩家生效，不影响分子之间的运动。
    """
    order = list(range(len(mols)))
    rng.shuffle(order)
    moved = 0
    if gravity is None:
        gravity = DEFAULT_GRAVITY
    if use_radial is None:
        use_radial = DEFAULT_RADIAL
    if decay is None:
        decay = DEFAULT_DECAY
    if asym is None:
        asym = DEFAULT_ASYM
    # 冷却递减
    for m in mols:
        if getattr(m, "swap_cool", 0) > 0:
            m.swap_cool -= 1
    # 沉降权重：state_mass = 物态基底 + 质量；mass = 只看质量
    for m in mols:
        m.w_eff = m.mass_val if weight_by == "mass" else m.weight
    # 按列累积的重量（重力叠加：下方分子承担上方全部重量）
    cumw = column_pressure(mols) if pressure else {id(m): m.weight for m in mols}
    for i in order:
        m = mols[i]
        if use_radial:
            eff_g = gravity * (cumw[id(m)] / W_MAX)
        else:
            eff_g = gravity
        # 分子间力（不含重力）；用于判断是否被"化学结合"
        px, py = net_force(m, grid, 0.0, decay=decay, asym=asym)
        chem_bound = math.hypot(px, py) > settle_ratio * abs(eff_g) if settle_ratio > 0 else False
        # 沉降优先：正下方是空位或更轻的分子时强制下沉；
        # 沉不下去时，**非固体且非零质量**的分子向左右铺平（模拟压强）。
        acted = False
        cause = None
        if settle_priority and m.w_eff > 0 and not chem_bound:
            below = (m.x, m.y + 1)
            if 0 <= below[1] < GRID:
                occ_b = grid.get(below)
                if occ_b is None:
                    del grid[(m.x, m.y)]
                    m.x, m.y = below
                    grid[below] = m
                    moved += 1
                    acted = True
                    cause = "settle"
                elif occ_b.w_eff < m.w_eff:
                    if push_chain(grid, (m.x, m.y), 0, 1):
                        moved += 1
                        acted = True
                        cause = "settle"
                    else:
                        swap_cells(grid, (m.x, m.y), below)
                        moved += 1
                        acted = True
                        cause = "settle"
            speed_now = math.hypot(m.vx, m.vy)
            if not acted and flatten and speed_now < 0.15:
                for dx in rng.sample([-1, 1], 2):
                    side = (m.x + dx, m.y)
                    if not (0 <= side[0] < GRID):
                        continue
                    # 沙堆式平衡：只有当侧列"下方比自己少"时才侧移，
                    # 平衡后不再移动（否则表面会永不停歇地侧滑）
                    if flatten_mode == "balance":
                        mine = sum(1 for yy in range(m.y + 1, GRID)
                                   if (m.x, yy) in grid)
                        theirs = sum(1 for yy in range(m.y + 1, GRID)
                                     if (side[0], yy) in grid)
                        if theirs >= mine:
                            continue
                    occ_s = grid.get(side)
                    if occ_s is None:
                        del grid[(m.x, m.y)]
                        m.x, m.y = side
                        grid[side] = m
                        moved += 1
                        acted = True
                        cause = "flatten"
                        break
                    if occ_s.w_eff < m.w_eff:
                        swap_cells(grid, (m.x, m.y), side)
                        moved += 1
                        acted = True
                        cause = "flatten"
                        break
        if acted:
            if stats is not None:
                stats[cause] = stats.get(cause, 0) + 1
            continue
        fx, fy = px, py + (eff_g if use_radial else 0.0)
        mag = math.hypot(fx, fy)
        if inertia:
            m.vx = (m.vx + fx * dt) * damp
            m.vy = (m.vy + fy * dt) * damp
            speed = math.hypot(m.vx, m.vy)
            if speed < threshold:
                continue
            steps = min(max_step, max(1, int(speed * 3.0)))
            ux, uy = m.vx / speed, m.vy / speed
        else:
            if mag < threshold:
                continue
            steps = 1
            ux, uy = fx / mag, fy / mag
        # 沿速度/力方向逐格推进：**受阻时沿障碍滑行**（网格惯性）
        for _ in range(steps):
            cands = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = m.x + dx, m.y + dy
                    if not (0 <= nx < GRID and 0 <= ny < GRID):
                        continue
                    occ_c = grid.get((nx, ny))
                    if occ_c is None:
                        # 空格：有重量的分子不允许自己往上走
                        if no_self_rise and use_radial and m.w_eff > 0 and dy < 0:
                            continue
                    score = (dx * ux + dy * uy) / math.hypot(dx, dy)
                    cands.append((score, dx, dy, occ_c))
            cands.sort(key=lambda c: -c[0])
            acted = False
            for score, dx, dy, occ_c in cands:
                if score < 0.15:
                    break
                best = (m.x + dx, m.y + dy)
                if occ_c is None:
                    del grid[(m.x, m.y)]
                    m.x, m.y = best
                    grid[best] = m
                    moved += 1
                    acted = True
                    break
                # 同种分子互换没有物理意义（不可区分）→ 禁止
                if occ_c.formula == m.formula:
                    continue
                # 占位：只能"保序"交换
                if not (dy == 0 or (dy > 0 and m.w_eff >= occ_c.w_eff)
                        or (dy < 0 and m.w_eff <= occ_c.w_eff)):
                    continue
                if abs(math.hypot(fx, fy)) < force_threshold:
                    continue
                # **主导力源判据（唯一过滤）**：
                #   交换伙伴不能是主导力源；且交换方向必须朝主导源（吸引）或背离它（排斥）
                if DOM_SOURCE_CHECK:
                    ds = dominant_source(m, grid, decay=decay, asym=asym)
                    if ds is None or ds is occ_c:
                        continue
                    f_ds = pair_force(m, ds, decay=decay, asym=asym)
                    if f_ds == 0:
                        continue
                    sxn, syn = ds.x - m.x, ds.y - m.y
                    sn = math.hypot(sxn, syn) or 1.0
                    tn = math.hypot(dx, dy) or 1.0
                    dot = (dx * sxn + dy * syn) / (sn * tn)
                    # 吸引 → 朝它走；排斥 → 背离它
                    if (f_ds > 0 and dot < 0.5) or (f_ds < 0 and dot > -0.5):
                        continue
                swap_cells(grid, (m.x, m.y), best)
                moved += 1
                acted = True
                if stats is not None:
                    stats["force"] = stats.get("force", 0) + 1
                break
            if not acted:
                break
    return moved


def metrics(mols: list[Mol], grid: dict) -> dict:
    """聚集度、相分离度、组分半径。"""
    same = 0
    diff = 0
    for m in mols:
        for cx, cy in neighbours(m.x, m.y, 1):
            o = grid.get((cx, cy))
            if o is None:
                continue
            if o.formula == m.formula:
                same += 1
            else:
                diff += 1
    total_pairs = (same + diff) / 2 or 1

    # 接触概率：同类接触 / 期望同类接触
    from collections import Counter
    cnt = Counter(m.formula for m in mols)
    n = len(mols)
    exp_same = sum((c / n) ** 2 for c in cnt.values())
    obs_same = same / (same + diff) if (same + diff) else 0
    seg = obs_same / exp_same if exp_same else 0.0

    # 各组分半径（围绕质心）
    radii = {}
    for f in cnt:
        pts = [(m.x, m.y) for m in mols if m.formula == f]
        if not pts:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        radii[f] = math.sqrt(sum((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in pts) / len(pts))
    return {"same_neighbors": same / max(1, len(mols)),
            "segregation": seg,
            "radii": radii,
            "pairs": int(total_pairs)}


def render(mols: list[Mol], path: str, scale: int = 8, by_state: bool = True):
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    img = Image.new("RGB", (GRID * scale, GRID * scale), (250, 250, 250))
    d = ImageDraw.Draw(img)
    palette = {}
    cols = [(70, 185, 91), (245, 166, 35), (63, 208, 201), (142, 90, 168),
            (59, 111, 212), (240, 122, 200), (231, 76, 60), (179, 179, 179), (245, 224, 75)]
    for m in mols:
        if by_state:
            c = STATE_COLOR.get(getattr(m, "state_simple", "气"), (128, 128, 128))
        else:
            if m.formula not in palette:
                palette[m.formula] = cols[len(palette) % len(cols)]
            c = palette[m.formula]
        d.rectangle([m.x * scale, m.y * scale, m.x * scale + scale - 1,
                     m.y * scale + scale - 1], fill=c)
    img.save(path)


def main():
    rng = random.Random(SEED)
    n_mol = int(GRID * GRID * FILL)
    grid, mols = build(n_mol, rng)
    print(f"网格 {GRID}×{GRID}，分子 {len(mols)} 个（填充率 {FILL:.0%}）")
    print(f"组分: " + ", ".join(f"{k}×{v}" for k, v in
                              sorted({m.formula: sum(1 for x in mols if x.formula == m.formula)
                                      for m in mols}.items(), key=lambda kv: -kv[1])[:6]))

    m0 = metrics(mols, grid)
    print(f"\n{'tick':>5}{'同种邻居':>10}{'分离度':>9}{'LF半径':>9}{'OXCPWKA半径':>13}{'移动数':>8}")
    print(f"{0:5}{m0['same_neighbors']:10.2f}{m0['segregation']:9.2f}"
          f"{m0['radii'].get('LF', 0):9.2f}{m0['radii'].get('OXCPWKA', 0):13.2f}{'-':>8}")
    render(mols, "images/lattice_t0.png")

    for t in range(1, TICKS + 1):
        moved = step(grid, mols, rng)
        if t % 50 == 0:
            mm = metrics(mols, grid)
            print(f"{t:5}{mm['same_neighbors']:10.2f}{mm['segregation']:9.2f}"
                  f"{mm['radii'].get('LF', 0):9.2f}{mm['radii'].get('OXCPWKA', 0):13.2f}{moved:8}")

    render(mols, "images/lattice_t300.png")
    print("\n图: images/lattice_t0.png / images/lattice_t300.png")


if __name__ == "__main__":
    main()
