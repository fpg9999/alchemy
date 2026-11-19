# -*- coding: utf-8 -*-
"""自然反应：**不完全反应**——只切断最不稳定的键，剩下的部分再结合。

规则
----
- 键的稳定性由**周期表距离**决定：距离越近越不稳定
  （同种元素 = 0，最不稳定；O–K = 6，最稳定）
- 断键步骤：
    1. 找该分子里周期表距离**最小**的键，全部断开
    2. 没有这样的键，再找距离 +1 的，全部断开
    3. 以此类推（本例只断最弱的那一层）
- **断键数** = 被断开的键数；反应阈值 = 两个分子的断键数之和
- 断开后，**存活的键保留**，只有断口重新按自然规则结合（rule 1：距离远的先连）
"""

from __future__ import annotations

from functools import lru_cache

from .core.elements import VAL, ORDER, formula_of, parse_formula
from .core.reactor import _trace, ptable_dist


@lru_cache(maxsize=4096)
def structure_of(formula: str) -> tuple:
    """由分子式还原出一个分子的结构：``(atoms, edges)``（取最大的连通块）。"""
    v = parse_formula(formula)
    atoms = [e for e, n in zip(ORDER, v) for _ in range(int(n))]
    if not atoms:
        return ((), ())
    tr = _trace(atoms)
    if not tr or not tr["mols"]:
        return (tuple(atoms), ())
    best = max(tr["mols"], key=lambda m: len(m["atoms"]))
    return (tuple(best["atoms"]), tuple(best["edges"]))


def weakest_layer(atoms, edges) -> tuple[list, int, int | None]:
    """返回 (存活键, 断键数, 被断的最小距离)。"""
    if not edges:
        return ([], 0, None)
    ds = [ptable_dist(atoms[i], atoms[j]) for (i, j, m) in edges]
    mn = min(ds)
    surviving = [(i, j, m) for (i, j, m), d in zip(edges, ds) if d > mn]
    broken = sum(1 for d in ds if d == mn)
    return (surviving, broken, mn)


def break_count(formula: str) -> int:
    """该分子自然断键时会断几根（阈值用）。"""
    atoms, edges = structure_of(formula)
    return weakest_layer(atoms, edges)[1]


@lru_cache(maxsize=8192)
def natural_products(fa: str, fb: str) -> tuple[tuple[str, ...], int] | None:
    """两分子自然相遇的产物。返回 (产物分子式元组, 总断键数) 或 None。"""
    aa, ea = structure_of(fa)
    ab, eb = structure_of(fb)
    if not aa or not ab:
        return None
    sa, ba, _ = weakest_layer(aa, ea)
    sb, bb, _ = weakest_layer(ab, eb)
    atoms = list(aa) + list(ab)
    off = len(aa)
    seed = list(sa) + [(i + off, j + off, m) for (i, j, m) in sb]
    tr = _trace(atoms, seed_bonds=seed)
    if not tr or not tr["mols"]:
        return None
    prods = tuple(formula_of(m["atoms"]) for m in tr["mols"])
    return (prods, ba + bb)
