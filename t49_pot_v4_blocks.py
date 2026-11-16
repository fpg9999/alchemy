# -*- coding: utf-8 -*-
"""t49_pot_v4_blocks.py：口径 1~11（pot_v4）下，全部三价组合的 6 级块是否都属于 38 库。"""
import sys
import random
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v4
import t39_library_verify as V

VAL = P.VAL


def main():
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    bad = []
    nonlib = {}
    classes = set()
    sizes = Counter()
    max_total = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    for total in range(1, max_total + 1):
        for nO in range(total + 1):
            for nP in range(total - nO + 1):
                nK = total - nO - nP
                if nO == nP == nK == 0:
                    continue
                atoms = []
                for e, c in zip(("O", "P", "K"), (nO, nP, nK)):
                    atoms += [e] * c
                mols, l6 = pot_v4.simulate(atoms, return_level6=True)
                if mols is None:
                    continue
                for (ats, es, mem) in l6:
                    k = V.block_label(ats, es)
                    classes.add(k)
                    sizes[len(ats)] += 1
                    if k not in libkeys:
                        nonlib.setdefault(k, {"atoms": ats,
                                              "edges": [list(e) for e in es],
                                              "counts": (nO, nP, nK)})
    print("block classes:", len(classes))
    print("non-library classes:", len(nonlib))
    for k, v in nonlib.items():
        print(" ", v["counts"], v["atoms"], v["edges"])
    print("sizes:", dict(sorted(sizes.items())))

    # 大投料随机抽样
    rng = random.Random(7)
    sampled_blocks = 0
    for t in range(400):
        total = rng.randint(13, 60)
        a = rng.randint(0, total)
        b = rng.randint(0, total - a)
        c = total - a - b
        atoms = []
        for e, cc in zip(("O", "P", "K"), (a, b, c)):
            atoms += [e] * cc
        mols, l6 = pot_v4.simulate(atoms, return_level6=True)
        if mols is None:
            continue
        for (ats, es, mem) in l6:
            sampled_blocks += 1
            k = V.block_label(ats, es)
            if k not in libkeys:
                nonlib.setdefault(k, {"atoms": ats, "edges": [list(e) for e in es],
                                      "counts": (a, b, c)})
    print("large sampling blocks:", sampled_blocks, "non-library total:", len(nonlib))


if __name__ == "__main__":
    main()
