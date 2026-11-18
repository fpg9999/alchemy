# -*- coding: utf-8 -*-
"""打印 (4,3,2) 反应的每一步，用于对照找出错的一步"""
import sys
from collections import defaultdict, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot3 as P

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {frozenset("OO"): 0, frozenset("XX"): 0, frozenset("CC"): 0,
        frozenset("OX"): 1, frozenset("OC"): 2, frozenset("XC"): 1}
NAME = {"O": "秩", "X": "晶", "C": "冰"}
F = lambda s: "".join(NAME[c] for c in s)


def trace(atom_list):
    n = len(atom_list)
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    step = 0

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

    def desc(cid, groups):
        mem = groups[cid]
        cnt = defaultdict(int)
        for i in mem:
            cnt[atom_list[i]] += 1
        return "".join(NAME[e] + (str(cnt[e]) if cnt[e] > 1 else "") for e in ["O", "X", "C"] if cnt[e])

    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i][j] if cross == 0 else 999
                si, sj = csize[ci], csize[cj]
                t = len(ctypes[ci] | ctypes[cj])
                d = DIST[frozenset((atom_list[i], atom_list[j]))]
                key = (-d, -(rem[i] + rem[j]), 0, cross, gd, min(si, sj), -max(si, sj), -t)
                cands.append((key, i, j, (ci, cj), (sorted(ctypes[ci]), sorted(ctypes[cj])), t, si, sj, d))
        if not cands:
            break
        # 找出"规则1~7全同"的候选，展示
        best = min(c[0] for c in cands)
        tied = [c for c in cands if c[0] == best]
        k, i, j, comps2, tsets, t, si, sj, d = tied[0]
        step += 1
        print(f"\n第 {step} 步：连 {i}{NAME[atom_list[i]]}–{j}{NAME[atom_list[j]]}")
        print(f"   规则1 周期距离={d}  规则2 剩余键和={rem[i]+rem[j]} ({rem[i]}+{rem[j]})")
        print(f"   规则4 跨分子={'是' if k[3] else '否'} 分子内距离={k[4]}")
        print(f"   规则5 分子大小=({min(si,sj)},{max(si,sj)})  规则6 并集种类数={t} ({F(tsets[0])}+{F(tsets[1])})")
        if len(tied) > 1:
            print(f"   （同级并列 {len(tied)} 个：{[(a, NAME[atom_list[a]], b, NAME[atom_list[b]]) for (_,a,b,_,_,_,_,_,_) in tied]}，未用到规则7，按对称任选）")
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    print("\n最终产物：")
    comp, groups, _ = comps()
    out = []
    for cid, mem in enumerate(groups):
        cnt = defaultdict(int)
        for i in mem:
            cnt[atom_list[i]] += 1
        out.append("".join(NAME[e] + (str(cnt[e]) if cnt[e] > 1 else "") for e in ["O", "X", "C"] if cnt[e]))
    print("  ", out)


if __name__ == "__main__":
    trace(["O"] * 4 + ["X"] * 3 + ["C"] * 2)
