# -*- coding: utf-8 -*-
"""对 t61_hex_layouts.py 中 4 个未成功摆放的 39/40 原子大分子做加强搜索：
随机原子标号重排 + 多种子 embed_mol2 + pot_all.embed_mol 大预算。"""
import json
import random
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
data = json.load(open(BASE + r"\t61_hex_layouts.json", encoding="utf-8"))


def try_embed(atoms, edges, seed, max_nodes):
    rng = random.Random(seed)
    n = len(atoms)
    perm = list(range(n))
    rng.shuffle(perm)
    new_atoms = [atoms[perm[i]] for i in range(n)]
    # 旧编号 k -> 新编号 i（perm[i]==k）；修正原 inv={i:perm[i]} 的映射 bug
    inv = {perm[i]: i for i in range(n)}
    new_edges = []
    for (a, b, m) in edges:
        new_edges.append((inv[a], inv[b], m))
    place = pot_v2.embed_mol2(new_atoms, [tuple(e) for e in new_edges], max_nodes=max_nodes)
    if place is None:
        return None
    ok, _ = pot_v2.validate_place(place, new_atoms, [tuple(e) for e in new_edges])
    if not ok:
        return None
    # 映射回原编号
    back = {}
    for i in range(n):
        back[perm[i]] = place[i]
    return back


fixed = 0
for rec in data["items"]:
    if rec["valid"]:
        continue
    atoms, edges = rec["atoms"], [tuple(e) for e in rec["edges"]]
    print("trying", rec["formula"], rec["n_atoms"], flush=True)
    t0 = time.time()
    place = None
    method = None
    # 1) 大预算原顺序
    p = pot_v2.embed_mol2(atoms, edges, max_nodes=20_000_000)
    if p is not None and pot_v2.validate_place(p, atoms, edges)[0]:
        place, method = p, "embed_mol2_20M"
    # 2) 随机重排多种子
    if place is None:
        for seed in range(12):
            p = try_embed(atoms, edges, seed, 1_500_000)
            if p is not None:
                place, method = p, "embed_mol2_perm_seed%d" % seed
                break
    # 3) pot_all
    if place is None:
        p = P.embed_mol(atoms, edges, max_nodes=20_000_000)
        if p is not None and pot_v2.validate_place(p, atoms, edges)[0]:
            place, method = p, "pot_all_embed_20M"
    if place is not None:
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
        fixed += 1
        print("  FIXED", method, rec["layout_seconds"], "s", flush=True)
    else:
        print("  STILL INVALID", rec["layout_seconds"], "s", flush=True)

data["summary"]["n_valid"] = sum(1 for r in data["items"] if r["valid"])
data["summary"]["n_invalid"] = sum(1 for r in data["items"] if not r["valid"])
data["summary"]["invalid"] = [r["formula"] for r in data["items"] if not r["valid"]]
data["summary"]["fixed_extra"] = fixed
json.dump(data, open(BASE + r"\t61_hex_layouts.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("fixed", fixed, "remaining invalid", data["summary"]["invalid"])
