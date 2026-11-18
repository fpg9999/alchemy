# -*- coding: utf-8 -*-
"""测试公用工具。"""

import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import alchemy  # noqa: E402
from alchemy import ORDER, VAL  # noqa: E402
from alchemy.core.canon import mol_label  # noqa: E402


def mol_multiset(mols):
    """把产物列表转成可比较的"多重集"：[(分子式, 规范形), ...] 排序后。"""
    return sorted(
        (alchemy.formula_of(m["atoms"]), mol_label(m["atoms"], m["edges"]))
        for m in mols
    )


def formula_sequence(mols):
    """产物分子式的有序序列（用于检查返回顺序是否与原实现一致）。"""
    return [alchemy.formula_of(m["atoms"]) for m in mols]


def random_feed(rng: random.Random, max_types: int = 4, max_n: int = 12):
    """随机生成一个"价数和为偶数"的元素序列。"""
    while True:
        n = rng.randint(1, max_n)
        pool = rng.sample(ORDER, rng.randint(1, max_types))
        atoms = [rng.choice(pool) for _ in range(n)]
        if sum(VAL[e] for e in atoms) % 2 == 0:
            return atoms


def random_feeds(seed: int, count: int, max_types: int = 4, max_n: int = 12):
    """确定性随机投料集合（固定 seed，可复现）。"""
    rng = random.Random(seed)
    out = []
    while len(out) < count:
        f = random_feed(rng, max_types=max_types, max_n=max_n)
        out.append(f)
    return out


def load_originals():
    """导入仓库根的历史实现（pot_all / pot_v3 / pot_v4），供差分测试用。"""
    import importlib

    mods = {}
    for name in ("pot_all", "pot_v2", "pot_v3", "pot_v4"):
        mods[name] = importlib.import_module(name)
    return mods
