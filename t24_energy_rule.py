# -*- coding: utf-8 -*-
"""t24_energy_rule.py：以键能权重 + 每根断开重连键需释放 2 单位能量，推导自然反应规则
键能权重：S=3, C=2, L=1；分子键能 E(M)=Σ w(键型)×键数。
自然反应（端帽交换）要求：E_before − E_after ≥ 2 × n（n=断开的端帽-骨架键数 = 交换端帽容量和）。
由于单根键释放 max = 3−1 = 2，要达到阈值，每根被交换的键必须恰好 S→L。
结论：只有"聚/散端帽、原来以短键 S 连接、交换后改以长键 L 连接"才可能反应。
"""
import json
import random
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}
CAT = {e: ("聚" if e in "OXC" else ("动" if e in "PWL" else "散")) for e in ORDER}
ONE = {"C", "L", "F"}
TWO = {"X", "W", "A"}
EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG = {(2 * a, 2 * b) for (a, b) in EDGE}
W = {"S": 3, "C": 2, "L": 1}


def rel(d):
    if d in EDGE:
        return "S"
    if d in CORN:
        return "C"
    if d in LONG:
        return "L"
    return None


def formula(atoms):
    c = Counter(atoms)
    return "".join(s + (str(c[s]) if c[s] > 1 else "") for s in ORDER if c[s])


def info(rec):
    atoms = rec["atoms"]
    place = {int(k): (int(v[0]), int(v[1])) for k, v in (rec.get("place") or {}).items()}
    if len(place) != len(atoms):
        return None
    nb = [dict() for _ in range(len(atoms))]
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        nb[i][j] = nb[i].get(j, 0) + m
        nb[j][i] = nb[j].get(i, 0) + m
    caps = []
    for i, el in enumerate(atoms):
        if el in ONE:
            caps.append((i, 1))
        elif el in TWO and len(nb[i]) == 1 and list(nb[i].values())[0] == 2:
            caps.append((i, 2))
    capset = {i for i, _ in caps}
    skel = [i for i in range(len(atoms)) if i not in capset]
    rem = {i: VAL[atoms[i]] - sum(m for j, m in nb[i].items() if j not in capset) for i in skel}
    K = sum(c for _, c in caps)
    # 每个端帽的旧键描述
    capdesc = []
    for i, cap in caps:
        bond_types = []
        partners = []
        for j, m in nb[i].items():
            if j in capset:
                partners.append(None)
                bond_types.append(None)
                continue
            t = rel((place[j][0] - place[i][0], place[j][1] - place[i][1]))
            bond_types.append(t)
            partners.append(CAT[atoms[j]])
        capdesc.append({"idx": i, "cap": cap, "el": atoms[i], "types": bond_types,
                        "partners": partners})
    return {"atoms": atoms, "place": place, "caps": caps, "capdesc": capdesc,
            "skel": skel, "rem": rem, "K": K, "nb": nb}


def energy(info):
    e = 0
    for (i, j, m) in []:
        pass
    for i in range(len(info["atoms"])):
        for j, m in info["nb"][i].items():
            if j < i:
                continue
            t = rel((info["place"][j][0] - info["place"][i][0],
                     info["place"][j][1] - info["place"][i][1]))
            if t:
                e += W[t] * m
    return e


def l_cells(info, si, capcat):
    """端帽改接长键 L 的候选格（要求允许 L：capcat 或骨架类别含散）"""
    at = info["atoms"]
    base = info["place"][si]
    if not (capcat == "散" or CAT[at[si]] == "散"):
        return []
    out = []
    for off in LONG:
        mid = (base[0] + off[0] // 2, base[1] + off[1] // 2)
        out.append((base[0] + off[0], base[1] + off[1], mid))
    return out


def try_attach_L(info, newcaps):
    """强制全部新端帽以 L 键挂上（用于判断 S→L 交换可行性）"""
    skel = info["skel"]
    rem = dict(info["rem"])
    occ = {info["place"][i] for i in skel}
    mids = set()
    place = {}
    caps = list(newcaps)
    caps.sort(key=lambda e: -e[1])

    def dfs(t):
        if t == len(caps):
            return all(v == 0 for v in rem.values())
        el, cap = caps[t]
        idx = 10**6 + t
        slots = [i for i in skel if rem[i] >= 1]
        for si in slots:
            for (cx, cy, mid) in l_cells(info, si, CAT[el]):
                if (cx, cy) in occ or (cx, cy) in mids:
                    continue
                if mid in occ or mid in mids:
                    continue
                if cap == 1:
                    rem[si] -= 1
                    occ.add((cx, cy))
                    mids.add(mid)
                    place[idx] = (cx, cy)
                    if dfs(t + 1):
                        return True
                    del place[idx]
                    mids.discard(mid)
                    occ.discard((cx, cy))
                    rem[si] += 1
                else:
                    # 双键端帽：两根 L 单键挂两个不同骨架原子（同一原子双键L不可能：L 方向唯一，同原子最多 1 根）
                    for sj in slots:
                        if sj == si or rem[sj] < 1:
                            continue
                        cel = info["place"][sj]
                        d = (cel[0] - cx, cel[1] - cy)
                        if d not in LONG:
                            continue
                        mid2 = ((cx + cel[0]) // 2, (cy + cel[1]) // 2)
                        if mid2 in occ or mid2 in mids or mid2 == (cx, cy):
                            continue
                        rem[si] -= 1
                        rem[sj] -= 1
                        occ.add((cx, cy))
                        mids.add(mid)
                        mids.add(mid2)
                        place[idx] = (cx, cy)
                        if dfs(t + 1):
                            return True
                        del place[idx]
                        mids.discard(mid)
                        mids.discard(mid2)
                        occ.discard((cx, cy))
                        rem[si] += 1
                        rem[sj] += 1
        return False

    return dfs(0)


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    small = [r for r in cat if len(r["atoms"]) <= 8 and r.get("place")]
    infos = {}
    energies = {}
    for r in small:
        a = info(r)
        if a:
            infos[r["formula"]] = a
            energies[r["formula"]] = energy(a)
    print("小物质:", len(infos))
    # 统计：端帽全部 S 的分子（full exchange 候选）
    allS = {}
    for f, a in infos.items():
        ok = all(all(t == "S" for t in d["types"] if t) for d in a["capdesc"])
        allS[f] = ok
    print("端帽全为 S 键的物质:", sum(1 for v in allS.values() if v), "/", len(infos))
    groups = defaultdict(list)
    for f, a in infos.items():
        groups[a["K"]].append(f)
    rng = random.Random(2027)
    cat_formula = {r["formula"] for r in cat}
    stats = Counter()
    examples = []
    for K, fs in groups.items():
        if K == 0:
            continue
        candidates = [f for f in fs if allS[f]]
        pairs = []
        n = len(candidates)
        total = n * (n - 1) // 2
        if total <= 20000:
            pairs = [(candidates[i], candidates[j]) for i in range(n) for j in range(i + 1, n)]
        else:
            seen = set()
            while len(pairs) < 20000:
                a, b = rng.sample(candidates, 2)
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                pairs.append((a, b))
        stats["候选对"] += len(pairs)
        for A, B in pairs:
            ia, ib = infos[A], infos[B]
            capsA = [(ia["atoms"][i], c) for i, c in ia["caps"]]
            capsB = [(ib["atoms"][i], c) for i, c in ib["caps"]]
            # 全部端帽以 L 方式挂到对方骨架
            if try_attach_L(ia, capsB) and try_attach_L(ib, capsA):
                stats["可行交换"] += 1
                pA = formula([ia["atoms"][i] for i in ia["skel"]] + [e for e, _ in capsB])
                pB = formula([ib["atoms"][i] for i in ib["skel"]] + [e for e, _ in capsA])
                if pA in cat_formula and pB in cat_formula:
                    stats["产物都在目录"] += 1
                else:
                    stats["含目录外产物"] += 1
                if len(examples) < 15:
                    n_bonds = K
                    release = 2 * n_bonds
                    examples.append({"A": A, "B": B, "K": K, "n_bonds": n_bonds,
                                     "release": release,
                                     "E_before": energies[A] + energies[B],
                                     "E_after": energies[A] + energies[B] - release,
                                     "prodA": pA, "prodB": pB})
    print("端帽全 S 候选对中，S→L 全交换可行:", stats["可行交换"], "对")
    for e in examples:
        print(f"  {e['A']} + {e['B']} → {e['prodA']} + {e['prodB']}  "
              f"K={e['K']} 释放={e['release']}  E:{e['E_before']}→{e['E_after']}")
    json.dump({"stats": dict(stats), "examples": examples,
               "allS_count": sum(1 for v in allS.values() if v)},
              open(BASE + r"\t24_energy_rule.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t24_energy_rule.json")


if __name__ == "__main__":
    main()
