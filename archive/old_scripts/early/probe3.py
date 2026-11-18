# -*- coding: utf-8 -*-
"""probe3：找出范围3里的大分子（例投料 + 结构），为"无限族"找证据。"""
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import importlib.util

spec = importlib.util.spec_from_file_location("TPA", r"G:\AI work\deepseek\work1\alchemy\test_pot_all.py")
TPA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TPA)

ELEMS = ["O", "X", "C", "K", "A", "F"]
N = 12

known = {}
example = {}
struct = {}
for f in [e + "2" for e in ELEMS]:
    known[f] = TPA.parse_in(f, ELEMS)
it = 0
while True:
    vecs = TPA.semigroup(list(known.values()), N)
    new = 0
    for v in vecs:
        atoms = P.vec_to_atoms(v, ELEMS)
        mols = P.simulate(atoms)
        if mols is None or not P.embed_all(mols):
            continue
        for m in mols:
            f = P.formula_of(m["atoms"])
            if f not in known:
                known[f] = TPA.parse_in(f, ELEMS)
                example[f] = v
                struct[f] = m
                new += 1
    it += 1
    print(f"iter {it}: 向量={len(vecs)} 已知={len(known)} 新增={new}", flush=True)
    if new == 0:
        break

print("\n=== 10 原子以上的大分子 ===")
for f in sorted(known, key=lambda s: -sum(P.parse_formula(s))):
    nat = sum(P.parse_formula(f))
    if nat < 10:
        continue
    m = struct.get(f)
    print(f"\n{f}  {P.zh_of(m['atoms'])}  原子={nat}  投料例={example[f]}")
    if m:
        deg = defaultdict(int)
        for (i, j, k) in m["edges"]:
            deg[i] += k
            deg[j] += k
        print("  原子序列:", " ".join(f"{k}:{e}({deg[k]})" for k, e in enumerate(m["atoms"])))
        print("  键:", m["edges"])
        pl = P.embed_mol(m["atoms"], m["edges"])
        print("  摆放(q,r):", pl)
        # 每根键的类型
        types = []
        for (i, j, k) in m["edges"]:
            d = (pl[j][0] - pl[i][0], pl[j][1] - pl[i][1])
            types.append(P.classify_offset(d))
        print("  键型:", types)
