# -*- coding: utf-8 -*-
"""T92 群系网格统计（只读 t92_biome_grid.json，打印 markdown 片段）"""
import io
import json
import os
import statistics as st

BASE = r"G:\AI work\deepseek\work1\alchemy"
IN = os.path.join(BASE, "t92_biome_grid.json")


def main():
    d = json.load(io.open(IN, encoding="utf-8"))
    cfg, bs = d["config"], d["biomes"]
    print("总群系数:", len(bs))
    types = ["A 单主", "B 主辅", "C 双主", "D 多主"]
    print("\n## 按元素数\n")
    print("| 元素数 | 群系数 | 平均 HHI | 中位 HHI | 平均终态种数 | 平均反应 | 平均重档 | A/B/C/D |")
    print("|---|---|---|---|---|---|---|---|")
    for el in sorted({b["n_elem"] for b in bs}):
        p = [b for b in bs if b["n_elem"] == el]
        cnt = {t: sum(1 for x in p if x["type"] == t) for t in types}
        print("| %d | %d | %.3f | %.3f | %.0f | %.0f | %.0f%% | %d/%d/%d/%d |" % (
            el, len(p), sum(x["hhi"] for x in p) / len(p),
            st.median([x["hhi"] for x in p]),
            sum(x["n_distinct"] for x in p) / len(p),
            sum(x["n_react"] for x in p) / len(p),
            100 * sum(x["tiers_mass"][2] for x in p) / len(p),
            cnt["A 单主"], cnt["B 主辅"], cnt["C 双主"], cnt["D 多主"]))
    print("\n总体类型:", {t: sum(1 for x in bs if x["type"] == t) for t in types})

    print("\n## 最集中（HHI 最高）")
    for b in sorted(bs, key=lambda x: -x["hhi"])[:8]:
        print("| %s | %d 元 | pool %d | HHI %.3f | 优势 %s %.1f%% | 种数 %d | %s |" % (
            b["name"], b["n_elem"], b["feed_pool"], b["hhi"], b["dominant"],
            100 * b["dominant_share"], b["n_distinct"], b["type"]))

    print("\n## 最分散（HHI 最低）")
    for b in sorted(bs, key=lambda x: x["hhi"])[:5]:
        print("| %s | %d 元 | pool %d | HHI %.4f | 种数 %d | %s |" % (
            b["name"], b["n_elem"], b["feed_pool"], b["hhi"], b["n_distinct"], b["type"]))

    print("\n## 多样性最高（终态种数）")
    for b in sorted(bs, key=lambda x: -x["n_distinct"])[:8]:
        print("| %s | %d 元 | 种数 %d | HHI %.3f | 反应 %d | %s |" % (
            b["name"], b["n_elem"], b["n_distinct"], b["hhi"], b["n_react"], b["type"]))

    print("\n## A 单主群系（dom>=30%）")
    a = [b for b in bs if b["type"] == "A 单主"]
    print("数量:", len(a))
    for b in sorted(a, key=lambda x: -x["dominant_share"])[:10]:
        print("| %s | %d 元 | pool %d | %s %.1f%% | HHI %.3f | N %d→%d |" % (
            b["name"], b["n_elem"], b["feed_pool"], b["dominant"],
            100 * b["dominant_share"], b["hhi"], b["n0"], b["n_final"]))

    print("\n## 重档最高")
    for b in sorted(bs, key=lambda x: -x["tiers_mass"][2])[:8]:
        print("| %s | 重档 %.0f%% | y均值 %s | type %s |" % (
            b["name"], 100 * b["tiers_mass"][2],
            "/".join("%.0f" % v if v is not None else "-" for v in b["y_mean_mass"]), b["type"]))

    print("\n## 反应最多")
    for b in sorted(bs, key=lambda x: -x["n_react"])[:8]:
        print("| %s | 反应 %d | complete %d / incomplete %d | 种数 %d |" % (
            b["name"], b["n_react"], b["n_complete"], b["n_incomplete"], b["n_distinct"]))

    # 相关性
    def corr(a, b):
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((x - mb) ** 2 for x in b)
        if va <= 0 or vb <= 0:
            return 0.0
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5

    print("\n## 相关性（Pearson）")
    for k in ["n_elem", "feed_pool", "n_react", "n_distinct", "tiers_mass"]:
        if k == "tiers_mass":
            xs = [b["tiers_mass"][2] for b in bs]
        else:
            xs = [b[k] for b in bs]
        print("- %s vs HHI: %.3f ／ vs 种数: %.3f" % (
            k, corr(xs, [b["hhi"] for b in bs]),
            corr(xs, [b["n_distinct"] for b in bs])))


if __name__ == "__main__":
    main()
