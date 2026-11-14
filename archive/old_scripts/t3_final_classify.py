# -*- coding: utf-8 -*-
"""t3_final_classify：生成 511 类别修正分类表（9 最小核心 = 2 个不同大类 3 价 + 1 个 2 价）。

输出:
  classification_revised.json   —— 511 条：elements / n / infinite / cores / known_count(<=16) / max_natoms_catalog
  CLASSIFICATION_REVISED.md     —— 511 行表格 + 统计 + 证据说明
"""
import itertools
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
THREE = set("OPK")
TWO = set("XWA")


def elem_set(f):
    out = set()
    i = 0
    while i < len(f):
        out.add(f[i])
        i += 1
        while i < len(f) and f[i].isdigit():
            i += 1
    return frozenset(out)


def main():
    cat = json.load(open(BASE + r"\catalog_raw_compact.json", encoding="utf-8"))
    per = defaultdict(lambda: {"count": 0, "max": 0})
    for x in cat:
        s = elem_set(x["formula"])
        per[s]["count"] += 1
        per[s]["max"] = max(per[s]["max"], x["natoms"])

    # 证据文件
    try:
        gp = json.load(open(BASE + r"\t3_growth_triples.json", encoding="utf-8"))
    except Exception:
        gp = {}
    try:
        probe = json.load(open(BASE + r"\t3_triple_probe_raw.json", encoding="utf-8"))
    except Exception:
        probe = {}
    try:
        an = json.load(open(BASE + r"\t3_subset_anneal.json", encoding="utf-8"))
    except Exception:
        an = []
    anneal = {}
    for r in an:
        k = "/".join(r["elems"])
        if k not in anneal or (r.get("max") or 0) > anneal[k].get("max", 0):
            anneal[k] = r

    rows = []
    for n in range(1, 10):
        for c in itertools.combinations(P.ORDER, n):
            S = frozenset(c)
            a = len(S & THREE)
            b = len(S & TWO)
            cores = []
            if a >= 2 and b >= 1:
                for x in itertools.combinations(sorted(S & THREE), 2):
                    for y in sorted(S & TWO):
                        cores.append(set(x) | {y})
            inf = bool(cores)
            key = "/".join(c)
            # 证据：三元组实测最大（T=64 精确扫描）
            ev = None
            if n == 3:
                pr = probe.get(key, {})
                ev = {T: pr[T]["max"] for T in ("48", "56", "64") if T in pr}
                if not ev and key in gp:
                    ev = {T: gp[key][T]["max"] for T in gp[key]}
            rows.append({
                "elements": list(c), "n": n, "infinite": inf,
                "cores": ["/".join(sorted(m)) for m in cores],
                "known_count_16": per.get(S, {}).get("count", 0),
                "max_catalog": per.get(S, {}).get("max", 0),
                "evidence": ev,
                "anneal96": anneal.get(key, {}).get("max") if key in anneal else None,
            })

    out = {
        "criterion": "类别 S 无限 ⇔ S 含 9 个最小无限核心之一：两个不同大类的 3 价元素 + 一个 2 价元素"
                     "（3 价 ∈ {O,P,K}，2 价 ∈ {X,W,A}）",
        "n_total": len(rows),
        "n_infinite": sum(1 for r in rows if r["infinite"]),
        "n_finite": sum(1 for r in rows if not r["infinite"]),
        "by_size": {n: {"inf": sum(1 for r in rows if r["n"] == n and r["infinite"]),
                        "fin": sum(1 for r in rows if r["n"] == n and not r["infinite"])}
                    for n in range(1, 10)},
        "minimal_infinite": ["/".join(sorted(set(x) | {y}))
                             for x in itertools.combinations(sorted(THREE), 2) for y in sorted(TWO)],
        "rows": rows,
        "caveat": "有限/无限判定是实测口径下的工作分类（无限核心的无穷性由 T=64 的 42 原子分子等证据支持，"
                  "非形式化证明）；有限类“完整清单”受扫描截断限制，见说明。",
    }
    json.dump(out, open(BASE + r"\classification_revised.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # Markdown 表
    L = []
    L.append("# 511 元素组合类别 · 修正分类表")
    L.append("")
    L.append("> 本表是对 `CATALOG.md` 分类部分的**修正**。物质清单本身（≤16 原子全扫描 82239 条）仍然有效；")
    L.append("> 需要修正的是「有限/无限」标签与「最小无限核心」列表。")
    L.append("")
    L.append("## 判据")
    L.append("")
    L.append("> **类别 S 无限 ⇔ S 同时含有：① {O,P,K} 中至少 2 个（不同大类的 3 价元素）；"
             "② {X,W,A} 中至少 1 个（2 价元素）。**")
    L.append("")
    L.append("等价说法：S 包含下表 9 个「最小无限三元组」之一（向上封闭）。")
    L.append("")
    L.append("| 最小无限核心 | T=48 最大分子 | T=56 | T=64 |")
    L.append("|---|---|---|---|")
    for core in out["minimal_infinite"]:
        ev = probe.get(core, {})
        L.append(f"| {core} | {ev.get('48', {}).get('max', '-')} | "
                 f"{ev.get('56', {}).get('max', '-')} | {ev.get('64', {}).get('max', '-')} |")
    L.append("")
    L.append("对照：其余三元组在同样 T=64 全枚举下的最大分子只有 18~31（明显封顶），"
             "例如 O/X/A=31、O/X/W=31、X/P/W=31、X/K/A=31、P/W/A=31、W/K/A=31、O/P/K=26、O/W/A=23、X/P/A=23、X/W/K=23。")
    L.append("")
    L.append("## 统计")
    L.append("")
    L.append(f"- 类别总数 **{out['n_total']}**，其中 **无限 {out['n_infinite']}**，**有限 {out['n_finite']}**。")
    L.append(f"- 旧版分类为无限 304 / 有限 207（16 个最小核心），本表修正为 224 / 287（9 个最小核心）。")
    L.append("")
    L.append("| 元素数 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    L.append("| 无限 | " + " | ".join(str(out["by_size"][n]["inf"]) for n in range(1, 10)) + " |")
    L.append("| 有限 | " + " | ".join(str(out["by_size"][n]["fin"]) for n in range(1, 10)) + " |")
    L.append("")
    L.append("## 511 类别总表")
    L.append("")
    L.append("> 物质数 = `catalog_raw_compact.json`（≤16 原子全 9 元素全投料扫描）中「组成元素恰好等于该类别」的物质数；")
    L.append("> 有限类在更大原子数下可能还有少量物质（见「有限类封顶突破」一节）。")
    L.append("")
    L.append("| # | 类别（元素） | n | 判定 | 最小核心 | 已收物质数(≤16) | 已收最大原子 |")
    L.append("|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        name = " ".join(r["elements"])
        judge = "**无限**" if r["infinite"] else "有限"
        cores = ", ".join(r["cores"][:3]) + ("…" if len(r["cores"]) > 3 else "")
        L.append(f"| {i} | {name} | {r['n']} | {judge} | {cores} | {r['known_count_16']} | {r['max_catalog']} |")
    L.append("")
    L.append("## 有限类封顶突破（重要修正）")
    L.append("")
    L.append("早期「有限类封顶 16 原子（后续扩到 23）」的说法不成立。实测已确认的更大分子：")
    L.append("")
    L.append("| 类别 | 分子式 | 原子数 | 投料（9 元向量） | 校验 |")
    L.append("|---|---|---|---|---|")
    L.append("| X/C/K/A | X6C9K11A7 | 33 | [11,15,21,17] @T=64 | 精确全枚举 + 可摆 |")
    L.append("| O/X/W/A/C/L/F | O8X13W10A15 | 46 | [13,18,17,23,7,11,7] @T=96 | 随机搜索 + 可摆 |")
    L.append("| K/X/W/A/C/L/F | X16C2W8K6A14 | 46 | [8,22,14,20,12,12,8] @T=96 | 随机搜索 + 可摆 |")
    L.append("| 全 9 元素 | O3X8C15P10WK36A22F2 | 97 | [3,8,15,10,1,0,36,22,2] @T=97 | 一锅一分子 + 可摆（10M 预算） |")
    L.append("")
    L.append("因此：① 上表「有限」类别中有一部分（尤其 4~7 元、含 K/A 的组合）真实物质数可能超过 ≤16 扫描；")
    L.append("② 上表「无限」类别在 T=64 已实测到 42 原子分子（O/X/K 的 O9X10K23、X/P/K 的 X10P9K23、"
             "P/K/A 的 P9K23A10 等），而非常规的「最大 16」。")
    L.append("")
    L.append("## 证据与脚本")
    L.append("")
    L.append("- 精确全枚举：`t3_growth_triples.py`/`t3_growth_scan.py`（T=48/56/64，记录最大单分子）")
    L.append("- 大 T 探针：`t3_triple_probe.py`、`t3_exact_growth.py`（含 {X,C,K,A} 全枚举到 T=64）")
    L.append("- 大分子搜索：`t3_max_search.py`（找到 66/68 原子）、`t3_anneal.py`（找到 97/129 原子一锅一分子）、")
    L.append("  `t3_subset_anneal.py`（子集固定 T 搜索）")
    L.append("- 数据：`t3_growth_triples.json`、`t3_triple_probe_raw.json`、`t3_subset_anneal.json`、`t3_max_search.json`")
    L.append("")
    open(BASE + r"\CLASSIFICATION_REVISED.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("n_infinite", out["n_infinite"], "n_finite", out["n_finite"])
    print("by_size", out["by_size"])
    print("saved classification_revised.json & CLASSIFICATION_REVISED.md")


if __name__ == "__main__":
    main()
