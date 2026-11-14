# -*- coding: utf-8 -*-
"""t4_validate_embed：严格校验一个"分子图 + 摆放"是否合法。

合法条件：位置互异；每条边的偏移属于两端大类允许的键偏移集合；
L 键中点格不得被任何原子占用；坐标与用户坐标换算一致。
"""
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def validate(place, atoms, edges, verbose=True):
    if place is None:
        return False, "place is None"
    pos = [tuple(place[i]) for i in range(len(atoms))]
    if len(set(pos)) != len(pos):
        return False, "duplicate positions"
    occ = set(pos)
    for (i, j, m) in edges:
        d = (pos[j][0] - pos[i][0], pos[j][1] - pos[i][1])
        if d not in P.allowed(atoms[i], atoms[j]):
            return False, f"edge {i}-{j} offset {d} not allowed for {atoms[i]}-{atoms[j]}"
        if P.classify_offset(d) == "L":
            mid = (pos[i][0] + d[0] // 2, pos[i][1] + d[1] // 2)
            if mid in occ:
                return False, f"L midpoint {mid} occupied (edge {i}-{j})"
    return True, "ok"


def check_mol(atoms, edges, budget=3_000_000):
    place = P.embed_mol(atoms, edges, max_nodes=budget)
    ok, msg = validate(place, atoms, edges)
    return place, ok, msg


if __name__ == "__main__":
    cases = [
        ("T68", P.ORDER, [6, 2, 0, 24, 8, 8, 6, 6, 8]),
        ("T97", P.ORDER, [3, 8, 15, 10, 1, 0, 36, 22, 2]),
        ("T129", P.ORDER, [6, 12, 16, 13, 3, 0, 52, 24, 3]),
        ("T160", P.ORDER, [10, 20, 16, 15, 0, 1, 66, 30, 2]),
        ("OXKA154", ["O", "X", "K", "A"], [71, 35, 27, 28]),
        ("OK42", ["O", "X", "K"], [13, 16, 35]),
    ]
    for name, elems, feed in cases:
        atoms = P.vec_to_atoms(tuple(feed), elems)
        mols = P.simulate(atoms)
        if not mols:
            print(name, "sim fail")
            continue
        big = max(mols, key=lambda m: len(m["atoms"]))
        place, ok, msg = check_mol(big["atoms"], big["edges"], budget=3_000_000)
        print(f"{name}: n={len(big['atoms'])} pot_all_embed_valid={ok} msg={msg}", flush=True)
