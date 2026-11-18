# -*- coding: utf-8 -*-
"""物质目录：规模、字段、查询、路径解析。"""

import os
import random

import _util

import alchemy
from alchemy.core.catalog import ENV_VAR, default_catalog_path


def test_catalog_size():
    cat = alchemy.get_catalog()
    assert len(cat) == 84225
    st = cat.stats()
    assert st["total"] == 84225
    assert st["le16"] == 82961
    assert st["max_natoms"] == 97
    assert st["missing_place"] > 0


def test_required_fields():
    cat = alchemy.get_catalog()
    for rec in cat.records()[:200]:
        for key in ("formula", "natoms", "atoms", "edges"):
            assert key in rec, (rec.get("formula"), key)
        assert len(rec["atoms"]) == rec["natoms"]
        # 键表下标必须在范围内
        for e in rec["edges"]:
            assert 0 <= e[0] < rec["natoms"] and 0 <= e[1] < rec["natoms"]
            assert e[2] >= 1


def test_known_substances():
    cat = alchemy.get_catalog()
    for f, natoms in [("OXC", 3), ("OX2C", 4), ("OK", 2), ("LF", 2),
                      ("OXCPWKA", 7), ("O2X3C3K3A3", 14)]:
        assert f in cat, f
        assert cat[f]["natoms"] == natoms
        assert cat[f]["formula"] == f


def test_lookup_apis():
    cat = alchemy.get_catalog()
    assert cat.get("NOT_A_FORMULA") is None
    assert cat.get("NOT_A_FORMULA", "x") == "x"
    assert cat["OXC"]["zh"] == "秩晶冰"
    hist = cat.natoms_histogram()
    assert hist[2] > 0 and sum(hist.values()) == len(cat)
    assert len(cat.by_natoms(3)) > 0
    assert len(cat.formulas()) == len(cat)


def test_feed_vector():
    cat = alchemy.get_catalog()
    v = cat.feed("OXC")
    assert v == (1, 1, 1, 0, 0, 0, 0, 0, 0)
    # 用自身组成投料，能查回自己（不动点）
    assert cat.find_by_vec(v)["formula"] == "OXC"


def test_catalog_matches_engine():
    """目录里的物质，用 pot_v4 验证：结构应等于 F(自身组成)（抽样）。"""
    cat = alchemy.get_catalog()
    rng = random.Random(2026)
    recs = [cat.records()[i] for i in rng.sample(range(len(cat)), 80)]
    same = 0
    for rec in recs:
        mols = alchemy.simulate(list(rec["atoms"]))
        if mols is None or len(mols) != 1:
            continue
        if mols[0]["atoms"] == rec["atoms"]:
            pass
        from alchemy.core.canon import mol_label
        if mol_label(mols[0]["atoms"], mols[0]["edges"]) == \
                mol_label(rec["atoms"], [tuple(e) for e in rec["edges"]]):
            same += 1
    # 大部分记录应与规则 1~11 一致（部分历史记录是旧口径，见 CALIBER_DIVERGENCE）
    assert same >= len(recs) * 0.7, f"只有 {same}/{len(recs)} 条与引擎一致"


def test_default_path_has_no_absolute_hardcoding():
    p = default_catalog_path()
    assert p.name == "t4_catalog_all_validated.json"
    assert p.is_absolute()
    assert p.parent == _util.REPO


def test_env_var_override(tmp_path=None):
    # 用环境变量把目录指到一个临时（不存在的）路径，应该报出带提示的错误
    old = os.environ.get(ENV_VAR)
    try:
        os.environ[ENV_VAR] = str(_util.REPO / "_no_such_file.json")
        try:
            alchemy.load_catalog()
        except FileNotFoundError as exc:
            assert "unpack_data.py" in str(exc)
        else:
            raise AssertionError("应当抛 FileNotFoundError")
    finally:
        if old is None:
            os.environ.pop(ENV_VAR, None)
        else:
            os.environ[ENV_VAR] = old
