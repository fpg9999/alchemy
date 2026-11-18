# -*- coding: utf-8 -*-
"""T68 statistics for documentation."""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, "t68_data.json"), encoding="utf-8"))
mols = data["molecules"] if isinstance(data, dict) else data
print("n_mol", len(mols))
print("total_atoms", sum(m["n_atoms"] for m in mols))
print("n_skel", sum(len(m["skeletons"]) for m in mols))
print("n_bridge", sum(len(m["bridges"]) for m in mols))
print("n_blocks", sum(len(s["blocks"]) for m in mols for s in m["skeletons"]))
print("n_fusion_bonds", sum(s.get("n_fusion_bonds", 0) for m in mols for s in m["skeletons"]))
print("n_fusion_skel", sum(1 for m in mols for s in m["skeletons"] if s.get("n_fusion_bonds")))
fam = collections.Counter(m["family_zh"] for m in mols)
print("mol_family", dict(fam))
blk = collections.Counter()
for m in mols:
    for s in m["skeletons"]:
        for b in s["blocks"]:
            blk[b["lib_formula"] if b.get("in_lib") else "LIB_OUTSIDE:" + b["formula"]] += 1
print("block_forms")
for k, v in blk.most_common():
    print("   ", k, v)
print("block_forms_all_in_lib", all(not k.startswith("LIB_OUTSIDE") for k in blk))
dek = collections.Counter()
for m in mols:
    for k, v in (m.get("deco_stats") or {}).items():
        dek[k] += v
print("deco_sum", dict(dek))
bt = collections.Counter()
for m in mols:
    for b in m["bridges"]:
        bt[b["kind"]] += 1
        for t in b["types"]:
            bt["type:" + t] += 1
print("bridge_kinds", dict(bt))
nf = [m for m in mols if any(s.get("n_fusion_bonds") for s in m["skeletons"])]
print("mol_with_fusion", [m["mid"] for m in nf])
print("mol_zero_bridge", [m["mid"] for m in mols if not m["bridges"]])
print("exp_count", collections.Counter(m["exp"] for m in mols))
print("n_atoms_dist", collections.Counter(m["n_atoms"] for m in mols))
print("n_skel_dist", collections.Counter(len(m["skeletons"]) for m in mols))
for m in mols:
    print("%s | %s | %d atoms | %d skel | %d bridge | %s | skel=%s" % (
        m["mid"], m["formula"], m["n_atoms"], len(m["skeletons"]),
        len(m["bridges"]), m["family_zh"],
        " + ".join("%s(%s)" % (s["formula"], ",".join(b["lib_formula"] for b in s["blocks"]))
                   for s in m["skeletons"])))
