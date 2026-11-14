# -*- coding: utf-8 -*-
"""pot_all：通用模拟器（三类 + 跨类），规则 1~8 + typed embedding（HANDOFF 第 6 节）。

- 元素：O/X/C（聚）、P/W/L（动）、K/A/F（散），价数 3/2/1，恒素 E 不参与。
- 反应阶段不分键型（HANDOFF 9.1）；键型在几何可实现性阶段按两端大类允许集合指派。
- 几何：axial 坐标 (q,r)，用户坐标 X=q, Y=q+2r。
    S 相邻偏移 S_NBRS；C 角向偏移 C_NBRS；L 偏移 = 2×S，中间格必须为空。
"""
from collections import defaultdict, deque
import itertools

# ---------------------------------------------------------------- 元素表
ELEM = {
    "O": ("聚", 3), "X": ("聚", 2), "C": ("聚", 1),
    "P": ("动", 3), "W": ("动", 2), "L": ("动", 1),
    "K": ("散", 3), "A": ("散", 2), "F": ("散", 1),
}
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
VAL = {e: v for e, (c, v) in ELEM.items()}
CAT = {e: c for e, (c, v) in ELEM.items()}

# ---------------------------------------------------------------- 几何偏置（axial (q,r)）
S_NBRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
C_NBRS = [(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)]
L_NBRS = [(2 * a, 2 * b) for (a, b) in S_NBRS]
S_SET, C_SET, L_SET = set(S_NBRS), set(C_NBRS), set(L_NBRS)

# 方向号（写键用；用户坐标 ΔX,ΔY 表见 HANDOFF 2.4）
S_DIRS = {1: (0, 1), 3: (1, 0), 5: (1, -1), 7: (0, -1), 9: (-1, 0), 11: (-1, 1)}
C_DIRS = {2: (1, 1), 4: (2, -1), 6: (1, -2), 8: (-1, -1), 10: (-2, 1), 12: (-1, 2)}
L_DIRS = {k: (2 * a, 2 * b) for k, (a, b) in S_DIRS.items()}

CAT_ALLOWED = {
    frozenset(("聚", "聚")): S_SET,
    frozenset(("动", "动")): C_SET,
    frozenset(("散", "散")): L_SET,
    frozenset(("聚", "动")): S_SET | C_SET,
    frozenset(("动", "散")): C_SET | L_SET,
    frozenset(("聚", "散")): S_SET | L_SET,
}
FAMILY_RANK = {frozenset(("聚", "散")): 0, frozenset(("聚", "动")): 1, frozenset(("动", "散")): 2}


def allowed(a, b):
    return CAT_ALLOWED[frozenset((CAT[a], CAT[b]))]


def ptable_dist(a, b):
    if CAT[a] == CAT[b]:
        return abs(VAL[a] - VAL[b])
    return VAL[a] + VAL[b]


def family_rank(a, b):
    if CAT[a] == CAT[b]:
        return 0  # 同大类不参与规则 3，固定常数排前
    return FAMILY_RANK[frozenset((CAT[a], CAT[b]))]


def formula_of(atoms):
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    return "".join(e + (str(cnt[e]) if cnt[e] > 1 else "") for e in ORDER if cnt[e])


def zh_of(atoms):
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    return "".join(CN[e] + (str(cnt[e]) if cnt[e] > 1 else "") for e in ORDER if cnt[e])


def parse_formula(f):
    cnt = defaultdict(int)
    i = 0
    while i < len(f):
        e = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        cnt[e] += int(num) if num else 1
    return tuple(cnt[e] for e in ORDER)


def vec_to_atoms(v, elems):
    out = []
    for e, c in zip(elems, v):
        out += [e] * c
    return out


# ---------------------------------------------------------------- 键路径距离
def classify_offset(delta):
    if delta in S_SET:
        return "S"
    if delta in C_SET:
        return "C"
    if delta in L_SET:
        return "L"
    return None


def midpoint_of(delta):
    """L 偏移 (2a,2b) → 中间格偏移 (a,b)"""
    return (delta[0] // 2, delta[1] // 2)


# ---------------------------------------------------------------- 反应模拟（规则 1~8）
def simulate(atom_list, rng=None):
    n = len(atom_list)
    if n == 0:
        return []
    total_val = sum(VAL[e] for e in atom_list)
    if total_val % 2:  # 价数总和为奇数 → 不可能接满
        return None
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = family_rank(atom_list[i], atom_list[j])

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
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj),
                       -(ri + rj), -min(ri, rj))
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
        atoms = [atom_list[v] for v in mem]
        edges = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    edges.append((a, b, m))
        mols.append({"atoms": atoms, "edges": edges})
    return mols


# ---------------------------------------------------------------- 几何可实现性（typed embedding）
def embed_mol(atoms, edges, max_nodes=None):
    """返回摆放 {i:(q,r)} 或 None。键型按端点大类允许集合，摆放时定。
    支持混合键型（同一分子 S/C/L 混用）。BFS 顺序放置 + 回溯。
    max_nodes: 搜索节点上限（防止大分子搜索爆炸；超限返回 None，调用方可视为"未判定"）。"""
    n = len(atoms)
    if n == 1:
        return {0: (0, 0)}
    nodes = [0]
    adj = [dict() for _ in range(n)]
    for (i, j, m) in edges:
        adj[i][j] = adj[j][i] = allowed(atoms[i], atoms[j])
    # BFS 顺序：每次选"已放置邻居最多、再按度数"的未放置顶点
    start = max(range(n), key=lambda i: len(adj[i]))
    placed = {}
    cells = set()
    order = [start]
    seen = {start}
    while len(order) < n:
        bestu, bestkey = None, None
        for v in range(n):
            if v in seen:
                continue
            pn = sum(1 for u in adj[v] if u in seen)
            key = (-pn, -len(adj[v]))
            if bestu is None or key < bestkey:
                bestu, bestkey = v, key
        if bestu is None or bestkey[0] == 0:
            # 不应发生（分子连通）；否则说明有不可达顶点
            return None
        seen.add(bestu)
        order.append(bestu)
    pos = [None] * n
    occ = set()
    lmid = set()  # 已放置 L 键的中间格

    def reps_for(allowed_set):
        """60° 旋转对称破缺：allowed_set 的每个轨道（S/C/L 各 6 个）取一个代表。"""
        reps = []
        for orbit in (S_SET, C_SET, L_SET):
            inter = allowed_set & orbit
            if inter:
                reps.append(min(inter))
        return reps

    def try_place(k):
        nodes[0] += 1
        if max_nodes is not None and nodes[0] > max_nodes:
            return False
        if k == n:
            return True
        v = order[k]
        placed_u = []
        if k == 0:
            cands = [(0, 0)]
        else:
            placed_u = [u for u in adj[v] if pos[u] is not None]
            if not placed_u:
                return False
            base = None
            for u in placed_u:
                s = {(pos[u][0] + dx, pos[u][1] + dy) for (dx, dy) in adj[u][v]}
                base = s if base is None else (base & s)
            cands = [p for p in base if p not in occ and p not in lmid]
            if k == 1:
                u0 = order[0]
                reps = reps_for(adj[u0][v])
                want = set()
                for r in reps:
                    want.add((pos[u0][0] + r[0], pos[u0][1] + r[1]))
                cands = [p for p in cands if p in want]
        for p in cands:
            new_lmids = []
            ok = True
            for u in placed_u:
                d = (p[0] - pos[u][0], p[1] - pos[u][1])
                if classify_offset(d) == "L":
                    mid = (pos[u][0] + d[0] // 2, pos[u][1] + d[1] // 2)
                    if mid in occ:
                        ok = False
                        break
                    new_lmids.append(mid)
            if not ok:
                continue
            pos[v] = p
            occ.add(p)
            lmid.update(new_lmids)
            if try_place(k + 1):
                return True
            pos[v] = None
            occ.discard(p)
            for m in new_lmids:
                lmid.discard(m)
        return False

    if try_place(0):
        return {i: pos[i] for i in range(n)}
    return None


def embed_all(mols):
    for m in mols:
        if embed_mol(m["atoms"], m["edges"]) is None:
            return False
    return True


# ---------------------------------------------------------------- 规范形（cache 用，按大类着色）
def _refine(mat, colors, n):
    while True:
        sigs = []
        for i in range(n):
            sigs.append((colors[i], tuple(sorted((mat[i][j], colors[j]) for j in range(n) if j != i))))
        uniq = sorted(set(sigs))
        idx = {s: k for k, s in enumerate(uniq)}
        new = [idx[s] for s in sigs]
        if new == colors:
            return colors
        colors = new


def _canon_rec(mat, colors, n, best, budget=None):
    if budget is not None:
        budget[0] -= 1
        if budget[0] < 0:
            raise TimeoutError("canon")
    colors = _refine(mat, colors, n)
    classes = defaultdict(list)
    for i in range(n):
        classes[colors[i]].append(i)
    cell = None
    for key in sorted(classes):
        if len(classes[key]) > 1:
            cell = classes[key]
            break
    if cell is None:
        order = sorted(range(n), key=lambda i: colors[i])
        cert = tuple(order) + tuple(mat[order[a]][order[b]] for a in range(n) for b in range(a + 1, n))
        if best[0] is None or cert < best[0]:
            best[0] = cert
        return
    for v in cell:
        cols2 = list(colors)
        cols2[v] = max(colors) + 1
        _canon_rec(mat, cols2, n, best, budget)


def canon_signature(atoms, edges):
    """按大类着色的规范形（embed 只依赖大类，故可用作 cache key）。"""
    n = len(atoms)
    mat = [[0] * n for _ in range(n)]
    for (i, j, m) in edges:
        mat[i][j] = mat[j][i] = m
    base = [{"聚": 0, "动": 1, "散": 2}[CAT[e]] for e in atoms]
    best = [None]
    try:
        _canon_rec(mat, base, n, best, [40000])
        return best[0]
    except TimeoutError:
        # 对称度爆炸时退化为"仅本次表示"的键（sound：同键必同图，绝不同图碰撞）
        return ("raw", tuple(base), tuple((i, j, m) for (i, j, m) in edges))


# ---------------------------------------------------------------- 导出用：分子式 + 结构
def mol_label(atoms, edges):
    """元素标号的规范形（导出/比对/去重用）。"""
    n = len(atoms)
    mat = [[0] * n for _ in range(n)]
    for (i, j, k) in edges:
        mat[i][j] = mat[j][i] = k
    base = [ORDER.index(e) for e in atoms]
    best = [None]
    _canon_rec(mat, base, n, best)
    cert = best[0]
    order = list(cert[:n])
    n_edges = n * (n - 1) // 2
    return "".join(atoms[i] for i in order) + "|" + "".join(str(c) for c in cert[n:n + n_edges])


def canonical_sig(atoms, edges):
    """embed 可行性的 cache key：只依赖大类标号的多重图规范形。"""
    sig = canon_signature(atoms, edges)
    order = list(sig[:len(atoms)])
    n = len(atoms)
    n_edges = n * (n - 1) // 2
    return (n, tuple(order), tuple(sig[n:n + n_edges]))


def molecule_dict(atoms, edges):
    place = embed_mol(atoms, edges)
    return {
        "atoms": list(atoms),
        "edges": [list(e) for e in edges],
        "place": {str(k): list(v) for k, v in place.items()} if place else None,
    }
