# -*- coding: utf-8 -*-
"""修正 t61_fix_invalid.py 的重排映射 bug（inv 应为 {perm[i]: i}），重算 4 个巨型分子的摆放。"""
import json
import random
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
TARGETS = {"O8X6CP13W4K6A2", "O5X3C2P14W4LK5A2F3", "O8X6P13W4K6AF", "O8X5P13W4K5A4"}


def try_embed(atoms, edges, seed, max_nodes):
    rng = random.Random(seed)
    n = len(atoms)
    perm = list(range(n))
    rng.shuffle(perm)
    new_atoms = [atoms[perm[i]] for i in range(n)]
    # 旧编号 k -> 新编号 i（perm[i]==k）
    old_to_new = {perm[i]: i for i in range(n)}
    new_edges = [(old_to_new[a], old_to_new[b], m) for (a, b, m) in edges]
    place = pot_v2.embed_mol2(new_atoms, [tuple(e) for e in new_edges], max_nodes=max_nodes)
    if place is None:
        return None
    ok, _ = pot_v2.validate_place(place, new_atoms, [tuple(e) for e in new_edges])
    if not ok:
        return None
    back = {}
    for i in range(n):
        back[perm[i]] = place[i]
    return back


def main():
    data = json.load(open(BASE + r"\t61_hex_layouts.json", encoding="utf-8"))
    fixed = 0
    for rec in data["items"]:
        if rec["formula"] not in TARGETS:
            continue
        atoms, edges = rec["atoms"], [tuple(e) for e in rec["edges"]]
        t0 = time.time()
        place = None
        method = None
        for seed in range(24):
            p = try_embed(atoms, edges, seed, 2_000_000)
            if p is not None:
                place, method = p, "embed_mol2_perm_seed%d_fixed" % seed
                break
        if place is None:
            print("FAILED", rec["formula"])
            continue
        pos = [tuple(place[k]) for k in range(len(atoms))]
        bonds = []
        for (a, b, m) in edges:
            d = (pos[b][0] - pos[a][0], pos[b][1] - pos[a][1])
            typ = P.classify_offset(d)
            mid = None
            if typ == "L":
                mid = (pos[a][0] + d[0] // 2, pos[a][1] + d[1] // 2)
            bonds.append({"a": a, "b": b, "m": m, "type": typ,
                          "mid": list(mid) if mid else None})
        xs = [p[0] for p in pos]
        ys = [p[1] for p in pos]
        rec["place"] = pos
        rec["bonds"] = bonds
        rec["bbox"] = [min(xs), min(ys), max(xs), max(ys)]
        rec["valid"] = True
        rec["layout_method"] = method
        rec["layout_seconds"] = round(time.time() - t0, 2)
        ok, msg = pot_v2.validate_place(place, atoms, edges)
        print("FIXED", rec["formula"], method, "%.2fs" % rec["layout_seconds"],
              "validate", ok, msg)
        fixed += 1
    data["summary"]["fixed_extra"] = data["summary"].get("fixed_extra", 0)
    data["summary"]["refix_note"] = "4 个 39/40 原子分子的重排映射已修正（inv={perm[i]:i}）"
    json.dump(data, open(BASE + r"\t61_hex_layouts.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("fixed", fixed)


if __name__ == "__main__":
    main()
