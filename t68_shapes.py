# -*- coding: utf-8 -*-
"""t68_shapes.py —— T68「骨架形状语言」绘制库（Pillow）

形状语法（详见 docs/T68_GLYPH_SYSTEM.md）：
  三价骨架层原子字形：
    O 秩 = 正三角形（尖朝上）     单秩元素 = 三角形
    P 势 = 圆形                   单势元素 = 圆形
    K 散 = 正多边形，角数 = 3 + 骨架内散原子数（K 只有 1 个 → 正方形；
            2 个 → 五边形；3 个 → 六边形；……即"正方形或更多的角"）
  二价连接层原子字形：X 晶 = 尖六边形；W 流 = 圆角六边形；A 气 = 虚线六边形
  一价终端层：C 冰 / L 电 / F 焰 = 小圆点
  键（三价-三价）：S 短键红实线、C 角键绿实线、L 长键紫虚线+中点空格；
            同类 0 级键 = 深色双线 + 焊刻痕（融合/加固）
  骨架家族外形容器（7 种）：
    纯秩=三角形  纯势=圆  纯散=3+k 边形  秩势=拱形(三角∪圆)  秩散=盾形(三角∪方)
    势散=圆角方(方圆超椭圆)  秩势散=六边形
  连接语法：融合（0 级同类键，两块轮廓焊接）/ S 刚性焊桥（双线焊板）/
            C 铰接桥（圆环关节）/ L 浮空软桥（虚线+空格）/ 支臂 / 端帽 / 骨架内桥
"""
import math

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
ELEMCOL = {"O": "#2ecc71", "X": "#f39c12", "C": "#3498db", "P": "#8e44ad",
           "W": "#16a085", "L": "#d35400", "K": "#c0392b", "A": "#1abc9c",
           "F": "#e74c3c"}
TRI = ("O", "P", "K")
DIV = ("X", "W", "A")
MONO = ("C", "L", "F")

BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}
BONDZH = {"S": "S 短键", "C": "C 角键", "L": "L 长键"}
BRIDGE_COL = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483",
              "混合": "#7f8c8d"}

# 家族：键 = 三价元素集合串（按 O,P,K 顺序）
FAMILY = {
    "O":   {"zh": "纯秩", "col": "#2ecc71", "shape": "tri"},
    "P":   {"zh": "纯势", "col": "#8e44ad", "shape": "cir"},
    "K":   {"zh": "纯散", "col": "#c0392b", "shape": "kpoly"},
    "OP":  {"zh": "秩势", "col": "#16a085", "shape": "arch"},
    "OK":  {"zh": "秩散", "col": "#d35400", "shape": "shield"},
    "PK":  {"zh": "势散", "col": "#2980b9", "shape": "squircle"},
    "OPK": {"zh": "秩势散", "col": "#2c3e50", "shape": "hex"},
}
S3 = math.sqrt(3)


# ------------------------------------------------------------------ 基础几何
def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, int(size))


def lighten(hexcol, f):
    h = hexcol.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return tuple(int(c + (255 - c) * f) for c in (r, g, b))


def with_alpha(hexcol, a):
    h = hexcol.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(a))


def center_of(cell, s):
    """轴向坐标 (q,r) → 像素中心（flat-top 六边形）"""
    q, r = cell
    return (1.5 * s * q, S3 * s * (r + q / 2.0))


def hex_pts(cx, cy, s):
    return [(cx + s * math.cos(math.radians(60 * k)),
             cy + s * math.sin(math.radians(60 * k))) for k in range(6)]


def poly_pts(cx, cy, rx, ry, n, rot=-math.pi / 2.0):
    return [(cx + rx * math.cos(rot + 2 * math.pi * j / n),
             cy + ry * math.sin(rot + 2 * math.pi * j / n)) for j in range(n)]


def kpoly_pts(cx, cy, r, n, flat=True):
    """散素多边形：n=4 → 轴对齐正方形；偶数 n 底边水平；奇数 n 顶点朝上。"""
    if n % 2 == 0:
        rot = -math.pi / 2 + math.pi / n
    else:
        rot = -math.pi / 2
    return poly_pts(cx, cy, r, r, n, rot)


def convex_hull(pts):
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in pts))
    if len(pts) < 3:
        return pts

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 1e-9:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 1e-9:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def pad_hull(pts, pad):
    """把点集膨胀成多边形：每个点画圆采样后取凸包（哪怕 1~2 个原子也有厚度）。"""
    out = []
    for (x, y) in pts:
        for k in range(12):
            a = 2 * math.pi * k / 12
            out.append((x + pad * math.cos(a), y + pad * math.sin(a)))
    return convex_hull(out)


def ray_exit(poly, c, other):
    """从 c 沿 c→other 方向射出，返回与凸多边形边界的交点（远端）。"""
    dx, dy = other[0] - c[0], other[1] - c[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    dx, dy = dx / L, dy / L
    best = None
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = dx * ey - dy * ex
        if abs(den) < 1e-9:
            continue
        acx, acy = a[0] - c[0], a[1] - c[1]
        t = (acx * ey - acy * ex) / den
        u = (acx * dy - acy * dx) / den
        if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9:
            if best is None or t > best:
                best = t
    return (c[0] + dx * best, c[1] + dy * best) if best else None


def dashed(d, p1, p2, fill, width=2, dash=7, gap=5):
    x1, y1 = p1
    x2, y2 = p2
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-6:
        return
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    t = 0.0
    while t < L:
        e = min(t + dash, L)
        d.line([(x1 + ux * t, y1 + uy * t),
                (x1 + ux * e, y1 + uy * e)], fill=fill, width=width)
        t = e + gap


def dashed_poly(d, pts, fill, width=2, dash=6, gap=5):
    for i in range(len(pts)):
        dashed(d, pts[i], pts[(i + 1) % len(pts)], fill, width, dash, gap)


def offset_line(p1, p2, off):
    ux, uy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(ux, uy)
    if L < 1e-6:
        return p1, p2
    nx, ny = -uy / L, ux / L
    return ((p1[0] + nx * off, p1[1] + ny * off),
            (p2[0] + nx * off, p2[1] + ny * off))


def text_center(d, cx, cy, s, size, fill="#111", bold=True):
    f = font(size, bold)
    bb = d.textbbox((0, 0), s, font=f)
    d.text((cx - (bb[2] - bb[0]) / 2 - bb[0],
            cy - (bb[3] - bb[1]) / 2 - bb[1]), s, font=f, fill=fill)


def draw_formula(d, cx, cy, text, size, fill="#111111", bold=True,
                 center=True):
    """带下标数字的分子式；center=True 时 cx 为水平中心，否则为左边界。"""
    f_main = font(size, bold)
    f_sub = font(int(size * 0.64), bold)
    segs, buf, cur = [], "", None
    for ch in text:
        t = "sub" if ch.isdigit() else "main"
        if t != cur and buf:
            segs.append((buf, cur))
            buf = ""
        cur, buf = t, buf + ch
    if buf:
        segs.append((buf, cur))
    widths = [d.textlength(s, font=(f_main if t == "main" else f_sub))
              for s, t in segs]
    x = cx - sum(widths) / 2 if center else cx
    yb = cy + size * 0.36
    for (seg, t), w in zip(segs, widths):
        if t == "main":
            d.text((x, yb), seg, font=f_main, fill=fill, anchor="ls")
        else:
            d.text((x, yb + size * 0.18), seg, font=f_sub, fill=fill,
                   anchor="ls")
        x += w


# ------------------------------------------------------------------ 原子字形
def glyph_radius(el, s, kcount=1):
    if el == "O":
        return 0.60 * s
    if el == "P":
        return 0.50 * s
    if el == "K":
        n = min(8, 3 + kcount)
        return 0.46 * s / math.cos(math.pi / n)
    if el == "X":
        return 0.52 * s
    if el == "W":
        return 0.52 * s
    if el == "A":
        return 0.52 * s
    return 0.33 * s  # 一价


def atom_poly(el, cx, cy, s, kcount=1):
    """返回原子字形多边形点列。"""
    if el == "O":
        return poly_pts(cx, cy, glyph_radius(el, s), glyph_radius(el, s), 3)
    if el == "P":
        return poly_pts(cx, cy, glyph_radius(el, s), glyph_radius(el, s), 40)
    if el == "K":
        n = min(8, 3 + kcount)
        return kpoly_pts(cx, cy, glyph_radius(el, s), n)
    if el == "X":
        return hex_pts(cx, cy, glyph_radius(el, s))
    if el == "W":  # 圆角六边形：切角
        R = glyph_radius(el, s)
        raw = hex_pts(cx, cy, R)
        out = []
        for i in range(6):
            a, b = raw[i], raw[(i + 1) % 6]
            for t in (0.16, 0.84):
                out.append((a[0] + (b[0] - a[0]) * t,
                            a[1] + (b[1] - a[1]) * t))
            # 圆滑过渡用中点替换尖角
        # 用边上的点组成圆角近似：直接返回 12 边形（去尖角）
        return out
    if el == "A":
        return hex_pts(cx, cy, glyph_radius(el, s))
    r = glyph_radius(el, s)
    if el == "C":   # 冰：小菱形
        return poly_pts(cx, cy, r * 1.18, r * 1.18, 4)
    if el == "F":   # 焰：小三角形
        return poly_pts(cx, cy, r * 1.3, r * 1.3, 3)
    return poly_pts(cx, cy, r, r, 24)  # L 电：小圆点


def draw_atom(d, el, poly, cx, cy, s, role="skel", kcount=1):
    """画原子字形。role: skel/bridge/intra/arm/mono/free"""
    base = ELEMCOL[el]
    if role == "skel":
        fill = lighten(base, 0.35)
        outline = "#1c2833"
        width = max(2, int(s * 0.075))
    elif role in ("bridge", "intra"):
        fill = lighten(base, 0.45)
        outline = "#1c2833"
        width = max(2, int(s * 0.06))
    else:
        fill = lighten(base, 0.68)
        outline = "#7f8c8d"
        width = max(1, int(s * 0.045))
    if el == "A":
        d.polygon(poly, fill=fill, outline=None)
        dashed_poly(d, poly, outline if outline != "#7f8c8d" else "#1c2833",
                    width, 5, 4)
    else:
        d.polygon(poly, fill=fill, outline=outline, width=width)
    # 元素字母（骨架/桥用深色，装饰用灰）
    letter_size = max(7, int(s * (0.40 if role in ("skel", "bridge") else 0.34)))
    text_center(d, cx, cy, el, letter_size,
                "#111111" if role in ("skel", "bridge") else "#5d6d7e")


# ------------------------------------------------------------------ 家族外形
def fam_key(elems):
    es = set(elems)
    return "".join(e for e in ("O", "P", "K") if e in es)


def fam_of_mol_atoms(atoms):
    return fam_key([a for a in atoms if a in TRI])


def fam_tint(atoms):
    """返回 (组成集合键, 家族色)。颜色统一按三价组成类别（7 家族），
    字形本身（△○■）负责表达具体元素。"""
    key = fam_key(atoms)
    return key, FAMILY[key]["col"]


def fam_shape(key, cx, cy, rx, ry, kcount=1):
    """家族外形容器多边形（以 cx,cy 为中心，半轴 rx,ry）。"""
    kind = FAMILY[key]["shape"]
    if kind == "tri":
        return poly_pts(cx, cy, rx, ry, 3)
    if kind == "cir":
        return poly_pts(cx, cy, rx, ry, 48)
    if kind == "kpoly":
        n = min(8, 3 + kcount)
        if n % 2 == 0:
            rot = -math.pi / 2 + math.pi / n
        else:
            rot = -math.pi / 2
        return poly_pts(cx, cy, rx, ry, n, rot)
    if kind == "hex":
        return poly_pts(cx, cy, rx, ry, 6, -math.pi / 2 + math.pi / 6)
    if kind == "arch":     # 秩势：三角 ∪ 圆
        pts = poly_pts(0, 0, 1, 1, 3) + \
            poly_pts(0, 0.22, 0.82, 0.82, 40)
        h = convex_hull(pts)
        return [(cx + x * rx, cy + y * ry) for (x, y) in h]
    if kind == "shield":   # 秩散：三角 ∪ 方
        sq = [(-0.72, -0.35), (0.72, -0.35), (0.72, 0.95), (-0.72, 0.95)]
        pts = poly_pts(0, 0, 1, 1, 3) + sq
        h = convex_hull(pts)
        return [(cx + x * rx, cy + y * ry) for (x, y) in h]
    if kind == "squircle":  # 势散：方圆超椭圆
        p = 3.4
        out = []
        for k in range(64):
            a = 2 * math.pi * k / 64
            ca, sa = math.cos(a), math.sin(a)
            r = 1.0 / ((abs(ca) ** p + abs(sa) ** p) ** (1.0 / p))
            out.append((cx + r * ca * rx, cy + r * sa * ry))
        return out
    return poly_pts(cx, cy, rx, ry, 36)


def fam_fit_poly(key, cx, cy, atoms_pts, pad, kcount=1, max_rx=1e9,
                 max_ry=1e9):
    """把家族容器缩放到刚好包住 atoms_pts（点集）并留 pad。"""
    if not atoms_pts:
        return fam_shape(key, cx, cy, pad, pad, kcount)
    xs = [p[0] for p in atoms_pts]
    ys = [p[1] for p in atoms_pts]
    rx = max(pad, (max(xs) - min(xs)) / 2 + pad)
    ry = max(pad, (max(ys) - min(ys)) / 2 + pad)
    rx = min(rx, max_rx)
    ry = min(ry, max_ry)
    # 容器必须包含所有点：逐步放大
    for _ in range(24):
        poly = fam_shape(key, cx, cy, rx, ry, kcount)
        if all(point_in_poly(p, poly, pad * 0.55) for p in atoms_pts):
            break
        rx *= 1.08
        ry *= 1.08
    return poly


def point_in_poly(p, poly, tol=0.0):
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and \
                (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
    if inside:
        return True
    if tol <= 0:
        return False
    # 距离边界 <= tol 也算在内
    for i in range(n):
        if dist_point_seg(p, poly[i], poly[(i + 1) % n]) <= tol:
            return True
    return False


def dist_point_seg(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


# ------------------------------------------------------------------ 画布
class Canvas:
    def __init__(self, w, h, bg="#ffffff"):
        self.W, self.H = int(w), int(h)
        self.img = Image.new("RGB", (self.W, self.H), bg)
        self.d = ImageDraw.Draw(self.img)
        self._fonts = {}

    def f(self, size, bold=False):
        key = (int(size), bool(bold))
        if key not in self._fonts:
            self._fonts[key] = font(int(size), bool(bold))
        return self._fonts[key]

    def txt(self, x, y, s, size=14, bold=False, fill="#222", anchor="la"):
        self.d.text((x, y), s, font=self.f(size, bold), fill=fill,
                    anchor=anchor)

    def txt_bg(self, x, y, s, size=13, bold=False, fill="#222", anchor="la",
               bg="#ffffff", pad=3, outline=None):
        f = self.f(size, bold)
        w = f.getlength(s)
        h = size + 6
        if anchor.startswith("l"):
            left = x
        elif anchor.startswith("r"):
            left = x - w
        else:
            left = x - w / 2
        if anchor.endswith("a"):
            top = y
        elif anchor.endswith("m"):
            top = y - h / 2
        else:
            top = y - h
        if bg is not None:
            self.d.rectangle([left - pad, top - pad + 1,
                              left + w + pad, top + h - pad],
                             fill=bg, outline=outline or bg)
        self.d.text((x, y), s, font=f, fill=fill, anchor=anchor)

    def wrap(self, s, max_w, size=13, bold=False):
        f = self.f(size, bold)
        lines, cur = [], ""
        for ch in s:
            if f.getlength(cur + ch) <= max_w or not cur:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines

    def dashed(self, p1, p2, fill, width=2, dash=7, gap=5):
        dashed(self.d, p1, p2, fill, width, dash, gap)

    def rgba(self):
        """新建同尺寸 RGBA 图层，返回 (img, draw)。用完 composite()。"""
        layer = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        return layer, ImageDraw.Draw(layer)

    def composite(self, layer):
        self.img = Image.alpha_composite(self.img.convert("RGBA"),
                                         layer).convert("RGB")
        self.d = ImageDraw.Draw(self.img)

    def save(self, path):
        self.img.save(path)
        print("saved", path)


# ------------------------------------------------------------------ 分子绘制
def fit_layout(place, box, margin=0.6, max_s=None):
    """把 place（轴向坐标）适配进 box=(x0,y0,w,h)，返回 (s, ox, oy)。"""
    x0, y0, w, h = box
    cells = [tuple(p) for p in place]
    # 用 hex 中心坐标求包围范围（s=1）
    pts = [center_of(c, 1.0) for c in cells]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    bw = max(xs) - min(xs) + 2 * margin
    bh = max(ys) - min(ys) + 2 * margin
    s = min(w / bw, h / bh)
    if max_s:
        s = min(s, max_s)
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    ox = x0 + w / 2 - cx * s
    oy = y0 + h / 2 - cy * s
    return s, ox, oy


def draw_lattice(cv, mol, pos, s, cells_l, color="#ececec"):
    d = cv.d
    for i, (q, r) in enumerate(mol["place"]):
        cx, cy = pos[i]
        d.polygon(hex_pts(cx, cy, s), fill=None, outline=color, width=1)
    for mid in cells_l:
        cx, cy = center_of(mid, s)
        dashed_poly(d, hex_pts(cx, cy, s), "#c9c9c9", 1, 4, 4)


def block_hull_polys(mol, pos, s, pad):
    """每个骨架的每个 6 级块 → 膨胀凸包（块轮廓）。"""
    out = []
    for sk in mol["skeletons"]:
        blocks = []
        for blk in sk["blocks"]:
            mem = blk["mem"]
            pts = [pos[v] for v in mem]
            h = pad_hull(pts, glyph_radius("P", s) * 0.9 + pad)
            key, tint = fam_tint([mol["atoms"][v] for v in mem])
            blocks.append({"mem": mem, "hull": h, "fam": key, "tint": tint,
                           "formula": blk["formula"]})
        out.append({"sk": sk, "blocks": blocks})
    return out


def draw_molecule(cv, box, mol, letter=True, hull_alpha=52, show_badges=True,
                  badge_font=13, max_s=None):
    """在 box 内画分子（骨架高亮 + 6 级块轮廓 + 桥符号 + 原子字形）。
    返回 dict(s, pos, hull_info, badges)。"""
    place = [tuple(p) for p in mol["place"]]
    atoms = mol["atoms"]
    role = mol["role"]
    s, ox, oy = fit_layout(place, box, max_s=max_s)
    pos = []
    for (q, r) in place:
        x, y = center_of((q, r), s)
        pos.append((x + ox, y + oy))
    # 骨架内 K 数（用于 K 字形角数）
    kcount_skel = {}
    for sk in mol["skeletons"]:
        kk = sum(1 for v in sk["idx"] if atoms[v] == "K")
        for v in sk["idx"]:
            kcount_skel[v] = max(1, kk)
    polys = []
    for i, el in enumerate(atoms):
        polys.append(atom_poly(el, pos[i][0], pos[i][1], s,
                               kcount_skel.get(i, 1)))
    # L 键中间空格
    mids = set()
    for bd in mol.get("bonds", []):
        if bd.get("type") == "L" and bd.get("mid"):
            mids.add(tuple(bd["mid"]))
    draw_lattice(cv, mol, pos, s, mids)
    # ---- 块轮廓（半透明，在键与原子之下）
    layer, ld = cv.rgba()
    hull_info = block_hull_polys(mol, pos, s, pad=max(2.0, 0.34 * s))
    for skh in hull_info:
        for blk in skh["blocks"]:
            c = blk["tint"]
            ld.polygon(blk["hull"], fill=with_alpha(c, 44))
        for blk in skh["blocks"]:
            c = blk["tint"]
            ld.line([(x, y) for (x, y) in blk["hull"]] +
                    [blk["hull"][0]], fill=with_alpha(c, 215),
                    width=max(2, int(s * 0.055)))
    cv.composite(layer)
    # ---- 键
    d = cv.d
    for bd in mol.get("bonds", []):
        a, b, m, t = bd["a"], bd["b"], bd.get("m", 1), bd.get("type")
        if a >= len(atoms) or b >= len(atoms):
            continue
        pa, pb = pos[a], pos[b]
        ea, eb = atoms[a], atoms[b]
        both_tri = ea in TRI and eb in TRI
        same_elem = both_tri and ea == eb
        if both_tri and not same_elem:
            col = BONDC.get(t, "#555555")
            width = max(2, int(s * 0.055))
            _bond_lines(d, polys[a], polys[b], pa, pb, m, col, width, t,
                        bd.get("mid"), s)
        elif both_tri and same_elem:
            # 0 级同类键：深色双线 + 焊刻痕
            _weld_bond(d, polys[a], polys[b], pa, pb, m, s,
                       highlight=any(fb["a"] == a and fb["b"] == b
                                     for sk in mol["skeletons"]
                                     for fb in sk.get("fusion", [])))
        else:
            col = lighten(BONDC.get(t, "#7f8c8d"), 0.30)
            width = max(1, int(s * 0.035))
            _bond_lines(d, polys[a], polys[b], pa, pb, m, col, width, t,
                        bd.get("mid"), s)
    # ---- 桥符号（在键上，原子之下）
    for bi, br in enumerate(mol["bridges"]):
        for sid, blist in br["bonds_to_skel"].items():
            for bd in blist:
                if bd["type"] == "S":
                    _weld_plate(d, pos[bd["div"]], pos[bd["skel_atom"]], s)
                elif bd["type"] == "C":
                    dx, dy = pos[bd["div"]]
                    d.ellipse([dx - s * 0.22, dy - s * 0.22,
                               dx + s * 0.22, dy + s * 0.22],
                              outline=BRIDGE_COL["C"],
                              width=max(2, int(s * 0.06)))
    # ---- 原子
    for i, el in enumerate(atoms):
        draw_atom(d, el, polys[i], pos[i][0], pos[i][1], s,
                  role.get(str(i), role.get(i, "mono")),
                  kcount_skel.get(i, 1))
    # ---- 骨架编号徽章
    badges = []
    if show_badges:
        for sk in mol["skeletons"]:
            cxs = [pos[v][0] for v in sk["idx"]]
            cys = [pos[v][1] for v in sk["idx"]]
            bx, by = sum(cxs) / len(cxs), sum(cys) / len(cys)
            # 避免压住原子：向上方空白偏移
            bx, by = _nudge_badge(bx, by, sk["idx"], pos, s)
            fkey, col = fam_tint([atoms[v] for v in sk["idx"]])
            r = max(12, s * 0.42)
            d.ellipse([bx - r, by - r, bx + r, by + r], fill="#ffffff",
                      outline=col, width=max(2, int(s * 0.06)))
            text_center(d, bx, by, "%d" % sk["num"], max(9, int(r * 0.95)),
                        col)
            badges.append({"num": sk["num"], "x": bx, "y": by,
                           "col": col})
        # 桥徽章
        for bi, br in enumerate(mol["bridges"]):
            xs = [pos[v][0] for v in br["idx"]]
            ys = [pos[v][1] for v in br["idx"]]
            bx, by = sum(xs) / len(xs), sum(ys) / len(ys)
            bx, by = _nudge_badge(bx, by, br["idx"], pos, s)
            col = BRIDGE_COL.get(br["kind"][:1], "#7f8c8d")
            rw, rh = max(17.0, s * 0.52), max(10.0, s * 0.30)
            d.ellipse([bx - rw, by - rh, bx + rw, by + rh],
                      fill="#ffffff", outline=col, width=max(1, int(s * 0.04)))
            text_center(d, bx, by, "桥%d" % (bi + 1),
                        max(9, int(s * 0.24)), col)
    return {"s": s, "pos": pos, "hull": hull_info, "badges": badges}


def _nudge_badge(bx, by, idxs, pos, s):
    """把徽章推到不与原子中心重叠的位置。"""
    for _ in range(12):
        bad = False
        for v in idxs:
            if math.hypot(pos[v][0] - bx, pos[v][1] - by) < s * 0.62:
                bad = True
                break
        if not bad:
            return bx, by
        by -= s * 0.35
    return bx, by


def _bond_lines(d, poly_a, poly_b, pa, pb, m, col, width, t, mid, s):
    """画两点之间的键（按类型/多重度），端点落在字形边界。"""
    p1 = ray_exit(poly_a, pa, pb)
    p2 = ray_exit(poly_b, pb, pa)
    if p1 is None or p2 is None:
        return
    if t == "L":
        gap = max(2.0, s * 0.10)
        for k in range(m):
            off = (k - (m - 1) / 2) * gap
            a, b = offset_line(p1, p2, off)
            dashed(d, a, b, col, width, 7, 5)
        if mid:
            mx, my = center_of(tuple(mid), s)
            dashed_poly(d, hex_pts(mx, my, s), "#b3b3b3", 1, 4, 4)
        return
    gap = max(2.2, s * 0.13)
    for k in range(m):
        off = (k - (m - 1) / 2) * gap
        a, b = offset_line(p1, p2, off)
        d.line([a, b], fill=col, width=width)


def _weld_bond(d, poly_a, poly_b, pa, pb, m, s, highlight=False):
    """0 级同类键：深色双线 + 中部焊刻痕（融合/加固）。
    highlight=True → 橙色焊刻痕 + 「融合」标签（跨两个 6 级块的融合键）。"""
    p1 = ray_exit(poly_a, pa, pb)
    p2 = ray_exit(poly_b, pb, pa)
    if p1 is None or p2 is None:
        return
    col = "#34495e"
    tick = "#e67e22" if highlight else "#7f8c8d"
    w = max(3, int(s * 0.09)) if highlight else max(2, int(s * 0.06))
    gap = max(2.5, s * 0.13)
    lines = [(p1, p2)] if m == 1 else [offset_line(p1, p2, -gap),
                                       offset_line(p1, p2, gap)]
    for a, b in lines:
        d.line([a, b], fill=col, width=w)
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    ux, uy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(ux, uy) or 1
    nx, ny = -uy / L, ux / L
    half = s * 0.20
    for t in (-0.22, 0.0, 0.22):
        cx, cy = mx + ux * t * 2, my + uy * t * 2
        d.line([(cx - nx * half, cy - ny * half),
                (cx + nx * half, cy + ny * half)], fill=tick,
               width=max(2, int(s * 0.055)))
    if highlight:
        tx, ty = mx + nx * s * 0.72, my + ny * s * 0.72
        text_center(d, tx, ty, "融合", max(10, int(s * 0.28)),
                    "#d35400")


def _weld_plate(d, p_div, p_skel, s):
    """S 刚性焊桥的焊板：在骨架上贴一个小方板。"""
    x, y = p_skel
    dx, dy = p_div[0] - p_skel[0], p_div[1] - p_skel[1]
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    c = (x + ux * s * 0.55, y + uy * s * 0.55)
    h = s * 0.16
    d.line([(c[0] - nx * h - ux * h, c[1] - ny * h - uy * h),
            (c[0] + nx * h - ux * h, c[1] + ny * h - uy * h),
            (c[0] + nx * h + ux * h, c[1] + ny * h + uy * h),
            (c[0] - nx * h + ux * h, c[1] - ny * h + uy * h),
            (c[0] - nx * h - ux * h, c[1] - ny * h - uy * h)],
           fill=BRIDGE_COL["S"], width=max(2, int(s * 0.05)))
