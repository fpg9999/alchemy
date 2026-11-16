# -*- coding: utf-8 -*-
"""t40_verify_fusion.py：在全目录（84,225 物质）上复核
  A) 每种物质的大锅反应（规则 1~9，正式 pot_v3 口径，默认并列裁决）的「6 级中间态骨架」
     是否全部属于 38 库；
  B) 终态三价连通块是否 = 该物质自身 6 级块之并 + 0 级同类键融合/自加固
     （即「终态骨架能由中间态骨架融合或自加固得到」）。
输出：t40_verify_fusion.json
"""
import json
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


def simulate_capture(atoms):
    """规则 1~9（pot_v3 同 key，tied[0]），返回 (level6_blocks, final_comps)。
    level6_blocks: [(atoms, edges)] 6 级结束时三价诱导子图的连通块；
    final_comps: [(atoms, edges)] 终态三价诱导子图连通块。"""
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
        i, j = tied[0]
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
    final = triv_comps()
    return level6, final


def main():
    t0 = time.time()
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    stats = Counter()
    bad_blocks = []
    cover_bad = []
    block_sizes = Counter()
    n = 0
    all_blocks = {}
    for rec in cat:
        atoms = list(rec["atoms"])
        level6, final = simulate_capture(atoms)
        if level6 is None:
            stats["sim_fail"] += 1
            continue
        n += 1
        # A) 6 级块是否都在 38 库
        ok_a = True
        for blk in level6:
            block_sizes[len(blk["atoms"])] += 1
            k = V.block_label(blk["atoms"], blk["edges"])
            all_blocks.setdefault(k, {"atoms": blk["atoms"],
                                      "edges": [list(e) for e in blk["edges"]],
                                      "size": len(blk["atoms"]), "example": rec["formula"]})
            if k not in libkeys:
                ok_a = False
                if len(bad_blocks) < 20:
                    bad_blocks.append({"formula": rec["formula"], "atoms": blk["atoms"],
                                       "edges": [list(e) for e in blk["edges"]]})
        stats["level6_all_in_lib" if ok_a else "level6_bad"] += 1
        # B) 终态三价组件 = 自身 6 级块之并（结构定理）
        ok_b = True
        for fc in final:
            blocks = [b for b in level6 if b["mem"] <= fc["mem"]]
            cover = set()
            for b in blocks:
                cover |= b["mem"]
            if not blocks or cover != set(fc["mem"]):
                ok_b = False
                if len(cover_bad) < 20:
                    cover_bad.append({"formula": rec["formula"],
                                      "final_size": len(fc["mem"]),
                                      "blocks": [len(b["mem"]) for b in blocks]})
                break
        stats["final_cover_ok" if ok_b else "final_cover_bad"] += 1
        stats["substances"] += 1
        if n % 10000 == 0:
            print(f"  {n} ... {time.time()-t0:.0f}s", flush=True)
    print(dict(stats))
    print("6 级块大小分布:", dict(sorted(block_sizes.items())))
    out = {"substances": stats["substances"], "sim_fail": stats["sim_fail"],
           "level6_all_in_lib": stats["level6_all_in_lib"],
           "level6_bad": stats["level6_bad"],
           "final_cover_ok": stats["final_cover_ok"],
           "final_cover_bad": stats["final_cover_bad"],
           "distinct_level6_blocks": len(all_blocks),
           "block_sizes": dict(sorted(block_sizes.items())),
           "bad_blocks": bad_blocks,
           "cover_bad": cover_bad,
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open(BASE + r"\t40_verify_fusion.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t40_verify_fusion.json")


if __name__ == "__main__":
    main()
