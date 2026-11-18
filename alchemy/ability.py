# -*- coding: utf-8 -*-
"""能力系统：三条轴 × 每轴 8 种情况 = 512 种复合能力。

## 规则（2026-11-18，用户口径）

**沿用"最多原子主导"**，但**并列最多时不再裁断，而是记为"复合能力"**。
每条轴（= 每个价数层）提供**一个能力维度**，每个维度有 **8 种情况**：

| 类别 | 情况 | 说明 |
|---|---|---|
| 单元素主导 | 3 种 | 该层三元素里只有一个是最大 |
| 双元素主导 | 3 种 | 恰好两个并列最大 |
| 三元素主导 | 1 种 | 三者全等（且 > 0） |
| 无主导 | 1 种 | 该层三元素全为 0（没有这一层的原子） |

3 + 3 + 1 + 1 = **8 种/轴**，三条轴复合 → **8³ = 512 种能力**。

> 注意：这与 `docs/T74_CLASSIFICATION.md` 的"并列裁断"不同——那里并列要按优先级裁决，
> 这里并列**保留为复合能力**，所以信息不丢失（双主导、三主导都是独立情况）。

## 用法

    >>> import alchemy.ability as AB
    >>> AB.ability_of("OXC")["id"]
    'O|X|C'
    >>> AB.ability_of("OXCWKAF")["label"]
    '秩|晶|冰'
    >>> AB.ability_of("O2X2P2W2K2A2")["id"]     # 三价 O=K=P 并列
    'ALL|ALL|NONE'
"""

from __future__ import annotations

from collections import Counter

from .core.elements import ORDER, parse_formula

__all__ = [
    "AXES", "CASES", "N_CASES", "N_ABILITIES",
    "axis_case", "case_name", "ability_of", "distribution", "catalog_combos",
]

#: 三条轴：(键, 中文名, 三元组)。三元组顺序也决定双主导的书写顺序。
AXES: tuple[tuple[str, str, tuple[str, str, str]], ...] = (
    ("skeleton", "三价", ("O", "K", "P")),
    ("state", "二价", ("X", "A", "W")),
    ("energy", "一价", ("C", "F", "L")),
)

#: 8 种情况的键：三个单元素（元素符号本身）+ 三个双主导 + ALL + NONE
CASES: tuple[str, ...] = ("SINGLE1", "SINGLE2", "SINGLE3", "DUAL12", "DUAL13", "DUAL23",
                          "ALL", "NONE")
N_CASES = 8
N_ABILITIES = N_CASES ** len(AXES)     # 512

#: 每轴 8 种情况的中文名
CASE_NAMES: dict[str, dict[str, str]] = {
    "skeleton": {"O": "秩", "K": "沌", "P": "势",
                 "OK": "秩沌", "OP": "秩势", "KP": "沌势",
                 "ALL": "三合", "NONE": "无"},
    "state": {"X": "晶", "A": "气", "W": "流",
              "XA": "晶气", "XW": "晶流", "AW": "气流",
              "ALL": "三合", "NONE": "无"},
    "energy": {"C": "冰", "F": "焰", "L": "电",
               "CF": "冰焰", "CL": "冰电", "FL": "焰电",
               "ALL": "三合", "NONE": "无"},
}


def axis_case(vec, trio) -> str:
    """一条轴上的 8 种情况之一。

    - 严格最大 → 该元素符号（``O`` / ``K`` / ``P`` …）
    - 两个并列最大 → 按轴内顺序拼接（``OK`` / ``OP`` / ``KP`` …）
    - 三者全等且 > 0 → ``ALL``
    - 全为 0 → ``NONE``
    """
    counts = {e: vec[ORDER.index(e)] for e in trio}
    mx = max(counts.values())
    if mx == 0:
        return "NONE"
    tops = [e for e in trio if counts[e] == mx]     # 已按轴内顺序
    if len(tops) == 1:
        return tops[0]
    if len(tops) == 2:
        return "".join(tops)
    return "ALL"


def case_name(axis_key: str, case: str) -> str:
    """情况的中文名。"""
    return CASE_NAMES[axis_key].get(case, case)


def ability_of(formula_or_vec) -> dict:
    """一个物质的复合能力。

    返回 ``{'formula','cases','names','id','label','counts'}``；
    ``id`` 形如 ``O|X|C``，``label`` 形如 ``秩|晶|冰``。
    """
    if isinstance(formula_or_vec, str):
        formula = formula_or_vec
        vec = parse_formula(formula)
    else:
        vec = tuple(int(x) for x in formula_or_vec)
        from .core.elements import formula_of, vec_to_atoms
        formula = formula_of(vec_to_atoms(vec))

    cases = {}
    names = {}
    counts = {}
    for key, _cn, trio in AXES:
        case = axis_case(vec, trio)
        cases[key] = case
        names[key] = case_name(key, case)
        counts[key] = {e: vec[ORDER.index(e)] for e in trio}

    keys = [k for k, _, _ in AXES]
    return {
        "formula": formula,
        "cases": cases,
        "names": names,
        "counts": counts,
        "id": "|".join(cases[k] for k in keys),
        "label": "|".join(names[k] for k in keys),
    }


def distribution(formulas, axis: str | None = None) -> dict:
    """统计能力分布：``axis`` 省略时统计 512 种复合；指定轴时统计该轴的 8 种。"""
    if axis is None:
        c = Counter(ability_of(f)["id"] for f in formulas)
    else:
        idx = {"skeleton": 0, "state": 1, "energy": 2}[axis]
        c = Counter(ability_of(f)["id"].split("|")[idx] for f in formulas)
    return dict(c.most_common())


def catalog_combos(formulas) -> dict:
    """返回 ``{'n_present': 已出现的复合数, 'n_total': 512, 'empty': 未出现的组合}``。"""
    present = {ability_of(f)["id"] for f in formulas}
    empty = []
    for a in _case_keys("skeleton"):
        for b in _case_keys("state"):
            for c in _case_keys("energy"):
                combo = f"{a}|{b}|{c}"
                if combo not in present:
                    empty.append(combo)
    return {"n_present": len(present), "n_total": N_ABILITIES, "empty": empty}


def _case_keys(axis: str) -> list[str]:
    trio = dict((k, t) for k, _, t in AXES)[axis]
    a, b, c = trio
    return [a, b, c, a + b, a + c, b + c, "ALL", "NONE"]
