# -*- coding: utf-8 -*-
"""t4p_scale：检验"缩放投料"是否仍给一锅一分子、以及是否几何可摆。
O/X/K 的 42 原子最大分子按 t 倍缩放。
"""
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2


def report(elems, feed, budget=2_000_000):
    atoms = P.vec_to_atoms(tuple(feed), elems)
    mols = P.simulate(atoms)
    if not mols:
        print(f"  feed={dict(zip(elems,feed))}: 反应失败（有原子没接满）")
        return None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    print(f"  feed={dict(zip(elems,feed))}: 分子数={len(mols)} 大小={sizes[:10]}")
    big = max(mols, key=lambda m: len(m["atoms"]))
    if len(big["atoms"]) < 8:
        return big
    pl = pot_v2.embed_mol2(big["atoms"], big["edges"], max_nodes=budget)
    ok, msg = pot_v2.validate_place(pl, big["atoms"], big["edges"])
    print(f"    最大分子 n={len(big['atoms'])} embed={pl is not None} valid={ok} msg={msg}")
    return big


if __name__ == "__main__":
    print("O/X/K 缩放（原 42 原子分子 = 9,10,23）:")
    for t in (1, 2, 3, 4, 5):
        report(["O", "X", "K"], (9 * t, 10 * t, 23 * t))
    print("\n全 9 元素 97 原子分子的缩放:")
    base = [3, 8, 15, 10, 1, 0, 36, 22, 2]
    for t in (1, 2):
        report(P.ORDER, [x * t for x in base])
    print("\n便于连接的比例随机试算:")
    for feed in [(18, 20, 46), (9, 10, 24), (9, 10, 23), (12, 13, 31), (6, 7, 15),
                 (9, 10, 22), (9, 10, 25), (18, 20, 45), (18, 20, 47)]:
        report(["O", "X", "K"], feed, budget=1_000_000)
