# -*- coding: utf-8 -*-
"""把分子形状渲染成示意图（Pillow）"""
import math
import sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import hexmodel as H

S3 = math.sqrt(3)
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT = "C:/Windows/Fonts/msyh.ttc"

ELEM_FILL = {
    "O": "#34558b", "X": "#5b8fc9", "C": "#c9e2f5",
    "P": "#a0522d", "W": "#d9945b", "L": "#f6e0c8",
    "K": "#5b3a8e", "A": "#9b7fc7", "F": "#e3d6f2",
}
BOND_COLOR = {"short": "#c0392b", "corner": "#1e8449", "long": "#6c3483"}
BOND_NAME = {"short": "短键", "corner": "角键", "long": "长键"}


def font(path, size):
    return ImageFont.truetype(path, size)


def text_center(draw, cx, cy, text, fnt, fill):
    bb = draw.textbbox((0, 0), text, font=fnt)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - w / 2 - bb[0], cy - h / 2 - bb[1]), text, font=fnt, fill=fill)


def hex_center_px(q, r, s):
    return (1.5 * s * q, S3 * s * (r + q / 2.0))


def hex_pts(cx, cy, s):
    return [(cx + s * math.cos(math.radians(60 * k)),
             cy + s * math.sin(math.radians(60 * k))) for k in range(6)]


def poly_center(pts):
    return (sum(p[0] for p in pts) / 6.0, sum(p[1] for p in pts) / 6.0)


def ray_exit(poly, c, other):
    dx, dy = other[0] - c[0], other[1] - c[1]
    best = None
    for i in range(6):
        a, b = poly[i], poly[(i + 1) % 6]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = dx * ey - dy * ex
        if abs(den) < 1e-9:
            continue
        acx, acy = a[0] - c[0], a[1] - c[1]
        t = (acx * ey - acy * ex) / den
        u = (acx * dy - acy * dx) / den
        if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9:
            if best is None or t < best:
                best = t
    if best is None:
        return None
    return (c[0] + dx * best, c[1] + dy * best)


def shared_vertices(p1, p2, tol=1e-6):
    out = []
    for a in p1:
        for b in p2:
            if abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol:
                out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    return out


def dashed(draw, p1, p2, fill, width, dash=9, gap=7):
    x1, y1 = p1
    x2, y2 = p2
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-6:
        return
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    t = 0.0
    while t < L:
        e = min(t + dash, L)
        draw.line([(x1 + ux * t, y1 + uy * t), (x1 + ux * e, y1 + uy * e)],
                  fill=fill, width=width)
        t = e + gap


def dotted_poly(draw, pts, fill, width=2, dash=5, gap=5):
    for i in range(len(pts)):
        dashed(draw, pts[i], pts[(i + 1) % len(pts)], fill, width, dash, gap)


def draw_mol(draw, cells_hex, cat, box, s_cap=33.0, show_labels=True):
    """在 box=(x,y,w,h) 中画一个分子。"""
    x0, y0, w, h = box
    mid = []
    pairs = H.hex_bonds(cells_hex, cat)
    if cat == "san":
        for p, q, _ in pairs:
            m = ((p[0] + q[0]) // 2, (p[1] + q[1]) // 2)
            if m not in mid:
                mid.append(m)
    all_cells = list(cells_hex) + mid

    # 先按 s=40 估尺寸，再缩放
    def extent(s):
        pts = [hex_center_px(q, r, s) for (q, r) in all_cells]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), max(xs), min(ys), max(ys)

    s = s_cap
    for _ in range(24):
        xmin, xmax, ymin, ymax = extent(s)
        bw, bh = (xmax - xmin) + 2.3 * s, (ymax - ymin) + 2.3 * s
        if bw <= w and bh <= h:
            break
        s *= 0.94
    xmin, xmax, ymin, ymax = extent(s)
    ox = x0 + w / 2 - (xmin + xmax) / 2
    oy = y0 + h / 2 - (ymin + ymax) / 2
    pos = {c: (hex_center_px(c[0], c[1], s)[0] + ox,
               hex_center_px(c[0], c[1], s)[1] + oy) for c in all_cells}
    polys = {c: hex_pts(*pos[c], s) for c in all_cells}

    # 背景格子网格（淡）
    qs = [c[0] for c in all_cells]
    rs = [c[1] for c in all_cells]
    bg = []
    for q in range(min(qs) - 2, max(qs) + 3):
        for r in range(min(rs) - 2, max(rs) + 3):
            c = (q, r)
            if c in pos:
                continue
            p = (hex_center_px(q, r, s)[0] + ox, hex_center_px(q, r, s)[1] + oy)
            if x0 - s < p[0] < x0 + w + s and y0 - s < p[1] < y0 + h + s:
                pts = hex_pts(p[0], p[1], s)
                draw.polygon(pts, outline="#ececec", fill=None)

    # 空格（长键中间格）
    for c in mid:
        draw.polygon(polys[c], fill="#f7f7f7", outline=None)
        dotted_poly(draw, polys[c], "#9b9b9b", 2)
        if s > 20:
            text_center(draw, *poly_center(polys[c]), "空", font(FONT, int(s * 0.42)), "#9b9b9b")

    # 元素格
    degs = {c: 0 for c in cells_hex}
    for p, q, _ in pairs:
        degs[p] += 1
        degs[q] += 1
    for c in cells_hex:
        sym = H.VAL2SYM[cat][degs[c]]
        ch, _, val = H.ELEMS[sym]
        fill = ELEM_FILL[sym]
        draw.polygon(polys[c], fill=fill, outline="#333333", width=max(1, int(s / 16)))
        if show_labels and s > 16:
            dark = sym in ("O", "X", "P", "K", "A") and sym not in ("X", "A")
            tc = "white" if sym in ("O", "P", "K") else "#1a1a1a"
            text_center(draw, pos[c][0], pos[c][1] - s * 0.18, sym,
                        font(FONT_BOLD, int(s * 0.62)), tc)
            text_center(draw, pos[c][0], pos[c][1] + s * 0.36, ch,
                        font(FONT, int(s * 0.40)), tc)

    # 键
    for p, q, kind in pairs:
        col = BOND_COLOR[kind]
        if kind == "short":
            sv = shared_vertices(polys[p], polys[q])
            if len(sv) >= 2:
                draw.line([sv[0], sv[1]], fill=col, width=max(5, int(s / 6.5)))
        else:
            e1 = ray_exit(polys[p], pos[p], pos[q])
            e2 = ray_exit(polys[q], pos[q], pos[p])
            if e1 and e2:
                if kind == "corner":
                    draw.line([e1, e2], fill=col, width=max(3, int(s / 11)))
                else:
                    dashed(draw, e1, e2, col, max(3, int(s / 11)), dash=int(s * 0.32), gap=int(s * 0.22))
    return s


def panel(img, draw, box, cells_hex, cat, header=None, cap1=None, cap2=None,
          border="#ffffff", s_cap=33.0, header_color="#333333"):
    x0, y0, w, h = box
    if border:
        draw.rectangle([x0, y0, x0 + w, y0 + h], outline=border, width=2)
    top = y0
    if header:
        text_center(draw, x0 + w / 2, y0 + 20, header, font(FONT_BOLD, 21), header_color)
        top = y0 + 40
    draw_mol(draw, cells_hex, cat, (x0 + 6, top + 4, w - 12, h - (top - y0) - 62), s_cap=s_cap)
    if cap1:
        text_center(draw, x0 + w / 2, y0 + h - 44, cap1, font(FONT_BOLD, 25), "#111111")
    if cap2:
        text_center(draw, x0 + w / 2, y0 + h - 18, cap2, font(FONT, 18), "#777777")


# ---------------------------------------------------------------- 图1：三种键的几何
def fig_bond_geometry(path):
    W, Hh = 1560, 620
    img = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(img)
    d.text((28, 18), "三种键 = 三种相对位置；每个元素在这套格子上都有 6+6+6 = 18 个成键位置",
           font=font(FONT_BOLD, 27), fill="#111111")

    specs = [
        ("ju", "① 短键：两格共边（聚素之间）", "6 个“贴边”邻居"),
        ("dong", "② 角键：角对角，中间正好隔一条格边（动素之间）", "6 个“斜角”邻居"),
        ("san", "③ 长键：中间正好隔一个空格（散素之间）", "6 个“隔一格”邻居"),
    ]
    pw = (W - 40) / 3
    for i, (cat, title, sub) in enumerate(specs):
        x0 = 20 + i * pw
        y0 = 70
        d.rectangle([x0 + 6, y0, x0 + pw - 12, Hh - 70], outline="#dddddd", width=2)
        text_center(d, x0 + pw / 2, y0 + 28, title, font(FONT_BOLD, 21), "#111111")
        text_center(d, x0 + pw / 2, y0 + 58, sub, font(FONT, 18), "#777777")

        center = (0, 0)
        partner = H.CATS[cat]["off"] if cat != "ju" else H.T_NBRS
        cells = [center] + [H.add(center, o) for o in partner]

        # 用 draw_mol 的定位逻辑，但自己画（中心/伙伴不标元素）
        s = 46 if cat == "ju" else 40
        allc = list(cells)
        mid = []
        if cat == "san":
            for o in partner:
                mid.append(((o[0]) // 2, (o[1]) // 2))
            allc += [m for m in mid if m not in allc]
        pts0 = [hex_center_px(q, r, s) for (q, r) in allc]
        xs = [p[0] for p in pts0]
        ys = [p[1] for p in pts0]
        bw = max(xs) - min(xs) + 2.3 * s
        bh = max(ys) - min(ys) + 2.3 * s
        boxw, boxh = pw - 60, Hh - 70 - y0 - 90
        s2 = s * min(1.0, boxw / bw, boxh / bh)
        pts0 = [hex_center_px(q, r, s2) for (q, r) in allc]
        xs = [p[0] for p in pts0]
        ys = [p[1] for p in pts0]
        cx = x0 + pw / 2 - (min(xs) + max(xs)) / 2
        cy = y0 + 90 + boxh / 2 - (min(ys) + max(ys)) / 2
        pos = {c: (hex_center_px(c[0], c[1], s2)[0] + cx, hex_center_px(c[0], c[1], s2)[1] + cy) for c in allc}
        polys = {c: hex_pts(*pos[c], s2) for c in allc}

        # 背景格
        for q in range(-4, 5):
            for r in range(-4, 5):
                c = (q, r)
                if c in pos:
                    continue
                p = (hex_center_px(q, r, s2)[0] + cx, hex_center_px(q, r, s2)[1] + cy)
                if x0 < p[0] < x0 + pw and y0 < p[1] < Hh - 60:
                    d.polygon(hex_pts(p[0], p[1], s2), outline="#eeeeee")

        if cat == "san":
            for c in mid:
                d.polygon(polys[c], fill="#f7f7f7")
                dotted_poly(d, polys[c], "#aaaaaa", 2)
                text_center(d, *poly_center(polys[c]), "空", font(FONT, int(s2 * 0.40)), "#9b9b9b")

        # 中心 / 伙伴
        d.polygon(polys[(0, 0)], fill="#333333", outline="#000000", width=2)
        text_center(d, pos[(0, 0)][0], pos[(0, 0)][1] - s2 * 0.16, "元素", font(FONT_BOLD, int(s2 * 0.46)), "white")
        text_center(d, pos[(0, 0)][0], pos[(0, 0)][1] + s2 * 0.34, "本格", font(FONT, int(s2 * 0.36)), "#dddddd")
        for o in partner:
            c = H.add((0, 0), o)
            d.polygon(polys[c], fill="#e8e8e8", outline="#bbbbbb", width=1)

        # 键
        col = BOND_COLOR[{"ju": "short", "dong": "corner", "san": "long"}[cat]]
        for o in partner:
            c = H.add((0, 0), o)
            if cat == "ju":
                sv = shared_vertices(polys[(0, 0)], polys[c])
                if len(sv) >= 2:
                    d.line([sv[0], sv[1]], fill=col, width=max(5, int(s2 / 6.5)))
            else:
                e1 = ray_exit(polys[(0, 0)], pos[(0, 0)], pos[c])
                e2 = ray_exit(polys[c], pos[c], pos[(0, 0)])
                if e1 and e2:
                    if cat == "dong":
                        d.line([e1, e2], fill=col, width=max(3, int(s2 / 10)))
                        # 标出"正好一条格边"：两角之间的那条边
                        mx, my = (e1[0] + e2[0]) / 2, (e1[1] + e2[1]) / 2
                        d.ellipse([mx - 3, my - 3, mx + 3, my + 3], fill="#1e8449")
                    else:
                        dashed(d, e1, e2, col, max(3, int(s2 / 10)), int(s2 * 0.3), int(s2 * 0.2))

    d.text((28, Hh - 46), "注：短键/角键/长键分别只用于同一大类内部；右两类分子只能落在各自的“子格”上（角键 3 套、长键 4 套）。",
           font=font(FONT, 20), fill="#555555")
    img.save(path)
    print("saved", path)


# ---------------------------------------------------------------- 图2：三类 × 5 个分子
EXAMPLES = [
    ("哑铃", "价数 1·1", ((0, 0), (0, 1))),
    ("三角", "价数 2·2·2", ((0, 0), (0, 1), (1, 0))),
    ("三角+尾", "价数 3·2·2·1", ((0, 0), (0, 1), (0, 2), (1, 0))),
    ("三叉星", "价数 3·1·1·1", ((0, 1), (1, 1), (1, 2), (2, 0))),
    ("六元环", "价数 2×6", ((0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1))),
]

CAT_LABEL = {"ju": ("聚素", "短键"), "dong": ("动素", "角键"), "san": ("散素", "长键")}
CAT_COLOR = {"ju": "#34558b", "dong": "#a0522d", "san": "#5b3a8e"}


def cnf(sym_formula):
    """把 X2 之类转成下标"""
    return H.pretty(sym_formula)


def fig_molecules(path):
    ncol, nrow = len(EXAMPLES), 3
    pw, ph = 312, 334
    left, top = 148, 178
    W = left + ncol * pw + 26
    Hh = top + nrow * ph + 26
    img = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(img)

    d.text((24, 14), "同一套几何形状 × 三大类 = 三种不同的单质／化合物",
           font=font(FONT_BOLD, 26), fill="#111111")
    d.text((24, 50), "列标题是形状与价数图案；每格下方为该类的符号式与中文式。全部例子已程序校验：每格度数 = 元素价数、无多余成键、整体连通。",
           font=font(FONT, 18), fill="#666666")
    legend = [("短键：红色粗边（共边）", "#c0392b"),
              ("角键：绿色细线（角对角）", "#1e8449"),
              ("长键：紫色虚线（中间隔一格）", "#6c3483")]
    lx = 24
    for txt, col in legend:
        d.ellipse([lx, 86, lx + 12, 98], fill=col)
        d.text((lx + 18, 82), txt, font=font(FONT, 18), fill="#444444")
        lx += 18 + d.textlength(txt, font=font(FONT, 18)) + 34
    d.text((24, 108), "虚线格 = 长键中间必须为空、不能放元素的格子。",
           font=font(FONT, 17), fill="#888888")

    # 列表头
    for j, (name, val, cells) in enumerate(EXAMPLES):
        x = left + j * pw
        text_center(d, x + pw / 2, 140, name, font(FONT_BOLD, 24), "#111111")
        text_center(d, x + pw / 2, 165, val, font(FONT, 18), "#777777")

    for i, cat in enumerate(["ju", "dong", "san"]):
        y = top + i * ph
        name, bond = CAT_LABEL[cat]
        text_center(d, left / 2, y + ph / 2 - 26, name, font(FONT_BOLD, 30), CAT_COLOR[cat])
        text_center(d, left / 2, y + ph / 2 + 12, bond, font(FONT, 21), CAT_COLOR[cat])
        for j, (nm, val, cells_uv) in enumerate(EXAMPLES):
            x = left + j * pw
            cells_hex = [H.EMBED[cat](u, v) for (u, v) in cells_uv]
            f = H.formula(cells_uv, cat)
            # 中文式：元素中文 + 个数
            sig = H.signature(cells_uv)
            zh_parts = []
            for deg, cnt in ((3, sig[2]), (2, sig[1]), (1, sig[0])):
                if cnt:
                    ch = H.ELEMS[H.VAL2SYM[cat][deg]][0]
                    zh_parts.append(ch + (str(cnt) if cnt > 1 else ""))
            panel(img, d, (x + 4, y + 4, pw - 8, ph - 8), cells_hex, cat,
                  cap1=cnf(f), cap2="".join(zh_parts), s_cap=30.0)
    img.save(path)
    print("saved", path)


if __name__ == "__main__":
    fig_bond_geometry(r"G:\AI work\deepseek\work1\alchemy\fig1_bond_geometry.png")
    fig_molecules(r"G:\AI work\deepseek\work1\alchemy\fig2_molecules.png")
