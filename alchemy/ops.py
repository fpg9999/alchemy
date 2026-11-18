# -*- coding: utf-8 -*-
"""物质操作层 v5：把 9 元素能力重定义为可计算、可联动的 9 种操作（动词）。

## 口径（2026-11-19，T77，见 ``intake/ability_spec.md``）

v3/v4 的能力值是 ``Σ 元素个数 × 价数``（静态量）；v5 改为**功能位形计数**：
同一元素处在骨架节点 / 桥位 / 端帽位，操作强度不同；同一分子式、不同结构，能力谱不同。

| 主方向 | 操作（key, 中文, 载体, 动词） | 阈值（全目录 p33/p67） |
|---|---|---|
| 聚 poly | sup 支撑 O 撑 / rig 刚性 X 锁 / adh 粘合 C 黏 | 1.15/2.66 · 0.48/1.28 · 1.20/2.40 |
| 散 scatter | dif 分化 K 分 / ads 吸附 A 捕 / clv 切割 F 断 | 1.13/2.30 · 0.92/2.10 · 1.30/2.60 |
| 动 move | sto 储能 P 蓄 / mov 移动 W 移 / sig 信号 L 传 | 1.50/2.62 · 1.25/2.75 · 1.25/2.25 |

- :func:`op_scores` → 9 项数值 + 三主方向合计；:func:`op_profile` → 含低/中/高与主方向；
- :func:`op_features` → 结构特征（位形计数 / 键型适配率），是 9 项值的中间量；
- :func:`assembly_ops` / :func:`organ_modules` → 用 :data:`LINKAGE` 矩阵把多分子能力合成为
  组装体能力与六种类器官模块（骨/壳、基质、膜、重组/愈合、消化腺、肌/马达、神经原基）；
- 生命特征不用标量"生命度"：由 :func:`assembly_ops` 返回的 ``features`` 给出 §7 的 6 条耦合谓词。

## 与 v3/v4 的关系

所有旧接口（``ability.scores/profile/abilities_of`` …）原样保留；本模块只新增。
v5 数值尺度与 v4 不同（v5 支撑 = 位形计数，v4 支撑 = 3×O），**禁止把 v5 值塞进 v4 阈值**。
纯公式字符串输入无法还原结构位形，退化为 v4 计数近似并在返回值里标 ``"degraded": True``。

## 用法

    >>> import alchemy.ops as OP
    >>> rec = get_catalog().get("OXC")
    >>> OP.op_scores(rec)["ops"]["sup"]
    0.575
    >>> OP.op_profile(rec)["ops"][0]["tier"]
    '低'
    >>> OP.linkage("sup", "rig")
    (1.5, '协', '框架+刚性杆=承重骨架；无锁的框架会塌，无锁的骨架无处安装')

## 公式（§2，逐项写清；位形权重 0.3~1.0，主位形 1.0）

```
sup = Σ_O (1.0 if τ≥2 else 0.5) × (1 + 0.15·share_O(S))
rig = Σ_X (1.0 if role∈{bridge,intra} 且含 S 焊桥 else 0.4) × (1 + 0.2·share_X(S))
adh = Σ_C (1.0 if 邻接三价 else 0.3) × (1 + 0.2·单键率_C)
dif = Σ_K (1.0 if τ≥2 else 0.5) × (1 + 0.2·share_K(L))
ads = Σ_A (1.0 if role∈{bridge,free} 或邻接 MONO else 0.4) × (1 + 0.2·share_A(L))
clv = Σ_F (1.0 if end(i) else 0.4) × (1 + 0.3·单键率_F)
sto = Σ_P (1.0 if τ≥2 else 0.5) × (1 + 0.5·mult(P))
mov = Σ_W (1.0 if role∈{bridge,arm} else 0.3) × (1 + 0.25·share_W(C))
sig = Σ_L (1.0 if role∈{bridge,arm} 或邻接三价 else 0.4) × (1 + 0.25·share_L(S|C))
```
"""

from __future__ import annotations

from .ability import sub_tier
from .core.elements import (
    DIV, MONO, TRI, VAL, classify_offset, formula_of, parse_formula,
)

__all__ = [
    "MATERIAL_OPS", "OP_KEYS", "OP_TH", "OP_TIERS", "OP_NAME", "OP_ELEMENT",
    "OP_MAIN", "OP_OF_ELEMENT", "CLAUSE", "FEATURE_NAMES", "MODULE_NAMES",
    "op_tier", "op_features", "op_scores", "op_profile", "material_abilities_of",
    "LINKAGE", "linkage", "assembly_ops", "organ_modules",
]

# ---------------------------------------------------------------- 常量表
#: 9 项操作：(key, 中文, 载体元素, 动词, 主方向)。顺序即能力向量维度顺序。
MATERIAL_OPS: tuple[tuple[str, str, str, str, str], ...] = (
    ("sup", "支撑", "O", "撑", "poly"),
    ("rig", "刚性", "X", "锁", "poly"),
    ("adh", "粘合", "C", "黏", "poly"),
    ("dif", "分化", "K", "分", "scatter"),
    ("ads", "吸附", "A", "捕", "scatter"),
    ("clv", "切割", "F", "断", "scatter"),
    ("sto", "储能", "P", "蓄", "move"),
    ("mov", "移动", "W", "移", "move"),
    ("sig", "信号", "L", "传", "move"),
)

OP_KEYS: tuple[str, ...] = tuple(k for k, _, _, _, _ in MATERIAL_OPS)
OP_NAME: dict[str, str] = {k: name for k, name, _, _, _ in MATERIAL_OPS}
OP_ELEMENT: dict[str, str] = {k: e for k, _, e, _, _ in MATERIAL_OPS}
OP_MAIN: dict[str, str] = {k: m for k, _, _, _, m in MATERIAL_OPS}
OP_OF_ELEMENT: dict[str, str] = {e: k for k, _, e, _, _ in MATERIAL_OPS}
MAIN_LABEL: dict[str, str] = {"poly": "聚", "scatter": "散", "move": "动"}

#: 全目录非零样本 p33 / p67 阈值（§5.2）。0 与"无该元素"归低。
OP_TH: dict[str, tuple[float, float]] = {
    "sup": (1.15, 2.66),
    "rig": (0.48, 1.28),
    "adh": (1.20, 2.40),
    "dif": (1.13, 2.30),
    "ads": (0.92, 2.10),
    "clv": (1.30, 2.60),
    "sto": (1.50, 2.62),
    "mov": (1.25, 2.75),
    "sig": (1.25, 2.25),
}

OP_TIERS: tuple[str, ...] = ("低", "中", "高")

#: §7 六条生命特征谓词的英文键（中文名）。
FEATURE_NAMES: dict[str, str] = {
    "metabolism": "代谢",
    "motion": "运动",
    "sensing": "感知-响应",
    "feeding": "摄食/吸收",
    "division": "分化/分工",
    "repair": "修复/复制",
}

#: §3.2 六个涌现模块 + §3.1 中其余 Λ≥1.2 的协同对（扩展命名）。
MODULE_NAMES: dict[frozenset, str] = {
    frozenset(("sup", "rig")): "骨/壳",
    frozenset(("sup", "adh")): "基质/膜",
    frozenset(("adh", "clv")): "重组/愈合",
    frozenset(("ads", "clv")): "消化腺",
    frozenset(("sto", "mov")): "肌/马达",
    frozenset(("dif", "sig")): "神经原基",
    frozenset(("rig", "adh")): "复合骨板",
    frozenset(("adh", "dif")): "附着芽",
    frozenset(("dif", "clv")): "再生芽",
    frozenset(("clv", "sto")): "代谢回路",
}

# ---------------------------------------------------------------- 阈值 / 三阶
def op_tier(value: float, th=None) -> str:
    """三阶判定：``<= t1`` 低、``<= t2`` 中、否则高；0 归低。

    ``th`` 可为 ``(t1, t2)`` 元组、操作 key 字符串（查 :data:`OP_TH`），或 ``None``
    （无阈值信息时只区分零 / 非零：0 → 低，>0 → 高）。内部复用
    :func:`alchemy.ability.sub_tier`，保证与 v4 三档语义一致。
    """
    if th is None:
        th = (0.0, 0.0)
    elif isinstance(th, str):
        th = OP_TH[th]
    if value <= 0:
        return "低"
    return sub_tier(value, th)


# ---------------------------------------------------------------- 结构特征
def _normalize_mol(mol):
    """输入规范化：``(atoms, edges, place_dict|None, formula)``。

    ``edges`` 为 ``[[i, j, 键级], ...]``；``place`` 为 ``{原子下标: (q, r)}``。
    结构信息不完整（无 edges / 无 place / 公式字符串）时 place 返回 None，走退化路径。
    """
    if isinstance(mol, str):
        atoms = [e for e, c in zip(
            ("O", "X", "C", "P", "W", "L", "K", "A", "F"), parse_formula(mol)) for _ in range(c)
        ]
        return atoms, None, None, mol
    if not isinstance(mol, dict):
        raise TypeError(f"op_* 需要 molecule dict 或分子式字符串，得到 {type(mol).__name__}")
    atoms = list(mol.get("atoms") or [])
    if not atoms:
        raise ValueError("molecule 缺少 atoms")
    edges = [tuple(e) for e in (mol.get("edges") or [])]
    place = mol.get("place")
    formula = mol.get("formula") or formula_of(atoms)
    if not edges or not place:
        return atoms, edges or None, None, formula
    try:
        pl = {int(k): (int(v[0]), int(v[1])) for k, v in place.items()}
    except (TypeError, ValueError, IndexError):
        return atoms, edges, None, formula
    if len(pl) != len(atoms):
        return atoms, edges, None, formula
    return atoms, edges, pl, formula


def _degraded_features(atoms) -> dict[str, float]:
    """公式退化：用 v4 计数近似（价数 × 元素个数），标 ``degraded=1.0``。"""
    cnt: dict[str, int] = {}
    for e in atoms:
        cnt[e] = cnt.get(e, 0) + 1
    out: dict[str, float] = {}
    for key, name, elem, _verb, _main in MATERIAL_OPS:
        v = float(VAL[elem] * cnt.get(elem, 0))
        out[f"{key}_main"] = v
        out[f"{key}_adapt"] = 0.0
    out["degraded"] = 1.0
    return out


def op_features(mol) -> dict[str, float]:
    """9 项操作的**结构特征**（位形计数 + 键型适配因子），是 9 项能力值的中间量。

    返回 ``{"<key>_main": 位形权重和, "<key>_adapt": 键型适配率, "degraded": 0/1}``。
    最终值 = ``main × (1 + adapt)``（见 :func:`op_scores`）。位形权重取 0.3~1.0，
    主位形 1.0；``share_e(K)`` 为 e 原子所连键中键型 ∈ K 的比例，``mult(e)`` 为
    e 原子所连键中键级 ≥2 的比例，``end(i)`` 为度为 1。
    """
    atoms, edges, place, _formula = _normalize_mol(mol)
    if edges is None or place is None:
        return _degraded_features(atoms)

    n = len(atoms)
    adj: list[list[tuple[int, int, str]]] = [[] for _ in range(n)]
    deg = [0] * n
    for (i, j, m) in edges:
        if not (0 <= i < n and 0 <= j < n):
            continue
        delta = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        bt = classify_offset(delta) or "C"      # 坐标异常兜底，不影响计数
        adj[i].append((j, int(m), bt))
        adj[j].append((i, int(m), bt))
        deg[i] += 1
        deg[j] += 1

    is_tri = [atoms[i] in TRI for i in range(n)]

    # --- 三价连通块（骨架）及二价/一价原子的附着关系
    tri_comp = [-1] * n
    n_comp = 0
    for s in range(n):
        if not is_tri[s] or tri_comp[s] != -1:
            continue
        tri_comp[s] = n_comp
        stack = [s]
        while stack:
            u = stack.pop()
            for v, _m, _t in adj[u]:
                if is_tri[v] and tri_comp[v] == -1:
                    tri_comp[v] = n_comp
                    stack.append(v)
        n_comp += 1

    # 二价原子按连通簇归并（角色判定以"二价簇"为单位；一价端帽不计入簇，
    # 与 ability_spec 的 struct_probe 一致：MONO 是终端，不参与 bridge/intra/arm 划分）
    is_div = [atoms[i] in DIV for i in range(n)]
    div_comp = [-1] * n
    cluster_touch: list[set[int]] = []      # 该簇附着的骨架块集合
    cluster_in_edges: list[int] = []        # 该簇进入骨架的键数
    cluster_welded: list[bool] = []         # 该簇的入口键中是否含 S 焊桥
    cid = 0
    for s in range(n):
        if not is_div[s] or div_comp[s] != -1:
            continue
        div_comp[s] = cid
        stack = [s]
        touch: set[int] = set()
        in_edges = 0
        welded_c = False
        while stack:
            u = stack.pop()
            for v, _m, t in adj[u]:
                if is_tri[v]:
                    touch.add(tri_comp[v])
                    in_edges += 1
                    if t == "S":
                        welded_c = True
                elif is_div[v] and div_comp[v] == -1:
                    div_comp[v] = cid
                    stack.append(v)
        cluster_touch.append(touch)
        cluster_in_edges.append(in_edges)
        cluster_welded.append(welded_c)
        cid += 1

    role: list[str] = ["free"] * n
    welded: list[bool] = [False] * n
    for i in range(n):
        if not is_div[i]:
            continue
        c = div_comp[i]
        k = len(cluster_touch[c])
        if k >= 2:
            role[i] = "bridge"
        elif k == 1 and cluster_in_edges[c] >= 2:
            role[i] = "intra"
        elif k == 1:
            role[i] = "arm"
        else:
            role[i] = "free"
        # "含 S 焊桥"取簇级判定（入口键里有 S 即算焊接）
        welded[i] = cluster_welded[c]

    tau = [sum(1 for v, _m, _t in adj[i] if is_tri[v]) for i in range(n)]
    adjacent_tri = [any(is_tri[v] for v, _m, _t in adj[i]) for i in range(n)]
    adjacent_mono = [any(atoms[v] in MONO for v, _m, _t in adj[i]) for i in range(n)]
    end = [deg[i] == 1 for i in range(n)]

    # --- 元素级统计
    def share(e: str, kinds: set[str]) -> float:
        num = den = 0
        for i in range(n):
            if atoms[i] != e:
                continue
            for _v, _m, t in adj[i]:
                den += 1
                if t in kinds:
                    num += 1
        return num / den if den else 0.0

    def single_rate(e: str) -> float:
        num = den = 0
        for i in range(n):
            if atoms[i] != e:
                continue
            for _v, m, _t in adj[i]:
                den += 1
                if m == 1:
                    num += 1
        return num / den if den else 0.0

    def mult_rate(e: str) -> float:
        num = den = 0
        for i in range(n):
            if atoms[i] != e:
                continue
            for _v, m, _t in adj[i]:
                den += 1
                if m >= 2:
                    num += 1
        return num / den if den else 0.0

    # 每项：位形权重和 + 适配率
    main: dict[str, float] = {}
    adapt: dict[str, float] = {}

    def acc(key: str, elem: str, weight, adapt_coef: float, adapt_rate: float) -> None:
        tot = 0.0
        for i in range(n):
            if atoms[i] == elem:
                tot += weight(i)
        main[key] = tot
        adapt[key] = adapt_coef * adapt_rate

    acc("sup", "O", lambda i: 1.0 if tau[i] >= 2 else 0.5, 0.15, share("O", {"S"}))
    acc("rig", "X",
        lambda i: 1.0 if (role[i] in ("bridge", "intra") and welded[i]) else 0.4,
        0.2, share("X", {"S"}))
    acc("adh", "C", lambda i: 1.0 if adjacent_tri[i] else 0.3, 0.2, single_rate("C"))
    acc("dif", "K", lambda i: 1.0 if tau[i] >= 2 else 0.5, 0.2, share("K", {"L"}))
    acc("ads", "A",
        lambda i: 1.0 if (role[i] in ("bridge", "free") or adjacent_mono[i]) else 0.4,
        0.2, share("A", {"L"}))
    acc("clv", "F", lambda i: 1.0 if end[i] else 0.4, 0.3, single_rate("F"))
    acc("sto", "P", lambda i: 1.0 if tau[i] >= 2 else 0.5, 0.5, mult_rate("P"))
    acc("mov", "W", lambda i: 1.0 if role[i] in ("bridge", "arm") else 0.3,
        0.25, share("W", {"C"}))
    acc("sig", "L",
        lambda i: 1.0 if (role[i] in ("bridge", "arm") or adjacent_tri[i]) else 0.4,
        0.25, share("L", {"S", "C"}))

    out: dict[str, float] = {}
    for key in OP_KEYS:
        out[f"{key}_main"] = round(main[key], 6)
        out[f"{key}_adapt"] = round(adapt[key], 6)
    out["degraded"] = 0.0
    return out


# ---------------------------------------------------------------- 能力值 / 档位
def _scores_from_features(feats: dict[str, float], formula: str, degraded: bool) -> dict:
    ops = {key: round(feats[f"{key}_main"] * (1.0 + feats[f"{key}_adapt"]), 4)
           for key in OP_KEYS}
    out = {
        "formula": formula,
        "ops": ops,
        # 三主方向合计（与 v3 的 poly/scatter/move 对齐，便于替换旧接口）
        "poly": round(ops["sup"] + ops["rig"] + ops["adh"], 4),
        "scatter": round(ops["dif"] + ops["ads"] + ops["clv"], 4),
        "move": round(ops["sto"] + ops["mov"] + ops["sig"], 4),
        "degraded": bool(degraded),
    }
    return out


def op_scores(mol_or_formula, weights=None) -> dict:
    """9 项操作值 + 三主方向合计。

    参数 ``mol_or_formula`` 为目录记录 / molecule dict（``atoms/edges/place``）或分子式字符串。
    分子式无法还原结构位形，退化为 v4 计数近似并标 ``"degraded": True``；
    ``weights`` 仅在该退化路径有意义（元素权重替换），结构模式下被忽略。
    """
    atoms, edges, place, formula = _normalize_mol(mol_or_formula)
    if edges is None or place is None:
        if weights:
            ops = {key: round(float(weights.get(OP_ELEMENT[key], VAL[OP_ELEMENT[key]]))
                              * atoms.count(OP_ELEMENT[key]), 4) for key in OP_KEYS}
            out = {
                "formula": formula,
                "ops": ops,
                "poly": round(ops["sup"] + ops["rig"] + ops["adh"], 4),
                "scatter": round(ops["dif"] + ops["ads"] + ops["clv"], 4),
                "move": round(ops["sto"] + ops["mov"] + ops["sig"], 4),
                "degraded": True,
            }
            return out
        feats = _degraded_features(atoms)
        return _scores_from_features(feats, formula, True)
    feats = op_features({"atoms": atoms, "edges": edges, "place": place, "formula": formula})
    return _scores_from_features(feats, formula, False)


def op_profile(mol_or_formula) -> dict:
    """9 项操作的完整档位：``{"ops": [{key, name, value, tier, main, main_label}...]}``。"""
    sc = op_scores(mol_or_formula)
    rows = []
    for key, name, elem, _verb, main in MATERIAL_OPS:
        v = sc["ops"][key]
        rows.append({
            "key": key, "name": name, "element": elem,
            "value": v, "tier": op_tier(v, OP_TH[key]),
            "main": main, "main_label": MAIN_LABEL[main],
        })
    return {"formula": sc["formula"], "ops": rows, "degraded": sc["degraded"]}


def material_abilities_of(mol_or_formula) -> list[dict]:
    """与 :func:`alchemy.ability.abilities_of` 同形的扁平列表，便于直接替换旧接口。"""
    p = op_profile(mol_or_formula)
    return [{**row, "main": row["main"], "main_label": row["main_label"]} for row in p["ops"]]


# ---------------------------------------------------------------- 联动矩阵
_RAW_LINKAGE: tuple[tuple[str, str, float, str, str], ...] = (
    ("sup", "rig", 1.5, "协", "框架+刚性杆=承重骨架；无锁的框架会塌，无锁的骨架无处安装"),
    ("sup", "adh", 1.2, "协", "骨架+胶结=块体/基质；黏需要撑提供连续被黏面"),
    ("sup", "dif", 1.1, "补", "框架给出分化位点；分化需要撑提供可长出的母体"),
    ("sup", "ads", 0.7, "中", "支撑面顺带提供捕获面，但撑不主动捕获"),
    ("sup", "clv", 0.3, "拮", "框架抵抗断裂；断键破坏框架，两者互毁"),
    ("sup", "sto", 0.6, "中", "框架只能容纳储能单元，不参与蓄能"),
    ("sup", "mov", 0.3, "拮", "固定框架限制位移；移动需要松开框架"),
    ("sup", "sig", 0.8, "中", "刚性骨架可作传导体（骨传导），但需连续键路"),
    ("rig", "adh", 1.3, "协", "刚性件+胶=复合骨板/外骨骼"),
    ("rig", "dif", 0.9, "补", "刚性节点可作为分化锚点（分叉必须锚在硬点上）"),
    ("rig", "ads", 0.6, "中", "刚性表面可附着捕获物，但不主动伸出"),
    ("rig", "clv", 0.2, "拮", "刚性抗切割；切割加工刚性材料效率极低"),
    ("rig", "sto", 0.5, "竞", "刚性结构容纳重键储能会应力集中，互相不利"),
    ("rig", "mov", 0.3, "拮", "锁死关节就没有位移"),
    ("rig", "sig", 0.7, "中", "刚性介质传导振动，但绝缘（无 L 则无效）"),
    ("adh", "dif", 1.2, "协", "黏合面分化出接口/芽（黏住的地方长出器官）"),
    ("adh", "ads", 1.1, "补", "黏附+捕获=附着捕食（触手）"),
    ("adh", "clv", 1.4, "协", "断后黏合=重组/焊接/愈合（代谢与修复的核心）"),
    ("adh", "sto", 0.6, "中", "胶层可封装储能单元，但不贡献能量"),
    ("adh", "mov", 0.5, "竞", "黏着与滑移互斥（黏住就难动）"),
    ("adh", "sig", 0.8, "中", "接触面可传扰动（触觉），但传不远"),
    ("dif", "ads", 1.1, "补", "分化出捕获器官（触手/绒毛）"),
    ("dif", "clv", 1.2, "协", "分化+切割=再生/修补（断口处长新芽）"),
    ("dif", "sto", 0.9, "补", "分化出储能单元（脂肪/电池器官）"),
    ("dif", "mov", 1.0, "补", "分化出运动器官（足/鞭毛）"),
    ("dif", "sig", 1.3, "协", "分化出感受器/神经（器官分工的信息侧）"),
    ("ads", "clv", 1.0, "补", "捕获+切割=消化（抓住再切开）"),
    ("ads", "sto", 0.7, "中", "捕获物可暂存，但不转化为能量"),
    ("ads", "mov", 1.1, "补", "趋化捕食（边动边抓）"),
    ("ads", "sig", 1.0, "补", "捕获信号/受体响应"),
    ("clv", "sto", 1.3, "协", "断键释能=代谢（能量从键里放出来）"),
    ("clv", "mov", 0.3, "拮", "切割破坏运动结构（自断其足）"),
    ("clv", "sig", 0.5, "竞", "断裂中断传导路径"),
    ("sto", "mov", 1.5, "协", "能量→位移=马达/肌肉"),
    ("sto", "sig", 1.0, "补", "能量→电信号（动作电位）"),
    ("mov", "sig", 1.5, "协", "运动+信号=反射弧/趋化（感知-运动闭环）"),
)

#: 联动矩阵 Λ：``{(op_i, op_j): (系数, 类型, 物理理由)}``，对称、对角 0、只存 i<j。
LINKAGE: dict[tuple[str, str], tuple[float, str, str]] = {
    (a, b): (c, typ, why) for a, b, c, typ, why in _RAW_LINKAGE
}


def _norm_op(name: str) -> str:
    """操作别名归一：key / 中文名 / 载体元素 → key。"""
    if name in OP_KEYS:
        return name
    for k, cn in OP_NAME.items():
        if name == cn:
            return k
    if name in OP_OF_ELEMENT:
        return OP_OF_ELEMENT[name]
    raise KeyError(f"未知操作：{name!r}（可用 key={OP_KEYS}、中文名或载体元素）")


def linkage(a: str, b: str) -> tuple[float, str, str]:
    """两项操作的联动系数 / 类型 / 物理理由（自动归一参数顺序）。"""
    ka, kb = _norm_op(a), _norm_op(b)
    if ka == kb:
        return (0.0, "—", "同一操作不对自身做联动耦合（对角项由实现补 1.0）")
    if (ka, kb) in LINKAGE:
        return LINKAGE[(ka, kb)]
    return LINKAGE[(kb, ka)]


# ---------------------------------------------------------------- 组装体合成
def _member_ops(member) -> dict[str, float]:
    """成员能力向量：接受 molecule dict / op_scores 结果 / {ops:{...}}。"""
    if isinstance(member, dict):
        ops = member.get("ops")
        if isinstance(ops, dict) and all(k in ops for k in OP_KEYS):
            return {k: float(ops[k]) for k in OP_KEYS}
    return op_scores(member)["ops"]


def _modules_from(member_vectors: list[dict[str, float]], S: dict[str, float]) -> list[dict]:
    """§3.2 / §3.3：Λ≥1.2 的协同操作对 → 候选模块（含成员数与操作覆盖数）。"""
    mods: list[dict] = []
    for i in range(len(OP_KEYS)):
        for j in range(i + 1, len(OP_KEYS)):
            ki, kj = OP_KEYS[i], OP_KEYS[j]
            coef = linkage(ki, kj)[0]
            if coef < 1.2 or S[ki] <= 0 or S[kj] <= 0:
                continue
            contributors = [v for v in member_vectors if v[ki] > 0 or v[kj] > 0]
            covered = [k for k in OP_KEYS if sum(v[k] for v in contributors) > 0]
            # 互补模块：模块之外还有 Λ≥0.9 的操作出现在组装体里
            complementary = any(
                linkage(ki, k)[0] >= 0.9 or linkage(kj, k)[0] >= 0.9
                for k in OP_KEYS if k not in (ki, kj) and S[k] > 0
            )
            mods.append({
                "ops": [ki, kj],
                "name": MODULE_NAMES.get(frozenset((ki, kj)), "组合模块"),
                "coef": coef,
                "type": linkage(ki, kj)[1],
                "members": len(contributors),
                "ops_covered": len(covered),
                "complementary": complementary,
                # §3.3：模块含 ≥3 项操作且成员 ≥3 → 升格为类器官
                "organ_candidate": len(contributors) >= 3 and len(covered) >= 3,
            })
    mods.sort(key=lambda m: (-m["coef"], m["ops"]))
    return mods


def organ_modules(members: list[dict]) -> list[dict]:
    """多分子组装体的**六类模块候选**（骨/壳、基质/膜、重组/愈合、消化腺、肌/马达、神经原基…）。

    成员可以是目录记录 / molecule dict / ``op_scores`` 结果；模块判定按 §3.3：
    ``Λ_ij ≥ 1.2`` 的协同操作对，且记录成员数、操作覆盖数、是否满足类器官升格条件。
    """
    vecs = [_member_ops(m) for m in members]
    S = {k: sum(v[k] for v in vecs) for k in OP_KEYS}
    return _modules_from(vecs, S)


def assembly_ops(members: list[dict]) -> dict:
    """组装体能力合成（§3.3）+ §7 六条生命特征谓词。

    ```
    S_i = Σ_m v_i^(m)                # 原始总量
    q_j = S_j / (max_k S_k + 1e-9)   # 相对丰度
    β_i = 1 + Σ_{j≠i} Λ_ij · q_j     # 耦合增益（只放大已出现的操作）
    A_i = S_i · β_i                  # 组装体能力（涌现后）
    ```

    返回 ``{"n","raw","gain","ops","modules","features","features_zh","coverage"}``。
    ``features`` 是 §7 的 6 条布尔谓词（代谢/运动/感知-响应/摄食/分化/修复），
    **不含任何标量"生命度"**。
    """
    members = list(members)
    vecs = [_member_ops(m) for m in members]
    n = len(vecs)
    S = {k: round(sum(v[k] for v in vecs), 4) for k in OP_KEYS}
    mx = max(S.values()) if S else 0.0
    q = {k: (S[k] / (mx + 1e-9)) for k in OP_KEYS}
    beta: dict[str, float] = {}
    for ki in OP_KEYS:
        g = 1.0
        for kj in OP_KEYS:
            if kj == ki:
                continue
            g += linkage(ki, kj)[0] * q[kj]
        beta[ki] = g
    A = {k: round(S[k] * beta[k], 4) for k in OP_KEYS}
    gain = {k: round(A[k] - S[k], 4) for k in OP_KEYS}
    mods = _modules_from(vecs, S)
    covered = [k for k in OP_KEYS if S[k] > 0]

    def tier_at_least_mid(key: str) -> bool:
        """人均能力 ≥ 中档（组装体规模补偿：按成员数平均后再比阈值）。"""
        if n == 0:
            return False
        return op_tier(A[key] / n, OP_TH[key]) in ("中", "高")

    lam = lambda a, b: linkage(a, b)[0]  # noqa: E731
    features = {
        # 1 代谢：蓄×断 协同 ≥1.3 且两种操作都出现
        "metabolism": lam("sto", "clv") >= 1.3 and A["sto"] > 0 and A["clv"] > 0,
        # 2 运动：蓄×移 ≥1.5 且 移 人均 ≥ 中档
        "motion": lam("sto", "mov") >= 1.5 and tier_at_least_mid("mov"),
        # 3 感知-响应：移×传 ≥1.5 或 捕×传 ≥1.0，且 传 人均 ≥ 中档
        "sensing": (lam("mov", "sig") >= 1.5 or lam("ads", "sig") >= 1.0)
        and tier_at_least_mid("sig"),
        # 4 摄食/吸收：捕×断 ≥1.0 且两种操作都出现
        "feeding": lam("ads", "clv") >= 1.0 and A["ads"] > 0 and A["clv"] > 0,
        # 5 分化/分工：分×传 ≥1.3 且至少 2 个不同模块
        "division": lam("dif", "sig") >= 1.3 and len(mods) >= 2,
        # 6 修复/复制：黏×断 ≥1.4 且 分×断 ≥1.2
        "repair": lam("adh", "clv") >= 1.4 and lam("dif", "clv") >= 1.2,
    }
    return {
        "n": n,
        "raw": S,
        "gain": gain,
        "ops": A,
        "modules": mods,
        "features": features,
        "features_zh": {FEATURE_NAMES[k]: v for k, v in features.items()},
        "coverage": len(covered),
    }
