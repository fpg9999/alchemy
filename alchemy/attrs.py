# -*- coding: utf-8 -*-
"""物质的三个轴：质量 / 物态 / 温度，各自对应一套游戏系统。

## 规则（2026-11-19 定稿）

三条轴分别由三个价数层的元素特征值**累加后取平均**得到，再按阈值分三档：

| 轴 | 价数层 | 属性 | 权重（每个原子） | 三档 | 决定的游戏系统 |
|---|---|---|---|---|---|
| **概念族** | 3 价 秩O / 沌K / 势P | **质量** | O 3 / K 2 / P 1 | 轻 / 中 / 重 | **重力行为**（上升/悬浮/下沉） |
| **物质族** | 2 价 晶X / 流W / 气A | **物态** | X 3 / W 2 / A 1 | 固 / 液 / 气 | **碰撞判定**（阻挡/游泳/穿过） |
| **能量族** | 1 价 焰F / 电L / 冰C | **温度** | F 3 / L 2 / C 1 | 冷 / 温 / 热 | **恒素富集**（稀薄/中性/富集） |

**取值**：``属性 = Σ(该层元素数 × 权重) / 该层原子数``，范围 [0, 3]。

**缺失层不需要特判**：该层不存在时分子为 0，**0 必然落在最低档**
（质量=轻、物态=气、温度=冷）——这正好符合语义：
没有骨架就最轻、没有桥就没有内聚所以是气、没有能量元素就是绝对零度。

## 三条轴为什么这样定（历史结论）

| 曾用方案 | 为什么被否 |
|---|---|
| **硬度** | 只对固体有意义，"硬度 × 液体"那一栏只能生搬硬套 |
| **密度 + 粘性** | 两者都是"凝聚程度"的投影（r(粘性,物态) = −0.77），会重复计同一件事 |
| **熵 / 物态 / 温度** | 只是把密度/粘性做了归一化，物理内核没变 |
| **活性** | 与恒素机制冲突：**反应只由恒素浓度 ρ_E 判定** |
| **导电性** | 与 电L 的权能冲突 |

**判据**：一条轴必须 (a) 对应一套独立的游戏系统，(b) 在三种物态下都有明确交互差异。
质量 / 物态 / 温度是唯一同时满足这两条的一组。

## 27 格实测（全目录抽样 6000）

- 覆盖 **27 / 27**，每格 **2.7% ~ 4.5%**（162~273 个成员）
- 三对相关：r(质量,物态) = +0.034、r(质量,温度) = −0.002、r(物态,温度) = +0.016
- 阈值：质量 (1.67, 2.30)、物态 (1.70, 2.22)、温度 (1.50, 2.00)

## 用法

    >>> import alchemy.attrs as A
    >>> d = A.attrs_of("OXC")
    >>> d["mass"], d["state"], d["temperature"]
    (3.0, 3.0, 1.0)
    >>> p = A.property_of(d)
    >>> p["cell"]
    '重·固·冷'
    >>> p["behavior"]["gravity"]
    '下沉'
"""

from __future__ import annotations

from collections import Counter

from .core.elements import DIV, MONO, TRI

__all__ = [
    "MASS_W", "STATE_W", "TEMP_W", "THRESHOLDS", "GRADES", "TIER_NAMES",
    "CALIBRATION", "AXIS_NAMES", "N_CELLS",
    "molecule_attrs", "attrs_of", "skeleton_units",
    "grade", "tier_name", "cell_of", "property_of", "behavior", "grid",
    "buoyancy", "COLLISION", "GRAVITY", "E_SOURCE",
]

#: 质量权重：三价层（骨架主干）。秩 O 最重 > 沌 K > 势 P。
MASS_W: dict[str, float] = {"O": 3.0, "K": 2.0, "P": 1.0}

#: 物态权重：二价层（桥）。晶 X 最凝聚(固) > 流 W > 气 A。
STATE_W: dict[str, float] = {"X": 3.0, "W": 2.0, "A": 1.0}

#: 温度权重：一价层（端帽）。焰 F 最热 > 电 L > 冰 C（0 = 绝对零度）。
TEMP_W: dict[str, float] = {"F": 3.0, "L": 2.0, "C": 1.0}

GRADES = ("低", "中", "高")

#: 三轴：键 / 中文名 / 价数层
AXIS_NAMES: tuple[tuple[str, str, str], ...] = (
    ("mass", "质量", "三价"),
    ("state", "物态", "二价"),
    ("temperature", "温度", "一价"),
)

#: 每条轴的三个档位名（语义名，直接用于类名）
TIER_NAMES: dict[str, tuple[str, str, str]] = {
    "mass": ("轻", "中", "重"),
    "state": ("气", "液", "固"),
    "temperature": ("冷", "温", "热"),
}

#: 27 格
N_CELLS = 3 ** 3

#: 档位阈值（在**按层平均**后的 [0,3] 标度上）
THRESHOLDS: dict[str, tuple[float, float]] = {
    "mass": (1.67, 2.30),
    "state": (1.70, 2.22),
    "temperature": (1.50, 2.00),
}

#: 定标记录（2026-11-19，全目录 6000 抽样，按层平均）
CALIBRATION: dict = {
    "scope": "molecule-per-layer-average",
    "samples": 6000,
    "shares": {
        "mass@(1.67,2.30)": (0.355, 0.340, 0.305),
        "state@(1.70,2.22)": (0.332, 0.358, 0.310),
        "temperature@(1.50,2.00)": (0.331, 0.345, 0.324),
    },
    "cell_range": (0.027, 0.045),
    "correlations": {"mass,state": 0.034, "mass,temp": -0.002, "state,temp": 0.016},
}

#: 碰撞判定（物态）
COLLISION: dict[str, str] = {
    "固": "完全阻挡，可站立，需破坏",
    "液": "可进入，游泳/减速，有浮力",
    "气": "完全穿过，无阻力",
}

#: 重力行为（质量）
GRAVITY: dict[str, str] = {
    "轻": "上升（浮力 > 重力）",
    "中": "悬浮/随介质",
    "重": "下沉（重力 > 浮力）",
}

#: 恒素富集（温度）
E_SOURCE: dict[str, str] = {
    "冷": "稀薄恒素，周围反应冻结",
    "温": "中性",
    "热": "富集恒素，周围反应活跃",
}


# ---------------------------------------------------------------- 分子级属性
def molecule_attrs(atoms, edges=None) -> dict:
    """整个分子的 质量 / 物态 / 温度（**按层平均**，范围 0~3）。"""
    atoms = list(atoms)
    out = {"natoms": len(atoms)}
    contrib = {}
    for key, W in (("mass", MASS_W), ("state", STATE_W), ("temperature", TEMP_W)):
        sub = Counter(a for a in atoms if a in W)
        n = sum(sub.values())
        total = sum(W[e] * c for e, c in sub.items())
        out[key] = round(total / n, 4) if n else 0.0
        contrib[key] = dict(sub)
    out["contrib"] = contrib
    return out


def attrs_of(formula_or_atoms, edges=None, catalog=None) -> dict:
    """对分子式计算三轴属性，附带骨架分解（供外观层使用）。"""
    if isinstance(formula_or_atoms, str):
        formula = formula_or_atoms
        if catalog is None:
            from .core.catalog import get_catalog
            catalog = get_catalog()
        rec = catalog.get(formula)
        if rec is None:
            return {"formula": formula, "error": "not_in_catalog", "skeletons": [],
                    "mass": 0.0, "state": 0.0, "temperature": 0.0, "contrib": {}}
        atoms = list(rec["atoms"])
        edges = [tuple(e) for e in rec["edges"]]
    else:
        atoms = list(formula_or_atoms)
        edges = [tuple(e) for e in (edges or [])]
        from .core.elements import formula_of
        formula = formula_of(atoms)

    out = {"formula": formula}
    out.update(molecule_attrs(atoms, edges))
    out["skeletons"] = skeleton_units(atoms, edges)
    out["n_skeletons"] = len(out["skeletons"])
    return out


# ---------------------------------------------------------------- 骨架分解（外观层）
def skeleton_units(atoms, edges) -> list[dict]:
    """把分子拆成骨架单元，供**外观**层使用（不参与属性计算）。

    骨架 = 三价原子的连通块；**跨两个骨架的二价桥同时属于这两个骨架**。
    """
    atoms = list(atoms)
    edges = [tuple(e) for e in edges]
    n = len(atoms)
    adj: list[list[int]] = [[] for _ in range(n)]
    for (a, b, _m) in edges:
        adj[a].append(b)
        adj[b].append(a)

    tri_idx = [i for i in range(n) if atoms[i] in TRI]
    comp_of: dict[int, int] = {}
    comps: list[list[int]] = []
    for s in tri_idx:
        if s in comp_of:
            continue
        cid = len(comps)
        comp_of[s] = cid
        stack, mem = [s], [s]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if atoms[v] in TRI and v not in comp_of:
                    comp_of[v] = cid
                    stack.append(v)
                    mem.append(v)
        comps.append(sorted(mem))
    if not comps:
        return []

    touch: dict[int, set[int]] = {}
    for i in range(n):
        if atoms[i] in TRI:
            continue
        seen = {i}
        stack = [i]
        reached: set[int] = set()
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v in seen:
                    continue
                if atoms[v] in TRI:
                    reached.add(comp_of[v])
                    continue
                seen.add(v)
                stack.append(v)
        touch[i] = reached

    units = []
    for cid, mem in enumerate(comps):
        members = list(mem)
        bridges = []
        for i, reached in touch.items():
            if cid in reached:
                members.append(i)
                if len(reached) >= 2:
                    bridges.append(i)
        members = sorted(set(members))
        units.append({
            "members": members,
            "atoms": [atoms[i] for i in members],
            "size": len(mem),
            "bridge_members": sorted(bridges),
        })
    return units


# ---------------------------------------------------------------- 阈值分档与 27 格
def grade(value: float, attr: str, thresholds=None) -> str:
    """把一个值切成 低 / 中 / 高（用于编号）。"""
    lo, hi = (thresholds or THRESHOLDS)[attr]
    if value <= lo:
        return GRADES[0]
    if value <= hi:
        return GRADES[1]
    return GRADES[2]


def tier_name(value: float, attr: str, thresholds=None) -> str:
    """把一个值切成该轴的语义档名（轻/中/重、气/液/固、冷/温/热）。"""
    return TIER_NAMES[attr][GRADES.index(grade(value, attr, thresholds))]


def cell_of(mass: float, state: float, temperature: float,
            thresholds=None) -> str:
    """三档组合成 27 格之一，如 ``重·固·冷``。"""
    return "·".join((
        tier_name(mass, "mass", thresholds),
        tier_name(state, "state", thresholds),
        tier_name(temperature, "temperature", thresholds),
    ))


def behavior(mass_tier: str, state_tier: str, temp_tier: str) -> dict:
    """由三档名给出游戏行为（碰撞 / 重力 / 恒素）。"""
    return {
        "collision": COLLISION[state_tier],
        "gravity": GRAVITY[mass_tier],
        "e_field": E_SOURCE[temp_tier],
    }


def property_of(attrs: dict, thresholds=None) -> dict:
    """由三轴数值得出 27 格之一，含游戏行为。"""
    m, s, t = attrs["mass"], attrs["state"], attrs["temperature"]
    gm = grade(m, "mass", thresholds)
    gs = grade(s, "state", thresholds)
    gt = grade(t, "temperature", thresholds)
    cell = "·".join((TIER_NAMES["mass"][GRADES.index(gm)],
                     TIER_NAMES["state"][GRADES.index(gs)],
                     TIER_NAMES["temperature"][GRADES.index(gt)]))
    return {
        "mass": m, "state": s, "temperature": t,
        "grades": {"mass": gm, "state": gs, "temperature": gt},
        "cell": cell,
        "index": GRADES.index(gm) * 9 + GRADES.index(gs) * 3 + GRADES.index(gt),
        "behavior": behavior(TIER_NAMES["mass"][GRADES.index(gm)],
                             TIER_NAMES["state"][GRADES.index(gs)],
                             TIER_NAMES["temperature"][GRADES.index(gt)]),
    }


def grid() -> list[dict]:
    """枚举全部 27 格（编号 / 类名 / 三档 / 行为）。"""
    out = []
    for i, m in enumerate(TIER_NAMES["mass"]):
        for j, s in enumerate(TIER_NAMES["state"]):
            for k, t in enumerate(TIER_NAMES["temperature"]):
                out.append({
                    "index": i * 9 + j * 3 + k,
                    "cell": f"{m}·{s}·{t}",
                    "mass": m, "state": s, "temperature": t,
                    "behavior": behavior(m, s, t),
                })
    return out


# ---------------------------------------------------------------- 浮力
def buoyancy(object_mass: float, medium_mass: float, volume: float = 1.0) -> dict:
    """浮力：``F = (介质质量 − 物体质量) × 体积``。

    注：上升/下沉永远是**相对介质**而言。同一块轻固体在重气体里上浮，
    在轻气体里照样下沉。
    """
    weight = object_mass * volume
    lift = medium_mass * volume
    net = lift - weight
    return {
        "weight": round(weight, 3),
        "buoyancy": round(lift, 3),
        "net": round(net, 3),
        "motion": "上升" if net > 0 else ("下沉" if net < 0 else "悬浮"),
        "can_carry": round(max(0.0, net), 3),   # 可托起的最大重量
    }
