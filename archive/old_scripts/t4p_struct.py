# -*- coding: utf-8 -*-
"""t4p_struct：分析反应产物组件的分级结构（每条 bond 的距离、组件内键数分布）。"""
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def run(elems, feed):
    atoms = P.vec_to_atoms(tuple(feed), elems)
    mols = P.simulate(atoms)
    if not mols:
        print("sim fail"); return
    mols.sort(key=lambda m: -len(m["atoms"]))
    for m in mols[:6]:
        ats, edges = m["atoms"], m["edges"]
        n = len(ats)
        dhist = Counter()
        cp = Counter()
        degs = [0]*n
        for (i, j, mult) in edges:
            d = P.ptable_dist(ats[i], ats[j])
            dhist[d] += mult
            cp[tuple(sorted((P.CAT[ats[i]], P.CAT[ats[j]])))] += mult
            degs[i] += mult; degs[j] += mult
        print(f"  mol n={n} elems={dict(Counter(ats))}")
        print(f"    bond distances={dict(sorted(dhist.items(), reverse=True))}  catpair={ {k:v for k,v in cp.items()} }")
        print(f"    degree ok={all(degs[i]==P.VAL[ats[i]] for i in range(n))}  mult={dict(Counter(e[2] for e in edges))}")
        if n <= 20:
            print("    edges:", [(ats[i]+str(i), ats[j]+str(j), mult, P.ptable_dist(ats[i],ats[j])) for i,j,mult in edges])


if __name__ == "__main__":
    print("=== O18 X20 K46 (t=2) ===")
    run(["O","X","K"], (18,20,46))
    print("=== O9 X10 K23 (t=1) ===")
    run(["O","X","K"], (9,10,23))
    print("=== O27 X30 K69 (t=3) ===")
    run(["O","X","K"], (27,30,69))
