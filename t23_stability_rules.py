# -*- coding: utf-8 -*-
"""t23_stability_rules.py：设计"自然环境稳定反应规则"并量化比较
候选规则：
R0 基础：端帽键数 K 相等的端帽交换（全部对，参照）
R1 已知物质律：交换产物必须都已经存在（大锅目录）→ 不产生新物质
R2 同端帽律：两边端帽多重集相同（只换位置，不改变组成）
R3 稳定化律：在 R1 基础上，要求反应后总"端帽失配能" E 严格下降
E 定义：每个端帽按其与骨架的键型是否是该元素的"偏好键型"计 1 点失配
  （聚系端帽偏好 S、动系偏好 C、散系偏好 L）
统计各规则下"会反应"的对数占比。
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
TWO = {"X", "W", "A"}
CAT = P.CAT
EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG = {(2 * a, 2 * b) for (a, b) in EDGE}
PREF = {"聚": "S", "动": "C", "散": "L"}


def rel_type(d):
    if d in EDGE:
        return "S"
    if d in CORN:
        return "C"
    if d in LONG:
        return "L"
    return None


def formula(atoms):
    cnt = Counter(atoms)
    return "".join(s + (str(cnt[s]) if cnt[s] > 1 else "") for s in ORDER if cnt[s])


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
    K = sum(c for _, c in caps)
    return {"atoms": atoms, "place": place, "caps": caps, "skel": skel, "K": K,
            "nb": nb, "formula": rec["formula"]}


def energy(rec):
    a = info(rec)
    if a is None:
        return None
    e = 0
    for i, cap in a["caps"]:
        el = a["atoms"][i]
        # 找到它连的骨架原子与键型
        for j, m in a["nb"][i].items():
            if j in {x for x, _ in a["caps"]}:
                continue
            d = (a["place"][j][0] - a["place"][i][0], a["place"][j][1] - a["place"][i][1])
            t = rel_type(d)
            if t is None:
                continue
            pref = PREF[CAT[el]]
            if t != pref:
                e += 1
    return e


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    small = [r for r in cat if len(r["atoms"]) <= 8 and r.get("place")]
    infos = {}
    energies = {}
    for r in small:
        a = info(r)
        if a:
            infos[r["formula"]] = a
            energies[r["formula"]] = energy(r)
    print("小物质:", len(infos))
    cat_formula = set(energies)
    groups = defaultdict(list)
    for f, a in infos.items():
        groups[a["K"]].append(f)
    rng = random.Random(2027)
    stats = Counter()
    examples = {"R1": [], "R3": []}
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
            capsA = tuple(sorted((ia["atoms"][i], c) for i, c in ia["caps"]))
            capsB = tuple(sorted((ib["atoms"][i], c) for i, c in ib["caps"]))
            pA = formula([ia["atoms"][i] for i in ia["skel"]] + [e for e, _ in capsB])
            pB = formula([ib["atoms"][i] for i in ib["skel"]] + [e for e, _ in capsA])
            stats["R0_全部同K对"] += 1
            if capsA == capsB:
                stats["R2_同端帽"] += 1
            known = (pA in cat_formula) and (pB in cat_formula)
            if known:
                stats["R1_产物都已知"] += 1
                e0 = energies.get(A, 0) + energies.get(B, 0)
                e1 = energies.get(pA, 0) + energies.get(pB, 0)
                if e1 < e0:
                    stats["R3_稳定化(能量下降)"] += 1
                    if len(examples["R3"]) < 10:
                        examples["R3"].append({"A": A, "B": B, "prodA": pA, "prodB": pB,
                                               "E_before": e0, "E_after": e1})
                if len(examples["R1"]) < 10:
                    examples["R1"].append({"A": A, "B": B, "prodA": pA, "prodB": pB,
                                           "E_before": e0, "E_after": e1, "stabilizing": e1 < e0})
    print("统计:")
    for k, v in stats.items():
        print(f"  {k}: {v}  ({v / stats['R0_全部同K对'] * 100:.2f}%)")
    print("\nR3 稳定化反应例子:")
    for e in examples["R3"]:
        print(f"  {e['A']} + {e['B']} → {e['prodA']} + {e['prodB']}  E: {e['E_before']}→{e['E_after']}")
    print("\nR1 已知物质反应例子:")
    for e in examples["R1"]:
        print(f"  {e['A']} + {e['B']} → {e['prodA']} + {e['prodB']}  E: {e['E_before']}→{e['E_after']} 稳定化={e['stabilizing']}")
    json.dump({"stats": dict(stats), "examples_R3": examples["R3"],
               "examples_R1": examples["R1"]},
              open(BASE + r"\t23_stability_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t23_stability_rules.json")


if __name__ == "__main__":
    main()
