# -*- coding: utf-8 -*-
"""t37b_branch.py：抽样并列选择，检查大锅产物的骨架是否有歧义"""
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


for f in ["O5X3KA", "O5X3PA", "OP5W3A", "OWK5A3", "OCP7W2KA2"]:
    atoms = pot_all.vec_to_atoms(pot_all.parse_formula(f), ORDER)
    outs = set()
    for i in range(300):
        r = T.run(atoms, policy="random", rng=random.Random(i))
        if r:
            outs.add(canon(r))
    rd = T.run(atoms, policy="first", collect_ties=True)
    ri = T.run(atoms, policy="intra") if "policy" in T.run.__code__.co_varnames else None
    print(f, "distinct skeleton outcomes:", len(outs),
          "ties(default):", len(rd["ties"]) if rd else None)
