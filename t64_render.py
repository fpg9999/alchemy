# -*- coding: utf-8 -*-
"""t64_render.py —— T64「12 生态群系」实验图表

读取 t64_analysis.json，生成 12 张图（前缀 t64_，输出到 images/）：
  images/t64_design.png               ① 12 群系投料设计（总原子/元素覆盖/温度日程）
  images/t64_temperature.png          ② 温度日程（退火 + 25°C 恒温浮动）
  images/t64_composition_matrix.png   ③ 终态组成矩阵（top 分子式 × 12 群系，对数）
  images/t64_families.png             ④ 家族占比（聚素/动素/散素/混合）
  images/t64_diversity.png            ⑤ 多样性 / 新物质 / 尺寸 / 专一性
  images/t64_size_distribution.png    ⑥ 分子尺寸分布（12 群系小面板，对数）
  images/t64_polymerization.png       ⑦ 聚合度 vs 元素数（平均/最大原子数）
  images/t64_element_usage.png        ⑧ 元素利用率（9 元素 × 12 群系）
  images/t64_persistence.png          ⑨ 群系组成相似度 + 物种共享
  images/t64_snapshot_grid.png        ⑩ 2D 快照网格（4 群系 × 5 时刻）
  images/t64_reaction_stats.png       ⑪ 反应判定/capped/净事件/耗时
  images/t64_feature_ranking.png      ⑫ 特色群系排名（自动评分 + 理由）

缺失群系（结果未就绪）时：占位面板；快照图需要原始 result JSON，缺失则画占位。

用法：
  python t64_render.py
  python t64_render.py --analysis t64_analysis.json --images images
  python t64_render.py --only design,temperature     # 自测部分图
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_ANALYSIS = os.path.join(BASE, "t64_analysis.json")
DEFAULT_IMAGES = os.path.join(BASE, "images")

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT_REG

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
ELEMCOL = {"O": "#2ecc71", "X": "#f39c12", "C": "#3498db", "P": "#8e44ad",
           "W": "#16a085", "L": "#d35400", "K": "#c0392b", "A": "#1abc9c",
           "F": "#e74c3c"}
BONDCOL = {1: "#9aa5b1", 2: "#34495e", 3: "#c0392b"}
FAM_ORDER = ["poly", "dyn", "scat", "mixed"]
FAM_COL = {"poly": "#2e86de", "dyn": "#e67e22", "scat": "#c0392b",
           "mixed": "#8e44ad"}
FAM_CN = {"poly": "聚素", "dyn": "动素", "scat": "散素", "mixed": "混合"}
NELEM_COL = {3: "#7f8c8d", 4: "#e74c3c", 5: "#f39c12", 6: "#16a085",
             7: "#8e44ad", 8: "#2e86de", 9: "#c0392b"}
PAL = ["#2e86de", "#ee5253", "#10ac84", "#f39c12", "#8e44ad", "#16a085",
       "#d35400", "#2c3e50", "#c0392b", "#7f8c8d", "#27ae60", "#e84393"]
SNAP_PAL = ["#2ecc71", "#f39c12", "#3498db", "#9b59b6", "#1abc9c", "#e74c3c",
            "#00acc1", "#e84393", "#7f8c8d", "#2c3e50", "#8e44ad", "#a0522d"]


# ---------------------------------------------------------------- 通用
def nice_ticks(lo, hi, n=6):
    if hi <= lo:
        return [lo]
    span = hi - lo
    raw = span / max(1, n)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = mag
    for m in (1, 2, 2.5, 5, 10):
        if span / (m * mag) <= n + 2:
            step = m * mag
            break
    first = math.ceil(lo / step) * step
    out, v = [], first
    while v <= hi + 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def log_ticks(lo, hi):
    lo = max(1.0, float(lo))
    hi = max(lo + 1, float(hi))
    out, p = [], 0
    while 10 ** p <= hi * 1.0001:
        if 10 ** p >= lo * 0.9999:
            out.append(10 ** p)
        p += 1
    return out


def fmt_num(v, nd=0):
    if v is None:
        return "-"
    av = abs(v)
    if av >= 1e6:
        return "%.2fM" % (v / 1e6)
    if av >= 1e4:
        return "%.0fk" % (v / 1e3)
    if av >= 1e3 and nd == 0:
        return "%.0fk" % (v / 1e3)
    return ("%." + str(nd) + "f") % v


def fmt_commas(v):
    if v is None:
        return "-"
    return "{:,}".format(int(round(v)))


def pct(x, nd=1):
    if x is None:
        return "-"
    return ("%." + str(nd) + "f") % (100.0 * float(x))


class Chart:
    def __init__(self, w, h, title=None, subtitle=None):
        self.W, self.H = w, h
        self.img = Image.new("RGB", (w, h), "white")
        self.d = ImageDraw.Draw(self.img)
        self._fonts = {}
        if title:
            self.txt(36, 18, title, size=27, bold=True, fill="#111")
        if subtitle:
            self.txt(36, 56, subtitle, size=15, fill="#555")

    def f(self, size, bold=False):
        key = (int(size), bool(bold))
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(
                FONT_BOLD if bold else FONT_REG, int(size))
        return self._fonts[key]

    def txt(self, x, y, s, size=15, bold=False, fill="#222", anchor="la"):
        self.d.text((x, y), s, font=self.f(size, bold), fill=fill, anchor=anchor)

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
        self.d.rectangle([left - pad, top - pad + 1, left + w + pad, top + h - pad],
                         fill=bg, outline=outline or bg)
        self.txt(x, y, s, size=size, bold=bold, fill=fill, anchor=anchor)

    def rot(self, x, y, s, size=14, bold=False, fill="#222"):
        f = self.f(size, bold)
        tw = int(f.getlength(s)) + 8
        th = int(size) + 10
        tmp = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
        ImageDraw.Draw(tmp).text((4, 3), s, font=f, fill=fill)
        tmp = tmp.rotate(90, expand=True)
        self.img.paste(tmp, (int(x - tmp.width / 2), int(y - tmp.height / 2)), tmp)

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

    def frame(self, box, xlim, ylim, xticks, yticks, grid=True, logy=False,
              logx=False, xtick_fmt=None, ytick_fmt=None, tick_size=13,
              grid_color="#e9e9e9", xtick_labels=None, frame=True):
        x0, y0, x1, y1 = box
        xlo, xhi = float(xlim[0]), float(xlim[1])
        ylo, yhi = float(ylim[0]), float(ylim[1])

        def mx(v):
            v = float(v)
            if logx:
                v = max(v, xlo)
                t = (math.log(v) - math.log(xlo)) / (math.log(xhi) - math.log(xlo))
            else:
                t = (v - xlo) / (xhi - xlo)
            return x0 + t * (x1 - x0)

        def my(v):
            v = float(v)
            if logy:
                v = max(v, ylo)
                t = (math.log(v) - math.log(ylo)) / (math.log(yhi) - math.log(ylo))
            else:
                t = (v - ylo) / (yhi - ylo)
            return y1 - t * (y1 - y0)

        if grid:
            for xv in xticks:
                if xlo <= float(xv) <= xhi:
                    self.d.line([mx(xv), y0, mx(xv), y1], fill=grid_color, width=1)
            for yv in yticks:
                if ylo <= float(yv) <= yhi:
                    self.d.line([x0, my(yv), x1, my(yv)], fill=grid_color, width=1)
        if frame:
            self.d.rectangle([x0, y0, x1, y1], outline="#333", width=2)
        fmt_x = xtick_fmt or (lambda v: ("%g" % v))
        for i, xv in enumerate(xticks):
            if not (xlo <= float(xv) <= xhi):
                continue
            X = mx(xv)
            self.d.line([X, y1, X, y1 + 6], fill="#333", width=1)
            lab = (xtick_labels[i] if xtick_labels and i < len(xtick_labels)
                   else fmt_x(xv))
            self.txt(X, y1 + 10, lab, size=tick_size, anchor="ma", fill="#333")
        fmt_y = ytick_fmt or (lambda v: ("%g" % v))
        for yv in yticks:
            if not (ylo <= float(yv) <= yhi):
                continue
            Y = my(yv)
            self.d.line([x0 - 6, Y, x0, Y], fill="#333", width=1)
            self.txt(x0 - 10, Y, fmt_y(yv), size=tick_size, anchor="rm", fill="#333")
        return mx, my

    def border(self, box, fill=None):
        self.d.rectangle(box, outline="#333", width=2, fill=fill)

    def legend(self, x, y, items, size=13, row_h=25, cols=1, col_w=190,
               swatch=13):
        for i, (col, lab) in enumerate(items):
            r, c = divmod(i, cols)
            X, Y = x + c * col_w, y + r * row_h
            self.d.rectangle([X, Y + 3, X + swatch, Y + 3 + swatch],
                             fill=col, outline="#555", width=1)
            self.txt(X + swatch + 7, Y, lab, size=size)

    def dashed(self, p0, p1, fill="#888", width=1, dash=6, gap=4):
        x0, y0 = p0
        x1, y1 = p1
        L = math.hypot(x1 - x0, y1 - y0)
        if L <= 0:
            return
        pos = 0.0
        while pos < L:
            e = min(L, pos + dash)
            self.d.line([x0 + (x1 - x0) * pos / L, y0 + (y1 - y0) * pos / L,
                         x0 + (x1 - x0) * e / L, y0 + (y1 - y0) * e / L],
                        fill=fill, width=width)
            pos += dash + gap

    def line(self, pts, fill="#333", width=3):
        pts = [p for p in pts if p is not None]
        if len(pts) >= 2:
            self.d.line(pts, fill=fill, width=width, joint="curve")

    def save(self, path):
        self.img.save(path)
        return os.path.getsize(path)


def data_note(c, lines, y=None, size=13, color="#555", x=36):
    wrapped = []
    for s in lines:
        wrapped.extend(c.wrap(s, c.W - x - 24, size=size))
    y = c.H - 18 - 22 * len(wrapped) if y is None else y
    for i, s in enumerate(wrapped):
        c.txt(x, y + i * 22, s, size=size, fill=color)


def pending_panel(c, box, msg="未就绪", sub="结果未就绪"):
    x0, y0, x1, y1 = box
    c.d.rectangle(box, outline="#c0392b", width=2, fill="#fff8f8")
    c.txt((x0 + x1) / 2, (y0 + y1) / 2 - 12, msg, size=18, bold=True,
          anchor="mm", fill="#c0392b")
    c.txt((x0 + x1) / 2, (y0 + y1) / 2 + 16, sub, size=12, anchor="mm",
          fill="#a05252")


def layout_mol(atoms, edges, iters=260):
    n = len(atoms)
    if n == 1:
        return [(0.0, 0.0)]
    if n == 2:
        return [(-1.0, 0.0), (1.0, 0.0)]
    adj = [[] for _ in range(n)]
    for e in edges:
        i, j = int(e[0]), int(e[1])
        adj[i].append(j)
        adj[j].append(i)
    pos = [[math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)]
           for i in range(n)]
    k = 1.0 / math.sqrt(n)
    for it in range(iters):
        disp = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            xi, yi = pos[i]
            for j in range(i + 1, n):
                dx, dy = xi - pos[j][0], yi - pos[j][1]
                d2 = dx * dx + dy * dy
                if d2 < 1e-6:
                    dx, dy, d2 = 0.01 * (i - j + 1), 0.01, 1e-4
                d = math.sqrt(d2)
                f = k * k / d
                ux, uy = dx / d, dy / d
                disp[i][0] += ux * f
                disp[i][1] += uy * f
                disp[j][0] -= ux * f
                disp[j][1] -= uy * f
        for i in range(n):
            for j in adj[i]:
                if j <= i:
                    continue
                dx, dy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                d = math.hypot(dx, dy) or 1e-6
                f = d / k * 0.6
                ux, uy = dx / d, dy / d
                disp[i][0] += ux * f
                disp[i][1] += uy * f
                disp[j][0] -= ux * f
                disp[j][1] -= uy * f
        temp = max(0.015, 0.10 * (1 - it / float(iters)))
        for i in range(n):
            dl = math.hypot(disp[i][0], disp[i][1]) or 1.0
            step = min(dl, temp)
            pos[i][0] += disp[i][0] / dl * step
            pos[i][1] += disp[i][1] / dl * step
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sx = max(1e-6, (max(xs) - min(xs)) / 2)
    sy = max(1e-6, (max(ys) - min(ys)) / 2)
    s = max(sx, sy)
    return [((p[0] - cx) / s, (p[1] - cy) / s) for p in pos]


def draw_mol_panel(c, rec, box, header_size=13, sub=True):
    x0, y0, x1, y1 = box
    atoms = rec.get("atoms") or []
    edges = rec.get("edges") or []
    n = len(atoms)
    formula = rec.get("formula") or ""
    c.txt((x0 + x1) / 2, y0 + 4, formula, size=header_size, bold=True,
          anchor="ma", fill="#111")
    pad = 8
    bx0, by0, bx1, by1 = x0 + pad, y0 + 26, x1 - pad, y1 - 40
    bw, bh = bx1 - bx0, by1 - by0
    c.d.rectangle([bx0, by0, bx1, by1], fill="#fbfbfb", outline="#e0e0e0")
    if n:
        pos = layout_mol(atoms, edges)
        rad = max(2.6, min(9.0, 0.5 * min(bw, bh) / (math.sqrt(max(1, n)) * 1.9)))
        if n > 24:
            rad = max(2.2, min(4.5, rad))
        pts = [(bx0 + bw / 2 + px * (bw / 2 - rad - 3),
                by0 + bh / 2 + py * (bh / 2 - rad - 3)) for px, py in pos]
        for e in edges:
            i, j, m = int(e[0]), int(e[1]), int(e[2])
            c.d.line([pts[i], pts[j]], fill=BONDCOL.get(m, "#888"),
                     width=1 if m == 1 else 2)
        for i, e in enumerate(atoms):
            X, Y = pts[i]
            c.d.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                        fill=ELEMCOL.get(e, "#ccc"), outline="#333", width=1)
            if rad >= 5.5:
                c.txt(X, Y - 1, e, size=max(7, int(rad * 1.5)), bold=True,
                      anchor="mm", fill="#111")
    else:
        c.txt((bx0 + bx1) / 2, (by0 + by1) / 2, "（无结构数据）", size=12,
              anchor="mm", fill="#888")
    if sub:
        c.txt((x0 + x1) / 2, y1 - 30, "×%s · %d 原子" % (
            fmt_commas(rec.get("count")), rec.get("atoms") or n),
            size=11, anchor="ma", fill="#333")
        if rec.get("family"):
            c.txt((x0 + x1) / 2, y1 - 14, FAM_CN.get(rec["family"], rec["family"]),
                  size=10, anchor="ma", fill="#666")


# ---------------------------------------------------------------- 分析数据访问
def biomes(a):
    return a.get("biomes") or []


def present(a):
    return [b for b in biomes(a) if b.get("present")]


def biome(a, bid):
    for b in biomes(a):
        if b.get("id") == bid:
            return b
    return {}


def schedule_curve(sch, t):
    s = sch or {}
    T0 = float(s.get("T0") or 1000.0)
    tm = float(s.get("T_mid") or 25.0)
    ann = float(s.get("anneal_minutes") or 975)
    hold = float(s.get("hold_minutes") or 600)
    if t <= ann:
        return T0 - (T0 - tm) * t / ann
    dt = t - ann
    day = float(s.get("day_amp") or 8.0)
    dper = float(s.get("day_period") or 240.0)
    yamp = float(s.get("year_amp") or 3.0)
    yper = float(s.get("year_period") or 900.0)
    yph = float(s.get("year_phase") or 0.0)
    return tm + day * math.sin(2 * math.pi * dt / dper) + \
        yamp * math.sin(2 * math.pi * dt / yper + yph)


_RAW = {}


def load_raw(a, bid):
    if bid in _RAW:
        return _RAW[bid]
    path = ((a.get("meta") or {}).get("files") or {}).get("biomes", {}).get(
        bid, {}).get("result")
    data = None
    if path:
        cands = [path, os.path.join(BASE, path)]
        for p in cands:
            if p and os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as fh:
                        data = json.load(fh)
                    break
                except Exception:
                    data = None
    _RAW[bid] = data
    return data


# ---------------------------------------------------------------- ① 投料设计
def chart_design(a, out):
    ds = a.get("design") or {}
    bs = ds.get("biomes") or biomes(a)
    sch = a.get("schedule") or {}
    n_present = len(present(a))
    W, H = 1600, 1120
    c = Chart(
        W, H,
        "① T64 生态群系投料设计：12 群系 × 3~9 种元素的双原子单质",
        "每群系只投入自己元素的双原子单质；每元素 2,000~4,000 原子；L=17,000~20,000；"
        "cap=40；总 1575 分钟（975min 退火 + 600min 恒温浮动）")
    # 左：12 群系总原子条形
    box = (90, 180, 1000, 1000)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "12 群系投料量（总原子数，颜色=元素数）",
           size=16, bold=True)
    bx = (box[0] + 210, box[1] + 50, box[2] - 130, box[3] - 70)
    maxat = max([b.get("total_atoms") or 0 for b in bs] or [1]) * 1.08
    mx, my = c.frame(bx, (0, maxat), (0, len(bs)),
                     nice_ticks(0, maxat, 6),
                     [i + 0.5 for i in range(len(bs))],
                     xtick_fmt=lambda v: fmt_num(v),
                     ytick_fmt=lambda v: "")
    rh = (bx[3] - bx[1]) / float(max(1, len(bs)))
    for i, b in enumerate(bs):
        y = bx[1] + i * rh
        at = b.get("total_atoms") or 0
        ne = b.get("n_elements") or len(b.get("elements") or [])
        x1 = mx(at)
        c.d.rectangle([bx[0], y + rh * 0.16, max(bx[0] + 2, x1), y + rh * 0.84],
                      fill=NELEM_COL.get(ne, "#7f8c8d"), outline="#555")
        c.txt(bx[0] - 8, y + rh / 2, "%s %s" % (b.get("id"), b.get("name") or ""),
              size=13, anchor="rm", fill="#222")
        c.txt(x1 + 8, y + rh / 2, "%s 原子 · %s 元素" % (fmt_commas(at), ne),
              size=12, anchor="lm", fill="#333")
    c.legend(box[0] + 210, box[3] - 42,
             [(NELEM_COL[k], "%d 元素" % k) for k in (3, 4, 5, 6, 7, 8, 9)],
             size=12, cols=7, col_w=100, row_h=20)
    # 右上：元素覆盖矩阵 12×9
    box2 = (1040, 180, 1560, 640)
    c.border(box2)
    c.txt(box2[0] + 14, box2[1] + 8, "元素覆盖矩阵（■=该群系投入该元素）",
           size=16, bold=True)
    gx0, gy0 = box2[0] + 152, box2[1] + 70
    cw = (box2[2] - gx0 - 20) / 9.0
    chh = (box2[3] - gy0 - 26) / float(len(bs))
    for j, e in enumerate(ORDER):
        c.txt(gx0 + cw * (j + 0.5), gy0 - 22, "%s %s" % (e, CN[e]), size=12,
              anchor="ma", bold=True, fill=ELEMCOL[e])
    for i, b in enumerate(bs):
        els = set(b.get("elements") or [])
        c.txt(gx0 - 8, gy0 + chh * (i + 0.5), "%s %s" % (b.get("id"), b.get("name") or ""),
              size=10, anchor="rm", fill="#222")
        for j, e in enumerate(ORDER):
            x0 = gx0 + cw * j
            y0 = gy0 + chh * i
            if e in els:
                c.d.rectangle([x0 + 1, y0 + 1, x0 + cw - 1, y0 + chh - 1],
                              fill=ELEMCOL[e], outline="#fff")
                c.txt(x0 + cw / 2, y0 + chh / 2, "●", size=9, anchor="mm",
                      fill="#ffffff")
            else:
                c.d.rectangle([x0 + 1, y0 + 1, x0 + cw - 1, y0 + chh - 1],
                              fill="#f6f6f6", outline="#eee")
    # 右下：温度日程
    box3 = (1040, 670, 1560, 1000)
    c.border(box3)
    c.txt(box3[0] + 14, box3[1] + 8, "温度日程（1000→25°C 退火 + 25°C 恒温浮动）",
           size=15, bold=True)
    tb = (box3[0] + 74, box3[1] + 44, box3[2] - 20, box3[3] - 40)
    minutes = int(sch.get("minutes") or 1575)
    mx2, my2 = c.frame(tb, (0, minutes), (0, 1040),
                       [0, 250, 500, 750, 975, 1200, 1575],
                       [0, 250, 500, 750, 1000],
                       ytick_fmt=lambda v: "%d" % v)
    pts = []
    for k in range(0, minutes * 2 + 1):
        t = k / 2.0
        pts.append((mx2(t), my2(schedule_curve(sch, t))))
    c.line(pts, fill="#c0392b", width=2)
    Xh = mx2(float(sch.get("anneal_minutes") or 975))
    c.dashed((Xh, tb[1]), (Xh, tb[3]), fill="#888", width=1)
    c.txt(Xh - 4, tb[1] + 6, "975min 退火结束", size=10, anchor="rm", fill="#666")
    for b in present(a):
        if b.get("final_T") is not None:
            c.d.ellipse([mx2(minutes) - 3, my2(b["final_T"]) - 3,
                         mx2(minutes) + 3, my2(b["final_T"]) + 3],
                        fill="#2e86de")
    c.txt(tb[0], 1010, "时间 t（分钟）· 蓝点=各群系实测 final_T", size=11,
          fill="#666")
    data_note(c, [
        "12 群系均只投入自身元素的双原子单质（每元素 2,000/2,500/3,000/3,500/4,000 原子不等），"
        "所有群系至少含一种三价元素（O/P/K），L=17,000~20,000、cap=40。",
        "每群系独立种子 seed=20261127+序号；温度日程：1000°C 按 1°C/分钟降到 25°C（975 分钟），"
        "随后 600 分钟 25°C 恒温 ±8°C 日周期（240min）+ ±3°C 季节浮动（900min）。",
        "总模拟 1575 分钟，事件蓄水池 30,000；本页数据 %d/12 群系已就绪。" % n_present,
    ])
    return c.save(out)


# ---------------------------------------------------------------- ② 温度日程
def chart_temperature(a, out):
    sch = a.get("schedule") or {}
    minutes = int(sch.get("minutes") or 1575)
    ann = float(sch.get("anneal_minutes") or 975)
    W, H = 1600, 1120
    c = Chart(
        W, H,
        "② T64 温度日程：975min 退火（1000→25°C）+ 600min 25°C 恒温浮动",
        "恒温段 = 25°C + 8°C·sin(2πt/240min) + 3°C·sin(2πt/900min+0.7)，实际 14~36°C")
    box = (90, 190, 1490, 610)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "全程温度曲线（0~1575 分钟）", size=16, bold=True)
    bx = (box[0] + 80, box[1] + 50, box[2] - 24, box[3] - 50)
    mx, my = c.frame(bx, (0, minutes), (0, 1060),
                     [0, 250, 500, 750, 975, 1200, 1400, 1575],
                     [0, 250, 500, 750, 1000],
                     ytick_fmt=lambda v: "%d" % v)
    pts = [(mx(k / 2.0), my(schedule_curve(sch, k / 2.0)))
           for k in range(0, minutes * 2 + 1)]
    c.line(pts, fill="#c0392b", width=3)
    Xh = mx(ann)
    c.dashed((Xh, bx[1]), (Xh, bx[3]), fill="#888", width=2)
    c.d.text((Xh + 8, bx[1] + 10), "t=975min", font=c.f(12), fill="#666")
    c.txt(bx[0] + 10, bx[1] + 10, "1000°C", size=13, fill="#666")
    c.txt(bx[2] - 70, bx[3] - 44, "25°C", size=13, anchor="ra", fill="#666")
    # 实测 final_T
    for b in present(a):
        if b.get("final_T") is not None:
            X, Y = mx(minutes), my(b["final_T"])
            c.d.ellipse([X - 3, Y - 3, X + 3, Y + 3], fill="#2e86de")
    c.txt(bx[2] - 8, bx[1] + 10, "蓝点 = 各群系实测 final_T", size=11, anchor="ra",
          fill="#2e86de")
    # 下：恒温段放大
    box2 = (90, 650, 1490, 990)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "恒温段放大（975~1575 分钟，25±11°C 浮动）",
           size=16, bold=True)
    bx2 = (box2[0] + 80, box2[1] + 48, box2[2] - 24, box2[3] - 46)
    lo, hi = 975, minutes
    mx2, my2 = c.frame(bx2, (lo, hi), (12, 40),
                       [975, 1050, 1125, 1200, 1300, 1400, 1500, 1575],
                       [12, 18, 24, 30, 36, 40],
                       ytick_fmt=lambda v: "%d" % v)
    pts = [(mx2(lo + k / 10.0), my2(schedule_curve(sch, lo + k / 10.0)))
           for k in range(0, int((hi - lo) * 10) + 1)]
    c.line(pts, fill="#c0392b", width=2)
    c.dashed((bx2[0], my2(25)), (bx2[2], my2(25)), fill="#888", width=1)
    c.dashed((bx2[0], my2(33)), (bx2[2], my2(33)), fill="#f39c12", width=1)
    c.dashed((bx2[0], my2(17)), (bx2[2], my2(17)), fill="#2e86de", width=1)
    c.txt(bx2[2] - 4, my2(33) - 6, "33°C = 25+8", size=10, anchor="ra",
          fill="#f39c12")
    c.txt(bx2[2] - 4, my2(17) - 6, "17°C = 25-8", size=10, anchor="ra",
          fill="#2e86de")
    data_note(c, [
        "退火段 975 分钟从 1000°C 线性降到 25°C（1°C/分钟）；恒温段 600 分钟内温度在 25°C 附近做"
        "日周期（±8°C，240min）与季节（±3°C，900min）叠加浮动，理论范围 14~36°C。",
        "T64 的 12 个群系共用同一温度日程，只有元素组合/投料量/群系系数不同；实测 final_T 均在 22°C 附近"
        "（受 phase 与最后一帧影响）。",
        "恒温段事件数远小于退火段：终态产物基本在 1000→25°C 冷却过程中定型，25°C 只做缓慢重排。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ③ 组成矩阵
def chart_composition_matrix(a, out):
    cross = a.get("cross") or {}
    rows = cross.get("matrix") or []
    ids = cross.get("biome_ids") or []
    W, H = 1600, 1180
    c = Chart(
        W, H,
        "③ T64 终态组成矩阵：各群系 top 分子式 × 12 群系（分子数，对数色阶）",
        "行=至少进入一个群系终态组成的分子式（按覆盖群系数/总量排序，最多 30 行）；格子数字=该群系终态分子数")
    box = (90, 180, 1560, 1030)
    c.border(box)
    gx0, gy0 = box[0] + 240, box[1] + 76
    cw = (box[2] - gx0 - 60) / float(max(1, len(ids)))
    nrow = max(1, len(rows))
    chh = min(26.0, (box[3] - gy0 - 30) / float(nrow))
    for j, bid in enumerate(ids):
        c.txt(gx0 + cw * (j + 0.5), gy0 - 24, bid, size=12, anchor="ma", bold=True)
    maxc = 1
    for r in rows:
        for v in r["counts"].values():
            maxc = max(maxc, v)
    for i, r in enumerate(rows):
        y0 = gy0 + chh * i
        fam = r.get("family") or "poly"
        c.d.rectangle([box[0] + 12, y0 + 2, box[0] + 16, y0 + chh - 2],
                      fill=FAM_COL.get(fam, "#888"))
        c.txt(box[0] + 20, y0 + chh / 2 - 1, "%s（%s, %d原子）" % (
            r["formula"], FAM_CN.get(fam, fam), r["max_atoms"]),
            size=11, anchor="lm", fill="#222")
        c.txt(gx0 - 8, y0 + chh / 2 - 1, "%d 群系" % r["n_biomes"], size=10,
              anchor="rm", fill="#666")
        for j, bid in enumerate(ids):
            v = r["counts"].get(bid) or 0
            x0 = gx0 + cw * j
            if v > 0:
                t = math.log(v + 1) / math.log(maxc + 1)
                col = (int(255 - 200 * t), int(245 - 160 * t), int(250 - 90 * t))
                col = "#%02x%02x%02x" % (max(30, col[0]), max(40, col[1]),
                                         max(80, col[2]))
                c.d.rectangle([x0 + 1, y0 + 1, x0 + cw - 1, y0 + chh - 1],
                              fill=col, outline="#fff")
                if cw >= 66 and chh >= 18:
                    c.txt(x0 + cw / 2, y0 + chh / 2, fmt_commas(v), size=9,
                          anchor="mm", fill="#fff" if t > 0.55 else "#111")
            else:
                c.d.rectangle([x0 + 1, y0 + 1, x0 + cw - 1, y0 + chh - 1],
                              fill="#fafafa", outline="#eee")
    # 色阶图例
    lx, ly = box[0] + 250, box[3] - 22
    for k in range(10):
        t = k / 9.0
        col = (int(255 - 200 * t), int(245 - 160 * t), int(250 - 90 * t))
        col = "#%02x%02x%02x" % (max(30, col[0]), max(40, col[1]), max(80, col[2]))
        c.d.rectangle([lx + k * 26, ly, lx + (k + 1) * 26, ly + 12], fill=col,
                      outline="#ddd")
    c.txt(lx - 8, ly + 1, "少", size=10, anchor="rm", fill="#666")
    c.txt(lx + 10 * 26 + 6, ly + 1, "多（最大 %s）" % fmt_commas(maxc), size=10,
          anchor="lm", fill="#666")
    c.legend(box[2] - 330, box[3] - 26,
             [(FAM_COL[g], FAM_CN[g]) for g in FAM_ORDER], size=11, cols=4,
             col_w=80, row_h=18)
    data_note(c, [
        "行覆盖多个群系的分子式（如 OXC、PWL、KAF 等三元产物）说明不同元素组合倾向于形成"
        "“元素计量比固定”的特征化合物；跨群系共享行越少，群系终态越独特。",
        "分子数为该群系终态该分子式的分子个数（非原子数）；颜色对数压缩，空格=该群系终态没有该分子式。",
        "T64 每群系终态种数 4~24 种（B06=4、B11=24、B08=17、B09/B10=20），绝大多数分子为 3~17 原子；"
        "最大分子 39 原子出现在 B09/B10/B11（B05 最大仅 17 原子）。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ④ 家族占比
def chart_families(a, out):
    ps = present(a)
    W, H = 1600, 1180
    c = Chart(
        W, H,
        "④ T64 家族占比：聚素 / 动素 / 散素 / 混合（按终态原子占比）",
        "家族=分子中出现的元素组：聚素 O/X/C、动素 P/W/L、散素 K/A/F；同时含 2 组以上=混合")
    box = (90, 180, 1560, 910)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "终态原子占比（每群系 100% 堆叠）", size=16,
           bold=True)
    bx = (box[0] + 220, box[1] + 60, box[2] - 430, box[3] - 54)
    mx, my = c.frame(bx, (0, 1.0), (0, len(ps)), [0, 0.25, 0.5, 0.75, 1.0],
                     [i + 0.5 for i in range(len(ps))],
                     xtick_fmt=lambda v: "%d%%" % round(v * 100),
                     ytick_fmt=lambda v: "")
    rh = (bx[3] - bx[1]) / float(max(1, len(ps)))
    for i, b in enumerate(ps):
        y = bx[1] + i * rh
        c.txt(bx[0] - 8, y + rh / 2, "%s %s" % (b["id"], b["name"]), size=12,
              anchor="rm", fill="#222")
        x = bx[0]
        for g in FAM_ORDER:
            sh = (b.get("groups") or {}).get(g, {}).get("atoms_share") or 0
            w = (bx[2] - bx[0]) * sh
            if w > 0:
                c.d.rectangle([x, y + rh * 0.15, x + w, y + rh * 0.85],
                              fill=FAM_COL[g], outline="#555")
                if w > 60:
                    c.txt(x + w / 2, y + rh / 2, "%s%%" % pct(sh, 1), size=11,
                          anchor="mm", fill="#fff", bold=True)
                x += w
        # 右侧：残留/转化 + 含 F/A/K 原子占比
        rx = bx[2] + 24
        res = (b.get("residue") or {}).get("atoms_share") or 0
        c.d.rectangle([rx, y + rh * 0.22, rx + 120 * res, y + rh * 0.78],
                      fill="#95a5a6", outline="#555")
        esh = {e: ((b.get("elements") or {}).get(e) or {}).get("share") or 0
               for e in ("F", "A", "K")}
        c.txt(rx + 128, y + rh / 2,
              "残留 %s%% · 转化 %s%% · 含F/A/K %s/%s/%s%%" % (
                  pct(res, 1), pct(b.get("conversion"), 1),
                  pct(esh["F"], 1), pct(esh["A"], 1), pct(esh["K"], 1)),
              size=10, anchor="lm", fill="#333")
    c.legend(box[0] + 220, box[3] + 8,
             [(FAM_COL[g], FAM_CN[g]) for g in FAM_ORDER] +
             [("#95a5a6", "单质残留（灰条）")], size=13, cols=5, col_w=150,
             row_h=22)
    data_note(c, [
        "聚素=只含 O/X/C 的分子（如 OXC、O2X2C4）；动素=P/W/L；散素=K/A/F；"
        "混合=同时含两组以上元素（如含 P 的 O-P 化合物），代表跨族耦合。",
        "单质残留=仍以 X2 等单原子分子存在的原子占比；转化=1-单质残留，表示元素进入化合物的比例。",
        "三价元素（O/P/K）利用率越高、单质残留越低，说明该群系越“充分反应”。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ⑤ 多样性
def chart_diversity(a, out):
    ps = present(a)
    W, H = 1600, 1180
    c = Chart(
        W, H,
        "⑤ T64 多样性 / 新物质 / 尺寸 / 专一性：12 群系对比",
        "终点态统计；柱色=元素数；有效物种=exp(Shannon 熵)，越小说明产物越集中")
    fields = [
        ("distinct_formulas", "终态分子式种数", lambda v: "%d" % v, "种"),
        ("effective_species", "有效物种数", lambda v: "%.2f" % v, "种"),
        ("new_substances", "目录外新物质数", lambda v: "%d" % v, "种"),
        ("max_atoms", "最大分子原子数", lambda v: "%d" % v, "原子"),
        ("top1_share", "头号产物占比", lambda v: "%.0f%%" % v, ""),
        ("mean_atoms", "平均分子原子数", lambda v: "%.2f" % v, "原子"),
    ]
    cols, rows = 3, 2
    pw = (W - 120) / cols
    ph = (H - 260) / rows
    for idx, (field, title, f, unit) in enumerate(fields):
        r, cc = divmod(idx, cols)
        x = 60 + cc * pw
        y = 170 + r * ph
        box = (x, y, x + pw - 24, y + ph - 40)
        c.border(box)
        c.txt(box[0] + 10, box[1] + 6, title, size=15, bold=True)
        if not ps:
            pending_panel(c, box)
            continue
        vals = [b.get(field) or 0 for b in ps]
        if field == "top1_share":
            vals = [v * 100.0 for v in vals]
        vmax = max(vals) if max(vals) > 0 else 1
        bx = (box[0] + 46, box[1] + 38, box[2] - 10, box[3] - 52)
        mx, my = c.frame(bx, (0, len(ps)), (0, vmax * 1.15),
                         [i + 0.5 for i in range(len(ps))],
                         nice_ticks(0, vmax * 1.15, 4),
                         xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: ("%d%%" % v) if field == "top1_share" else fmt_num(v))
        gw = (bx[2] - bx[0]) / float(len(ps))
        for i, b in enumerate(ps):
            v = vals[i]
            x0 = bx[0] + gw * (i + 0.18)
            bw = gw * 0.64
            h = (bx[3] - bx[1]) * v / float(vmax * 1.15)
            col = NELEM_COL.get(b.get("n_elements") or 0, "#7f8c8d")
            c.d.rectangle([x0, bx[3] - h, x0 + bw, bx[3]], fill=col,
                          outline="#555")
            c.txt(x0 + bw / 2, bx[3] - h - 7, f(v), size=9, anchor="mb",
                  bold=True)
            c.txt(x0 + bw / 2, bx[3] + 8, b["id"], size=9, anchor="ma",
                  fill="#333")
    data_note(c, [
        "终态种数取 len(final_composition)（4~24 种）；B04 的 142 等更大数字来自 fcnt 历史累计键，"
        "不是终态实际种数。",
        "有效物种 exp(Shannon)：B01/B02/B03 只有一个峰（≈1.0 种），B04/B05 等混合群系产物更分散。",
        "top1 占比=终态数量最多的分子式占比；top1 越高说明产物越专一（趋近单一产物）。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ⑥ 尺寸分布
def chart_size_distribution(a, out):
    ps = present(a)
    bs = biomes(a)
    W, H = 1600, 1500
    c = Chart(
        W, H,
        "⑥ T64 分子尺寸分布：12 群系终态（原子数 × 分子数，对数轴）",
        "每小图=一个群系的终态分子尺寸分布；x=分子原子数，y=分子数（对数）；红条=该群系最大分子尺寸")
    cols, rows = 3, 4
    pw = (W - 100) / cols
    ph = (H - 230) / rows
    for i, b in enumerate(bs):
        r, cc = divmod(i, cols)
        x = 50 + cc * pw
        y = 160 + r * ph
        box = (x, y, x + pw - 18, y + ph - 36)
        c.border(box)
        if not b.get("present"):
            pending_panel(c, box, "未就绪", "%s 结果未就绪" % b["id"])
            continue
        c.txt(box[0] + 8, box[1] + 4, "%s %s" % (b["id"], b["name"]), size=13,
              bold=True)
        dist = {}
        for comp in b.get("composition") or []:
            dist[comp["atoms"]] = dist.get(comp["atoms"], 0) + comp["count"]
        if not dist:
            continue
        sizes = sorted(dist)
        vals = [dist[s] for s in sizes]
        vmax = max(vals)
        vmin = max(1, min(vals))
        bx = (box[0] + 46, box[1] + 26, box[2] - 8, box[3] - 34)
        n = len(sizes)
        mx, my = c.frame(bx, (0, max(1, n)), (1, vmax * 1.3),
                         [j + 0.5 for j in range(n)], log_ticks(vmin, vmax * 1.2),
                         logy=True, xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: fmt_num(v), tick_size=10)
        gw = (bx[2] - bx[0]) / float(max(1, n))
        for j, s in enumerate(sizes):
            v = dist[s]
            h = (bx[3] - bx[1]) * (math.log(max(1, v)) / math.log(vmax * 1.3))
            x0 = bx[0] + gw * (j + 0.15)
            bw = max(2.0, gw * 0.7)
            col = "#c0392b" if s == b.get("max_atoms") else "#2e86de"
            c.d.rectangle([x0, bx[3] - h, x0 + bw, bx[3]], fill=col,
                          outline="#555")
            if n <= 12:
                c.txt(x0 + bw / 2, bx[3] + 6, str(s), size=9, anchor="ma",
                      fill="#333")
        c.txt(bx[2], box[1] + 4, "N=%s · max %d 原子" % (
            fmt_commas(b.get("final_N")), b.get("max_atoms") or 0),
            size=10, anchor="ra", fill="#666")
    data_note(c, [
        "多数群系终态由 3 原子与 2 原子分子主导：退火后 25°C 下双原子/三原子产物是稳定形态；"
        "多元素群系出现 5~39 原子的多元素分子（B08 最大 19 原子，B09/B10/B11 达 39 原子）。",
        "红条=各群系最大分子（B05 17、B08 19、B09/B10/B11 39）；最大分子数量极少但决定“最大尺寸”指标。",
        "x 轴=分子原子数（离散），y 轴=分子数（对数）；小图内 x 轴刻度仅在种数 ≤12 时标出。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ⑦ 聚合度
def chart_polymerization(a, out):
    ps = present(a)
    W, H = 1600, 1120
    c = Chart(
        W, H,
        "⑦ T64 聚合度 vs 元素数：平均/最大原子数随群系元素数变化",
        "点=群系；x=元素数；点大小=N；颜色=元素数；标注群系 id")
    box1 = (90, 190, 780, 860)
    c.border(box1)
    c.txt(box1[0] + 12, box1[1] + 8, "平均分子原子数（聚合度）vs 元素数", size=16,
           bold=True)
    bx = (box1[0] + 74, box1[1] + 54, box1[2] - 30, box1[3] - 56)
    yhi1 = max(3.6, max([b.get("mean_atoms") or 0 for b in ps] + [0]) * 1.18)
    mx, my = c.frame(bx, (2.5, 9.8), (0, yhi1), [3, 4, 5, 6, 7, 8, 9],
                     nice_ticks(0, yhi1, 6),
                     ytick_fmt=lambda v: "%.1f" % v)
    labels = []
    for b in ps:
        X = mx(b.get("n_elements") or 3)
        Y = my(b.get("mean_atoms") or 0)
        r = 6 + 14 * math.sqrt((b.get("final_N") or 0) / float(
            max([x.get("final_N") or 1 for x in ps] or [1])))
        col = NELEM_COL.get(b.get("n_elements") or 0, "#7f8c8d")
        c.d.ellipse([X - r, Y - r, X + r, Y + r], fill=col, outline="#333")
        labels.append((X, Y, b["id"]))
    groups = {}
    for X, Y, bid in labels:
        groups.setdefault((round(X), round(Y)), []).append((X, Y, bid))
    for key in groups:
        for k, (X, Y, bid) in enumerate(sorted(groups[key], key=lambda t: t[2])):
            c.txt(X, Y - 16 - 14 * k, "%s" % bid, size=11, anchor="mb", bold=True)
    box2 = (820, 190, 1510, 860)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "最大分子原子数 vs 元素数", size=16, bold=True)
    bx2 = (box2[0] + 74, box2[1] + 54, box2[2] - 30, box2[3] - 56)
    yhi2 = max(20, max([b.get("max_atoms") or 0 for b in ps] + [0]) * 1.12)
    mx2, my2 = c.frame(bx2, (2.5, 9.8), (0, yhi2), [3, 4, 5, 6, 7, 8, 9],
                       nice_ticks(0, yhi2, 6), ytick_fmt=lambda v: "%d" % v)
    labels2 = []
    for b in ps:
        X = mx2(b.get("n_elements") or 3)
        Y = my2(b.get("max_atoms") or 0)
        col = NELEM_COL.get(b.get("n_elements") or 0, "#7f8c8d")
        c.d.ellipse([X - 7, Y - 7, X + 7, Y + 7], fill=col, outline="#333")
        labels2.append((X, Y, "%s(%d)" % (b["id"], b.get("max_atoms") or 0)))
    groups2 = {}
    for X, Y, lab in labels2:
        groups2.setdefault((round(X), round(Y)), []).append((X, Y, lab))
    for key in groups2:
        for k, (X, Y, lab) in enumerate(sorted(groups2[key], key=lambda t: t[2])):
            c.txt(X, Y - 14 - 13 * k, lab, size=10, anchor="mb", fill="#333")
    box3 = (90, 880, 1510, 1032)
    c.border(box3)
    c.txt(box3[0] + 12, box3[1] + 8, "聚合度结论", size=15, bold=True)
    y = box3[1] + 38
    if ps:
        top_mean = max(ps, key=lambda b: b.get("mean_atoms") or 0)
        low_mean = min(ps, key=lambda b: b.get("mean_atoms") or 0)
        top_max = max(ps, key=lambda b: b.get("max_atoms") or 0)
        e3 = [b for b in ps if (b.get("n_elements") or 0) == 3]
        lines = [
            "平均聚合度最高：%s %s，%.2f 原子/分子（全体均值 %.2f）；最低：%s（%.2f）。"
            % (top_mean["id"], top_mean["name"], top_mean.get("mean_atoms") or 0,
               sum((b.get("mean_atoms") or 0) for b in ps) / float(len(ps)),
               low_mean["id"], low_mean.get("mean_atoms") or 0),
            "最大分子：%s %s 达 %d 原子；元素数 3 的群系（%s）平均 %.2f 原子/分子。"
            % (top_max["id"], top_max["name"], top_max.get("max_atoms") or 0,
               "/".join(b["id"] for b in e3[:4]) if e3 else "-",
               sum((b.get("mean_atoms") or 0) for b in e3) / float(len(e3)) if e3 else 0),
            "聚合度与元素数并不单调：骨架型三价元素（O/P/K）越多、越易形成多原子骨架；"
            "端帽元素（F/A/L）占比高时反而抑制超大分子。",
        ]
    else:
        lines = ["暂无已就绪群系。"]
    for line in lines:
        for s in c.wrap(line, box3[2] - box3[0] - 30, size=13):
            c.txt(box3[0] + 16, y, s, size=13, fill="#333")
            y += 22
    data_note(c, [
        "平均原子数=终态总原子/总分子数；最大原子数取终态分子式中最大的 atoms。",
        "点大小=终态分子总数（相对）；颜色按元素数。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ⑧ 元素利用率
def chart_element_usage(a, out):
    ps = present(a)
    W, H = 1600, 1180
    c = Chart(
        W, H,
        "⑧ T64 元素利用率：9 元素 × 12 群系（已进入化合物的原子占比）",
        "利用率 = 1 - 该元素仍以单质（X2）残留的原子比例；灰色=该群系未投入此元素")
    box = (90, 200, 1560, 980)
    c.border(box)
    gx0, gy0 = box[0] + 130, box[1] + 60
    cw = (box[2] - gx0 - 40) / float(max(1, len(ps)))
    rh = (box[3] - gy0 - 70) / 9.0
    for j, e in enumerate(ORDER):
        c.txt(box[0] + 20, gy0 + rh * (j + 0.5), "%s %s（%d价）" % (
            e, CN[e], {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1,
                       "K": 3, "A": 2, "F": 1}[e]),
            size=12, anchor="lm", fill=ELEMCOL[e], bold=True)
    for i, b in enumerate(ps):
        x = gx0 + cw * i
        c.txt(x + cw / 2, gy0 - 20, b["id"], size=12, anchor="ma", bold=True)
        for j, e in enumerate(ORDER):
            y = gy0 + rh * j
            u = (b.get("usage") or {}).get(e)
            if not u:
                c.d.rectangle([x + 1, y + 1, x + cw - 1, y + rh - 1],
                              fill="#f2f2f2", outline="#eee")
                continue
            t = u["utilization"]
            col = "#%02x%02x%02x" % (int(255 - 190 * t), int(245 - 120 * t),
                                     int(235 - 60 * t))
            c.d.rectangle([x + 1, y + 1, x + cw - 1, y + rh - 1], fill=col,
                          outline="#fff")
            c.txt(x + cw / 2, y + rh / 2, "%d%%" % round(t * 100), size=11,
                  anchor="mm", fill="#111" if t < 0.7 else "#fff", bold=True)
    c.txt(box[0] + 130, box[3] - 40,
          "颜色越深=该元素进入化合物的比例越高；白色/浅色=大量以单质残留（X2 等未被反应消耗）。",
          size=12, fill="#555")
    data_note(c, [
        "利用率按元素单独统计：元素 e 的总原子 = atoms_per_element，单质残留 = e2 分子里的 e 原子数。",
        "三价元素（O/P/K）通常利用率最高（易与一价/二价端接）；一价元素（C/L/F）在双原子单质中"
        "需要成键对象，若被端帽消耗则利用率也高。",
        "B01/B02/B03 三纯族群系所有元素都接近 100% 转化；含未反应单质的群系（如 B05 的 X）利用率低。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ⑨ 相似度/共享
def chart_persistence(a, out):
    cross = a.get("cross") or {}
    sim = (cross.get("similarity") or {})
    ids = sim.get("ids") or []
    vals = sim.get("values") or []
    rows = cross.get("matrix") or []
    W, H = 1600, 1180
    c = Chart(
        W, H,
        "⑨ T64 群系组成相似度（终态组成余弦）+ 物种共享",
        "左=两两余弦相似度（1=组成完全一致，0=无共同分子式）；右=每个群系与其他群系共享的分子式数")
    box = (90, 190, 900, 1020)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "终态组成相似度（12×12）", size=16, bold=True)
    gx0, gy0 = box[0] + 150, box[1] + 70
    cw = (box[2] - gx0 - 30) / float(max(1, len(ids)))
    chh = (box[3] - gy0 - 40) / float(max(1, len(ids)))
    for j, bid in enumerate(ids):
        c.txt(gx0 + cw * (j + 0.5), gy0 - 22, bid, size=11, anchor="ma")
    for i, bid in enumerate(ids):
        c.txt(gx0 - 8, gy0 + chh * (i + 0.5), bid, size=11, anchor="rm")
        for j in range(len(ids)):
            v = vals[i][j] if i < len(vals) and j < len(vals[i]) else 0
            t = max(0.0, min(1.0, float(v)))
            col = "#%02x%02x%02x" % (int(250 - 180 * t), int(250 - 130 * t),
                                     int(250 - 40 * t))
            c.d.rectangle([gx0 + cw * j + 1, gy0 + chh * i + 1,
                           gx0 + cw * (j + 1) - 1, gy0 + chh * (i + 1) - 1],
                          fill=col, outline="#fff")
            if cw >= 44 and i != j:
                c.txt(gx0 + cw * (j + 0.5), gy0 + chh * (i + 0.5), "%.2f" % t,
                      size=9, anchor="mm", fill="#111" if t < 0.6 else "#fff")
    # 右：共享物种
    box2 = (940, 190, 1560, 1020)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "各群系与其他群系共享的终态分子式数", size=16,
           bold=True)
    shared = {}
    for bid in ids:
        n = 0
        for r in rows:
            if (r["counts"].get(bid) or 0) > 0 and r["n_biomes"] > 1:
                n += 1
        shared[bid] = n
    bx = (box2[0] + 90, box2[1] + 60, box2[2] - 120, box2[3] - 50)
    vmax = max([shared.get(bid, 0) for bid in ids] or [1])
    xt = sorted(set([0, vmax // 2, vmax]))
    mx, my = c.frame(bx, (0, max(1, vmax) * 1.2), (0, len(ids)),
                     xt, [i + 0.5 for i in range(len(ids))],
                     xtick_fmt=lambda v: "%d" % v, ytick_fmt=lambda v: "")
    rh = (bx[3] - bx[1]) / float(max(1, len(ids)))
    for i, bid in enumerate(ids):
        v = shared.get(bid, 0)
        y = bx[1] + i * rh
        c.d.rectangle([bx[0], y + rh * 0.15, bx[0] + (bx[2] - bx[0]) * v / float(max(1, vmax) * 1.2),
                       y + rh * 0.85], fill="#2e86de", outline="#555")
        c.txt(bx[0] - 8, y + rh / 2, bid, size=11, anchor="rm")
        c.txt(bx[0] + (bx[2] - bx[0]) * v / float(max(1, vmax) * 1.2) + 8, y + rh / 2,
              "%d 个" % v, size=11, anchor="lm")
    c.txt(box2[0] + 12, 1032,
          "共享分子式 = 同时出现在 ≥2 个群系终态组成的分子式；纯族群系之间几乎零共享（各自形成 OXC/PWL/KAF）。",
          size=11, fill="#555")
    data_note(c, [
        "相似度用终态各分子式的分子数占比向量做余弦；对 12 群系两两计算，对角线=1。",
        "群系越相似，说明其元素组合/投料比导致相同的产物谱；T64 中不同群系基本是不同产物谱（相似度很低）。",
        "B 系列（散素）与聚素/动素群系即使共享元素（如 K/A/F）也因投料比例不同而产物不同。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ⑩ 快照网格
SNAP_TARGETS = [0, 500, 975, 1200, 1574]


def _snap_colmap(sn, topn=12):
    """按面板自身组合频率取 topn 独立着色；其余为灰。返回 (colmap, 主导code, 占比, legend, 组合数)。"""
    pts = sn.get("points") or []
    cnt = {}
    for p in pts:
        code = int(p[2])
        cnt[code] = cnt.get(code, 0) + 1
    order = sorted(cnt, key=lambda k: (-cnt[k], k))
    colmap = {code: SNAP_PAL[i % len(SNAP_PAL)] for i, code in enumerate(order[:topn])}
    lab = sn.get("legend") or {}
    dom = order[0] if order else None
    share = (cnt[dom] / float(len(pts))) if pts and dom is not None else 0.0
    return colmap, dom, share, lab, len(cnt), cnt.get(dom, 0)


def chart_snapshot_grid(a, out):
    ps = present(a)
    # 选 4 个代表群系：元素数最多、最少、以及两个极端
    picks = []
    if ps:
        srt = sorted(ps, key=lambda b: (-(b.get("n_elements") or 0), b["id"]))
        picks.append(srt[0])
        srt2 = sorted(ps, key=lambda b: ((b.get("n_elements") or 0), b["id"]))
        for b in srt2:
            if b["id"] not in [x["id"] for x in picks]:
                picks.append(b)
                break
        for b in srt:
            if b["id"] not in [x["id"] for x in picks]:
                picks.append(b)
            if len(picks) >= 4:
                break
    picks = picks[:4]
    W, H = 1600, 1500
    c = Chart(
        W, H,
        "⑩ T64 2D 快照网格：4 个代表群系 × 5 个时刻（element_bitmask）",
        "点=粒子（元素组合按 bitmask 上色）；t=0 投料 / 500 中退火 / 975 退火结束 / 1200 恒温 / 1574 终态")
    pw = (W - 100) / 5.0
    ph = (H - 300) / 4.0
    for r, b in enumerate(picks):
        raw = load_raw(a, b["id"])
        if not raw:
            for j in range(5):
                x = 50 + j * pw
                y = 160 + r * ph
                pending_panel(c, (x, y, x + pw - 16, y + ph - 34),
                              "无原始数据", "%s result 缺失" % b["id"])
            continue
        snaps = raw.get("snapshots") or []
        # 选最近时刻
        chosen = []
        for tg in SNAP_TARGETS:
            if snaps:
                chosen.append(min(snaps, key=lambda s: abs(
                    int(s.get("t", 0)) - tg)))
            else:
                chosen.append(None)
        for j, sn in enumerate(chosen):
            x = 50 + j * pw
            y = 160 + r * ph
            box = (x, y, x + pw - 16, y + ph - 34)
            c.d.rectangle(box, outline="#333", width=1)
            if sn is None:
                continue
            c.txt(box[0] + 8, box[1] + 4, "%s  t=%s" % (b["id"], sn.get("t")),
                  size=13, bold=True,
                  fill=NELEM_COL.get(b.get("n_elements") or 0, "#333"))
            pts = sn.get("points") or []
            xs = [p[0] for p in pts] or [0]
            ys = [p[1] for p in pts] or [0]
            xlo, xhi = min(xs), max(xs)
            ylo, yhi = min(ys), max(ys)
            if xhi <= xlo:
                xhi = xlo + 1
            if yhi <= ylo:
                yhi = ylo + 1
            px0, py0 = box[0] + 6, box[1] + 26
            px1, py1 = box[2] - 6, box[3] - 22
            colmap, dom, share, lab, ncode, ndom = _snap_colmap(sn)
            for p in pts:
                X = px0 + (p[0] - xlo) / (xhi - xlo) * (px1 - px0)
                Y = py0 + (p[1] - ylo) / (yhi - ylo) * (py1 - py0)
                col = colmap.get(int(p[2]), "#cfcfcf")
                c.d.ellipse([X - 2, Y - 2, X + 2, Y + 2], fill=col)
            c.txt(box[0] + 6, box[3] - 18,
                  "点数 %d · 主导 %s %.0f%%" % (
                      len(pts), (lab.get(str(dom)) or lab.get(dom) or ("组合%d" % dom)) if dom is not None else "-",
                      share * 100),
                  size=9, fill="#666")
    items = [
        (SNAP_PAL[0], "该面板主导组合"),
        (SNAP_PAL[1], "次主导组合"),
        (SNAP_PAL[2], "第 3 组合"),
        ("#cfcfcf", "其他组合（未入 top12）"),
    ]
    c.legend(50, 1378, items, size=11, cols=4, col_w=380, row_h=22)
    data_note(c, [
        "快照从各群系原始 result JSON 读取；每面板 3000 点抽样，颜色=元素组合 bitmask（同 T63 口径）。"
        "t=0 是投料瞬间纯双原子单质；500 离退火中段；975 退火结束 25°C；1200 恒温段中；1574 终态。",
        "颜色按各面板自身组合频率 top12 独立着色（每个群系的主导组合都有自己的颜色）；"
        "灰=该群系其他组合。代表群系选元素数最多者 + 最少者 + 其余；结果未就绪时显示占位面板。",
    ], y=1440)
    return c.save(out)


# ---------------------------------------------------------------- ⑩b 全群系终态快照
def chart_snapshot_biomes(a, out):
    ps = present(a)
    W, H = 1600, 1480
    c = Chart(
        W, H,
        "10b T64 12 群系终态 2D 快照（每群系一子图，t≈1574）",
        "点=粒子（element_bitmask 上色）；每面板 3000 点抽样；颜色按各群系自身 top12 组合独立着色")
    raws = {}
    for b in ps:
        raw = load_raw(a, b["id"])
        if not raw:
            continue
        raws[b["id"]] = raw
    cols, rows = 3, 4
    pw = (W - 100) / float(cols)
    ph = (H - 300) / float(rows)
    for idx, b in enumerate(ps):
        r, cc = divmod(idx, cols)
        x = 50 + cc * pw
        y = 170 + r * ph
        box = (x, y, x + pw - 16, y + ph - 36)
        c.d.rectangle(box, outline="#333", width=1)
        c.txt(box[0] + 8, box[1] + 4, "%s %s" % (b["id"], b["name"]), size=13,
              bold=True, fill=NELEM_COL.get(b.get("n_elements") or 0, "#333"))
        raw = raws.get(b["id"])
        if not raw:
            pending_panel(c, box, "无原始数据", "%s result 缺失" % b["id"])
            continue
        snaps = raw.get("snapshots") or []
        if not snaps:
            pending_panel(c, box, "无快照", "result 内无 snapshots")
            continue
        sn = min(snaps, key=lambda s: abs(int(s.get("t", 0)) - 1574))
        c.txt(box[2] - 6, box[1] + 4, "t=%s" % sn.get("t"), size=10,
              anchor="ra", fill="#666")
        pts = sn.get("points") or []
        xs = [p[0] for p in pts] or [0]
        ys = [p[1] for p in pts] or [0]
        xlo, xhi = min(xs), max(xs)
        ylo, yhi = min(ys), max(ys)
        if xhi <= xlo:
            xhi = xlo + 1
        if yhi <= ylo:
            yhi = ylo + 1
        px0, py0 = box[0] + 6, box[1] + 26
        px1, py1 = box[2] - 6, box[3] - 20
        colmap, dom, share, lab, ncode, ndom = _snap_colmap(sn)
        for p in pts:
            X = px0 + (p[0] - xlo) / (xhi - xlo) * (px1 - px0)
            Y = py0 + (p[1] - ylo) / (yhi - ylo) * (py1 - py0)
            col = colmap.get(int(p[2]), "#cfcfcf")
            c.d.ellipse([X - 2, Y - 2, X + 2, Y + 2], fill=col)
        c.txt(box[0] + 6, box[3] - 16,
              "点数 %d（%d 种组合）· 主导 %s %.0f%%" % (
                  len(pts), ncode,
                  (lab.get(str(dom)) or lab.get(dom) or ("组合%d" % dom)) if dom is not None else "-",
                  share * 100),
              size=9, fill="#666")
    items = [
        (SNAP_PAL[0], "该群系主导组合"),
        (SNAP_PAL[1], "次主导组合"),
        (SNAP_PAL[2], "第 3 组合"),
        ("#cfcfcf", "其他组合（未入 top12）"),
    ]
    c.legend(50, 1390, items, size=11, cols=4, col_w=380, row_h=22)
    data_note(c, [
        "每群系取最接近 t=1574 的快照（结果 JSON snapshots 常以 25 分钟为间隔）；"
        "颜色按各群系自身出现频率 top12 的组合独立着色，灰=该群系其他组合。",
        "对比可见：纯族群系大面积单色（单一三元产物，如 B02 PWL、B03 KAF 主导组合有自己的颜色），"
        "多元素群系颜色更杂（多产物共存）。",
    ], y=1440)
    return c.save(out)


# ---------------------------------------------------------------- ⑪ 反应统计
def chart_reaction_stats(a, out):
    ps = present(a)
    W, H = 1600, 1200
    c = Chart(
        W, H,
        "11 T64 反应判定 / capped / 净事件 / 耗时：12 群系",
        "complete/incomplete/none/capped 为反应判定计数；capped=合并后 >40 原子的弹性截断")
    panels = [
        ("complete", "complete 判定数（对数）", "complete", True),
        ("incomplete", "incomplete 判定数（对数）", "incomplete", True),
        ("capped", "capped 次数", "capped", False),
        ("events_total", "净事件总数", "events_total", False),
    ]
    pw = (W - 120) / 2.0
    ph = (H - 420) / 2.0
    for idx, (field, title, key, logy) in enumerate(panels):
        r, cc = divmod(idx, 2)
        x = 60 + cc * pw
        y = 170 + r * ph
        box = (x, y, x + pw - 40, y + ph - 40)
        c.border(box)
        c.txt(box[0] + 10, box[1] + 6, title, size=15, bold=True)
        if not ps:
            pending_panel(c, box)
            continue
        vals = []
        for b in ps:
            if field == "events_total":
                vals.append(b.get("events_total") or 0)
            else:
                vals.append((b.get("reaction_counts") or {}).get(field, 0))
        vmax = max(vals + [1])
        bx = (box[0] + 70, box[1] + 42, box[2] - 16, box[3] - 52)
        if logy:
            lo = 1
            hi = vmax * 1.3
            mx, my = c.frame(bx, (0, len(ps)), (lo, hi),
                             [i + 0.5 for i in range(len(ps))],
                             log_ticks(lo, hi), logy=True,
                             xtick_fmt=lambda v: "",
                             ytick_fmt=lambda v: fmt_num(v))
        else:
            hi = vmax * 1.15
            mx, my = c.frame(bx, (0, len(ps)), (0, hi),
                             [i + 0.5 for i in range(len(ps))],
                             nice_ticks(0, hi, 4),
                             xtick_fmt=lambda v: "",
                             ytick_fmt=lambda v: fmt_num(v))
        gw = (bx[2] - bx[0]) / float(len(ps))
        for i, b in enumerate(ps):
            v = vals[i]
            x0 = bx[0] + gw * (i + 0.15)
            bw = gw * 0.7
            if logy:
                h = (bx[3] - bx[1]) * math.log(max(1, v) / float(lo)) / math.log(hi / float(lo))
            else:
                h = (bx[3] - bx[1]) * v / float(hi)
            col = NELEM_COL.get(b.get("n_elements") or 0, "#7f8c8d")
            c.d.rectangle([x0, bx[3] - h, x0 + bw, bx[3]], fill=col,
                          outline="#555")
            if v > 0:
                c.txt(x0 + bw / 2, bx[3] - h - 6, fmt_commas(v), size=9,
                      anchor="mb")
            c.txt(x0 + bw / 2, bx[3] + 8, b["id"], size=10, anchor="ma")
    # 底部：耗时与 capped 占比（两列 6 行，避免 12 群系溢出）
    box = (60, 900, 1540, 1110)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "模拟耗时与 capped 占比", size=15, bold=True)
    half = (len(ps) + 1) // 2
    for i, b in enumerate(ps):
        col_i, row_i = divmod(i, half)
        xx = box[0] + 16 + col_i * 730
        yy = box[1] + 42 + row_i * 22
        cap = b.get("capped") or 0
        capsh = b.get("capped_share")
        c.txt(xx, yy, "%s %s：耗时 %s s · capped %s 次（%s%%）· 净事件 %s" % (
            b["id"], b["name"], b.get("runtime_s") if b.get("runtime_s") is not None else "-",
            fmt_commas(cap), pct(capsh, 3) if capsh is not None else "-",
            fmt_commas(b.get("events_total"))), size=11, fill="#333")
    cap_bs = [b["id"] for b in ps if (b.get("capped") or 0) > 0]
    cap_line = ("本次仅 %s 出现 capped，其余群系 capped=0。" % "/".join(cap_bs)) if cap_bs \
        else "本次 12 群系均无 capped 判定。"
    data_note(c, [
        "complete=反应判定完成；incomplete=未完成；none=无反应判定；capped=合并后原子数 >40 被弹性截断。"
        + cap_line,
    ], y=1150)
    return c.save(out)


# ---------------------------------------------------------------- ⑫ 特色群系
def chart_feature_ranking(a, out):
    feats = a.get("features") or {}
    ps = present(a)
    ranking = feats.get("ranking") or []
    axes = feats.get("axes") or []
    W, H = 1600, 1420
    c = Chart(
        W, H,
        "12 T64 特色群系自动评选：综合特色分 + 主导维度",
        "特色分=各维度 z-score 正向平方和；前 3 名优先来自不同主导维度；理由由数据自动生成")
    # 左：全部群系特色分条形
    box = (90, 190, 760, 900)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "12 群系特色分排名", size=16, bold=True)
    # 计算所有群系的分数（含未进前 3 的）
    scores = feats.get("scores") or []
    zmap = {r["id"]: r.get("per_axis_z") or {} for r in scores}
    scmap = {r["id"]: r.get("score") or 0.0 for r in scores}
    allsc = [(b["id"], b["name"], scmap.get(b["id"], 0.0), zmap.get(b["id"], {}))
             for b in ps]
    allsc.sort(key=lambda x: (-x[2], x[0]))
    if not allsc:
        pending_panel(c, box)
    else:
        vals = [x[2] for x in allsc]
        vmax = max(vals + [1])
        bx = (box[0] + 150, box[1] + 56, box[2] - 30, box[3] - 50)
        mx, my = c.frame(bx, (0, vmax * 1.1), (0, len(allsc)),
                         nice_ticks(0, vmax * 1.1, 4),
                         [i + 0.5 for i in range(len(allsc))],
                         xtick_fmt=lambda v: "%.1f" % v, ytick_fmt=lambda v: "")
        rh = (bx[3] - bx[1]) / float(len(allsc))
        top3 = [r["id"] for r in ranking]
        for i, (bid, name, sc, zz) in enumerate(allsc):
            y = bx[1] + i * rh
            col = "#e67e22" if bid in top3 else "#7f8c8d"
            c.d.rectangle([bx[0], y + rh * 0.18,
                           bx[0] + (bx[2] - bx[0]) * max(0.004, sc / (vmax * 1.1)),
                           y + rh * 0.82], fill=col, outline="#555")
            c.txt(bx[0] - 8, y + rh / 2, "%s %s" % (bid, name), size=11,
                  anchor="rm")
            c.txt(bx[0] + (bx[2] - bx[0]) * max(0.004, sc / (vmax * 1.1)) + 6,
                  y + rh / 2, "%.2f" % sc, size=10, anchor="lm")
    # 右上：主导维度 heatmap（12 群系 × 8 轴 z）
    box2 = (800, 190, 1560, 700)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "各维度 z-score（>0 为该维度表现突出）", size=16,
           bold=True)
    ids = [b["id"] for b in ps]
    gx0, gy0 = box2[0] + 96, box2[1] + 66
    cw = (box2[2] - gx0 - 24) / float(max(1, len(axes)))
    rh2 = (box2[3] - gy0 - 20) / float(max(1, len(ids)))
    for j, ax in enumerate(axes):
        c.txt(gx0 + cw * (j + 0.5), gy0 - 22, ax["cn"][:4], size=10,
              anchor="ma", fill="#333")
    for i, bid in enumerate(ids):
        c.txt(gx0 - 8, gy0 + rh2 * (i + 0.5), bid, size=11, anchor="rm")
        zz = zmap.get(bid, {})
        for j, ax in enumerate(axes):
            v = zz.get(ax["key"], 0.0)
            t = max(-2.5, min(2.5, float(v))) / 2.5
            if t >= 0:
                col = "#%02x%02x%02x" % (int(240 - 140 * t), int(240 - 60 * t),
                                         int(240 - 120 * t))
            else:
                col = "#%02x%02x%02x" % (int(215 + 20 * t), int(225 + 15 * t),
                                         int(245))
            c.d.rectangle([gx0 + cw * j + 1, gy0 + rh2 * i + 1,
                           gx0 + cw * (j + 1) - 1, gy0 + rh2 * (i + 1) - 1],
                          fill=col, outline="#fff")
            c.txt(gx0 + cw * (j + 0.5), gy0 + rh2 * (i + 0.5), "%+.1f" % v,
                  size=9, anchor="mm", fill="#111")
    # 下：前 3 特色卡片
    y0 = 720
    cw3 = (W - 120 - 40) / 3.0
    for i, r in enumerate(ranking[:3]):
        x = 60 + i * (cw3 + 20)
        box3 = (x, y0, x + cw3, y0 + 250)
        col = ["#c0392b", "#e67e22", "#8e44ad"][i]
        c.d.rectangle(box3, outline=col, width=3, fill="#fdfdfd")
        c.txt(box3[0] + 14, box3[1] + 10, "第 %d 名  %s %s" % (
            r["rank"], r["id"], r["name"]), size=17, bold=True, fill=col)
        c.txt(box3[0] + 14, box3[1] + 38, "特色分 %.2f · 主导：%s" % (
            r["score"], r["dominant_cn"]), size=12, fill="#555")
        yy = box3[1] + 66
        for reason in r.get("reasons") or []:
            for s in c.wrap("· " + reason, cw3 - 30, size=12):
                c.txt(box3[0] + 14, yy, s, size=12, fill="#222")
                yy += 20
        yy += 6
        c.txt(box3[0] + 14, yy, "final_N %s · 种数 %s · top1 %s%% · 平均 %s 原子 · capped %s" % (
            fmt_commas(r["highlights"]["final_N"]),
            r["highlights"]["distinct_formulas"],
            pct(r["highlights"]["top1_share"], 1),
            r["highlights"]["mean_atoms"],
            fmt_commas(r["highlights"]["capped"])), size=11, fill="#666")
    # 底部：各维度领先群系（覆盖聚合度/九元素/无氧/纯族/高 capped/双三价）
    lbox = (90, 1000, 1510, 1230)
    c.border(lbox)
    c.txt(lbox[0] + 12, lbox[1] + 8, "各维度领先群系（特色候选覆盖）", size=15,
           bold=True)
    pab = feats.get("per_axis_best") or []
    if pab:
        cols, rows = 4, (len(pab) + 3) // 4
        cwid = (lbox[2] - lbox[0] - 40) / float(cols)
        for k, it in enumerate(pab):
            rr, cc2 = divmod(k, cols)
            x = lbox[0] + 20 + cc2 * cwid
            y = lbox[1] + 42 + rr * 54
            c.txt(x, y, it["axis_cn"], size=11, fill="#666")
            c.txt(x, y + 18, "%s %s" % (it["id"], it["name"]), size=12, bold=True,
                  fill="#222")
            c.txt(x, y + 34, "%s %s" % (fmt_num(it["value"]), it["unit"]), size=10,
                  fill="#555")
        cl = feats.get("capped_leaders") or []
        if cl:
            c.txt(lbox[0] + 20, lbox[3] - 24,
                  "capped 领先：" + "、".join("%s %s（%s 次，%s%%）" % (
                      r["id"], r["name"], fmt_commas(r["capped"]),
                      pct(r.get("capped_share"), 3)) for r in cl),
                  size=11, fill="#8e44ad")
        # 其他候选覆盖：无氧 / 双三价 / 纯族专一
        bmap = {b["id"]: b for b in biomes(a)}
        no_ox = [b for b in ps if "O" not in set(bmap.get(b["id"], {}).get("elements") or [])]
        dbl = [b for b in ps if sum(1 for e in set(bmap.get(b["id"], {}).get("elements") or [])
                                    if e in ("O", "P", "K")) >= 2]
        pure = [b for b in ps if (b.get("groups") or {}).get("poly", {}).get("atoms_share", 0) >= 0.99]
        bits = []
        if no_ox:
            bits.append("无氧群系 %s" % "/".join(
                "%s（%s）" % (b["id"], "".join(bmap.get(b["id"], {}).get("elements") or []))
                for b in no_ox[:3]))
        if dbl:
            bits.append("双三价群系 %s" % "/".join(b["id"] for b in dbl[:4]))
        if pure:
            bits.append("纯族专一 %s（top1 99%%+）" % "/".join(b["id"] for b in pure[:4]))
        if bits:
            c.txt(lbox[0] + 20, lbox[3] - 46, "其他候选：" + "；".join(bits), size=11,
                  fill="#555")
    data_note(c, [
        "评分口径：8 个维度（多样性/专一性/平均聚合度/最大尺寸/三价利用率/转化率/恒温活性/新物质）"
        "在本次已就绪群系内做 z-score，正向 z 的平方和=特色分；主导维度=z 最大的维度。",
        "为让“特色”覆盖不同侧面，前 3 名优先选自不同主导维度；同一维度只取最高分者，其余按分数补位。"
        "底部列出各维度第一，便于覆盖聚合度/九元素/无氧/纯族/高 capped 等候选。",
    ], y=1290)
    return c.save(out)


# ---------------------------------------------------------------- 主流程
CHARTS = [
    ("design", "t64_design.png", chart_design),
    ("temperature", "t64_temperature.png", chart_temperature),
    ("composition_matrix", "t64_composition_matrix.png", chart_composition_matrix),
    ("families", "t64_families.png", chart_families),
    ("diversity", "t64_diversity.png", chart_diversity),
    ("size_distribution", "t64_size_distribution.png", chart_size_distribution),
    ("polymerization", "t64_polymerization.png", chart_polymerization),
    ("element_usage", "t64_element_usage.png", chart_element_usage),
    ("persistence", "t64_persistence.png", chart_persistence),
    ("snapshot_grid", "t64_snapshot_grid.png", chart_snapshot_grid),
    ("snapshot_biomes", "t64_snapshot_biomes.png", chart_snapshot_biomes),
    ("reaction_stats", "t64_reaction_stats.png", chart_reaction_stats),
    ("feature_ranking", "t64_feature_ranking.png", chart_feature_ranking),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", default=DEFAULT_ANALYSIS)
    ap.add_argument("--images", default=DEFAULT_IMAGES)
    ap.add_argument("--only", default="", help="逗号分隔图名，如 design,temperature")
    args = ap.parse_args()
    with open(args.analysis, "r", encoding="utf-8") as f:
        a = json.load(f)
    os.makedirs(args.images, exist_ok=True)
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    t0 = __import__("time").time()
    ok = 0
    for name, fn, func in CHARTS:
        if only and name not in only:
            continue
        out = os.path.join(args.images, fn)
        try:
            size = func(a, out)
            print("[ok] %-20s %8d bytes  %s" % (name, size,
                                                os.path.join(args.images, fn)))
            ok += 1
        except Exception as e:
            import traceback
            print("[FAIL] %-18s %s" % (name, e))
            traceback.print_exc()
    print("[done] %d/%d charts ok  %.1fs" % (
        ok, len(CHARTS) if not only else len(only),
        __import__("time").time() - t0))


if __name__ == "__main__":
    main()
