# -*- coding: utf-8 -*-
"""t8_render_forms.py：把 6 级结束的三价元素形态画成图（4 种元素池情况各一页）"""
import json
import math
import sys
from collections import Counter
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

S3 = math.sqrt(3)
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
CN = {"O": "秩", "P": "势", "K": "沌"}
BASE_FILL = {"O": (107, 191, 107), "P": (240, 130, 185), "K": (150, 110, 220)}
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}
BASE = r"G:\AI work\deepseek\work1\alchemy"

EDGE_OFF = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORNER_OFF = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG_OFF = {(2 * a, 2 * b) for (a, b) in EDGE_OFF}


def rel_type(dd):
    if dd in EDGE_OFF:
        return "S"
    if dd in CORNER_OFF:
        return "C"
    if dd in LONG_OFF:
        return "L"
    return None




def font(path, size):
    return ImageFont.truetype(path, size)


def lighten(rgb, f):
    return tuple(int(c + (255 - c) * f) for c in rgb)


def text_center(d, cx, cy, text, fnt, fill="#111111"):
    bb = d.textbbox((0, 0), text, font=fnt)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text((cx - w / 2 - bb[0], cy - h / 2 - bb[1]), text, font=fnt, fill=fill)


def draw_formula(d, cx, cy, text, size, fill="#111111", bold=True):
    f_main = font(FONT_B if bold else FONT, size)
    f_sub = font(FONT_B if bold else FONT, int(size * 0.62))
    segs, buf, cur = [], "", None
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
    x = cx - total / 2
    yb = cy + size * 0.34
    for (seg, t), w in zip(segs, widths):
        if t == "main":
            d.text((x, yb), seg, font=f_main, fill=fill, anchor="ls")
        else:
            d.text((x, yb + size * 0.16), seg, font=f_sub, fill=fill, anchor="ls")
        x += w


def hex_pts(cx, cy, s):
    return [(cx + s * math.cos(math.radians(60 * k)), cy + s * math.sin(math.radians(60 * k)))
            for k in range(6)]


def center_of(cell, s):
    q, r = cell
    return (1.5 * s * q, S3 * s * (r + q / 2.0))


def common_vertices(p1, p2, tol=1e-6):
    out = []
    for a in p1:
        for b in p2:
            if abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol:
                out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    return out


def nearest_vertices(p1, p2):
    best = None
    for a in p1:
        for b in p2:
            d = math.hypot(a[0] - b[0], a[1] - b[1])
            if best is None or d < best[0]:
                best = (d, a, b)
    return best[1], best[2]


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
    return (c[0] + dx * best, c[1] + dy * best) if best else None


def dashed(d, p1, p2, fill, width, dash=8, gap=6):
    x1, y1 = p1
    x2, y2 = p2
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-6:
        return
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    t = 0.0
    while t < L:
        e = min(t + dash, L)
        d.line([(x1 + ux * t, y1 + uy * t), (x1 + ux * e, y1 + uy * e)], fill=fill, width=width)
        t = e + gap


def dotted_poly(d, pts, fill, width=2):
    for i in range(len(pts)):
        dashed(d, pts[i], pts[(i + 1) % len(pts)], fill, width, 5, 5)


def ray_offset_line(d, p1, p2, fill, width, m):
    ux, uy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(ux, uy)
    if L < 1e-6:
        return
    nx, ny = -uy / L, ux / L
    gap = max(3.0, L * 0.0 + 6.0)
    for k in range(m):
        off = (k - (m - 1) / 2) * gap
        a = (p1[0] + nx * off, p1[1] + ny * off)
        b = (p2[0] + nx * off, p2[1] + ny * off)
        d.line([a, b], fill=fill, width=width)


def draw_form(d, form, box):
    x0, y0, w, h = box
    atoms = form["atoms"]
    edges = [tuple(e) for e in form["edges"]]
    rems = form["rems"]
    place = {int(k): tuple(v) for k, v in form["place"].items()}
    s = 34.0
    for _ in range(40):
        pts = [center_of(place[i], s) for i in range(len(atoms))]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bw, bh = max(xs) - min(xs) + 2.6 * s, max(ys) - min(ys) + 2.6 * s
        if bw <= w and bh <= h:
            break
        s *= 0.93
    pts = [center_of(place[i], s) for i in range(len(atoms))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ox = x0 + w / 2 - (min(xs) + max(xs)) / 2
    oy = y0 + h / 2 - (min(ys) + max(ys)) / 2
    pos = [(p[0] + ox, p[1] + oy) for p in pts]
    polys = [hex_pts(pos[i][0], pos[i][1], s) for i in range(len(atoms))]

    # 中间空格（L 键）
    mids = []
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = rel_type(dd)
        if t == "L":
            mid = ((place[i][0] + place[j][0]) // 2, (place[i][1] + place[j][1]) // 2)
            mids.append(mid)
    mid_polys = {}
    for mid in set(mids):
        if mid in place.values():
            continue
        cp = center_of(mid, s)
        cp = (cp[0] + ox, cp[1] + oy)
        poly = hex_pts(cp[0], cp[1], s)
        mid_polys[mid] = poly
        d.polygon(poly, fill="#f3f3f3")
        dotted_poly(d, poly, "#aaaaaa", 2)

    # 键
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = rel_type(dd)
        col = BONDC.get(t, "#333333")
        width = max(3, int(s / 12)) if t in ("S", "C") else max(2, int(s / 14))
        if t == "S":
            sv = common_vertices(polys[i], polys[j])
            if len(sv) >= 2:
                p1, p2 = sv[0], sv[1]
                ray_offset_line(d, p1, p2, col, width, m)
        elif t == "C":
            p1, p2 = nearest_vertices(polys[i], polys[j])
            ray_offset_line(d, p1, p2, col, width, m)
        elif t == "L":
            p1 = ray_exit(polys[i], pos[i], pos[j])
            p2 = ray_exit(polys[j], pos[j], pos[i])
            if p1 and p2:
                ux, uy = p2[0] - p1[0], p2[1] - p1[1]
                L = math.hypot(ux, uy)
                nx, ny = -uy / L, ux / L
                gap = 6.0
                for k in range(m):
                    off = (k - (m - 1) / 2) * gap
                    a = (p1[0] + nx * off, p1[1] + ny * off)
                    b = (p2[0] + nx * off, p2[1] + ny * off)
                    dashed(d, a, b, col, width)

    # 元素
    for i, e in enumerate(atoms):
        rgb = BASE_FILL[e]
        fill = rgb if rems[i] == 0 else lighten(rgb, 0.55)
        outline = "#333333"
        d.polygon(polys[i], fill=fill, outline=outline, width=max(1, int(s / 22)))
        if rems[i] > 0:
            d.polygon(polys[i], outline="#e8a000", width=max(3, int(s / 9)))
        text_center(d, pos[i][0], pos[i][1] - s * 0.16, e, font(FONT_B, int(s * 0.55)), "#111111")
        text_center(d, pos[i][0], pos[i][1] + s * 0.33, CN[e], font(FONT, int(s * 0.36)), "#111111")
        if rems[i] > 0:
            text_center(d, pos[i][0] + s * 0.62, pos[i][1] - s * 0.62, str(rems[i]),
                        font(FONT_B, int(s * 0.38)), "#b8860b")


def make_page(path, title, subtitle, forms, ncol=5, pw=310, ph=330):
    nrow = (len(forms) + ncol - 1) // ncol
    left, top = 26, 128
    W = left + ncol * pw + 22
    H = top + nrow * ph + 26
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 16), title, font=font(FONT_B, 28), fill="#111111")
    d.text((26, 56), subtitle, font=font(FONT, 17), fill="#555555")
    d.text((26, 84), "金色粗框+右上角数字=还剩的键（rem）；实心格=键已满(rem=0)；红=短键S、绿=角键C、紫虚线=长键L（虚线格为中间空格）。",
           font=font(FONT, 16), fill="#888888")
    for i, f in enumerate(forms):
        r, c = divmod(i, ncol)
        x0 = left + c * pw + 3
        y0 = top + r * ph + 3
        w, h = pw - 6, ph - 6
        d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dddddd", width=1)
        d.text((x0 + 8, y0 + 6), f"{i+1:02d}", font=font(FONT_B, 15), fill="#999999")
        text_center(d, x0 + w - 56, y0 + 14, f"{f['size']}原子/活跃{f['active']}",
                    font(FONT, 13), "#999999")
        draw_form(d, f, (x0 + 4, y0 + 22, w - 8, h - 74))
        draw_formula(d, x0 + w / 2, y0 + h - 52, f["formula"], 24, "#111111")
        remstr = ",".join(f"{k}×{v}" for k, v in sorted(f["rem_dist"].items()))
        text_center(d, x0 + w / 2, y0 + h - 22, "rem=" + remstr, font(FONT, 14), "#666666")
    img.save(path)
    print("saved", path)


def main():
    forms = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
    cases = [
        ("OP", "情况① 两种三价元素：秩O + 势P", "聚-动 之间：短键 S / 角键 C"),
        ("KO", "情况② 两种三价元素：秩O + 沌K", "聚-散 之间：短键 S / 长键 L"),
        ("KP", "情况③ 两种三价元素：势P + 沌K", "动-散 之间：角键 C / 长键 L"),
        ("KOP", "情况④ 三种三价元素：秩O + 势P + 沌K", "含三种元素的 14 种形态"),
    ]
    for types, title, sub in cases:
        sub_forms = [f for f in forms if f["types"] == types]
        # 按 size, formula 排序
        sub_forms.sort(key=lambda x: (x["size"], x["formula"]))
        make_page(BASE + rf"\t8_forms_{types}.png", title, sub, sub_forms)


if __name__ == "__main__":
    main()
