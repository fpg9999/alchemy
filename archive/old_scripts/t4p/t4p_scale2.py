# -*- coding: utf-8 -*-
"""t4p_scale2：对若干元素子集，按比例缩放投料，观察最大分子是否饱和（有限性实验）。"""
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def maxmol(elems, feed):
    atoms = P.vec_to_atoms(tuple(feed), elems)
    mols = P.simulate(atoms)
    if not mols:
        return None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    return sizes


def main():
    families = [
        ("K,X (散3,聚2)", ["K", "X"], lambda t: (3 * t, 2 * t)),
        ("K,A (散3,散2)", ["K", "A"], lambda t: (3 * t, 2 * t)),
        ("K,F (散3,散1)", ["K", "F"], lambda t: (3 * t, 1 * t)),
        ("O,K (聚3,散3)", ["O", "K"], lambda t: (3 * t, 2 * t)),
        ("O,K,X (9,10,23)", ["O", "X", "K"], lambda t: (9 * t, 10 * t, 23 * t)),
        ("O,P,K (聚3,动3,散3)", ["O", "P", "K"], lambda t: (3 * t, 3 * t, 2 * t)),
        ("O,X,C (纯聚)", ["O", "X", "C"], lambda t: (2 * t, 3 * t, 4 * t)),
        ("O,X,P,W (两两不同类)", ["O", "X", "P", "W"], lambda t: (3 * t, 3 * t, 3 * t, 2 * t)),
        ("O,X,K,A (2+2)", ["O", "X", "K", "A"], lambda t: (3 * t, 3 * t, 3 * t, 3 * t)),
    ]
    for name, elems, fn in families:
        print(f"\n=== {name} ===")
        for t in (1, 2, 3, 5, 8):
            feed = fn(t)
            sizes = maxmol(elems, feed)
            if sizes is None:
                print(f"  t={t} feed={feed}: 失败")
            else:
                print(f"  t={t} feed={feed} N={sum(feed)}: 分子数={len(sizes)} 最大={sizes[:6]}")


if __name__ == "__main__":
    main()
