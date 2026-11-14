# -*- coding: utf-8 -*-
"""t36_both_skeletons.py：寻找同时包含
  (A) 38 库中的多三价元素骨架（≥2 种三价元素）
  (B) 7×3 单三价元素骨架库中的骨架
的物质。
"""
import json
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))

# 38 库 key（仅取多三价元素形态）
multi_keys = {}
for f in t8:
    ats = f["atoms"]
    if len(set(ats) & TRI) >= 2:
        k = wl_key(ats, [tuple(e) for e in f["edges"]])
        multi_keys[k] = f["formula"]

# 7 个单元素骨架形态 × 3 种元素（键型由价数规则决定；这里用实际形态）
single_templates = [
    ("单原子", [], []),
    ("单键二聚", ["A", "A"], [(0, 1, 1)]),
    ("双键二聚", ["A", "A"], [(0, 1, 2)]),
    ("三键二聚", ["A", "A"], [(0, 1, 3)]),
    ("三元链", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1)]),
    ("三元环(全单)", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    ("三元环(一单双)", ["A", "A", "A"], [(0, 1, 2), (1, 2, 1), (0, 2, 1)]),
]
single_keys = {}
for name, ats, es in single_templates:
    k = wl_key(ats, [tuple(e) for e in es])
    single_keys[k] = name


def comps_of(rec):
    atoms = rec["atoms"]
    n = len(atoms)
    adj = [[] for _ in range(n)]
    edges = {tuple(sorted((e[0], e[1]))): e[2] for e in rec["edges"]}
    for (i, j) in edges:
        if atoms[i] in TRI and atoms[j] in TRI:
            adj[i].append(j)
            adj[j].append(i)
    seen = set()
    out = []
    for s in range(n):
        if s in seen or atoms[s] not in TRI:
            continue
        st = [s]
        seen.add(s)
        mem = [s]
        while st:
            u = st.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
                    mem.append(v)
        mem.sort()
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                ei, ej = mem[a], mem[b]
                m = edges.get(tuple(sorted((ei, ej))))
                if m:
                    es.append((a, b, m))
        out.append({"mem": mem, "atoms": [atoms[i] for i in mem],
                    "edges": es, "formula": "".join(sorted(atoms[i] for i in mem))})
    return out


hits = []
stats = Counter()
examples = []
for rec in cat:
    cs = comps_of(rec)
    stats["总物质"] += 1
    if len(cs) < 2:
        continue
    multi = []
    single = []
    for c in cs:
        types = set(c["atoms"]) & TRI
        k = wl_key(c["atoms"], [tuple(e) for e in c["edges"]])
        if len(types) >= 2 and k in multi_keys:
            multi.append({**c, "lib": multi_keys[k]})
        if len(types) == 1 and k in single_keys:
            single.append({**c, "lib": single_keys[k]})
    if multi and single:
        stats["同时包含两类骨架"] += 1
        hits.append({"formula": rec["formula"], "natoms": len(rec["atoms"]),
                     "components": [{"formula": c["formula"], "size": len(c["atoms"]),
                                     "types": sorted(set(c["atoms"]) & TRI),
                                     "lib": c.get("lib")} for c in cs],
                     "multi": [{"formula": c["formula"], "lib": c["lib"], "size": len(c["atoms"])} for c in multi],
                     "single": [{"formula": c["formula"], "lib": c["lib"], "size": len(c["atoms"])} for c in single]})
        if len(examples) < 20:
            examples.append(hits[-1])

print("总物质:", stats["总物质"], "同时包含两类骨架:", stats["同时包含两类骨架"])
hits.sort(key=lambda h: (h["natoms"], h["formula"]))
print("\n最小例子:")
for h in hits[:15]:
    print(h["formula"], "natoms", h["natoms"], "multi", h["multi"], "single", h["single"])
json.dump({"n_hits": len(hits), "hits": hits,
           "multi_keys": {str(k): v for k, v in multi_keys.items()},
           "single_keys": {str(k): v for k, v in single_keys.items()}},
          open(BASE + r"\t36_both_skeletons.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t36_both_skeletons.json")
