# -*- coding: utf-8 -*-
"""ops.py：v5 九项操作核（MATERIAL_OPS / OP_TH / LINKAGE / 组装体合成）单元测试。"""

import _util  # noqa: F401  # sys.path 引导

from alchemy import ops as OPS
from alchemy.core.catalog import get_catalog


def _rec(formula):
    """取目录记录（带 atoms/edges/place，走结构路径）。"""
    rec = get_catalog().get(formula)
    assert rec is not None, f"目录缺少 {formula}"
    return rec


# ---------------------------------------------------------------------------
# 表与阈值
# ---------------------------------------------------------------------------

def test_material_ops_table():
    assert len(OPS.MATERIAL_OPS) == 9
    assert list(OPS.OP_KEYS) == [m[0] for m in OPS.MATERIAL_OPS]
    assert len(set(OPS.OP_KEYS)) == 9
    for key, name, element, verb, main in OPS.MATERIAL_OPS:
        assert OPS.OP_NAME[key] == name
        assert OPS.OP_ELEMENT[key] == element
        assert OPS.OP_OF_ELEMENT[element] == key
        assert OPS.OP_MAIN[key] == main
        assert main in OPS.MAIN_LABEL
    # 九个载体元素互不相同（9 元素 ↔ 9 操作 1:1）
    assert len(set(OPS.OP_ELEMENT.values())) == 9
    assert set(OPS.OP_ELEMENT.values()) == set("OXCPWLKAF")


def test_op_thresholds_and_tier():
    assert set(OPS.OP_TH) == set(OPS.OP_KEYS)
    for key, (lo, hi) in OPS.OP_TH.items():
        assert 0.0 < lo < hi
        assert OPS.op_tier(lo - 0.01, key) == OPS.OP_TIERS[0]
        assert OPS.op_tier(lo + 0.01, key) == OPS.OP_TIERS[1]
        assert OPS.op_tier(hi + 0.01, key) == OPS.OP_TIERS[2]
    # 0 归低档；未知值也不抛异常
    for key in OPS.OP_KEYS:
        assert OPS.op_tier(0.0, key) == OPS.OP_TIERS[0]
    assert OPS.op_tier(0.5) in OPS.OP_TIERS


def test_linkage_table_complete_and_symmetric():
    keys = list(OPS.OP_KEYS)
    assert len(OPS.LINKAGE) == 9 * 8 // 2  # 36 对，只存 i<j
    coefs = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            assert (a, b) in OPS.LINKAGE
            coef, kind, reason = OPS.LINKAGE[(a, b)]
            assert 0.2 <= coef <= 1.5
            assert isinstance(kind, str) and kind
            assert isinstance(reason, str) and reason
            coefs.append(coef)
            # 对称查找
            assert OPS.linkage(a, b) == OPS.linkage(b, a)
    # 对角为 0（自耦合由实现补）
    for a in keys:
        assert OPS.linkage(a, a)[0] == 0.0
    # 中文名 / 载体元素两种归一方式
    assert OPS.linkage("支撑", "刚性") == OPS.linkage("sup", "rig")
    assert OPS.linkage("O", "X") == OPS.linkage("sup", "rig")
    # 未知操作报 KeyError
    try:
        OPS.linkage("不存在", "sup")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("未知操作应抛 KeyError")
    # 已知 36 对值的抽样（spec ability_spec §4）
    assert OPS.linkage("sup", "rig")[0] == 1.5
    assert OPS.linkage("sto", "mov")[0] == 1.5
    assert OPS.linkage("sig", "mov")[0] == 1.5
    assert OPS.linkage("clv", "adh")[0] == 1.4
    assert OPS.linkage("clv", "rig")[0] == 0.2


# ---------------------------------------------------------------------------
# 九项操作值（对 spec §5.2 的实测示例；容差 0.15，见 ops.py docstring）
# ---------------------------------------------------------------------------

def test_op_scores_spec_examples():
    def ops(f):
        return OPS.op_scores(_rec(f))["ops"]

    v = ops("OXC")
    assert abs(v["sup"] - 0.57) <= 0.15
    assert abs(v["rig"] - 0.48) <= 0.15
    assert abs(v["adh"] - 1.20) <= 0.15

    v = ops("O3XP4WK3A")
    assert abs(v["sup"] - 3.25) <= 0.15
    assert abs(v["rig"] - 0.40) <= 0.15
    assert abs(v["dif"] - 3.30) <= 0.15
    assert abs(v["ads"] - 1.10) <= 0.15
    assert abs(v["mov"] - 1.12) <= 0.15
    # 已知偏差：sto 比 spec 探针低约 2%（docstring 已记录）
    assert abs(v["sto"] - 4.16) <= 0.20

    v = ops("O4X6P6")
    assert abs(v["sup"] - 4.22) <= 0.15
    assert abs(v["sto"] - 4.67) <= 0.20

    v = ops("O2X3C3K3A3")
    assert abs(v["sup"] - 2.15) <= 0.15
    assert abs(v["rig"] - 1.32) <= 0.15
    assert abs(v["adh"] - 1.08) <= 0.15
    assert abs(v["ads"] - 3.30) <= 0.15

    # 单元素端帽：F2 只有切割
    v = ops("F2")
    assert abs(v["clv"] - 2.60) <= 0.15
    assert v["sup"] == 0.0 and v["sto"] == 0.0


def test_op_scores_shape_and_groups():
    s = OPS.op_scores(_rec("O3XP4WK3A"))
    assert set(s["ops"]) == set(OPS.OP_KEYS)
    assert s["degraded"] is False
    assert s["formula"] == "O3XP4WK3A"
    # poly/scatter/move 三组 = 组内三项之和
    assert abs(s["poly"] - (s["ops"]["sup"] + s["ops"]["rig"] + s["ops"]["adh"])) < 1e-9
    assert abs(s["scatter"] - (s["ops"]["dif"] + s["ops"]["ads"] + s["ops"]["clv"])) < 1e-9
    assert abs(s["move"] - (s["ops"]["sto"] + s["ops"]["mov"] + s["ops"]["sig"])) < 1e-9


def test_op_scores_degraded_formula_path():
    """只有分子式时退化为 v4 价数计数，并标 degraded=True。"""
    s = OPS.op_scores("OXC")
    assert s["degraded"] is True
    assert s["ops"]["sup"] == 3.0  # O 的价数×1
    assert s["ops"]["rig"] == 2.0
    assert s["ops"]["adh"] == 1.0
    assert s["ops"]["dif"] == 0.0
    # 结构路径与退化路径对同一分子式不应相等（OXC 真实结构有键型适配）
    real = OPS.op_scores(_rec("OXC"))["ops"]
    assert real["sup"] != s["ops"]["sup"]


def test_op_features():
    feat = OPS.op_features(_rec("OXC"))
    assert not feat["degraded"]
    for key in OPS.OP_KEYS:
        assert f"{key}_main" in feat
        assert f"{key}_adapt" in feat
        assert feat[f"{key}_main"] >= 0.0
    # 退化路径（只有分子式）
    assert OPS.op_features("OXC")["degraded"]


def test_op_profile_order_and_tiers():
    prof = OPS.op_profile(_rec("O3XP4WK3A"))
    assert prof["formula"] == "O3XP4WK3A"
    assert prof["degraded"] is False
    assert [row["key"] for row in prof["ops"]] == list(OPS.OP_KEYS)
    for row in prof["ops"]:
        assert row["name"] == OPS.OP_NAME[row["key"]]
        assert row["element"] == OPS.OP_ELEMENT[row["key"]]
        assert row["tier"] in OPS.OP_TIERS
        assert row["main"] == OPS.OP_MAIN[row["key"]]
        assert row["value"] >= 0.0


def test_material_abilities_of_matches_scores():
    rec = _rec("O2X3C3K3A3")
    rows = OPS.material_abilities_of(rec)
    assert len(rows) == 9
    vals = {row["element"]: row for row in rows}
    for key, value in OPS.op_scores(rec)["ops"].items():
        element = OPS.OP_ELEMENT[key]
        assert abs(vals[element]["value"] - value) < 1e-9
        assert vals[element]["tier"] in OPS.OP_TIERS
        assert vals[element]["main"] == OPS.OP_MAIN[key]


# ---------------------------------------------------------------------------
# 组装体合成（§6：q/β/A + 模块 + 六特征谓词）
# ---------------------------------------------------------------------------

def test_assembly_ops_synthesis_and_modules():
    members = ["O4X6P6", "O2X3C3K3A3", "O3XP4WK3A", "OXC"]
    res = OPS.assembly_ops(members)
    assert res["n"] == 4
    assert set(res["raw"]) == set(OPS.OP_KEYS)
    assert set(res["gain"]) == set(OPS.OP_KEYS)
    assert set(res["ops"]) == set(OPS.OP_KEYS)
    # 协同增益 β≥1 → 合成能力不小于原始能力
    for key in OPS.OP_KEYS:
        assert res["ops"][key] >= res["raw"][key] - 1e-9
    assert res["modules"], "应至少识别出一个模块"
    names = set()
    for mod in res["modules"]:
        assert mod["name"]
        assert 0.0 < mod["coef"] <= 2.0
        assert len(mod["ops"]) >= 1
        assert mod["members"] >= 1
        names.add(mod["name"])
    # 六条生命特征谓词（英文键 + 中文键两套视图）
    assert set(res["features"]) == {"metabolism", "motion", "sensing",
                                    "feeding", "division", "repair"}
    assert len(res["features_zh"]) == len(res["features"])
    assert all(isinstance(v, bool) for v in res["features"].values())
    # 至少有一个操作被覆盖
    assert res["coverage"] >= 1


def test_organ_modules_candidates():
    members = ["O4X6P6", "O2X3C3K3A3", "O3XP4WK3A", "OXC"]
    mods = OPS.organ_modules(members)
    assert isinstance(mods, list) and mods
    for mod in mods:
        for k in ("ops", "name", "coef", "type", "members", "ops_covered"):
            assert k in mod
    # 至少一个模块满足类器官候选（成员≥3 且覆盖≥3 项操作）
    assert any(m.get("organ_candidate") for m in mods)
