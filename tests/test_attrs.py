# -*- coding: utf-8 -*-
"""物质的三个数值属性（分子级）：硬度 / 粘性 / 温度。"""

import random

import _util

import alchemy
import alchemy.attrs as A


def test_weights_are_as_specified():
    """权重表必须与用户口径一致。"""
    assert A.HARD_W == {"O": 3.0, "K": 2.0, "P": 1.0}
    assert A.STICK_W == {"X": 3.0, "W": 2.0, "A": 1.0}
    assert A.TEMP_W == {"F": 3.0, "L": 2.0, "C": 1.0}


def test_temperature_has_no_negative():
    """温度改成 F3/L2/C1 后是纯热值，没有负值。"""
    assert all(v > 0 for v in A.TEMP_W.values())
    assert A.TEMP_W["F"] > A.TEMP_W["L"] > A.TEMP_W["C"]


def test_oxc_molecule_attrs():
    d = A.attrs_of("OXC")
    assert d["hardness"] == 3.0      # O × 3
    assert d["stickiness"] == 3.0    # X × 3
    assert d["temperature"] == 1.0   # C × 1
    assert d["hard_contrib"] == {"O": 1}
    assert d["temp_contrib"] == {"C": 1}


def test_accumulate_per_atom():
    # O2X3C3K3A3：H = 2×3 + 3×2 = 12；V = 3×3 + 3×1 = 12；T = 3×1 = 3
    d = A.attrs_of("O2X3C3K3A3")
    assert d["hardness"] == 12.0
    assert d["stickiness"] == 12.0
    assert d["temperature"] == 3.0


def test_molecule_level_counts_every_atom():
    """属性按整个分子算：桥上的二价原子也要计入粘性。

    ``O2XP2WK2A2`` = O2 + X1 + P2 + W1 + K2 + A2
    硬度 = 2×3 + 2×2 + 2×1 = 12；粘性 = 1×3 + 1×2 + 2×1 = 7；温度 = 0
    """
    d = A.attrs_of("O2XP2WK2A2")
    assert d["stickiness"] == 7.0
    assert d["hardness"] == 12.0
    assert d["temperature"] == 0.0


def test_bridge_belongs_to_both_skeletons():
    """连接两个骨架的二价桥，同时属于这两个骨架（外观层用）。"""
    d = A.attrs_of("O2XP2WK2A2")
    assert d["n_skeletons"] == 2
    both = [s for s in d["skeletons"] if s["bridge_members"]]
    assert len(both) == 2, "两个骨架都应记到同一批桥成员"
    # 两个骨架记到的桥成员集合应相同
    assert both[0]["bridge_members"] == both[1]["bridge_members"]


def test_skeletonless_molecules_still_have_attrs():
    """没有三价原子的分子没有骨架，但分子级属性仍然存在。"""
    for f in ("F2", "XA", "LF"):
        d = A.attrs_of(f)
        assert d["n_skeletons"] == 0, f
        assert d["hardness"] == 0.0, f
    # F2 是焰二聚：温度 = 2 × 3 = 6
    assert A.attrs_of("F2")["temperature"] == 6.0
    # XA：粘性 = X3 + A1 = 4，温度 = 0
    assert A.attrs_of("XA")["stickiness"] == 4.0
    assert A.attrs_of("XA")["temperature"] == 0.0


def test_grades_are_three_levels():
    d = {"hardness": 0.0, "stickiness": 0.0, "temperature": 0.0}
    p = A.property_of(d)
    assert p["grades"] == {"hardness": "低", "stickiness": "低", "temperature": "低"}
    d2 = {"hardness": 999.0, "stickiness": 999.0, "temperature": 999.0}
    p2 = A.property_of(d2)
    assert p2["grades"] == {"hardness": "高", "stickiness": "高", "temperature": "高"}


def test_thresholds_are_ordered():
    for k, (lo, hi) in A.THRESHOLDS.items():
        assert 0 <= lo <= hi, (k, lo, hi)


def test_catalog_wide_monotone():
    """全目录抽样：属性值非负，且档位只会是 低/中/高。"""
    cat = alchemy.get_catalog()
    rng = random.Random(5)
    for i in rng.sample(range(len(cat)), 300):
        r = cat.records()[i]
        d = A.molecule_attrs(r["atoms"], [tuple(e) for e in r["edges"]])
        assert d["hardness"] >= 0 and d["stickiness"] >= 0 and d["temperature"] >= 0
        p = A.property_of(d)
        assert set(p["grades"].values()) <= {"低", "中", "高"}


def test_attrs_of_accepts_atoms_edges():
    mol = alchemy.simulate(["O", "X", "C"])[0]
    d = A.attrs_of(mol["atoms"], mol["edges"])
    assert d["formula"] == "OXC"
    assert d["hardness"] == 3.0
