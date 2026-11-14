# -*- coding: utf-8 -*-
"""render_dong：动素（P/W/L，角键 C）物质表渲染。

与聚素 render_final.py 的区别只在于键的画法：
  聚素短键 S：两格共边 → 画共边的平行线；
  动素角键 C：两角之间正好隔一条格边 → 两格中心距 3s，朝对方的那两个角相距 s，
              直接把这段长 s 的"格边"画成键（1~3 根平行短线）。
用户坐标 (X,Y) 与屏幕坐标：screen = (1.5*s*X, sqrt(3)/2*s*Y)。
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

CN = {"P": "势", "W": "流", "L": "电"}
FILL = {"P": "#cf6a87", "W": "#5aa9d6", "L": "#e8c351"}   # 势玫红 / 流蓝 / 电金
BONDC = "#7d3f9c"                                          # 角键：紫
BASE = r"G:\AI work\deepseek\work1\alchemy"


def hex_pts(cx, cy, s):
    return [(cx + s * math.cos(math.radians(60 * k)), cy + s * math.sin(math.radians(60 * k)))
            for k in range(6)]


def draw_molecule(d, item, box):
    x0, y0, w, h = box
    atoms = item["atoms"]
    edges = [tuple(e) for e in item["edges"]]
    xy = {int(k): tuple(v) for k, v in item["place_xy"].items()}
    # 自适应缩放
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

    # 元素底色
    for i, e in enumerate(atoms):
        d.polygon(polys[i], fill=FILL[e], outline="#444444", width=max(1, int(s / 20)))
    # 角键：两格中心距 3s，朝对方的两个角相距 s —— 把这段"格边"画成 1~3 根平行短线
    for (i, j, m) in edges:
        ux, uy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        a = (pos[i][0] + ux * s, pos[i][1] + uy * s)
        b = (pos[j][0] - ux * s, pos[j][1] - uy * s)
        nx, ny = -uy, ux
        gap = max(2.5, s * 0.14)
        for k in range(m):
            off = (k - (m - 1) / 2) * gap
            p1 = (a[0] + nx * off, a[1] + ny * off)
            p2 = (b[0] + nx * off, b[1] + ny * off)
            d.line([p1, p2], fill=BONDC, width=max(3, int(s / 12)))
    # 文字
    for i, e in enumerate(atoms):
        text_center(d, pos[i][0], pos[i][1] - s * 0.17, e, font(FONT_B, int(s * 0.58)), "#111111")
        text_center(d, pos[i][0], pos[i][1] + s * 0.33, CN[e], font(FONT, int(s * 0.38)), "#111111")
    return s


def group_key(it):
    p, w, l = it["vec"]
    if p and w and l:
        g = 4
    elif p and w:
        g = 1
    elif p and l:
        g = 2
    elif w and l:
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
    d.text((26, 18), "动素 · 自然反应可产出物质总表（29 种）", font=font(FONT_B, 30), fill="#111111")
    d.text((26, 62), "规则 1~8 同聚素；穷举总原子 ≤36 的所有投料 + 产物再投料闭包，无并列、无规则 9。",
           font=font(FONT, 18), fill="#555555")
    d.text((26, 90), "角键 C 用偶数方向号（2/4/6/8/10/12）：两个格子的角相对、中间正好隔一条格边。",
           font=font(FONT, 18), fill="#7d3f9c")
    d.text((26, 116), "紫短线 = 角键（1~3 根）；玫红=势、蓝=流、金=电；右上角为该分子的原子数。",
           font=font(FONT, 17), fill="#888888")
    for i, it in enumerate(items):
        r, c = divmod(i, ncol)
        x0 = left + c * pw + 3
        y0 = top + r * ph + 3
        w = pw - 6
        h = ph - 6
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
    d.text((26, 88), "紫短线 = 角键 C（偶数方向，两个角之间隔一条格边，同一对元素 1~3 根）；玫红=势、蓝=流、金=电。",
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
    data = json.load(open(BASE + r"\substances_dong.json", encoding="utf-8"))
    by = {x["formula"]: x for x in data}
    items = sorted(data, key=group_key)
    make_all_table(items, BASE + r"\dong_all_29.png")

    g1 = ["P2", "W2", "W3", "P2W", "P2W2", "P2W3", "P2W4", "P2W5", "P2W6", "P2W7"]
    g2 = ["P2", "L2", "PL3", "P2L2", "P2L4", "P3L3", "P3L5", "W2", "WL2", "W2L2", "W3L2"]
    g3 = ["PWL", "PW2L", "PW3L", "P2WL2", "P2WL4", "P2W2L4", "P2W3L4", "P3WL", "P3WL3", "P3W2L"]
    make_page(BASE + r"\dong_1_shi_liu.png",
              "动素物质总表（29 种）· 图 1：单质 与 势–流 系（10 种）",
              "势（玫红）、流（蓝）组成的全部物质；势2流7（P2W7）是最大的一个（9 个原子）。",
              [by[f] for f in g1])
    make_page(BASE + r"\dong_2_shi_dian_liu_dian.png",
              "动素物质总表（29 种）· 图 2：势–电 系 与 流–电 系（11 种）",
              "电（金）当叶子挂在势/流上；电–流–流–电、电–流–流–流–电 这类链也在其中。",
              [by[f] for f in g2])
    make_page(BASE + r"\dong_3_three_element.png",
              "动素物质总表（29 种）· 图 3：三元素化合物（10 种）",
              "同时含势、流、电的全部物质；注意 势3流2电（P3W2L）的骨架是三个势成链、各挂一个流。",
              [by[f] for f in g3])


if __name__ == "__main__":
    main()
