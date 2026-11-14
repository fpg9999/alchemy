# -*- coding: utf-8 -*-
"""t15_render.py：绘制「终态三价骨架不在 45 库中」的实例（骨架高亮，其余灰色）"""
import json
import math
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
FILL = {"O": (107, 191, 107), "X": (240, 160, 75), "C": (127, 182, 232),
        "P": (240, 130, 185), "W": (201, 162, 39), "L": (255, 224, 102),
        "K": (150, 110, 220), "A": (143, 214, 192), "F": (224, 90, 79)}
GRAY = (214, 214, 214)
TRI = {"O", "P", "K"}
FONT = R.FONT
FONT_B = R.FONT_B
font = R.font
text_center = R.text_center
draw_formula = R.draw_formula
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}


def draw(d, rec, isk, box):
    atoms = rec["molecule_atoms"]
    edges = [tuple(e) for e in rec["molecule_edges"]]
    place = {int(k): tuple(v) for k, v in rec["place"].items()}
    n = len(atoms)
    s = 90.0
    for _ in range(90):
        pts = [R.center_of(place[i], s) for i in range(n)]
        bw = max(p[0] for p in pts) - min(p[0] for p in pts) + 2.4 * s
        bh = max(p[1] for p in pts) - min(p[1] for p in pts) + 2.4 * s
        if bw <= box[2] and bh <= box[3]:
            break
        s *= 0.93
    pts = [R.center_of(place[i], s) for i in range(n)]
    ox = box[0] + box[2] / 2 - (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    oy = box[1] + box[3] / 2 - (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    pos = [(p[0] + ox, p[1] + oy) for p in pts]
    polys = [R.hex_pts(pos[i][0], pos[i][1], s) for i in range(n)]
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = R.rel_type(dd)
        col = BONDC.get(t, "#555")
        width = max(1, int(s / 12)) if t in ("S", "C") else max(1, int(s / 16))
        if t == "S":
            sv = R.common_vertices(polys[i], polys[j])
            if len(sv) >= 2:
                R.ray_offset_line(d, sv[0], sv[1], col, width, m)
        elif t == "C":
            p1, p2 = R.nearest_vertices(polys[i], polys[j])
            R.ray_offset_line(d, p1, p2, col, width, m)
        elif t == "L":
            p1 = R.ray_exit(polys[i], pos[i], pos[j])
            p2 = R.ray_exit(polys[j], pos[j], pos[i])
            if p1 and p2:
                ux, uy = p2[0] - p1[0], p2[1] - p1[1]
                L = math.hypot(ux, uy)
                nx, ny = -uy / L, ux / L
                for k in range(m):
                    off = (k - (m - 1) / 2) * max(1.5, s * 0.12)
                    a = (p1[0] + nx * off, p1[1] + ny * off)
                    b = (p2[0] + nx * off, p2[1] + ny * off)
                    R.dashed(d, a, b, col, width)
    for i, el in enumerate(atoms):
        fill = FILL.get(el, GRAY) if i in isk else GRAY
        d.polygon(polys[i], fill=fill, outline="#333", width=max(1, int(s / 20)))
        if s >= 9:
            text_center(d, pos[i][0], pos[i][1], el, font(FONT_B, int(s * 0.5)), "#111")


def main():
    d0 = json.load(open(BASE + r"\t15_forms.json", encoding="utf-8"))
    want = ["O3P", "O3KA2", "CP2K3", "O2K4", "O2K6", "O2P6", "O5P5K2", "O4X9P19W4K5"]
    byf = {}
    for x in d0:
        if x["example"] not in byf or x["n"] > byf[x["example"]]["n"]:
            byf[x["example"]] = x
    picks = [byf[f] for f in want if f in byf and byf[f].get("place")]
    missing = [f for f in want if f in byf and not byf[f].get("place")]
    if missing:
        print("no place, skipped:", missing)
    print("picked:", [(x["example"], x["n"]) for x in picks])
    ncol, pw, ph = 2, 900, 560
    nrow = (len(picks) + ncol - 1) // ncol
    W, H = 30 + ncol * pw + 20, 150 + nrow * ph + 20
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 16), "终态三价骨架：不在 45 种骨架库中的实例（彩色=三价骨架原子，灰色=二价/一价装饰）",
           font=font(FONT_B, 26), fill="#111")
    d.text((24, 52), "45 库 = 3（无三价）+7（单三价模块）+35（6 级中间态双/三三价骨架）。",
           font=font(FONT, 17), fill="#555")
    d.text((24, 78), "以下七/八例的终态三价连通块都超出该库：含同类三价键（O–O/P–P/K–K）、4 原子以上连通块、或带多键的混合骨架。",
           font=font(FONT, 17), fill="#b8860b")
    for k, rec in enumerate(picks):
        r, c = divmod(k, ncol)
        x0 = 30 + c * pw + 4
        y0 = 150 + r * ph + 4
        w, h = pw - 8, ph - 8
        d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dddddd")
        d.text((x0 + 12, y0 + 8), f"{k+1:02d}  {rec['example']}（三价骨架 {rec['n']} 原子）",
               font=font(FONT_B, 22), fill="#111")
        isk = set(rec["component"])
        draw(d, rec, isk, (x0 + 10, y0 + 44, w - 20, h - 110))
        d.text((x0 + 12, y0 + h - 58), "骨架原子：" + "".join(rec["atoms"]) +
               "    骨架边：" + str(rec["edges"]), font=font(FONT, 14), fill="#444")
    img.save(BASE + r"\images\t15_new_skeletons.png")
    print("saved images/t15_new_skeletons.png")


if __name__ == "__main__":
    main()
