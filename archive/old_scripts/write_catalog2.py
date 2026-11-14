# -*- coding: utf-8 -*-
"""write_catalog2：生成最终 CATALOG.md（511 类别目录 + 无限规律）。"""
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


def main():
    st = load("catalog2_stats.json")
    cats = load("catalog2_subsets.json")
    comps = load("catalog2_composition.json")
    mins = load("catalog2_minimal.json")
    extm = load("extended_finite_merged.json") or {}
    if not st or not cats:
        print("缺少 catalog2_*")
        return
    L = []
    A = L.append
    A("# 炼金术 · 全类别物质目录（511 个元素组合类别）")
    A("")
    A("> **口径**：类别 = 允许出现的元素集合（9 元素 O X C P W L K A F 的所有非空子集，共 511 个）。")
    A("> 物质按分子式统计；已验证「任何物质都可以用自己组成里的元素直接投料复现」（抽样 800/800），")
    A("> 因此类别 S 的物质 = 组成元素 ⊆ S 的全部可产出物质。")
    A("> **重要修正**：早期「有限类别封顶 16 原子」的假设是错的——大投料（T=32）实测发现 O/X/W 等")
    A("> 能产出 21~26 原子分子。本目录的有限/无限结论全部改为**大投料实测口径**（整锅成功=所有产物可摆）。")
    A("")
    A("## 总体统计")
    A("")
    A(f"- 类别总数 **{st['n_pool_categories']}**：无限 **{st['n_infinite']}**，有限 **{st['n_finite']}**")
    A(f"- 直接实测到无限证据的类别：{st['n_direct_evidence']} 个；最小无限核心 **{st['n_minimal']}** 个")
    A(f"- ≤16 原子的物质总目录：{st['catalog_size']} 条（分子式去重）")
    A("- **全部物质总数（含 17~23 原子的扩展段）：82335 条** = 82239（≤16）+ 96（>16，见 `CATALOG_FINITE_LISTS.md`）")
    A("")
    A("| 元素数 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for key, label in (("finite_by_size", "有限"), ("infinite_by_size", "无限")):
        A(f"| {label} | " + " | ".join(str(st[key].get(str(r), 0)) for r in range(1, 10)) + " |")
    A("")
    A("## 无限规律（对所有无限类别）")
    A("")
    A("### 判据")
    A("")
    A("1. **无限向上封闭**：若类别 S 无限，则任何 S 的超集也无限（同一投料在超集里也能用）。")
    A("2. 因此只需找**最小无限集合**（本目录实测出 "
      f"{st['n_minimal']} 个，见下表）；任何类别：含任一最小无限集合 → 无限，否则有限。")
    A("3. **共同机制**：每个最小无限集合里都存在可无限延长的部分——")
    A("   - 一条 **2 价元素链**（X / W / A 可首尾相接任意长，配合 3 价元素 O/P/K 作节点或封端）；或")
    A("   - 由 **3 价元素 O/P/K 组成的网络**（3 价原子可三分叉，网络可无限扩展）。")
    A("")
    A("### 最小无限集合与参数族")
    A("")
    A("| 最小无限集合 | 实测最大分子（T=32） | ≤16 原子物质数 | 参数族（m=1,2,3,…） |")
    A("|---|---|---|---|")
    for m in mins:
        elems = "/".join(m["elems"])
        fam = ""
        if m["families"]:
            f = max(m["families"], key=lambda x: len(x["members"]))
            mem = f["members"]
            show = mem[:3] + (["…"] if len(mem) > 3 else [])
            fam = f"方向 {f['dir']}：" + " → ".join(x["formula"] for x in show[:3]) + " → …"
        A(f"| {elems} | {m['evidence_max']} | {m['count_le16']} | {fam} |")
    A("")
    A("### 计数增长规律")
    A("")
    A("- 对每个最小无限集合，都给出「≤N 原子物质数」曲线（`catalog2_growth_curves.png`）。")
    A("- 规律：物质数随 N **持续增长且不停**（无封顶）；各核心的曲线在 ≤16 段见 JSON 的 count_by_N。")
    A("- 典型参数族（取自 `families_full/empirical`）：")
    A("  - `X_m K_2`：XK2 → X2K2 → X3K2 → …（X 链任意长，K2 封端）")
    A("  - `O_m K_{m+2}`：OK3 → O2K4 → O3K5 → …")
    A("  - `O_m X_m K_{m+2}`：OXK3 → O2X2K4 → O3X3K5 → …")
    A("  - 4 元/5 元最小集合同理：出现更长的 2 价链（如 W13、X13、A13）或 3 价网络。")
    A("")
    A("## 511 类别总表")
    A("")
    A("> 类型：无限=含 16 个最小无限集合之一；有限=实测封顶（部分类别封顶可达 23 原子）。")
    A("> 「实测最大分子」= 大投料实测中出现过的最大可摆分子（0 表示未发现 >16）。")
    A("> ★ = 该类有限但含 >16 原子物质，完整清单见 `CATALOG_FINITE_LISTS.md`。")
    A("")
    A("| # | 元素组合 | 中文 | 元素数 | 类型 | 实测最大分子 | ≤16原子数 | 无限核心 | 代表物质（前3） |")
    A("|---|---|---|---|---|---|---|---|---|")
    for i, x in enumerate(cats, 1):
        typ = "无限" if x["infinite"] else "有限"
        cores = "、".join(x["cores"]) if x["cores"] else "—"
        reps = " ".join(r["formula"] for r in x["reps"])
        key = "/".join(x["elems"])
        cnt = x["count_le16"]
        star = ""
        emax = x["evidence_max"]
        if not x["infinite"] and key in extm:
            cnt = extm[key]["count"]
            emax = max(emax, extm[key]["max"])
            if extm[key]["max"] > 16:
                star = "★"
        A(f"| {i} | {key} | {x['zh']} | {x['n_elems']} | {typ}{star} | {emax} | "
          f"{cnt} | {cores} | {reps} |")
    A("")
    A("## 精确元素组成的物质清单（每个物质只出现一次；此处只列 ≤16 原子部分）")
    A("")
    for key in sorted(comps, key=lambda k: (len(k.split("/")), [P.ORDER.index(e) for e in k.split("/")])):
        g = comps[key]
        A(f"### {key}（{g['zh']}） {'∞ 无限' if g['infinite'] else '有限'} · {g['count_le16']} 种")
        A("")
        if g["infinite"]:
            A(f"- 含无限核心：{'、'.join(g['cores'])}")
        chunks = [f"{s['formula']}（{s['zh']},{s['natoms']}）" for s in g["substances"]]
        for j in range(0, len(chunks), 6):
            A("  " + " | ".join(chunks[j:j + 6]))
        A("")
    A("## 文件与局限")
    A("")
    A("- JSON：`catalog2_subsets.json`（511 类别）、`catalog2_composition.json`（精确组成物质）、")
    A("  `catalog2_minimal.json`（最小无限集合+参数族）、`catalog2_stats.json`")
    A("- 图：`catalog2_overview.png`、`catalog2_growth_curves.png`、`core_families2.png`")
    A("- 局限：① 有限类是「大投料随机实测未超 16」（非形式化证明）；② 无限类的参数族给的是实测族，")
    A("  可能存在其它族；③ 同分异构按分子式统计，结构只存一种摆法。")
    open(BASE + r"\CATALOG.md", "w", encoding="utf-8").write("\n".join(L))
    print("saved CATALOG.md lines:", len(L))


if __name__ == "__main__":
    main()
