# -*- coding: utf-8 -*-
"""聚素自然反应模拟器（v1）

规则实现：
  周期表距离(聚素)：O-C=2, O-X=X-C=1, 同种=0
  每步挑一对原子连一根键，优先级：
   1) 周期表距离最大
   2) 剩余可连键数之和最大
   3) 族组合：聚素内部全是同族，此条不参与
   4) 跨分子连接最少（同分子优先），再实际距离（分子内键路径长度）最小
   5) 最小分子 + 最大分子
   6) 两分子元素种类数之和最多
   7) 焰气沌电流势冰晶秩恒 顺序（兜底，实现为端点元素名次字典序）
  每对最多 3 根键。走到底后：若有剩余键 → 失败；产物每分子都必须能在六边形棋盘摆出来，否则失败。
"""
import itertools
import random
from collections import defaultdict, deque

ELEMS = ["O", "X", "C"]
VAL = {"O": 3, "X": 2, "C": 1}
NAME = {"O": "秩", "X": "晶", "C": "冰"}
DIST = {("O", "O"): 0, ("X", "X"): 0, ("C", "C"): 0,
        ("O", "X"): 1, ("X", "O"): 1,
        ("O", "C"): 2, ("C", "O"): 2,
        ("X", "C"): 1, ("C", "X"): 1}
RANK = {"F": 0, "A": 1, "K": 2, "L": 3, "W": 4, "P": 5, "C": 6, "X": 7, "O": 8, "E": 9}
HEX_NBRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def formula_of(atoms):
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    order = ["O", "X", "C"]
    out = ""
    for e in order:
        if cnt[e]:
            out += e + (str(cnt[e]) if cnt[e] > 1 else "")
    return out


def embeddable(atoms, edges):
    """判定简单图能否作为六边形格子邻接图的子图摆出来（非边相邻允许）。"""
    n = len(atoms)
    if n == 1:
        return True
    adj = [[] for _ in range(n)]
    for (i, j, _m) in edges:
        adj[i].append(j)
        adj[j].append(i)
    seen = {0}
    st = [0]
    while st:
        u = st.pop()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                st.append(v)
    if len(seen) != n:
        return False
    order = sorted(range(n), key=lambda i: -len(adj[i]))
    placed = {}
    cells = set()

    def dfs(k):
        if k == n:
            return True
        v = order[k]
        if k == 0:
            cands = [(0, 0)]
        else:
            base = set()
            for u in adj[v]:
                if u in placed:
                    cx, cy = placed[u]
                    for dx, dy in HEX_NBRS:
                        p = (cx + dx, cy + dy)
                        if p not in cells:
                            base.add(p)
            cands = list(base)
        for p in cands:
            ok = True
            for u in adj[v]:
                if u in placed:
                    ux, uy = placed[u]
                    if (p[0] - ux, p[1] - uy) not in HEX_NBRS:
                        ok = False
                        break
            if not ok:
                continue
            placed[v] = p
            cells.add(p)
            if dfs(k + 1):
                return True
            del placed[v]
            cells.discard(p)
        return False

    return dfs(0)


def simulate(atom_list, verbose=False):
    """atom_list: 元素符号列表（顺序会影响并列时的选择，用来测试确定性）。
    返回 None(失败) 或 分子列表 [{'atoms':[..], 'edges':[(i,j,mult)...]}]"""
    n = len(atom_list)
    if n == 0:
        return []
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    parent = list(range(n))
    size = [1] * n
    types = [{e} for e in atom_list]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if size[ra] < size[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        size[ra] += size[rb]
        types[ra] |= types[rb]

    def bfs_dist(a, b):
        if a == b:
            return 0
        seen = {a}
        dq = deque([(a, 0)])
        while dq:
            u, d = dq.popleft()
            for v in range(n):
                if bond[u][v] and v not in seen:
                    if v == b:
                        return d + 1
                    seen.add(v)
                    dq.append((v, d + 1))
        return 10 ** 6

    while True:
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                ci, cj = find(i), find(j)
                cross = 0 if ci == cj else 1
                gd = bfs_dist(i, j) if cross == 0 else 10 ** 6
                si, sj = size[ci], size[cj]
                typesum = len(types[ci]) + len(types[cj])
                ri, rj = RANK[atom_list[i]], RANK[atom_list[j]]
                key = (-DIST[(atom_list[i], atom_list[j])],
                       -(rem[i] + rem[j]),
                       0,          # 族组合（同族，恒定）
                       cross,
                       gd,
                       min(si, sj), -max(si, sj),
                       -typesum,
                       min(ri, rj), max(ri, rj),
                       i, j)
                cands.append((key, i, j))
        if not cands:
            break
        cands.sort(key=lambda t: t[0])
        key, i, j = cands[0]
        if verbose:
            print("bond", atom_list[i], i, atom_list[j], j, "key=", key[:8])
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        union(i, j)

    if any(r > 0 for r in rem):
        return None

    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    mols = []
    for g in groups.values():
        idx = {v: k for k, v in enumerate(g)}
        edges = []
        for ii in range(len(g)):
            for jj in range(ii + 1, len(g)):
                a, b = g[ii], g[jj]
                if bond[a][b]:
                    edges.append((ii, jj, bond[a][b]))
        mol = {"atoms": [atom_list[v] for v in g], "edges": edges}
        mols.append(mol)
    for mol in mols:
        if not embeddable(mol["atoms"], mol["edges"]):
            return None
    return mols


def mol_canon(mol):
    """粗略规范形：按元素分组做全排列，取最小邻接矩阵字符串（分子小，够用）。"""
    atoms = mol["atoms"]
    n = len(atoms)
    mat = [[0] * n for _ in range(n)]
    for (i, j, m) in mol["edges"]:
        mat[i][j] = mat[j][i] = m
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


def result_signature(mols):
    if mols is None:
        return "FAIL"
    return " + ".join(sorted(mol_canon(m) for m in mols))


def result_formulas(mols):
    if mols is None:
        return None
    return sorted(formula_of(m["atoms"]) for m in mols)


if __name__ == "__main__":
    # 手算例子核对
    tests = [
        (["O", "O", "X", "X"], "秩---秩 + 晶--晶"),
        (["O", "O", "C", "C"], "秩---秩 + 冰-冰"),
        (["O", "O", "X", "X", "C", "C"], "三个一起"),
        (["O", "O"], "只有秩---秩"),
        (["O", "O", "O", "O"], "4 个秩"),
        (["X", "X", "X", "X"], "4 个晶"),
        (["O", "X", "C"], "(1,1,1)"),
        (["O", "X", "X", "C"], "(1,2,1)"),
    ]
    for atoms, name in tests:
        r = simulate(atoms)
        print(f"{name:28s} -> {result_formulas(r)}   {result_signature(r)}")
