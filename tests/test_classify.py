# -*- coding: utf-8 -*-
"""骨架分类：库完整性、三层拆解、结构定理、稳定性判定。"""

import random

import _util

import alchemy
from alchemy.core import classify as C


def test_library_loads():
    lib = C.load_library()
    assert lib["n_forms"] == 38
    assert lib["n_multi"] == 35
    assert lib["n_single_templates"] == 7
    # 单元素类型块统一记为 O
    assert C.block_label(["K"], []) == C.block_label(["O"], [])
    assert C.block_label(["O"], []) == C.block_label(["P"], [])


def test_block_library_coverage():
    """35 个多三价形态 + 7 个单三价模块，全部应能在库里命中。"""
    lib = C.load_library()
    for f in lib["forms"]:
        atoms = list(f["atoms"])
        edges = [tuple(e) for e in f["edges"]]
        rep = C.classify_block(atoms, edges, lib)
        assert rep["in_library"], f"{f['formula']} 未被库识别"
    for n, es in C.SINGLE_TEMPLATES:
        rep = C.classify_block(["O"] * n, es, lib)
        assert rep["in_library"] and rep["kind"] == "single"


def test_classify_simple():
    # 用引擎自己产出的结构（OXC = O-C 单键 + O=X 双键）
    mol = alchemy.simulate(["O", "X", "C"])[0]
    out = alchemy.classify(mol["atoms"], mol["edges"])
    assert out["ok"] is True
    assert out["formula"] == "OXC"
    assert out["category"] == "single_trivalent"
    assert out["in_library"] is True
    assert out["level6"]["n_blocks"] == 1
    assert out["level6"]["blocks"][0]["kind"] == "single"
    # atoms = ['O', 'C', 'X'] -> O 骨架、C 端帽、X 桥
    assert out["layers"] == {"skeleton": [0], "bridge": [2], "cap": [1]}
    assert out["stable"] is True
    assert out["skeleton"]["structure_theorem_ok"] is True


def test_classify_no_trivalent():
    # C-F 没有三价元素
    out = alchemy.classify(["C", "F"], [(0, 1, 1)])
    assert out["category"] == "no_trivalent"
    assert out["level6"]["n_blocks"] == 0
    assert out["in_library"] is True
    assert out["skeleton"]["structure_theorem_ok"] is True


def test_classify_odd_valence():
    out = alchemy.classify(["O", "K", "F"], [])
    assert out["ok"] is False
    assert out["reason"] == "valence_unfillable"


def test_fusion_bonds():
    # O-O 同类三价键 = 0 级融合
    out = alchemy.classify(["O", "O", "X", "X"], [(0, 1, 1), (0, 2, 1), (1, 3, 1)])
    assert out["skeleton"]["n_fusion_bonds"] == 1
    assert out["skeleton"]["fusion_bonds"][0]["element"] == "O"


def test_divalent_roles():
    # K-A-K：A 是跨块真桥
    out = alchemy.classify(
        ["K", "A", "K", "C", "C"],
        [(0, 1, 1), (1, 2, 1), (0, 3, 1), (2, 4, 1)],
    )
    roles = [d["role"] for d in out["divalent"]]
    assert roles == ["真桥(跨块)"], roles


def test_structure_theorem_on_catalog_sample():
    """复核 T17/T18 的结构定理：终态三价组件 = 6 级块之并（抽样，两种口径都成立）。

    注意：结构定理是**内禀**性质（由 F(组成) 决定），与目录里存的结构是哪个口径无关。
    """
    cat = alchemy.get_catalog()
    lib = C.load_library()
    rng = random.Random(11)
    idxs = rng.sample(range(len(cat)), 250)
    for rules in (9, 11):
        bad_cover = bad_lib = n = 0
        for i in idxs:
            rec = cat.records()[i]
            out = alchemy.classify(rec["atoms"], [tuple(e) for e in rec["edges"]],
                                   rules=rules, library=lib, check_stable=False)
            if not out["ok"]:
                continue
            n += 1
            if not out["in_library"]:
                bad_lib += 1
            if not out["skeleton"]["structure_theorem_ok"]:
                bad_cover += 1
        assert n > 240
        assert bad_lib == 0, f"rules={rules}: {bad_lib}/{n} 条出现库外 6 级块"
        assert bad_cover == 0, f"rules={rules}: {bad_cover}/{n} 条违反结构定理"


def test_catalog_structures_are_rules11_caliber():
    """目录结构是规则 1~11 口径：用 rules=9 重算会"认不出"约 17% 的记录。

    这是"口径不一致"最直接的证据，也说明为什么内核默认 rules=11。
    """
    from alchemy.core.canon import mol_label

    cat = alchemy.get_catalog()
    rng = random.Random(11)
    idxs = rng.sample(range(len(cat)), 200)
    match = {}
    for rules in (9, 11):
        ok = n = 0
        for i in idxs:
            rec = cat.records()[i]
            tr = alchemy.trace(list(rec["atoms"]), rules=rules)
            if tr is None or len(tr["mols"]) != 1:
                continue
            n += 1
            if mol_label(tr["mols"][0]["atoms"], tr["mols"][0]["edges"]) == \
                    mol_label(rec["atoms"], [tuple(e) for e in rec["edges"]]):
                ok += 1
        match[rules] = ok / n
    # 规则 1~11 下目录应 100% 自洽；规则 1~9 下会明显偏低
    assert match[11] > 0.98, match
    assert match[9] < match[11] - 0.05, match


def test_known_sku_sizes():
    """6 级块大小不应超过 13（T5 上界）。"""
    cat = alchemy.get_catalog()
    rng = random.Random(3)
    for i in rng.sample(range(len(cat)), 120):
        rec = cat.records()[i]
        out = alchemy.classify(rec["atoms"], [tuple(e) for e in rec["edges"]],
                               rules=9, check_stable=False)
        if not out["ok"]:
            continue
        for b in out["level6"]["blocks"]:
            assert b["size"] <= 13, (rec["formula"], b["formula"], b["size"])


def test_classify_feed():
    """一锅反应的逐产物分类。"""
    out = alchemy.classify_feed(
        alchemy.vec_to_atoms((3, 0, 0, 0, 1, 0, 0, 2, 1)))
    assert out["ok"] is True
    assert out["summary"]["n_mols"] == 2
    assert set(out["summary"]["formulas"]) == {"O2WA", "OAF"}
    for m in out["mols"]:
        assert m["ok"]
        assert "level6" in m and "layers" in m


def test_classify_record_with_place():
    cat = alchemy.get_catalog()
    out = alchemy.classify_record(cat["OXC"], check_stable=False)
    assert out["ok"]
    assert out["bonds"]
    types = {b["type"] for b in out["bonds"]}
    assert types <= {"S", "C", "L"}
    assert out["source"] is not None or out["source"] is None  # 字段存在


def test_unstable_substance_detected():
    """构造一个不稳定物质：结构 != F(组成)，应被判 stable=False。"""
    # 组成 OOXXC（价数 3+3+2+2+1 = 11 奇数不行），改用 OOXCC
    atoms = ["O", "O", "X", "C", "C"]     # 3+3+2+1+1 = 10
    # 人为给一个"未填满价数"的结构（O 只连一个），它必然不是 F(v)
    edges = [(0, 1, 1), (1, 2, 1), (2, 3, 1), (2, 4, 1)]
    out = alchemy.classify(atoms, edges, check_stable=True)
    assert out["ok"] is True
    assert out["stable"] is False
