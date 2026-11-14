# -*- coding: utf-8 -*-
"""t37c_ambiguity.py：对比默认/随机并列 vs 新规则（优先中间态骨架内原子）"""
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all
import t37_tie_analysis as T
from t15_forms_examples import wl_key

ORDER = pot_all.ORDER


def canon(r):
    keys = [wl_key(m["atoms"], [tuple(e) for e in m["edges"]]) for m in r["molecules"]]
    return tuple(sorted(keys, key=str))


def formula(r):
    c = {}
    for m in r["molecules"]:
        for a in m["atoms"]:
            c[a] = c.get(a, 0) + 1
    return tuple(sorted(c.items()))


def sample(atoms, policy, n=300):
    outs = set()
    for i in range(n):
        r = T.run(atoms, policy=policy, rng=random.Random(i * 7 + 3))
        if r:
            outs.add(canon(r))
    return outs


for f in ["O5X3KA", "O5X3PA", "OP5W3A", "OWK5A3", "OCP7W2KA2", "X3A", "WA3F2"]:
    atoms = pot_all.vec_to_atoms(pot_all.parse_formula(f), ORDER)
    rd = T.run(atoms, policy="first", collect_ties=True)
    all_outs = sample(atoms, "random", 300)
    intra_outs = sample(atoms, "intra_random", 300)
    print(f, "atoms", len(atoms), "default ties", len(rd["ties"]) if rd else None,
          "all-tie outcomes", len(all_outs), "intra-rule outcomes", len(intra_outs))
    if len(intra_outs) > 1:
        print("  RESIDUAL AMBIGUITY remains after intra rule")
