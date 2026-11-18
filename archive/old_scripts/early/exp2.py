# -*- coding: utf-8 -*-
"""exp2：分别探测 6 元素范围（N=18）与 9 元素范围（N=12/14）的闭包规模。"""
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
    name = sys.argv[1]
    N = int(sys.argv[2])
    elems = SUBSETS[name]
    t = time.time()
    known = TPA.closure(elems, [e + "2" for e in elems], N, verbose=True)
    stat = defaultdict(int)
    for f in known:
        stat[classify(f)] += 1
    print(f"[{name}] N={N} 物质 {len(known)} 用时 {time.time()-t:.1f}s 分类: {dict(stat)}")


if __name__ == "__main__":
    main()
