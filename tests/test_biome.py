# -*- coding: utf-8 -*-
"""生物群系物种表：默认只输出客观量（丰度/储量/结构/属性），不做生态归类。"""

import _util

import alchemy
import alchemy.biome as B


def test_load_result_t62b():
    run = B.load_result(_util.REPO / "t62_phaseB_result.json")
    assert run["spec"]["n_species"] == 43
    assert len(run["species"]) == 43
    counts = [s["count"] for s in run["species"]]
    assert counts == sorted(counts, reverse=True)
    shares = run["spec"]["element_shares"]
    assert len(shares) == 9
    assert all(0.10 < v < 0.12 for v in shares.values())


def test_abundance_table_t62b():
    run = B.load_result(_util.REPO / "t62_phaseB_result.json")
    rows = B.abundance_table(run)
    assert len(rows) == 43
    assert abs(sum(r["abundance"] for r in rows) - 1.0) < 1e-4
    assert {rows[0]["formula"], rows[1]["formula"]} == {"OXCPWKA", "LF"}
    assert rows[0]["abundance"] > 0.4


def test_default_has_no_role_or_game_name():
    """默认不归类、不命名——这是设计决策，不是数据的必然推论。"""
    run = B.load_result(_util.REPO / "t62_phaseB_result.json")
    rows = B.abundance_table(run)
    for r in rows:
        assert "tier" not in r, "默认不应输出生态层"
        assert "name" not in r, "默认不应输出游戏名"
        assert r["label"]                      # 只有机械标识


def test_table_fields_complete():
    run = B.load_result(_util.REPO / "t62_phaseB_result.json")
    rows = B.abundance_table(run)
    required = {"formula", "label", "natoms", "count", "abundance", "atom_abundance",
                "reserve_units", "stable", "in_catalog", "category",
                "in_library", "shape", "skeleton_blocks", "layer_counts",
                "divalent_roles", "props", "attrs"}
    for r in rows:
        assert required <= set(r), required - set(r)
    top = rows[0]
    assert top["props"]["hp"] > 0
    assert top["shape"] in {"环", "团", "链", "星", "孤核", "稠环", "?"}


def test_opt_in_tier_and_names():
    run = B.load_result(_util.REPO / "t62_phaseB_result.json")
    rows = B.abundance_table(run, with_tier=True, with_names=True)
    assert all("tier" in r for r in rows)
    assert all(r["tier"] in {"terrain", "mineral", "flora", "fauna", "dust"} for r in rows)
    by_f = {r["formula"]: r for r in rows}
    assert by_f["OXCPWKA"]["name"] == "九素环"
    # 未覆盖的物种回退到 label
    assert by_f["LF"]["name"] == "雷火晶"


def test_systematic_label():
    mol = alchemy.simulate(["O", "X", "C"])[0]
    cls = alchemy.classify(mol["atoms"], mol["edges"])
    label = B.systematic_name("OXC", cls)
    assert label.startswith("秩晶冰·")


def test_biome_summary():
    run = B.load_result(_util.REPO / "t62_phaseB_result.json")
    s = B.biome_summary(run)
    # 等摩尔双组分 -> 高度集中
    assert s["dominance"] > 0.5
    assert s["top2_mass_share"] > 0.9
    assert s["n_species"] == 43
    assert 1 <= s["effective_species"] <= s["n_species"]
    assert 0 <= s["singleton_fraction"] <= 1
    assert s["max_natoms"] >= 7


def test_template_catalogue_orders_by_diversity():
    paths = [_util.REPO / "t57_area_result.json",      # 死世界
             _util.REPO / "t62_phaseB_result.json",    # 标准世界
             _util.REPO / "t58_result.json"]           # 发散世界
    cat = B.template_catalogue(paths)
    assert len(cat) == 3
    names = [c["name"] for c in cat]
    assert names[0] == "t57_area"          # 最单调
    assert names[-1] == "t58"              # 最发散
    eff = [c["effective_species"] for c in cat]
    assert eff == sorted(eff)
    # T58 的等效物种数远高于另外两个
    assert cat[-1]["effective_species"] > 10 * cat[0]["effective_species"]


def test_export_roundtrip():
    import json
    import tempfile
    from pathlib import Path

    run = B.load_result(_util.REPO / "t63_phase4_result.json")
    rows = B.abundance_table(run)
    d = Path(tempfile.mkdtemp())
    csv_path = B.to_csv(rows, d / "t.csv")
    json_path = B.to_json(rows, d / "t.json", spec=run["spec"])
    assert csv_path.exists() and json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["n_species"] == len(rows)
    assert "tier_counts" not in payload      # 没开归类就不该有这一节
    header = csv_path.read_text(encoding="utf-8-sig").splitlines()[0]
    assert header.startswith("formula,label,")
    assert "tier" not in header and "name" not in header


def test_biomes_differ():
    """不同配比 -> 不同的地表物种集合（这就是"群系"的含义）。"""
    a = B.load_result(_util.REPO / "t62_phaseB_result.json")
    b = B.load_result(_util.REPO / "t57_area_result.json")
    ta = {r["formula"] for r in B.abundance_table(a)[:2]}
    tb = {r["formula"] for r in B.abundance_table(b)[:2]}
    assert ta and tb
    assert ta != tb
