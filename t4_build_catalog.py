# -*- coding: utf-8 -*-
"""t4_build_catalog：合并修正版数据，生成
1) t4_catalog_all.json —— 去重后的全部已知物质（≤16 完备 + 三元组 >16 完备 + 4+ 元素搜索到的合法大分子）
2) T4_CATALOG.md —— 511 类别总表 + 每类物质清单（说明完备性）
"""
import itertools
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def eset_atoms(atoms):
    return frozenset(atoms)


def main():
    le16 = json.load(open(BASE + r"\t4_catalog_le16.json", encoding="utf-8"))
    tri = json.load(open(BASE + r"\t4_triples_complete.json", encoding="utf-8"))
    try:
        caps = json.load(open(BASE + r"\t4_caps_all.json", encoding="utf-8"))
    except FileNotFoundError:
        caps = {}

    # 合并物质（按分子式去重；分子式唯一决定组成）
    substances = {}
    for x in le16:
        substances[x["formula"]] = {
            "formula": x["formula"], "natoms": x["natoms"], "zh": x["zh"],
            "atoms": x["atoms"], "edges": x["edges"], "place": x["place"],
            "feed": x["feed"], "source": "le16",
        }
    n_from_tri = 0
    for k, v in tri.items():
        for x in v["substances"]:
            if x["formula"] not in substances:
                substances[x["formula"]] = {
                    "formula": x["formula"], "natoms": x["natoms"], "zh": x["zh"],
                    "atoms": x["atoms"], "edges": x["edges"], "place": x["place"],
                    "feed": x["feed"], "source": "triple",
                }
                n_from_tri += 1
    n_from_caps = 0
    for key, v in caps.items():
        bv = v.get("best_valid")
        if not bv:
            continue
        f = bv["formula"]
        if f in substances:
            continue
        # 用投料再算一次产物（找到对应分子）
        elems = key.split("/")
        atoms = P.vec_to_atoms(tuple(bv["feed"]), elems)
        mols = P.simulate(atoms)
        if not mols:
            continue
        target = None
        for m in mols:
            if P.formula_of(m["atoms"]) == f:
                target = m
                break
        if target is None:
            continue
        substances[f] = {
            "formula": f, "natoms": bv["natoms"], "zh": P.zh_of(target["atoms"]),
            "atoms": list(target["atoms"]), "edges": [list(e) for e in target["edges"]],
            "place": None, "feed": bv["feed"], "source": "search",
        }
        n_from_caps += 1
    # 额外已知合法大分子（cap probe + 全 9 元素 97 原子）
    extra_feeds = []
    try:
        probe = json.load(open(BASE + r"\t4_cap_probe.json", encoding="utf-8"))
        for r in probe:
            if r.get("valid"):
                extra_feeds.append((r["elems"], r["feed"]))
    except FileNotFoundError:
        pass
    extra_feeds.append((P.ORDER, [3, 8, 15, 10, 1, 0, 36, 22, 2]))
    for elems, feed in extra_feeds:
        atoms = P.vec_to_atoms(tuple(feed), elems)
        mols = P.simulate(atoms)
        if not mols:
            continue
        for m in mols:
            f = P.formula_of(m["atoms"])
            if f in substances:
                continue
            if len(m["atoms"]) < 17:
                continue
            substances[f] = {
                "formula": f, "natoms": len(m["atoms"]), "zh": P.zh_of(m["atoms"]),
                "atoms": list(m["atoms"]), "edges": [list(e) for e in m["edges"]],
                "place": None, "feed": list(feed), "source": "search",
            }
            n_from_caps += 1
    sub_list = sorted(substances.values(), key=lambda x: (x["natoms"], x["formula"]))
    json.dump(sub_list, open(BASE + r"\t4_catalog_all.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"merged catalog: {len(sub_list)} (le16={len(le16)}, +triple>{16}={n_from_tri}, +search={n_from_caps})")

    # 按精确元素集合分组
    groups = defaultdict(list)
    for x in sub_list:
        groups[eset_atoms(x["atoms"])].append(x)

    # 三元组完备数据（允许池 -> 物质集合），用于计算"完备"标记
    tri_pools = {frozenset(k.split("/")): v for k, v in tri.items()}

    lines = []
    lines.append("# 炼金术 · 511 元素组合类别 · 修正版完整目录")
    lines.append("")
    lines.append("> 可摆放性用修复后的 `pot_v2`（严格校验：每条键偏移允许、L 中点为空、坐标互异）检查。")
    lines.append("> 数据来源：全 9 元素 ≤16 原子全枚举（%d 条）+ 84 个三元组 T≤48 完备枚举（多出 %d 条 >16 原子）"
                 "+ 4~9 元类别大分子搜索（%d 条）。" % (len(le16), n_from_tri, n_from_caps))
    lines.append("")
    lines.append("## 总体统计")
    lines.append("")
    lines.append(f"- 已知物质总数：**{len(sub_list)}** 条（去重分子式）")
    lines.append(f"- 511 类别：**全部有限**（无无限族）")
    lines.append("")
    lines.append("## 511 类别总表")
    lines.append("")
    lines.append("| # | 类别 | n | 判定 | 完备性 | 精确组成物质数 | 允许池物质数(已知) | 最大分子(已知) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for idx, (n, c) in enumerate([(n, c) for n in range(1, 10)
                                  for c in itertools.combinations(P.ORDER, n)], 1):
        S = frozenset(c)
        exact = groups.get(S, [])
        pool = [x for x in sub_list if eset_atoms(x["atoms"]) <= S]
        if n <= 3:
            comp = "完备"
        else:
            comp = "≤16完备+大分子搜索"
        cap = max((x["natoms"] for x in pool), default=0)
        lines.append(f"| {idx} | {' '.join(c)} | {n} | 有限 | {comp} | {len(exact)} | {len(pool)} | {cap} |")
    lines.append("")
    lines.append("## 每类精确组成物质清单")
    lines.append("")
    lines.append("> 说明：仅列出「组成元素恰好等于该类别」的物质；分子式写法如 `O2X`（O 2 个、X 1 个）。")
    lines.append("")
    for n in range(1, 10):
        for c in itertools.combinations(P.ORDER, n):
            S = frozenset(c)
            items = groups.get(S, [])
            if not items:
                continue
            lines.append(f"### {' '.join(c)}（{n} 元）— {len(items)} 条")
            lines.append("")
            lines.append("、".join(f"{x['formula']}({x['natoms']})" for x in items))
            lines.append("")
    open(BASE + r"\T4_CATALOG.md", "w", encoding="utf-8").write("\n".join(lines))
    print("saved T4_CATALOG.md, lines", len(lines))


if __name__ == "__main__":
    main()
