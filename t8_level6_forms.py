# -*- coding: utf-8 -*-
"""t8_level6_forms.py
研究「三价元素（O/P/K）彼此结合完毕、只剩一根键」时的组件形态。
= 6 级子过程（只连异类 3 价原子，距离 6）结束时，各连通组件的形态库。
分类：{O,P} / {O,K} / {P,K} / {O,P,K} 四种元素池情况。
输出：t8_forms.json（每个形态：元素、键、rem、公式、活跃数、坐标摆放）
"""
import json
import sys
from collections import Counter, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

TYPES = ("O", "P", "K")
BASE = r"G:\AI work\deepseek\work1\alchemy"


def level6_components(counts):
    atoms = []
    for e, c in zip(TYPES, counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return []
    rem = [3] * n
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atoms[i], atoms[j])
            fam[i][j] = fam[j][i] = P.family_rank(atoms[i], atoms[j])

    def comps():
        comp = [-1] * n
        groups = []
        for s in range(n):
            if comp[s] != -1:
                continue
            cid = len(groups)
            comp[s] = cid
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v in adj[u]:
                    if comp[v] == -1:
                        comp[v] = cid
                        st.append(v)
                        mem.append(v)
            groups.append(mem)
        dists = []
        for mem in groups:
            d = {}
            for s in mem:
                dd = {s: 0}
                dq = deque([s])
                while dq:
                    u = dq.popleft()
                    for v in adj[u]:
                        if v not in dd:
                            dd[v] = dd[u] + 1
                            dq.append(v)
                d[s] = dd
            dists.append(d)
        return comp, groups, dists

    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3 or dt[i][j] != 6:
                    continue
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj))
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    comp, groups, _ = comps()
    out = []
    for g in groups:
        at = [atoms[i] for i in g]
        ed = []
        for a in range(len(g)):
            for b in range(a + 1, len(g)):
                m = bond[g[a]][g[b]]
                if m:
                    ed.append([a, b, m])
        out.append({"atoms": at, "edges": ed, "rems": [rem[i] for i in g],
                    "label": P.mol_label(at, [tuple(e) for e in ed])})
    return out


def formula_of(atoms):
    cnt = Counter(atoms)
    return "".join(e + (str(cnt[e]) if cnt[e] > 1 else "") for e in TYPES if cnt[e])


def main():
    forms = {}     # key -> dict
    pool_stats = {}
    pools = {
        "OP": [("O", "P")],
        "OK": [("O", "K")],
        "PK": [("P", "K")],
        "OPK": None,
    }
    # 各池的计数网格
    for name, pair in [("OP", ("O", "P")), ("OK", ("O", "K")), ("PK", ("P", "K"))]:
        stats = Counter()
        a, b = pair
        for na in range(0, 19):
            for nb in range(0, 19):
                if na + nb == 0:
                    continue
                counts = {"O": 0, "P": 0, "K": 0}
                counts[a] = na
                counts[b] = nb
                comps = level6_components((counts["O"], counts["P"], counts["K"]))
                for c in comps:
                    key = (c["label"], tuple(sorted(c["rems"])), tuple(sorted(c["atoms"])))
                    if key not in forms:
                        forms[key] = {
                            "atoms": c["atoms"], "edges": c["edges"], "rems": c["rems"],
                            "formula": formula_of(c["atoms"]),
                            "size": len(c["atoms"]), "active": sum(1 for r in c["rems"] if r > 0),
                            "types": "".join(sorted(set(c["atoms"]))),
                            "pool": [],
                        }
                    forms[key]["pool"].append(name)
                stats[len(comps)] += 1
        pool_stats[name] = len(stats)

    # 三类池（各 1..12）
    for nO in range(1, 13):
        for nP in range(1, 13):
            for nK in range(1, 13):
                comps = level6_components((nO, nP, nK))
                for c in comps:
                    key = (c["label"], tuple(sorted(c["rems"])), tuple(sorted(c["atoms"])))
                    if key not in forms:
                        forms[key] = {
                            "atoms": c["atoms"], "edges": c["edges"], "rems": c["rems"],
                            "formula": formula_of(c["atoms"]),
                            "size": len(c["atoms"]), "active": sum(1 for r in c["rems"] if r > 0),
                            "types": "".join(sorted(set(c["atoms"]))),
                            "pool": [],
                        }
                    if "OPK" not in forms[key]["pool"]:
                        forms[key]["pool"].append("OPK")

    # 汇总 + 尝试摆放
    import pot_v2
    out = []
    for key, f in forms.items():
        place = pot_v2.embed_mol2(f["atoms"], f["edges"])
        f["place"] = {str(k): list(v) for k, v in place.items()} if place else None
        f["rem_dist"] = dict(Counter(f["rems"]))
        f["bond_count"] = sum(e[2] for e in f["edges"])
        f["pools"] = sorted(set(f["pool"]))
        out.append(f)
    out.sort(key=lambda x: (x["types"], x["size"], x["formula"]))
    json.dump(out, open(BASE + r"\t8_forms.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 控制台摘要
    by_types = Counter(x["types"] for x in out)
    print("total forms:", len(out))
    print("by types:", dict(by_types))
    for types in sorted(by_types):
        sub = [x for x in out if x["types"] == types]
        print(f"\n[{types}] {len(sub)} forms:")
        for x in sub:
            print(f"  {x['formula']:12s} size={x['size']:2d} active={x['active']:2d} rem={x['rem_dist']} place={'ok' if x['place'] else 'NONE'} pools={x['pools']}")


if __name__ == "__main__":
    main()
