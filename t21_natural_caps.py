# -*- coding: utf-8 -*-
"""t21_natural_caps.py：自然环境「端帽交换」反应
规则：两个物质端帽（1 价原子）数量相等时，交换全部端帽；骨架（其余原子及其键）保持不变；
新端帽按大锅规则重新接到骨架上（只允许端帽-骨架成键，几何必须合法）。
分析：是否产生大锅无法产生的新物质？可逆性？失败？
"""
import json
import random
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
VAL = P.VAL
ONE = {"C", "L", "F"}
TRI = {"O", "P", "K"}
TWO = {"X", "W", "A"}
CAT = P.CAT
EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG = {(2 * a, 2 * b) for (a, b) in EDGE}


def rel_type(d):
    if d in EDGE:
        return "S"
    if d in CORN:
        return "C"
    if d in LONG:
        return "L"
    return None


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
    caps = [i for i in range(n) if atoms[i] in ONE]
    skel = [i for i in range(n) if atoms[i] not in ONE]
    if not caps or not skel or not place or len(place) != n:
        return None
    skel_set = set(skel)
    bonds = []
    deg = Counter()
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        if i in skel_set and j in skel_set:
            bonds.append((i, j, m))
            deg[i] += m
            deg[j] += m
    rem = {i: VAL[atoms[i]] - deg[i] for i in skel}
    assert sum(rem.values()) == len(caps)
    skel_mids = set()
    for (i, j, m) in bonds:
        d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        if d in LONG:
            skel_mids.add(((place[i][0] + place[j][0]) // 2,
                           (place[i][1] + place[j][1]) // 2))
    return {"atoms": atoms, "place": place, "caps": caps, "skel": skel,
            "bonds": bonds, "rem": rem, "skel_mids": skel_mids}


def try_attach(info, new_caps):
    """把 new_caps（元素列表）接到 info 的骨架上；返回放置结果或 None"""
    atoms = info["atoms"]
    place = dict(info["place"])
    skel = info["skel"]
    rem = dict(info["rem"])
    occ = {place[i] for i in skel}
    # 候选槽位
    k = len(new_caps)
    order = sorted(range(k), key=lambda i: -VAL[new_caps[i]])
    cap_pos = {}
    mids_used = set()
    skel_mids = set(info.get("skel_mids", set()))

    def cells_for(si, el):
        out = []
        base = place[si]
        allow = allowed(CAT[atoms[si]], CAT[el])
        for off, t in (((o, "S") for o in EDGE)):
            pass
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

    def dfs(t):
        if t == k:
            return True
        el = new_caps[order[t]]
        # 槽位按剩余键降序
        slots = sorted([i for i in skel if rem[i] > 0], key=lambda i: -rem[i])
        for si in slots:
            for (cx, cy, tp, mid) in cells_for(si, el):
                if (cx, cy) in occ or (cx, cy) in mids_used or (cx, cy) in skel_mids:
                    continue
                if mid is not None and (mid in occ or mid in mids_used or mid in skel_mids):
                    continue
                ok = True
                # 与已放置端帽不能占同格（occ 已含）
                rem[si] -= 1
                occ.add((cx, cy))
                if mid is not None:
                    mids_used.add(mid)
                cap_pos[order[t]] = ((cx, cy), si, tp)
                if dfs(t + 1):
                    return True
                rem[si] += 1
                occ.discard((cx, cy))
                if mid is not None:
                    mids_used.discard(mid)
                del cap_pos[order[t]]
        return False

    if not dfs(0):
        return None
    return {"caps_pos": dict(cap_pos), "place": place, "rem": rem}


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    small = [r for r in cat if len(r["atoms"]) <= 8 and r.get("place")]
    print("小物质（≤8 原子）:", len(small))
    infos = {}
    for r in small:
        a = analyse(r)
        if a:
            infos[r["formula"]] = (a, r)
    formulas = set(infos)
    # 按端帽数分组
    groups = defaultdict(list)
    for f, (a, r) in infos.items():
        groups[len(a["caps"])].append(f)
    for k in sorted(groups):
        print(f"cap数 {k}: {len(groups[k])} 种物质")
    cat_formula = {r["formula"] for r in cat}

    rng = random.Random(2027)
    results = []
    stats = Counter()
    examples_new = []
    new_formula_set = set()
    known_formula_set = set()
    examples_known = []
    examples_fail = []
    for k, fs in groups.items():
        if k < 1:
            continue
        pairs = []
        n = len(fs)
        total = n * (n - 1) // 2
        if total <= 30000:
            pairs = [(fs[i], fs[j]) for i in range(n) for j in range(i + 1, n)]
        else:
            seen = set()
            while len(pairs) < 30000:
                a, b = rng.sample(fs, 2)
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                pairs.append((a, b))
        for A, B in pairs:
            ia, ra = infos[A]
            ib, rb = infos[B]
            capsA = [ia["atoms"][i] for i in ia["caps"]]
            capsB = [ib["atoms"][i] for i in ib["caps"]]
            if sorted(capsA) == sorted(capsB):
                stats["同端帽元素(只换位置)"] += 1
            prodA_formula = formula([ia["atoms"][i] for i in ia["skel"]] + capsB)
            prodB_formula = formula([ib["atoms"][i] for i in ib["skel"]] + capsA)
            in_catA = prodA_formula in cat_formula
            in_catB = prodB_formula in cat_formula
            res = {"A": A, "B": B, "k": k,
                   "prodA": prodA_formula, "prodB": prodB_formula,
                   "in_catA": in_catA, "in_catB": in_catB}
            # 几何可行性（只对"公式不在目录"的做验证）
            okA = True
            if not in_catA:
                att = try_attach(ia, capsB)
                okA = att is not None
            okB = True
            if not in_catB:
                att = try_attach(ib, capsA)
                okB = att is not None
            res["geomA"] = okA
            res["geomB"] = okB
            if not in_catA:
                new_formula_set.add(prodA_formula)
            else:
                known_formula_set.add(prodA_formula)
            if not in_catB:
                new_formula_set.add(prodB_formula)
            else:
                known_formula_set.add(prodB_formula)
            stats["pairs"] += 1
            if not okA or not okB:
                stats["几何失败"] += 1
                if len(examples_fail) < 10:
                    examples_fail.append(res)
                continue
            if not in_catA or not in_catB:
                stats["含目录外产物"] += 1
                if len(examples_new) < 20:
                    examples_new.append(res)
            else:
                stats["产物都在目录"] += 1
                if len(examples_known) < 10:
                    examples_known.append(res)
            results.append(res)
    stats["distinct_new_formulas"] = len(new_formula_set)
    stats["distinct_known_formulas"] = len(known_formula_set)
    print("统计:", dict(stats))
    print("\n新物质例子（产物不在目录、几何可行）:")
    for e in examples_new[:15]:
        print(f"  {e['A']} + {e['B']} → {e['prodA']} + {e['prodB']}  (k={e['k']}, catA={e['in_catA']}, catB={e['in_catB']})")
    print("\n几何失败例子:")
    for e in examples_fail[:8]:
        print(f"  {e['A']} + {e['B']} → {e['prodA']} + {e['prodB']}  (k={e['k']})")
    print("\n产物仍在目录的例子:")
    for e in examples_known[:8]:
        print(f"  {e['A']} + {e['B']} → {e['prodA']} + {e['prodB']}  (k={e['k']})")
    json.dump({"stats": dict(stats), "new": examples_new, "fail": examples_fail,
               "new_formulas": sorted(new_formula_set)[:200],
               "known": examples_known,
               "groups": {k: len(v) for k, v in groups.items()}},
              open(BASE + r"\t21_natural_caps.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nsaved t21_natural_caps.json")


if __name__ == "__main__":
    main()
