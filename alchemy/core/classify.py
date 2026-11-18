# -*- coding: utf-8 -*-
"""骨架分类（skeleton classification）。

把任意分子拆成三层结构，并判定它是否落在已验证的骨架库里：

    骨架层（三价 O/P/K）  ← 6 级中间态骨架块（38 形态库）+ 0 级同类键融合
    连接层（二价 X/W/A）  ← 桥 / 链段 / 支臂 / 端帽双键 / 二聚 / 小环 …
    终端层（一价 C/L/F）  ← 端帽

## 核心定理（T17 / T18，84,225 条目录全部验证过）

三价–三价键只可能出现在两个"级数"：

- **6 级**：两个**不同**的三价元素（周期表距离 6，最先成键）；
- **0 级**：**同一种**三价元素（周期表距离 0，最后成键）。

因此骨架严格两阶段形成：

1. 6 级结束 → 得到若干**骨架块**，必属于 38 形态库，且**只由元素计数决定**（内禀属性）；
2. 0 级 → 同类三价键只能做两件事：**块内加固**、**块间融合**。

推论：**终态三价骨架 = 该物质自身 6 级骨架块 + 0 级融合/加固**，不需要二价桥参与。
本模块的 ``structure_theorem_ok`` 就是在复核这条推论。

## 库

- **38 形态库**：6 级结束时的三价骨架形态，含 3 个单原子 + 35 个多原子形态，
  来自 ``data/forms38.json``（仓库根 ``t8_forms.json`` 的副本）。
- **7×3 单三价库**：单一三价元素的 7 种模块（单原子/单键二聚/双键二聚/三键二聚/
  三元链/三元环(全单)/三元环(含一条双键)），按元素 O/P/K 各一套，共 21 种。
  单元素类型的块在比较时统一按 O 标号（与项目历史口径一致）。

> 注意：早先用的 ``wl_key`` 不是同构不变量，会造成"库外"假阳性。本模块一律用
> :func:`alchemy.core.canon.mol_label`。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from . import reactor
from .canon import mol_label
from .elements import (
    DIV, MONO, ORDER, TRI, VAL, classify_offset, formula_of, ptable_dist, zh_of,
)

__all__ = [
    "SINGLE_TEMPLATES", "load_library", "block_label", "classify_block",
    "classify", "classify_feed", "classify_record",
]

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: 单三价 7 种模块模板：(原子数, 键表)。见 ``docs/T8_TRIVALENT_FORMS.md``。
SINGLE_TEMPLATES: list[tuple[int, list[tuple[int, int, int]]]] = [
    (1, []),
    (2, [(0, 1, 1)]),
    (2, [(0, 1, 2)]),
    (2, [(0, 1, 3)]),
    (3, [(0, 1, 1), (1, 2, 1)]),
    (3, [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    (3, [(0, 1, 2), (1, 2, 1), (0, 2, 1)]),
]

_LIB_CACHE: dict[str, dict] = {}


def block_label(atoms, edges) -> str:
    """骨架块的规范形。单元素类型的块统一记为 O（与历史口径一致）。"""
    atoms = list(atoms)
    if len(set(atoms)) == 1:
        atoms = ["O"] * len(atoms)
    return mol_label(atoms, [tuple(e) for e in edges])


def load_library(path=None) -> dict:
    """加载骨架库。返回 ``{"multi": {...}, "single": {...}, "forms": [...], ...}``。

    ``multi``  : 规范形 -> 形态分子式（35 个多三价形态）
    ``single`` : 规范形 -> 模块原子数（7 个单三价模块；按元素通用）
    """
    p = Path(path) if path is not None else _DATA_DIR / "forms38.json"
    key = str(p)
    if key in _LIB_CACHE:
        return _LIB_CACHE[key]
    if not p.exists():
        raise FileNotFoundError(f"找不到骨架库数据文件：{p}")
    with open(p, encoding="utf-8") as fh:
        forms = json.load(fh)

    multi: dict[str, str] = {}
    single: dict[str, int] = {}
    for f in forms:
        atoms = list(f["atoms"])
        edges = [tuple(e) for e in f["edges"]]
        if len(atoms) > 1:
            multi[block_label(atoms, edges)] = f["formula"]
    for n, es in SINGLE_TEMPLATES:
        single[block_label(["O"] * n, es)] = n
    lib = {
        "multi": multi,
        "single": single,
        "forms": forms,
        "n_forms": len(forms),
        "n_multi": len(forms) - sum(1 for f in forms if len(f["atoms"]) == 1),
        "n_single_templates": len(SINGLE_TEMPLATES),
        "path": str(p),
    }
    _LIB_CACHE[key] = lib
    return lib


def classify_block(atoms, edges, library: dict) -> dict:
    """判定一个骨架块属于 38 库（multi）/ 7×3 库（single）/ 库外（BAD）。"""
    types = set(atoms) & TRI
    label = block_label(atoms, edges)
    if len(types) >= 2:
        kind = "multi" if label in library["multi"] else "bad"
        lib_formula = library["multi"].get(label)
    elif len(types) == 1:
        kind = "single" if label in library["single"] else "bad"
        lib_formula = None
    else:
        kind = "no_trivalent"
        lib_formula = None
    return {"kind": kind, "in_library": kind in ("multi", "single", "no_trivalent"),
            "library_formula": lib_formula, "label": label}


# ---------------------------------------------------------------- 内部工具
def _trivalent_blocks(level6_blocks) -> list[dict]:
    """把 reactor 的 level6 块过滤成三价诱导子图（骨架块）。

    6 级封口时所有键都是三价-三价，因此这一步通常是无操作；保留是为了对任意来源
    的块列表都稳健。
    """
    out = []
    for ats, es, mem in level6_blocks:
        keep = [k for k, e in enumerate(ats) if e in TRI]
        if not keep:
            continue
        remap = {k: new for new, k in enumerate(keep)}
        sub_atoms = [ats[k] for k in keep]
        sub_edges = [(remap[a], remap[b], m) for (a, b, m) in es if a in remap and b in remap]
        out.append({"atoms": sub_atoms, "edges": sub_edges,
                    "members": tuple(mem[k] for k in keep)})
    return out


def _induced_components(atoms, edges, subset: frozenset) -> list[dict]:
    """某类元素（三价/二价/一价）诱导子图的连通块。"""
    n = len(atoms)
    keep = [i for i in range(n) if atoms[i] in subset]
    keep_set = set(keep)
    adj = {i: [] for i in keep}
    for (a, b, m) in edges:
        if a in keep_set and b in keep_set:
            adj[a].append((b, m))
            adj[b].append((a, m))
    seen = set()
    comps = []
    for s in keep:
        if s in seen:
            continue
        seen.add(s)
        st = [s]
        mem = [s]
        while st:
            u = st.pop()
            for v, _ in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
                    mem.append(v)
        mem.sort()
        remap = {v: k for k, v in enumerate(mem)}
        es = []
        for a in mem:
            for b, m in adj[a]:
                if b in remap and a < b:
                    es.append((remap[a], remap[b], m))
        comps.append({"members": tuple(mem), "atoms": [atoms[v] for v in mem], "edges": es})
    return comps


def _divalent_roles(atoms, edges, triv_comp_of: dict[int, int]) -> list[dict]:
    """二价原子（X/W/A）的存在形式。

    口径与 ``t20_divalent_stats.py`` 一致：
    - 只有 1 个邻居：``同一{T|O|W}原子 x{键级}``
    - 恰好 2 个邻居且两端都是三价（不同原子）：跨块 -> ``真桥(跨块)``；同块 -> ``骨架内桥``
    - 其余 2 邻居：邻居类别组合，如 ``T+O``、``T+W``、``W+W``
    - 3+ 邻居：``多邻居``
    """
    n = len(atoms)
    inc: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for (i, j, m) in edges:
        inc[i].append((j, m))
        inc[j].append((i, m))

    def cls_of(v):
        if atoms[v] in TRI:
            return "T"
        if atoms[v] in MONO:
            return "O"
        return "W"

    out = []
    for i in range(n):
        if atoms[i] not in DIV:
            continue
        neigh = inc[i]
        cls = [cls_of(j) for j, _ in neigh]
        if len(neigh) == 1:
            role = f"同一{cls[0]}原子 x{neigh[0][1]}"
        elif len(neigh) == 2 and cls[0] == "T" and cls[1] == "T" and neigh[0][0] != neigh[1][0]:
            same = triv_comp_of.get(neigh[0][0]) == triv_comp_of.get(neigh[1][0])
            role = "骨架内桥" if same else "真桥(跨块)"
        elif len(neigh) == 2:
            role = "+".join(sorted(cls))
        else:
            role = "多邻居"
        out.append({"index": i, "element": atoms[i], "role": role,
                    "degree": len(neigh), "neighbor_classes": cls,
                    "bonds": [(j, m) for j, m in neigh]})
    return out


def _stable(atoms, edges, rules: int) -> bool:
    """是否为"稳定物质"：``F(组成) == {自身}``（一步自分解不动点）。"""
    tr = reactor.trace(atoms, rules=rules)
    if tr is None or len(tr["mols"]) != 1:
        return False
    m = tr["mols"][0]
    return mol_label(m["atoms"], m["edges"]) == mol_label(atoms, edges)


# ---------------------------------------------------------------- 主入口
def classify(atoms, edges, rules: int = 11, library: dict | None = None,
             place=None, check_stable: bool = True) -> dict:
    """分类一个分子（原子序列 + 键表）。

    参数
    ----
    atoms   : 元素序列
    edges   : ``[(i, j, mult), ...]``
    rules   : 用于计算 6 级骨架块的规则版本（默认 11 = 当前正式口径）
    library : 预加载的骨架库（省略则自动加载）
    place   : 可选，``{下标: (q, r)}``；提供时额外给出每条键的键型 S/C/L
    check_stable : 是否做"稳定物质"判定（需要一次模拟，略慢）

    返回
    ----
    dict，主要字段：

    ``formula / zh / natoms / category``   身份与三价种类数
        （``no_trivalent`` / ``single_trivalent`` / ``multi_trivalent``）
    ``in_library``      全部 6 级块是否都在 38 库 / 7×3 库
    ``stable``          传入结构是否等于 ``F(自身组成)``（一步自分解不动点）
    ``level6``          6 级中间态骨架块（内禀，只由元素计数决定）
    ``skeleton``        观测结构的终态三价组件、0 级融合键、结构定理复核
    ``layers``          三层拆解（骨架 / 连接 / 终端）
    ``divalent``        二价原子的存在形式与角色

    注意 ``skeleton.structure_theorem_ok`` 与 ``stable`` 是两件事：

    - ``structure_theorem_ok`` 是**内禀**性质，用 ``F(组成)`` 自己的终态骨架去复核
      "终态 = 6 级块之并"，与传入结构无关；
    - ``stable`` 才是"传入的这个结构是不是稳定物质"；不稳定物质会被自然环境的
      自分解规则送回 ``F(组成)``。
    """
    atoms = list(atoms)
    edges = [tuple(e) for e in edges]
    lib = library if library is not None else load_library()
    formula = formula_of(atoms)
    n = len(atoms)

    tr = reactor.trace(atoms, rules=rules)
    if tr is None:
        return {"ok": False, "formula": formula, "natoms": n, "rules": rules,
                "reason": "valence_unfillable",
                "detail": "总价数为奇数，或存在无法填满价数的原子"}

    blocks = _trivalent_blocks(tr["level6"])
    block_reports = []
    for blk in blocks:
        rep = classify_block(blk["atoms"], blk["edges"], lib)
        rep.update({"atoms": blk["atoms"],
                    "edges": blk["edges"],
                    "members": blk["members"],
                    "size": len(blk["atoms"]),
                    "formula": formula_of(blk["atoms"]),
                    "zh": zh_of(blk["atoms"])})
        block_reports.append(rep)

    all_in_lib = all(b["in_library"] for b in block_reports)
    n_types = len(set(atoms) & TRI)
    if n_types == 0:
        category = "no_trivalent"
    elif n_types == 1:
        category = "single_trivalent"
    else:
        category = "multi_trivalent"

    # 实际结构（传入的 edges）的终态三价连通块 —— 用于层拆解与二价角色
    obs_comps = _induced_components(atoms, edges, TRI)
    triv_comp_of: dict[int, int] = {}
    for ci, comp in enumerate(obs_comps):
        for v in comp["members"]:
            triv_comp_of[v] = ci

    def cover_flags(comps):
        """每个终态三价组件是否恰好 = 若干 6 级块之并。"""
        flags = []
        for comp in comps:
            members = set(comp["members"])
            covered = set()
            for blk in blocks:
                if set(blk["members"]) <= members:
                    covered |= set(blk["members"])
            flags.append(bool(covered) and covered == members)
        return flags

    obs_flags = cover_flags(obs_comps)
    # 结构定理是**内禀**性质：用 F(组成) 的终态三价组件来复核，与传入结构无关
    sim_comps = _induced_components(atoms, tr["bonds"], TRI)
    theorem_ok = all(cover_flags(sim_comps))

    comp_reports = []
    for comp, ok in zip(obs_comps, obs_flags):
        comp_reports.append({
            "members": sorted(comp["members"]),
            "atoms": comp["atoms"],
            "edges": comp["edges"],
            "size": len(comp["members"]),
            "formula": formula_of(comp["atoms"]),
            "covers_level6": ok,
        })

    # 0 级同类三价键 = 融合/加固键
    fusion = [{"i": i, "j": j, "mult": m, "element": atoms[i]}
              for (i, j, m) in edges
              if atoms[i] in TRI and atoms[j] in TRI and ptable_dist(atoms[i], atoms[j]) == 0]

    divalent = _divalent_roles(atoms, edges, triv_comp_of)
    role_counts = Counter(d["role"] for d in divalent)

    layers = {
        "skeleton": [i for i in range(n) if atoms[i] in TRI],
        "bridge": [i for i in range(n) if atoms[i] in DIV],
        "cap": [i for i in range(n) if atoms[i] in MONO],
    }
    caps = [{"index": i, "element": atoms[i]} for i in layers["cap"]]

    bonds = None
    if place:
        bonds = []
        for (i, j, m) in edges:
            d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
            bonds.append({"i": i, "j": j, "mult": m, "type": classify_offset(d)})

    result = {
        "ok": True,
        "formula": formula,
        "zh": zh_of(atoms),
        "natoms": n,
        "rules": rules,
        "category": category,
        "in_library": all_in_lib,
        "level6": {
            "blocks": block_reports,
            "n_blocks": len(block_reports),
            "all_in_library": all_in_lib,
            "sizes": [b["size"] for b in block_reports],
        },
        "skeleton": {
            "components": comp_reports,
            "fusion_bonds": fusion,
            "n_fusion_bonds": len(fusion),
            "structure_theorem_ok": theorem_ok,
        },
        "layers": layers,
        "divalent": divalent,
        "divalent_roles": dict(role_counts),
        "caps": caps,
    }
    if bonds is not None:
        result["bonds"] = bonds
    if check_stable:
        result["stable"] = _stable(atoms, edges, rules)
    return result


def classify_feed(atom_list, rules: int = 11, library: dict | None = None,
                  check_stable: bool = True) -> dict:
    """对一锅投料做"反应 + 逐产物分类"。

    返回 ``{"feed": [...], "formula": ..., "ok": bool, "mols": [分类结果, ...],
    "summary": {...}}``。产物不可行时 ``ok=False``。
    """
    atom_list = list(atom_list)
    lib = library if library is not None else load_library()
    tr = reactor.trace(atom_list, rules=rules)
    if tr is None:
        return {"ok": False, "feed": atom_list, "formula": formula_of(atom_list),
                "rules": rules, "mols": [], "reason": "valence_unfillable"}
    mols = [classify(m["atoms"], m["edges"], rules=rules, library=lib,
                     check_stable=check_stable)
            for m in tr["mols"]]
    formulas = Counter(m["formula"] for m in mols)
    return {
        "ok": True,
        "feed": atom_list,
        "formula": formula_of(atom_list),
        "rules": rules,
        "mols": mols,
        "summary": {
            "n_mols": len(mols),
            "formulas": dict(formulas),
            "all_in_library": all(m.get("in_library", False) for m in mols),
            "all_stable": all(m.get("stable", False) for m in mols) if check_stable else None,
            "level6_blocks": sorted({
                b["formula"] for m in mols for b in m["level6"]["blocks"]
            }),
        },
    }


def classify_record(rec: dict, rules: int = 11, library: dict | None = None,
                    check_stable: bool = True) -> dict:
    """分类一条目录记录（自动带上 place，用于给出键型 S/C/L）。

    批量分类时建议传 ``check_stable=False``（跳过"稳定物质"判定，省一次模拟）。
    """
    place = None
    if rec.get("place"):
        place = {int(k): (int(v[0]), int(v[1])) for k, v in rec["place"].items()}
    out = classify(rec["atoms"], [tuple(e) for e in rec["edges"]],
                   rules=rules, library=library, place=place, check_stable=check_stable)
    out["source"] = rec.get("source")
    out["catalog_formula"] = rec.get("formula")
    return out
