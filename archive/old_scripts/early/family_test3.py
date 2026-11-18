# -*- coding: utf-8 -*-
"""family_test3：验证假设的无限族 O_{3m}K_mF_{2m} 及其它范围的类比。"""
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def test(elems, counts, label, target=None):
    atoms = P.vec_to_atoms(tuple(counts), elems)
    mols = P.simulate(atoms)
    if mols is None:
        print(f"  {label}: 反应失败(剩键)")
        return
    if not P.embed_all(mols):
        print(f"  {label}: 产物摆不出来")
        return
    fs = [P.formula_of(m["atoms"]) for m in mols]
    if target is None and len(fs) == 1:
        print(f"  {label}: 单分子 {fs[0]} ({sum(P.parse_formula(fs[0]))}原子) OK")
    elif target and target in fs:
        print(f"  {label}: 命中 {target}（产物 {len(fs)} 个，最大 {max(sum(P.parse_formula(f)) for f in fs)} 原子）OK")
    else:
        print(f"  {label}: NO  产物={fs[:8]}{' ...' if len(fs) > 8 else ''}（最大 {max(sum(P.parse_formula(f)) for f in fs)} 原子）")


def main():
    print("[A] 范围3 假设族：O_{3m} K_m F_{2m}")
    for m in (2, 4, 6):
        elems = ["O", "X", "C", "K", "A", "F"]
        target = "".join(e + (str(c) if c > 1 else "") for e, c in
                         [("O", 3 * m), ("X", 0), ("C", 0), ("K", m), ("A", 0), ("F", 2 * m)] if c)
        test(elems, (3 * m, 0, 0, m, 0, 2 * m), f"m={m} 目标 {target}", target)

    print("\n[B] 范围3 假设族：O_{3m} K_m C_{2m}（C 代替 F）")
    for m in (2, 4, 6):
        elems = ["O", "X", "C", "K", "A", "F"]
        target = "".join(e + (str(c) if c > 1 else "") for e, c in
                         [("O", 3 * m), ("X", 0), ("C", 2 * m), ("K", m), ("A", 0), ("F", 0)] if c)
        test(elems, (3 * m, 0, 2 * m, m, 0, 0), f"m={m} 目标 {target}", target)

    print("\n[C] 范围4 假设族：O_{3m} P_m C_{2m}")
    for m in (2, 4, 6):
        elems = ["O", "X", "C", "P", "W", "L"]
        target = "".join(e + (str(c) if c > 1 else "") for e, c in
                         [("O", 3 * m), ("P", m), ("C", 2 * m)] if c)
        test(elems, (3 * m, 0, 2 * m, m, 0, 0), f"m={m} 目标 {target}", target)

    print("\n[D] 范围5 假设族：P_{3m} K_m F_{2m}")
    for m in (2, 4, 6):
        elems = ["P", "W", "L", "K", "A", "F"]
        target = "".join(e + (str(c) if c > 1 else "") for e, c in
                         [("P", 3 * m), ("K", m), ("F", 2 * m)] if c)
        test(elems, (3 * m, 0, 0, m, 0, 2 * m), f"m={m} 目标 {target}", target)


if __name__ == "__main__":
    main()
