# -*- coding: utf-8 -*-
"""t22b_verify.py：严格验证扩展端帽（含 2 价双键端帽）交换产物"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v2
from t22_natural_caps2 import analyse, try_attach

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
byname = {r["formula"]: r for r in cat}
res = json.load(open(BASE + r"\t22_natural_caps2.json", encoding="utf-8"))
out = []
for e in res["new_examples"][:10]:
    ia = analyse(byname[e["A"]])
    ib = analyse(byname[e["B"]])
    capsA = [(ia["atoms"][i], c) for i, c in ia["caps"]]
    capsB = [(ib["atoms"][i], c) for i, c in ib["caps"]]
    for who, info, newcaps, prod in (("A'", ia, capsB, e["prodA"]), ("B'", ib, capsA, e["prodB"])):
        att = try_attach(info, newcaps)
        if att is None:
            out.append({"product": prod, "attach": False})
            print(who, prod, "ATTACH FAIL")
            continue
        place0, edges0, capids = att
        skel = list(info["skel"])
        remap = {old_i: k for k, old_i in enumerate(skel)}
        atoms = [info["atoms"][i] for i in skel] + [el for el, _ in newcaps]
        ncap = len(newcaps)
        capidx = {capids[t]: len(skel) + t for t in range(ncap)}
        place2 = {remap[i]: place0[i] for i in skel}
        for t in range(ncap):
            place2[len(skel) + t] = place0[capids[t]]
        edges = [[remap[i], remap[j], m] for (i, j, m) in info["bonds"]]
        for (si, idx, m) in edges0:
            edges.append([remap[si], capidx[idx], m])
        ok, msg = pot_v2.validate_place(place2, atoms, edges)
        out.append({"parent": e["A"] if who == "A'" else e["B"], "product": prod,
                    "validate": ok, "msg": msg, "in_catalog": prod in byname})
        print(who, "→", prod, "validate", ok, msg, "in_cat", prod in byname, flush=True)
json.dump(out, open(BASE + r"\t22_verified.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t22_verified.json")
