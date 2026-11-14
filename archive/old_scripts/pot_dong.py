# -*- coding: utf-8 -*-
"""pot_dong：动素（P/W/L，角键 C）版模拟器，规则 1~8 与 pot4（聚素）完全同构。

与 pot4 的唯一区别：
  - 元素：P(势,3价) / W(流,2价) / L(电,1价)
  - 键几何：角键 C（偶数方向号），而非短键 S（奇数方向号）

坐标约定（沿用 pot4 的轴向坐标 (q,r)，等价于 HANDOFF 里用户坐标 (X,Y) 的 X=q, Y=q+2r）：
  - 用户坐标 S(奇) 偏置：1=(0,2) 3=(1,1) 5=(1,-1) 7=(0,-2) 9=(-1,-1) 11=(-1,1)
  - 用户坐标 C(偶) 偏置：2=(1,3) 4=(2,0) 6=(1,-3) 8=(-1,-3) 10=(-2,0) 12=(-1,3)
  - 换算到 (q,r)：C 偏置 = 2→(1,1) 4→(2,-1) 6→(1,-2) 8→(-1,-1) 10→(-2,1) 12→(-1,2)
  - 屏幕坐标 = (1.5*s*X, sqrt(3)/2*s*Y)，C 键中心距 3s，角-角之间正好一条格边长 s。
"""
from collections import defaultdict, deque
import itertools

VAL = {"P": 3, "W": 2, "L": 1}
DIST = {frozenset("PP"): 0, frozenset("WW"): 0, frozenset("LL"): 0,
        frozenset("PW"): 1, frozenset("PL"): 2, frozenset("WL"): 1}
# 角键 C 的 6 个 (q,r) 偏置（对应偶数方向 2,4,6,8,10,12）
C_NBRS = [(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)]
# 角键方向号 ↔ (q,r) 偏置
C_DIRS = {2: (1, 1), 4: (2, -1), 6: (1, -2), 8: (-1, -1), 10: (-2, 1), 12: (-1, 2)}


def dir_of(dq, dr):
    """由 (q,r) 偏置求方向号（C 键只走 2,4,6,8,10,12）。"""
    for k, (a, b) in C_DIRS.items():
        if (a, b) == (dq, dr):
            return k
    raise ValueError(("不是角键偏置", dq, dr))


def formula_of(atoms):
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    return "".join(e + (str(cnt[e]) if cnt[e] > 1 else "") for e in ["P", "W", "L"] if cnt[e])


def embed_place(atoms, edges):
    """返回一个合法摆放 {局部顶点: (q,r)}，摆不出来返回 None。
    搜索顺序按 BFS（保证每个新原子有已放置邻居）——踩坑记录：按度数排序会误判链状分子。"""
    n = len(atoms)
    if n == 1:
        return {0: (0, 0)}
    adj = [[] for _ in range(n)]
    for (i, j, _m) in edges:
        adj[i].append(j)
        adj[j].append(i)
    start = max(range(n), key=lambda i: len(adj[i]))
    order = [start]
    seen = {start}
    qi = 0
    while qi < len(order):
        u = order[qi]
        qi += 1
        for v in sorted(adj[u], key=lambda t: -len(adj[t])):
            if v not in seen:
                seen.add(v)
                order.append(v)
    if len(order) != n:
        return None
    placed = {}
    cells = set()

    def dfs(k):
        if k == n:
            return True
        v = order[k]
        if k == 0:
            cands = [(0, 0)]
        else:
            base = None
            for u in adj[v]:
                if u in placed:
                    cx, cy = placed[u]
                    s = {(cx + dx, cy + dy) for dx, dy in C_NBRS}
                    base = s if base is None else (base & s)
            if not base:
                return False
            cands = [p for p in base if p not in cells]
            if k == 1:
                # 只做对称性破缺，不限制可摆性（等价于固定首根键方向）
                cands = [p for p in cands if p in ((1, 1), (2, -1), (1, -2))]
        for p in cands:
            placed[v] = p
            cells.add(p)
            if dfs(k + 1):
                return True
            del placed[v]
            cells.discard(p)
        return False

    return dict(placed) if dfs(0) else None


def simulate(atom_list, rng=None, r7="sum", r8="sum"):
    n = len(atom_list)
    if n == 0:
        return []
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]

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
                gd = dists[ci][i][j] if cross == 0 else 10 ** 6
                si, sj = csize[ci], csize[cj]
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                d = DIST[frozenset((atom_list[i], atom_list[j]))]
                if r7 == "sum":
                    k7 = (ti + tj, min(ti, tj))
                else:
                    k7 = (min(ti, tj), max(ti, tj))
                if r8 == "sum":
                    k8 = (-(ri + rj), -min(ri, rj))
                else:
                    k8 = (-min(ri, rj), -(ri + rj))
                key = (-d, -(rem[i] + rem[j]), 0, cross, gd,
                       min(si, sj), -max(si, sj), -ut) + k7 + k8
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = rng.choice(tied) if rng is not None else tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None
    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        idx = {v: k for k, v in enumerate(mem)}
        atoms = [atom_list[v] for v in mem]
        edges = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    edges.append((a, b, m))
        mols.append({"atoms": atoms, "edges": edges})
    return mols


def embed_all(mols):
    for m in mols:
        if embed_place(m["atoms"], m["edges"]) is None:
            return False
    return True


def mol_label(m):
    atoms = m["atoms"]
    n = len(atoms)
    mat = [[0] * n for _ in range(n)]
    for (i, j, k) in m["edges"]:
        mat[i][j] = mat[j][i] = k
    groups = defaultdict(list)
    for i, e in enumerate(atoms):
        groups[e].append(i)
    keys = sorted(groups)
    perms = [list(itertools.permutations(groups[k])) for k in keys]
    best = None
    for combo in itertools.product(*perms):
        p = []
        for part in combo:
            p.extend(part)
        s = "".join(atoms[i] for i in p) + "|"
        for a in range(n):
            for b in range(a + 1, n):
                s += str(mat[p[a]][p[b]])
        if best is None or s < best:
            best = s
    return best


def signature(mols):
    if mols is None:
        return "FAIL"
    return " + ".join(sorted(mol_label(m) for m in mols))
