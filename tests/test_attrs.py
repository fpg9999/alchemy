# -*- coding: utf-8 -*-
"""三轴：质量 / 物态 / 温度 → 27 格物质类。"""

import _util

import alchemy
import alchemy.attrs as A


def test_weights():
    assert A.MASS_W == {"O": 3.0, "K": 2.0, "P": 1.0}
    assert A.STATE_W == {"X": 3.0, "W": 2.0, "A": 1.0}
    assert A.TEMP_W == {"F": 3.0, "L": 2.0, "C": 1.0}


def test_values_are_layer_averages():
    """取值 = 该层加权和 / 该层原子数（0~3）。"""
    d = A.attrs_of("OXC")
    assert d["mass"] == 3.0      # O×3 / 1
    assert d["state"] == 3.0     # X×3 / 1
    assert d["temperature"] == 1.0   # C×1 / 1

    d2 = A.attrs_of("O2X3C3K3A3")
    assert d2["mass"] == 2.4     # (2×3 + 3×2) / 5
    assert d2["state"] == 2.0    # (3×3 + 3×1) / 6
    assert d2["temperature"] == 1.0


def test_oxc_is_heavy_solid_cold():
    d = A.attrs_of("OXC")
    p = A.property_of(d)
    assert p["cell"] == "重·固·冷"
    assert p["behavior"]["collision"].startswith("完全阻挡")
    assert p["behavior"]["gravity"].startswith("下沉")
    assert "稀薄恒素" in p["behavior"]["e_field"]


def test_missing_layer_falls_to_lowest_tier():
    """缺失层：分子为 0，0 必然落在最低档（轻 / 气 / 冷）。"""
    d = A.attrs_of("F2")           # 只有一价，无三价、无二价
    assert d["mass"] == 0.0 and d["state"] == 0.0
    p = A.property_of(d)
    assert p["cell"] == "轻·气·热"
    # 轻气 + 热：上升、灼伤、富集恒素
    assert p["behavior"]["gravity"].startswith("上升")
    assert "富集恒素" in p["behavior"]["e_field"]


def test_xa_is_light_liquid():
    d = A.attrs_of("XA")           # 无三价、无 1 价
    p = A.property_of(d)
    assert p["cell"].split("·")[0] == "轻"
    assert p["cell"].split("·")[1] == "液"
    assert p["cell"].split("·")[2] == "冷"


def test_grade_and_tier_names():
    assert A.grade(0.0, "mass") == "低"
    assert A.grade(2.0, "mass") == "中"
    assert A.grade(3.0, "mass") == "高"
    assert A.tier_name(0.0, "mass") == "轻"
    assert A.tier_name(3.0, "state") == "固"
    assert A.tier_name(0.0, "temperature") == "冷"


def test_27_grid():
    g = A.grid()
    assert len(g) == 27 == A.N_CELLS
    assert [c["index"] for c in g] == list(range(27))
    assert len({c["cell"] for c in g}) == 27
    for c in g:
        assert set(c["behavior"]) == {"collision", "gravity", "e_field"}


def test_cell_matches_grid():
    p = A.property_of(A.attrs_of("OXC"))
    assert p["cell"] == A.grid()[p["index"]]["cell"]


def test_behavior_tables_cover_all_tiers():
    for t in A.TIER_NAMES["mass"]:
        assert t in A.GRAVITY
    for t in A.TIER_NAMES["state"]:
        assert t in A.COLLISION
    for t in A.TIER_NAMES["temperature"]:
        assert t in A.E_SOURCE


def test_buoyancy_is_relative_to_medium():
    """同一块轻固体：在重液体里上浮，在轻气体里下沉。"""
    r1 = A.buoyancy(object_mass=1.0, medium_mass=2.8, volume=10)
    assert r1["net"] > 0 and r1["motion"] == "上升"
    r2 = A.buoyancy(object_mass=1.0, medium_mass=0.0, volume=10)
    assert r2["net"] < 0 and r2["motion"] == "下沉"
    r3 = A.buoyancy(object_mass=2.0, medium_mass=2.0, volume=5)
    assert r3["motion"] == "悬浮"


def test_buoyancy_carry_capacity():
    r = A.buoyancy(object_mass=1.0, medium_mass=2.8, volume=10)
    assert abs(r["can_carry"] - 18.0) < 1e-6


def test_catalog_wide():
    import random
    cat = alchemy.get_catalog()
    rng = random.Random(5)
    seen = set()
    for i in rng.sample(range(len(cat)), 400):
        r = cat.records()[i]
        d = A.molecule_attrs(r["atoms"], [tuple(e) for e in r["edges"]])
        for k in ("mass", "state", "temperature"):
            assert 0.0 <= d[k] <= 3.0, (r["formula"], k, d[k])
        p = A.property_of(d)
        assert 0 <= p["index"] < 27
        seen.add(p["index"])
    assert len(seen) > 10
