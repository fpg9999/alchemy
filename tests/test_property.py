# -*- coding: utf-8 -*-
"""物性名合成：三轴 -> {概念形容词}{能量形容词}{物态名词}。"""

import _util

import alchemy
import alchemy.phase as F


def test_oxc_is_rigid_cold_solid():
    """用户给的例子：OXC 是"刚性低温固体"，即岩石。"""
    d = F.describe("OXC")
    assert d["frame"] == "刚体"
    assert d["state"] == "固"
    assert d["energy"] == "冰"
    assert d["name"] == "刚性低温固体"
    assert d["typical"] == "岩石、金属、水晶"
    assert d["gravity"] is True


def test_name_format_is_three_parts():
    """物性名 = 概念形容词 + 能量形容词 + 物态名词。"""
    for f in ("OXC", "OXCPWKA", "O2X3C3K3A3", "O3XP4WK3A", "F2", "L2"):
        d = F.describe(f)
        assert d["name"] == (F.FRAME_ADJ[d["frame"]] +
                             F.ENERGY_ADJ[d["energy"]] +
                             F.STATE_NOUN[d["state"]])


def test_reproduces_nine_cell_table():
    """v3 只有 3×3 = 9 格：概念 × 物态，逐格验证典型对应物存在。"""
    # 用严格多数构造 3x3 代表向量
    from alchemy.core.elements import ORDER

    def vec(**kw):
        v = [0] * 9
        for e, n in kw.items():
            v[ORDER.index(e)] = n
        return tuple(v)

    frames = {"O": "刚体", "K": "胶体", "P": "软体"}
    states = {"X": "固", "A": "气", "W": "液"}
    seen = set()
    for fe, fname in frames.items():
        for se, sname in states.items():
            d = F.describe(vec(**{fe: 2, se: 2}))
            assert d["frame"] == fname, (fe, d)
            assert d["state"] == sname, (se, d)
            assert d["typical"], (fname, sname)
            seen.add((fname, sname))
    assert len(seen) == 9


def test_oxc_and_xa_both_rigid_cold_solid():
    """v3 下全零层按 聚 裁决，所以 XA 也落到刚体·固·冰。"""
    for f in ("OXC", "XA"):
        d = F.describe(f)
        assert d["name"] == "刚性低温固体"
        assert d["typical"] == "岩石、金属、水晶"


def test_three_frames_only_in_v3():
    """v3 抹除第四相后，概念族只剩三主相。"""
    seen = {F.describe(f)["frame"] for f in
            ("OXC", "OXCPWKA", "O2X3C3K3A3", "O3XP4WK3A", "XA", "F2", "PK", "WA")}
    assert seen == {"刚体", "胶体", "软体"}


def test_no_fourth_phase_by_default():
    """默认模式下任何物质都不会得到第四相（〇）。"""
    for f in ("OXC", "OXCPWKA", "LF", "F2", "XA", "OK", "O2XP2WK2A2", "O3XP4WK3A"):
        p = F.phase_of(f)
        assert p["n_fourth"] == 0, f
        assert F.FOURTH not in p["id"], f
        assert F.state_of(f) in ("固", "液", "气"), f
        assert F.energy_of(f)["energy"] in ("冰", "焰", "电"), f
        assert F.role_of(f)["role"] in ("刚体", "胶体", "软体"), f


def test_describe_fields():
    d = F.describe("OK")
    for k in ("formula", "frame", "state", "energy", "id", "name", "typical",
              "hardness", "density", "cohesion", "gravity", "energy_effect"):
        assert k in d, k
    # 虚态不受重力
    if d["state"] == "虚":
        assert d["gravity"] is False


def test_property_profile_ordering():
    """刚体密度最高、晶体最硬、软体黏聚最低。"""
    p = F._PROFILE
    assert max(v[1] for v in p.values()) == p["刚体"][1]
    assert max(v[0] for v in p.values()) == p["晶体"][0]
    assert min(v[2] for v in p.values()) == p["软体"][2]


def test_physical_name_on_vector():
    from alchemy.core.elements import parse_formula
    assert F.physical_name(parse_formula("OXC")) == F.physical_name("OXC")
