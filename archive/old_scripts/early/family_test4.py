# -*- coding: utf-8 -*-
"""family_test4：验证"大分子随投料线性增长"的候选族（P_{5m}K_{2m} 等）。"""
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def show(elems, counts, label):
    atoms = P.vec_to_atoms(tuple(counts), elems)
    mols = P.simulate(atoms)
    if mols is None:
        print(f"  {label:26s} 剩键失败")
        return None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    fs = [P.formula_of(m["atoms"]) for m in mols]
    ok = "可摆" if P.embed_all(mols) else "摆不出"
    print(f"  {label:26s} 分子{len(mols):2d}个 最大{sizes[0]:2d} {ok}  产物={fs[:6]}")
    return mols, sizes, fs


EL5 = ["P", "W", "L", "K", "A", "F"]
EL3 = ["O", "X", "C", "K", "A", "F"]

print("== 范围5：P_{5m} K_{2m} ==")
for m in (2, 4, 6):
    show(EL5, (5 * m, 0, 0, 2 * m, 0, 0), f"P{5*m}K{2*m}")

print("\n== 范围5：P_{10m} K_{4m} ==")
for m in (1, 2):
    show(EL5, (10 * m, 0, 0, 4 * m, 0, 0), f"P{10*m}K{4*m}")

print("\n== 范围3：O_{5m} K_{2m} ==")
for m in (2, 4, 6):
    show(EL3, (5 * m, 0, 0, 2 * m, 0, 0), f"O{5*m}K{2*m}")

print("\n== 范围3：O_{2m} K_{m} F_{2m}（每 m 单元）==")
for m in (2, 4, 6):
    show(EL3, (2 * m, 0, 0, m, 0, 2 * m), f"O{2*m}K{m}F{2*m}")

print("\n== 范围4：O_{5m} P_{2m} ==")
EL4 = ["O", "X", "C", "P", "W", "L"]
for m in (2, 4, 6):
    show(EL4, (5 * m, 0, 0, 2 * m, 0, 0), f"O{5*m}P{2*m}")
