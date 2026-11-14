# -*- coding: utf-8 -*-
"""render_catalog：类别总览图 + 最小无限核心的增长曲线。"""
import json
import math

from PIL import Image, ImageDraw

import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import render_final as RF

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT, FONT_B = RF.FONT, RF.FONT_B
font, text_center = RF.font, RF.text_center


def overview():
    st = json.load(open(BASE + r"\catalog_stats.json", encoding="utf-8"))
    W, H = 1400, 760
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 16), "511 个元素组合类别总览：有限 vs 无限（按类别元素数）", font=font(FONT_B, 28), fill="#111")
    d.text((30, 54), f"类别总数 {st['n_pool_categories']}；有限 {st['n_finite_categories']}，无限 {st['n_infinite_categories']}；"
                     f"≤16 原子物质总目录 {st['catalog_size']} 条", font=font(FONT, 17), fill="#555")
    left, top, right, bottom = 90, 130, 60, 110
    px0, py0, px1, py1 = left, top, W - right, H - bottom
    maxc = max(max(st["finite_by_size"].values()), max(st["infinite_by_size"].values()))
    bw = (px1 - px0) / 9
    for r in range(1, 10):
        fi = st["finite_by_size"].get(str(r), 0)
        inf = st["infinite_by_size"].get(str(r), 0)
        x0 = px0 + (r - 1) * bw + 8
        x1 = px0 + r * bw - 8
        hf = (fi / maxc) * (py1 - py0)
        hi = (inf / maxc) * (py1 - py0)
        d.rectangle([x0, py1 - hf, x1, py1], fill="#4c9a4c")
        d.rectangle([x0, py1 - hf - hi, x1, py1 - hf], fill="#c0392b")
        text_center(d, (x0 + x1) / 2, py1 + 20, str(r), font(FONT, 16), "#333")
        if fi:
            text_center(d, (x0 + x1) / 2, py1 - hf / 2, str(fi), font(FONT_B, 14), "white")
        if inf:
            text_center(d, (x0 + x1) / 2, py1 - hf - hi / 2, str(inf), font(FONT_B, 14), "white")
    d.line([(px0, py1), (px1, py1)], fill="#333", width=2)
    d.line([(px0, py0), (px0, py1)], fill="#333", width=2)
    d.text((px1 - 150, py1 + 45), "类别元素数", font=font(FONT_B, 17), fill="#333")
    d.rectangle([px1 - 240, py0 + 10, px1 - 226, py0 + 24], fill="#4c9a4c")
    d.text((px1 - 218, py0 + 8), "有限类别", font=font(FONT, 16), fill="#333")
    d.rectangle([px1 - 240, py0 + 38, px1 - 226, py0 + 52], fill="#c0392b")
    d.text((px1 - 218, py0 + 36), "无限类别", font=font(FONT, 16), fill="#333")
    img.save(BASE + r"\catalog_overview.png")
    print("saved catalog_overview.png")


def growth_curves():
    cores = json.load(open(BASE + r"\cores_growth.json", encoding="utf-8"))
    keys = list(cores.keys())
    cols = 3
    rows = (len(keys) + cols - 1) // cols
    pw, ph = 430, 340
    W, H = 40 + cols * pw + 30, 120 + rows * ph + 30
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 16), "最小无限类别的增长曲线：物质数（≤N 原子）随 N 增长", font=font(FONT_B, 27), fill="#111")
    d.text((30, 52), "横轴 N=总原子上限，纵轴=该类物质数（≤N，按分子式去重）。曲线斜率递增 → 无限增长。",
           font=font(FONT, 15), fill="#666")
    for i, key in enumerate(keys):
        r, c = divmod(i, cols)
        x0 = 30 + c * pw
        y0 = 100 + r * ph
        d.rectangle([x0 + 4, y0 + 4, x0 + pw - 4, y0 + ph - 4], outline="#dddddd")
        d.text((x0 + 12, y0 + 10), key.replace("/", "/"), font=font(FONT_B, 18), fill="#111")
        by = cores[key]["count_by_N"]
        Ns = sorted(int(k) for k in by)
        if not Ns:
            continue
        vals = [by[str(n)] for n in Ns]
        cx0, cy0, cx1, cy1 = x0 + 55, y0 + 50, x0 + pw - 20, y0 + ph - 45
        nmax = max(Ns)
        vmax = max(vals)
        d.line([(cx0, cy1), (cx1, cy1)], fill="#333", width=1)
        d.line([(cx0, cy0), (cx0, cy1)], fill="#333", width=1)
        pts = []
        for n, v in zip(Ns, vals):
            px = cx0 + (n / max(1, nmax)) * (cx1 - cx0)
            py = cy1 - (v / max(1, vmax)) * (cy1 - cy0)
            pts.append((px, py))
        d.line(pts, fill="#c0392b", width=2)
        for p in pts[:: max(1, len(pts) // 8)]:
            d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill="#c0392b")
        d.text((cx0, cy1 + 8), "N=2", font=font(FONT, 12), fill="#888")
        d.text((cx1 - 34, cy1 + 8), f"N={nmax}", font=font(FONT, 12), fill="#888")
        d.text((x0 + 12, y0 + ph - 26), f"总数(≤{nmax})={vals[-1]}", font=font(FONT, 13), fill="#555")
    img.save(BASE + r"\core_growth_curves.png")
    print("saved core_growth_curves.png")


if __name__ == "__main__":
    overview()
    growth_curves()
