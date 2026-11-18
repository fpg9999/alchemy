# -*- coding: utf-8 -*-
"""scan_single：在一个范围里找"整锅只出一个大分子"的投料，为无限族找规律。

用法: python scan_single.py <scope_id> <N> [elems...]
只统计单分子产物、原子数>=10 的情况，输出分子式（不打印结构）。
"""
import sys
import time
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

SCOPES = {
    3: ["O", "X", "C", "K", "A", "F"],
    4: ["O", "X", "C", "P", "W", "L"],
    5: ["P", "W", "L", "K", "A", "F"],
    6: P.ORDER,
}


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def main():
    sid = int(sys.argv[1])
    N = int(sys.argv[2])
    elems = SCOPES[sid] if len(sys.argv) <= 3 else sys.argv[3].split(",")
    t0 = time.time()
    found = {}   # formula -> (feed, structure)
    cnt_done = 0
    for total in range(10, N + 1):
        t = time.time()
        for v in gen_compositions(total, len(elems)):
            cnt_done += 1
            atoms = P.vec_to_atoms(v, elems)
            mols = P.simulate(atoms)
            if not mols or len(mols) != 1:
                continue
            m = mols[0]
            if len(m["atoms"]) < 10:
                continue
            if P.embed_mol(m["atoms"], m["edges"]) is None:
                continue
            f = P.formula_of(m["atoms"])
            if f not in found:
                found[f] = (v, m)
        print(f"  total={total}: 单分子大物质累计={len(found)} "
              f"({time.time()-t:.1f}s, 已算 {cnt_done})", flush=True)
    print(f"\n范围{sid} N={N} 共 {len(found)} 个单分子大物质, 用时 {time.time()-t0:.1f}s")
    bysize = defaultdict(list)
    for f in found:
        bysize[sum(P.parse_formula(f))].append(f)
    for sz in sorted(bysize):
        print(f"  {sz} 原子 ({len(bysize[sz])}):", " ".join(sorted(bysize[sz])[:40]))


if __name__ == "__main__":
    main()
