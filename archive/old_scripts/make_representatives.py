# -*- coding: utf-8 -*-
"""make_representatives：组装代表分子（最小例子 / 有限团簇 / 无限族大分子 / 三类混合）供画图。"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
EL = {
    3: ["O", "X", "C", "K", "A", "F"],
    4: ["O", "X", "C", "P", "W", "L"],
    5: ["P", "W", "L", "K", "A", "F"],
    6: P.ORDER,
}


def record(label, scope, elems, feed_counts, target=None):
    atoms = P.vec_to_atoms(tuple(feed_counts), elems)
    mols = P.simulate(atoms)
    if not mols:
        print("FAIL(剩键)", label)
        return None
    cand = [m for m in mols] if target is None else [m for m in mols if P.formula_of(m["atoms"]) == target]
    if not cand:
        cand = sorted(mols, key=lambda m: len(m["atoms"]), reverse=True)
    m = max(cand, key=lambda x: len(x["atoms"]))
    place = P.embed_mol(m["atoms"], m["edges"])
    if place is None or not P.embed_all(mols):
        print("FAIL(摆不出)", label, [P.formula_of(x["atoms"]) for x in mols])
        return None
    feed9 = [0] * 9
    for e, c in zip(elems, feed_counts):
        feed9[P.ORDER.index(e)] = c
    cats = sorted({P.CAT[e] for e in m["atoms"]}, key=lambda c: "聚动散".index(c))
    print(f"OK {label}: {P.formula_of(m['atoms'])} ({len(m['atoms'])}原子, {'-'.join(cats)})")
    return {
        "label": label,
        "formula": P.formula_of(m["atoms"]),
        "zh": P.zh_of(m["atoms"]),
        "natoms": len(m["atoms"]),
        "cats": "-".join(cats),
        "feed": feed9,
        "atoms": list(m["atoms"]),
        "edges": [list(e) for e in m["edges"]],
        "place": {str(k): list(p) for k, p in place.items()},
        "scope": scope,
    }


def from_bigfile(path, scope, Tlist):
    d = json.load(open(path, encoding="utf-8"))
    out = []
    for x in d:
        if x["T"] in Tlist:
            cats = sorted({P.CAT[e] for e in x["atoms"]}, key=lambda c: "聚动散".index(c))
            out.append({
                "label": f"范围{scope} T={x['T']}",
                "formula": x["formula"],
                "zh": P.zh_of(x["atoms"]),
                "natoms": x["natoms"],
                "cats": "-".join(cats),
                "feed": x["feed"],
                "atoms": x["atoms"],
                "edges": x["edges"],
                "place": x["place"],
                "scope": scope,
            })
    return out


def main():
    reps345 = []
    # 最小跨类分子（2 原子）
    reps345.append(record("最小 秩–沌 OK", 3, EL[3], (2, 0, 0, 2, 0, 0), "OK"))
    reps345.append(record("最小 秩–势 OP", 4, EL[4], (2, 0, 0, 2, 0, 0), "OP"))
    reps345.append(record("最小 势–沌 PK", 5, EL[5], (2, 0, 0, 2, 0, 0), "PK"))
    reps345.append(record("最小 晶=气 XA", 3, EL[3], (0, 2, 0, 0, 2, 0), "XA"))
    reps345.append(record("最小 晶=流 XW", 4, EL[4], (0, 2, 0, 0, 2, 0), "XW"))
    reps345.append(record("最小 流=气 WA", 5, EL[5], (0, 2, 0, 0, 2, 0), "WA"))
    reps345.append(record("最小 冰–焰 CF", 3, EL[3], (0, 0, 2, 0, 0, 2), "CF"))
    # 有限团簇
    reps345.append(record("有限团簇 秩10沌4", 3, EL[3], (10, 0, 0, 4, 0, 0), "O10K4"))
    reps345.append(record("有限团簇 秩10势4", 4, EL[4], (10, 0, 0, 4, 0, 0), "O10P4"))
    reps345.append(record("有限团簇 势10沌4", 5, EL[5], (10, 0, 0, 4, 0, 0), "P10K4"))
    # 无限族大分子（从 big_examples 取）
    reps345 += from_bigfile(BASE + r"\scope3_big_examples.json", 3, {18, 24, 26})
    reps345 += from_bigfile(BASE + r"\scope4_big_examples.json", 4, {18, 24, 26})
    reps345 += from_bigfile(BASE + r"\scope5_big_examples.json", 5, {18, 24, 26})
    reps345 = [x for x in reps345 if x]
    json.dump(reps345, open(BASE + r"\reps_cross_345.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved reps_cross_345.json:", len(reps345))

    reps6 = from_bigfile(BASE + r"\scope6_big_examples.json", 6, {16, 18, 20, 22, 24, 27, 30, 34})
    json.dump(reps6, open(BASE + r"\reps_scope6.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved reps_scope6.json:", len(reps6))


if __name__ == "__main__":
    main()
