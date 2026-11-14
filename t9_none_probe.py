# -*- coding: utf-8 -*-
"""t9_none_probe.py：不含三价元素（X/C/W/L/A/F）的大投料探测：
统计不同元素池、不同规模下最大分子尺寸，判断是否有 >16 原子的物质/增长趋势。"""
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

POOLS = {
    "XW": ("X", "W"),
    "XC": ("X", "C"),
    "WL": ("W", "L"),
    "AC": ("A", "C"),
    "XA": ("X", "A"),
    "WA": ("W", "A"),
    "XWC": ("X", "W", "C"),
    "XWL": ("X", "W", "L"),
    "XWA": ("X", "W", "A"),
    "XCF": ("X", "C", "F"),
    "XWCA": ("X", "W", "C", "A"),
    "ALL6": ("X", "C", "W", "L", "A", "F"),
}

for name, elems in POOLS.items():
    e = list(elems)
    row = []
    for k in (2, 4, 6, 8, 12, 16, 24, 32, 48):
        counts = {s: 0 for s in "XCWLAF"}
        for s in e:
            counts[s] = k
        atoms = []
        for s in "XCWLAF":
            atoms += [s] * counts[s]
        mols = P.simulate(atoms)
        if mols is None:
            row.append((k, "FAIL", 0))
            continue
        ok = P.embed_all(mols) if hasattr(P, "embed_all") else True
        mx = max(len(m["atoms"]) for m in mols)
        row.append((k, "ok" if ok else "noembed", mx))
    print(name, "k=2,4,6,8,12,16,24,32,48 ->", row, flush=True)
