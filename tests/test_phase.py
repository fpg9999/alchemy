# -*- coding: utf-8 -*-
"""相分类规则：三条轴 + 两两并列循环压制 + 三者全等第四相。"""

import itertools
import random

import _util

import alchemy
import alchemy.phase as F
from alchemy.core.elements import ORDER, parse_formula
from alchemy.core.reactor import RULE9_PRIORITY


def test_priority_reuses_rule9():
    """层级模式的裁决优先级必须与反应规则 9 完全一致。"""
    assert F.RULE9_PRIORITY == RULE9_PRIORITY
    cats = [alchemy.CAT[e] for e in F.RULE9_PRIORITY]
    assert cats == ["聚"] * 3 + ["散"] * 3 + ["动"] * 3


def test_axes_cover_all_nine_elements():
    all_e = [e for _, _, trio in F.AXES for e in trio]
    assert sorted(all_e) == sorted(ORDER)
    for _, label, trio in F.AXES:
        assert sorted(alchemy.CAT[e] for e in trio) == ["动", "散", "聚"], label


def test_cycle_is_a_three_cycle():
    """聚>散、散>动、动>聚 必须构成真循环，不能退化成层级。"""
    assert ("聚", "散") in F.BEATS
    assert ("散", "动") in F.BEATS
    assert ("动", "聚") in F.BEATS
    # 反向不在压制集合里
    assert ("散", "聚") not in F.BEATS
    # 三条轴各取一对，验证动素能赢聚素（循环才有这条路）
    assert F.axis_winner(_vec({"O": 1, "P": 1}), ("O", "K", "P"), mode="cycle")[0] == "P"
    assert F.axis_winner(_vec({"X": 1, "W": 1}), ("X", "A", "W"), mode="cycle")[0] == "W"
    assert F.axis_winner(_vec({"C": 1, "L": 1}), ("C", "F", "L"), mode="cycle")[0] == "L"


def _vec(counts: dict) -> tuple:
    v = [0] * 9
    for e, n in counts.items():
        v[ORDER.index(e)] = n
    return tuple(v)


def test_two_way_tie_pairs_under_cycle():
    trio = ("X", "A", "W")
    cases = {(1, 1, 0): "X",   # 聚 vs 散 -> 聚
             (0, 1, 1): "A",   # 散 vs 动 -> 散
             (1, 0, 1): "W"}   # 动 vs 聚 -> 动
    for (x, a, w), expect in cases.items():
        el, cnt, tie = F.axis_winner(_vec({"X": x, "A": a, "W": w}), trio, mode="cycle")
        assert (el, cnt, tie) == (expect, 1, True), (x, a, w)


def test_hybrid_is_the_default_rule():
    """v4：两两并列走循环，三者全等归聚；永不产生第四相。"""
    assert F.DEFAULT_MODE == "hybrid"

    # 两两并列 → 循环（动可以赢聚）
    trio = ("X", "A", "W")
    assert F.axis_winner(_vec({"X": 1, "W": 1}), trio)[0] == "W"   # 动压聚
    assert F.axis_winner(_vec({"A": 1, "W": 1}), trio)[0] == "A"   # 散压动
    assert F.axis_winner(_vec({"X": 1, "A": 1}), trio)[0] == "X"   # 聚压散

    # 三者全等 → 聚（不是第四相）
    el3, cnt3, tie3 = F.axis_winner(_vec({"X": 2, "A": 2, "W": 2}), trio)
    assert (el3, cnt3, tie3) == ("X", 2, True)
    # 全零 → 同样归聚
    assert F.axis_winner(_vec({}), trio)[0] == "X"

    # 全目录上：默认模式永不产生第四相
    cat = alchemy.get_catalog()
    for r in cat.records():
        p = F.phase_of(r["formula"])
        assert p["n_fourth"] == 0, r["formula"]
        assert F.FOURTH not in p["id"], r["formula"]


def test_hybrid_keeps_liquid_and_electric():
    """v4 相对 v3 的关键收益：液与电没有被"聚优先"吞掉。"""
    import collections
    cat = alchemy.get_catalog()
    forms = [r["formula"] for r in cat.records()]
    st = collections.Counter(F.state_of(f) for f in forms)
    en = collections.Counter(F.energy_of(f)["energy"] for f in forms)
    n = len(forms)
    assert st["液"] / n > 0.25, st          # 液应占 1/4 以上
    assert en["电"] / n > 0.20, en          # 电应占 1/5 以上
    assert st["固"] / n < 0.45, st          # 固不应超过 45%


def test_hierarchy_mode_keeps_strict_order():
    """v1 的层级模式：并列一律按 聚>散>动，动素永不赢。"""
    trio = ("X", "A", "W")
    assert F.axis_winner(_vec({"X": 1, "W": 1}), trio, mode="hierarchy")[0] == "X"
    assert F.axis_winner(_vec({"A": 1, "W": 1}), trio, mode="hierarchy")[0] == "A"


def test_three_way_tie_is_fourth_phase():
    trio = ("X", "A", "W")
    for counts in ({"X": 1, "A": 1, "W": 1}, {"X": 2, "A": 2, "W": 2}):
        el, cnt, tie = F.axis_winner(_vec(counts), trio, mode="cycle")
        assert el == F.FOURTH and tie is True
    # 层级模式（v1）不产生第四相：三者全等按优先级取聚
    el_h, _, _ = F.axis_winner(_vec({"X": 1, "A": 1, "W": 1}), trio, mode="hierarchy")
    assert el_h == "X"


def test_absent_layer_three_ways():
    """该层全零有三种处理：第四相 / 聚优先约定 / 记为"无该层"。"""
    trio = ("X", "A", "W")
    assert F.axis_winner(_vec({}), trio, mode="cycle", absent_mode="fourth")[0] == F.FOURTH
    assert F.axis_winner(_vec({}), trio, mode="cycle", absent_mode="poly")[0] == "X"
    el_abs, cnt, _ = F.axis_winner(_vec({}), trio, mode="cycle", absent_mode="none")
    assert el_abs == F.ABSENT and cnt == 0
    # 注意：hierarchy 模式不受 absent_mode 影响，一律按层级裁决
    assert F.axis_winner(_vec({}), trio, mode="hierarchy")[0] == "X"


def test_simple_cases():
    # OXC：三层各有严格多数，所有模式都一样
    for mode in F.SUPPORTED_MODES:
        for am in F.ABSENT_MODES:
            p = F.phase_of("OXC", mode=mode, absent_mode=am)
            assert p["id"] == "O/X/C"
            assert p["names"] == ("秩", "固", "冰")
            assert p["n_tied_axes"] == 0

    # O2XP2WK2A2：骨架层 O2=K2=P2 三者全等；能量层全零
    assert F.phase_id("O2XP2WK2A2", mode="cycle", absent_mode="fourth") == "〇/A/〇"
    assert F.phase_id("O2XP2WK2A2", mode="cycle", absent_mode="poly") == "〇/A/C"
    assert F.phase_id("O2XP2WK2A2", mode="cycle", absent_mode="none") == "〇/A/—"
    assert F.phase_id("O2XP2WK2A2", mode="hierarchy") == "O/A/C"

    # OXCPWKA：骨架 O=K=P=1、状态 X=A=W=1 -> 两条轴都是第四相；能量 C1 严格
    assert F.phase_id("OXCPWKA", mode="cycle") == "〇/〇/C"
    assert F.phase_id("OXCPWKA", mode="hierarchy") == "O/X/C"


def test_every_vector_has_definite_phase():
    """任何计数向量都能拿到确定结果（相 / 第四相 / 缺席），不会异常。"""
    allowed = {"O", "K", "P", "X", "A", "W", "C", "F", "L", F.FOURTH, F.ABSENT}
    for v in itertools.product(range(3), repeat=3):
        vec = _vec({"X": v[0], "K": v[1], "F": v[2]})
        for mode in F.SUPPORTED_MODES:
            for am in F.ABSENT_MODES:
                p = F.phase_of(vec, mode=mode, absent_mode=am)
                for k in ("skeleton", "state", "energy"):
                    assert p[k] in allowed, (v, mode, am, k, p[k])


def test_27_types_all_reachable():
    """严格多数应能构造出全部 27 型（不含第四相）。"""
    winners = (("O", "K", "P"), ("X", "A", "W"), ("C", "F", "L"))
    seen = set()
    for trio in itertools.product(*winners):
        vec = _vec({e: 2 for e in trio})
        seen.add(F.phase_id(vec, mode="cycle"))
    assert len(seen) == 27, len(seen)


def test_cycle_never_leaves_a_loose_end():
    """循环模式下，两两并列的胜出者必须属于该并列对，且关系是压制。"""
    rng = random.Random(11)
    for _ in range(3000):
        vec = tuple(rng.randint(0, 3) for _ in range(9))
        for _, label, trio in F.AXES:
            v = F.axis_vote(vec, trio, mode="cycle")
            if v["kind"] == "two":
                a, b = v["tops"]
                assert v["element"] in (a, b), (label, v)
                ca, cb = alchemy.CAT[a], alchemy.CAT[b]
                assert (ca, cb) in F.BEATS or (cb, ca) in F.BEATS


def test_formula_and_vector_agree():
    for f in ("OXC", "O2XP2WK2A2", "LF", "O2X3C3K3A3"):
        for mode in F.SUPPORTED_MODES:
            assert F.phase_of(f, mode=mode)["id"] == \
                F.phase_of(parse_formula(f), mode=mode)["id"]


def test_distribution_helpers():
    forms = ["OXC", "LF", "O2XP2WK2A2"]
    assert sum(F.distribution(forms).values()) == 3
    dstate = F.distribution(forms, axis="state", absent_mode="none")
    assert sum(dstate.values()) == 3
    assert set(dstate) <= {"X", "A", "W", F.FOURTH, F.ABSENT}


def test_catalog_wide_invariants():
    """全目录：层级模式下动素不赢并列；循环模式下三者全等必为第四相。"""
    cat = alchemy.get_catalog()
    for r in cat.records():
        p_h = F.phase_of(r["formula"], mode="hierarchy")
        for key in ("skeleton", "state", "energy"):
            a = p_h["axes"][key]
            if a["kind"] == "two":
                assert alchemy.CAT[a["element"]] != "动", (r["formula"], key)
        p_c = F.phase_of(r["formula"], mode="cycle")
        for key in ("skeleton", "state", "energy"):
            a = p_c["axes"][key]
            if a["kind"] == "three":
                assert a["element"] == F.FOURTH
