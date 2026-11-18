# -*- coding: utf-8 -*-
"""元素表、价数、周期表距离、六边形几何与分子式工具。

本模块是内核的**基础层**，不含任何成键逻辑，全部为纯函数、无副作用、无 IO。

术语（与项目文档一致）：
- 三大类：聚（poly）/ 动（move）/ 散（scatter），每类各有 3/2/1 价元素各一；
- 价数（valence）：每个元素最多能接的键数（键级之和）；
- 周期表距离 ``ptable_dist(a, b)``：同类 = |价数差|，跨类 = 价数和。
  这个值在成键规则里充当"优先级编号"，也是"6 级 / 0 级"骨架理论的级数。
- 键型由**两端元素的大类**决定：聚-聚=短键 S、动-动=角键 C、散-散=长键 L，
  跨类取两者允许集合的并集。
"""
from __future__ import annotations

from collections import defaultdict

__all__ = [
    "ELEM", "ORDER", "CN", "VAL", "CAT",
    "CAT_POLY", "CAT_MOVE", "CAT_SCAT",
    "TRI", "DIV", "MONO", "ELEMENTS_BY_VALENCE",
    "S_NBRS", "C_NBRS", "L_NBRS", "S_SET", "C_SET", "L_SET",
    "S_DIRS", "C_DIRS", "L_DIRS",
    "CAT_ALLOWED", "FAMILY_RANK",
    "allowed", "allowed_set", "ptable_dist", "family_rank",
    "formula_of", "zh_of", "parse_formula", "vec_to_atoms", "atoms_to_vec",
    "classify_offset", "midpoint_of", "element_category", "valence",
]

# ---------------------------------------------------------------- 元素表
CAT_POLY = "聚"
CAT_MOVE = "动"
CAT_SCAT = "散"

#: 元素 -> (大类, 价数)。键序即官方分子式书写顺序 ORDER。
ELEM: dict[str, tuple[str, int]] = {
    "O": (CAT_POLY, 3), "X": (CAT_POLY, 2), "C": (CAT_POLY, 1),
    "P": (CAT_MOVE, 3), "W": (CAT_MOVE, 2), "L": (CAT_MOVE, 1),
    "K": (CAT_SCAT, 3), "A": (CAT_SCAT, 2), "F": (CAT_SCAT, 1),
}

#: 分子式书写顺序（也是元素计数向量的维度顺序）。
ORDER: list[str] = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]

#: 元素 -> 中文单字（用于 zh 名称，如 OXC = 秩晶冰）。
CN: dict[str, str] = {
    "O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
    "K": "沌", "A": "气", "F": "焰",
}

VAL: dict[str, int] = {e: v for e, (c, v) in ELEM.items()}
CAT: dict[str, str] = {e: c for e, (c, v) in ELEM.items()}

#: 三价（骨架层）/ 二价（连接层）/ 一价（终端层）。
TRI: frozenset[str] = frozenset({"O", "P", "K"})
DIV: frozenset[str] = frozenset({"X", "W", "A"})
MONO: frozenset[str] = frozenset({"C", "L", "F"})
ELEMENTS_BY_VALENCE: dict[int, tuple[str, ...]] = {
    3: tuple(e for e in ORDER if VAL[e] == 3),
    2: tuple(e for e in ORDER if VAL[e] == 2),
    1: tuple(e for e in ORDER if VAL[e] == 1),
}

# ---------------------------------------------------------------- 六边形几何（axial (q, r) 坐标）
#: 短键 S：共边相邻格（聚-聚）
S_NBRS: list[tuple[int, int]] = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
#: 角键 C：共顶点（动-动）
C_NBRS: list[tuple[int, int]] = [(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)]
#: 长键 L：隔一格（散-散），中间格必须为空
L_NBRS: list[tuple[int, int]] = [(2 * a, 2 * b) for (a, b) in S_NBRS]

S_SET = frozenset(S_NBRS)
C_SET = frozenset(C_NBRS)
L_SET = frozenset(L_NBRS)

#: 方向号（1..12）-> 位移，供绘图/摆放脚本使用。
S_DIRS = {1: (0, 1), 3: (1, 0), 5: (1, -1), 7: (0, -1), 9: (-1, 0), 11: (-1, 1)}
C_DIRS = {2: (1, 1), 4: (2, -1), 6: (1, -2), 8: (-1, -1), 10: (-2, 1), 12: (-1, 2)}
L_DIRS = {k: (2 * a, 2 * b) for k, (a, b) in S_DIRS.items()}

#: 大类组合 -> 允许的位移集合。同类只用该类自己的键型，跨类取并集。
CAT_ALLOWED: dict[frozenset, frozenset] = {
    frozenset((CAT_POLY, CAT_POLY)): S_SET,
    frozenset((CAT_MOVE, CAT_MOVE)): C_SET,
    frozenset((CAT_SCAT, CAT_SCAT)): L_SET,
    frozenset((CAT_POLY, CAT_MOVE)): S_SET | C_SET,
    frozenset((CAT_MOVE, CAT_SCAT)): C_SET | L_SET,
    frozenset((CAT_POLY, CAT_SCAT)): S_SET | L_SET,
}

#: 键族优先级（规则 3）：聚-散 < 聚-动 < 动-散。同类不参与，固定为 0。
FAMILY_RANK: dict[frozenset, int] = {
    frozenset((CAT_POLY, CAT_SCAT)): 0,
    frozenset((CAT_POLY, CAT_MOVE)): 1,
    frozenset((CAT_MOVE, CAT_SCAT)): 2,
}


def element_category(e: str) -> str:
    """元素所在大类（聚/动/散）。"""
    return CAT[e]


def valence(e: str) -> int:
    """元素价数（3/2/1）。"""
    return VAL[e]


def allowed(a: str, b: str) -> frozenset:
    """元素 a 与 b 成键时允许的位移集合。"""
    return CAT_ALLOWED[frozenset((CAT[a], CAT[b]))]


def allowed_set(a: str, b: str) -> frozenset:
    """``allowed`` 的别名，语义更明确。"""
    return allowed(a, b)


def ptable_dist(a: str, b: str) -> int:
    """"周期表距离"：同类按价数差，跨类按价数和。

    取值 0..6；其中 6 只可能来自两个三价元素跨类（O-K / O-P / K-P），
    这正是"6 级中间态骨架"的级数来源。
    """
    if CAT[a] == CAT[b]:
        return abs(VAL[a] - VAL[b])
    return VAL[a] + VAL[b]


def family_rank(a: str, b: str) -> int:
    """规则 3 的键族优先级常数；同大类固定返回 0（不参与比较）。"""
    if CAT[a] == CAT[b]:
        return 0
    return FAMILY_RANK[frozenset((CAT[a], CAT[b]))]


# ---------------------------------------------------------------- 分子式
def formula_of(atoms) -> str:
    """元素序列 -> 官方分子式字符串（按 ORDER 排序，数量 1 省略）。"""
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    return "".join(e + (str(cnt[e]) if cnt[e] > 1 else "") for e in ORDER if cnt[e])


def zh_of(atoms) -> str:
    """元素序列 -> 中文名（如 OXC -> 秩晶冰）。"""
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    return "".join(CN[e] + (str(cnt[e]) if cnt[e] > 1 else "") for e in ORDER if cnt[e])


def parse_formula(f: str) -> tuple[int, ...]:
    """分子式字符串 -> 9 维元素计数向量（ORDER 顺序）。"""
    cnt = defaultdict(int)
    i = 0
    while i < len(f):
        e = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        cnt[e] += int(num) if num else 1
    return tuple(cnt[e] for e in ORDER)


def atoms_to_vec(atoms) -> tuple[int, ...]:
    """元素序列 -> 9 维元素计数向量。"""
    return parse_formula(formula_of(atoms))


def vec_to_atoms(v, elems=None) -> list[str]:
    """元素计数向量 -> 元素序列。``elems`` 默认 ORDER。"""
    elems = ORDER if elems is None else elems
    out: list[str] = []
    for e, c in zip(elems, v):
        out += [e] * int(c)
    return out


# ---------------------------------------------------------------- 位移分类
def classify_offset(delta: tuple[int, int]) -> str | None:
    """位移 -> 键型 "S"/"C"/"L"；不合法返回 None。"""
    if delta in S_SET:
        return "S"
    if delta in C_SET:
        return "C"
    if delta in L_SET:
        return "L"
    return None


def midpoint_of(delta: tuple[int, int]) -> tuple[int, int] | None:
    """长键 L 位移 -> 中间格位移；非 L 返回 None。"""
    if delta not in L_SET:
        return None
    return (delta[0] // 2, delta[1] // 2)
