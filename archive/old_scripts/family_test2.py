# -*- coding: utf-8 -*-
"""family_test2：按"链 + 侧挂 1 价端基"构造候选无限族，验证 ①几何可摆 ②可被反应产出。

投料计数全部取偶数（可由单质 O2/K2/... 凑出），保证"可产出"证明链从基础单质出发。
"""
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def build_chain_family(elems, n, chain_a, chain_b, pendant_a, pendant_b):
    """构造链分子：n 段 a-b 交替链（2n 原子），每个链原子挂一个端基，两端各补一个端基。
    返回 (atoms, edges) 结构。原子顺序：先链原子 0..2n-1（交替 a,b），再端基。"""
    atoms = []
    edges = []
    chainA_idx = []
    for i in range(2 * n):
        atoms.append(chain_a if i % 2 == 0 else chain_b)
        chainA_idx.append(len(atoms) - 1)
        if i > 0:
            edges.append((i - 1, i, 1))
    # 每原子挂一个端基
    for i in range(2 * n):
        pa = pendant_a if i % 2 == 0 else pendant_b
        atoms.append(pa)
        edges.append((i, len(atoms) - 1, 1))
    # 两端各补一个端基
    atoms.append(pendant_a)
    edges.append((0, len(atoms) - 1, 1))
    atoms.append(pendant_b)
    edges.append((2 * n - 1, len(atoms) - 1, 1))
    return atoms, edges


def test_structure(atoms, edges, label):
    place = P.embed_mol(atoms, edges)
    print(f"  {label}: 结构 {'可摆 OK' if place else '摆不出'}")
    if place:
        types = []
        for (i, j, m) in edges:
            d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
            types.append(P.classify_offset(d))
        print("    键型:", "".join(t[0] for t in types))
    return place


def test_reaction(elems, counts, target, label):
    atoms = P.vec_to_atoms(tuple(counts), elems)
    mols = P.simulate(atoms)
    if mols is None:
        print(f"  {label}: 反应失败(剩键)")
        return False
    if not P.embed_all(mols):
        print(f"  {label}: 产物摆不出来")
        return False
    fs = [P.formula_of(m["atoms"]) for m in mols]
    hit = target in fs
    print(f"  {label}: 投料={counts} 目标 {target} -> {'OK' if hit else 'NO'}  产物={fs[:10]}")
    return hit


def main():
    # ---------- 范围3：K_n O_n C_{2n+2}，链 a=O(聚) b=K(散)，端基 O 挂 C、K 挂 C ----------
    print("[A] 范围3 族 A_n: K_n O_n C_{2n+2}（O-K 链 + 每原子挂 C + 两端补 C）")
    for n in (2, 4, 6):
        atoms, edges = build_chain_family(None, n, "O", "K", "C", "C")
        test_structure(atoms, edges, f"n={n} 结构")
        target = P.formula_of(atoms)
        test_reaction(["O", "X", "C", "K", "A", "F"],
                      (n, 0, 2 * n + 2, n, 0, 0), target, f"n={n} 反应")

    # ---------- 范围4：O_n P_n C_{2n+2} ----------
    print("\n[B] 范围4 族：O_n P_n C_{2n+2}（O-P 链 + 挂 C）")
    for n in (2, 4, 6):
        atoms, edges = build_chain_family(None, n, "O", "P", "C", "C")
        test_structure(atoms, edges, f"n={n} 结构")
        target = P.formula_of(atoms)
        test_reaction(["O", "X", "C", "P", "W", "L"],
                      (n, 0, 2 * n + 2, n, 0, 0), target, f"n={n} 反应")

    # ---------- 范围5：P_n K_n F_{2n+2} ----------
    print("\n[C] 范围5 族：P_n K_n F_{2n+2}（P-K 链 + 挂 F）")
    for n in (2, 4, 6):
        atoms, edges = build_chain_family(None, n, "P", "K", "F", "F")
        test_structure(atoms, edges, f"n={n} 结构")
        target = P.formula_of(atoms)
        test_reaction(["P", "W", "L", "K", "A", "F"],
                      (n, 0, 0, n, 0, 2 * n + 2), target, f"n={n} 反应")


if __name__ == "__main__":
    main()
