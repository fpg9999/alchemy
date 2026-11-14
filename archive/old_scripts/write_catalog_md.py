# -*- coding: utf-8 -*-
"""write_catalog_md：生成 CATALOG.md（511 类别总表 + 精确组成物质清单 + 无限规律）。"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def load(name, default=None):
    try:
        return json.load(open(BASE + "\\" + name, encoding="utf-8"))
    except Exception:
        return default


def sig(elems):
    return "/".join(sorted(elems, key=lambda e: P.ORDER.index(e)))


def main():
    stats = load("catalog_stats.json")
    cats = load("catalog_subsets.json")
    comps = load("catalog_composition.json")
    cores = load("cores_growth.json", {})
    fams = load("families.json", {})
    verify = load("finite_verify.json", {})
    if not stats or not cats:
        print("缺少 catalog_*.json，先跑 build_catalog.py")
        return

    lines = []
    A = lines.append
    A("# 炼金术 · 全类别物质目录（511 个元素组合类别）")
    A("")
    A("> 口径：类别 = **允许出现的元素集合**（9 元素的所有非空子集，共 511 个）。")
    A("> 物质按分子式统计；已验证「任何物质都可以用自己组成里的元素直接投料复现」（抽样 800/800）。")
    A("> 因此：**类别 S 的物质 = 组成元素 ⊆ S 的全部物质**。全部物质由全 9 元素 ≤16 原子全扫描得到。")
    A("")
    A("## 总体统计")
    A("")
    A(f"- 类别总数：{stats['n_pool_categories']}")
    A(f"- 有限类别：{stats['n_finite_categories']}；无限类别：{stats['n_infinite_categories']}")
    A(f"- ≤16 原子的物质总目录：{stats['catalog_size']} 条；精确元素组成种类：{stats['n_composition_groups']}")
    A(f"- 有限/无限类别按元素数分布：")
    A("")
    A("| 元素数 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for key, label in (("finite_by_size", "有限"), ("infinite_by_size", "无限")):
        row = " | ".join(str(stats[key].get(str(r), 0)) for r in range(1, 10))
        A(f"| {label} | {row} |")
    A("")
    A("## 无限判据（本目录的有限/无限结论）")
    A("")
    A("### 最小无限类别（实测出的“无限核心”）")
    A("")
    A("| 核心 | 类型 | 最小例子 | 增长计数（物质数 ≤N，N=8/10/12/14/16/18/20） | 无限规律 |")
    A("|---|---|---|---|---|")
    minf = load("minimal_infinite.json", {})
    for key in minf.get("minimal", []):
        elems = key.split("/")
        c = cores.get(key, {})
        cnt = c.get("count_by_N", {})
        row = "/".join(str(cnt.get(str(n), "?")) for n in (8, 10, 12, 14, 16, 18, 20))
        A(f"| {key} | 无限 | | {row} | {stats.get('law_hint', '')} |")
    A("")
    A("## 511 类别总表")
    A("")
    A("> 列说明：元素组合 = 类别允许的元素（字母=符号）；类型=有限/无限；≤16原子数=该类别中已枚举的物质个数；")
    A("> 无限类别的“无限核心”= 该类别含有的最小无限子集；“规律”见上一节。")
    A("")
    A("| # | 元素组合 | 中文 | 元素数 | 类型 | ≤16原子物质数 | 无限核心 / 备注 | 代表物质（前 3） |")
    A("|---|---|---|---|---|---|---|---|")
    for i, x in enumerate(cats, 1):
        elems = "/".join(x["elems"])
        typ = "**无限**" if x["infinite"] else "有限"
        note = ""
        if x["infinite"]:
            note = "、".join(x["cores"])
        else:
            mx = x["max_natoms"]
            note = f"封顶 {mx} 原子"
            v = verify.get(sig(x["elems"]))
            if v:
                note += f"（大投料实测≤{v['max']}）"
        reps = " ".join(x["formulas_le16"][:3])
        A(f"| {i} | {elems} | {x['zh']} | {x['n_elems']} | {typ} | {x['count_le16']} | {note} | {reps} |")
    A("")
    A("## 精确元素组成的物质清单（每个物质只出现一次）")
    A("")
    A("> 按“分子里出现的元素集合”分组。有限组成 = 完整清单；无限组成 = ≤16 原子部分 + 无限说明。")
    A("")
    for key in sorted(comps, key=lambda k: (len(k.split("/")), [P.ORDER.index(e) for e in k.split("/")])):
        g = comps[key]
        A(f"### {key} （{g['zh']}）  {'∞ 无限' if g['infinite'] else '有限'} · {g['count_le16']} 种")
        A("")
        if g["infinite"]:
            A(f"- 无限核心：{', '.join(g['cores'])}")
        chunks = []
        for s in g["substances"]:
            chunks.append(f"{s['formula']}（{s['zh']}，{s['natoms']}）")
        for j in range(0, len(chunks), 6):
            A("  " + " | ".join(chunks[j:j + 6]))
        A("")
    A("## 文件")
    A("")
    A("- `catalog_subsets.json`：511 类别汇总（含有限类完整分子式清单）")
    A("- `catalog_composition.json`：511 个精确组成分组（全部物质）")
    A("- `catalog_stats.json`：统计")
    A("- `cores_growth.json`：最小无限类别的精确增长计数与代表")
    A("- `families.json`：最小无限类别的参数族（方向/序列）")
    A("- 图：`catalog_overview.png`、`core_growth_curves.png`、`core_families.png`")
    open(BASE + r"\CATALOG.md", "w", encoding="utf-8").write("\n".join(lines))
    print("saved CATALOG.md, lines:", len(lines))


if __name__ == "__main__":
    main()
