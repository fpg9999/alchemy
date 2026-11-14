# -*- coding: utf-8 -*-
"""t36b_both_relaxed.py：放宽匹配——多三价元素组件去掉同元素键后，其跨类子骨架匹配 38 库；
单三价元素组件精确匹配 7×3 库。
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

multi_keys = {}
for f in t8:
    ats = f["atoms"]
    if len(set(ats) & TRI) >= 2:
        multi_keys[wl_key(ats, [tuple(e) for e in f["edges"]])] = f["formula"]

single_templates = [
    ("单原子", ["A"], []),
    ("单键二聚", ["A", "A"], [(0, 1, 1)]),
    ("双键二聚", ["A", "A"], [(0, 1, 2)]),
    ("三键二聚", ["A", "A"], [(0, 1, 3)]),
    ("三元链", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1)]),
    ("三元环(全单)", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    ("三元环(一单双)", ["A", "A", "A"], [(0, 1, 2), (1, 2, 1), (0, 2, 1)]),
]
single_keys = {wl_key(a, [tuple(e) for e in es]): n for n, a, es in single_templates}


def components(rec):
    atoms = rec["atoms"]
    n = len(atoms)
    adj = [[] for _ in range(n)]
    em = {}
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        em[tuple(sorted((i, j)))] = m
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
                m = em.get(tuple(sorted((mem[a], mem[b]))))
                if m:
                    es.append((a, b, m))
        out.append({"mem": mem, "atoms": [atoms[i] for i in mem], "edges": es})
    return out


def cross_blocks(comp):
    """去掉同元素键后，按跨类边分连通块，返回每个块的 (atoms, edges)"""
    ats = comp["atoms"]
    # 只保留跨元素的边
    es = [(i, j, m) for (i, j, m) in comp["edges"] if ats[i] != ats[j]]
    n = len(ats)
    adj = [[] for _ in range(n)]
    for (i, j, m) in es:
        adj[i].append(j)
        adj[j].append(i)
    seen = set()
    blocks = []
    for s in range(n):
        if s in seen:
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
        bs = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = {tuple(sorted((x, y))): mm for (x, y, mm) in es}.get(tuple(sorted((mem[a], mem[b]))))
                if m:
                    bs.append((a, b, m))
        blocks.append({"atoms": [ats[i] for i in mem], "edges": bs})
    return blocks


hits = []
stats = Counter()
examples = []
for rec in cat:
    cs = components(rec)
    if len(cs) < 2:
        continue
    singles = []
    multi_blocks = []
    for c in cs:
        types = set(c["atoms"]) & TRI
        if len(types) == 1:
            k = wl_key(c["atoms"], [tuple(e) for e in c["edges"]])
            if k in single_keys:
                singles.append({"formula": "".join(c["atoms"]), "lib": single_keys[k]})
        else:
            for b in cross_blocks(c):
                k = wl_key(b["atoms"], [tuple(e) for e in b["edges"]])
                if k in multi_keys:
                    multi_blocks.append({"formula": "".join(sorted(b["atoms"])),
                                         "lib": multi_keys[k]})
    if singles and multi_blocks:
        stats["同时包含"] += 1
        hit = {"formula": rec["formula"], "natoms": len(rec["atoms"]),
               "components": [{"formula": "".join(sorted(c["atoms"])),
                               "types": sorted(set(c["atoms"]) & TRI),
                               "size": len(c["atoms"])} for c in cs],
               "single": singles, "multi": multi_blocks}
        hits.append(hit)
        if len(examples) < 20:
            examples.append(hit)

print("同时包含:", stats["同时包含"])
hits.sort(key=lambda h: (h["natoms"], h["formula"]))
for h in hits[:20]:
    print(h["formula"], "natoms", h["natoms"], "single", h["single"], "multi", h["multi"], "comps", h["components"])
json.dump({"n_hits": len(hits), "hits": hits},
          open(BASE + r"\t36_both_skeletons.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t36_both_skeletons.json")
