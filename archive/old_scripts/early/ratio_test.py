# -*- coding: utf-8 -*-
"""ratio_test：按元素比例扫一批投料，看最大分子尺寸是否随投料增大而增长（判断有限/无限）。"""
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

EL = ["O", "X", "C", "K", "A", "F"]


def test(counts, label):
    atoms = P.vec_to_atoms(tuple(counts), EL)
    mols = P.simulate(atoms)
    if mols is None:
        print(f"  {label:34s} 剩键失败")
        return
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    ok = "摆不出" if not P.embed_all(mols) else "可摆"
    print(f"  {label:34s} 原子{sum(counts):2d} -> 分子{len(mols):2d}个 最大{max(sizes):2d} 尺寸{sizes[:6]} {ok}")


def main():
    print("== 只有 O,K（比例族）==")
    for m in range(1, 9):
        test((2 * m, 0, 0, m, 0, 0), f"O_{2*m} K_{m}")
    for m in range(1, 7):
        test((3 * m, 0, 0, m, 0, 0), f"O_{3*m} K_{m}")
    for m in range(1, 5):
        test((3 * m, 0, 0, 2 * m, 0, 0), f"O_{3*m} K_{2*m}")
    for m in range(1, 5):
        test((2 * m, 0, 0, 2 * m, 0, 0), f"O_{2*m} K_{2*m}")

    print("\n== O,K,F（端基封口）==")
    for m in range(1, 7):
        test((3 * m, 0, 0, m, 0, 2 * m), f"O_{3*m} K_{m} F_{2*m}")
    for m in range(1, 7):
        test((2 * m, 0, 0, m, 0, 2 * m), f"O_{2*m} K_{m} F_{2*m}")
    for m in range(1, 7):
        test((2 * m, 0, 0, m, 0, 2 * m), f"O_{2*m} K_{m} C_{2*m}（C 位用 F）")


if __name__ == "__main__":
    main()
