# -*- coding: utf-8 -*-
"""能力系统：每轴 8 种情况，三维复合 8³ = 512。"""

import _util

import alchemy
import alchemy.ability as AB
from alchemy.core.elements import ORDER


def _vec(counts: dict) -> tuple:
    v = [0] * 9
    for e, n in counts.items():
        v[ORDER.index(e)] = n
    return tuple(v)


def test_eight_cases_per_axis():
    trio = ("O", "K", "P")
    assert AB.axis_case(_vec({"O": 3}), trio) == "O"          # 单主导
    assert AB.axis_case(_vec({"O": 2, "K": 2}), trio) == "OK"  # 双主导
    assert AB.axis_case(_vec({"O": 1, "P": 1}), trio) == "OP"
    assert AB.axis_case(_vec({"K": 1, "P": 1}), trio) == "KP"
    assert AB.axis_case(_vec({"O": 2, "K": 2, "P": 2}), trio) == "ALL"   # 三合
    assert AB.axis_case(_vec({"O": 0, "K": 0, "P": 0}), trio) == "NONE"  # 无


def test_strict_dominance_beats_tie():
    trio = ("O", "K", "P")
    assert AB.axis_case(_vec({"O": 3, "K": 2, "P": 2}), trio) == "O"
    assert AB.axis_case(_vec({"O": 3, "K": 3, "P": 1}), trio) == "OK"


def test_dual_order_follows_axis_order():
    trio = ("O", "K", "P")
    # 即使输入里先写 P 再写 O，输出仍按轴内顺序 O→K→P
    assert AB.axis_case(_vec({"P": 2, "O": 2}), trio) == "OP"
    assert AB.axis_case(_vec({"P": 2, "K": 2}), trio) == "KP"


def test_ability_of_basic():
    a = AB.ability_of("OXC")
    assert a["id"] == "O|X|C"
    assert a["label"] == "秩|晶|冰"
    assert a["cases"] == {"skeleton": "O", "state": "X", "energy": "C"}


def test_ability_of_composite():
    # OXCPWKA：各元素各一个 → 三价 O=K=P、二价 X=A=W 都是三合；一价只有 C
    a = AB.ability_of("OXCPWKA")
    assert a["id"] == "ALL|ALL|C"
    # O2X2P2W2K2A2：三价/二价都三合，没有一价元素
    assert AB.ability_of("O2X2P2W2K2A2")["id"] == "ALL|ALL|NONE"


def test_ability_space_size():
    assert AB.N_CASES == 8
    assert AB.N_ABILITIES == 512


def test_all_512_ids_constructible():
    ids = set()
    for a in AB._case_keys("skeleton"):
        for b in AB._case_keys("state"):
            for c in AB._case_keys("energy"):
                ids.add(f"{a}|{b}|{c}")
    assert len(ids) == 512


def test_case_names_exist():
    for key, _cn, _trio in AB.AXES:
        for case in AB._case_keys(key):
            assert AB.case_name(key, case) != case or case in ("ALL", "NONE") or len(case) <= 1


def test_catalog_combos_partial():
    """全目录上 512 种组合只出现一部分——说明理论空间大于实际可见空间。"""
    cat = alchemy.get_catalog()
    forms = [r["formula"] for r in cat.records()]
    info = AB.catalog_combos(forms)
    assert info["n_total"] == 512
    assert 200 <= info["n_present"] <= 512
    assert len(info["empty"]) == 512 - info["n_present"]


def test_distribution_helpers():
    forms = ["OXC", "OXCPWKA"]
    d = AB.distribution(forms)
    assert sum(d.values()) == 2
    dstate = AB.distribution(forms, axis="state")
    assert sum(dstate.values()) == 2
    assert set(dstate) <= set(AB._case_keys("state"))
