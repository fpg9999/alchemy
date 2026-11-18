# -*- coding: utf-8 -*-
"""物质的三个数值属性：硬度 / 粘性 / 温度（分子级）。

## 规则（2026-11-18 第二轮修订，用户口径）

不再用"最大元素 = 性质"的离散分类，改成**按原子逐个累加**的数值属性：

| 属性 | 由哪一层决定 | 权重（每个原子） |
|---|---|---|
| **硬度** | 三价层 秩O / 沌K / 势P | **O +3、K +2、P +1** |
| **粘性** | 二价层 晶X / 流W / 气A | **X +3、W +2、A +1** |
| **温度** | 一价层 焰F / 电L / 冰C | **F +3、L +2、C +1**（纯热值，无负值） |

### 2026-11-18 第二轮的三个改动

1. **粘性权重**改为 X3 / W2 / A1（原 X3 / A2 / W1）；
2. **温度权重**改为 F3 / L2 / C1（原 C −3 / L +1 / F +5）。
   注意：**温度不再有负值**，冰只是"热值最低"，因此档位标签从"冷/常温/热"改为"低/中/高"；
3. **属性按整个分子算**，不再按骨架拆开算。**骨架概念保留**，但它现在只用于决定**物质外观**
   （由 `skeleton_units()` 提供分解）。

### 骨架桥的归属

**连接两个骨架的二价桥，同时属于它所连接的两个骨架**（2026-11-18 修订）。
它不再被"排除"，而是在 `skeleton_units()` 里同时记到两侧的成员表里——这只影响外观层，
不影响分子级属性（分子级本来就数全部原子）。

## 用法

    >>> import alchemy.attrs as A
    >>> A.attrs_of("OXC")
    {'formula': 'OXC', 'hardness': 3.0, 'stickiness': 3.0, 'temperature': 1.0, ...}
    >>> A.property_of(A.attrs_of("OXC"))["label"]
    '硬-低/粘-中/温-低'
"""

from __future__ import annotations

from collections import Counter

from .core.elements import DIV, MONO, TRI

__all__ = [
    "HARD_W", "STICK_W", "TEMP_W", "THRESHOLDS", "GRADES", "CALIBRATION",
    "molecule_attrs", "attrs_of", "skeleton_units", "grade", "property_of",
]

#: 硬度权重：三价层。聚（秩 O）> 散（沌 K）> 动（势 P）。
HARD_W: dict[str, float] = {"O": 3.0, "K": 2.0, "P": 1.0}

#: 粘性权重：二价层。晶 X 3 > 流 W 2 > 气 A 1。
STICK_W: dict[str, float] = {"X": 3.0, "W": 2.0, "A": 1.0}

#: 温度权重：一价层。焰 F 3 > 电 L 2 > 冰 C 1（**纯热值，无负值**）。
TEMP_W: dict[str, float] = {"F": 3.0, "L": 2.0, "C": 1.0}

GRADES = ("低", "中", "高")

#: 档位阈值：``(低/中 分界, 中/高 分界)``，按全目录分子级分布定标（见 :data:`CALIBRATION`）。
#: 取 33% / 67% 分位数，三档大致均分（低 30% / 中 33% / 高 36%）。
THRESHOLDS: dict[str, tuple[float, float]] = {
    "hardness": (10.0, 16.0),
    "stickiness": (6.0, 11.0),
    "temperature": (3.0, 6.0),
}

#: 定标记录（2026-11-18 第二轮：分子级、权重 O3/K2/P1、X3/W2/A1、F3/L2/C1）
CALIBRATION: dict = {
    "scope": "molecule",
    "samples": 6000,
    "percentiles": {
        "hardness": {"p33": 10.0, "p50": 13.0, "p67": 16.0, "min": 0.0, "max": 73.0},
        "stickiness": {"p33": 6.0, "p50": 8.0, "p67": 11.0, "min": 0.0, "max": 69.0},
        "temperature": {"p33": 3.0, "p50": 4.0, "p67": 6.0, "min": 0.0, "max": 30.0},
    },
    "shares": {
        "hardness@(10,16)": (0.297, 0.368, 0.335),
        "stickiness@(6,11)": (0.312, 0.321, 0.366),
        "temperature@(3,6)": (0.298, 0.316, 0.386),
    },
}


# ---------------------------------------------------------------- 分子级属性
def _tally(atoms) -> tuple[float, float, float, Counter, Counter, Counter]:
    hard = stick = temp = 0.0
    hc: Counter = Counter()
    vc: Counter = Counter()
    tc: Counter = Counter()
    for e in atoms:
        if e in HARD_W:
            hard += HARD_W[e]
            hc[e] += 1
        elif e in STICK_W:
            stick += STICK_W[e]
            vc[e] += 1
        elif e in TEMP_W:
            temp += TEMP_W[e]
            tc[e] += 1
    return hard, stick, temp, hc, vc, tc


def molecule_attrs(atoms, edges=None) -> dict:
    """**整个分子**的硬度 / 粘性 / 温度（含全部原子，不按骨架拆分、不排除桥）。"""
    atoms = list(atoms)
    hard, stick, temp, hc, vc, tc = _tally(atoms)
    return {
        "natoms": len(atoms),
        "hardness": round(hard, 2),
        "stickiness": round(stick, 2),
        "temperature": round(temp, 2),
        "hard_contrib": dict(hc),
        "stick_contrib": dict(vc),
        "temp_contrib": dict(tc),
    }


def attrs_of(formula_or_atoms, edges=None, catalog=None) -> dict:
    """对分子式计算三个属性（分子级）。

    参数可以是分子式字符串（从目录取结构），或 ``(atoms, edges)``。
    额外附带骨架分解（``skeletons``，供"外观"层使用）。
    """
    if isinstance(formula_or_atoms, str):
        formula = formula_or_atoms
        if catalog is None:
            from .core.catalog import get_catalog
            catalog = get_catalog()
        rec = catalog.get(formula)
        if rec is None:
            return {"formula": formula, "error": "not_in_catalog",
                    "skeletons": [], "hardness": 0.0, "stickiness": 0.0,
                    "temperature": 0.0}
        atoms = list(rec["atoms"])
        edges = [tuple(e) for e in rec["edges"]]
    else:
        atoms = list(formula_or_atoms)
        edges = [tuple(e) for e in (edges or [])]
        from .core.elements import formula_of
        formula = formula_of(atoms)

    out = {"formula": formula}
    out.update(molecule_attrs(atoms, edges))
    out["n_skeletons"] = 0
    out["skeletons"] = skeleton_units(atoms, edges)
    out["n_skeletons"] = len(out["skeletons"])
    return out


# ---------------------------------------------------------------- 骨架分解（外观层）
def skeleton_units(atoms, edges) -> list[dict]:
    """把分子拆成骨架单元，供**外观**层使用（不参与属性计算）。

    规则：
    - 骨架 = 三价原子的连通块；
    - **连接两个骨架的二价桥同时属于这两个骨架**（2026-11-18 修订，不再排除）；
    - 其余二价/一价原子归它挂着的那个骨架；挂不到任何骨架的（如 `XA`）单列。

    返回 ``[{members, atoms, bridge_members, ...}]``。没有三价原子的分子返回 ``[]``。
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

    # 每个非三价原子能触及的骨架集合
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
                    bridges.append(i)      # 同时属于多个骨架
        members = sorted(set(members))
        units.append({
            "members": members,
            "atoms": [atoms[i] for i in members],
            "size": len(mem),
            "bridge_members": sorted(bridges),
            "hardness": round(sum(HARD_W.get(atoms[i], 0) for i in mem), 2),
            "stickiness": round(sum(STICK_W.get(atoms[i], 0) for i in members), 2),
            "temperature": round(sum(TEMP_W.get(atoms[i], 0) for i in members), 2),
        })
    return units


# ---------------------------------------------------------------- 阈值分档
def grade(value: float, attr: str, thresholds=None) -> str:
    """把一个属性值切成 低 / 中 / 高。"""
    lo, hi = (thresholds or THRESHOLDS)[attr]
    if value < lo:
        return GRADES[0]
    if value < hi:
        return GRADES[1]
    return GRADES[2]


def property_of(attrs: dict, thresholds=None) -> dict:
    """由三个数值得出物性标签，如 ``硬-中/粘-高/温-低``。"""
    h, v, t = attrs["hardness"], attrs["stickiness"], attrs["temperature"]
    g = {"hardness": grade(h, "hardness", thresholds),
         "stickiness": grade(v, "stickiness", thresholds),
         "temperature": grade(t, "temperature", thresholds)}
    return {
        "hardness": h, "stickiness": v, "temperature": t,
        "grades": g,
        "label": f"硬-{g['hardness']}/粘-{g['stickiness']}/温-{g['temperature']}",
    }
