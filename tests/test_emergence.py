# -*- coding: utf-8 -*-
"""emergence.py：涌现原型（L1 分子 → L2 组装体 → L3 器官 → L4 判据）单元测试。

全部用 30~60 分子的 smoke 仿真，不跑完整 6000×1200（见 examples/emergence_demo.py）。
"""

import json
import subprocess
import sys
from pathlib import Path

import _util  # noqa: F401  # sys.path 引导

from alchemy import emergence as E

REPO = Path(__file__).resolve().parents[1]


def _small_params(**over):
    """小世界参数：40 分子、L=40、10~30 步，保证测试秒级完成。"""
    P = E.default_params()
    P.update({"N": 40, "L": 40, "steps": 10, "T_obs": 6, "t_warm": 3,
              "tau_asm": 3, "tau_org": 6, "tau_sys": 8})
    P.update(over)
    return P


def _small_world(seed=5, n=40, steps=8, **over):
    P = _small_params(steps=steps, **over)
    records = E.sample_records(n, seed + 100)
    world, reports = E.run_world(records, seed, P)
    return world, reports, P


# ---------------------------------------------------------------------------
# 参数与矩阵（§3.4 / §7.4）
# ---------------------------------------------------------------------------

def test_params_json_roundtrip():
    path = REPO / "alchemy" / "data" / "emergence_params.json"
    assert path.is_file(), "缺少 alchemy/data/emergence_params.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    P = E.load_params()
    for key in ("N", "L", "steps", "T_obs", "kappa0", "M_MIN", "W_MIN",
                "E_min", "c_min", "k_on0", "k_off0", "beta", "p_move"):
        assert key in raw
        assert abs(float(P[key]) - float(raw[key])) < 1e-12
    # 矩阵不写进 JSON（由 LINKAGE 派生）
    for key in ("M", "M_eff", "M_dir", "K", "psi"):
        assert key not in raw
    assert P["M"] and P["M_eff"] and P["M_dir"]


def test_matrices_shape_symmetry_and_repulsion():
    M, M_eff, M_dir = E.build_matrices()
    n = 9
    for mat in (M, M_eff, M_dir):
        assert len(mat) == n
        assert all(len(row) == n for row in mat)
    # 对角为正（同类自聚）
    for i in range(n):
        assert M[i][i] >= 0.9
    # M_eff 必须对称；M_dir 保留有向先验
    for i in range(n):
        for j in range(n):
            assert abs(M_eff[i][j] - M_eff[j][i]) < 1e-9
            assert -1.0 <= M[i][j] <= 1.6
    assert any(abs(M_dir[i][j] - M_dir[j][i]) > 0.01
               for i in range(n) for j in range(n))
    # 排斥语义：存在负的非对角项（Λ<0.6 的对被映射为负）
    assert any(M[i][j] < 0 for i in range(n) for j in range(n) if i != j)
    # 所有值都应是有限数
    for mat in (M, M_eff, M_dir):
        for row in mat:
            for v in row:
                assert v == v and abs(v) < 10.0


# ---------------------------------------------------------------------------
# L1：位点提取 / 分子实例化
# ---------------------------------------------------------------------------

def test_extract_sites_range_and_kinds():
    P = E.default_params()
    records = E.sample_records(40, 3)
    n_with_sites = 0
    total = 0
    for rec in records:
        sites = E.extract_sites(rec, P)
        assert len(sites) <= P["max_sites"]
        for site in sites:
            assert site.kind in ("cap", "hull", "bridge")
            assert 0.0 < site.sigma <= 1.0 + 1e-9
            assert site.bond_type in ("S", "C", "L")
            assert site.ability in E.OPS.OP_KEYS
            assert site.element in set("OXCPWLKAF")
        n_with_sites += 1 if sites else 0
        total += len(sites)
    assert n_with_sites >= 20, f"位点覆盖过低：{n_with_sites}/40"
    assert total >= 40


def test_make_molecule_fields():
    P = E.default_params()
    rec = E.sample_records(1, 11)[0]
    mol = E.make_molecule(rec, 7, P)
    assert mol.uid == 7
    assert mol.formula == rec["formula"]
    assert len(mol.atoms) == rec["natoms"]
    assert mol.energy == P["energy_init"]
    assert 0 <= mol.max_contacts <= P["max_sites"]
    # cells 在 init_world 放置时才填充；make_molecule 阶段只有局域 footprint
    assert isinstance(mol.local_cells, list) and mol.local_cells
    assert isinstance(mol.site_counts, dict)
    assert sum(mol.site_counts.values()) == len(mol.sites)
    # 放置后应有世界格坐标
    world = E.init_world([rec], __import__("random").Random(0), P)
    placed = next(iter(world.molecules.values()))
    assert isinstance(placed.cells, list) and placed.cells
    assert placed.body_cells and len(placed.body_cells) == len(placed.local_cells)
    assert placed.cells and len(placed.cells) == len(placed.local_cells)
    # 位点 σ = tier_score(0.35/0.70/1.00) × exposure(1.0/0.55/0.70) × affinity(1.0)
    allowed = {round(t * ex, 9)
               for t in (0.35, 0.70, 1.00) for ex in (1.0, 0.55, 0.70)}
    for site in mol.sites:
        assert any(abs(site.sigma - a) < 1e-9 for a in allowed), site.sigma


# ---------------------------------------------------------------------------
# L2：界面能 / 动力学
# ---------------------------------------------------------------------------

def test_p_on_p_off_monotonic():
    P = E.default_params()
    assert E.p_on(0.0, P) < E.p_on(0.5, P) < E.p_on(2.0, P)
    assert 0.0 < E.p_on(0.5, P) < 1.0
    # p_off 随剪切增大；同 w 下剪切越大越易断
    assert E.p_off(0.5, 2.0, P) > E.p_off(0.5, 0.0, P)
    assert 0.0 < E.p_off(0.5, 0.5, P) < 1.0
    # 极弱键 w<W_MIN 时 p_on 很小（k_on0·e^{-β·W0} ≈ 3%）
    assert E.p_on(0.01, P) < 0.05


def test_interface_energy_and_candidates():
    P = E.default_params()
    world = E.init_world(E.sample_records(30, 4), __import__("random").Random(1), P)
    mols = list(world.molecules.values())
    pairs = [(i, j) for i in range(len(mols)) for j in range(i + 1, len(mols))
             if mols[i].sites and mols[j].sites]
    assert pairs, "样例世界缺少带位点的分子对"
    i, j = pairs[0]
    w = E.interface_energy(mols[i], mols[j], mols[i].sites[0], mols[j].sites[0], world.env, P)
    assert -1.5 <= w <= 2.5 + 1e-9
    cand = E.candidate_sites(mols[i], mols[j], P)
    assert isinstance(cand, list)
    assert len(cand) <= 8


def test_classify_shape_six_kinds():
    def bond(a, b):
        return E.InterfaceBond(a=a, b=b, site_a=0, site_b=0, w=0.5,
                               pair=(0, 0), born=0)

    cells = {0: [(0, 0)], 1: [(1, 0)], 2: [(2, 0)], 3: [(3, 0)]}
    # 4 分子链（3 条边，beta0=0，直径 3）
    chain = [bond(0, 1), bond(1, 2), bond(2, 3)]
    assert E.classify_shape([0, 1, 2, 3], chain, cells) == "链"
    # 单分子 / 两个分子
    assert E.classify_shape([0], [], {0: [(0, 0)]}) == "簇"
    assert E.classify_shape([0, 1], [bond(0, 1)], cells) == "簇"
    # 结果永远是六类之一
    kinds = set(E.SHAPE_NAMES) if hasattr(E, "SHAPE_NAMES") else None
    for mols, bonds in (([0, 1, 2, 3], chain), ([0, 1], [bond(0, 1)]), ([0], [])):
        shape = E.classify_shape(mols, bonds, cells)
        if kinds:
            assert shape in kinds
        else:  # pragma: no cover
            assert shape in ("壳", "骨架网络", "膜", "链", "簇", "团")


# ---------------------------------------------------------------------------
# L3/L4：器官与生命判据（只读性质 A0）
# ---------------------------------------------------------------------------

def test_life_report_is_pure_read():
    world, reports, P = _small_world(seed=5, n=40, steps=12)
    digest_before = E._world_digest(world)
    out = E.life_report_all(world)
    digest_after = E._world_digest(world)
    assert digest_before == digest_after, "life_report 不得修改世界状态（A0）"
    assert isinstance(out, list)
    for rep in out:
        assert rep.tier in E.TIERS
        assert set(rep.criteria) == {"B", "M", "R", "I", "H", "A"}
    # run_world 返回的 reports 与 life_report_all 一致（同一只读观测）
    assert len(reports) == len(out)
    assert [r.criteria for r in reports] == [r.criteria for r in out]


def test_tier_from_criteria_maps_four_tiers():
    world, reports, P = _small_world(seed=7, n=40, steps=8)
    reps = E.life_report_all(world)
    if reps:
        for rep in reps:
            assert E.tier_from_criteria(rep, world) == rep.tier
    else:
        # 没有器官系统时，人造报告落到"无机晶体"
        rep = E.LifeReport(sid=0, tier="无机晶体",
                           criteria={k: False for k in ("B", "M", "R", "I", "H", "A")},
                           values={}, window=(0, 0))
        assert E.tier_from_criteria(rep, world) == E.TIERS[0]


def test_project_blocks_and_legacy_score():
    world, reports, P = _small_world(seed=9, n=30, steps=6)
    blocks = E.project_blocks(world)
    assert len(blocks) == len(world.molecules)
    for blk in blocks:
        assert set(blk) >= {"uid", "formula", "pos", "rot", "cells", "natoms", "sites"}
    score = E.legacy_life_score(world)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 端到端：可复现 / 实验输出结构
# ---------------------------------------------------------------------------

def test_same_seed_is_bit_reproducible():
    P = _small_params(steps=8)
    records = E.sample_records(30, 13)
    w1, _ = E.run_world(records, 21, P)
    w2, _ = E.run_world(records, 21, P)
    assert E._world_digest(w1) == E._world_digest(w2)
    # 不同 seed 应不同
    w3, _ = E.run_world(records, 22, P)
    assert E._world_digest(w1) != E._world_digest(w3)


def test_run_experiment_keys_and_ranges():
    P = _small_params(steps=10)
    records = E.sample_records(30, 17)
    out = E.run_experiment(records, 3, P)
    for key in ("params", "seed", "t", "molecules", "dropped", "assemblies",
                "asm_size", "assembly_rate", "organs", "organs_per_asm",
                "organ_kind_share", "organ_kinds_hist", "systems", "rates",
                "tiers", "reports", "assemblies_detail", "energy_mean",
                "bond_count", "elapsed_s", "digest", "provenance", "novelty"):
        assert key in out, f"run_experiment 缺少键 {key}"
    assert out["seed"] == 3
    assert out["t"] == P["steps"]
    assert 0.0 <= out["assembly_rate"] <= 100.0
    assert set(out["tiers"]) == set(E.TIERS)
    assert sum(out["tiers"].values()) == len(out["reports"])
    assert set(out["rates"]) == {"B", "M", "R", "I", "H", "A"}
    assert len(out["digest"]) == 64
    # JSON 可序列化（demo 会写文件）
    json.dumps(out, ensure_ascii=False)


def test_sample_records_stratified_and_valid():
    records = E.sample_records(50, 2)
    assert len(records) == 50
    assert len({r["formula"] for r in records}) >= 45
    for rec in records:
        assert 4 <= rec["natoms"] <= 30
        assert rec.get("place"), "抽样应丢弃 place 缺失的记录"
        assert rec["edges"], "记录必须带键"


def test_cli_help():
    env = dict(__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"
    res = subprocess.run([sys.executable, "-m", "alchemy.emergence", "--help"],
                         cwd=str(REPO), capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=env, timeout=120)
    assert res.returncode == 0, res.stderr
    assert "--sample" in res.stdout
    assert "--steps" in res.stdout
