# -*- coding: utf-8 -*-
"""物质的三个数值属性（分子级）：密度 / 粘性 / 温度 → 3³ = 27 格。"""

import _util

import alchemy
import alchemy.attrs as A


def test_weights_are_as_specified():
    """权重表必须与用户口径一致。"""
    assert A.DENS_W == {"O": 3.0, "K": 2.0, "P": 1.0}
    assert A.STICK_W == {"X": 3.0, "W": 2.0, "A": 1.0}
    assert A.TEMP_W == {"F": 3.0, "L": 2.0, "C": 1.0}


def test_temperature_zero_is_absolute_zero():
    """温度是热力学量：无能量元素时 0 = 绝对零度，无负值。"""
    assert all(v > 0 for v in A.TEMP_W.values())
    assert A.attrs_of("F2")["temperature"] == 6.0     # 2 × 3
    assert A.attrs_of("XA")["temperature"] == 0.0     # 无能量元素


def test_oxc_attrs():
    d = A.attrs_of("OXC")
    assert d["density"] == 3.0      # O × 3
    assert d["stickiness"] == 3.0   # X × 3
    assert d["temperature"] == 1.0  # C × 1


def test_accumulate_per_atom():
    # O2X3C3K3A3：密度 = 2×3 + 3×2 = 12；粘性 = 3×3 + 3×1 = 12；温度 = 3×1 = 3
    d = A.attrs_of("O2X3C3K3A3")
    assert d["density"] == 12.0
    assert d["stickiness"] == 12.0
    assert d["temperature"] == 3.0


def test_molecule_level_counts_every_atom():
    """属性按整个分子算：桥上的二价原子也要计入粘性。

    O2XP2WK2A2 = O2 + X1 + P2 + W1 + K2 + A2
    密度 = 2×3 + 2×2 + 2×1 = 12；粘性 = 1×3 + 1×2 + 2×1 = 7；温度 = 0
    """
    d = A.attrs_of("O2XP2WK2A2")
    assert d["density"] == 12.0
    assert d["stickiness"] == 7.0
    assert d["temperature"] == 0.0


def test_bridge_belongs_to_both_skeletons():
    """跨两个骨架的二价桥，同时属于这两个骨架（外观层用）。"""
    d = A.attrs_of("O2XP2WK2A2")
    assert d["n_skeletons"] == 2
    both = [s for s in d["skeletons"] if s["bridge_members"]]
    assert len(both) == 2
    assert both[0]["bridge_members"] == both[1]["bridge_members"]


def test_skeletonless_molecules_still_have_attrs():
    for f in ("F2", "XA", "LF"):
        d = A.attrs_of(f)
        assert d["n_skeletons"] == 0, f
        assert d["density"] == 0.0, f
    assert A.attrs_of("XA")["stickiness"] == 4.0   # X3 + A1


def test_grade_three_levels():
    assert A.grade(0.0, "density") == "低"
    assert A.grade(12.0, "density") == "中"
    assert A.grade(99.0, "density") == "高"


def test_27_grid():
    """每轴三相 → 3³ = 27 格，编号 0~26 且互不重复。"""
    g = A.grid()
    assert len(g) == 27
    assert A.N_CELLS == 27
    assert [c["index"] for c in g] == list(range(27))
    assert len({c["cell"] for c in g}) == 27


def test_property_cell_matches_grid():
    d = A.attrs_of("OXC")
    p = A.property_of(d)
    # 密度 3.0 < 10 → 低；粘性 3.0 < 6 → 低；温度 1.0 < 3 → 低
    assert p["cell"] == "密-低|粘-低|温-低"
    assert 0 <= p["index"] < 27
    assert p["cell"] == A.grid()[p["index"]]["cell"]


def test_thresholds_are_ordered():
    for k, (lo, hi) in A.THRESHOLDS.items():
        assert 0 <= lo <= hi, (k, lo, hi)


def test_catalog_wide():
    """全目录抽样：属性非负，格位落在 0~26。"""
    import random
    cat = alchemy.get_catalog()
    rng = random.Random(5)
    seen = set()
    for i in rng.sample(range(len(cat)), 400):
        r = cat.records()[i]
        d = A.molecule_attrs(r["atoms"], [tuple(e) for e in r["edges"]])
        assert d["density"] >= 0 and d["stickiness"] >= 0 and d["temperature"] >= 0
        p = A.property_of(d)
        assert 0 <= p["index"] < 27
        seen.add(p["index"])
    assert len(seen) > 10


def test_attrs_of_accepts_atoms_edges():
    mol = alchemy.simulate(["O", "X", "C"])[0]
    d = A.attrs_of(mol["atoms"], mol["edges"])
    assert d["formula"] == "OXC"
    assert d["density"] == 3.0
