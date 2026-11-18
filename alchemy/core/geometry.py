# -*- coding: utf-8 -*-
"""六边形网格摆放（embedding）与严格校验。

一个分子"化学上合法"（价数填满）不等于"几何上放得下"：必须在六边形网格上给每个原子
一个 axial 坐标，使得
1. 每条键的位移落在两端大类允许的偏移集合内；
2. 原子不重叠；
3. 长键 L 的中间格必须为空（且不能是端点自己）；
4. 方向关系正确（首个原子选定向，避免 60° 旋转重复搜索）。

搜索是 BFS 定点 + 回溯：每次挑"已放置邻居最多、其次度数最大"的原子放置，
第一个原子定在 (0,0)，第二个原子只试每个键型轨道的一个代表（破缺 60° 旋转对称）。

历史上的 bug（已在 ``embed`` 中修复，对应旧 ``pot_v2.embed_mol2``）：
旧版 ``pot_all.embed_mol`` 用 set 记录 L 键中间格，回溯撤销时会误删"另一个仍存在的
L 键共享的中间格"，导致后续原子可以放到该中间格上，产出非法摆放。
这里改用计数 ``Counter``，并在搜索结束时做一次严格校验。
"""
from __future__ import annotations

from collections import Counter

from .elements import C_SET, L_SET, S_SET, allowed, classify_offset

__all__ = ["embed", "embed_all", "validate", "embed_mol2", "validate_place", "to_place_dict"]


def validate(place, atoms, edges) -> tuple[bool, str]:
    """严格校验一个摆放是否合法。返回 ``(ok, msg)``。

    ``place`` 为 ``{原子下标: (q, r)}`` 的 dict，或按顺序的坐标序列。
    """
    if place is None:
        return False, "None"
    atoms = list(atoms)
    edges = [tuple(e) for e in edges]
    n = len(atoms)
    if isinstance(place, dict):
        pos = [tuple(place[i]) for i in range(n)]
    else:
        pos = [tuple(p) for p in place]
    if len(set(pos)) != n:
        return False, "duplicate positions"
    occ = set(pos)
    for (i, j, m) in edges:
        d = (pos[j][0] - pos[i][0], pos[j][1] - pos[i][1])
        if d not in allowed(atoms[i], atoms[j]):
            return False, f"offset {d} not allowed ({atoms[i]}-{atoms[j]})"
        if classify_offset(d) == "L":
            mid = (pos[i][0] + d[0] // 2, pos[i][1] + d[1] // 2)
            if mid in occ:
                return False, f"L midpoint {mid} occupied"
            if mid == pos[i] or mid == pos[j]:
                return False, "L midpoint equals endpoint"
    return True, "ok"


def embed(atoms, edges, max_nodes: int | None = None, final_check: bool = True):
    """为分子找一个合法摆放。成功返回 ``{下标: (q, r)}``，失败返回 ``None``。

    ``max_nodes``：搜索节点上限（防止大分子搜索爆炸）；超限返回 ``None``，
    调用方应把它理解为"未判定"而不是"不可能"。
    ``final_check``：回溯到完整解后再跑一次 :func:`validate`（默认开启）。
    """
    atoms = list(atoms)
    edges = [tuple(e) for e in edges]
    n = len(atoms)
    if n == 0:
        return {}
    if n == 1:
        return {0: (0, 0)}

    adj: list[dict[int, frozenset]] = [dict() for _ in range(n)]
    for (i, j, m) in edges:
        adj[i][j] = adj[j][i] = allowed(atoms[i], atoms[j])

    # BFS 定点顺序：优先"已放置邻居多"，其次"度数大"
    start = max(range(n), key=lambda i: len(adj[i]))
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
            return None  # 分子不连通
        seen.add(bestu)
        order.append(bestu)

    pos: list[tuple[int, int] | None] = [None] * n
    occ: set[tuple[int, int]] = set()
    lmid: Counter = Counter()
    nodes = [0]

    def reps_for(allow: frozenset):
        """每个键型轨道（S/C/L 各 6 个位移）取一个代表，破缺 60° 旋转对称。"""
        reps = []
        for orbit in (S_SET, C_SET, L_SET):
            inter = allow & orbit
            if inter:
                reps.append(min(inter))
        return reps

    def try_place(k: int) -> bool:
        nodes[0] += 1
        if max_nodes is not None and nodes[0] > max_nodes:
            return False
        if k == n:
            if final_check:
                return validate({i: pos[i] for i in range(n)}, atoms, edges)[0]
            return True
        v = order[k]
        placed_u: list[int] = []
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
            cands = [p for p in base if p not in occ and lmid[p] == 0]
            if k == 1:
                u0 = order[0]
                want = {(pos[u0][0] + r[0], pos[u0][1] + r[1]) for r in reps_for(adj[u0][v])}
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
            for m in new_lmids:
                lmid[m] += 1
            if try_place(k + 1):
                return True
            pos[v] = None
            occ.discard(p)
            for m in new_lmids:
                lmid[m] -= 1
                if lmid[m] == 0:
                    del lmid[m]
        return False

    if try_place(0):
        return {i: pos[i] for i in range(n)}
    return None


def embed_all(mols, max_nodes: int | None = None, final_check: bool = True) -> bool:
    """一锅产物是否**全部**可摆放。"""
    for m in mols:
        if embed(m["atoms"], m["edges"], max_nodes=max_nodes, final_check=final_check) is None:
            return False
    return True


def to_place_dict(place, atoms=None) -> dict[str, list[int]]:
    """把 ``{下标: (q, r)}`` 转成目录/JSON 使用的 ``{"0": [q, r], ...}``。"""
    if not place:
        return {}
    return {str(k): [int(v[0]), int(v[1])] for k, v in sorted(place.items())}


# ---------------------------------------------------------------- 兼容别名
# 旧脚本里的名字，保留以便平滑迁移；新代码请用 embed / validate。
embed_mol2 = embed
validate_place = validate
