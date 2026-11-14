# -*- coding: utf-8 -*-
"""t11_binary_more.py：把二元反应从聚素 29 扩到「无三价 175」+ 交叉 29×175
统一用 9 维元素向量；输出结果表 + 统计 + 等价类 + 物质反应画像。
"""
import json
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER9 = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
IDX = {s: i for i, s in enumerate(ORDER9)}


def vec9_from_atoms(atoms):
    v = [0] * 9
    for a in atoms:
        v[IDX[a]] += 1
    return tuple(v)


def atoms_of(v):
    return [s for s, c in zip(ORDER9, v) for _ in range(c)]


def react(va, vb):
    v = tuple(a + b for a, b in zip(va, vb))
    mols = P.simulate(atoms_of(v))
    if mols is None:
        return False, None
    if not pot_v2.embed_all2(mols):
        return False, None
    return True, sorted(P.formula_of(m["atoms"]) for m in mols)


def run_pairs(items):
    """items: list of (name, vec9)；返回 [(A,B,ok,products)]"""
    out = []
    n = len(items)
    for i in range(n):
        a, va = items[i]
        for j in range(i, n):
            b, vb = items[j]
            ok, prods = react(va, vb)
            out.append((a, b, ok, prods))
    return out


def summarize(rows, label):
    ok = [r for r in rows if r[2]]
    fail = [r for r in rows if not r[2]]
    inert = [r for r in ok if sorted(r[3]) == sorted([r[0], r[1]])]
    single = [r for r in ok if len(r[3]) == 1]
    multi = [r for r in ok if len(r[3]) > 1 and r not in inert]
    print(f"\n### {label}: 共 {len(rows)} 对 | 成功 {len(ok)} 失败 {len(fail)}")
    print(f"  惰性 {len(inert)}；单产物 {len(single)}；多产物 {len(multi)}")
    return ok, fail, inert, single, multi


def main():
    # 数据
    sub = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    ju = [(d["formula"], vec9_from_atoms(d["atoms"])) for d in sub]
    t9 = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
    none = [(r["formula"], vec9_from_atoms(r["atoms"])) for r in t9["none"]]

    rows_none = run_pairs(none)
    rows_cross = []
    for a, va in ju:
        for b, vb in none:
            ok, prods = react(va, vb)
            rows_cross.append((a, b, ok, prods))

    json.dump(rows_none, open(BASE + r"\t11_binary_none.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    json.dump(rows_cross, open(BASE + r"\t11_binary_cross.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)

    summarize(rows_none, "无三价 175 内部")
    summarize(rows_cross, "聚素 29 × 无三价 175")

    # 无三价内部：失败 / 惰性 / 单产物
    ok, fail, inert, single, multi = summarize(rows_none, "无三价 175 内部(重复)")
    print("\n失败对:", [(r[0], r[1]) for r in fail][:30], "..." if len(fail) > 30 else "")
    print("\n单产物反应（前 30）:")
    for r in single[:30]:
        print(f"  {r[0]} + {r[1]} -> {r[3][0]}")
    print("\n惰性对数量:", len(inert), "前 15:", [(r[0], r[1]) for r in inert[:15]])

    # 等价类（按总向量）
    def classes(rows):
        cls = defaultdict(list)
        for a, b, ok_, prods in rows:
            v = tuple(x + y for x, y in zip(
                vec9_from_atoms(a) if a in dict(none) else vec9_from_atoms(a),  # 简化：用表中名字反查
                (0,) * 9))
        return cls

    # 正确的等价类：重新用名称->向量映射
    vmap = dict(ju)
    vmap.update(dict(none))
    for label, rows in [("无三价", rows_none), ("交叉", rows_cross)]:
        cls = defaultdict(list)
        for a, b, ok_, prods in rows:
            cls[tuple(x + y for x, y in zip(vmap[a], vmap[b]))].append((a, b, ok_, prods))
        multi_cls = {k: v for k, v in cls.items() if len(v) > 1}
        print(f"\n{label}：不同总向量 {len(cls)} 类；同一总向量含>1对的类 {len(multi_cls)} 个")
        for k, v in list(multi_cls.items())[:8]:
            outs = {tuple(x[3]) if x[2] else None for x in v}
            print(f"  向量{k}: {len(v)} 对，结果种类={len(outs)}")
            for x in v[:5]:
                print("    ", x[0], "+", x[1], "->", x[3] if x[2] else "失败")

    # 反应画像：对每个物质统计 与其它物质（同集合+交叉）的结果分布
    prof = defaultdict(Counter)
    for rows, tag in [(rows_none, "none"), (rows_cross, "cross")]:
        for a, b, ok_, prods in rows:
            for x, y in ((a, b), (b, a)):
                if ok_:
                    if sorted(prods) == sorted([x, y]):
                        prof[x]["inert"] += 1
                    elif len(prods) == 1:
                        prof[x]["single"] += 1
                    else:
                        prof[x]["multi"] += 1
                else:
                    prof[x]["fail"] += 1
    print("\n=== 反应画像（前 12：最惰性） ===")
    for s, c in sorted(prof.items(), key=lambda kv: -kv[1]["inert"])[:12]:
        print(f"  {s:10s} inert={c['inert']:3d} single={c['single']:3d} multi={c['multi']:3d} fail={c['fail']:2d}")
    print("=== 最容易发生单产物化合（作为反应物） ===")
    for s, c in sorted(prof.items(), key=lambda kv: -kv[1]["single"])[:12]:
        print(f"  {s:10s} single={c['single']:3d} inert={c['inert']:3d} multi={c['multi']:3d} fail={c['fail']:2d}")
    print("=== 最容易失败（不相容） ===")
    for s, c in sorted(prof.items(), key=lambda kv: -kv[1]["fail"])[:12]:
        print(f"  {s:10s} fail={c['fail']:3d} inert={c['inert']:3d} single={c['single']:3d} multi={c['multi']:3d}")


if __name__ == "__main__":
    main()
