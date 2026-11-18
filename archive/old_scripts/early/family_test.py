# -*- coding: utf-8 -*-
"""family_test：测试候选无限族是否真的可产出（某投料例 → 单一分子公式）。"""
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def feed_atoms(counts):
    out = []
    for e, c in counts.items():
        out += [e] * c
    return out


def run(counts, expect, label=""):
    atoms = feed_atoms(counts)
    mols = P.simulate(atoms)
    if mols is None:
        print(f"  {label}: 反应失败(剩键)")
        return False
    if not P.embed_all(mols):
        print(f"  {label}: 产物摆不出来  {[P.formula_of(m['atoms']) for m in mols]}")
        return False
    fs = [P.formula_of(m["atoms"]) for m in mols]
    hit = expect in fs
    print(f"  {label}: 产物={fs}  期望含 {expect} -> {'OK' if hit else 'NO'}")
    return hit


def main():
    print("[A] 聚+散：环 (X-A)_n  —— 投料 n*X2 + n*A2（X=2n, A=2n）")
    for n in range(2, 9):
        run({"X": 2 * n, "A": 2 * n}, P.formula_of(["X"] * n + ["A"] * n), f"n={n} X{n}A{n}")

    print("\n[B] 聚+散：链 C-X_n-A_(n-1)-F —— 投料 X2*n + A2*(n-1) + C2 + F2？(C,F 各 1 无法投料，改用 C2/F2 侧)")
    # C/F 一价只能成 C-F；链端需要 1 个 C 和 1 个 F，但投料只有 C2/F2（成对），所以先用 C2 + F2 试
    for n in range(2, 7):
        # 尝试 C2 + F2 + X2*n + A2*(n-1)，总价数须偶
        v = {"C": 2, "F": 2, "X": 2 * n, "A": 2 * (n - 1)}
        run(v, f"C X{n} A{n-1} F", f"n={n} 期望 C X{n} A{n-1} F")

    print("\n[C] 聚+散：O-K 交替环？ O_n K_n (O 3价 K 3价 → 环上各 2 键缺 1)")
    for n in range(3, 7):
        run({"O": 2 * n, "K": 2 * n}, f"O{n}K{n}", f"n={n}")


if __name__ == "__main__":
    main()
