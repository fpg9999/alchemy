# -*- coding: utf-8 -*-
"""大锅反应引擎（完全反应）：贪心成键，规则 1~11。

一次"大锅反应"= 把一堆原子按固定的优先级顺序两两成键，直到没有任何一对还有剩余自由价。
结果是**确定性**的：相同的元素计数向量必然得到相同的产物（项目已验证），因此可以缓存。

## 规则版本（``rules`` 参数）

项目历史上把成键优先级从 8 条逐步扩到 11 条，三套口径同时存在于仓库数据中：

+-------+----------------------+--------------------------------------------------+
| 版本  | 权威实现              | 说明                                             |
+=======+======================+==================================================+
| 8     | ``pot_all.simulate``  | 规则 1~8，并列时取候选顺序第一个                 |
| 9     | ``pot_v3.simulate``   | 追加规则 9（元素优先级 O>X>C>K>A>F>P>W>L）      |
| 11    | ``pot_v4.simulate``   | 追加规则 10（同中间态骨架块优先）、11（链先于环）|
+-------+----------------------+--------------------------------------------------+

**新代码请一律用 ``rules=11``**（当前正式口径）。``rules=8`` / ``9`` 只为复现历史数据保留。

## 优先级 key（字典序最小者先成键）

1. 周期表距离**降序**（远的先成键）
2. 两端剩余价数和降序
3. 键族优先级（聚-散 < 聚-动 < 动-散）
4. 跨组件优先（同组件 cross=1）
5. 组件内图距离
6. 较小组件尺寸升序、再较大组件尺寸降序
7. 并集元素种类数降序
8. 组件元素种类数之和、min、max
9. 总剩余价数降序、min 剩余价数降序
10. 规则 9：结合后各元素数，按 O>X>C>K>A>F>P>W>L 逐项降序
11. 规则 10：同 6 级中间态骨架块内优先（6 级阶段尚未分块，取常数 0）
12. 规则 11：链优先于环（两端"是否在环上"标志之和升序）
"""
from __future__ import annotations

from collections import Counter, deque

from .elements import TRI, VAL, family_rank, ptable_dist

__all__ = ["simulate", "simulate_many", "trace", "RULE9_PRIORITY", "SUPPORTED_RULES"]

#: 规则 9 的元素优先级（用户正式确认：秩 > 晶 > 凝/冰 > 沌 > 气 > 焰 > 势 > 流 > 电）。
RULE9_PRIORITY: tuple[str, ...] = ("O", "X", "C", "K", "A", "F", "P", "W", "L")

SUPPORTED_RULES = (8, 9, 11)


def _rule9_extra(celem_i: Counter, celem_j: Counter) -> tuple[int, ...]:
    """规则 9 的 key 分量：结合后各元素数量（按优先级），多者优先（取负）。"""
    return tuple(-(celem_i.get(e, 0) + celem_j.get(e, 0)) for e in RULE9_PRIORITY)


def _ring_flags(n: int, adj: list[dict[int, int]]) -> list[bool]:
    """每个原子是否在某个环上（O(V+E) 桥检测）。"""
    disc = [-1] * n
    low = [0] * n
    ring = [False] * n
    timer = [0]

    def dfs(u: int, parent: int) -> None:
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v in adj[u]:
            if v == parent:
                continue
            if disc[v] == -1:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] <= disc[u]:
                    ring[u] = True
                    ring[v] = True
            else:
                low[u] = min(low[u], disc[v])
                ring[u] = True
                ring[v] = True

    for s in range(n):
        if disc[s] == -1:
            dfs(s, -1)
    return ring


def _trace(atom_list, rules: int = 11):
    """完整跑一遍并保留中间信息。返回 dict 或 None（价数填不满）。

    返回字段：
      mols            : [{"atoms": [...], "edges": [(i, j, mult), ...]}, ...]
      level6          : 6 级结束时的连通块（含二价/一价成员），格式同 pot_v4
                        ``[(atoms, edges, members), ...]``，只保留含三价原子的块
      bonds           : 最终键表 [(i, j, mult), ...]（原子级下标）
      atoms           : 输入原子序列
      steps           : 成键步数
    """
    if rules not in SUPPORTED_RULES:
        raise ValueError(f"rules 只支持 {SUPPORTED_RULES}，收到 {rules!r}")

    atom_list = list(atom_list)
    n = len(atom_list)
    if n == 0:
        return {"mols": [], "level6": [], "bonds": [], "atoms": [], "steps": 0}
    if sum(VAL[e] for e in atom_list) % 2:
        return None  # 价数总和为奇数 -> 不可能接满

    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj: list[dict[int, int]] = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = family_rank(atom_list[i], atom_list[j])

    def comps():
        comp = [-1] * n
        groups: list[list[int]] = []
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

    def snapshot(groups_, bond_, atom_list_, want_all_components: bool):
        """把当前连通块转成 level6 块列表（pot_v4 口径：包含全部成员）。"""
        blocks = []
        for g in groups_:
            if not any(atom_list_[v] in TRI for v in g):
                continue
            mem = sorted(g)
            ats = [atom_list_[v] for v in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    m = bond_[mem[a]][mem[b]]
                    if m:
                        es.append((a, b, m))
            blocks.append((ats, es, tuple(mem)))
        return blocks

    level6 = None
    blockid = None
    steps = 0
    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]

        # 规则 10 需要 blockid；仅在 rules>=11 且 6 级已封口时维护
        if rules >= 11 and level6 is not None and blockid is None:
            blockid = [-1] * n
            for bi, blk in enumerate(level6):
                for v in blk[2]:
                    blockid[v] = bi

        rf = _ring_flags(n, adj) if rules >= 11 else None

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
                       ti + tj, min(ti, tj), max(ti, tj),
                       -(ri + rj), -min(ri, rj))
                if rules >= 9:
                    key = key + (_rule9_extra(celem[ci], celem[cj]))
                if rules >= 11:
                    # 规则 10：同中间态骨架块内优先（6 级前本项无意义，取 0）
                    if level6 is None:
                        key = key + (0,)
                    else:
                        key = key + (0 if blockid[i] >= 0 and blockid[i] == blockid[j] else 1,)
                    # 规则 11：链优先于环
                    key = key + (rf[i] + rf[j],)
                cands.append((key, i, j))

        # 6 级封口：已经没有 dt==6 的候选了，此刻的连通块就是 6 级中间态骨架
        if level6 is None and not any6:
            level6 = snapshot(groups, bond, atom_list, True)

        if not cands:
            break
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]  # 完全并列时确定性取第一个（候选生成顺序 = 下标序）
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
        steps += 1

    if any(r > 0 for r in rem):
        return None  # 有原子价数没填满

    if level6 is None:
        level6 = snapshot(comps()[1], bond, atom_list, True)

    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        ats = [atom_list[v] for v in mem]
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((a, b, m))
        mols.append({"atoms": ats, "edges": es})

    bonds = []
    for i in range(n):
        for j in range(i + 1, n):
            if bond[i][j]:
                bonds.append((i, j, bond[i][j]))
    return {"mols": mols, "level6": level6, "bonds": bonds,
            "atoms": atom_list, "steps": steps}


def simulate(atom_list, rules: int = 11, return_level6: bool = False):
    """跑一锅反应。

    参数
    ----
    atom_list : 元素序列（如 ``["O", "X", "C"]``）
    rules     : 规则版本 8 / 9 / 11，默认 11（当前正式口径）
    return_level6 : 是否同时返回 6 级中间态骨架块

    返回
    ----
    - 成功：产物分子列表 ``[{"atoms": [...], "edges": [(i, j, mult), ...]}, ...]``
    - 失败（价数无法填满）：``None``
    - ``return_level6=True``：``(mols, level6)``，``level6`` 格式为
      ``[(atoms, edges, members), ...]``（与 pot_v4 一致，含二价/一价成员）

    说明：空输入返回 ``[]``。产物按组件下标顺序返回，同一输入完全确定。
    """
    info = _trace(atom_list, rules=rules)
    if info is None:
        return (None, None) if return_level6 else None
    if return_level6:
        return info["mols"], info["level6"]
    return info["mols"]


def trace(atom_list, rules: int = 11):
    """返回带中间信息的完整轨迹（见 :func:`_trace`）。失败返回 ``None``。"""
    return _trace(atom_list, rules=rules)


def simulate_many(feeds, rules: int = 11):
    """批量模拟。``feeds`` 为元素序列的可迭代对象；返回同样顺序的结果列表。"""
    return [simulate(f, rules=rules) for f in feeds]
