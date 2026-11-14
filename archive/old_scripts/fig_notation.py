# -*- coding: utf-8 -*-
"""按新记号画图：方向编号图 + 分子例子图"""
import math
import sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import notation as N
from figures import (ELEM_FILL, BOND_COLOR, hex_pts, ray_exit, shared_vertices,
                     dashed, dotted_poly, text_center, font, FONT, FONT_BOLD)

S3 = math.sqrt(3)


def xy_px(X, Y, s):
    """用户坐标 -> 屏幕像素（Y 向上为正，屏幕 Y 向下，所以取负）"""
    return (1.5 * s * X, -(S3 / 2.0) * s * Y)


# ---------------------------------------------------------------- 图3：方向编号图
def fig_directions(path):
    W, Hh = 1520, 900
    img = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 16), "键的方向编号：正上方 = 1，顺时针每 30° 加 1（共 12 个方向）",
           font=font(FONT_BOLD, 27), fill="#111111")
    d.text((26, 54), "短键 S 与长键 L 用奇数方向（1,3,5,7,9,11，都是“共边轴”）；角键 C 用偶数方向（2,4,6,8,10,12）。",
           font=font(FONT, 19), fill="#555555")

    # ---- 左panel：S 与 C
    s = 44
    cx, cy = 380, 480
    cells = {}
    for k, (dx, dy) in N.S_OFF.items():
        cells[(dx, dy)] = ("S", k)
    for k, (dx, dy) in N.C_OFF.items():
        cells[(dx, dy)] = ("C", k)
    pos = {c: (cx + xy_px(c[0], c[1], s)[0], cy + xy_px(c[0], c[1], s)[1]) for c in cells}
    pos[(0, 0)] = (cx, cy)
    polys = {c: hex_pts(*pos[c], s) for c in pos}

    # 背景格
    for X in range(-3, 4):
        for Y in range(-4, 5):
            if (X - Y) % 2 or (X, Y) in pos:
                continue
            p = (cx + xy_px(X, Y, s)[0], cy + xy_px(X, Y, s)[1])
            if 20 < p[0] < 700 and 90 < p[1] < 760:
                d.polygon(hex_pts(p[0], p[1], s), outline="#efefef")

    d.polygon(polys[(0, 0)], fill="#333333", outline="#000000", width=2)
    text_center(d, cx, cy, "本元素", font(FONT_BOLD, 20), "white")
    for c, (typ, k) in cells.items():
        fill = "#fde8e8" if typ == "S" else "#e6f4ea"
        d.polygon(polys[c], fill=fill, outline="#999999", width=1)
        col = BOND_COLOR["short"] if typ == "S" else BOND_COLOR["corner"]
        text_center(d, pos[c][0], pos[c][1], f"{typ}{k}", font(FONT_BOLD, 22), col)

    for k, (dx, dy) in N.S_OFF.items():
        c = (dx, dy)
        sv = shared_vertices(polys[(0, 0)], polys[c])
        if len(sv) >= 2:
            d.line([sv[0], sv[1]], fill=BOND_COLOR["short"], width=7)
    for k, (dx, dy) in N.C_OFF.items():
        c = (dx, dy)
        e1 = ray_exit(polys[(0, 0)], pos[(0, 0)], pos[c])
        e2 = ray_exit(polys[c], pos[c], pos[(0, 0)])
        d.line([e1, e2], fill=BOND_COLOR["corner"], width=5)

    text_center(d, 380, 130, "① 短键 S（奇数）与角键 C（偶数）——12 个方向各对应一个格子", font(FONT_BOLD, 22), "#111111")

    # ---- 右panel：L
    cx2, cy2 = 1130, 480
    middles = {}
    for k, (dx, dy) in N.L_OFF.items():
        middles[(dx // 2, dy // 2)] = k
    far = {N.L_OFF[k]: k for k in N.L_OFF}
    allp = [(0, 0)] + list(middles) + list(far)
    pos2 = {c: (cx2 + xy_px(c[0], c[1], s)[0], cy2 + xy_px(c[0], c[1], s)[1]) for c in allp}
    polys2 = {c: hex_pts(*pos2[c], s) for c in pos2}
    for X in range(-3, 4):
        for Y in range(-4, 5):
            if (X - Y) % 2 or (X, Y) in pos2:
                continue
            p = (cx2 + xy_px(X, Y, s)[0], cy2 + xy_px(X, Y, s)[1])
            if 800 < p[0] < 1500 and 90 < p[1] < 760:
                d.polygon(hex_pts(p[0], p[1], s), outline="#efefef")

    for c in middles:
        d.polygon(polys2[c], fill="#f7f7f7")
        dotted_poly(d, polys2[c], "#9b9b9b", 2)
    for c, k in far.items():
        d.polygon(polys2[c], fill="#f3eaf9", outline="#999999")
        text_center(d, pos2[c][0], pos2[c][1], f"L{k}", font(FONT_BOLD, 22), BOND_COLOR["long"])
    d.polygon(polys2[(0, 0)], fill="#333333", outline="#000000", width=2)
    text_center(d, cx2, cy2, "本元素", font(FONT_BOLD, 20), "white")
    for c, k in far.items():
        e1 = ray_exit(polys2[(0, 0)], pos2[(0, 0)], pos2[c])
        e2 = ray_exit(polys2[c], pos2[c], pos2[(0, 0)])
        dashed(d, e1, e2, BOND_COLOR["long"], 6, 12, 8)

    text_center(d, 1130, 130, "② 长键 L（奇数方向，距离是短键的 2 倍，中间那格必须为空）", font(FONT_BOLD, 22), "#111111")

    # ---- 表
    lines = []
    odd = [(k, N.S_OFF[k]) for k in (1, 3, 5, 7, 9, 11)]
    even = [(k, N.C_OFF[k]) for k in (2, 4, 6, 8, 10, 12)]
    lines.append("S / L 方向（奇数）： " + "   ".join(f"{k}:({dx:+d},{dy:+d})" for k, (dx, dy) in odd))
    lines.append("C 方向（偶数）：     " + "   ".join(f"{k}:({dx:+d},{dy:+d})" for k, (dx, dy) in even))
    lines.append("L 的偏移 = S 的 2 倍；例如 L1=(0,+4)、L3=(+2,+2)、L7=(0,-4)。相反方向：k 与 k±6 互为反向。")
    y = 790
    for ln in lines:
        d.text((40, y), ln, font=font(FONT, 19), fill="#333333")
        y += 32
    img.save(path)
    print("saved", path)


# ---------------------------------------------------------------- 图4：分子例子
def mol_entries(cells):
    """{(X,Y): (elem, [(t,k)...])} from notation-style entries"""
    out = {}
    for e in cells:
        elem, x, y, bonds = N.parse(e)
        out[(x, y)] = (elem, bonds)
    return out


def draw_formula(d, cx, cy, text, size, fill, bold=True, align="center"):
    """把 'O2X' / '秩2晶' 画成带下标的形式（PIL 一次画不了两种字号，手动画）。"""
    f_main = font(FONT_BOLD if bold else FONT, size)
    f_sub = font(FONT_BOLD if bold else FONT, int(size * 0.62))
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
    widths = [d.textlength(seg, font=(f_main if t == "main" else f_sub)) for seg, t in segs]
    total = sum(widths)
    x = cx if align == "left" else cx - total / 2
    base_main = cy + size * 0.34
    for (seg, t), w in zip(segs, widths):
        if t == "main":
            d.text((x, base_main), seg, font=f_main, fill=fill, anchor="ls")
        else:
            d.text((x, base_main + size * 0.16), seg, font=f_sub, fill=fill, anchor="ls")
        x += w


def draw_mol(draw, entries, box, s_cap=30.0):
    x0, y0, w, h = box
    cells = mol_entries(entries)
    # 收集长键中间格
    mids = set()
    for (x, y), (elem, bonds) in cells.items():
        for (t, k) in bonds:
            dx, dy = N.OFFS[t][k]
            if t == "L":
                mids.add((x + dx // 2, y + dy // 2))
    allc = list(cells) + [m for m in mids if m not in cells]

    def extent(s):
        ps = [xy_px(c[0], c[1], s) for c in allc]
        xs = [p[0] for p in ps]
        ys = [p[1] for p in ps]
        return min(xs), max(xs), min(ys), max(ys)

    s = s_cap
    for _ in range(30):
        xmin, xmax, ymin, ymax = extent(s)
        bw, bh = (xmax - xmin) + 2.4 * s, (ymax - ymin) + 2.4 * s
        if bw <= w and bh <= h:
            break
        s *= 0.94
    xmin, xmax, ymin, ymax = extent(s)
    pos = {c: (x0 + w / 2 - (xmin + xmax) / 2 + xy_px(c[0], c[1], s)[0],
               y0 + h / 2 - (ymin + ymax) / 2 + xy_px(c[0], c[1], s)[1]) for c in allc}
    polys = {c: hex_pts(*pos[c], s) for c in allc}

    # 背景格
    Xs = [c[0] for c in allc]
    Ys = [c[1] for c in allc]
    for X in range(min(Xs) - 2, max(Xs) + 3):
        for Y in range(min(Ys) - 2, max(Ys) + 3):
            if (X - Y) % 2 or (X, Y) in pos:
                continue
            p = pos.get((X, Y)) or (x0 + w / 2 - (xmin + xmax) / 2 + xy_px(X, Y, s)[0],
                                    y0 + h / 2 - (ymin + ymax) / 2 + xy_px(X, Y, s)[1])
            if x0 - s < p[0] < x0 + w + s and y0 - s < p[1] < y0 + h + s:
                draw.polygon(hex_pts(p[0], p[1], s), outline="#f0f0f0")

    for m in mids:
        if m in cells:
            continue
        draw.polygon(polys[m], fill="#f7f7f7")
        dotted_poly(draw, polys[m], "#9b9b9b", 1 if s < 18 else 2)

    # 元素填充
    for (x, y), (elem, bonds) in cells.items():
        draw.polygon(polys[(x, y)], fill=ELEM_FILL[elem], outline="#444444", width=max(1, int(s / 20)))

    # 键（带重数）：画在填充之后，双键/三键的平行线才看得见
    pairs = {}
    for (x, y), (elem, bonds) in cells.items():
        for (t, k) in bonds:
            dx, dy = N.OFFS[t][k]
            q = (x + dx, y + dy)
            if q in cells:
                key = (min((x, y), q), max((x, y), q), t)
                pairs[key] = pairs.get(key, 0) + 1

    for (p, q, t), m in pairs.items():
        if t == "S":
            sv = shared_vertices(polys[p], polys[q])
            p1, p2 = sv[0], sv[1]
        else:
            p1 = ray_exit(polys[p], pos[p], pos[q])
            p2 = ray_exit(polys[q], pos[q], pos[p])
        ux, uy = p2[0] - p1[0], p2[1] - p1[1]
        L = math.hypot(ux, uy)
        nx, ny = -uy / L, ux / L
        gap = max(4.0, s * 0.17)
        col = BOND_COLOR[{"S": "short", "C": "corner", "L": "long"}[t]]
        for i in range(m):
            off = (i - (m - 1) / 2) * gap
            a = (p1[0] + nx * off, p1[1] + ny * off)
            b = (p2[0] + nx * off, p2[1] + ny * off)
            if t == "L":
                dashed(draw, a, b, col, max(2, int(s / 12)), int(s * 0.3), int(s * 0.2))
            else:
                draw.line([a, b], fill=col, width=max(2, int(s / (15 if t == "S" else 16))))

    # 元素文字
    for (x, y), (elem, bonds) in cells.items():
        tc = "white" if elem in ("O", "P", "K") else "#1a1a1a"
        text_center(draw, pos[(x, y)][0], pos[(x, y)][1] - s * 0.18, elem,
                    font(FONT_BOLD, int(s * 0.60)), tc)
        text_center(draw, pos[(x, y)][0], pos[(x, y)][1] + s * 0.34, N.CN[elem],
                    font(FONT, int(s * 0.40)), tc)
    return s


def fig_examples(path):
    names = [
        ("秩2 · O2", "三重键", [("O", 0, 0, ["S1", "S1", "S1"]), ("O", 0, 2, ["S7", "S7", "S7"])]),
        ("秩2晶 · O2X", "双键 + 两根单键", [("O", 0, 0, ["S1", "S1", "S3"]), ("O", 0, 2, ["S7", "S7", "S5"]), ("X", 1, 1, ["S9", "S11"])]),
        ("冰2晶 · C2X", "晶为 2 价", [("C", 0, 0, ["S3"]), ("X", 1, 1, ["S5", "S9"]), ("C", 2, 0, ["S11"])]),
        ("秩冰3 · OC3", "秩为 3 价", [("C", 0, 0, ["S3"]), ("O", 1, 1, ["S1", "S5", "S9"]), ("C", 1, 3, ["S7"]), ("C", 2, 0, ["S11"])]),
        ("电2 · L2", "角键单键", [("L", 0, 0, ["C2"]), ("L", 1, 3, ["C8"])]),
        ("流3 · W3", "角键三角", [("W", 0, 0, ["C2", "C4"]), ("W", 2, 0, ["C10", "C12"]), ("W", 1, 3, ["C6", "C8"])]),
        ("势电3 · PL3", "1 个 3 价 + 3 个 1 价", [("L", 0, 0, ["C2"]), ("L", 0, 6, ["C6"]), ("P", 1, 3, ["C4", "C8", "C12"]), ("L", 3, 3, ["C10"])]),
        ("焰2 · F2", "长键单键", [("F", 0, 0, ["L1"]), ("F", 0, 4, ["L7"])]),
        ("气3 · A3", "长键三角", [("A", 0, 0, ["L1", "L3"]), ("A", 0, 4, ["L5", "L7"]), ("A", 2, 2, ["L9", "L11"])]),
        ("沌气2焰 · KA2F", "1 个 3 价 + 2 个 2 价 + 1 个 1 价", [("F", 0, 0, ["L3"]), ("K", 2, 2, ["L1", "L3", "L9"]), ("A", 2, 6, ["L5", "L7"]), ("A", 4, 4, ["L9", "L11"])]),
    ]
    ncol, nrow = 5, 2
    pw, ph = 306, 330
    left, top = 30, 122
    W = left + ncol * pw + 20
    Hh = top + nrow * ph + 40
    img = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 14), "几个成立的分子式（每个元素后面的键数 = 它的价数，键的两端互相承认）",
           font=font(FONT_BOLD, 26), fill="#111111")
    d.text((26, 50), "红色粗线 = 短键 S（聚素）；绿色线 = 角键 C（动素）；紫色虚线 = 长键 L（散素，虚线格必须为空）。同一对元素之间可以画 1~3 根平行键。",
           font=font(FONT, 17), fill="#666666")
    cat_of = {"聚": "#34558b", "动": "#a0522d", "散": "#5b3a8e"}
    for i, (name, note, entries) in enumerate(names):
        r, c = divmod(i, ncol)
        x = left + c * pw
        y = top + r * ph
        d.rectangle([x + 2, y + 2, x + pw - 2, y + ph - 2], outline="#e5e5e5", width=1)
        draw_formula(d, x + 10, y + 12, name, 21, "#111111", align="left")
        d.text((x + 10, y + 34), note, font=font(FONT, 16), fill="#888888")
        draw_mol(d, entries, (x + 4, y + 52, pw - 8, ph - 100), s_cap=29.0)
        f = build_formula(entries)
        draw_formula(d, x + pw / 2, y + ph - 62, f[0], 26, "#111111")
        draw_formula(d, x + pw / 2, y + ph - 28, f[1], 18, "#777777", bold=False)
    img.save(path)
    print("saved", path)


def build_formula(entries):
    from collections import Counter
    cnt = Counter()
    for e in entries:
        cnt[e[0]] += 1
    order = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
    sym = "".join(s + (str(cnt[s]) if cnt[s] > 1 else "") for s in order if cnt[s])
    zh = "".join(N.CN[s] + (str(cnt[s]) if cnt[s] > 1 else "") for s in order if cnt[s])
    sub = str.maketrans("0123456789", "0123456789")
    return sym.translate(sub), zh


if __name__ == "__main__":
    fig_directions(r"G:\AI work\deepseek\work1\alchemy\fig3_directions.png")
    fig_examples(r"G:\AI work\deepseek\work1\alchemy\fig4_examples.png")
