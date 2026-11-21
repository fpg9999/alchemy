# -*- coding: utf-8 -*-
"""T92: 3/4/5 元子集群系网格 —— 汇总图 v2（Pillow，只读 t92_biome_grid.json）"""
import io
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
IN = os.path.join(BASE, "t92_biome_grid.json")
OUT = os.path.join(BASE, "images", "t92_biome_grid.png")
JSON_OUT = os.path.join(BASE, "t92_biome_summary.json")

INK = (28, 30, 36)
SUB = (95, 100, 112)
GRIDC = (228, 230, 236)
BG = (250, 250, 247)
COL = {
    "A 单主": (214, 96, 76),
    "B 主辅": (228, 152, 58),
    "C 双主": (90, 140, 190),
    "D 多主": (128, 134, 146),
}


def fnt(sz, bold=False):
    p = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
    return ImageFont.truetype(p, sz)


def load():
    d = json.load(io.open(IN, encoding="utf-8"))
    return d["config"], d["biomes"]


def panel(d, box, title, sub=""):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], fill=(255, 255, 255), outline=(198, 200, 208))
    d.text((x0 + 14, y0 + 8), title, font=fnt(20, True), fill=INK)
    if sub:
        d.text((x0 + 14, y0 + 34), sub, font=fnt(13), fill=SUB)
    top = y0 + (58 if sub else 42)
    return x0 + 62, top, x1 - 18, y1 - 44


def plot_box(d, box, xlab, ylab, ymax, yticks=4, xcats=None):
    x0, y0, x1, y1 = box
    # 背景网格
    for i in range(yticks + 1):
        y = y1 - (y1 - y0) * i / yticks
        d.line([(x0, y), (x1, y)], fill=GRIDC)
        d.text((x0 - 8 - len("%.2f" % (ymax * i / yticks)) * 7, y - 9),
               "%.2f" % (ymax * i / yticks), font=fnt(13), fill=SUB)
    d.line([(x0, y1), (x1, y1)], fill=(90, 92, 100), width=2)
    d.line([(x0, y0), (x0, y1)], fill=(90, 92, 100), width=2)
    d.text(((x0 + x1) / 2 - len(xlab) * 7, y1 + 10), xlab, font=fnt(15), fill=SUB)
    if xcats:
        n = len(xcats)
        for i, lab in enumerate(xcats):
            x = x0 + (i + 0.5) * (x1 - x0) / n
            d.text((x - len(str(lab)) * 7, y1 + 10), str(lab), font=fnt(15), fill=INK)
    return x0, y0, x1 - 12, y1


def ypos(v, vmax, box):
    x0, y0, x1, y1 = box
    return y1 - (y1 - y0) * min(1.0, max(0.0, v / vmax))


def xcat(i, n, box):
    x0, y0, x1, y1 = box
    return x0 + (i + 0.5) * (x1 - x0) / n


def main():
    cfg, bs = load()
    n = len(bs)
    sizes = sorted({b["n_elem"] for b in bs})
    types = ["A 单主", "B 主辅", "C 双主", "D 多主"]
    W, H = 2600, 1640
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((40, 22), "T92 群系网格：全部 3/4/5 元元素子集的环境群系扫描", font=fnt(30, True), fill=INK)
    d.text((40, 68),
           "规则=T87（连续重力+非对称三素力+骨架占格+resolve 完全/不完全+10°C 恒温）；世界 160×110、%d 分子、400 拍；共 %d 个群系"
           % (cfg["n_mol"], n), font=fnt(17), fill=SUB)
    d.text((40, 94),
           "类型：优势种 ≥30%→A 单主，≥15%→B 主辅，前二合计 ≥50%→C 双主，否则 D 多主；HHI=Σp²（越大越集中）",
           font=fnt(15), fill=SUB)

    # A: HHI vs 元素数
    box = panel(d, (40, 126, 860, 640), "A 集中度 HHI vs 元素数", "每个点=一个群系；颜色=类型；纵轴=HHI")
    pb = plot_box(d, box, "元素数", "HHI", max(0.06, max(b["hhi"] for b in bs) * 1.1),
                  yticks=4, xcats=sizes)
    for i, el in enumerate(sizes):
        pts = [b for b in bs if b["n_elem"] == el]
        x = xcat(i, len(sizes), pb)
        for k, b in enumerate(pts):
            jx = ((k % 15) - 7) / 7.0 * 26
            y = ypos(b["hhi"], max(0.06, max(x["hhi"] for x in bs) * 1.1), pb)
            d.ellipse([x + jx - 4, y - 4, x + jx + 4, y + 4], fill=COL[b["type"]],
                      outline=(255, 255, 255))
    for i, t in enumerate(types):
        d.rectangle([760, 168 + i * 22, 774, 180 + i * 22], fill=COL[t])
        d.text((780, 166 + i * 22), t, font=fnt(13), fill=SUB)

    # B: 类型构成
    box = panel(d, (880, 126, 1700, 640), "B 类型构成（按元素数分组）", "纵轴=群系数（每组的合计）")
    pb = plot_box(d, box, "元素数", "群系数", max(sum(1 for x in bs if x["n_elem"] == e) for e in sizes),
                  yticks=4, xcats=sizes)
    tall = max(sum(1 for x in bs if x["n_elem"] == e) for e in sizes)
    for i, el in enumerate(sizes):
        cnt = {t: sum(1 for x in bs if x["n_elem"] == el and x["type"] == t) for t in types}
        x = xcat(i, len(sizes), pb)
        bw = min(120, (pb[2] - pb[0]) / len(sizes) * 0.5)
        y = pb[3]
        for t in types:
            h = cnt[t] / tall * (pb[3] - pb[1])
            d.rectangle([x - bw / 2, y - h, x + bw / 2, y], fill=COL[t])
            if cnt[t] > 0:
                d.text((x - 8, y - h - 20), str(cnt[t]), font=fnt(14), fill=INK)
            y -= h
    for i, t in enumerate(types):
        d.rectangle([1600, 168 + i * 22, 1614, 180 + i * 22], fill=COL[t])
        d.text((1620, 166 + i * 22), t, font=fnt(13), fill=SUB)

    # C: 投料池 vs 终态种数
    box = panel(d, (1720, 126, 2560, 640), "C 投料池 vs 终态种数", "横轴=投料池种数(对数)；纵轴=终态种数；颜色=类型")
    xmax = max(b["feed_pool"] for b in bs)
    ymax = max(b["n_distinct"] for b in bs)
    pb = plot_box(d, box, "投料池种数（对数）", "终态种数", ymax * 1.05, yticks=4)
    for b in bs:
        lx = math.log(max(2, b["feed_pool"])) / math.log(xmax)
        x = pb[0] + lx * (pb[2] - pb[0])
        y = ypos(b["n_distinct"], ymax * 1.05, pb)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=COL[b["type"]], outline=(255, 255, 255))
    d.text((pb[0] - 6, pb[3] + 10), "2", font=fnt(13), fill=SUB)
    d.text((pb[2] - 30, pb[3] + 10), str(xmax), font=fnt(13), fill=SUB)

    # D: 优势种份额 vs 元素数
    box = panel(d, (40, 668, 860, 1180), "D 优势种份额 vs 元素数", "纵轴=优势种份额；红线=A 单主门槛 30%")
    pb = plot_box(d, box, "元素数", "优势种份额", 0.62, yticks=4, xcats=sizes)
    for i, el in enumerate(sizes):
        pts = [b["dominant_share"] for b in bs if b["n_elem"] == el]
        x = xcat(i, len(sizes), pb)
        for k, v in enumerate(pts):
            jx = ((k % 13) - 6) / 6.0 * 24
            y = ypos(v, 0.62, pb)
            d.ellipse([x + jx - 4, y - 4, x + jx + 4, y + 4], fill=COL["B 主辅"],
                      outline=(255, 255, 255))
    yy = ypos(0.30, 0.62, pb)
    d.line([(pb[0], yy), (pb[2], yy)], fill=(206, 90, 80), width=2)
    d.text((pb[2] - 120, yy - 20), "A 单主线 30%", font=fnt(13), fill=(206, 90, 80))

    # E: 重档占比
    box = panel(d, (880, 668, 1700, 1180), "E 重档（mass>2.30）占比 vs 元素数", "纵轴=重档占比；黑线=组内均值")
    pb = plot_box(d, box, "元素数", "重档占比", 1.0, yticks=4, xcats=sizes)
    for i, el in enumerate(sizes):
        pts = [b["tiers_mass"][2] for b in bs if b["n_elem"] == el]
        x = xcat(i, len(sizes), pb)
        for k, v in enumerate(pts):
            jx = ((k % 13) - 6) / 6.0 * 24
            y = ypos(v, 1.0, pb)
            d.ellipse([x + jx - 4, y - 4, x + jx + 4, y + 4], fill=COL["A 单主"],
                      outline=(255, 255, 255))
        m = sum(pts) / len(pts)
        yy = ypos(m, 1.0, pb)
        d.line([(x - 34, yy), (x + 34, yy)], fill=(50, 52, 60), width=3)

    # F: 文字统计
    box = panel(d, (1720, 668, 2560, 1180), "F 分组统计", "")
    fx0, fy0, fx1, fy1 = box
    lines = []
    for el in sizes:
        pts = [b for b in bs if b["n_elem"] == el]
        lines.append("N=%d 元：%d 个群系" % (el, len(pts)))
        lines.append("  平均 HHI %.3f，平均终态种数 %.0f" % (
            sum(p["hhi"] for p in pts) / len(pts),
            sum(p["n_distinct"] for p in pts) / len(pts)))
        lines.append("  平均反应 %.0f，平均重档 %.0f%%" % (
            sum(p["n_react"] for p in pts) / len(pts),
            100 * sum(p["tiers_mass"][2] for p in pts) / len(pts)))
        cnt = {t: sum(1 for p in pts if p["type"] == t) for t in types}
        lines.append("  " + "  ".join("%s %d" % (t, cnt[t]) for t in types))
        lines.append("")
    lines.append("全体：%d 群系，平均 HHI %.3f，平均种数 %.0f" % (
        n, sum(b["hhi"] for b in bs) / n, sum(b["n_distinct"] for b in bs) / n))
    y = fy0 + 6
    for ln in lines:
        d.text((fx0, y), ln, font=fnt(16), fill=INK)
        y += 27

    d.text((40, 1540),
           "读图：元素数 3→5，HHI 与优势种份额下降、终态种数上升；重档占比三组都约 22%（投料按元素等份额配平，质量档分布与元素数基本无关），但单个群系可在 0~86% 间变化。",
           font=fnt(16), fill=SUB)
    d.text((40, 1572),
           "注意：700 分子 × 400 拍的小世界扫描，只用于趋势与分类；单群系结论以 T88（2500 分子、800 拍）为准。每个群系单 seed。",
           font=fnt(15), fill=SUB)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)

    summ = {"config": cfg, "n_biomes": n,
            "by_size": {str(el): {
                "n": sum(1 for b in bs if b["n_elem"] == el),
                "hhi_mean": sum(b["hhi"] for b in bs if b["n_elem"] == el) /
                             max(1, sum(1 for b in bs if b["n_elem"] == el)),
                "distinct_mean": sum(b["n_distinct"] for b in bs if b["n_elem"] == el) /
                                  max(1, sum(1 for b in bs if b["n_elem"] == el)),
                "type_counts": {t: sum(1 for b in bs if b["n_elem"] == el and b["type"] == t)
                                for t in types},
                "heavy_mean": sum(b["tiers_mass"][2] for b in bs if b["n_elem"] == el) /
                               max(1, sum(1 for b in bs if b["n_elem"] == el)),
            } for el in sizes}}
    io.open(JSON_OUT, "w", encoding="utf-8").write(
        json.dumps(summ, ensure_ascii=False, indent=1))
    print("saved", OUT, os.path.getsize(OUT))
    print("biomes", n)


if __name__ == "__main__":
    main()
