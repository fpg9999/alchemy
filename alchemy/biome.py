# -*- coding: utf-8 -*-
"""生物群系：把一次"宇宙爆炸"实验的终态丰度谱，转成游戏用的**物种表**。

## 思路

项目里的碰撞实验（T55~T63）本质上是在模拟一次宇宙爆炸：一堆元素按比例投进空间、
高温退火冷却，最后稳定下来的物质就是这个世界的地基。

    群系 = 元素配比（决定背景物种） + 冷却曲线（决定冻结多少中间态）
    物种表 = 终态丰度谱 × 结构分类 × 性质系数 × 命名
    地图生成 = 用物种表的"丰度/储量"决定生成什么、生成多少

## 一张表里有什么

:func:`abundance_table` 输出每行一个物种（= 一个分子式）：

====================  ==========================================================
``formula``           分子式（物质主键）
``label``             机械标识 `元素中文串·结构`（**不是游戏名**，只是给人看的把手）
``natoms``            原子数 = 游戏里的"体型/占格"
``count``             该世界里有多少个（个体的绝对值）
``abundance``         占分子总数的比例（丰度，决定生成频率）
``reserve_units``     原子储量 = count × natoms（决定矿脉/森林的总量）
``stable``            ``F(组成) == 自身``？不稳定的会按半衰期自分解
``in_catalog``        是否在 84,225 条已验证目录内
``category``          三价骨架种类（no/single/multi_trivalent）
``skeleton_blocks``   6 级骨架块分子式（"器官原型"，38 库）
``layer_counts``      骨架/连接/终端三层原子数
``props``             质量/耐久/强度/柔性/抗性/能量/机动/感知/攻击/接口数
``shape``             结构形状标签（团/环/链/星/孤）——地图上的轮廓
====================  ==========================================================

**没有** ``tier``（生态层）和 ``name``（游戏名）：这两个是**设计决策**，不是数据的必然推论。
需要时显式开启：``abundance_table(run, with_tier=True, with_names=True)``。

## 用法

    >>> import alchemy.biome as B
    >>> run = B.load_result("t62_phaseB_result.json")
    >>> rows = B.abundance_table(run)
    >>> B.to_csv(rows, "data/biomes/t62B.csv")
    >>> print(B.render_markdown(rows, top=12))

## 层次说明

**世界 = 多个群系模板拼接**；每个模板来自一次独立实验（一套元素配比 + 冷却曲线）。
死世界（只有 1~2 种物质）也有价值——可以当沙漠/戈壁的底材；植被丰富的模板当雨林；
过于发散的模板（如 T58，937 种、74.9% 只出现 1 个）通常是没退火干净的动力学噪声，应丢弃。

用 :func:`template_catalogue` 的**描述性指标**挑模板（不做生态归类）：

- ``effective_species``：等效物种数（`exp(Shannon 熵)`），1.0 = 单调世界，20 = 高度发散
- ``dominance`` / ``top2_mass_share``：前 1 / 前 2 名的质量集中度
- ``singleton_fraction``：只出现 1 个的物种占比 → 尾部噪声程度
- ``n_ge5`` / ``max_natoms``：能看出形状的东西有几个、最大多大
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .core import classify as C
from .core.catalog import get_catalog
from .core.elements import ELEM, ORDER, TRI, formula_of, parse_formula, zh_of

__all__ = [
    "TIERS", "ELEM_PROPS", "load_result", "abundance_table", "assign_tier",
    "properties", "systematic_name", "shape_label", "tier_counts",
    "biome_summary", "template_catalogue",
    "to_csv", "to_json", "render_markdown", "load_names", "save_names",
]

# ---------------------------------------------------------------- 生态分层（阈值是设计旋钮）
#: 生态分层阈值。**默认不启用**——这些是"建议值"，不是项目决定。
#: 需要时传 ``abundance_table(..., with_tier=True)``，或参考 ``biome_summary`` 的描述性指标自行决定。
TIERS: dict[str, float] = {
    "terrain": 0.10,        # 丰度 ≥10%  -> 空气 / 地面（世界底色）
    "mineral": 0.01,        # 1%~10%    -> 矿物
    "flora": 0.001,         # 0.1%~1%   -> 植物
    "dust_max_atoms": 4,    # 原子数 ≤4 的稀有物 -> "尘埃/杂质"，不占生态位
    "flora_min_atoms": 5,   # 稀有但 ≥5 原子 -> 植物（够大才看得见）
    "fauna_min_atoms": 7,   # 稀有 + ≥7 原子 + 有骨架 -> 动物（够复杂才算生物）
}

#: T18D 的元素属性系数表：每 1 个原子对 9 项属性的贡献（0~4 分制，游戏内可再乘系数）。
ELEM_PROPS: dict[str, dict[str, int]] = {
    #            质量 耐久 强度 柔性 抗性 能量 机动 感知 攻击
    "O": dict(mass=3, hp=3, strength=1, flex=0, resist=2, energy=0, mobility=0, sense=1, attack=0),
    "X": dict(mass=4, hp=4, strength=2, flex=0, resist=3, energy=0, mobility=0, sense=0, attack=1),
    "C": dict(mass=1, hp=1, strength=0, flex=2, resist=1, energy=2, mobility=1, sense=1, attack=1),
    "P": dict(mass=3, hp=1, strength=4, flex=1, resist=0, energy=2, mobility=1, sense=0, attack=2),
    "W": dict(mass=2, hp=1, strength=1, flex=3, resist=0, energy=1, mobility=3, sense=0, attack=1),
    "L": dict(mass=1, hp=0, strength=1, flex=2, resist=1, energy=3, mobility=1, sense=2, attack=2),
    "K": dict(mass=3, hp=2, strength=2, flex=1, resist=2, energy=1, mobility=1, sense=1, attack=1),
    "A": dict(mass=1, hp=0, strength=0, flex=2, resist=1, energy=0, mobility=2, sense=0, attack=0),
    "F": dict(mass=2, hp=0, strength=1, flex=1, resist=0, energy=2, mobility=0, sense=0, attack=4),
}

_PROP_KEYS = ("mass", "hp", "strength", "flex", "resist", "energy", "mobility", "sense", "attack")


# ---------------------------------------------------------------- 读实验结果
def load_result(path) -> dict:
    """读一次碰撞实验的结果文件（``t*_result.json``），抽出群系与物种丰度。

    返回 ``{"name", "spec", "species", "structures", "new_substances"}``：

    - ``spec``：元素配比、环境尺寸、温度程、分子数/原子数
    - ``species``：[{formula, count, natoms, known29}]，按 count 降序
    - ``structures``：{formula: {atoms, edges}}（实验记录的 top 结构，可能只有前 24 个）
    """
    p = Path(path)
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)

    fc = d.get("final_composition") or {}
    species = []
    for formula, info in fc.items():
        if isinstance(info, dict):
            cnt = int(info.get("count", 0))
            natoms = int(info.get("atoms", 0)) or len(parse_formula(formula))
            known = info.get("known29")
        else:  # 兼容直接存 int 的旧文件
            cnt = int(info)
            natoms = len(parse_formula(formula))
            known = None
        species.append({"formula": formula, "count": cnt,
                        "natoms": natoms, "known29": known})
    species.sort(key=lambda s: -s["count"])

    cfg = d.get("config") or {}
    load = d.get("load_summary") or {}
    summary = d.get("summary") or {}
    total_mol = sum(s["count"] for s in species) or summary.get("final_N") or 1

    spec = {
        "source": str(p),
        "name": p.stem.replace("_result", ""),
        "phase": d.get("phase") or d.get("stage"),
        "element_atoms": load.get("element_atoms"),
        "element_shares": load.get("element_shares"),
        "valence_shares": load.get("valence_shares"),
        "L": cfg.get("L"),
        "T0": cfg.get("T0"),
        "T_end": cfg.get("T_end"),
        "minutes": cfg.get("minutes"),
        "max_reaction_atoms": cfg.get("max_reaction_atoms"),
        "n_molecules": total_mol,
        "n_atoms": summary.get("final_atoms") or sum(s["count"] * s["natoms"] for s in species),
        "n_species": len(species),
    }

    structures = {}
    for formula, st in (d.get("final_top_structures") or {}).items():
        if isinstance(st, dict) and st.get("atoms"):
            structures[formula] = {"atoms": st["atoms"], "edges": st.get("edges", [])}

    return {"name": spec["name"], "spec": spec, "species": species,
            "structures": structures,
            "new_substances": d.get("new_substances") or {}}


# ---------------------------------------------------------------- 结构 / 性质
def _structure_of(formula, run, catalog):
    """取物种的结构：优先实验记录的实际结构，其次 84,225 目录。"""
    st = run.get("structures", {}).get(formula)
    if st:
        return list(st["atoms"]), [tuple(e) for e in st["edges"]], "experiment"
    rec = catalog.get(formula) if catalog is not None else None
    if rec:
        return list(rec["atoms"]), [tuple(e) for e in rec["edges"]], "catalog"
    return None, None, None


def shape_label(classification) -> str:
    """结构形状标签：团 / 星 / 环 / 链 / 孤核 —— 地图上的轮廓。

    优先看**三价骨架**（骨架才是"器官原型"），骨架太小（<3 原子）时退回看整分子拓扑，
    否则像 ``OXC`` 这种 3 原子小分子会被标成"孤核"，读起来很怪。

    判定顺序：
    - **团**：有 4 原子以上的骨架块（完全图/稠集团）
    - **星**：3 价原子连 3 个方向且骨架 ≥4 原子（枢纽）
    - **环**：整分子含环
    - **链**：其余（含 2~3 原子的双原子盐/小分子）
    - **孤核**：单原子，或既无骨架又无环且只有 2 个原子以下
    """
    if not classification or not classification.get("ok"):
        return "?"
    blocks = classification["level6"]["blocks"]
    comps = classification["skeleton"]["components"]
    natoms = classification.get("natoms") or 0
    cyclic = bool(classification.get("_cyclic"))
    degrees = classification.get("_skeleton_degrees") or []

    if any(b["size"] >= 4 for b in blocks):
        return "团"
    if degrees and max(degrees) >= 3 and max((c["size"] for c in comps), default=0) >= 4:
        return "星"
    if cyclic:
        return "环"
    max_comp = max((c["size"] for c in comps), default=0)
    if max_comp >= 3 or natoms >= 3:
        return "链"
    if natoms <= 1:
        return "孤核"
    return "链"


def properties(atoms, edges, classification=None) -> dict:
    """按 T18D 的系数表算 9 项属性 + 能力槽。

    这些是**可调的**基础值：元素贡献 + 结构加成，游戏内再乘自己的平衡系数。
    """
    atoms = list(atoms)
    edges = [tuple(e) for e in edges]
    prop = {k: 0 for k in _PROP_KEYS}
    for e in atoms:
        for k in _PROP_KEYS:
            prop[k] += ELEM_PROPS[e][k]

    n_tri = sum(1 for a in atoms if a in TRI)
    n_multibond = sum(1 for (_, _, m) in edges if m >= 2)
    extra_mult = sum(max(0, m - 1) for (_, _, m) in edges)

    # 结构加成
    n_blocks = n_fusion = n_true_bridge = n_hinge = n_soft = n_rigid = 0
    n_ring = 0
    cyc = len(edges) - len(atoms) + 1   # 连通分子的圈数（cyclomatic number）
    if cyc > 0:
        n_ring = cyc
    if classification and classification.get("ok"):
        n_blocks = len(classification["level6"]["blocks"])
        n_fusion = classification["skeleton"]["n_fusion_bonds"]
        for dv in classification["divalent"]:
            if dv["role"] == "真桥(跨块)":
                n_true_bridge += 1
            elif dv["role"] == "骨架内桥":
                n_rigid += 1
        for b in classification.get("bonds", []):
            if b["type"] == "C":
                n_hinge += 1
            elif b["type"] == "L":
                n_soft += 1

    prop["hp"] = 10 * prop["hp"] + 20 * n_blocks + 15 * n_fusion + 30 * n_true_bridge
    prop["strength"] += 2 * n_tri + 5 * n_multibond
    prop["flex"] += 3 * n_hinge + 2 * n_soft
    prop["resist"] += 2 * n_ring + 3 * n_rigid
    prop["mobility"] += 3 * n_hinge + 2 * n_soft - 1 * n_rigid
    # 环/团 加成
    if n_ring:
        prop["hp"] = prop["hp"] * 1.2
        prop["resist"] += 2
    if any(b["size"] >= 4 for b in (classification or {}).get("level6", {}).get("blocks", [])):
        prop["hp"] = prop["hp"] * 1.3
        prop["strength"] += 2

    caps = [c["element"] for c in (classification or {}).get("caps", [])]
    n_f, n_l, n_c = caps.count("F"), caps.count("L"), caps.count("C")
    prop["energy"] += 2 * (n_f + n_l)
    prop["sense"] += 2 * n_l
    prop["attack"] += 3 * n_f + 2 * n_c

    for k in _PROP_KEYS:
        prop[k] = round(prop[k], 1)

    # 接口数（能力槽的**分析侧**代理）：真实分子的自由价恒为 0，所以不能用"自由 stub"。
    # 这里数"可替换的接口"：端帽（可换武器/传感器）+ 真桥（可换连接方式）。
    # 数值越大 = 越模块化，越容易改造；T18D 的原始公式是**设计侧**的（从骨架块搭分子时用）。
    prop["slots"] = len(caps) + n_true_bridge
    prop["interfaces"] = prop["slots"]
    prop["ring_count"] = n_ring
    prop["multibond"] = n_multibond
    prop["extra_mult"] = extra_mult
    return prop


# ---------------------------------------------------------------- 命名
def systematic_name(formula, classification=None, props=None) -> str:
    """系统名：`元素中文串 + 结构后缀`，稳定、唯一、可机器生成。

    例：``OXC`` -> ``秩晶冰·链``；``O3P`` -> ``秩3势·团``；``OXCPWKA`` -> ``秩晶冰势流沌气·环``。
    """
    base = zh_of(_atoms_of(formula))
    if props and props.get("ring_count", 0) >= 3:
        return f"{base}·稠环"
    shape = shape_label(classification) if classification is not None else "?"
    return f"{base}·{shape}"


def _atoms_of(formula):
    out = []
    for e, c in zip(ORDER, parse_formula(formula)):
        out += [e] * c
    return out


def load_names(path=None) -> dict:
    """读策划名覆盖表：``{"OXC": "秩晶冰", ...}``。"""
    if path is None:
        p = Path(__file__).resolve().parent / "data" / "biome_names.json"
    else:
        p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_names(names: dict, path=None) -> Path:
    """写策划名覆盖表。"""
    p = Path(path) if path else Path(__file__).resolve().parent / "data" / "biome_names.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(names, fh, ensure_ascii=False, indent=1)
    return p


# ---------------------------------------------------------------- 分层
def assign_tier(abundance: float, natoms: int, stable=None, tiers=None,
                has_skeleton: bool = False) -> str:
    """按丰度 + 体型 + 骨架给生态层。

    ``terrain`` 空气/地面 · ``mineral`` 矿物 · ``flora`` 植物 · ``fauna`` 动物 · ``dust`` 尘埃

    规则（可在 ``TIERS`` 里改）：
    1. 丰度 ≥ 10% → terrain（世界底色）
    2. 1%~10% → mineral
    3. 0.1%~1% → flora（够常见，哪怕是 2 原子的小分子也先当"植被层"）
    4. 更稀有（<0.1%）才按体型细分：
       ≤4 原子 → dust（太小的东西当不了生物）；≥7 原子且有骨架 → fauna；其余 ≥5 → flora

    为什么不用 ``stable`` 分层：完全退火的世界里所有幸存物种都是稳定的（``F(v)=自身``），
    这个标志在退火实验里恒为真。它只在**部分退火**的世界（如 T58）里才有区分度，
    那时"亚稳 = 会自分解 = 有寿命"，适合当树/动物。
    """
    t = dict(TIERS)
    if tiers:
        t.update(tiers)
    if abundance >= t["terrain"]:
        return "terrain"
    if abundance >= t["mineral"]:
        return "mineral"
    if abundance >= t["flora"]:
        return "flora"
    if natoms <= t["dust_max_atoms"]:
        return "dust"
    if natoms >= t["fauna_min_atoms"] and has_skeleton:
        return "fauna"
    if natoms >= t["flora_min_atoms"]:
        return "flora"
    return "dust"


def tier_counts(rows) -> dict:
    """各生态层物种数统计（只在 ``with_tier=True`` 生成的表上有意义）。"""
    out: dict[str, int] = {}
    for r in rows:
        if r.get("tier"):
            out[r["tier"]] = out.get(r["tier"], 0) + 1
    return out


# ---------------------------------------------------------------- 主入口
def abundance_table(run: dict, *, rules: int = 11, min_count: int = 1,
                    with_tier: bool = False, tiers=None,
                    with_names: bool = False, names=None,
                    catalog=None, library=None,
                    with_props: bool = True) -> list[dict]:
    """生成物种表（每行一个物种），按丰度降序。

    **默认不做生态归类、也不填游戏名**——这两件事是设计决策，不是数据的必然推论。
    表只给"客观量"（丰度、储量、结构、属性）+ 一个机械标识 ``label``。

    参数
    ----
    run         : :func:`load_result` 的返回值
    rules       : 用哪个规则版本复算结构分类（默认 11）
    min_count   : 少于这个个体数的物种直接丢掉（控制表的行数）
    with_tier   : 是否附带**建议**生态层（默认关闭；见 ``TIERS``）
    tiers       : 覆盖 ``TIERS`` 阈值
    with_names  : 是否用 ``biome_names.json`` 里的名字替换 ``label``（默认关闭）
    names       : 策划名覆盖表（``{formula: 名字}``）
    catalog     : 预加载的目录（省略则按需加载）
    with_props  : 是否计算 9 项属性（关掉更快）
    """
    from .core import classify as Cmod

    if library is None:
        library = Cmod.load_library()
    if catalog is None:
        catalog = get_catalog()
    if with_names and names is None:
        names = load_names()

    total_mol = sum(s["count"] for s in run["species"]) or 1
    total_atoms = sum(s["count"] * s["natoms"] for s in run["species"]) or 1

    rows = []
    for s in run["species"]:
        formula, count, natoms = s["formula"], s["count"], s["natoms"]
        if count < min_count:
            continue
        abundance = count / total_mol
        atoms, edges, src = _structure_of(formula, run, catalog)
        cls = None
        if atoms is not None:
            cls = Cmod.classify(atoms, edges, rules=rules, library=library,
                                check_stable=True)
            if not cls.get("ok"):
                cls = None
        stable = cls.get("stable") if cls else None
        if cls:
            # 供 shape_label 用的内部字段
            deg = {}
            for (i, j, m) in edges:
                deg[i] = deg.get(i, 0) + m
                deg[j] = deg.get(j, 0) + m
            tri_deg = [deg.get(i, 0) for i, a in enumerate(atoms) if a in TRI]
            cls["_skeleton_degrees"] = tri_deg
            cls["_cyclic"] = (len(edges) - len(atoms) + 1) > 0

        props = properties(atoms, edges, cls) if (atoms is not None and with_props) else None
        label = systematic_name(formula, cls, props)

        row = {
            "formula": formula,
            "label": label,
            "natoms": natoms,
            "count": count,
            "abundance": round(abundance, 6),
            "atom_abundance": round(count * natoms / total_atoms, 6),
            "reserve_units": count * natoms,
            "stable": stable,
            "in_catalog": formula in catalog,
            "structure_source": src,
            "category": cls["category"] if cls else None,
            "in_library": cls["in_library"] if cls else None,
            "skeleton_blocks": [b["formula"] for b in cls["level6"]["blocks"]] if cls else [],
            "level6_sizes": [b["size"] for b in cls["level6"]["blocks"]] if cls else [],
            "shape": shape_label(cls) if cls else "?",
            "layer_counts": (
                {"skeleton": len(cls["layers"]["skeleton"]),
                 "bridge": len(cls["layers"]["bridge"]),
                 "cap": len(cls["layers"]["cap"])} if cls else None
            ),
            "divalent_roles": cls["divalent_roles"] if cls else None,
            "props": {k: props[k] for k in (*_PROP_KEYS, "slots")} if props else None,
            "attrs": ({"ring_count": props["ring_count"], "multibond": props["multibond"]}
                      if props else None),
        }
        if with_names and names:
            row["name"] = names.get(formula) or label
        if with_tier:
            has_skeleton = bool(cls) and any(b["size"] >= 2 for b in cls["level6"]["blocks"])
            row["tier"] = assign_tier(abundance, natoms, stable, tiers,
                                      has_skeleton=has_skeleton)
        rows.append(row)

    rows.sort(key=lambda r: -r["count"])
    return rows


def biome_summary(run: dict, rows=None, **table_kw) -> dict:
    """一个群系模板的**描述性指标**（不做生态归类，只描述"这个世界的形状"）。

    这些指标用来判断"这个模板适合当什么地貌"：

    - ``dominance``：第 1 名占的**质量份额**（越大越单调；1.0 = 只有一种物质）
    - ``top2_mass_share`` / ``top5_mass_share``：前 2 / 前 5 名的质量份额
    - ``effective_species``：``exp(Shannon 熵)``，即"等效物种数"（不受长尾虚增影响）
    - ``singleton_fraction``：只出现 1 个的物种占比 → 尾部噪声程度
    - ``rare_fraction``：丰度 < 0.1% 的物种占比
    - ``n_ge5``：≥5 原子的物种数（"能看出形状"的东西有几个）
    - ``max_natoms`` / ``mean_natoms``：体形范围
    """
    import math

    if rows is None:
        rows = abundance_table(run, **table_kw)
    n = len(rows)
    if n == 0:
        return {"name": run.get("name")}
    total_atoms = sum(r["reserve_units"] for r in rows) or 1
    mass = sorted((r["atom_abundance"] for r in rows), reverse=True)
    # 用分子丰度算 Shannon 熵
    h = 0.0
    for r in rows:
        p = r["abundance"]
        if p > 0:
            h -= p * math.log(p)
    return {
        "name": run["name"],
        "source": run["spec"]["source"],
        "ratio": run["spec"].get("element_shares"),
        "L": run["spec"].get("L"),
        "T0": run["spec"].get("T0"),
        "minutes": run["spec"].get("minutes"),
        "n_species": n,
        "n_molecules": sum(r["count"] for r in rows),
        "n_atoms": total_atoms,
        "max_natoms": max(r["natoms"] for r in rows),
        "mean_natoms": round(sum(r["count"] * r["natoms"] for r in rows)
                             / max(1, sum(r["count"] for r in rows)), 2),
        "n_ge5": sum(1 for r in rows if r["natoms"] >= 5),
        "dominance": round(mass[0], 4),
        "top1": rows[0]["formula"],
        "top2_mass_share": round(sum(mass[:2]), 4),
        "top5_mass_share": round(sum(mass[:5]), 4),
        "shannon_bits": round(h, 3),
        "effective_species": round(math.exp(h), 1),
        "singleton_fraction": round(sum(1 for r in rows if r["count"] == 1) / n, 3),
        "rare_fraction": round(sum(1 for r in rows if r["abundance"] < 0.001) / n, 3),
    }


def template_catalogue(paths, **table_kw) -> list[dict]:
    """把多个实验模板汇总成一张对照表（用来挑"哪些模板要、哪些要丢"）。

    返回每个模板一行的 ``biome_summary``，按 ``effective_species`` 升序
    （从"单调世界"到"发散世界"）。
    """
    out = []
    for p in paths:
        try:
            run = load_result(p)
            out.append(biome_summary(run, **table_kw))
        except Exception as exc:  # 缺文件/格式不符时不让整批失败
            out.append({"source": str(p), "error": str(exc)})
    out.sort(key=lambda s: s.get("effective_species", 1e9))
    return out


# ---------------------------------------------------------------- 导出
def to_csv(rows, path) -> Path:
    """写 CSV（嵌套字段压成 JSON 字符串，方便 Excel 打开）。

    列按表里实际存在的字段生成：没开 ``with_names`` / ``with_tier`` 时不会多出空列。
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    base = ["formula", "label"]
    optional = ["name", "tier"]
    rest = ["natoms", "count", "abundance", "atom_abundance", "reserve_units",
            "stable", "in_catalog", "category", "in_library", "shape",
            "skeleton_blocks", "structure_source", "divalent_roles", "props", "attrs"]
    present = set()
    for r in rows:
        present |= set(r)
    fields = base + [k for k in optional if k in present] + rest
    with open(p, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            out = dict(r)
            for k in ("skeleton_blocks", "divalent_roles", "props", "attrs"):
                if out.get(k) is not None:
                    out[k] = json.dumps(out[k], ensure_ascii=False)
            w.writerow(out)
    return p


def to_json(rows, path, spec=None) -> Path:
    """写 JSON（完整字段 + 群系元信息）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"spec": spec, "n_species": len(rows), "species": rows}
    tc = tier_counts(rows)
    if tc:
        payload["tier_counts"] = tc
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    return p


def render_markdown(rows, top: int = 20, title: str = "") -> str:
    """渲染成 Markdown 表格（给人看 / 贴进文档）。有 ``name``/``tier`` 时才出对应列。"""
    has_name = bool(rows) and "name" in rows[0]
    has_tier = bool(rows) and "tier" in rows[0]
    lines = []
    if title:
        lines.append(f"### {title}\n")
    head = "| # | 分子式 |" + (" 名字 |" if has_name else "") + \
           (" 层 |" if has_tier else "") + \
           " 原子 | 个体数 | 丰度 | 质量份额 | 储量 | 稳定 | 形状 | 骨架块 | 攻/耐 |"
    lines.append(head)
    lines.append("|--:|---|" + ("---|" if has_name else "") + ("---|" if has_tier else "") +
                 "--:|--:|--:|--:|--:|:--:|---|---|---|")
    for i, r in enumerate(rows[:top], 1):
        props = r.get("props") or {}
        st = "稳" if r["stable"] else ("亚稳" if r["stable"] is False else "?")
        cells = [f"{i}", f"`{r['formula']}`"]
        if has_name:
            cells.append(r.get("name") or r.get("label") or "")
        if has_tier:
            cells.append(r.get("tier") or "")
        cells += [f"{r['natoms']}", f"{r['count']:,}", f"{r['abundance']:.3%}",
                  f"{r['atom_abundance']:.3%}", f"{r['reserve_units']:,}", st,
                  r["shape"], "+".join(r["skeleton_blocks"]) or "—",
                  f"{props.get('attack', '—')}/{props.get('hp', '—')}"]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    return "\n".join(lines)
