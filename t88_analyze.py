# -*- coding: utf-8 -*-
"""T88 环境群系对比分析：读 t88_env_*.json，汇总成一张表 + 分类。

用法：python t88_analyze.py
输出：t88_analysis.json（summary 表 + 每个群系的指标）
"""
from __future__ import annotations

import glob
import io
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

NAMES = ["B3_OFL", "B3_OXC", "B4_OXKF", "B5_OXKAF", "B6_OXCKAF", "B9_all9"]
LABEL = {
    "B3_OFL": "{O,F,L} 三族各一",
    "B3_OXC": "{O,X,C} 全三价",
    "B4_OXKF": "{O,X,K,F} 缺动素",
    "B5_OXKAF": "{O,X,K,A,F}",
    "B6_OXCKAF": "{O,X,C,K,A,F} 缺动素",
    "B9_all9": "九元素全开",
}


def classify(dom, top2, n_species):
    """按优势度给群系类型：A 单主 / B 主辅 / C 双主 / D 多主。"""
    if dom >= 0.30:
        return "A 单主"
    if n_species <= 3:
        return "A 单主"
    if dom + top2 >= 0.50 and dom < 0.30:
        return "C 双主"
    if dom >= 0.15:
        return "B 主辅"
    return "D 多主"


def load(name):
    p = os.path.join(BASE, "t88_env_%s.json" % name.lower())
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


def main():
    rows = []
    details = {}
    for name in NAMES:
        r = load(name)
        if r is None:
            print("missing:", name)
            continue
        cfg, s = r["config"], r["summary"]
        top = s["top"]
        comp_total = s["n_final"]
        dom = top[0][1] / max(1, comp_total) if top else 0.0
        top2 = top[1][1] / max(1, comp_total) if len(top) > 1 else 0.0
        mass = s["y_mean_mass"]
        clusters = s["clusters"]
        row = {
            "biome": name, "label": LABEL.get(name, ""),
            "subset": cfg["subset"], "n_elems": len(cfg["subset"]),
            "feed_species": cfg["feed"]["n_species"],
            "feed_atoms": cfg["feed"]["atoms"],
            "atoms_per_mol": cfg["feed"]["atoms_per_mol"],
            "valence": cfg["feed"]["valence_share"],
            "n0": s["n0"], "n_final": s["n_final"],
            "cells_used": s["cells_used"],
            "cells_pct": round(100.0 * s["cells_used"] / s["cells_total"], 2),
            "n_distinct": s["n_distinct"],
            "n_complete": s["n_complete"],
            "n_incomplete": s["n_incomplete"],
            "n_none": s["n_none"],
            "n_react": s["n_react"],
            "new_species": s["n_new_species"],
            "conservation_ok": s["conservation_ok"],
            "y_light": mass[0], "y_mid": mass[1], "y_heavy": mass[2],
            "mass_share": [round(x, 4) for x in s["tiers"]["mass"]],
            "clusters": clusters["n_components"],
            "max_cluster": clusters["max"],
            "in_big_pct": round(100.0 * clusters["in_big"] / max(1, s["n_final"]), 2),
            "band_react": s["band_react"],
            "top5": [[f, c, round(100.0 * c / max(1, comp_total), 2)]
                     for f, c in top[:5]],
            "HHI": s["HHI"], "dominant_share": round(dom, 4),
            "type": classify(dom, top2, s["n_distinct"]),
            "runtime_s": cfg["runtime_s"],
        }
        rows.append(row)
        details[name] = r

    out = {"rows": rows,
           "notes": [
               "每个群系 2,500 分子、240×160 硬边界世界、800 拍（400 拍降到 10°C 后恒温 400 拍）",
               "规则 = T87：连续重力 + 非对称分子间力（无匹配度）+ 骨架占格 + resolve",
               "投料 = 目录中元素集合 ⊆ 子集的 2~8 原子分子式，IPF 配平到等元素份额",
               "类型按优势物种份额：A 单主 ≥30%；B 主辅 ≥15%；C 双主 (top1+top2)≥50%；D 多主",
           ]}
    io.open(os.path.join(BASE, "t88_analysis.json"), "w",
            encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))

    hdr = ("%-9s %-16s %2s %5s %5s %5s %4s %5s %4s %7s %5s %6s %5s %5s %s"
           % ("群系", "元素", "nE", "N0", "N", "格数", "%", "种", "新",
              "反应", "最大团", "y轻", "y中", "y重", "类型"))
    print(hdr)
    def fy(v):
        return "-" if v is None else "%.1f" % v
    for r in rows:
        print("%-9s %-16s %2d %5d %5d %5d %5.1f %5d %4d %7d %5d %6s %5s %6s %s"
              % (r["biome"], "".join(r["subset"]), r["n_elems"], r["n0"],
                 r["n_final"], r["cells_used"], r["cells_pct"],
                 r["n_distinct"], r["new_species"], r["n_react"],
                 r["max_cluster"], fy(r["y_light"]), fy(r["y_mid"]),
                 fy(r["y_heavy"]), r["type"]))
    print()
    for r in rows:
        print("%-9s complete %5d  incomplete %5d  none %3d | HHI %.3f 优势 %.1f%% | top: %s"
              % (r["biome"], r["n_complete"], r["n_incomplete"], r["n_none"],
                 r["HHI"], 100 * r["dominant_share"],
                 ", ".join("%s %.1f%%" % (f, p) for f, c, p in r["top5"])))
    print("\nsaved t88_analysis.json")


if __name__ == "__main__":
    main()
