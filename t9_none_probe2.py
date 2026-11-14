# -*- coding: utf-8 -*-
"""t9_none_probe2.py：不含三价元素（X,C,W,L,A,F）的大规模探测
- 全部 15 个元素对：计数 0..24 网格
- 全部 20 个三元组：计数 0..24 步长 3 网格
- 六元随机大计数 40 组
记录「最大分子尺寸」，判断是否存在 >16 原子的物质。"""
import itertools
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

ELEMS = "XCWLAF"


def sim_max(counts, k=0):
    atoms = []
    for s in ELEMS:
        atoms += [s] * counts.get(s, 0)
    mols = P.simulate(atoms)
    if mols is None:
        return None, 0
    if not P.embed_all(mols):
        return None, -1
    return mols, max(len(m["atoms"]) for m in mols)


def main():
    globalmax = 0
    worst = None
    print("== 二元池 ==", flush=True)
    for a, b in itertools.combinations(ELEMS, 2):
        m = 0
        fail = 0
        for i in range(0, 25):
            for j in range(0, 25):
                if i + j == 0:
                    continue
                mols, mx = sim_max({a: i, b: j})
                if mx < 0:
                    fail += 1
                m = max(m, mx)
        globalmax = max(globalmax, m)
        if m > 0:
            worst = (a, b, m)
        print(f"  {a}{b}: 最大分子={m} 摆放失败={fail}", flush=True)

    print("== 三元池（步长 3） ==", flush=True)
    for tri in itertools.combinations(ELEMS, 3):
        m = 0
        for i in range(0, 25, 3):
            for j in range(0, 25, 3):
                for k in range(0, 25, 3):
                    if i + j + k == 0:
                        continue
                    c = {tri[0]: i, tri[1]: j, tri[2]: k}
                    mols, mx = sim_max(c)
                    m = max(m, mx)
        globalmax = max(globalmax, m)
        print(f"  {''.join(tri)}: 最大分子={m}", flush=True)

    print("== 六元随机大计数 ==", flush=True)
    rng = random.Random(7)
    m = 0
    for _ in range(40):
        c = {s: rng.randint(0, 20) for s in ELEMS}
        mols, mx = sim_max(c)
        m = max(m, mx)
    globalmax = max(globalmax, m)
    print(f"  随机40组: 最大分子={m}", flush=True)
    print("\n全局最大分子尺寸:", globalmax, " worst:", worst)


if __name__ == "__main__":
    main()
