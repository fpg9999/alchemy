# -*- coding: utf-8 -*-
"""t44_block_sampling.py：大投料（三价总数 14~60）的 6 级块抽样
目的：检查「不设原子数上限」时是否出现 t41 全分支穷举（≤12）之外的新中间态骨架。
方法：随机计数组合 + （默认并列 / 随机并列）各 1 次，只跑到 6 级结束，收集块形态。
输出：t44_block_sampling.json
"""
import json
import random
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra
import t39_library_verify as V

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = P.VAL


def level6_blocks(atoms, rng=None):
    n = len(atoms)
    rem = [VAL[e] for e in atoms]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]

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

    def blocks_now(groups):
        out = []
        for mem in groups:
            if not any(atoms[v] in TRI for v in mem):
                continue
            mem = sorted(mem)
            ats = [atoms[v] for v in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    m = bond[mem[a]][mem[b]]
                    if m:
                        es.append((a, b, m))
            out.append((ats, es))
        return out

    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
        cands = []
        any6 = False
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                if dt[i][j] == 6:
                    any6 = True
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append((key, i, j))
        if not any6:
            return blocks_now(groups)
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = rng.choice(tied) if rng is not None else tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1


def main():
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    found = set()
    r = json.load(open(BASE + r"\t41_all_intermediate.json", encoding="utf-8"))
    for b in r["blocks"]:
        found.add(V.block_label(b["atoms"], [tuple(e) for e in b["edges"]]))
    rng = random.Random(2026)
    sizes = Counter()
    total_blocks = 0
    runs = 0
    new = {}
    for t in range(300):
        total = rng.randint(14, 60)
        a = rng.randint(0, total)
        b = rng.randint(0, total - a)
        c = total - a - b
        atoms = []
        for e, cc in zip(("O", "P", "K"), (a, b, c)):
            atoms += [e] * cc
        for rngmode in (None, random.Random(t)):
            runs += 1
            for ats, es in level6_blocks(atoms, rngmode):
                total_blocks += 1
                sizes[len(ats)] += 1
                k = V.block_label(ats, es)
                if k not in found:
                    new.setdefault(k, {"atoms": ats, "edges": [list(e) for e in es],
                                       "size": len(ats), "composition": (a, b, c),
                                       "in_library": k in libkeys})
    out = {"runs": runs, "blocks": total_blocks,
           "max_trivalent_total": 60,
           "size_dist": dict(sorted(sizes.items())),
           "max_block_size": max(sizes),
           "new_classes_beyond_t41": list(new.values()),
           "note": "新类若都是库内形态且 size=13，则与 t41≤12 穷举 + 38 库互相印证"}
    json.dump(out, open(BASE + r"\t44_block_sampling.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "new_classes_beyond_t41"},
                     ensure_ascii=False, indent=1))
    for v in out["new_classes_beyond_t41"]:
        print("new class:", v["size"], v["composition"], "in_library", v["in_library"])
    print("saved t44_block_sampling.json")


if __name__ == "__main__":
    main()
