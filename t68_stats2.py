# -*- coding: utf-8 -*-
"""T68: extra details + markdown table for docs."""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, "t68_data.json"), encoding="utf-8"))
mols = data["molecules"] if isinstance(data, dict) else data
forms = json.load(open(os.path.join(HERE, "t8_forms.json"), encoding="utf-8"))
order = [f["formula"] for f in forms]
libidx = {f: i + 1 for i, f in enumerate(order)}

used = collections.Counter()
for m in mols:
    for s in m["skeletons"]:
        for b in s["blocks"]:
            used[b["lib_formula"]] += 1
print("distinct_block_forms", len(used))
print("unused_forms", [(libidx[f], f) for f in order if f not in used])
print("bridge_atoms", sum(b["k"] for m in mols for b in m["bridges"]))
print("block_sizes", sum(b["size"] for m in mols for s in m["skeletons"] for b in s["blocks"]))
print("singleton_P", sum(1 for m in mols for s in m["skeletons"] if s["n"] == 1))
print("max_blocks_per_skel", max(len(s["blocks"]) for m in mols for s in m["skeletons"]))
print("mol_same_skel_all", sum(1 for m in mols if len(set(s["formula"] for s in m["skeletons"])) == 1))
print("mol_multi_types", sum(1 for m in mols if len(set(s["formula"] for s in m["skeletons"])) > 1))
# bridge kind per molecule distribution
print("bridge_kind_dist", collections.Counter(
    collections.Counter(b["kind"] for b in m["bridges"]).most_common(1)[0][0]
    if m["bridges"] else "无桥" for m in mols))

rows = []
for m in mols:
    sk = " + ".join("%s（%s）" % (s["formula"], "+".join(
        b["lib_formula"] for b in s["blocks"])) for s in m["skeletons"])
    if any(s.get("n_fusion_bonds") for s in m["skeletons"]):
        sk += " ※含 1 根 0 级 P–P 融合键"
    rows.append("| %s | %s | %d | %d | %d | %s | %s |" % (
        m["mid"], m["formula"], m["n_atoms"], len(m["skeletons"]),
        len(m["bridges"]), m["exp"], sk))
open(os.path.join(HERE, "t68_table.md"), "w", encoding="utf-8").write("\n".join(rows))
print("table lines", len(rows))

# block frequency table sorted
print("freq_table")
for f, c in used.most_common():
    print("   %s #%d %d" % (f, libidx[f], c))

# bridge type counts per molecule kind
print("deco_check")
dek = collections.Counter()
for m in mols:
    for k, v in (m.get("deco_stats") or {}).items():
        dek[k] += v
print(dict(dek))
