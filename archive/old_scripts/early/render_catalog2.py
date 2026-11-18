# -*- coding: utf-8 -*-
"""render_catalog2：类别总览图 + 最小无限核心的计数增长曲线（数据来自 catalog2_*）。"""
import json
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import render_final as RF

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT, FONT_B = RF.FONT, RF.FONT_B
font, text_center = RF.font, RF.text_center


def overview():
    st = json.load(open(BASE + r"\catalog2_stats.json", encoding="utf-8"))
    W, H = 1400, 780
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 16), f"511 个元素组合类别：有限 {st['n_finite']} vs 无限 {st['n_infinite']}", font=font(FONT_B, 28), fill="#111")
    d.text((30, 58), f"分类基于大投料实测（整锅成功口径）：直接实测到「无限证据」的类别 {st['n_direct_evidence']} 个，"
                     f"最小无限核心 {st['n_minimal']} 个；≤16 原子物质总目录 {st['catalog_size']} 条。",
           font=font(FONT, 16), fill="#555")
    left, top, right, bottom = 90, 140, 60, 110
    px0, py0, px1, py1 = left, top, W - right, H - bottom
    maxc = max(st["finite_by_size"].get(str(r), 0) + st["infinite_by_size"].get(str(r), 0) for r in range(1, 10))
    bw = (px1 - px0) / 9
    for r in range(1, 10):
        fi = st["finite_by_size"].get(str(r), 0)
        inf = st["infinite_by_size"].get(str(r), 0)
        x0 = px0 + (r - 1) * bw + 10
        x1 = px0 + r * bw - 10
        hf = (fi / maxc) * (py1 - py0)
        hi = (inf / maxc) * (py1 - py0)
        d.rectangle([x0, py1 - hf, x1, py1], fill="#4c9a4c")
        d.rectangle([x0, py1 - hf - hi, x1, py1 - hf], fill="#c0392b")
        text_center(d, (x0 + x1) / 2, py1 + 20, str(r), font(FONT, 17), "#333")
        if fi:
            text_center(d, (x0 + x1) / 2, py1 - hf / 2, str(fi), font(FONT_B, 15), "white")
        if inf:
            text_center(d, (x0 + x1) / 2, py1 - hf - hi / 2, str(inf), font(FONT_B, 15), "white")
    d.line([(px0, py1), (px1, py1)], fill="#333", width=2)
    d.line([(px0, py0), (px0, py1)], fill="#333", width=2)
    d.text((px1 - 120, py1 + 46), "类别元素数", font=font(FONT_B, 17), fill="#333")
    d.rectangle([px1 - 230, py0 + 8, px1 - 216, py0 + 22], fill="#c0392b")
    d.text((px1 - 208, py0 + 6), "无限类别", font=font(FONT, 16), fill="#333")
    d.rectangle([px1 - 230, py0 + 36, px1 - 216, py0 + 50], fill="#4c9a4c")
    d.text((px1 - 208, py0 + 34), "有限类别", font=font(FONT, 16), fill="#333")
    d.text((30, py0 - 6), "柱高 = 类别数", font=font(FONT_B, 17), fill="#333")
    img.save(BASE + r"\catalog2_overview.png")
    print("saved catalog2_overview.png")


def curves():
    mins = json.load(open(BASE + r"\catalog2_minimal.json", encoding="utf-8"))
    cols = 3
    rows = (len(mins) + cols - 1) // cols
    pw, ph = 430, 330
    W, H = 40 + cols * pw + 30, 120 + rows * ph + 30
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 16), "最小无限核心：物质数（≤N 原子）曲线（数据取 ≤16 原子目录）", font=font(FONT_B, 26), fill="#111")
    d.text((30, 52), "横轴 N，纵轴该类物质数。斜率持续增加即无限增长；每类还给出实测最大分子（T=24/32）。",
           font=font(FONT, 15), fill="#666")
    for i, m in enumerate(mins):
        r, c = divmod(i, cols)
        x0 = 30 + c * pw
        y0 = 100 + r * ph
        d.rectangle([x0 + 4, y0 + 4, x0 + pw - 4, y0 + ph - 4], outline="#dddddd")
        d.text((x0 + 12, y0 + 8), "/".join(m["elems"]), font=font(FONT_B, 17), fill="#111")
        by = m["count_by_N"]
        Ns = sorted(int(k) for k in by)
        vals = [by[str(n)] for n in Ns]
        cx0, cy0, cx1, cy1 = x0 + 52, y0 + 40, x0 + pw - 18, y0 + ph - 40
        nmax, vmax = max(Ns), max(vals)
        d.line([(cx0, cy1), (cx1, cy1)], fill="#333", width=1)
        d.line([(cx0, cy0), (cx0, cy1)], fill="#333", width=1)
        pts = [(cx0 + (n / nmax) * (cx1 - cx0), cy1 - (v / max(1, vmax)) * (cy1 - cy0)) for n, v in zip(Ns, vals)]
        d.line(pts, fill="#c0392b", width=2)
        for p in pts[::2]:
            d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill="#c0392b")
        d.text((x0 + 12, y0 + ph - 22), f"≤16:{vals[-1]}  (T=32 实测最大 {m['evidence_max']})",
               font=font(FONT, 12), fill="#555")
    img.save(BASE + r"\catalog2_growth_curves.png")
    print("saved catalog2_growth_curves.png")


if __name__ == "__main__":
    overview()
    curves()
