# -*- coding: utf-8 -*-
"""六边形摆放：与 pot_v2 等价、校验器能抓出非法摆放、目录样例可摆放。"""

import random

import _util

import alchemy
from alchemy.core import geometry as G


def test_single_atom():
    assert alchemy.embed(["O"], []) == {0: (0, 0)}
    assert alchemy.embed([], []) == {}


def test_simple_molecules():
    for atoms, edges in [
        (["O", "K"], [(0, 1, 3)]),
        (["C", "F"], [(0, 1, 1)]),
        (["O", "X", "C"], [(0, 1, 1), (0, 2, 2)]),
        (["K", "A"], [(0, 1, 1)]),
        (["P", "W"], [(0, 1, 1)]),
    ]:
        place = alchemy.embed(atoms, edges)
        assert place is not None, (atoms, edges)
        ok, msg = alchemy.validate(place, atoms, edges)
        assert ok, msg


def test_equivalent_to_pot_v2():
    orig = _util.load_originals()["pot_v2"]
    rng = random.Random(1234)
    feeds = _util.random_feeds(seed=88, count=80, max_types=3, max_n=9)
    checked = 0
    for feed in feeds:
        mols = alchemy.simulate(feed)
        if mols is None:
            continue
        for m in mols:
            a, e = m["atoms"], m["edges"]
            mine = alchemy.embed(a, e)
            theirs = orig.embed_mol2(a, [tuple(x) for x in e])
            assert (mine is None) == (theirs is None), f"可摆放性判定不同：{a} {e}"
            if mine is not None:
                ok, msg = alchemy.validate(mine, a, e)
                assert ok, msg
                ok2, _ = orig.validate_place(mine, a, e)
                assert ok2
            checked += 1
    assert checked > 20


def test_validate_catches_bad_placements():
    atoms = ["O", "K"]
    edges = [(0, 1, 3)]
    # 位移不合法
    assert not alchemy.validate({0: (0, 0), 1: (5, 5)}, atoms, edges)[0]
    # 位置重复
    assert not alchemy.validate({0: (0, 0), 1: (0, 0)}, atoms, edges)[0]
    # L 键中间格被第三个原子占用
    atoms3 = ["K", "A", "C"]
    edges3 = [(0, 1, 1)]
    # K-A 是长键 L（散-散），位移必须 ±(2,0)/(0,2)... 中间格 (1,0) 被 C 占
    assert not alchemy.validate({0: (0, 0), 1: (2, 0), 2: (1, 0)}, atoms3, edges3)[0]
    ok, msg = alchemy.validate({0: (0, 0), 1: (2, 0), 2: (0, 1)}, atoms3, edges3)
    assert ok, msg


def test_validate_none():
    assert alchemy.validate(None, ["O"], []) == (False, "None")


def test_catalog_places_are_valid():
    """目录里已存好的 place 必须能通过严格校验（抽样）。"""
    cat = alchemy.get_catalog()
    rng = random.Random(5)
    recs = [cat.records()[i] for i in rng.sample(range(len(cat)), 150)]
    checked = 0
    for rec in recs:
        if not rec.get("place"):
            continue
        place = {int(k): (int(v[0]), int(v[1])) for k, v in rec["place"].items()}
        ok, msg = alchemy.validate(place, rec["atoms"], [tuple(e) for e in rec["edges"]])
        assert ok, f"{rec['formula']}: {msg}"
        checked += 1
    assert checked > 100


def test_place_dict_roundtrip():
    place = {0: (0, 0), 1: (1, 0)}
    d = alchemy.to_place_dict(place)
    assert d == {"0": [0, 0], "1": [1, 0]}
    assert alchemy.to_place_dict(None) == {}
