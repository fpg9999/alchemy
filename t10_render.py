# -*- coding: utf-8 -*-
"""t10_render.py：三价骨架模块库 + 实例（骨架原子高亮、装饰原子灰色）"""
import json
import math
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
font = R.font
FONT = R.FONT
FONT_B = R.FONT_B
text_center = R.text_center
draw_formula = R.draw_formula

TRI_FILL = {"O": (107, 191, 107), "P": (240, 130, 185), "K": (150, 110, 220)}
DEC_FILL = (208, 208, 208)
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}
CN = {"O": "秩", "P": "势", "K": "沌", "X": "晶", "C": "冰", "W": "流",
      "L": "电", "A": "气", "F": "焰"}


def node(d, cx, cy, r, fill, label, sub=None, outline="#333"):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=2)
    text_center(d, cx, cy - (6 if sub else 0), label, font(FONT_B, int(r * 0.95)), "#111")
    if sub:
        text_center(d, cx, cy + r * 0.5, sub, font(FONT, int(r * 0.5)), "#333")


def stub(d, cx, cy, r, ang, count, col="#b8860b"):
    """从节点向外画一条挂键短线，并标挂键数"""
    x1 = cx + math.cos(ang) * (r + 6)
    y1 = cy + math.sin(ang) * (r + 6)
    x2 = cx + math.cos(ang) * (r + 34)
    y2 = cy + math.sin(ang) * (r + 34)
    d.line([(x1, y1), (x2, y2)], fill=col, width=3)
    text_center(d, x2 + math.cos(ang) * 12, y2 + math.sin(ang) * 12, str(count),
                font(FONT_B, 15), "#b8860b")


def par_lines(d, p1, p2, m, col, width=3, gap=7):
    ux, uy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(ux, uy)
    nx, ny = -uy / L, ux / L
    for k in range(m):
        off = (k - (m - 1) / 2) * gap
        d.line([(p1[0] + nx * off, p1[1] + ny * off), (p2[0] + nx * off, p2[1] + ny * off)],
               fill=col, width=width)


MODULES = [
    ("单原子", 1, [(0, 0)], [], [(0.9, 3), (2.4, 3), (4.2, 3)]),
    ("单键二聚体", 1, [(-52, 0), (52, 0)], [(0, 1, 1)], [(-1, 2), (-2.2, 2), (1, 2), (2.2, 2)]),
    ("双键二聚体", 1, [(-52, 0), (52, 0)], [(0, 1, 2)], [(-1.6, 1), (1.6, 1)]),
    ("三键二聚体", 1, [(-52, 0), (52, 0)], [(0, 1, 3)], []),
    ("三元链", 1, [(-92, 0), (0, 0), (92, 0)], [(0, 1, 1), (1, 2, 1)],
     [(-2.6, 2), (-0.5, 2), (-1.05, 1), (-0.5, 1), (2.6, 2), (3.2, 2)]),
    ("三元环·全单键", 1, [(-70, 40), (70, 40), (0, -60)], [(0, 1, 1), (0, 2, 1), (1, 2, 1)],
     [(2.4, 1), (0.7, 1), (4.0, 1)]),
    ("三元环·含一条双键", 1, [(-70, 40), (70, 40), (0, -60)], [(0, 1, 1), (0, 2, 2), (1, 2, 1)],
     [(2.6, 0), (1.3, 0), (4.0, 1)]),
]


def page_modules(path):
    ncol, pw, ph = 4, 430, 380
    nrow = (len(MODULES) + ncol - 1) // ncol
    W = 30 + ncol * pw + 20
    H = 150 + nrow * ph + 20
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 18), "三价元素骨架模块库（7 种模块，连通块最多 3 原子）", font=font(FONT_B, 27), fill="#111")
    d.text((30, 58), "只含一种三价元素时：三价原子间只形成同类键（O–O 短键S / P–P 角键C / K–K 长键L），"
                     "在反应最后一级（距离0）才成键。", font=font(FONT, 16), fill="#555")
    d.text((30, 86), "金色短线+数字 = 该原子剩余可用于连接下价元素的挂键数；实线/多条平行线 = 三价原子之间的键（数字为键数）。",
           font=font(FONT, 16), fill="#888")
    d.text((30, 114), "骨架 = 这些模块的不交并：孤立原子、二聚体(1/2/3键)、三元链、三元环(全单键/含双键)。",
           font=font(FONT, 16), fill="#b8860b")
    for i, (name, mult, nodes, edges, stubs) in enumerate(MODULES):
        r, c = divmod(i, ncol)
        x0 = 30 + c * pw + 4
        y0 = 150 + r * ph + 4
        w, h = pw - 8, ph - 8
        d.rectangle([x0, y0, x0 + w, y0 + h], outline="#e0e0e0")
        d.text((x0 + 10, y0 + 8), f"{i+1:02d}  {name}", font=font(FONT_B, 20), fill="#111")
        cx, cy = x0 + w / 2, y0 + h / 2 + 10
        rn = 34
        pts = [(cx + x, cy + y) for (x, y) in nodes]
        # 边
        for (a, b, m) in edges:
            par_lines(d, pts[a], pts[b], m, "#c0392b", 3, 7)
        # 节点
        for k, (px, py) in enumerate(pts):
            node(d, px, py, rn, TRI_FILL["O"], "O", CN["O"])
        # 挂键
        for (ang, cnt) in stubs:
            # 选离该节点最近的节点索引
            idx = min(range(len(pts)), key=lambda k: (pts[k][0] - (cx + math.cos(ang) * 0)) ** 2 +
                                                     (pts[k][1] - (cy + math.sin(ang) * 0)) ** 2)
            if len(pts) == 1:
                idx = 0
            px, py = pts[idx]
            # 简化：对每个节点按角度画（角度是相对该节点中心）
            dline_from(d, px, py, rn, ang, cnt)
        # 公式示例（该模块在 O 体系中的例）
        ex = {0: "OAF", 1: "O2A2", 2: "O2A", 3: "O2", 4: "O3A2F", 5: "O3AF", 6: "O3C"}[i]
        draw_formula(d, x0 + w / 2, y0 + h - 22, "例：" + ex, 17, "#555")
    img.save(path)
    print("saved", path)


def dline_from(d, px, py, r, ang, cnt):
    x1 = px + math.cos(ang) * (r + 6)
    y1 = py + math.sin(ang) * (r + 6)
    x2 = px + math.cos(ang) * (r + 36)
    y2 = py + math.sin(ang) * (r + 36)
    d.line([(x1, y1), (x2, y2)], fill="#b8860b", width=3)
    text_center(d, x2 + math.cos(ang) * 12, y2 + math.sin(ang) * 12, str(cnt), font(FONT_B, 15), "#b8860b")


def draw_substance(d, rec, tri, box):
    x0, y0, w, h = box
    atoms = rec["atoms"]
    edges = [tuple(e) for e in rec["edges"]]
    place = {int(k): tuple(v) for k, v in rec["place"].items()}
    n = len(atoms)
    s = 30.0
    for _ in range(50):
        pts = [R.center_of(place[i], s) for i in range(n)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if (max(xs) - min(xs) + 2.6 * s) <= w and (max(ys) - min(ys) + 2.6 * s) <= h:
            break
        s *= 0.93
    pts = [R.center_of(place[i], s) for i in range(n)]
    ox = x0 + w / 2 - (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    oy = y0 + h / 2 - (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    pos = [(p[0] + ox, p[1] + oy) for p in pts]
    polys = [R.hex_pts(pos[i][0], pos[i][1], s) for i in range(n)]
    # 中间空格
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        if R.rel_type(dd) == "L":
            mid = ((place[i][0] + place[j][0]) // 2, (place[i][1] + place[j][1]) // 2)
            if mid not in place.values():
                cp = R.center_of(mid, s)
                poly = R.hex_pts(cp[0] + ox, cp[1] + oy, s)
                d.polygon(poly, fill="#f5f5f5")
                R.dotted_poly(d, poly, "#bbbbbb", 2)
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = R.rel_type(dd)
        col = BONDC.get(t, "#333")
        width = max(2, int(s / 13)) if t in ("S", "C") else max(2, int(s / 16))
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
                    off = (k - (m - 1) / 2) * 6
                    a = (p1[0] + nx * off, p1[1] + ny * off)
                    b = (p2[0] + nx * off, p2[1] + ny * off)
                    R.dashed(d, a, b, col, width)
    for i, e in enumerate(atoms):
        is_skel = (e == tri)
        fill = TRI_FILL[tri] if is_skel else DEC_FILL
        d.polygon(polys[i], fill=fill, outline="#333", width=max(1, int(s / 22)))
        text_center(d, pos[i][0], pos[i][1] - s * 0.14, e, font(FONT_B, int(s * 0.54)), "#111")
        text_center(d, pos[i][0], pos[i][1] + s * 0.34, CN[e], font(FONT, int(s * 0.34)),
                    "#111" if not is_skel else "#0b3d0b")


def page_examples(path, examples, tri):
    ncol, pw, ph = 3, 420, 360
    nrow = (len(examples) + ncol - 1) // ncol
    W = 30 + ncol * pw + 20
    H = 130 + nrow * ph + 20
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 16), f"骨架实例（{tri} 为三价元素）：彩色=骨架三价原子，灰色=装饰用的下价元素",
           font=font(FONT_B, 24), fill="#111")
    d.text((30, 50), "骨架 = 彩色原子之间的键；同一物质里，骨架由若干 ≤3 原子的模块不交并组成。"
                     "红=短键S，绿=角键C，紫虚线=长键L。", font=font(FONT, 15), fill="#555")
    for i, rec in enumerate(examples):
        r, c = divmod(i, ncol)
        x0 = 30 + c * pw + 4
        y0 = 130 + r * ph + 4
        w, h = pw - 8, ph - 8
        d.rectangle([x0, y0, x0 + w, y0 + h], outline="#e0e0e0")
        d.text((x0 + 8, y0 + 6), rec["formula"], font=font(FONT_B, 16), fill="#999")
        draw_substance(d, rec, tri, (x0 + 4, y0 + 20, w - 8, h - 46))
        draw_formula(d, x0 + w / 2, y0 + h - 18, rec["formula"], 20, "#111")
    img.save(path)
    print("saved", path)


if __name__ == "__main__":
    data = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
    page_modules(BASE + r"\t10_modules.png")
    ex = ["O2", "O2A", "O2A2", "O3C", "O3AF", "O3A2F", "O4X2A2", "O5X2A2F", "O7X3A4F"]
    idx = {r["formula"]: r for r in data["O"]}
    picks = [idx[f] for f in ex if f in idx]
    page_examples(BASE + r"\t10_examples_O.png", picks, "O")
    # P 版同理
    idxp = {r["formula"]: r for r in data["P"]}
    exP = ["P2", "P2A", "P2A2", "CP3", "CP3A", "CP3A2", "P4W2A2", "CP5W2A2", "CP7W3A4"]
    picksP = [idxp[f] for f in exP if f in idxp]
    page_examples(BASE + r"\t10_examples_P.png", picksP, "P")
