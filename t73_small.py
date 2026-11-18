# -*- coding: utf-8 -*-
"""T73 小分子“物质化”画法：把元素字形 + 键带并成一个连续的小身体，
再按键型/元素加表面纹理与端帽，让它看起来像一块真实的小物质而不是图符。"""
import json
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import pot_all as P
import t68_shapes as S
import t70b_body as B

SS = B.SS
TAU = math.pi * 2
INK = (40, 52, 66)

EL_COL = S.ELEMCOL
GL = {"O": "三角", "P": "圆", "K": "多角", "X": "尖六边", "W": "圆角六边", "A": "虚六边",
      "C": "菱形", "L": "圆点", "F": "小三角"}
GLYPH = {"O": "triangle", "P": "circle", "K": "poly", "X": "hex", "W": "chamfer",
         "A": "dashhex", "C": "diamond", "L": "dot", "F": "ftri"}


def _place_list(place):
    if isinstance(place, dict):
        return [tuple(place[str(i)]) for i in range(len(place))]
    return [tuple(p) for p in place]


def _fit(place, box, max_s):
    x0, y0, w, h = box
    qs = [p[0] for p in place]
    rs = [p[1] for p in place]
    cw = (max(qs) - min(qs)) * 1.5 + 2.4
    chh = (max(rs) - min(rs)) * math.sqrt(3) + (max(qs) - min(qs)) * 0.5 + 2.4
    s = min(w / max(1e-6, cw), h / max(1e-6, chh), max_s)
    mq = (min(qs) + max(qs)) / 2.0
    mr = (min(rs) + max(rs)) / 2.0
    pos = [S.center_of((q - mq, r - mr), s) for (q, r) in place]
    ox = x0 + w / 2.0
    oy = y0 + h / 2.0
    return s, [(ox + x, oy + y) for (x, y) in pos]


def _bond_type(place, a, b):
    dq = place[b][0] - place[a][0]
    dr = place[b][1] - place[a][1]
    return P.classify_offset((dq, dr)) or "C"


def _draw_texture(cv, atoms, edges, place, pos, s, mask):
    """表面纹理：S 短键刻横纹、C 角键画关节环、L 长键画虚线；X 画晶面线。"""
    d = cv.d
    for (a, b, m) in edges:
        pa, pb = pos[a], pos[b]
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1.0
        u = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
        n = (-u[1], u[0])
        t = _bond_type(place, a, b)
        if t == "S":
            k = int(max(2, L / (0.42 * s)))
            for i in range(1, k):
                tt = i / float(k)
                px = pa[0] + u[0] * L * tt
                py = pa[1] + u[1] * L * tt
                hw = 0.26 * s
                d.line([(px + n[0] * hw, py + n[1] * hw), (px - n[0] * hw, py - n[1] * hw)],
                       fill=(150, 164, 180), width=2)
        elif t == "C":
            r = 0.20 * s
            mx, my = (pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0
            d.ellipse([mx - r, my - r, mx + r, my + r], outline=(140, 156, 172), width=2)
        else:
            k = int(max(2, L / (0.5 * s)))
            for i in range(1, k):
                if i % 2:
                    continue
                tt = i / float(k)
                px = pa[0] + u[0] * L * tt
                py = pa[1] + u[1] * L * tt
                hw = 0.20 * s
                d.line([(px + n[0] * hw, py + n[1] * hw), (px - n[0] * hw, py - n[1] * hw)],
                       fill=(168, 150, 196), width=2)
    # X 晶面线
    for i, el in enumerate(atoms):
        if el != "X":
            continue
        cx, cy = pos[i]
        r = 0.34 * s
        for a in (0.2, 1.25, 2.4):
            d.line([(cx + math.cos(a) * r, cy + math.sin(a) * r),
                    (cx + math.cos(a + 2.2) * r, cy + math.sin(a + 2.2) * r)],
                   fill=(176, 168, 150), width=2)


def _draw_terminals(cv, atoms, place, pos, s):
    """一价原子的端帽：C 冰锥 / L 螺旋丝 / F 飘带。"""
    for i, el in enumerate(atoms):
        if el not in ("C", "L", "F"):
            continue
        cx, cy = pos[i]
        # 朝外方向：远离质心
        mx = sum(p[0] for p in pos) / len(pos)
        my = sum(p[1] for p in pos) / len(pos)
        dx, dy = cx - mx, cy - my
        L = math.hypot(dx, dy) or 1.0
        u = (dx / L, dy / L)
        base = (cx + u[0] * 0.30 * s, cy + u[1] * 0.30 * s)
        sz = 0.62 * s
        if el == "C":
            B._mask_spike(cv.d, base, u, sz * 2.0, sz * 0.34)
        elif el == "F":
            B._mask_ribbon(cv.d, base, u, sz * 2.0, sz * 0.50, 2)
        else:
            # 电 L：粗一点的螺旋丝蒙版（细线会被闭运算抹掉）
            spine = []
            n = 60
            for i in range(n + 1):
                t = i / float(n)
                px = base[0] + u[0] * sz * 2.2 * t
                py = base[1] + u[1] * sz * 2.2 * t
                off = sz * 0.26 * math.sin(math.pi * t) * math.sin(TAU * 1.5 * t)
                spine.append((px - u[1] * off, py + u[0] * off))
            cv.d.line([(x * SS, y * SS) for (x, y) in spine], fill=255,
                      width=max(4, int(0.16 * sz * SS)), joint="curve")


def draw_substance(cv, box, atoms, edges, place, max_s=74, label=False):
    """把小分子画成一块连续的物质。"""
    place = _place_list(place)
    s, pos = _fit(place, box, max_s)
    W, H = cv.img.size

    # ---- 蒙版：元素字形 + 键带 + 端帽
    mask = Image.new("L", (W * SS, H * SS), 0)
    dm = ImageDraw.Draw(mask)
    for (a, b, m) in edges:
        B._mask_thick(dm, pos[a], pos[b], 0.26 * s)
    for i, el in enumerate(atoms):
        poly = S.atom_poly(el, pos[i][0], pos[i][1], 0.74 * s, 1)
        B._mask_poly(dm, poly)
    # 端帽并入蒙版（画到同一张蒙版上）
    _draw_terminals(_MaskCanvas(cv, mask), atoms, place, pos, s)

    # ---- 轻微闭运算：让字形与键带融成一块，但保留轮廓个性
    f = 4
    k = max(5, int(0.16 * s))
    sb = mask.resize((max(8, W * SS // f), max(8, H * SS // f)), Image.LANCZOS)
    sb = sb.filter(ImageFilter.GaussianBlur(max(0.8, k * 0.45 / f)))
    sb = sb.point(lambda v: 255 if v > 96 else 0)
    big = sb.resize((W * SS, H * SS), Image.LANCZOS).point(lambda v: 255 if v > 128 else 0)
    full = big.resize((W, H), Image.LANCZOS)
    solid = full.point(lambda v: 255 if v > 128 else 0)

    # ---- 阴影 + 渐变身体
    sh = big.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(9))
    cv.img.paste(Image.new("RGB", (W, H), (150, 162, 176)), (0, 0),
                 sh.resize((W, H), Image.LANCZOS).point(lambda v: int(v * 0.33)))
    grad = Image.new("RGB", (1, H))
    gd = ImageDraw.Draw(grad)
    for yy in range(H):
        t = yy / float(max(1, H - 1))
        gd.point((0, yy), fill=(int(250 - 26 * t), int(252 - 22 * t), int(254 - 16 * t)))
    cv.img.paste(grad.resize((W, H)), (0, 0), solid)

    # ---- 元素色淡染
    for i, el in enumerate(atoms):
        poly = S.atom_poly(el, pos[i][0], pos[i][1], 0.62 * s, 1)
        im = Image.new("L", (W * SS, H * SS), 0)
        B._mask_poly(ImageDraw.Draw(im), poly)
        ims = im.resize((W, H), Image.LANCZOS).point(lambda v: 255 if v > 90 else 0)
        cv.img.paste(Image.new("RGB", (W, H), EL_COL.get(el, "#9aa7b4")), (0, 0),
                     ImageChops.multiply(ims, solid).point(lambda v: int(v * 0.30)))

    # ---- 外轮廓 + 内层膜
    band = ImageChops.subtract(big.filter(ImageFilter.MaxFilter(13)), big)
    cv.img.paste(Image.new("RGB", (W, H), INK), (0, 0), band.resize((W, H), Image.LANCZOS))
    inner = big.filter(ImageFilter.MinFilter(13))
    ring = ImageChops.subtract(inner, inner.filter(ImageFilter.MinFilter(5)))
    cv.img.paste(Image.new("RGB", (W, H), (176, 192, 208)), (0, 0),
                 ring.resize((W, H), Image.LANCZOS).point(lambda v: int(v * 0.5)))

    # ---- 表面纹理（端帽已经并进轮廓，不重复画）
    _draw_texture(cv, atoms, edges, place, pos, s, solid)
    return {"s": s, "pos": pos}


class _MaskCanvas(object):
    """把 cv.d 的绘制重定向到一张 L 蒙版上（复用 t70b 的端帽蒙版函数）。"""

    def __init__(self, cv, mask):
        self.cv = cv
        self._d = ImageDraw.Draw(mask)

    @property
    def d(self):
        return self._d


SMALL_PICK = ["OXC", "F2", "LF", "OK", "PK", "WA", "CL", "XA", "O2X2", "OP", "C2", "O2X2P2W2K2A2"]


def load_small():
    items = json.load(open("t4_catalog_all_validated.json", encoding="utf-8"))
    by = {}
    for it in items:
        f = it["formula"]
        if f in SMALL_PICK and f not in by and it["natoms"] <= 10:
            by[f] = it
    return [by[f] for f in SMALL_PICK if f in by]


def page_small(path="images/t73_small.png"):
    items = load_small()
    cols, cw, ch = 3, 500, 430
    rows = (len(items) + cols - 1) // cols
    W = 40 + cols * cw
    H = 160 + rows * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T73 小分子的物质形态（元素字形 + 键带并成一个身体）", 26, True, INK, "lm")
    cv.txt(40, 76, "小分子没有器官，但可以像大分子一样先并成一个整体，再按元素/键型加纹理与端帽——"
                   "读起来是一小块物质，而不是几个图符。", 12.3, False, (96, 112, 128), "lm")
    for i, it in enumerate(items):
        c, r = i % cols, i // cols
        x = 40 + c * cw
        y = 104 + r * ch
        cv.d.rounded_rectangle([x, y, x + cw - 16, y + ch - 16], radius=12,
                               fill=(252, 253, 255), outline=(226, 232, 238))
        cnt = {}
        for el in it["atoms"]:
            cnt[el] = cnt.get(el, 0) + 1
        cv.txt(x + 16, y + 20, it["formula"], 19, True, INK, "lm")
        cv.txt(x + 16, y + 44, "·".join("%s×%d" % (S.CN.get(el, el), n) for el, n in cnt.items()),
               10.5, False, (110, 126, 142), "lm")
        draw_substance(cv, (x + 16, y + 54, cw - 52, ch - 96), list(it["atoms"]),
                       [tuple(e) for e in it["edges"]], it["place"], max_s=72)
        # 底部：键型统计
        place = _place_list(it["place"])
        bt = {}
        for (a, b, m) in it["edges"]:
            t = _bond_type(place, a, b)
            bt[t] = bt.get(t, 0) + 1
        cv.txt(x + 16, y + ch - 40, "键：" + " · ".join("%s×%d" % ({"S": "S 短键", "C": "C 角键", "L": "L 长键"}.get(k, k), v)
                                                      for k, v in bt.items()), 10, False, (110, 126, 142), "lm")
    cv.save(path)
    print("saved", path)


def main():
    page_small()


if __name__ == "__main__":
    main()
