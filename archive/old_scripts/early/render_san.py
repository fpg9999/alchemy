# -*- coding: utf-8 -*-
"""render_san：散素（K/A/F，长键 L）物质表渲染。

长键 L：同轴、中间正好隔一个空格。两个格中心距 2√3·s，朝对方的边中点相距 √3·s，
直接把这段"跨空格"的线画成键（1~3 根平行线），中间那个空格不画格子。
"""
import json
import math
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import render_final as RF

S3 = math.sqrt(3)
FONT = RF.FONT
FONT_B = RF.FONT_B
font = RF.font
text_center = RF.text_center
draw_formula = RF.draw_formula

CN = {"K": "沌", "A": "气", "F": "焰"}
FILL = {"K": "#9b8cc9", "A": "#7fc48f", "F": "#e8744f"}   # 沌紫 / 气绿 / 焰橙
BONDC = "#1f7a7a"                                          # 长键：深青
BASE = r"G:\AI work\deepseek\work1\alchemy"
APOTHEM = S3 / 2.0


def hex_pts(cx, cy, s):
    return [(cx + s * math.cos(math.radians(60 * k)), cy + s * math.sin(math.radians(60 * k)))
            for k in range(6)]


def draw_molecule(d, item, box):
    x0, y0, w, h = box
    atoms = item["atoms"]
    edges = [tuple(e) for e in item["edges"]]
    xy = {int(k): tuple(v) for k, v in item["place_xy"].items()}
    s = 30.0
    for _ in range(60):
        pts = {i: (1.5 * s * X, S3 / 2 * s * Y) for i, (X, Y) in xy.items()}
        xs = [p[0] for p in pts.values()]
        ys = [p[1] for p in pts.values()]
        bw, bh = max(xs) - min(xs) + 2.4 * s, max(ys) - min(ys) + 2.4 * s
        if bw <= w and bh <= h:
            break
        s *= 0.93
    pts = {i: (1.5 * s * X, S3 / 2 * s * Y) for i, (X, Y) in xy.items()}
    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    ox = x0 + w / 2 - (min(xs) + max(xs)) / 2
    oy = y0 + h / 2 - (min(ys) + max(ys)) / 2
    pos = {i: (pts[i][0] + ox, pts[i][1] + oy) for i in pts}
    polys = {i: hex_pts(pos[i][0], pos[i][1], s) for i in pos}

    for i, e in enumerate(atoms):
        d.polygon(polys[i], fill=FILL[e], outline="#444444", width=max(1, int(s / 20)))
    # 长键：从 A 朝 B 的边中点画到 B 朝 A 的边中点（跨过中间空格）
    for (i, j, m) in edges:
        ux, uy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        a = (pos[i][0] + ux * APOTHEM * s, pos[i][1] + uy * APOTHEM * s)
        b = (pos[j][0] - ux * APOTHEM * s, pos[j][1] - uy * APOTHEM * s)
        nx, ny = -uy, ux
        gap = max(2.5, s * 0.14)
        for k in range(m):
            off = (k - (m - 1) / 2) * gap
            p1 = (a[0] + nx * off, a[1] + ny * off)
            p2 = (b[0] + nx * off, b[1] + ny * off)
            d.line([p1, p2], fill=BONDC, width=max(3, int(s / 12)))
    for i, e in enumerate(atoms):
        text_center(d, pos[i][0], pos[i][1] - s * 0.17, e, font(FONT_B, int(s * 0.58)), "#111111")
        text_center(d, pos[i][0], pos[i][1] + s * 0.33, CN[e], font(FONT, int(s * 0.38)), "#111111")
    return s


def group_key(it):
    k, a, f = it["vec"]
    if k and a and f:
        g = 4
    elif k and a:
        g = 1
    elif k and f:
        g = 2
    elif a and f:
        g = 3
    else:
        g = 0
    return (g, sum(it["vec"]), tuple(it["vec"]))


def make_all_table(items, path):
    ncol = 6
    pw, ph = 282, 320
    left, top = 26, 150
    nrow = (len(items) + ncol - 1) // ncol
    W = left + ncol * pw + 22
    H = top + nrow * ph + 26
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 18), "散素 · 自然反应可产出物质总表（29 种）", font=font(FONT_B, 30), fill="#111111")
    d.text((26, 62), "规则 1~8 同聚素；穷举投料 + 可达闭包，无并列。",
           font=font(FONT, 18), fill="#555555")
    d.text((26, 90), "长键 L 用奇数方向号（1/3/5/7/9/11）：两格同轴、中间正好隔一个空格（空格必须为空）。",
           font=font(FONT, 18), fill="#1f7a7a")
    d.text((26, 116), "青色线 = 长键（1~3 根）；紫=沌、绿=气、橙=焰；右上角为该分子的原子数。",
           font=font(FONT, 17), fill="#888888")
    for i, it in enumerate(items):
        r, c = divmod(i, ncol)
        x0 = left + c * pw + 3
        y0 = top + r * ph + 3
        w, h = pw - 6, ph - 6
        d.rectangle([x0, y0, x0 + w, y0 + h], fill="white", outline="#dddddd", width=1)
        d.text((x0 + 10, y0 + 7), f"{i+1:02d}", font=font(FONT_B, 16), fill="#999999")
        text_center(d, x0 + w - 40, y0 + 15, f"{it['natoms']}原子", font(FONT, 14), "#999999")
        draw_molecule(d, it, (x0 + 6, y0 + 24, w - 12, h - 96))
        draw_formula(d, x0 + w / 2, y0 + h - 62, it["formula"], 25, "#111111")
        draw_formula(d, x0 + w / 2, y0 + h - 32, it["zh"], 19, "#555555", bold=False)
    img.save(path)
    print("saved", path)


def make_page(path, title, subtitle, items, ncol=5, pw=300, ph=330):
    nrow = (len(items) + ncol - 1) // ncol
    left, top = 30, 128
    W = left + ncol * pw + 24
    H = top + nrow * ph + 30
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 18), title, font=font(FONT_B, 28), fill="#111111")
    d.text((26, 58), subtitle, font=font(FONT, 18), fill="#666666")
    d.text((26, 88), "青色线 = 长键 L（奇数方向，同轴隔一空格，同一对元素 1~3 根）；紫=沌、绿=气、橙=焰。",
           font=font(FONT, 17), fill="#888888")
    for i, it in enumerate(items):
        r, c = divmod(i, ncol)
        x0 = left + c * pw + 3
        y0 = top + r * ph + 3
        w, h = pw - 6, ph - 6
        d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dcdcdc", width=1)
        d.text((x0 + 10, y0 + 8), f"{i+1:02d}", font=font(FONT_B, 16), fill="#999999")
        draw_molecule(d, it, (x0 + 6, y0 + 26, w - 12, h - 88))
        draw_formula(d, x0 + w / 2, y0 + h - 56, it["formula"], 26, "#111111")
        draw_formula(d, x0 + w / 2, y0 + h - 24, it["zh"], 20, "#555555", bold=False)
        text_center(d, x0 + w - 34, y0 + 16, f"{it['natoms']}原子", font(FONT, 14), "#999999")
    img.save(path)
    print("saved", path)


def main():
    data = json.load(open(BASE + r"\substances_san.json", encoding="utf-8"))
    by = {x["formula"]: x for x in data}
    items = sorted(data, key=group_key)
    make_all_table(items, BASE + r"\san_all_29.png")
    g1 = ["K2", "A2", "A3", "K2A", "K2A2", "K2A3", "K2A4", "K2A5", "K2A6", "K2A7"]
    g2 = ["K2", "F2", "KF3", "K2F2", "K2F4", "K3F3", "K3F5", "A2", "AF2", "A2F2", "A3F2"]
    g3 = ["KAF", "KA2F", "KA3F", "K2AF2", "K2AF4", "K2A2F4", "K2A3F4", "K3AF", "K3AF3", "K3A2F"]
    make_page(BASE + r"\san_1_k_dui_a.png",
              "散素物质总表（29 种）· 图 1：单质 与 沌–气 系（10 种）",
              "沌（紫）、气（绿）组成的全部物质；沌2气7（K2A7）是最大的一个（9 个原子）。",
              [by[f] for f in g1])
    make_page(BASE + r"\san_2_k_dui_f_a_dui_f.png",
              "散素物质总表（29 种）· 图 2：沌–焰 系 与 气–焰 系（11 种）",
              "焰（橙）当叶子挂在沌/气上；焰–气–气–焰、焰–气–气–气–焰 这类链也在其中。",
              [by[f] for f in g2])
    make_page(BASE + r"\san_3_three_element.png",
              "散素物质总表（29 种）· 图 3：三元素化合物（10 种）",
              "同时含沌、气、焰的全部物质；注意 沌3气2焰（K3A2F）的骨架是三个沌成链、各挂一个气。",
              [by[f] for f in g3])


if __name__ == "__main__":
    main()
