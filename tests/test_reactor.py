# -*- coding: utf-8 -*-
"""反应引擎：文档中的已知案例、边界条件、确定性、幂等性。"""

import _util
import alchemy
from alchemy.core.canon import mol_label


def _formulas(mols):
    return sorted(alchemy.formula_of(m["atoms"]) for m in mols)


def test_empty_feed():
    assert alchemy.simulate([]) == []


def test_odd_valence_returns_none():
    # 总价数 3+2+1+1 = 7（奇数）-> 不可能接满
    assert alchemy.simulate(["O", "X", "C", "F"]) is None
    assert alchemy.simulate(["K"]) is None          # 3（奇数）
    assert alchemy.simulate(["O", "O"]) is not None  # 6（偶数）


def test_documented_cases_pot_v4():
    # pot_v4.py 自检案例
    assert _formulas(alchemy.simulate(
        alchemy.vec_to_atoms((3, 0, 0, 0, 1, 0, 0, 2, 1)))) == ["O2WA", "OAF"]
    assert _formulas(alchemy.simulate(
        alchemy.vec_to_atoms((0, 1, 0, 0, 1, 1, 2, 0, 1)))) == ["WKF", "XLK"]
    assert _formulas(alchemy.simulate(
        alchemy.vec_to_atoms((3, 0, 0, 5, 0, 0, 2, 0, 0)))) == ["O3P5K2"]


def test_oxc_structure():
    # 文档：OXC = O=X 双键 + O-C 单键
    mols = alchemy.simulate(["O", "X", "C"])
    assert len(mols) == 1
    m = mols[0]
    assert m["atoms"] == ["O", "C", "X"] or alchemy.formula_of(m["atoms"]) == "OXC"
    # 键级多重集 = {2, 1}
    assert sorted(mm for _, _, mm in m["edges"]) == [1, 2]


def test_deterministic():
    # 注意：价数和为偶数只是必要条件，仍可能因"剩下一个没成键的二价原子"而失败
    ok = 0
    for feed in _util.random_feeds(seed=1, count=40):
        a = alchemy.simulate(feed)
        b = alchemy.simulate(feed)
        assert (a is None) == (b is None)
        if a is None:
            continue
        assert _util.mol_multiset(a) == _util.mol_multiset(b)
        ok += 1
    assert ok >= 15, f"只有 {ok} 个可行投料"


def test_reactivity_depends_only_on_composition():
    # 项目已验证：结果只由元素计数向量决定（顺序无关）
    ok = 0
    for feed in _util.random_feeds(seed=2, count=40):
        a = alchemy.simulate(feed)
        if a is None:
            continue
        b = alchemy.simulate(list(reversed(feed)))
        assert b is not None
        assert _util.mol_multiset(a) == _util.mol_multiset(b)
        ok += 1
    assert ok >= 15


def test_idempotent(): 
    # F(F(v)) = F(v)：对产物自身组成再投料，得到同一结构
    for feed in (["O", "X", "C"], ["O", "K"], ["C", "F"],
                 list("OXCPWKA"), list("OOOKKK"), list("OXXCCF")):
        mols = alchemy.simulate(feed)
        if mols is None:
            continue
        atoms2 = [a for m in mols for a in m["atoms"]]
        mols2 = alchemy.simulate(atoms2)
        assert mols2 is not None
        assert _util.mol_multiset(mols) == _util.mol_multiset(mols2)


def test_atom_conservation():
    import random
    from collections import Counter
    from alchemy.core.elements import ORDER
    rng = random.Random(7)
    for _ in range(60):
        feed = _util.random_feed(rng)
        mols = alchemy.simulate(feed)
        if mols is None:
            continue
        out = Counter(a for m in mols for a in m["atoms"])
        assert out == Counter(feed)
        # 每个原子的价数都被填满
        for m in mols:
            deg = Counter()
            for (i, j, mm) in m["edges"]:
                deg[i] += mm
                deg[j] += mm
            for k, a in enumerate(m["atoms"]):
                assert deg[k] == alchemy.VAL[a], (m["atoms"], m["edges"], k)


def test_rules_versions_selectable():
    assert alchemy.SUPPORTED_RULES == (8, 9, 11)
    feed = list("OOOPPKKK")
    for r in (8, 9, 11):
        assert alchemy.simulate(feed, rules=r) is not None
    try:
        alchemy.simulate(feed, rules=10)
    except ValueError:
        pass
    else:
        raise AssertionError("rules=10 应当报错")


def test_return_level6_format():
    mols, level6 = alchemy.simulate(["O", "O", "K", "K"], return_level6=True)
    assert mols is not None
    assert isinstance(level6, list)
    assert len(level6) > 0
    for blk in level6:
        ats, es, mem = blk
        assert isinstance(ats, list) and isinstance(es, list) and isinstance(mem, tuple)
