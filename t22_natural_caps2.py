# -*- coding: utf-8 -*-
"""t22_natural_caps2.py：自然环境端帽交换（修正版）
端帽定义修正：
  - 1 价原子（C/L/F）：容量 1 的端帽；
  - 2 价原子（X/W/A）若两根键都连到同一个原子上（双键端帽）：容量 2 的端帽。
条件：两个物质的"端帽键总数"K 相等（1 价端帽记 1，双键端帽记 2）。
反应：交换全部端帽；骨架不动；新端帽按大锅规则重连（可单键挂、也可双键挂，甚至一根 2 价端帽
      分挂两个骨架原子变成"桥"）。
"""
import json
import random
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
VAL = P.VAL
ONE = {"C", "L", "F"}
TWO = {"X", "W", "A"}
CAT = P.CAT
EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG = {(2 * a, 2 * b) for (a, b) in EDGE}


def allowed(ca, cb):
    s = {ca, cb}
    out = set()
    if "聚" in s:
        out.add("S")
    if "动" in s:
        out.add("C")
    if "散" in s:
        out.add("L")
    return out


def formula(atoms):
    cnt = Counter(atoms)
    return "".join(s + (str(cnt[s]) if cnt[s] > 1 else "") for s in ORDER if cnt[s])


def analyse(rec):
    atoms = rec["atoms"]
    place = {}
    if rec.get("place"):
        for k, v in rec["place"].items():
            place[int(k)] = (int(v[0]), int(v[1]))
    n = len(atoms)
    if len(place) != n:
        return None
    # 邻居与多重键
    nb = [dict() for _ in range(n)]
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        nb[i][j] = nb[i].get(j, 0) + m
        nb[j][i] = nb[j].get(i, 0) + m
    caps = []      # (idx, capacity)
    for i in range(n):
        if atoms[i] in ONE:
            caps.append((i, 1))
        elif atoms[i] in TWO and len(nb[i]) == 1:
            # 双键挂同一原子 → 端帽双键
            m = list(nb[i].values())[0]
            if m == 2:
                caps.append((i, 2))
    capset = {i for i, _ in caps}
    skel = [i for i in range(n) if i not in capset]
    bonds = []
    deg = Counter()
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        if i not in capset and j not in capset:
            bonds.append((i, j, m))
            deg[i] += m
            deg[j] += m
    rem = {i: VAL[atoms[i]] - deg[i] for i in skel}
    if not skel:
        return None  # 纯端帽分子（无骨架）单独处理
    K = sum(c for _, c in caps)
    assert sum(rem.values()) == K, (rec["formula"], rem, caps)
    # 骨架已有 L 键中点
    skel_mids = set()
    for (i, j, m) in bonds:
        d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        if d in LONG:
            skel_mids.add(((place[i][0] + place[j][0]) // 2, (place[i][1] + place[j][1]) // 2))
    return {"atoms": atoms, "place": place, "caps": caps, "skel": skel,
            "bonds": bonds, "rem": rem, "K": K, "skel_mids": skel_mids,
            "cap_key": tuple(sorted(atoms[i] for i, _ in caps)),
            "formula": rec["formula"]}


def cells_for(info, si, el):
    atoms = info["atoms"]
    base = info["place"][si]
    allow = allowed(CAT[atoms[si]], CAT[el])
    out = []
    for off in EDGE:
        if "S" in allow:
            out.append((base[0] + off[0], base[1] + off[1], "S", None))
    for off in CORN:
        if "C" in allow:
            out.append((base[0] + off[0], base[1] + off[1], "C", None))
    for off in LONG:
        if "L" in allow:
            mid = (base[0] + off[0] // 2, base[1] + off[1] // 2)
            out.append((base[0] + off[0], base[1] + off[1], "L", mid))
    return out


def try_attach(info, new_caps):
    """new_caps: list of (element, capacity)。返回 (place, edges) 或 None"""
    atoms = info["atoms"]
    skel = info["skel"]
    rem = dict(info["rem"])
    occ = {info["place"][i] for i in skel}
    mids = set(info["skel_mids"])
    place = {i: info["place"][i] for i in skel}
    edges = []
    caps = list(new_caps)
    caps.sort(key=lambda e: -e[1])

    def dfs(t):
        if t == len(caps):
            return all(v == 0 for v in rem.values())
        el, cap = caps[t]
        idx = 10**6 + t
        slots = [i for i in skel if rem[i] >= 1]
        if cap == 1:
            for si in slots:
                for (cx, cy, tp, mid) in cells_for(info, si, el):
                    if (cx, cy) in occ or (cx, cy) in mids:
                        continue
                    if mid is not None and (mid in occ or mid in mids):
                        continue
                    rem[si] -= 1
                    occ.add((cx, cy))
                    if mid is not None:
                        mids.add(mid)
                    place[idx] = (cx, cy)
                    edges.append((si, idx, 1))
                    if dfs(t + 1):
                        return True
                    edges.pop()
                    del place[idx]
                    if mid is not None:
                        mids.discard(mid)
                    occ.discard((cx, cy))
                    rem[si] += 1
            return False
        else:
            # 方案 A：双键挂同一槽位
            for si in slots:
                for (cx, cy, tp, mid) in cells_for(info, si, el):
                    if (cx, cy) in occ or (cx, cy) in mids:
                        continue
                    if mid is not None and (mid in occ or mid in mids):
                        continue
                    if rem[si] >= 2:
                        rem[si] -= 2
                        occ.add((cx, cy))
                        if mid is not None:
                            mids.add(mid)
                        place[idx] = (cx, cy)
                        edges.append((si, idx, 2))
                        if dfs(t + 1):
                            return True
                        edges.pop()
                        del place[idx]
                        if mid is not None:
                            mids.discard(mid)
                        occ.discard((cx, cy))
                        rem[si] += 2
            # 方案 B：单键分挂两个骨架原子（端帽原子只占一个格子）
            for si in slots:
                for (cx, cy, tp, mid) in cells_for(info, si, el):
                    if (cx, cy) in occ or (cx, cy) in mids:
                        continue
                    if mid is not None and (mid in occ or mid in mids):
                        continue
                    for sj in slots:
                        if sj == si or rem[sj] < 1:
                            continue
                        cell_sj = info["place"][sj]
                        d = (cell_sj[0] - cx, cell_sj[1] - cy)
                        # 方向对称：用 cap->sj 的偏移判断关系
                        t2 = None
                        if d in EDGE:
                            t2 = "S"
                        elif d in CORN:
                            t2 = "C"
                        elif d in LONG:
                            t2 = "L"
                        if t2 is None or t2 not in allowed(CAT[el], CAT[atoms[sj]]):
                            continue
                        mid2 = None
                        if t2 == "L":
                            mid2 = ((cx + cell_sj[0]) // 2, (cy + cell_sj[1]) // 2)
                            if mid2 in occ or mid2 in mids:
                                continue
                        if rem[si] < 1:
                            continue
                        rem[si] -= 1
                        rem[sj] -= 1
                        occ.add((cx, cy))
                        if mid is not None:
                            mids.add(mid)
                        if mid2 is not None:
                            mids.add(mid2)
                        place[idx] = (cx, cy)
                        edges.append((si, idx, 1))
                        edges.append((sj, idx, 1))
                        if dfs(t + 1):
                            return True
                        edges.pop()
                        edges.pop()
                        del place[idx]
                        if mid is not None:
                            mids.discard(mid)
                        if mid2 is not None:
                            mids.discard(mid2)
                        occ.discard((cx, cy))
                        rem[si] += 1
                        rem[sj] += 1
            return False

    if not dfs(0):
        return None
    return place, edges, [10**6 + t for t in range(len(caps))]


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    small = [r for r in cat if len(r["atoms"]) <= 8 and r.get("place")]
    infos = {}
    for r in small:
        a = analyse(r)
        if a:
            infos[r["formula"]] = a
    print("小物质:", len(infos))
    groups = defaultdict(list)
    for f, a in infos.items():
        groups[a["K"]].append(f)
    for K in sorted(groups):
        print(f"端帽键数 K={K}: {len(groups[K])} 种物质")
    cat_formula = {r["formula"] for r in cat}
    rng = random.Random(2027)
    stats = Counter()
    new_formulas = set()
    examples_new = []
    for K, fs in groups.items():
        if K == 0:
            continue
        pairs = []
        n = len(fs)
        total = n * (n - 1) // 2
        if total <= 20000:
            pairs = [(fs[i], fs[j]) for i in range(n) for j in range(i + 1, n)]
        else:
            seen = set()
            while len(pairs) < 20000:
                a, b = rng.sample(fs, 2)
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                pairs.append((a, b))
        for A, B in pairs:
            ia, ib = infos[A], infos[B]
            capsA = [(ia["atoms"][i], c) for i, c in ia["caps"]]
            capsB = [(ib["atoms"][i], c) for i, c in ib["caps"]]
            pA = formula([ia["atoms"][i] for i in ia["skel"]] + [e for e, _ in capsB])
            pB = formula([ib["atoms"][i] for i in ib["skel"]] + [e for e, _ in capsA])
            stats["pairs"] += 1
            for prod, in_cat in ((pA, pA in cat_formula), (pB, pB in cat_formula)):
                if not in_cat:
                    new_formulas.add(prod)
            if pA not in cat_formula or pB not in cat_formula:
                stats["含目录外产物"] += 1
            else:
                stats["产物都在目录"] += 1
            # 对前若干例子做几何验证
            if len(examples_new) < 12 and (pA not in cat_formula or pB not in cat_formula):
                att = try_attach(ia, capsB)
                if att is not None:
                    examples_new.append({"A": A, "B": B, "K": K, "prodA": pA, "prodB": pB,
                                         "capsA": capsA, "capsB": capsB})
    stats["distinct_new_formulas"] = len(new_formulas)
    print("统计:", dict(stats))
    for e in examples_new[:10]:
        print(f"  {e['A']} + {e['B']} → {e['prodA']} + {e['prodB']}  (K={e['K']})")
    json.dump({"stats": dict(stats), "new_examples": examples_new,
               "new_formulas_sample": sorted(new_formulas)[:300],
               "groups": {K: len(v) for K, v in groups.items()}},
              open(BASE + r"\t22_natural_caps2.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t22_natural_caps2.json")


if __name__ == "__main__":
    main()
