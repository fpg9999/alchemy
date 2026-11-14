# -*- coding: utf-8 -*-
"""t37d_residual.py：找 O5X3KA 在「中间态骨架内优先」规则下残留的歧义来源"""
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all
import t37_tie_analysis as T
from t15_forms_examples import wl_key

ORDER = pot_all.ORDER


def canon(r):
    return tuple(sorted([wl_key(m["atoms"], [tuple(e) for e in m["edges"]]) for m in r["molecules"]], key=str))


atoms = pot_all.vec_to_atoms(pot_all.parse_formula("O5X3KA"), ORDER)
seen = {}
for seed in range(300):
    r = T.run(atoms, policy="intra_random", rng=random.Random(seed))
    c = canon(r)
    if c not in seen:
        seen[c] = r
    if len(seen) >= 2:
        break
print("distinct outcomes found:", len(seen))
items = list(seen.items())
if len(items) >= 2:
    c1, r1 = items[0]
    c2, r2 = items[1]
    ch1, ch2 = r1["choices"], r2["choices"]
    for k, (a, b) in enumerate(zip(ch1, ch2)):
        if a["chosen"] != b["chosen"]:
            print("first differing step", k)
            print("A tie len", len(a["tied"]), "chosen", a["chosen"], "blocks_ready", a["blocks_ready"], "intra", a["intra"])
            print("B tie len", len(b["tied"]), "chosen", b["chosen"], "blocks_ready", b["blocks_ready"], "intra", b["intra"])
            print("key", a["key"])
            break
