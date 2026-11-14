# -*- coding: utf-8 -*-
"""t7_tie_examples：枚举"并列裁决导致不同分子式多重集"的具体例子。

方法：对给定元素计数向量，做"并列分支 DFS"——每步若有多个 key 完全相同的候选对，
穷举所有选择；收集所有终态产物分子式多重集。若得到 ≥2 种 → 该投料对并列裁决敏感。

用途：给出 §7.4 所述 0.5% 并列歧义的**具体例子清单**（投料、两种产物、首次分歧点）。
"""
import itertools
import json
import os
import sys
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def run_ties(atom_list, max_leaves=5000):
    """返回 (outcomes: dict[outcome_tuple -> 次数], info)；
    info 含首次并列步数、并列候选数、是否超限。"""
    n = len(atom_list)
    rem0 = [P.VAL[e] for e in atom_list]
    if sum(rem0) % 2:
        return None
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = P.family_rank(atom_list[i], atom_list[j])

    outcomes = Counter()
    first_tie = {"step": None, "tied": None, "n_tied": 0}
    leaves = [0]
    over = [False]
    step = [0]

    def rec(bond, rem, adj, step_no):
        if over[0]:
            return
        # components
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
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
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
            # 终止：记录产物分子式多重集（若全部接满才有效）
            if any(r > 0 for r in rem):
                return
            # 计算产物
            seen = [-1] * n
            comps = []
            for s in range(n):
                if seen[s] != -1:
                    continue
                cid = len(comps)
                seen[s] = cid
                st = [s]
                mem = [s]
                while st:
                    u = st.pop()
                    for v in adj[u]:
                        if seen[v] == -1:
                            seen[v] = cid
                            st.append(v)
                            mem.append(v)
                comps.append(mem)
            forms = []
            for mem in comps:
                forms.append(P.formula_of([atom_list[i] for i in mem]))
            leaves[0] += 1
            if leaves[0] > max_leaves:
                over[0] = True
                return
            outcomes[tuple(sorted(forms))] += 1
            return
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        if len(tied) > 1 and first_tie["step"] is None:
            first_tie["step"] = step_no
            first_tie["tied"] = [(atom_list[i] + "-" + atom_list[j], i, j) for (i, j) in tied]
            first_tie["n_tied"] = len(tied)
        for (i, j) in tied:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            adj[i][j] = adj[i].get(j, 0) + 1
            adj[j][i] = adj[j].get(i, 0) + 1
            rec(bond, rem, adj, step_no + 1)
            adj[i][j] -= 1
            if adj[i][j] == 0:
                del adj[i][j]
            adj[j][i] -= 1
            if adj[j][i] == 0:
                del adj[j][i]
            rem[i] += 1
            rem[j] += 1
            bond[i][j] -= 1
            bond[j][i] -= 1
            if over[0]:
                return

    rec([[0] * n for _ in range(n)], list(rem0), [dict() for _ in range(n)], 0)
    info = dict(first_tie)
    info["over"] = over[0]
    info["n_leaves"] = leaves[0]
    return outcomes, info


def fmt_feed(counts):
    parts = []
    for e, c in zip(P.ORDER, counts):
        if c:
            parts.append(f"{e}{c}")
    return "".join(parts)


def analyze_feed(counts, max_leaves=5000):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    r = run_ties(atoms, max_leaves=max_leaves)
    if r is None:
        return None
    outcomes, info = r
    if len(outcomes) <= 1:
        return None
    return {
        "feed": list(counts), "feed_str": fmt_feed(counts), "T": len(atoms),
        "outcomes": [{"products": list(k), "count": v} for k, v in outcomes.items()],
        "first_tie": info,
    }


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def scan_range(args):
    T, limit = args
    found = []
    ncase = 0
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        res = analyze_feed(list(counts), max_leaves=800)
        if res:
            found.append(res)
            if len(found) >= limit:
                break
    return T, ncase, found


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "example"
    if what == "example":
        # 验证 T5/T6 里的例子：O3 F A2 W（O=3,F=1,A=2,W=1）
        counts = [3, 0, 0, 0, 1, 0, 0, 2, 1]
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        print("feed", counts, "T", len(atoms))
        print("  deterministic:", [P.formula_of(m["atoms"]) for m in (P.simulate(atoms) or [])])
        r = run_ties(atoms, max_leaves=20000)
        if r is None:
            print("  invalid (odd valence?)")
        else:
            outcomes, info = r
            print("  distinct outcomes:", len(outcomes))
            for k, v in outcomes.items():
                print("   ", k, "x", v)
            print("  first tie:", info.get("step"), info.get("tied"))
    elif what == "scan":
        Tmax = int(sys.argv[2]) if len(sys.argv) > 2 else 9
        jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) - 2)
        results = {}
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for T, ncase, found in ex.map(scan_range, [(T, 200) for T in range(3, Tmax + 1)]):
                results[str(T)] = {"ncase": ncase, "n_ambiguous": len(found), "examples": found}
                print(f"T={T}: 投料 {ncase}, 并列敏感 {len(found)}", flush=True)
                for f in found[:6]:
                    print("   ", f["feed_str"], "->", [o["products"] for o in f["outcomes"]], flush=True)
        json.dump(results, open(BASE + r"\t7_tie_examples.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("saved t7_tie_examples.json")


if __name__ == "__main__":
    main()
