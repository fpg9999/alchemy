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
    # v3：数值化能力（类别辐条 → 聚 / 散 / 动）
    "CATEGORY_AXES", "CATEG_W", "CATEG_W_ALT", "category_score", "scores",
    # v4：三主方向 × 三次级 × 三阶（能力并存、互不影响、不做组合）
    "SUB_ABILITIES", "MAIN_TH", "SUB_TIERS", "sub_tier", "profile", "abilities_of",
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


# ================================================================
# v3（2026-11-18）：能力轴改为**类别辐条**（聚 / 散 / 动），与物性的价数环垂直
# ================================================================
#
# 周期表是以恒素为中心的三辐星：
#   - **径向 = 价数环**（3 价外 / 2 价中 / 1 价内） → 决定**物性**（密度 / 粘性 / 温度）
#   - **角向 = 类别辐条**（聚 / 散 / 动）           → 决定**能力**（聚 / 散 / 动）
#
# 二者在几何上互相垂直，所以两套数值不会互相污染——这正是之前"刚性液体"问题的根治。
#
# 权重默认取**价数（环号）**：3 价原子记 3、2 价记 2、1 价记 1。
#   [聚] = 3·O + 2·X + 1·C
#   [散] = 3·K + 2·A + 1·F
#   [动] = 3·P + 2·W + 1·L
# 权重表 `CATEG_W` 可整体替换（换成旧的逐元素特征值也不影响接口）。

from .core.elements import VAL  # noqa: E402

#: 三条**类别辐条** → 三组能力
CATEGORY_AXES: tuple[tuple[str, str, tuple[str, str, str]], ...] = (
    ("poly", "聚", ("O", "X", "C")),
    ("scatter", "散", ("K", "A", "F")),
    ("move", "动", ("P", "W", "L")),
)

#: 能力权重：默认 = 价数（周期表环号）。
CATEG_W: dict[str, float] = {e: float(VAL[e]) for e in VAL}

#: 备选权重：直接把物性那套逐元素特征值按类别重组（供对比）
CATEG_W_ALT: dict[str, float] = {
    "O": 3.0, "X": 3.0, "C": 1.0,     # 聚
    "K": 2.0, "A": 1.0, "F": 3.0,     # 散
    "P": 1.0, "W": 2.0, "L": 2.0,     # 动
}


def category_score(vec, trio, weights=None) -> dict:
    """一条**类别辐条**上的能力值与元素占比。"""
    w = CATEG_W if weights is None else weights
    by = {e: round(w[e] * vec[ORDER.index(e)], 3) for e in trio}
    total = round(sum(by.values()), 3)
    shares = ({e: round(v / total, 4) for e, v in by.items()} if total > 0 else {})
    dominant = None
    if total > 0:
        mx = max(shares.values())
        tops = [e for e in trio if shares[e] == mx]
        dominant = tops[0] if len(tops) == 1 else None
    return {"value": total, "by_element": by, "shares": shares, "dominant": dominant}


def scores(formula_or_vec, weights=None) -> dict:
    """物质的**三项能力数值**（聚 / 散 / 动），附带元素占比与按原子归一的强度。"""
    if isinstance(formula_or_vec, str):
        formula = formula_or_vec
        vec = parse_formula(formula)
    else:
        vec = tuple(int(x) for x in formula_or_vec)
        from .core.elements import formula_of, vec_to_atoms
        formula = formula_of(vec_to_atoms(vec))

    out = {"formula": formula, "axes": {}}
    values = {}
    for key, cn, trio in CATEGORY_AXES:
        s = category_score(vec, trio, weights)
        s["label"] = cn
        out["axes"][key] = s
        values[key] = s["value"]
    for key in ("poly", "scatter", "move"):
        out[key] = values[key]
    n = sum(vec) or 1
    out["natoms"] = sum(vec)
    for key in ("poly", "scatter", "move"):
        out[f"{key}_per_atom"] = round(values[key] / n, 4)
    return out


def score_distribution(formulas, axis: str = "poly", weights=None) -> dict:
    c = Counter(scores(f, weights)[axis] for f in formulas)
    return dict(sorted(c.items()))


# ================================================================
# v4（2026-11-18）：三主方向 × 三层次级能力 × 三阶
# ================================================================
#
# 结构：
#   3 个**主能力方向**（聚 / 散 / 动，= 周期表三条辐条）
#     └ 每个主方向 3 个**次级能力**，每个元素掌管一个（共 9 个）
#          └ 每个次级能力用**两个阈值**切成 **3 阶**（低 / 中 / 高）
#
# 次级能力名取自 `docs/T71_ABILITIES.md` 的"材料层能力"表，保证与项目既有命名一致。
#
# 权重沿用 `CATEG_W`（= 价数），因此 **主能力值 = 三个次级能力值之和**，口径自洽。

#: 三主方向 × 三次级能力：(主键, 主名, ((元素, 次级能力名, (阈值1, 阈值2)), ...))
#: 阈值为**上界**（闭区间）：``value <= t1`` → 低（含 0，即"没有该元素"），
#: ``<= t2`` → 中，否则 → 高。**"无"与"低"合并为同一档。**
SUB_ABILITIES: tuple = (
    ("poly", "聚", (
        ("O", "结构支撑", (6, 12)),
        ("X", "刚性", (2, 6)),
        ("C", "粘合", (1, 2)),
    )),
    ("scatter", "散", (
        ("K", "分化", (3, 12)),
        ("A", "吸附", (2, 6)),
        ("F", "切割", (1, 2)),
    )),
    ("move", "动", (
        ("P", "储能", (6, 12)),
        ("W", "移动", (2, 6)),
        ("L", "信号", (1, 2)),
    )),
)

#: 主方向的三阶阈值（上界），由全目录 p33 / p67 定标
MAIN_TH: dict[str, tuple[float, float]] = {
    "poly": (6, 13),
    "scatter": (6, 12),
    "move": (6, 13),
}

#: 只有三阶。"无"并入"低"（2026-11-18：无与低是同一档）
SUB_TIERS = ("低", "中", "高")


def sub_tier(value: float, th: tuple[float, float]) -> str:
    """三阶：``<= t1`` → 低（含 0），``<= t2`` → 中，否则 → 高。

    注意 0 也属于"低"——**没有该元素**与**该元素极少**不再区分。
    """
    if value <= th[0]:
        return "低"
    if value <= th[1]:
        return "中"
    return "高"


def profile(formula_or_vec, weights=None) -> dict:
    """完整能力档位：3 主方向 × 3 次级能力，每项各自分三阶。

    **所有能力并存、互不影响**——这里只给出每项能力的数值与档位，
    不做组合枚举、不互相折算。

    返回 ``{主键: {'label','value','tier','subs':[{element,name,value,tier}]}}``。
    """
    if isinstance(formula_or_vec, str):
        formula = formula_or_vec
        vec = parse_formula(formula)
    else:
        vec = tuple(int(x) for x in formula_or_vec)
        from .core.elements import formula_of, vec_to_atoms
        formula = formula_of(vec_to_atoms(vec))

    w = CATEG_W if weights is None else weights
    out = {"formula": formula, "main": {}}
    for key, cn, subs in SUB_ABILITIES:
        total = 0.0
        rows = []
        for e, name, th in subs:
            v = round(w[e] * vec[ORDER.index(e)], 3)
            total += v
            rows.append({"element": e, "name": name, "value": v,
                         "tier": sub_tier(v, th)})
        total = round(total, 3)
        out["main"][key] = {
            "label": cn,
            "value": total,
            "tier": sub_tier(total, MAIN_TH[key]),
            "subs": rows,
        }
    return out


def abilities_of(formula_or_vec, weights=None) -> list[dict]:
    """把 9 项次级能力摊平成一维列表（每项独立，便于逐项展示/比较）。"""
    p = profile(formula_or_vec, weights)
    rows = []
    for key, cn, _subs in SUB_ABILITIES:
        for s in p["main"][key]["subs"]:
            rows.append({**s, "main": key, "main_label": cn})
    return rows


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
