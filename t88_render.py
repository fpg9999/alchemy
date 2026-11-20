# -*- coding: utf-8 -*-
"""T88 环境群系图：6 个群系终态色块图 + 规模/反应/分层对比。

用法：python t88_render.py
输入：t88_analysis.json + t88_env_*.json
输出：images/t88_biomes.png、images/t88_biome_*.png
"""
from __future__ import annotations

import glob
import hashlib
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import t83_env_axes as T83
from alchemy import attrs as A

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"
INK = (32, 34, 40)
SUB = (96, 100, 110)
PALETTE = [
    (222, 92, 82), (70, 130, 190), (232, 168, 60), (86, 160, 110),
    (150, 110, 180), (200, 110, 150), (90, 170, 180), (170, 140, 90),
    (120, 150, 90), (200, 130, 80), (110, 120, 170), (160, 100, 100),
    (90, 140, 120), (180, 150, 180), (130, 160, 200), (210, 160, 120),
    (100, 180, 160), (190, 120, 60),
]


def fnt(size, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, size)


def color_of(f):
    h = hashlib.md5(f.encode("utf-8")).digest()
    c = PALETTE[h[0] % len(PALETTE)]
    k = 0.86 + 0.22 * (h[1] / 255.0)
    return tuple(min(255, int(v * k)) for v in c)


_CAT = None
_TC = {}


def catalog():
    global _CAT
    if _CAT is None:
        _CAT = T83.catalog_index()
    return _CAT


def type_of(f, khint=None):
    t = _TC.get(f)
    if t is not None:
        return t
    rec = catalog().get(f)
    k = 1
    if khint is not None:
        k = max(1, int(khint))
    elif rec is not None:
        try:
            units = A.skeleton_units(list(rec["atoms"]),
                                     [tuple(e) for e in rec["edges"]])
            k = max(1, len(units))
        except Exception:
            k = 1
    shape = [(0, 0)]
    if k == 2:
        shape = [(0, 0), (0, 1)]
    elif k == 3:
        shape = [(0, 0), (1, 0), (2, 0)]
    elif k == 4:
        shape = [(0, 0), (0, 1), (1, 0), (1, 1)]
    t = (k, shape, color_of(f))
    _TC[f] = t
    return t


def draw_world(d, ox, oy, cell, mols, W, H):
    grid = {}
    for item in mols:
        r, c, f = item[0], item[1], item[2]
        kh = item[3] if len(item) > 3 else None
        k, shape, col = type_of(f, kh)
        for (dr, dc) in shape:
            grid[(r + dr, c + dc)] = col
    for (r, c), col in grid.items():
        x0 = ox + c * cell
        y0 = oy + r * cell
        d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=col)
    # 同色相邻自然合并；cell 很小时不描边，避免整片发黑


def load_biomes(rows):
    out = []
    for r in rows:
        p = os.path.join(BASE, "t88_env_%s.json" % r["biome"].lower())
        if not os.path.exists(p):
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        out.append((r, d))
    return out


def bar_chart_a(d, x0, y0, w, h, rows):
    """A：终态分子数（柱）+ 物种数（标注）。"""
    d.text((x0, y0), "A 终态规模：分子数（柱）/ 物种数（黑字）", font=fnt(19, True), fill=INK)
    y0 += 34
    n = max(r["n_final"] for r in rows) or 1
    cols = len(rows)
    bw = (w - 40) / cols
    for i, r in enumerate(rows):
        bh = (h - 60) * r["n_final"] / n
        bx = x0 + 20 + i * bw + bw * 0.15
        by = y0 + h - 52
        d.rectangle([bx, by - bh, bx + bw * 0.7, by], fill=(88, 128, 190))
        d.text((bx, by - bh - 20), "%d" % r["n_final"], font=fnt(13), fill=SUB)
        d.text((bx, by + 6), r["biome"].replace("_", " "), font=fnt(12), fill=SUB)
        d.text((bx + bw * 0.05, by - bh - 40), "%d种" % r["n_distinct"],
               font=fnt(12), fill=INK)
    d.line([(x0 + 20, y0 + h - 52), (x0 + w - 10, y0 + h - 52)], fill=(120, 120, 128))


def bar_chart_b(d, x0, y0, w, h, rows):
    """B：反应类型堆叠（complete / incomplete / none）。"""
    d.text((x0, y0), "B resolve 反应类型（complete / incomplete）", font=fnt(19, True), fill=INK)
    y0 += 34
    n = max(r["n_complete"] + r["n_incomplete"] + r["n_none"] for r in rows) or 1
    cols = len(rows)
    bw = (w - 40) / cols
    for i, r in enumerate(rows):
        tot = r["n_complete"] + r["n_incomplete"] + r["n_none"]
        bh = (h - 60) * tot / n
        bx = x0 + 20 + i * bw + bw * 0.15
        by = y0 + h - 52
        h1 = bh * r["n_complete"] / max(1, tot)
        h2 = bh * r["n_incomplete"] / max(1, tot)
        d.rectangle([bx, by - bh, bx + bw * 0.7, by - h1], fill=(232, 168, 60))
        d.rectangle([bx, by - h1, bx + bw * 0.7, by], fill=(86, 160, 110))
        d.text((bx, by - bh - 20), "%d%s" % (tot, ""), font=fnt(13), fill=SUB)
        d.text((bx, by + 6), r["biome"].replace("_", " "), font=fnt(12), fill=SUB)
        if r["n_incomplete"] > 0:
            d.text((bx, by - bh - 38), "I%.0f%%" % (100.0 * r["n_incomplete"] / tot),
                   font=fnt(12), fill=SUB)
    d.line([(x0 + 20, y0 + h - 52), (x0 + w - 10, y0 + h - 52)], fill=(120, 120, 128))
    d.text((x0 + 60, y0 + h - 20), "橙=complete  绿=incomplete", font=fnt(13), fill=SUB)


def bar_chart_c(d, x0, y0, w, h, rows):
    """C：质量档 y 均值（轻/中/重）。"""
    d.text((x0, y0), "C 质量分层：三档 y 均值（越小越靠上）", font=fnt(19, True), fill=INK)
    y0 += 34
    n = max(r["y_heavy"] or 0 for r in rows) or 1
    cols = len(rows)
    bw = (w - 40) / cols
    colors = [(86, 160, 110), (88, 128, 190), (222, 92, 82)]
    for i, r in enumerate(rows):
        bx = x0 + 20 + i * bw + bw * 0.12
        by = y0 + h - 52
        for j, val in enumerate((r["y_light"], r["y_mid"], r["y_heavy"])):
            if val is None:
                continue
            bh = (h - 60) * val / n
            bxx = bx + j * bw * 0.22
            d.rectangle([bxx, by - bh, bxx + bw * 0.18, by], fill=colors[j])
            d.text((bxx, by - bh - 16), "%.0f" % val, font=fnt(11), fill=SUB)
        d.text((bx, by + 6), r["biome"].replace("_", " "), font=fnt(12), fill=SUB)
    d.line([(x0 + 20, y0 + h - 52), (x0 + w - 10, y0 + h - 52)], fill=(120, 120, 128))
    d.text((x0 + 60, y0 + h - 20), "绿=轻档 蓝=中档 红=重档", font=fnt(13), fill=SUB)


def main():
    ana = json.load(io.open(os.path.join(BASE, "t88_analysis.json"),
                            encoding="utf-8"))
    rows = ana["rows"]
    pairs = load_biomes(rows)
    W_IMG, H_IMG = 3000, 2160
    img = Image.new("RGB", (W_IMG, H_IMG), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 26), "T88 环境群系：不同元素子集在 T87 规则下的终态",
           font=fnt(32, True), fill=INK)
    d.text((40, 74),
           "3~9 种元素 · 每群系 2,500 分子 · 240×160 硬边界方格 · 800 拍（400 拍降到 10°C 后恒温 400 拍）· "
           "连续重力 + 非对称力 + 骨架占格 + resolve 完全/不完全反应",
           font=fnt(16), fill=SUB)

    cell = 4
    pw, ph = 240 * cell, 160 * cell          # 960 x 640
    x0 = 40
    y0 = 130
    gap_x, gap_y = 22, 74
    for i, (r, data) in enumerate(pairs):
        row, col = divmod(i, 3)
        ox = x0 + col * (pw + gap_x)
        oy = y0 + row * (ph + gap_y + 84)
        mols = data["snapshots"][-1]["mols"]
        draw_world(d, ox, oy, cell, mols, 240, 160)
        d.rectangle([ox - 1, oy - 1, ox + pw, oy + ph], outline=(60, 60, 66))
        d.text((ox, oy - 26),
               "%s  %s" % (r["biome"], r["label"]), font=fnt(18, True), fill=INK)
        d.text((ox, oy + ph + 4),
               "N=%d  种=%d  最大团=%d (%.0f%%≥3团)  类型=%s"
               % (r["n_final"], r["n_distinct"], r["max_cluster"],
                  r["in_big_pct"], r["type"]), font=fnt(14), fill=SUB)
        d.text((ox, oy + ph + 24),
               "top: " + "  ".join("%s %.1f%%" % (f, p)
                                   for f, c, p in r["top5"][:3]),
               font=fnt(13), fill=(120, 96, 60))
        d.text((ox, oy + ph + 44),
               "y 轻/中/重 = %.0f/%s/%.0f   complete %d / incomplete %d"
               % (r["y_light"],
                  "-" if r["y_mid"] is None else "%.0f" % r["y_mid"],
                  r["y_heavy"], r["n_complete"], r["n_incomplete"]),
               font=fnt(13), fill=SUB)

    cy = y0 + 2 * (ph + gap_y + 84) + 6
    cw = (W_IMG - 80 - 40) / 3.0
    bar_chart_a(d, 40, cy, cw, 350, rows)
    bar_chart_b(d, 40 + cw + 20, cy, cw, 350, rows)
    bar_chart_c(d, 40 + 2 * (cw + 20), cy, cw, 350, rows)

    d.text((40, H_IMG - 46),
           "读图：每格=1 个骨架（k 骨架占 k 格），同物质同色、相邻同物质合并成大色块。质量档 y 越小越靠上。"
           "类型按优势物种份额（A 单主≥30% / B 主辅≥15% / C 双主 top1+top2≥50% / D 多主）。",
           font=fnt(14), fill=SUB)
    out = os.path.join(BASE, "images", "t88_biomes.png")
    img.save(out)
    print("saved", out, img.size)
    # 单张群系图
    for r, data in pairs:
        im2 = Image.new("RGB", (pw + 80, ph + 140), (255, 255, 255))
        d2 = ImageDraw.Draw(im2)
        d2.text((30, 16), "%s %s" % (r["biome"], r["label"]), font=fnt(20, True), fill=INK)
        draw_world(d2, 40, 60, cell, data["snapshots"][-1]["mols"], 240, 160)
        d2.rectangle([39, 59, 40 + pw, 60 + ph], outline=(60, 60, 66))
        d2.text((30, ph + 70),
                "N=%d  cells=%d  distinct=%d  max_cl=%d  complete/incomplete=%d/%d"
                % (r["n_final"], r["cells_used"], r["n_distinct"],
                   r["max_cluster"], r["n_complete"], r["n_incomplete"]),
                font=fnt(13), fill=SUB)
        p = os.path.join(BASE, "images", "t88_biome_%s.png" % r["biome"].lower())
        im2.save(p)
    print("saved 6 single-biome images")


if __name__ == "__main__":
    main()
