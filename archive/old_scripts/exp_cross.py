# -*- coding: utf-8 -*-
"""exp_cross：摸清跨类范围的规模（闭包在不同总原子上限下的物质数 / 用时）。"""
import sys
import time
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import importlib.util

spec = importlib.util.spec_from_file_location("TPA", r"G:\AI work\deepseek\work1\alchemy\test_pot_all.py")
TPA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TPA)

SUBSETS = {
    "聚散": ["O", "X", "C", "K", "A", "F"],
    "聚动": ["O", "X", "C", "P", "W", "L"],
    "动散": ["P", "W", "L", "K", "A", "F"],
    "全部": P.ORDER,
}


def classify(f):
    cats = set()
    for ch in f:
        if ch in P.CAT:
            cats.add(P.CAT[ch])
    return "-".join(c for c in ["聚", "动", "散"] if c in cats)


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 18
    for name, elems in SUBSETS.items():
        seeds = [e + "2" for e in elems]
        t = time.time()
        known = TPA.closure(elems, seeds, N, verbose=True)
        stat = defaultdict(int)
        for f in known:
            stat[classify(f)] += 1
        print(f"[{name}] N={N} 物质 {len(known)} 用时 {time.time()-t:.1f}s 分类: {dict(stat)}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
