# -*- coding: utf-8 -*-
"""物质的三个数值属性：密度 / 粘性 / 温度。

## 规则（2026-11-18 第三轮修订）

三条轴各决定一个**可累加的数值属性**，每条轴按阈值分成**三相（低/中/高）**，
三者构成 **3×3×3 = 27 格**物性网格。

| 轴 | 价数层 | 属性 | 权重（每个原子） |
|---|---|---|---|
| **概念/骨架** | 3 价 秩O / 沌K / 势P | **密度** | O +3、K +2、P +1 |
| **物态/连接** | 2 价 晶X / 流W / 气A | **粘性** | X +3、W +2、A +1 |
| **能量/端帽** | 1 价 焰F / 电L / 冰C | **温度** | F +3、L +2、C +1 |

- 公式一律 `Σ 该层元素的个数 × 权重`，作用于**整个分子的全部原子**；
- 温度是**热力学式**的量：**0 = 绝对零度**（无能量元素时可达），无负值。

### 为什么 3 价轴从"硬度"改成"密度"

硬度与"固态"在概念上重合（硬 → 必然固），所以会出现"刚性液体"这种不合理物质。
密度与粘性、温度**互不重合**：水银密度大而粘性小、蜂蜜密度中而粘性大、泡沫密度小却粘。
而且密度对固/液/气**都适用**，不会像硬度那样让"没有三价元素的分子硬度恒为 0"。

## 用法

    >>> import alchemy.attrs as A
    >>> A.attrs_of("OXC")["density"]
    3.0
    >>> A.property_of(A.attrs_of("OXC"))["cell"]
    '密-低|粘-低|温-中'
"""

from __future__ import annotations

from collections import Counter

from .core.elements import DIV, MONO, TRI

__all__ = [
    "DENS_W", "STICK_W", "TEMP_W", "THRESHOLDS", "GRADES", "CALIBRATION",
    "AXIS_NAMES", "molecule_attrs", "attrs_of", "skeleton_units",
    "grade", "property_of", "grid", "cell_of", "N_CELLS",
]

#: 密度权重：三价层（骨架主干）。秩 O 最致密 > 沌 K > 势 P。
DENS_W: dict[str, float] = {"O": 3.0, "K": 2.0, "P": 1.0}

#: 粘性权重：二价层（桥）。晶 X 3 > 流 W 2 > 气 A 1。
STICK_W: dict[str, float] = {"X": 3.0, "W": 2.0, "A": 1.0}

#: 温度权重：一价层（端帽）。焰 F 3 > 电 L 2 > 冰 C 1（纯热值，0 = 绝对零度）。
TEMP_W: dict[str, float] = {"F": 3.0, "L": 2.0, "C": 1.0}

GRADES = ("低", "中", "高")

#: 三轴：键 / 中文名 / 属性名 / 权重表
AXIS_NAMES: tuple[tuple[str, str, str], ...] = (
    ("density", "密度", "三价"),
    ("stickiness", "粘性", "二价"),
    ("temperature", "温度", "一价"),
)

#: 每条轴分三档，共 3³ = 27 格
N_CELLS = 3 ** 3

#: 档位阈值：``(低/中 分界, 中/高 分界)``，按全目录分子级分布定标（见 :data:`CALIBRATION`）。
THRESHOLDS: dict[str, tuple[float, float]] = {
    "density": (10.0, 16.0),
    "stickiness": (6.0, 11.0),
    "temperature": (3.0, 6.0),
}

#: 定标记录（2026-11-18 第三轮：分子级，3³ = 27 格）
CALIBRATION: dict = {
    "scope": "molecule",
    "samples": 6000,
    "percentiles": {
        "density": {"p33": 10.0, "p50": 13.0, "p67": 16.0, "min": 0.0, "max": 73.0},
        "stickiness": {"p33": 6.0, "p50": 8.0, "p67": 11.0, "min": 0.0, "max": 69.0},
        "temperature": {"p33": 3.0, "p50": 4.0, "p67": 6.0, "min": 0.0, "max": 30.0},
    },
    "shares": {
        "density@(10,16)": (0.297, 0.368, 0.335),
        "stickiness@(6,11)": (0.312, 0.321, 0.366),
        "temperature@(3,6)": (0.298, 0.316, 0.386),
    },
}


# ---------------------------------------------------------------- 分子级属性
def _tally(atoms) -> tuple[float, float, float, Counter, Counter, Counter]:
    dens = stick = temp = 0.0
    dc: Counter = Counter()
    vc: Counter = Counter()
    tc: Counter = Counter()
    for e in atoms:
        if e in DENS_W:
            dens += DENS_W[e]
            dc[e] += 1
        elif e in STICK_W:
            stick += STICK_W[e]
            vc[e] += 1
        elif e in TEMP_W:
            temp += TEMP_W[e]
            tc[e] += 1
    return dens, stick, temp, dc, vc, tc


def molecule_attrs(atoms, edges=None) -> dict:
    """**整个分子**的密度 / 粘性 / 温度（全部原子，不按骨架拆分）。"""
    atoms = list(atoms)
    dens, stick, temp, dc, vc, tc = _tally(atoms)
    return {
        "natoms": len(atoms),
        "density": round(dens, 2),
        "stickiness": round(stick, 2),
        "temperature": round(temp, 2),
        "dens_contrib": dict(dc),
        "stick_contrib": dict(vc),
        "temp_contrib": dict(tc),
    }


def attrs_of(formula_or_atoms, edges=None, catalog=None) -> dict:
    """对分子式计算三个属性（分子级），附带骨架分解（供外观层使用）。"""
    if isinstance(formula_or_atoms, str):
        formula = formula_or_atoms
        if catalog is None:
            from .core.catalog import get_catalog
            catalog = get_catalog()
        rec = catalog.get(formula)
        if rec is None:
            return {"formula": formula, "error": "not_in_catalog", "skeletons": [],
                    "density": 0.0, "stickiness": 0.0, "temperature": 0.0}
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
    """把一个属性值切成 低 / 中 / 高。"""
    lo, hi = (thresholds or THRESHOLDS)[attr]
    if value < lo:
        return GRADES[0]
    if value < hi:
        return GRADES[1]
    return GRADES[2]


def cell_of(density: float, stickiness: float, temperature: float,
            thresholds=None) -> str:
    """三档组合成 27 格的一格，如 ``密-低|粘-低|温-中``。"""
    g = (grade(density, "density", thresholds),
         grade(stickiness, "stickiness", thresholds),
         grade(temperature, "temperature", thresholds))
    return f"密-{g[0]}|粘-{g[1]}|温-{g[2]}"


def property_of(attrs: dict, thresholds=None) -> dict:
    """由三个数值得出物性格（27 格之一）。"""
    d, v, t = attrs["density"], attrs["stickiness"], attrs["temperature"]
    g = {"density": grade(d, "density", thresholds),
         "stickiness": grade(v, "stickiness", thresholds),
         "temperature": grade(t, "temperature", thresholds)}
    return {
        "density": d, "stickiness": v, "temperature": t,
        "grades": g,
        "cell": f"密-{g['density']}|粘-{g['stickiness']}|温-{g['temperature']}",
        "index": (GRADES.index(g["density"]) * 9
                  + GRADES.index(g["stickiness"]) * 3
                  + GRADES.index(g["temperature"])),
    }


def grid() -> list[dict]:
    """枚举全部 27 格（编号 / 三档），按 (密度, 粘性, 温度) 顺序。"""
    out = []
    for i, d in enumerate(GRADES):
        for j, v in enumerate(GRADES):
            for k, t in enumerate(GRADES):
                out.append({
                    "index": i * 9 + j * 3 + k,
                    "cell": f"密-{d}|粘-{v}|温-{t}",
                    "density": d, "stickiness": v, "temperature": t,
                })
    return out
