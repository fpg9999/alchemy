# -*- coding: utf-8 -*-
"""元素表、分子式、周期表距离、几何常量。"""

import _util  # noqa: F401  (确保仓库根在 sys.path)

import alchemy
from alchemy.core import elements as E


def test_element_table():
    assert len(E.ELEM) == 9
    assert E.ORDER == ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
    assert E.VAL == {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1,
                     "K": 3, "A": 2, "F": 1}
    assert E.TRI == {"O", "P", "K"}
    assert E.DIV == {"X", "W", "A"}
    assert E.MONO == {"C", "L", "F"}


def test_ptable_dist():
    # 同类按价数差，跨类按价数和
    assert E.ptable_dist("O", "X") == 1
    assert E.ptable_dist("O", "O") == 0
    assert E.ptable_dist("O", "K") == 6     # 三价跨类 -> 6 级
    assert E.ptable_dist("P", "K") == 6
    assert E.ptable_dist("O", "P") == 6
    assert E.ptable_dist("X", "F") == 3
    assert E.ptable_dist("C", "F") == 2     # 跨类 1+1
    assert E.ptable_dist("C", "L") == 2     # C 是聚、L 是动，跨类 -> 1+1
    assert E.ptable_dist("X", "W") == 4     # 聚-动 跨类 2+2


def test_formula_roundtrip():
    assert E.formula_of(["O", "X", "C"]) == "OXC"
    assert E.formula_of(["C", "O", "X"]) == "OXC"          # 顺序无关
    assert E.formula_of(["O", "O", "X", "X", "C"]) == "O2X2C"
    assert E.zh_of(["O", "X", "C"]) == "秩晶冰"
    v = E.atoms_to_vec(["O", "O", "K"])
    assert v == E.parse_formula("O2K")
    assert E.formula_of(E.vec_to_atoms(v)) == "O2K"
    assert E.formula_of([]) == ""


def test_offset_classification():
    for d in E.S_SET:
        assert E.classify_offset(d) == "S"
    for d in E.C_SET:
        assert E.classify_offset(d) == "C"
    for d in E.L_SET:
        assert E.classify_offset(d) == "L"
    assert E.classify_offset((0, 0)) is None
    assert E.classify_offset((5, 5)) is None
    # L 的中间格
    assert E.midpoint_of((2, 0)) == (1, 0)
    assert E.midpoint_of((1, 0)) is None


def test_allowed_sets():
    # 同类只用该类键型
    assert E.allowed("O", "X") <= E.S_SET
    assert E.allowed("P", "W") <= E.C_SET
    assert E.allowed("K", "A") <= E.L_SET
    # 跨类取并集
    assert E.allowed("O", "P") == E.S_SET | E.C_SET
    assert E.allowed("P", "K") == E.C_SET | E.L_SET
    assert E.allowed("O", "K") == E.S_SET | E.L_SET


def test_only_two_types_per_category():
    # 每个大类恰好 3 个元素、价数 3/2/1
    for cat in ("聚", "动", "散"):
        els = [e for e in E.ORDER if E.CAT[e] == cat]
        assert len(els) == 3
        assert sorted(E.VAL[e] for e in els) == [1, 2, 3]
