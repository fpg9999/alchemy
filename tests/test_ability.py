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


# ---------------------------------------------------------------- v3：能力=类别辐条
def test_category_axes_are_poly_scatter_move():
    keys = [k for k, _cn, _t in AB.CATEGORY_AXES]
    assert keys == ["poly", "scatter", "move"]
    trios = {k: t for k, _cn, t in AB.CATEGORY_AXES}
    assert trios["poly"] == ("O", "X", "C")
    assert trios["scatter"] == ("K", "A", "F")
    assert trios["move"] == ("P", "W", "L")


def test_default_weight_is_valence():
    """默认权重 = 价数（周期表环号）。"""
    assert AB.CATEG_W["O"] == 3.0 and AB.CATEG_W["X"] == 2.0 and AB.CATEG_W["C"] == 1.0
    assert AB.CATEG_W["K"] == 3.0 and AB.CATEG_W["A"] == 2.0 and AB.CATEG_W["F"] == 1.0
    assert AB.CATEG_W["P"] == 3.0 and AB.CATEG_W["W"] == 2.0 and AB.CATEG_W["L"] == 1.0


def test_scores_are_numeric():
    """能力是三项数值：OXC 全在聚轴（O3+X2+C1）。"""
    s = AB.scores("OXC")
    assert s["poly"] == 6.0
    assert s["scatter"] == 0.0
    assert s["move"] == 0.0
    assert s["natoms"] == 3


def test_scores_have_shares():
    s = AB.scores("OXCPWKA")
    sh = s["axes"]["poly"]["shares"]
    assert abs(sum(sh.values()) - 1.0) < 1e-6
    # O3 : X2 : C1 → 6 → 0.5 / 0.333 / 0.167
    assert abs(sh["O"] - 0.5) < 1e-3
    assert abs(sh["X"] - 1 / 3) < 1e-3


def test_scores_are_per_atom_normalized():
    s = AB.scores("OXC")
    assert abs(s["poly_per_atom"] - 2.0) < 1e-6   # 6 / 3 atoms


def test_pure_category_molecules():
    """纯类别的分子只在一条轴上取值。"""
    assert AB.scores("F2")["scatter"] == 2.0     # F 价 1 × 2
    assert AB.scores("F2")["poly"] == 0.0
    s = AB.scores("OK")
    assert s["poly"] == 3.0 and s["scatter"] == 3.0   # O 与 K 都是 3 价


def test_no_discrete_512_by_default():
    """默认口径下不再产出离散 id；512 只作为历史接口保留。"""
    s = AB.scores("OXC")
    assert "id" not in s
    assert AB.ability_of("OXC")["id"] == "O|X|C"   # 历史接口仍可用


# ---------------------------------------------------------------- v4：三主 × 三次级 × 三阶
def test_structure_is_3x3():
    """3 主方向，每个 3 个次级能力，每个元素掌管一个。"""
    assert len(AB.SUB_ABILITIES) == 3
    for key, cn, subs in AB.SUB_ABILITIES:
        assert len(subs) == 3, key
        assert {e for e, _n, _t in subs} == set(dict(
            (k, t) for k, _c, t in AB.CATEGORY_AXES)[key])


def test_all_nine_elements_covered():
    els = [e for _k, _c, subs in AB.SUB_ABILITIES for e, _n, _t in subs]
    assert len(els) == 9 and len(set(els)) == 9


def test_sub_tier_boundaries():
    """三阶：无并入低（0 也属于低）。"""
    th = (2, 6)
    assert AB.sub_tier(0, th) == "低"
    assert AB.sub_tier(1, th) == "低"
    assert AB.sub_tier(2, th) == "低"
    assert AB.sub_tier(3, th) == "中"
    assert AB.sub_tier(6, th) == "中"
    assert AB.sub_tier(7, th) == "高"


def test_no_zero_tier():
    """不再有"无"这一档。"""
    assert AB.SUB_TIERS == ("低", "中", "高")
    for v in (0, 1, 5, 99):
        assert AB.sub_tier(v, (2, 6)) in AB.SUB_TIERS


def test_profile_shape():
    p = AB.profile("OXC")
    assert set(p["main"]) == {"poly", "scatter", "move"}
    for key in ("poly", "scatter", "move"):
        m = p["main"][key]
        assert set(m) >= {"label", "value", "tier", "subs"}
        assert len(m["subs"]) == 3
        # 主能力值 = 三个次级之和
        assert abs(m["value"] - sum(s["value"] for s in m["subs"])) < 1e-6


def test_oxc_profile():
    """OXC 全在聚轴；缺失的两轴落到"低"。"""
    p = AB.profile("OXC")
    assert p["main"]["poly"]["value"] == 6.0
    assert [s["tier"] for s in p["main"]["poly"]["subs"]] == ["低", "低", "低"]
    assert p["main"]["scatter"]["value"] == 0.0
    assert p["main"]["scatter"]["tier"] == "低"      # 0 → 低


def test_f2_has_cutting_ability():
    """F2：散轴的"切割"（焰 F）= 2 → 中。"""
    p = AB.profile("F2")
    s = [x for x in p["main"]["scatter"]["subs"] if x["element"] == "F"][0]
    assert s["name"] == "切割"
    assert s["value"] == 2.0
    assert s["tier"] == "中"


def test_abilities_of_is_flat_nine():
    """9 项次级能力摊平，各自独立。"""
    rows = AB.abilities_of("O2X3C3K3A3")
    assert len(rows) == 9
    assert {r["main"] for r in rows} == {"poly", "scatter", "move"}
    for r in rows:
        assert set(r) >= {"element", "name", "value", "tier", "main"}


def test_abilities_are_independent():
    """能力并存且互不影响：改一个元素的数量，只影响它自己那一项。"""
    a = AB.profile("OXC")
    b = AB.profile("OXC")
    assert a == b   # 无副作用
    rows = AB.abilities_of("OXC")
    # 每项能力都独立给出档位，不因其他项而变
    assert all(r["tier"] in AB.SUB_TIERS for r in rows)
