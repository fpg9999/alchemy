# -*- coding: utf-8 -*-
"""render_cross：渲染跨类/混合键型分子（S/C/L 三种键 + 三类元素）。

用法: python render_cross.py <examples.json> <out.png> <标题> [每行个数]
examples.json 每项含 formula / atoms / edges / place / feed / natoms。
"""
import json
import math
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import render_final as RF

S3 = math.sqrt(3)
FONT = RF.FONT
FONT_B = RF.FONT_B
font = RF.font
text_center = RF.text_center
draw_formula = RF.draw_formula

# 按大类着色（跨类图用；与纯大类图的元素色不同，便于看"族"）
FILLCAT = {"聚": "#93cf93", "动": "#e8a0b0", "散": "#b9a2e0"}
BOND = {"S": "#c0392b", "C": "#7d3f9c", "L": "#1f7a7a"}
APOTHEM = S3 / 2.0


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


def draw_mol(d, ex, box):
    x0, y0, w, h = box
    atoms = ex["atoms"]
    edges = [tuple(e) for e in ex["edges"]]
    place = {int(k): tuple(v) for k, v in ex["place"].items()}
    fallback = ex.get("fallback_place")  # 若无摆放，可用 JSON 里自带
    if not place and fallback:
        place = {int(k): tuple(v) for k, v in fallback.items()}
    xy = {i: (q, q + 2 * r) for i, (q, r) in place.items()}
    s = 30.0
    for _ in range(80):
        pts = {i: (1.5 * s * X, S3 / 2 * s * Y) for i, (X, Y) in xy.items()}
        xs = [p[0] for p in pts.values()]
        ys = [p[1] for p in pts.values()]
        bw, bh = max(xs) - min(xs) + 2.6 * s, max(ys) - min(ys) + 2.6 * s
        if bw <= w and bh <= h:
            break
        s *= 0.94
    pts = {i: (1.5 * s * X, S3 / 2 * s * Y) for i, (X, Y) in xy.items()}
    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    ox = x0 + w / 2 - (min(xs) + max(xs)) / 2
    oy = y0 + h / 2 - (min(ys) + max(ys)) / 2
    pos = {i: (pts[i][0] + ox, pts[i][1] + oy) for i in pts}
    polys = {i: hex_pts(pos[i][0], pos[i][1], s) for i in pos}

    for i, e in enumerate(atoms):
        d.polygon(polys[i], fill=FILLCAT[P.CAT[e]], outline="#333333",
                  width=max(1, int(s / 22)))

    for (i, j, m) in edges:
        dq = place[j][0] - place[i][0]
        dr = place[j][1] - place[i][1]
        t = P.classify_offset((dq, dr))
        ux, uy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        if t == "S":
            seg = common_edge(polys[i], polys[j])
            if len(seg) < 2:
                continue
            a, b = seg[0], seg[1]
        elif t == "C":
            a = (pos[i][0] + ux * s, pos[i][1] + uy * s)
            b = (pos[j][0] - ux * s, pos[j][1] - uy * s)
        else:
            a = (pos[i][0] + ux * APOTHEM * s, pos[i][1] + uy * APOTHEM * s)
            b = (pos[j][0] - ux * APOTHEM * s, pos[j][1] - uy * APOTHEM * s)
        nx, ny = -uy, ux
        gap = max(2.0, s * 0.16)
        for kk in range(m):
            off = (kk - (m - 1) / 2) * gap
            p1 = (a[0] + nx * off, a[1] + ny * off)
            p2 = (b[0] + nx * off, b[1] + ny * off)
            d.line([p1, p2], fill=BOND[t], width=max(2, int(s / 13)))

    for i, e in enumerate(atoms):
        size = max(9, int(s * 0.62))
        text_center(d, pos[i][0], pos[i][1], e, font(FONT_B, size), "#111111")
    return s


def main():
    src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    ncol = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    data = json.load(open(src, encoding="utf-8"))
    pw, ph = 400, 400
    left, top = 28, 132
    nrow = (len(data) + ncol - 1) // ncol
    W = left + ncol * pw + 24
    H = top + nrow * ph + 26
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 16), title, font=font(FONT_B, 27), fill="#111111")
    d.text((26, 56), "跨类键型：红=短键 S（共边）、紫=角键 C（角对角隔一边）、青=长键 L（同轴隔一空格）；"
                     "底色按大类：绿=聚、粉=动、紫=散。", font=font(FONT, 15), fill="#666666")
    d.text((26, 80), "每格上方：分子式 + 原子数 + 一个投料例（元素顺序 O X C P W L K A F）。",
           font=font(FONT, 15), fill="#888888")
    for i, ex in enumerate(data):
        r, c = divmod(i, ncol)
        x0 = left + c * pw + 3
        y0 = top + r * ph + 3
        w, h = pw - 6, ph - 6
        d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dddddd", width=1)
        d.text((x0 + 10, y0 + 6), f"{i+1:02d}", font=font(FONT_B, 15), fill="#999999")
        text_center(d, x0 + w / 2, y0 + 16,
                    f"{ex['formula']}   {ex.get('natoms', len(ex['atoms']))}原子",
                    font(FONT_B, 17), "#111111")
        d.text((x0 + 8, y0 + 32), f"投料 {tuple(ex.get('feed', []))}", font=font(FONT, 13), fill="#666666")
        draw_mol(d, ex, (x0 + 6, y0 + 50, w - 12, h - 58))
    img.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
