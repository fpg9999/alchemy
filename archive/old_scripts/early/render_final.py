# -*- coding: utf-8 -*-
"""把 29 种聚素物质画成图"""
import json
import math
import sys
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont

S3 = math.sqrt(3)
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
CN = {"O": "秩", "X": "晶", "C": "冰"}
FILL = {"O": "#6bbf6b", "X": "#f2a24a", "C": "#7fb6e8"}   # 秩绿 / 晶橙 / 冰蓝
BONDC = "#c0392b"


def font(path, size):
    return ImageFont.truetype(path, size)


def text_center(d, cx, cy, text, fnt, fill="#111111"):
    bb = d.textbbox((0, 0), text, font=fnt)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text((cx - w / 2 - bb[0], cy - h / 2 - bb[1]), text, font=fnt, fill=fill)


def draw_formula(d, cx, cy, text, size, fill="#111111", bold=True, align="center"):
    f_main = font(FONT_B if bold else FONT, size)
    f_sub = font(FONT_B if bold else FONT, int(size * 0.62))
    segs = []
    buf, cur = "", None
    for ch in text:
        t = "sub" if ch.isdigit() else "main"
        if t != cur and buf:
            segs.append((buf, cur))
            buf = ""
        cur, buf = t, buf + ch
    if buf:
        segs.append((buf, cur))
    widths = [d.textlength(s, font=(f_main if t == "main" else f_sub)) for s, t in segs]
    total = sum(widths)
    x = cx if align == "left" else cx - total / 2
    base = cy + size * 0.34
    for (seg, t), w in zip(segs, widths):
        if t == "main":
            d.text((x, base), seg, font=f_main, fill=fill, anchor="ls")
        else:
            d.text((x, base + size * 0.16), seg, font=f_sub, fill=fill, anchor="ls")
        x += w


def hex_pts(cx, cy, s):
    return [(cx + s * math.cos(math.radians(60 * k)), cy + s * math.sin(math.radians(60 * k)))
            for k in range(6)]


def common_edge(p1, p2, tol=1e-6):
    out = []
    for a in p1:
        for b in p2:
            if abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol:
                out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    return out


def draw_molecule(d, item, box):
    x0, y0, w, h = box
    atoms = item["atoms"]
    edges = [tuple(e) for e in item["edges"]]
    place = {int(k): tuple(v) for k, v in item["place"].items()}
    # 计算尺寸
    s = 30.0
    for _ in range(40):
        pts = {i: (1.5 * s * q, S3 * s * (r + q / 2)) for i, (q, r) in place.items()}
        xs = [p[0] for p in pts.values()]
        ys = [p[1] for p in pts.values()]
        bw, bh = max(xs) - min(xs) + 2.4 * s, max(ys) - min(ys) + 2.4 * s
        if bw <= w and bh <= h:
            break
        s *= 0.93
    pts = {i: (1.5 * s * q, S3 * s * (r + q / 2)) for i, (q, r) in place.items()}
    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    ox = x0 + w / 2 - (min(xs) + max(xs)) / 2
    oy = y0 + h / 2 - (min(ys) + max(ys)) / 2
    pos = {i: (pts[i][0] + ox, pts[i][1] + oy) for i in pts}
    polys = {i: hex_pts(pos[i][0], pos[i][1], s) for i in pos}

    # 元素底色
    for i, e in enumerate(atoms):
        d.polygon(polys[i], fill=FILL[e], outline="#444444", width=max(1, int(s / 20)))
    # 键（平行线）
    for (i, j, m) in edges:
        seg = common_edge(polys[i], polys[j])
        if len(seg) < 2:
            continue
        a, b = seg[0], seg[1]
        ux, uy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ux, uy)
        nx, ny = -uy / L, ux / L
        gap = max(3.0, s * 0.17)
        for k in range(m):
            off = (k - (m - 1) / 2) * gap
            p1 = (a[0] + nx * off, a[1] + ny * off)
            p2 = (b[0] + nx * off, b[1] + ny * off)
            d.line([p1, p2], fill=BONDC, width=max(3, int(s / 13)))
    # 文字
    for i, e in enumerate(atoms):
        tc = "#111111"
        text_center(d, pos[i][0], pos[i][1] - s * 0.17, e, font(FONT_B, int(s * 0.58)), tc)
        text_center(d, pos[i][0], pos[i][1] + s * 0.33, CN[e], font(FONT, int(s * 0.38)), tc)
    return s


def panel(img, d, box, item, idx):
    x0, y0, w, h = box
    d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dcdcdc", width=1)
    d.text((x0 + 10, y0 + 8), f"{idx:02d}", font=font(FONT_B, 16), fill="#999999")
    draw_molecule(d, item, (x0 + 6, y0 + 26, w - 12, h - 88))
    draw_formula(d, x0 + w / 2, y0 + h - 56, item["formula"], 26, "#111111")
    draw_formula(d, x0 + w / 2, y0 + h - 24, item["zh"], 20, "#555555", bold=False)
    text_center(d, x0 + w - 34, y0 + 16, f"{item['natoms']}原子", font(FONT, 14), "#999999")


def make_page(path, title, subtitle, items, ncol=5, pw=300, ph=318):
    nrow = (len(items) + ncol - 1) // ncol
    left, top = 30, 128
    W = left + ncol * pw + 24
    H = top + nrow * ph + 30
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 18), title, font=font(FONT_B, 28), fill="#111111")
    d.text((26, 58), subtitle, font=font(FONT, 18), fill="#666666")
    d.text((26, 88), "红平行线 = 短键（聚素之间），同一对元素之间 1~3 根；单元格里大字=元素符号，小字=中文名。",
           font=font(FONT, 17), fill="#888888")
    for i, it in enumerate(items):
        r, c = divmod(i, ncol)
        panel(img, d, (left + c * pw + 3, top + r * ph + 3, pw - 6, ph - 6), it, i + 1)
    img.save(path)
    print("saved", path)


def main():
    data = json.load(open(r"G:\AI work\deepseek\work1\alchemy\substances.json", encoding="utf-8"))
    by = {x["formula"]: x for x in data}
    g1 = ["O2", "X2", "X3", "O2X", "O2X2", "O2X3", "O2X4", "O2X5", "O2X6", "O2X7"]
    g2 = ["O2", "C2", "OC3", "O2C2", "O2C4", "O3C3", "O3C5", "X2", "XC2", "X2C2", "X3C2"]
    g3 = ["OXC", "OX2C", "OX3C", "O2XC2", "O2XC4", "O2X2C4", "O2X3C4", "O3XC", "O3XC3", "O3X2C"]
    base = r"G:\AI work\deepseek\work1\alchemy"
    make_page(base + r"\final_1_zhi_jing.png",
              "聚素物质总表（29 种）· 图 1：单质 与 秩–晶 系（10 种）",
              "秩（绿）、晶（橙）组成的全部物质；秩2晶7（O2X7）是最大的一个（9 个原子）。",
              [by[f] for f in g1])
    make_page(base + r"\final_2_zhi_bing_jing_bing.png",
              "聚素物质总表（29 种）· 图 2：秩–冰 系 与 晶–冰 系（11 种）",
              "冰（蓝）当叶子挂在秩/晶上；冰–晶–晶–冰、冰–晶–晶–晶–冰 这类链也在其中。",
              [by[f] for f in g2])
    make_page(base + r"\final_3_three_element.png",
              "聚素物质总表（29 种）· 图 3：三元素化合物（10 种）",
              "同时含秩、晶、冰的全部物质；注意 秩3晶2冰（O3X2C）的骨架是三个秩连成链、各挂一个晶。",
              [by[f] for f in g3])


if __name__ == "__main__":
    main()
