# -*- coding: utf-8 -*-
"""t11_reactions.py —— 两个物质之间的反应（二元反应）
口径：A + B 投锅（恒素触媒忽略），全部原子按规则 1~8 重组；
产物确定、且每个产物分子需能合法摆放；否则记为"失败"。
输出 t11_binary_ju.json + 统计与有趣案例。
"""
import json
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]


def atoms_of(vec):
    return [s for s, c in zip(ORDER, vec) for _ in range(c)]


def react(vec_a, vec_b):
    v = tuple(a + b for a, b in zip(vec_a, vec_b))
    atoms = atoms_of(v)
    mols = P.simulate(atoms)
    if mols is None:
        return {"ok": False, "reason": "剩键", "products": None}
    if not pot_v2.embed_all2(mols):
        return {"ok": False, "reason": "摆放失败", "products": None}
    prods = sorted("".join(P.formula_of(m["atoms"]) for m in [mm]) for mm in mols)
    return {"ok": True, "reason": "", "products": prods}


def main():
    data = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    vecs = {d["formula"]: tuple(d["vec"]) for d in data}
    names = sorted(vecs)
    res = {}
    table = []
    for i, a in enumerate(names):
        for b in names[i:]:
            r = react(vecs[a], vecs[b])
            table.append({"A": a, "B": b, "ok": r["ok"], "reason": r["reason"],
                          "products": r["products"]})
    json.dump(table, open(BASE + r"\t11_binary_ju.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    # 统计
    ok = [t for t in table if t["ok"]]
    fail = [t for t in table if not t["ok"]]
    print(f"物质数 {len(names)}，二元反应 {len(table)} 对；成功 {len(ok)}，失败 {len(fail)}")
    print("失败原因:", Counter(t["reason"] for t in fail))
    cls = Counter()
    for t in ok:
        p = t["products"]
        if sorted(p) == sorted([t["A"], t["B"]]):
            cls["原样返回"] += 1
        elif len(p) == 1:
            cls["单一产物"] += 1
        elif t["A"] in p and t["B"] not in p:
            cls[f"{t['A']}未变"] += 1
        elif t["B"] in p and t["A"] not in p:
            cls[f"{t['B']}未变"] += 1
        else:
            cls["多产物"] += 1
    print("结果分类:", dict(cls))

    # 单一产物列表
    single = [t for t in ok if len(t["products"]) == 1]
    print(f"\n单一产物反应 {len(single)} 个，按产物统计:")
    byc = Counter(t["products"][0] for t in single)
    for c, n in byc.most_common():
        print(f"  -> {c}: {n} 个投料对")

    # 原样返回（惰性）
    inert = [t for t in ok if sorted(t["products"]) == sorted([t["A"], t["B"]])]
    print(f"\n惰性组合 {len(inert)} 个，前 20:", [(t["A"], t["B"]) for t in inert[:20]])

    # 催化类：产物含 A 不含 B，或含 B 不含 A
    cat = [t for t in ok if t["A"] in t["products"] and t["B"] not in t["products"] and len(t["products"]) > 1]
    print(f"\n类催化（A 不变、B 转化）{len(cat)} 个，前 15:",
          [(t["A"], t["B"], t["products"]) for t in cat[:15]])

    # 2-循环：A+B->C 且 C+D->A
    sp = {}
    for t in single:
        sp[(t["A"], t["B"])] = t["products"][0]
        if t["A"] != t["B"]:
            sp[(t["B"], t["A"])] = t["products"][0]
    cycles = []
    for (a, b), c in sp.items():
        for (c2, d), a2 in sp.items():
            if c2 != c:
                continue
            if a2 == a and d != a and d != c:
                cycles.append((a, b, c, d))
    print(f"\n检测到 2-循环（A+B→C，C+D→A）候选 {len(cycles)} 条")
    for x in cycles[:20]:
        print("   ", x)

    # 3-循环：A+B→C, C+D→E, E+F→A
    trip = []
    for (a, b), c in sp.items():
        for (c2, d), e in sp.items():
            if c2 != c:
                continue
            for (e2, f), a2 in sp.items():
                if e2 == e and a2 == a:
                    trip.append((a, b, c, d, e, f))
    print(f"\n检测到 3-循环候选 {len(trip)} 条")
    for x in trip[:10]:
        print("   ", x)


if __name__ == "__main__":
    main()
