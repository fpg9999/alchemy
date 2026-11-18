# -*- coding: utf-8 -*-
"""alchemy —— 炼金术化学内核。

一个"元素 → 价数 → 键型 → 分子 → 骨架"的确定性化学模型，为炼金术题材游戏提供
物质生成与结构分类的底层规则。

## 快速上手

>>> import alchemy
>>> alchemy.simulate(["O", "X", "C"])
[{'atoms': ['O', 'C', 'X'], 'edges': [(0, 1, 1), (0, 2, 2)]}]

>>> place = alchemy.embed(["O", "X", "C"], [(0, 1, 1), (0, 2, 2)])
>>> alchemy.validate(place, ["O", "X", "C"], [(0, 1, 1), (0, 2, 2)])[0]
True

>>> cat = alchemy.get_catalog()          # 84,225 条，首次调用读盘
>>> "OXC" in cat
True

>>> alchemy.classify(["O", "X", "C"], [(0, 1, 1), (0, 2, 2)])["level6"]["blocks"][0]["kind"]
'single'  # O 是唯一的三价元素 -> 6 级块是 7×3 单三价库里的"单原子"模块

## 四个入口

| 入口 | 作用 |
|---|---|
| ``simulate(atoms, rules=11)`` | 大锅反应（完全反应），确定性贪心成键 |
| ``embed(atoms, edges)`` / ``validate(place, atoms, edges)`` | 六边形网格摆放与严格校验 |
| ``get_catalog()`` / ``load_catalog()`` | 84,225 条物质目录（只读索引） |
| ``classify(atoms, edges)`` | 骨架分类（6 级骨架块 / 38 库 / 三层拆解） |

## 关于规则版本

项目历史上有三套口径同时存在于数据中：规则 1~8（``pot_all``）、1~9（``pot_v3``）、
1~11（``pot_v4``，当前正式）。``simulate(..., rules=8 | 9 | 11)`` 可切换，
**新代码请一律用默认的 11**。
"""
from __future__ import annotations

from .core import canon, catalog, classify as _classify_mod, elements, geometry, reactor
from .core.catalog import Catalog, clear_cache, get_catalog, load_catalog
from .core.classify import (
    block_label,
    classify,
    classify_block,
    classify_feed,
    classify_record,
    load_library,
)
from .core.elements import (
    CAT,
    CN,
    DIV,
    ELEM,
    MONO,
    ORDER,
    TRI,
    VAL,
    atoms_to_vec,
    classify_offset,
    formula_of,
    parse_formula,
    ptable_dist,
    vec_to_atoms,
    zh_of,
)
from .core.geometry import embed, embed_all, to_place_dict, validate
from .core.reactor import RULE9_PRIORITY, SUPPORTED_RULES, simulate, trace
from . import biome
from . import phase

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # 数据模型
    "ELEM", "ORDER", "VAL", "CAT", "CN", "TRI", "DIV", "MONO",
    "formula_of", "zh_of", "parse_formula", "vec_to_atoms", "atoms_to_vec",
    "ptable_dist", "classify_offset",
    # 四个入口
    "simulate", "trace", "embed", "embed_all", "validate", "to_place_dict",
    "Catalog", "get_catalog", "load_catalog", "clear_cache",
    "classify", "classify_feed", "classify_record", "classify_block",
    "load_library", "block_label",
    # 元信息
    "SUPPORTED_RULES", "RULE9_PRIORITY",
    # 子模块
    "canon", "catalog", "elements", "geometry", "reactor", "biome", "phase",
]
