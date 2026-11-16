# -*- coding: utf-8 -*-
"""t42_random_ties.py：在「任意并列分辨率」下复核
  A) 终态三价组件 = 自身 6 级块之并（融合/自加固结构定理）是否始终成立；
  B) 6 级块在任意并列下是否仍属于 38 库（统计出库比例与例子）；
样本：随机目录物质 + O3P5K2 专项 + 若干大分子。
"""
import json
import random
import sys
import time
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra
import t39_library_verify as V

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = P.VAL


def simulate_capture(atoms, rng):
    n = len(atoms)
    if sum(VAL[e] for e in atoms) % 2:
        return None, None
    rem = [VAL[e] for e in atoms]
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

    def triv_comps():
        idx = [i for i in range(n) if atoms[i] in TRI]
        m = len(idx)
        seen = [False] * m
        out = []
        for s in range(m):
            if seen[s]:
                continue
            seen[s] = True
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for b in range(m):
                    if not seen[b] and bond[idx[u]][idx[b]] > 0:
                        seen[b] = True
                        st.append(b)
                        mem.append(b)
            mem = sorted(idx[k] for k in mem)
            ats = [atoms[v] for v in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    mm = bond[mem[a]][mem[b]]
                    if mm:
                        es.append((a, b, mm))
            out.append({"mem": frozenset(mem), "atoms": ats, "edges": es})
        return out

    level6 = None
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
        if not cands:
            break
        if level6 is None and not any6:
            level6 = triv_comps()
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = rng.choice(tied)
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None, None
    if level6 is None:
        level6 = triv_comps()
    return level6, triv_comps()


def check_once(atoms, rng, libkeys):
    level6, final = simulate_capture(atoms, rng)
    if level6 is None:
        return None
    cover_ok = True
    for fc in final:
        blocks = [b for b in level6 if b["mem"] <= fc["mem"]]
        cov = set()
        for b in blocks:
            cov |= b["mem"]
        if not blocks or cov != set(fc["mem"]):
            cover_ok = False
            break
    bad = []
    for b in level6:
        if V.block_label(b["atoms"], b["edges"]) not in libkeys:
            bad.append(b)
    return cover_ok, bad


def main():
    t0 = time.time()
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    rng = random.Random(12345)
    sample = rng.sample(cat, 600)
    stats = Counter()
    outside = []
    # 小分子样本：每种 20 个随机并列
    for rec in sample:
        atoms = list(rec["atoms"])
        for t in range(20):
            r = check_once(atoms, random.Random(t * 31 + 7), libkeys)
            if r is None:
                stats["sim_fail"] += 1
                continue
            cover_ok, bad = r
            stats["runs"] += 1
            stats["cover_ok"] += cover_ok
            if bad:
                stats["runs_with_outside_block"] += 1
                if len(outside) < 10:
                    outside.append({"formula": rec["formula"],
                                    "blocks": [{"atoms": b["atoms"],
                                                "edges": [list(e) for e in b["edges"]]}
                                               for b in bad]})
    # O3P5K2 专项
    o3 = P.vec_to_atoms(P.parse_formula("O3P5K2"), P.ORDER)
    o3_stats = Counter()
    o3_classes = Counter()
    for t in range(2000):
        r = check_once(o3, random.Random(t), libkeys)
        if r is None:
            o3_stats["fail"] += 1
            continue
        cover_ok, bad = r
        o3_stats["runs"] += 1
        o3_stats["cover_ok"] += cover_ok
        o3_stats["with_outside"] += bool(bad)
    # 大分子（历史纪录结构）
    big = []
    for fn in ["t12c_big140.json", "t12c_big108.json", "t13_new_record.json",
               "t13_scale3.json", "t13_scale4.json"]:
        try:
            d = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
            rec = d[0] if isinstance(d, list) else d
            if isinstance(rec, dict) and rec.get("atoms"):
                big.append((fn, list(rec["atoms"])))
        except Exception:
            pass
    big_stats = Counter()
    for fn, atoms in big:
        for t in range(3):
            r = check_once(atoms, random.Random(t + 1), libkeys)
            if r is None:
                big_stats["fail"] += 1
                continue
            cover_ok, bad = r
            big_stats["runs"] += 1
            big_stats["cover_ok"] += cover_ok
            big_stats["with_outside"] += bool(bad)
            if bad and len(outside) < 12:
                outside.append({"formula": fn, "blocks": [{"atoms": b["atoms"],
                                                           "size": len(b["atoms"])}
                                                          for b in bad]})
    out = {"sample_substances": len(sample), "runs_each": 20,
           "small": dict(stats),
           "outside_examples": outside,
           "o3p5k2": dict(o3_stats),
           "big_molecules": [f for f, _ in big],
           "big": dict(big_stats),
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open(BASE + r"\t42_random_ties.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "outside_examples"},
                     ensure_ascii=False, indent=1))
    print("outside examples:", json.dumps(outside[:2], ensure_ascii=False)[:500])
    print("saved t42_random_ties.json")


if __name__ == "__main__":
    main()
