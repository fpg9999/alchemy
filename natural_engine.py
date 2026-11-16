# -*- coding: utf-8 -*-
"""natural_engine.py —— 自然环境反应引擎 v2（规则 1~11 + T35 温度判定）

把项目已有资产合并成一个可直接用于"时间步/粒子环境"的反应引擎：

* 完全反应：`pot_v4.simulate`（规则 1~11）—— 结果只由元素计数向量决定（项目已验证），
  因此按计数向量缓存。
* 不完全反应：`t28_rule_v2` 的规则（全局选最不稳定键类、每条元素对断 1 根、
  允许恢复被断键类、允许跨分子合并），但重结合改用**规则 1~11**（与 pot_v4 完全同一
  贪心 key / 规则 10 / 规则 11），而不是 t28 里的规则 1~9 版本。
* 自分解：不稳定物质 M（F(v_M) 不是自身）在 T >= c(M) 时 M -> F(v_M)。
* 温度判定：严格按 docs/T35_PRIORITY_SELF_DECOMP.md 的 T35 算法：

    resolve(接触集合 S, T):
      1) T >= Σc(S) 且完全反应可行 -> 完全反应（最高优先级）
      2) 否则：所有不稳定且 T >= c(M) 的 M 同时自分解 -> 对新产品集合重判（回到 1）
      3) 否则：T >= Σi(含当前全局最不稳定类的分子) 且不完全反应可行 -> 不完全反应
      4) 否则：不反应

定义（与 T33/T34/T35 一致）：
    c(M) = 分子总键数 = 所有边键级之和
    i(M) = 本次不完全反应中 M 要断的键数（= M 中属于选定键类的元素对数，每对断 1 根）
    键类 = (周期表距离 d, 键级 m, 端元最低价数 v)，不稳定度排序 (d 小, m 大, v 小)

分子对象 = dict：
    atoms  : tuple[str]
    edges  : tuple[(i, j, mult)]
    formula: str
    label  : pot_all.mol_label 规范形（同构判定用）
    vec    : 9 维元素计数 tuple（ORDER 顺序）
    c      : 总键数

所有函数确定性、可缓存；不绑定具体模拟器（粒子环境/随机循环都可用）。
"""
import sys
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
from pot_v3 import rule9_extra
from pot_v4 import ring_flags

VAL = P.VAL
ORDER = P.ORDER
TRI = {"O", "P", "K"}

# 快速引擎开关（T59 起）：complete/incomplete 的贪心重结合改用 fast_pot（与 pot_v4 等价，
# 增量并查集 + 分层字典序筛选，约 4~8 倍加速）。默认 False，保证历史口径不变。
_USE_FAST = False


def set_fast(flag=True):
    global _USE_FAST
    _USE_FAST = bool(flag)
    return _USE_FAST

# ---------------------------------------------------------------- 分子
_MOL_CACHE = {}


def make_mol(atoms, edges):
    """构造分子对象（去重缓存）。edges 用 (i,j,mult) 列表。"""
    ats = tuple(atoms)
    es = tuple(sorted((int(a), int(b), int(m)) for a, b, m in edges))
    key = (ats, es)
    hit = _MOL_CACHE.get(key)
    if hit is not None:
        return hit
    formula = P.formula_of(ats)
    mol = {
        "atoms": ats,
        "edges": es,
        "formula": formula,
        "label": P.mol_label(ats, es),
        "vec": tuple(P.parse_formula(formula)),
        "c": sum(m for _, _, m in es),
    }
    _MOL_CACHE[key] = mol
    return mol


def mol_from_record(rec):
    return make_mol(rec["atoms"], rec["edges"])


def mols_vec(mols):
    """接触集合的元素计数向量（9 维）。"""
    out = [0] * 9
    for m in mols:
        for i, v in enumerate(m["vec"]):
            out[i] += v
    return tuple(out)


def mols_labels(mols):
    return tuple(sorted(m["label"] for m in mols))


def mols_forms(mols):
    return tuple(sorted(m["formula"] for m in mols))


# ---------------------------------------------------------------- 规则 1~11 贪心成键（可带固定键）
def _components(n, bond):
    """返回 (comp, groups, dists)，与 pot_v4.simulate 内同构。"""
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
            for v in range(n):
                if bond[u][v] > 0 and comp[v] == -1:
                    comp[v] = cid
                    st.append(v)
                    mem.append(v)
        groups.append(mem)
    dists = []
    for mem in groups:
        d = {}
        for s in mem:
            dd = {s: 0}
            dq = __import__("collections").deque([s])
            while dq:
                u = dq.popleft()
                for v in range(n):
                    if bond[u][v] > 0 and v not in dd:
                        dd[v] = dd[u] + 1
                        dq.append(v)
            d[s] = dd
        dists.append(d)
    return comp, groups, dists


def greedy_bond(atom_list, base_edges=()):
    """规则 1~11 贪心成键。base_edges 为已固定键（不完全反应保留的键）。

    返回 Mol 列表；价数无法填满 / 价数和为奇数 -> None。
    与 pot_v4.simulate 的唯一区别是允许预置固定键（其余 key 逐字复制）。
    """
    atom_list = list(atom_list)
    n = len(atom_list)
    if n == 0:
        return []
    if sum(VAL[e] for e in atom_list) % 2:
        return None
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = P.family_rank(atom_list[i], atom_list[j])
    for (a, b, m) in base_edges:
        a, b, m = int(a), int(b), int(m)
        if m <= 0:
            continue
        bond[a][b] += m
        bond[b][a] += m
        rem[a] -= m
        rem[b] -= m
        adj[a][b] = adj[a].get(b, 0) + m
        adj[b][a] = adj[b].get(a, 0) + m
    if any(r < 0 for r in rem):
        return None

    level6 = None
    blockid = None
    while True:
        comp, groups, dists = _components(n, bond)
        if level6 is None:
            blockid = None
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]
        if level6 is not None and blockid is None:
            blockid = [-1] * n
            for bi, blk in enumerate(level6):
                for v in blk[2]:
                    blockid[v] = bi
        rf = ring_flags(n, adj)
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
                if level6 is None:
                    key = key + (0,)
                else:
                    key = key + (0 if blockid[i] >= 0 and blockid[i] == blockid[j] else 1,)
                key = key + (rf[i] + rf[j],)
                cands.append((key, i, j))
        if not cands:
            break
        if level6 is None and not any6:
            level6 = []
            for g in groups:
                if not any(atom_list[v] in TRI for v in g):
                    continue
                mem = sorted(g)
                ats = [atom_list[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                level6.append((ats, es, tuple(mem)))
        best = min(c[0] for c in cands)
        pick = None
        for (k, i, j) in cands:
            if k == best:
                pick = (i, j)
                break
        i, j = pick
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None
    comp, groups, _ = _components(n, bond)
    mols = []
    for mem in groups:
        ats = [atom_list[v] for v in mem]
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((a, b, m))
        mols.append(make_mol(ats, es))
    return mols


# ---------------------------------------------------------------- 完全反应 F
_F_CACHE = {}


def complete_products(vec):
    """F(vec)：完全大锅反应（规则 1~11）。返回 Mol 列表或 None。"""
    key = tuple(vec)
    if key in _F_CACHE:
        return _F_CACHE[key]
    atoms = P.vec_to_atoms(key, ORDER)
    if _USE_FAST:
        import fast_pot
        raw = fast_pot.simulate(atoms)
        prods = None if raw is None else [make_mol(m["atoms"], m["edges"]) for m in raw]
    else:
        prods = greedy_bond(atoms)
    _F_CACHE[key] = prods
    return prods


def f_of_mol(m):
    return complete_products(m["vec"])


# ---------------------------------------------------------------- 稳定性 / 自分解
_STABLE_CACHE = {}


def is_stable(m):
    """M 是否为大锅不动点：F(v_M) 恰为自身（按规范形比较）。"""
    lab = m["label"]
    if lab in _STABLE_CACHE:
        return _STABLE_CACHE[lab]
    prods = f_of_mol(m)
    ok = prods is not None and len(prods) == 1 and prods[0]["label"] == lab
    _STABLE_CACHE[lab] = ok
    return ok


def self_decomp_products(m):
    """自分解产物 = F(v_M)（不稳定物质专用）。"""
    return f_of_mol(m)


# ---------------------------------------------------------------- 键类
_BC_CACHE = {}


def bond_classes(m):
    """分子内键类计数：{(d,m,v): 元素对数}，v = 端元最低价数（t28 口径）。"""
    lab = m["label"]
    hit = _BC_CACHE.get(lab)
    if hit is not None:
        return hit
    cnt = Counter()
    ats = m["atoms"]
    for (i, j, mu) in m["edges"]:
        d = P.ptable_dist(ats[i], ats[j])
        cls = (d, mu, min(VAL[ats[i]], VAL[ats[j]]))
        cnt[cls] += 1
    _BC_CACHE[lab] = cnt
    return cnt


def select_class(mols):
    """全局最不稳定键类（t28 排序：d 小 -> m 大 -> 端元价数小）。无键返回 None。"""
    best = None
    for m in mols:
        for cls in bond_classes(m):
            k = (cls[0], -cls[1], cls[2])
            if best is None or k < best[0]:
                best = (k, cls)
    return None if best is None else best[1]


def has_class(m, cls):
    return cls in bond_classes(m)


def i_count(m, cls):
    """M 在本次不完全反应中要断的键数 = 该键类元素对数（每对断 1 根）。"""
    return bond_classes(m).get(cls, 0)


# ---------------------------------------------------------------- 不完全反应
_INC_CACHE = {}


def incomplete_products(mols):
    """对接触集合做一次不完全反应（t28 v2 + 规则 1~11 重结合）。

    返回 Mol 列表或 None（失败/不成立）。缓存键 = 参与者规范形排序。
    """
    key = mols_labels(mols)
    if key in _INC_CACHE:
        return _INC_CACHE[key]
    mols = list(mols)
    atom_list = []
    edges = []
    for m in mols:
        off = len(atom_list)
        atom_list += list(m["atoms"])
        for (a, b, mu) in m["edges"]:
            edges.append((a + off, b + off, mu))
    cls = select_class(mols)
    if cls is None:
        _INC_CACHE[key] = None
        return None
    d, mu, v = cls
    # 断键：每条属于该类的元素对断 1 根（t28 break_class）
    kept = []
    broken = 0
    for (a, b, mlt) in edges:
        if mlt == mu and P.ptable_dist(atom_list[a], atom_list[b]) == d and \
           min(VAL[atom_list[a]], VAL[atom_list[b]]) == v:
            mlt -= 1
            broken += 1
        if mlt > 0:
            kept.append((a, b, mlt))
    if broken == 0:
        _INC_CACHE[key] = None
        return None
    if _USE_FAST:
        import fast_pot
        raw = fast_pot.simulate(atom_list, base_edges=kept)
        prods = None if raw is None else [make_mol(m["atoms"], m["edges"]) for m in raw]
    else:
        prods = greedy_bond(atom_list, kept)
    _INC_CACHE[key] = prods
    return prods


# ---------------------------------------------------------------- 判定入口（T35）
def resolve(mols, T):
    """温度 T 下接触集合 mols 的判定。

    返回 dict：
      type     : 'complete' | 'incomplete' | 'none'
      products : Mol 列表（none 时为 None）
      state    : 判定结束后的接触集合（含自分解后的现状；none 时也可能已自分解）
      stages   : 判定轨迹（自分解记录等）
      class    : 实际使用的键类（incomplete）
      csum     : 最终集合 Σc
      isum     : 不完全阈值 Σi（若适用）
    """
    mols = list(mols)
    stages = []
    while True:
        csum = sum(m["c"] for m in mols)
        if T >= csum:
            prods = complete_products(mols_vec(mols))
            if prods is not None:
                return {"type": "complete", "products": prods, "state": prods,
                        "stages": stages, "class": None, "csum": csum, "isum": None}
        # 2) 不稳定物质自分解优先（同时处理全部满足者）
        changed = False
        nxt = []
        for m in mols:
            if (not is_stable(m)) and T >= m["c"]:
                subs = self_decomp_products(m)
                if subs is None:
                    nxt.append(m)
                    continue
                stages.append({"op": "self_decomp", "from": m["formula"],
                               "from_label": m["label"],
                               "to": [s["formula"] for s in subs],
                               "c": m["c"]})
                nxt.extend(subs)
                changed = True
            else:
                nxt.append(m)
        if changed:
            mols = nxt
            continue
        # 3) 不完全反应
        cls = select_class(mols)
        if cls is not None:
            part = [m for m in mols if has_class(m, cls)]
            isum = sum(i_count(m, cls) for m in part)
            if T >= isum:
                prods = incomplete_products(mols)
                if prods is not None:
                    return {"type": "incomplete", "products": prods, "state": prods,
                            "stages": stages, "class": cls, "csum": csum, "isum": isum}
        return {"type": "none", "products": None, "state": list(mols), "stages": stages,
                "class": cls, "csum": csum, "isum": None}


# ---------------------------------------------------------------- 常用工具
def formula_zh(f):
    """分子式 -> 中文名（若在 substances.json 的 29 种里有中文名）。"""
    return _ZH.get(f, f)


_ZH = {}


def load_zh(path=None):
    import json
    global _ZH
    if _ZH:
        return _ZH
    import os
    p = path or (BASE + r"\substances.json")
    if os.path.exists(p):
        for r in json.load(open(p, encoding="utf-8")):
            _ZH[r["formula"]] = r.get("zh", r["formula"])
    return _ZH


def clear_caches():
    _MOL_CACHE.clear()
    _F_CACHE.clear()
    _STABLE_CACHE.clear()
    _BC_CACHE.clear()
    _INC_CACHE.clear()


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    load_zh()
    print("== 完全反应（与 pot_v4 对齐）==")
    cases = [
        (["O", "O", "X", "X"], ["O2X2"]),
        (["O", "O", "C", "C"], ["O2C2"]),
        (["O", "O", "X", "X", "C", "C"], ["OXC", "OXC"]),
        (["O", "O", "O", "O", "X", "X"], ["O2X", "O2X"]),
    ]
    for atoms, expect in cases:
        got = complete_products(tuple(P.parse_formula(P.formula_of(atoms))))
        forms = sorted(m["formula"] for m in got) if got else None
        print(" ", P.formula_of(atoms), "->", forms,
              "OK" if forms == sorted(expect) else "MISMATCH")
    print("== 29 聚素物质稳定性 ==")
    import json
    subs = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    bad = []
    for r in subs:
        m = mol_from_record(r)
        if not is_stable(m):
            bad.append(r["formula"])
    print("  unstable:", bad if bad else "无（29/29 稳定）")
    print("== 键类/阈值示例 ==")
    o2 = make_mol(["O", "O"], [(0, 1, 3)])
    c2 = make_mol(["C", "C"], [(0, 1, 1)])
    x2 = make_mol(["X", "X"], [(0, 1, 2)])
    print("  O2 c=", o2["c"], "class=", dict(bond_classes(o2)))
    print("  C2 c=", c2["c"], "class=", dict(bond_classes(c2)))
    print("  X2 c=", x2["c"], "class=", dict(bond_classes(x2)))
    print("  select O2+C2 ->", select_class([o2, c2]))
    for T in (1000, 4, 3, 1, 0):
        r = resolve([o2, c2], T)
        print("  T=%5d O2+C2 -> %-10s %s" % (
            T, r["type"],
            sorted(p["formula"] for p in r["products"]) if r["products"] else r["products"]))
    print("== 自分解稳定性（F 不动点）检查 ==")
    unstable = []
    for o in range(0, 5):
        for x in range(0, 5):
            for c in range(0, 5):
                if o + x + c < 2:
                    continue
                vec = (o, x, c) + (0,) * 6
                F = complete_products(vec)
                if not F:
                    continue
                if len(F) != 1:
                    continue
                if not is_stable(F[0]):
                    unstable.append((vec, F[0]["formula"]))
    print("  F 单分子产物中不稳定者:", unstable if unstable else "无（符合 T30：F 产物为不动点）")
