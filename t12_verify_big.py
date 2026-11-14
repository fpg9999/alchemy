# -*- coding: utf-8 -*-
"""lead 复核：140 原子新纪录分子是否可严格摆放"""
import json
import sys
import time
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
for fn, budget in [("t12c_big140.json", 8_000_000), ("t12c_big108.json", 4_000_000)]:
    d = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
    rec = d[0] if isinstance(d, list) else d
    atoms = rec["atoms"]
    edges = [tuple(e) for e in rec["edges"]]
    t0 = time.time()
    place = pot_v2.embed_mol2(atoms, edges, max_nodes=budget)
    dt = time.time() - t0
    if place is None:
        print(fn, rec["formula"], "natoms", len(atoms), "摆放 FAIL", f"{dt:.1f}s")
        continue
    ok, msg = pot_v2.validate_place(place, atoms, edges)
    print(fn, rec["formula"], "natoms", len(atoms), "摆放 ok" if place else "FAIL",
          f"{dt:.1f}s", "严格校验:", ok, msg)
