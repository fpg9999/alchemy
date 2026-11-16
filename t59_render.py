# -*- coding: utf-8 -*-
"""t59_render.py —— T59 两阶段实验图表（Pillow 绘制，中文字体 msyh）

读取 t59_analysis.json，生成 11 张图：
  images/t59_loads.png              ① 投料/价数比例对比（A 三价最多、B 随机）
  images/t59_composition.png        ② 两阶段组成演化（A 与 B 上下双面板）
  images/t59_top20_compare.png      ③ A 终态 top20 vs B 终态 top20（并排/变化）
  images/t59_size_distribution.png  ④ 尺寸分布对比（A vs B）
  images/t59_diversity.png          ⑤ 多样性/新物质/最大尺寸（T58/T59A/T59B）
  images/t59_timeline.png           ⑥ 两阶段 timeline（N/mean/max/events/capped）
  images/t59_snapshots.png          ⑦ 2D 快照拼图（A 终态/B 终态/B 中期，bitmask）
  images/t59_top30_structures.png   ⑧ 最终 B 数量前 30 的分子结构图（重点）
  images/t59_top30_bars.png         ⑨ top30 数量/原子数条形 + 元素组成
  images/t59_reaction_capped.png    ⑩ 反应判定/capped 对比
  images/t59_conservation.png       ⑪ 元素/价数守恒与质量平衡

用法：
  python t59_render.py
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_ANALYSIS = os.path.join(BASE, "t59_analysis.json")
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
PAL = ["#2e86de", "#ee5253", "#10ac84", "#f39c12", "#8e44ad", "#16a085",
       "#d35400", "#2c3e50", "#c0392b", "#7f8c8d", "#27ae60", "#e84393",
       "#00acc1", "#795548", "#607d8b", "#f06292"]
TYPECOL = {"complete": "#e74c3c", "incomplete": "#f39c12",
           "none": "#95a5a6", "capped": "#8e44ad"}
GREEN = "#2e8b57"
ORANGE = "#e67e22"
BLUE = "#2e86de"
RED = "#c0392b"
SNAPCOL7 = {0: "#2ecc71", 1: "#f39c12", 2: "#3498db", 3: "#9b59b6",
            4: "#1abc9c", 5: "#e74c3c", 6: "#00acc1"}


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
              grid_color="#e9e9e9", xtick_labels=None):
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

    def border(self, box):
        self.d.rectangle(box, outline="#333", width=2)

    def right_axis(self, box, ylim2, yticks, fmt=None, color="#555", label=None,
                   tick_size=13):
        x0, y0, x1, y1 = box
        lo, hi = float(ylim2[0]), float(ylim2[1])

        def my2(v):
            return y1 - (float(v) - lo) / (hi - lo) * (y1 - y0)

        fmt = fmt or (lambda v: ("%g" % v))
        self.d.line([x1, y0, x1, y1], fill=color, width=1)
        for v in yticks:
            Y = my2(v)
            self.d.line([x1, Y, x1 + 6, Y], fill=color, width=1)
            self.txt(x1 + 10, Y, fmt(v), size=tick_size, anchor="lm", fill=color)
        if label:
            self.rot(x1 + 52, (y0 + y1) / 2, label, size=14, fill=color)
        return my2

    def legend(self, x, y, items, size=13, row_h=25, cols=1, col_w=190,
               swatch=13):
        for i, (col, lab) in enumerate(items):
            r, c = divmod(i, cols)
            X, Y = x + c * col_w, y + r * row_h
            self.d.rectangle([X, Y + 3, X + swatch, Y + 3 + swatch],
                             fill=col, outline="#555", width=1)
            self.txt(X + swatch + 7, Y, lab, size=size)

    def top_temp_axis(self, box, xlim, mx, T0, minutes, nticks=10):
        x0, y0, x1, y1 = box
        y = y0 - 30
        self.d.line([x0, y, x1, y], fill="#666", width=1)
        step = max(1, int(round(minutes / nticks)))
        ts = list(range(0, int(minutes) + 1, step))
        if ts[-1] != int(minutes):
            ts.append(int(minutes))
        for t in ts:
            X = mx(t)
            T = T0 - t
            self.d.line([X, y, X, y - 5], fill="#666", width=1)
            self.txt(X, y - 8, "%g" % T, size=12, anchor="mb", fill="#666")
        self.txt(x1 + 8, y, "温度 T (°C)", size=13, anchor="lm", fill="#666")

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


# ---------------------------------------------------------------- 结构布局/绘制
def layout_mol(atoms, edges, iters=260):
    """返回归一化坐标 [-1,1]^2；树状图用弹簧布局（含同斥力）。"""
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
    # 归一化到 [-1,1]
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sx = max(1e-6, (max(xs) - min(xs)) / 2)
    sy = max(1e-6, (max(ys) - min(ys)) / 2)
    s = max(sx, sy)
    return [((p[0] - cx) / s, (p[1] - cy) / s) for p in pos]


def draw_mol_panel(c, rec, box, header_size=13, node_letter=True, rank=None):
    """在一个面板内绘制分子结构 + 标注。"""
    x0, y0, x1, y1 = box
    st = rec.get("structure") or {}
    atoms = st.get("atoms") or []
    edges = st.get("edges") or []
    n = len(atoms)
    # 头部：公式
    formula = rec.get("formula") or ""
    zh = rec.get("zh") or ""
    c.txt((x0 + x1) / 2, y0 + 4, formula, size=header_size, bold=True,
          anchor="ma", fill="#111")
    # 绘图区
    pad = 8
    bx0, by0, bx1, by1 = x0 + pad, y0 + 26, x1 - pad, y1 - 44
    bw, bh = bx1 - bx0, by1 - by0
    c.d.rectangle([bx0, by0, bx1, by1], fill="#fbfbfb", outline="#e0e0e0")
    if n and edges is not None:
        pos = layout_mol(atoms, edges)
        rad = max(3.0, min(11.0, 0.5 * min(bw, bh) / (math.sqrt(n) * 1.9)))
        if n > 24:
            rad = max(2.6, min(5.5, rad))
        pts = [(bx0 + bw / 2 + px * (bw / 2 - rad - 3),
                by0 + bh / 2 + py * (bh / 2 - rad - 3)) for px, py in pos]
        for e in edges:
            i, j, m = int(e[0]), int(e[1]), int(e[2])
            col = BONDCOL.get(m, "#888")
            wdt = 1 if m == 1 else (2 if m == 2 else 2)
            c.d.line([pts[i], pts[j]], fill=col, width=wdt)
        for i, e in enumerate(atoms):
            X, Y = pts[i]
            c.d.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                        fill=ELEMCOL.get(e, "#ccc"), outline="#333",
                        width=1)
            if node_letter and rad >= 6:
                c.txt(X, Y - 1, e, size=max(8, int(rad * 1.5)), bold=True,
                      anchor="mm", fill="#111")
    else:
        c.txt((bx0 + bx1) / 2, (by0 + by1) / 2, "（无结构数据）", size=12,
              anchor="mm", fill="#888")
    # 底部标注
    line1 = "×%s · %d 原子" % (fmt_commas(rec.get("count")),
                              rec.get("atoms") or n)
    c.txt((x0 + x1) / 2, y1 - 34, line1, size=11, anchor="ma", fill="#333")
    extra = []
    if rank is not None:
        extra.append("#%d" % rank)
    if rec.get("f_stable"):
        extra.append("F稳定")
    if rec.get("in_catalog"):
        extra.append("目录内")
    if extra:
        c.txt((x0 + x1) / 2, y1 - 18, " · ".join(extra), size=10, anchor="ma",
              fill="#666")


# ---------------------------------------------------------------- ① 投料
def chart_loads(a, out):
    loads = a.get("loads") or {}
    A = loads.get("batchA") or {}
    B = loads.get("batchB") or {}
    W, H = 1600, 1080
    c = Chart(W, H,
              "① 投料设计：batchA 三价最多/一价最少（120 种），batchB 随机 120 种",
              "A 投料 13,174 分子 / 150,103 原子；B 投料 6,895 分子 / 80,030 原子；"
              "九元素全覆盖；数量∝1/面积")
    # 左上：价数原子数对比
    box = (90, 165, 790, 520)
    cats = ["3 价", "2 价", "1 价"]
    va = A.get("valence_atoms") or {}
    vb = B.get("valence_atoms") or {}
    vals = [[va.get("v3", 0), va.get("v2", 0), va.get("v1", 0)],
            [vb.get("v3", 0), vb.get("v2", 0), vb.get("v1", 0)]]
    ymax = max(max(vals[0]), max(vals[1])) * 1.25
    xt = [0.5, 1.5, 2.5]
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (0, 3), (0, ymax), xt, yt,
                     xtick_labels=cats, ytick_fmt=fmt_commas)
    bw = 0.22
    for gi, (valset, colr, off) in enumerate(((vals[0], BLUE, -bw),
                                              (vals[1], ORANGE, bw))):
        for i, val in enumerate(valset):
            X = mx(i + 0.5) + off * (mx(1.5) - mx(0.5))
            Y = my(val)
            c.d.rectangle([X - 28, Y, X + 28, box[3]], fill=colr,
                          outline="#333", width=1)
            c.txt(X, Y - 5, fmt_num(val), size=11, anchor="mb", fill="#333")
    c.rot(box[0] - 56, (box[1] + box[3]) / 2, "原子数", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 38, "价类（原子数）", size=15, anchor="ma")
    c.legend(box[0] + 16, box[1] - 38,
             [(BLUE, "batchA（三价最多）"), (ORANGE, "batchB（随机）")],
             size=13, row_h=24, cols=2, col_w=190)

    # 右上：价数占比
    box2 = (870, 165, 1560, 420)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 14, box2[1] + 12, "价数原子占比（3价 / 2价 / 1价）", size=16,
          bold=True)
    y = box2[1] + 50
    for tag, sh in (("batchA", A.get("valence_shares") or []),
                    ("batchB", B.get("valence_shares") or [])):
        total = sum(sh) or 1
        x = box2[0] + 120
        c.txt(box2[0] + 14, y + 6, tag, size=14, bold=True)
        for i, (name, colr) in enumerate((("3价", "#c0392b"), ("2价", BLUE),
                                          ("1价", "#10ac84"))):
            w = (box2[2] - box2[0] - 150) * (sh[i] if i < len(sh) else 0) / total
            c.d.rectangle([x, y, x + w, y + 26], fill=colr, outline="#333")
            if w > 50:
                c.txt(x + 6, y + 4, "%s %.1f%%" % (name, 100.0 * sh[i] / total),
                      size=12, fill="#fff")
            x += w
        y += 42
    c.txt(box2[0] + 14, y + 8,
          "A：78,512 : 39,419 : 32,172 = 52.3%% : 26.3%% : 21.4%%（3>2>1 严格满足）",
          size=13, fill="#333")
    c.txt(box2[0] + 14, y + 34,
          "B（随机）：37,308 : 26,458 : 16,264 = 46.6%% : 33.1%% : 20.3%%",
          size=13, fill="#555")

    # 左下：元素原子数（A vs B）
    box3 = (90, 560, 1140, 900)
    elA = A.get("element_atoms") or {}
    elB = B.get("element_atoms") or {}
    els = [e for e in ORDER if elA.get(e, 0) or elB.get(e, 0)]
    x0, x1 = box3[0] + 70, box3[2] - 20
    y0, y1 = box3[1] + 40, box3[3] - 70
    emax = max([max(elA.get(e, 0), elB.get(e, 0)) for e in els] + [1]) * 1.2
    for v in nice_ticks(0, emax, 4):
        Y = y1 - v / emax * (y1 - y0)
        c.d.line([x0, Y, x1, Y], fill="#eee", width=1)
        c.txt(x0 - 8, Y, fmt_num(v), size=12, anchor="rm")
    bw2 = (x1 - x0) / len(els) * 0.26
    for i, e in enumerate(els):
        X = x0 + (x1 - x0) / len(els) * (i + 0.5)
        for val, colr, off in ((elA.get(e, 0), BLUE, -bw2),
                               (elB.get(e, 0), ORANGE, bw2)):
            Y = y1 - val / emax * (y1 - y0)
            c.d.rectangle([X + off - bw2 / 2, Y, X + off + bw2 / 2, y1],
                          fill=colr, outline="#333", width=1)
        c.txt(X, y1 + 10, "%s %s" % (e, CN.get(e, "")), size=13, anchor="ma")
    c.rot(box3[0] - 52, (box3[1] + box3[3]) / 2, "原子数", size=14)
    c.txt((box3[0] + box3[2]) / 2, box3[1] + 8, "九元素原子数：batchA vs batchB",
          size=16, bold=True)

    # 右下：汇总
    box4 = (1170, 560, 1560, 900)
    c.d.rectangle(box4, outline="#333", width=2)
    c.txt(box4[0] + 14, box4[1] + 12, "投料汇总", size=16, bold=True)
    lines = [
        "batchA：%d 种 / %s 分子 / %s 原子"
        % (A.get("n_species"), fmt_commas(A.get("molecules")),
           fmt_commas(A.get("atoms"))),
        "　　　　（平均 %.2f 原子/分子）" % (A.get("mean_atoms") or 0),
        "batchB：%d 种 / %s 分子 / %s 原子"
        % (B.get("n_species"), fmt_commas(B.get("molecules")),
           fmt_commas(B.get("atoms"))),
        "　　　　（平均 %.2f 原子/分子）" % (B.get("mean_atoms") or 0),
        "两批合计：%s 分子 / %s 原子"
        % (fmt_commas((A.get("molecules") or 0) + (B.get("molecules") or 0)),
           fmt_commas((A.get("atoms") or 0) + (B.get("atoms") or 0))),
        "A 三价最多/一价最少 = %s" % ("满足" if A.get("strict_order_3gt2gt1")
                                     else "未满足"),
        "九元素：%s" % " ".join(A.get("elements_covered") or []),
        "环境 L=60000（比 T58 的 400000 面积缩小 44 倍）",
        "MAX_REACTION_ATOMS=40（允许 39/40 原子巨型分子）",
    ]
    y = box4[1] + 46
    for s in lines:
        for seg in c.wrap(s, box4[2] - box4[0] - 28, size=13):
            c.txt(box4[0] + 14, y, seg, size=13, fill="#222")
            y += 23
        y += 4
    return c.save(out)


# ---------------------------------------------------------------- ② 组成演化
def _stack_panel(c, box, series, order, minutes, T0, title=None):
    totals = [r.get("total") or 0 for r in series]
    ymax = max(totals + [1]) * 1.1
    xt = nice_ticks(0, minutes, 8)
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (0, minutes), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: fmt_commas(v))
    layers = [(f, [r.get("top_counts", {}).get(f, 0) for r in series])
              for f in order]
    layers.append(("其它", [r.get("other", 0) for r in series]))
    n = len(series)
    bottom = [0.0] * n
    for i, (name, vals) in enumerate(layers):
        tops = [bottom[j] + vals[j] for j in range(n)]
        pts = [(mx(series[j]["t"]), my(tops[j])) for j in range(n)]
        pts += [(mx(series[j]["t"]), my(bottom[j])) for j in range(n - 1, -1, -1)]
        c.d.polygon(pts, fill=PAL[i % len(PAL)])
        bottom = tops
    c.border(box)
    c.rot(box[0] - 56, (box[1] + box[3]) / 2, "分子数", size=14)
    if title:
        c.txt(box[0] + 10, box[1] + 8, title, size=15, bold=True,
              fill="#111", anchor="la")
    return layers, mx, my


def chart_composition(a, out):
    A = a.get("phaseA") or {}
    B = a.get("phaseB") or {}
    W, H = 1600, 980
    c = Chart(W, H,
              "② 两阶段组成演化：A（120 种投料）→ 43 种终态；整理后 + batchB 复热 → 67 种终态",
              "左右两阶段独立时间轴（各 0→1000 分钟，1000→0°C）；堆叠 = top10 分子式 + 其它")
    for idx, (P, tag) in enumerate(((A, "A"), (B, "B"))):
        series = P.get("series") or []
        order = P.get("stack_order") or []
        if not series:
            continue
        px = 40 + idx * 780
        box = (px + 70, 215, px + 730, 640)
        minutes = (P.get("config") or {}).get("minutes") or 1000
        T0 = (P.get("config") or {}).get("T0") or 1000
        layers, mx, my = _stack_panel(c, box, series, order, minutes, T0,
                                      "phase %s（终态 %d 种）"
                                      % (tag, P.get("final_distinct_formulas") or 0))
        c.top_temp_axis(box, (0, minutes), mx, T0, minutes)
        c.txt((box[0] + box[2]) / 2, box[3] + 42, "时间 t（分钟）", size=15,
              anchor="ma")
        # 图例
        items = []
        for i, f in enumerate(order):
            items.append((PAL[i % len(PAL)], f))
        items.append((PAL[len(order) % len(PAL)], "其它"))
        c.legend(px + 40, 720, items, size=11, row_h=21, cols=3, col_w=240)
    data_note(c, [
        "A 终态 27,431 分子 / 43 种（CF 9,349、O2XP2WK2A 6,204、L2 3,733、"
        "O4X2P5W2K3A2 2,110、LF 2,089、OCPKA 1,756 …）；B 终态 38,609 分子 / 67 种"
        "（CF 12,131、O2XP2WK2A2 6,615、OXCPWK 5,152、L2 4,981、LF 4,435、"
        "O4X2P5W2K3A2 4,254 …）。",
        "两阶段都出现 39/40 原子巨型分子（A 33 个、B 56 个），是 max_reaction_atoms=40 允许的 F 产物。",
    ], y=880)
    return c.save(out)


# ---------------------------------------------------------------- ③ top20 对比
def chart_top20_compare(a, out):
    cmp_ = a.get("compare") or {}
    rows = cmp_.get("top20_union") or []
    if not rows:
        raise RuntimeError("top20_union 为空")
    W, H = 1600, 1320
    c = Chart(W, H,
              "③ A 终态 top20 vs B 终态 top20：O2XP2WK2A2/OXCPWK/O3XP4WK3A 崛起，"
              "OCPKA/O3XP3WK2A 退出",
              "按 B 终态数量排序：实心=该阶段 top20 条目；数值为终态分子数；"
              "后 19 位多为 39/40 原子巨型分子（数量 1~2）")
    box = (560, 170, 1520, 1120)
    vmax = max([max(r["A_count"], r["B_count"]) for r in rows] + [1]) * 2.2
    x0, y0, x1, y1 = box
    logmin, logmax = 0.0, math.log10(max(vmax, 10))

    def mx(v):
        v = max(1.0, float(v))
        return max(x0 + 2.0, x0 + (math.log10(v) - logmin) /
                   (logmax - logmin) * (x1 - x0))

    yt = [v for v in (1, 10, 100, 1000, 10000) if v <= vmax] or [1, 10]
    for v in yt:
        X = mx(v)
        c.d.line([X, y0, X, y1], fill="#e9e9e9", width=1)
        c.d.line([X, y1, X, y1 + 6], fill="#333", width=1)
        c.txt(X, y1 + 10, "%g" % v, size=13, anchor="ma")
    c.d.rectangle(box, outline="#333", width=2)
    c.txt((x0 + x1) / 2, y1 + 42, "终态分子数（对数轴）", size=16, anchor="ma")
    n = len(rows)
    row_h = (y1 - y0) / max(1, n)
    for i, r in enumerate(rows):
        cy = y0 + row_h * (i + 0.5)
        label = "%s  %s（%s 原子）%s" % (
            r["formula"], r.get("zh") or "",
            r.get("B_atoms") or r.get("A_atoms") or "?",
            "（A-only）" if (r.get("B_count") or 0) == 0 else "")
        c.txt(x0 - 14, cy, label, size=11, anchor="rm",
              bold=(r.get("B_rank") is not None))
        bar_h = min(row_h * 0.36, 20)
        ya = cy - bar_h - 1
        yb = cy + 1
        if r["A_count"] > 0:
            c.d.rectangle([x0, ya, mx(r["A_count"]), ya + bar_h], fill=BLUE,
                          outline="#333")
        if r["B_count"] > 0:
            c.d.rectangle([x0, yb, mx(r["B_count"]), yb + bar_h], fill=ORANGE,
                          outline="#333")
        if r["B_count"] > 0:
            tag = ""
            if r["formula"] in (cmp_.get("new_in_B_top20") or []):
                tag = "  NEW"
            c.txt(mx(r["B_count"]) + 6, yb + 1, fmt_commas(r["B_count"]) + tag,
                  size=10, anchor="lm", fill="#333")
    c.legend(box[0] + 14, 150,
             [(BLUE, "A 终态"), (ORANGE, "B 终态"),
              ("#c0392b", "NEW = B 新进 top20")],
             size=13, row_h=24, cols=3, col_w=210)
    data_note(c, [
        "B 新进 top20：%s；A top20 退出：%s。"
        % ("、".join(cmp_.get("new_in_B_top20") or []),
           "、".join(cmp_.get("dropped_from_A_top20") or [])),
        "A 的巨型分子（39/40 原子）在 B 中大多仍存在（数量 1~2），但被新主导分子挤出 top20。",
    ], y=1180)
    return c.save(out)


# ---------------------------------------------------------------- ④ 尺寸分布
def chart_size_distribution(a, out):
    A = a.get("phaseA") or {}
    B = a.get("phaseB") or {}
    W, H = 1600, 1020
    c = Chart(W, H,
              "④ 尺寸分布对比：A vs B（终态）",
              "尺寸=分子原子数；A 双峰 2 原子/9 原子/18 原子为主；B 主导 2、6、10、18 原子，"
              "并保留 39/40 原子巨型分子")
    da = {int(d["atoms"]): d["molecules"] for d in (A.get("size_distribution") or [])}
    db = {int(d["atoms"]): d["molecules"] for d in (B.get("size_distribution") or [])}
    xs = sorted(set(da) | set(db))
    box = (110, 175, 1450, 700)
    ymax = max(list(da.values()) + list(db.values()) + [1]) * 1.6
    yt = [1, 10, 100, 1000, 10000]
    v = 100000
    while v <= ymax:
        yt.append(v)
        v *= 10
    mx, my = c.frame(box, (0.5, max(xs) + 0.5), (1, ymax), xs, yt, logy=True,
                     ytick_fmt=lambda v: "%g" % v)
    bw = (mx(2) - mx(1)) * 0.34
    for x in xs:
        for val, colr, off in ((da.get(x, 0), BLUE, -bw / 2),
                               (db.get(x, 0), ORANGE, bw / 2)):
            if val <= 0:
                continue
            X = mx(x) + off
            Y = my(val)
            c.d.rectangle([X - bw / 2, Y, X + bw / 2, box[3]], fill=colr,
                          outline="#333", width=1)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "分子数（对数）", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 38, "分子原子数", size=15, anchor="ma")
    c.legend(box[0] + 16, box[1] + 12,
             [(BLUE, "A 终态"), (ORANGE, "B 终态")],
             size=14, row_h=24, cols=2, col_w=180)
    # 关键点标注
    notes = [
        ("2 原子", da.get(2, 0), db.get(2, 0)),
        ("9 原子", da.get(9, 0), db.get(9, 0)),
        ("18 原子", da.get(18, 0), db.get(18, 0)),
        ("39/40", (da.get(39, 0) + da.get(40, 0)),
         (db.get(39, 0) + db.get(40, 0))),
    ]
    x = 150
    for lab, va, vb in notes:
        c.txt(x, 780, lab, size=14, bold=True)
        c.txt(x, 802, "A %s / B %s" % (fmt_commas(va), fmt_commas(vb)),
              size=13, fill="#333")
        x += 320
    data_note(c, [
        "A：27,431 分子 / 43 种；平均 %.2f、最大 40；2 原子 16,011、5 原子 1,756、"
        "9 原子 6,204、18 原子 2,110、39/40 原子 33（+37 原子 1）。" % (A.get("final_mean_atoms") or 0),
        "B：38,609 分子 / 67 种；平均 %.2f、最大 40；2 原子 21,644、6 原子 5,152、"
        "10 原子 6,615、18 原子 4,254、39/40 原子 56。" % (B.get("final_mean_atoms") or 0),
    ], y=940)
    return c.save(out)


# ---------------------------------------------------------------- ⑤ 多样性
def chart_diversity(a, out):
    hist = (a.get("history") or {}).get("table") or []
    W, H = 1600, 1040
    c = Chart(W, H,
              "⑤ 多样性/新物质/最大尺寸对比：T58 vs T59A vs T59B",
              "T58（L=400000，cap20）vs T59A（L=60000，cap40，120 种投料）vs "
              "T59B（整理底物+120 种，复热）")
    panels = [
        ("初始分子数", lambda t: t.get("molecules"), fmt_commas, False, 1000),
        ("初始原子数", lambda t: t.get("atoms"), fmt_commas, True, 1000),
        ("终态分子式数", lambda t: t.get("distinct"), fmt_commas, False, 0),
        ("新物质数", lambda t: t.get("new_substances"), fmt_commas, False, 0),
        ("终态最大原子数", lambda t: t.get("max_atoms"), lambda v: "%d" % v, False, 0),
        ("终态分子数", lambda t: t.get("final_N"), fmt_commas, False, 0),
    ]
    cols = ["#95a5a6", "#f39c12", "#2e86de"]
    pw, ph = 720, 250
    x0s = [60, 840]
    y0s = [110, 380, 650]
    for idx, (title, getter, fmt, logy, ymin) in enumerate(panels):
        px = x0s[idx % 2]
        py = y0s[idx // 2]
        box = (px + 100, py + 42, px + pw - 30, py + ph - 34)
        vals = [getter(t) or 0 for t in hist]
        vmax = max(vals + [1]) * 1.3
        c.txt(px + 16, py + 4, "%s %s" % ("①②③④⑤⑥"[idx], title), size=18, bold=True)
        if logy:
            yt = [v for v in (1000, 10000, 100000, 1000000) if v <= vmax] or [1, 10]
            y_lo = max(1000, min(vals + [1000]))
        else:
            yt = nice_ticks(ymin, vmax, 4)
            y_lo = ymin
        nn = len(hist)
        mx, my = c.frame(box, (0, nn), (y_lo, vmax),
                         [i + 0.5 for i in range(nn)], yt,
                         xtick_labels=[h["name"] for h in hist],
                         ytick_fmt=fmt, logy=logy)
        bw = (box[2] - box[0]) / nn * 0.42
        for i, t in enumerate(hist):
            X = box[0] + (box[2] - box[0]) / nn * (i + 0.5)
            val = vals[i]
            Y = my(max(val, y_lo if logy else ymin))
            c.d.rectangle([X - bw / 2, Y, X + bw / 2, box[3]],
                          fill=cols[i % len(cols)], outline="#333", width=1)
            c.txt(X, Y - 5, fmt(val), size=13, anchor="mb", bold=True)
    data_note(c, [
        "T59A：终态 27,431 分子/43 种/新物质 5,597/最大 40；T59B：38,609/67 种/2,504/40。"
        "T58 对比：15,823 分子/937 种/1,927 新物质/最大 20（cap20，L 大 44 倍）。",
        "T59 区域更小（L=60000）、碰撞更频繁，退火更充分 → 终态分子式数从 T58 的 937 降到 43/67；"
        "但允许 40 原子反应，保留 39/40 原子巨型分子。",
    ], y=940)
    return c.save(out)


# ---------------------------------------------------------------- ⑥ timeline
def chart_timeline(a, out):
    A = (a.get("phaseA") or {}).get("timeline") or []
    B = (a.get("phaseB") or {}).get("timeline") or []
    if not A or not B:
        raise RuntimeError("timeline 为空")
    W, H = 1600, 1120
    c = Chart(W, H,
              "⑥ 两阶段 timeline：A（0–1000 分钟）→ 整理/复热/二次投料 → B（1000–2000）",
              "x=0–1000 A 阶段；x=1000–2000 B 阶段（时间平移 1000）；"
              "竖线=整理归档 + 温度重置 + batchB 投料")
    TA = [dict(r, x=r["t"]) for r in A]
    TB = [dict(r, x=r["t"] + 1000) for r in B]
    allrows = TA + TB
    xt = list(range(0, 2001, 200))
    # 上：N
    box = (120, 170, 1470, 400)
    ymax = max(r.get("N") or 0 for r in allrows) * 1.12
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (0, 2000), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: fmt_commas(v))
    c.line([(mx(r["x"]), my(r.get("N") or 0)) for r in TA], fill=BLUE, width=3)
    c.line([(mx(r["x"]), my(r.get("N") or 0)) for r in TB], fill=ORANGE, width=3)
    c.dashed((mx(1000), box[1]), (mx(1000), box[3]), fill=RED, width=2)
    c.txt_bg(mx(1000) + 8, box[1] + 10,
             "整理归档 27,431 分子 → 复热 1000°C → 加入 batchB 6,895 分子",
             size=13, fill=RED)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "粒子数 N", size=14)
    c.legend(box[0] + 14, box[1] - 36, [(BLUE, "phase A"), (ORANGE, "phase B")],
             size=13, row_h=24, cols=2, col_w=150)
    # 中：mean/max 原子数
    box2 = (120, 470, 1470, 700)
    ymax2 = max(r.get("max_atoms") or 0 for r in allrows) * 1.15
    yt2 = nice_ticks(0, ymax2, 5)
    mx2, my2 = c.frame(box2, (0, 2000), (0, ymax2), xt, yt2)
    c.line([(mx2(r["x"]), my2(r.get("max_atoms") or 0)) for r in allrows],
           fill="#c0392b", width=2)
    c.line([(mx2(r["x"]), my2(r.get("mean_atoms") or 0)) for r in allrows],
           fill="#10ac84", width=3)
    c.dashed((mx2(1000), box2[1]), (mx2(1000), box2[3]), fill=RED, width=2)
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "原子数", size=14)
    c.legend(box2[0] + 14, box2[1] - 32,
             [("#10ac84", "平均原子数"), ("#c0392b", "最大原子数")],
             size=13, row_h=24, cols=2, col_w=180)
    # 下：events/capped 累计
    box3 = (120, 770, 1470, 1000)
    ymax3 = max([r.get("events_total") or 0 for r in allrows] +
                [r.get("capped_cum") or 0 for r in allrows] + [1]) * 1.15
    yt3 = nice_ticks(0, ymax3, 5)
    mx3, my3 = c.frame(box3, (0, 2000), (0, ymax3), xt, yt3,
                       ytick_fmt=lambda v: fmt_num(v))
    c.line([(mx3(r["x"]), my3(r.get("events_total") or 0)) for r in allrows],
           fill="#8e44ad", width=3)
    c.line([(mx3(r["x"]), my3(r.get("capped_cum") or 0)) for r in allrows],
           fill="#95a5a6", width=2)
    c.dashed((mx3(1000), box3[1]), (mx3(1000), box3[3]), fill=RED, width=2)
    c.rot(box3[0] - 58, (box3[1] + box3[3]) / 2, "累计事件数", size=14)
    c.txt((box3[0] + box3[2]) / 2, box3[3] + 36, "时间 t（分钟，两阶段拼接）",
          size=15, anchor="ma")
    c.legend(box3[0] + 14, box3[1] + 10,
             [("#8e44ad", "净变化事件（累计）"), ("#95a5a6", "capped（累计）")],
             size=13, row_h=24, cols=2, col_w=230)
    data_note(c, [
        "A：净事件 174,549、capped 32,985（占判定 0.40%）、终态 27,431 分子/43 种；"
        "B：净事件 206,740、capped 94,949（0.44%）、终态 38,609 分子/67 种。",
        "B 起点 = A 终态（27,431 分子 / 43 种结构）+ batchB（6,895 分子 / 80,030 原子），"
        "温度重置 1000°C，再冷到 0°C；因此 B 的 N/事件曲线在 t=1000 处重新起跳。",
    ], y=1060)
    return c.save(out)


# ---------------------------------------------------------------- ⑦ 快照
def _pick_snapshots(snaps, targets, max_n=8):
    snaps = [s for s in snaps if s.get("points")]
    if not snaps:
        return []
    used, out = set(), []
    for tg in targets:
        cand = min((s for s in snaps if id(s) not in used),
                   key=lambda s: abs((s.get("t") or 0) - tg), default=None)
        if cand is not None:
            used.add(id(cand))
            out.append(cand)
    out.sort(key=lambda s: s.get("t") or 0)
    return out[:max_n]


def chart_snapshots(a, out):
    raw = a.get("_raw") or {}
    A = raw.get("A") or {}
    B = raw.get("B") or {}
    sA = [s for s in (A.get("snapshots") or []) if s.get("points")]
    sB = [s for s in (B.get("snapshots") or []) if s.get("points")]
    picks = []
    for tag, snaps, tgs in (("A", sA, [0, 500, 1000]),
                            ("B", sB, [0, 500, 1000])):
        for s in _pick_snapshots(snaps, tgs, 3):
            picks.append((tag, s))
    if not picks:
        raise RuntimeError("没有可用 snapshots")
    L = (A.get("config") or {}).get("L") or 60000
    freq = {}
    for _, s in picks:
        for p in s.get("points") or []:
            if len(p) >= 3:
                freq[p[2]] = freq.get(p[2], 0) + 1
    top_codes = [c for c, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:12]]
    palette = {code: PAL[i % len(PAL)] for i, code in enumerate(top_codes)}
    cols, rows = 3, 2
    pw, ph = 500, 430
    W = cols * pw + 40
    H = 170 + rows * ph + 90
    c = Chart(W, H,
              "⑦ 2D 快照：A（上排）与 B（下排）在 t=0/500/995 的粒子分布（element_bitmask）",
              "颜色=元素组合（top12 组合）；A 末帧（t=995）与 B t=0 是同一份整理底物（复热重装）")
    for i, (tag, s) in enumerate(picks):
        r, col = divmod(i, cols)
        x0 = 30 + col * pw
        y0 = 130 + r * ph
        box = (x0, y0, x0 + pw - 18, y0 + ph - 60)
        c.d.rectangle(box, fill="#fbfbfb", outline="#ccc", width=1)
        pts = s.get("points") or []
        bw, bh = box[2] - box[0], box[3] - box[1]
        rad = 2.3 if len(pts) > 1500 else 2.8
        for p in pts:
            if len(p) < 3:
                continue
            px = box[0] + max(0.0, min(1.0, p[0] / L)) * bw
            py = box[3] - max(0.0, min(1.0, p[1] / L)) * bh
            c.d.ellipse([px - rad, py - rad, px + rad, py + rad],
                        fill=palette.get(p[2], "#b0bec5"))
        inf = [box[0] + 5, box[1] + 5, box[0] + 230, box[1] + 52]
        c.d.rectangle(inf, fill="#ffffff", outline="#d9d9d9")
        T0 = 1000
        T = T0 - (s.get("t") or 0)
        c.txt(inf[0] + 8, inf[1] + 5, "%s 阶段  t=%s  T=%s"
              % (tag, s.get("t"), T), size=14, bold=True, fill="#111")
        c.txt(inf[0] + 8, inf[1] + 27, "点数 %d（抽样）" % len(pts), size=12,
              fill="#555")
        c.d.rectangle(box, outline="#999", width=1)
    items = []
    for code in top_codes:
        lab = None
        for _, s in picks:
            leg = s.get("legend") or {}
            if str(code) in leg:
                lab = leg[str(code)]
                break
        items.append((palette[code], "%s %.1f%%" % (lab or code,
                                                   100.0 * freq[code] /
                                                   max(1, sum(freq.values())))))
    c.txt(36, H - 84, "元素组合图例（top %d，按 6 帧总频率）" % len(items),
          size=13, bold=True)
    c.legend(36, H - 58, items, size=12, row_h=22, cols=6, col_w=240)
    return c.save(out)


# ---------------------------------------------------------------- ⑧ top30 结构
def chart_top30_structures(a, out):
    structures = ((a.get("structures") or {}).get("top30")) or []
    if not structures:
        raise RuntimeError("structures.top30 为空")
    reg = [s for s in structures if (s.get("atoms") or 0) < 39]
    giant = [s for s in structures if (s.get("atoms") or 0) >= 39]
    W = 1600
    # 顶部：前 12（4 列 × 3 行，大面板）；底部：巨型/剩余（6 列 × 3 行，小面板）
    top = structures[:12]
    rest = structures[12:]
    top_cols, top_rows = 4, 3
    top_pw, top_ph = 390, 335
    bot_cols, bot_rows = 6, 3
    bot_pw, bot_ph = 260, 300
    top_y = 160
    bot_y = top_y + top_rows * (top_ph + 12) + 70
    H = bot_y + bot_rows * (bot_ph + 12) + 130
    c = Chart(W, H,
              "⑧ 最终 B 数量前 30 的分子结构（前 12 大面板 + 后 18 巨型分子 6 列网格）",
              "节点=原子（9 元素配色）；键按多重键着色（1 灰 / 2 深蓝 / 3 红）；"
              "布局为弹簧/环形自动排布；全部为 F 稳定单产物")
    # 元素图例
    items = [(ELEMCOL[e], "%s %s" % (e, CN[e])) for e in ORDER]
    c.legend(40, 96, items, size=13, row_h=24, cols=9, col_w=160)
    c.legend(1120, 96, [(BONDCOL[1], "单键"), (BONDCOL[2], "双键"),
                        (BONDCOL[3], "三键")], size=13, row_h=24, cols=3,
             col_w=130)
    # 前 12
    for i, rec in enumerate(top):
        r, col = divmod(i, top_cols)
        x0 = 25 + col * top_pw
        y0 = top_y + r * (top_ph + 12)
        box = (x0, y0, x0 + top_pw - 14, y0 + top_ph)
        c.d.rectangle(box, outline="#ddd", width=1)
        draw_mol_panel(c, rec, box, header_size=13, node_letter=True,
                       rank=rec.get("rank"))
    # 后 18
    for i, rec in enumerate(rest):
        r, col = divmod(i, bot_cols)
        x0 = 25 + col * bot_pw
        y0 = bot_y + r * (bot_ph + 12)
        box = (x0, y0, x0 + bot_pw - 10, y0 + bot_ph)
        c.d.rectangle(box, outline="#ddd", width=1)
        draw_mol_panel(c, rec, box, header_size=10, node_letter=False,
                       rank=rec.get("rank"))
    c.txt(30, bot_y - 30,
          "后 18 个（#13–#30）多为 39/40 原子巨型分子（数量 1–2）：cap=40 允许的最大 F 产物；"
          "节点较小，键级可见，元素组成见 ⑨", size=13, fill="#555")
    data_note(c, [
        "top30 中常规主导（%d 个，≤18 原子）：CF/O2XP2WK2A2/OXCPWK/L2/LF/O4X2P5W2K3A2/"
        "O3XP4WK3A/WA/OXCPWKA/O2XP2WK2A/O2XP2K2A；巨型（%d 个，39/40 原子）："
        "%d 个分子 / %d 原子（约占终态原子 %.1f%%）。"
        % (len(reg), len(giant), sum(s.get("count") or 0 for s in giant),
           sum((s.get("atoms") or 0) * (s.get("count") or 0) for s in giant),
           100.0 * sum((s.get("atoms") or 0) * (s.get("count") or 0)
                       for s in giant) / 230133.0),
        "结构来源：final_top_structures 前 24 + 其余 %d 个由 natural_engine.complete_products"
        "（fast 引擎）重建；全部 F 稳定。大分子布局为自动弹簧/环形，非原始 hex 网格。"
        % sum(1 for s in structures if s.get("rebuilt")),
    ], y=H - 92)
    return c.save(out)


# ---------------------------------------------------------------- ⑨ top30 bars
def chart_top30_bars(a, out):
    structures = ((a.get("structures") or {}).get("top30")) or []
    if not structures:
        raise RuntimeError("structures.top30 为空")
    W, H = 1600, 1210
    c = Chart(W, H,
              "⑨ top30 数量/原子数条形 + 元素组成",
              "数量前 30 的分子式：数量（对数）、原子数、目录内/外；右侧为 top30 的元素原子组成")
    box = (470, 170, 1150, 1040)
    vmax = max([s.get("count") or 1 for s in structures] + [1]) * 2.2
    x0, y0, x1, y1 = box
    logmin, logmax = 0.0, math.log10(max(vmax, 10))

    def mx(v):
        v = max(1.0, float(v))
        return max(x0 + 2.0, x0 + (math.log10(v) - logmin) /
                   (logmax - logmin) * (x1 - x0))

    yt = [v for v in (1, 10, 100, 1000, 10000) if v <= vmax] or [1, 10]
    for v in yt:
        X = mx(v)
        c.d.line([X, y0, X, y1], fill="#e9e9e9", width=1)
        c.d.line([X, y1, X, y1 + 6], fill="#333", width=1)
        c.txt(X, y1 + 10, "%g" % v, size=12, anchor="ma")
    c.d.rectangle(box, outline="#333", width=2)
    c.txt((x0 + x1) / 2, y1 + 40, "终态数量（对数轴）", size=15, anchor="ma")
    n = len(structures)
    row_h = (y1 - y0) / max(1, n)
    for i, s in enumerate(structures):
        cy = y0 + row_h * (i + 0.5)
        giant = (s.get("atoms") or 0) >= 39
        colr = ORANGE if giant else BLUE
        c.d.rectangle([x0, cy - row_h * 0.33, mx(s.get("count") or 0),
                       cy + row_h * 0.33], fill=colr, outline="#333", width=1)
        c.txt(x0 - 8, cy, "#%d %s（%d 原子）"
              % (s.get("rank"), s.get("formula"), s.get("atoms") or 0),
              size=10, anchor="rm")
        c.txt(mx(s.get("count") or 0) + 5, cy, fmt_commas(s.get("count")),
              size=10, anchor="lm")
    # 右侧：元素组成
    box2 = (1200, 170, 1560, 700)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 14, box2[1] + 12, "top30 的元素原子组成", size=16, bold=True)
    elem = {}
    for s in structures:
        for e, k in (s.get("element_counts") or {}).items():
            elem[e] = elem.get(e, 0) + k * (s.get("count") or 0)
    total = sum(elem.values()) or 1
    y = box2[1] + 46
    for e in ORDER:
        if not elem.get(e):
            continue
        w = (box2[2] - box2[0] - 130) * elem[e] / total
        c.d.rectangle([box2[0] + 90, y, box2[0] + 90 + w, y + 22],
                      fill=ELEMCOL[e], outline="#333")
        c.txt(box2[0] + 14, y + 3, "%s %s" % (e, CN[e]), size=12)
        c.txt(box2[0] + 96 + w, y + 3, "%s（%.1f%%）"
              % (fmt_commas(elem[e]), 100.0 * elem[e] / total), size=11)
        y += 28
    y += 10
    giant_atoms = sum((s.get("atoms") or 0) * (s.get("count") or 0)
                      for s in structures if (s.get("atoms") or 0) >= 39)
    c.txt(box2[0] + 14, y, "top30 原子总数 %s" % fmt_commas(total), size=13,
          bold=True)
    y += 24
    c.txt(box2[0] + 14, y, "其中巨型（39/40 原子）%s 个分子 / %s 原子（%.1f%%）"
          % (fmt_commas(sum(s.get("count") or 0 for s in structures
                            if (s.get("atoms") or 0) >= 39)),
             fmt_commas(giant_atoms), 100.0 * giant_atoms / max(1, total)),
          size=12, fill="#555")
    data_note(c, [
        "数量前 11 个为常规主导分子（合计 %s 个分子），第 12–30 为 39/40 原子巨型分子"
        "（合计 21 个分子）；巨型分子数量虽少，但展示了 cap=40 下 F 产物可达到的最大尺寸。"
        % fmt_commas(sum(s.get("count") or 0 for s in structures
                         if (s.get("atoms") or 0) < 39)),
    ], y=1130)
    return c.save(out)


# ---------------------------------------------------------------- ⑩ 反应/capped
def chart_reaction_capped(a, out):
    A = a.get("phaseA") or {}
    B = a.get("phaseB") or {}
    W, H = 1600, 1140
    c = Chart(W, H,
              "⑩ 反应判定/capped 对比：A vs B",
              "complete/incomplete/none/capped 判定计数（对数）；capped 占判定比例 A=0.40% / B=0.44%；"
              "净事件 A=174,549 / B=206,740")
    # 左：判定类型
    box = (110, 175, 780, 620)
    cats = ["complete", "incomplete", "none", "capped"]
    va = A.get("reaction_counts") or {}
    vb = B.get("reaction_counts") or {}
    ymax = max([va.get(k, 0) for k in cats] + [vb.get(k, 0) for k in cats] + [1]) * 2
    yt = [1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
    yt = [v for v in yt if v <= ymax]
    nn = len(cats)
    mx, my = c.frame(box, (0, nn), (1, ymax), [i + 0.5 for i in range(nn)], yt,
                     logy=True, xtick_labels=["complete", "incomplete", "none", "capped"],
                     ytick_fmt=lambda v: fmt_num(v))
    bw = (box[2] - box[0]) / nn * 0.28
    for i, k in enumerate(cats):
        X = box[0] + (box[2] - box[0]) / nn * (i + 0.5)
        for val, colr, off in ((va.get(k, 0), BLUE, -bw / 2),
                               (vb.get(k, 0), ORANGE, bw / 2)):
            if val <= 0:
                continue
            Y = my(val)
            c.d.rectangle([X + off - bw / 2, Y, X + off + bw / 2, box[3]],
                          fill=colr, outline="#333")
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "判定次数（对数）", size=14)
    c.legend(box[0] + 14, box[1] - 38, [(BLUE, "phase A"), (ORANGE, "phase B")],
             size=13, row_h=24, cols=2, col_w=150)

    # 右：capped 占比（分窗口）
    box2 = (840, 175, 1540, 620)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 14, box2[1] + 12, "capped 占比（分时间窗口）", size=16, bold=True)
    wins = [("0–100", "first_100min"), ("900–1000", "last_100min")]
    y = box2[1] + 50
    for tag, P in (("A", A), ("B", B)):
        c.txt(box2[0] + 14, y, "phase %s" % tag, size=14, bold=True)
        y += 24
        for lab, key in wins:
            v = P.get("capped_" + key) or {}
            share = v.get("share") or 0
            w = (box2[2] - box2[0] - 380) * share
            c.txt(box2[0] + 30, y + 3, "%s 分钟" % lab, size=12)
            c.d.rectangle([box2[0] + 150, y, box2[0] + 150 + max(2, w), y + 20],
                          fill=(BLUE if tag == "A" else ORANGE), outline="#333")
            c.txt(box2[0] + 160 + max(2, w), y + 2,
                  "%.2f%%（%s / %s 次）"
                  % (100.0 * share, fmt_commas(v.get("capped")),
                     fmt_commas(v.get("collisions"))), size=11)
            y += 28
        y += 8
    c.txt(box2[0] + 14, y + 6,
          "capped = 合并后 >40 原子的弹性保护；峰值 A t=%s（%s 次）、B t=%s（%s 次）"
          % ((A.get("capped_peak") or {}).get("t"),
             (A.get("capped_peak") or {}).get("capped"),
             (B.get("capped_peak") or {}).get("t"),
             (B.get("capped_peak") or {}).get("capped")), size=12, fill="#555")
    c.txt(box2[0] + 14, y + 34,
          "平均 capped：A %.0f 次/分、B %.0f 次/分（A 32,985 / B 94,949，各 1000 分钟）"
          % ((A.get("capped_total") or 0) / 1000.0,
             (B.get("capped_total") or 0) / 1000.0), size=12, fill="#555")

    # 下：capped 累计 vs 时间（两阶段拼接）
    box3 = (110, 700, 1490, 980)
    TA = A.get("timeline") or []
    TB = B.get("timeline") or []
    rows = [dict(r, x=r["t"]) for r in TA] + [dict(r, x=r["t"] + 1000) for r in TB]
    xt = list(range(0, 2001, 200))
    ymax3 = max([r.get("capped_cum") or 0 for r in rows] + [1]) * 1.15
    yt3 = nice_ticks(0, ymax3, 5)
    mx3, my3 = c.frame(box3, (0, 2000), (0, ymax3), xt, yt3,
                       ytick_fmt=lambda v: fmt_num(v))
    c.line([(mx3(r["x"]), my3(r.get("capped_cum") or 0)) for r in rows],
           fill="#8e44ad", width=3)
    c.dashed((mx3(1000), box3[1]), (mx3(1000), box3[3]), fill=RED, width=2)
    c.rot(box3[0] - 58, (box3[1] + box3[3]) / 2, "capped 累计", size=14)
    c.txt((box3[0] + box3[2]) / 2, box3[3] + 36, "时间 t（分钟，A 0–1000 / B 1000–2000）",
          size=14, anchor="ma")
    data_note(c, [
        "A：complete 8,089,903 / incomplete 64,113 / none 3,636 / capped 32,985（合计 8,190,637）；"
        "B：21,297,049 / 117,698 / 6,564 / 94,949（合计 21,516,260）。",
        "净事件：A 174,549、B 206,740；decomp 各 1 次。capped 累计在 t=1000 处重置为 0（B 阶段独立计数），"
        "B 的 capped 绝对值更大但占比与 A 接近（0.44% vs 0.40%）。",
    ], y=1060)
    return c.save(out)


# ---------------------------------------------------------------- ⑪ 守恒
def chart_conservation(a, out):
    cmp_ = a.get("compare") or {}
    rows = cmp_.get("element_check") or []
    vc = cmp_.get("valence_check") or {}
    mb = cmp_.get("mass_balance") or {}
    W, H = 1600, 1120
    c = Chart(W, H,
              "11 元素/价数守恒与质量平衡",
              "九元素逐元素校验（A 初始=A 终态；B 初始=A 终态+batchB=B 终态）；"
              "价数原子数同样守恒")
    # 元素守恒：A / B（初始 vs 终态成对柱）
    box = (110, 175, 1100, 640)
    els = [r["element"] for r in rows]
    x0, x1 = box[0] + 60, box[2] - 20
    y0, y1 = box[1] + 40, box[3] - 60
    vmax = max([r["A_initial"] for r in rows] + [r["B_initial"] for r in rows] + [1]) * 1.2
    for v in nice_ticks(0, vmax, 5):
        Y = y1 - v / vmax * (y1 - y0)
        c.d.line([x0, Y, x1, Y], fill="#eee", width=1)
        c.txt(x0 - 8, Y, fmt_num(v), size=12, anchor="rm")
    bw = (x1 - x0) / len(els) * 0.18
    for i, r in enumerate(rows):
        X = x0 + (x1 - x0) / len(els) * (i + 0.5)
        for val, colr, off in ((r["A_initial"], BLUE, -1.5 * bw),
                               (r["A_final"], "#1abc9c", -0.5 * bw),
                               (r["B_initial"], ORANGE, 0.5 * bw),
                               (r["B_final"], "#c0392b", 1.5 * bw)):
            Y = y1 - val / vmax * (y1 - y0)
            c.d.rectangle([X + off - bw / 2, Y, X + off + bw / 2, y1],
                          fill=colr, outline="#333", width=1)
        c.txt(X, y1 + 8, "%s %s" % (r["element"], r["zh"]), size=12, anchor="ma")
    c.rot(box[0] - 52, (box[1] + box[3]) / 2, "原子数", size=14)
    c.txt((box[0] + box[2]) / 2, box[1] + 8, "九元素守恒（A/B 初始 vs 终态）",
          size=16, bold=True)
    c.legend(box[0] + 10, box[3] + 28,
             [(BLUE, "A 初始"), ("#1abc9c", "A 终态"), (ORANGE, "B 初始"),
              ("#c0392b", "B 终态")], size=13, row_h=22, cols=4, col_w=160)

    # 价数守恒
    box2 = (1140, 175, 1560, 640)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 14, box2[1] + 12, "价数原子守恒", size=16, bold=True)
    y = box2[1] + 50
    for phase, key in (("A", "A"), ("B", "B")):
        init = vc.get("%s_initial" % key) or {}
        fin = vc.get("%s_final" % key) or {}
        c.txt(box2[0] + 14, y, "phase %s" % phase, size=14, bold=True)
        y += 26
        for k, lab, colr in (("v3", "3 价", "#c0392b"), ("v2", "2 价", BLUE),
                             ("v1", "1 价", "#10ac84")):
            iv, fv = init.get(k, 0), fin.get(k, 0)
            c.txt(box2[0] + 22, y, "%s：初始 %s / 终态 %s（差 %+d）"
                  % (lab, fmt_commas(iv), fmt_commas(fv), fv - iv),
                  size=12, fill=colr)
            y += 24
        y += 8
    c.txt(box2[0] + 14, y + 4,
          "A 守恒=%s；B 守恒=%s" % ("√" if vc.get("A_conserved") else "×",
                                     "√" if vc.get("B_conserved") else "×"),
          size=14, bold=True, fill=GREEN)

    # 质量平衡
    box3 = (110, 780, 1560, 1020)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 14, box3[1] + 12, "质量平衡：B 原子 = A 终态原子 + batchB 原子",
          size=16, bold=True)
    y = box3[1] + 48
    lines = [
        "A 终态：%s 原子（%s 分子，43 种结构）"
        % (fmt_commas(mb.get("A_final_atoms")),
           fmt_commas((a.get("phaseA") or {}).get("final_total_molecules"))),
        "batchB：%s 原子（%s 分子，120 种）"
        % (fmt_commas(mb.get("batchB_atoms")),
           fmt_commas(((a.get("loads") or {}).get("batchB") or {}).get("molecules"))),
        "= B 初始：%s 原子（%s 分子：整理底物 %s + batchB %s）"
        % (fmt_commas(mb.get("expected_B_atoms")),
           fmt_commas(mb.get("B_initial_particles_config")),
           fmt_commas(mb.get("seed_initial_count")),
           fmt_commas(mb.get("batchB_molecules"))),
        "= B 终态：%s 原子（%s 分子，67 种结构）→ 质量守恒 %s"
        % (fmt_commas(mb.get("B_final_atoms")),
           fmt_commas((a.get("phaseB") or {}).get("final_total_molecules")),
           "√" if mb.get("mass_conserved") else "×"),
    ]
    for s in lines:
        c.txt(box3[0] + 20, y, s, size=14, fill="#222")
        y += 28
    data_note(c, [
        "元素守恒：A 初始=batchA 元素原子数，A 终态逐元素求和；B 初始=A 终态+batchB，"
        "B 终态逐元素求和；全部 delta=0。",
        "价数守恒：按元素价数（O/K/P=3、X/A/W=2、C/L/F=1）统计 v3/v2/v1 原子数，两阶段均守恒。",
    ], y=1040)
    return c.save(out)


# ---------------------------------------------------------------- main
CHARTS = [
    ("loads", "t59_loads.png", chart_loads),
    ("composition", "t59_composition.png", chart_composition),
    ("top20_compare", "t59_top20_compare.png", chart_top20_compare),
    ("size_distribution", "t59_size_distribution.png", chart_size_distribution),
    ("diversity", "t59_diversity.png", chart_diversity),
    ("timeline", "t59_timeline.png", chart_timeline),
    ("snapshots", "t59_snapshots.png", chart_snapshots),
    ("top30_structures", "t59_top30_structures.png", chart_top30_structures),
    ("top30_bars", "t59_top30_bars.png", chart_top30_bars),
    ("reaction_capped", "t59_reaction_capped.png", chart_reaction_capped),
    ("conservation", "t59_conservation.png", chart_conservation),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="T59 图表渲染")
    ap.add_argument("--analysis", default=DEFAULT_ANALYSIS)
    ap.add_argument("--images", default=DEFAULT_IMAGES)
    ap.add_argument("--only", default=None)
    args = ap.parse_args(argv)
    if not os.path.exists(args.analysis):
        print("[error] 分析文件不存在：%s" % args.analysis)
        return 2
    a = json.load(open(args.analysis, encoding="utf-8"))
    # 快照原始数据不在分析 JSON 中（体积原因）
    meta = a.get("meta") or {}
    files = meta.get("files") or {}
    for tag, key in (("A", "phaseA"), ("B", "phaseB")):
        fn = files.get(key)
        if fn:
            p = os.path.join(BASE, fn)
            if os.path.exists(p):
                try:
                    raw = json.load(open(p, encoding="utf-8"))
                    a.setdefault("_raw", {})[tag] = raw
                    if tag == "A":
                        a.setdefault("_rawA", raw)
                except Exception as exc:
                    print("[warn] load %s failed: %s" % (fn, exc), flush=True)
    # 兼容：chart_snapshots 用 phases raw 的 snapshots（不在 analysis 里）
    for tag, key in (("A", "phaseA"), ("B", "phaseB")):
        pass
    os.makedirs(args.images, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None
    results = []
    for name, fn, func in CHARTS:
        if only and name not in only:
            continue
        out = os.path.join(args.images, fn)
        try:
            size = func(a, out)
            ok = size > 3000
            results.append((name, out, size, ok))
            print("[ok] %-20s %8d bytes  %s" % (name, size, out), flush=True)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            results.append((name, out, 0, False))
            print("[FAIL] %-18s %s" % (name, exc), flush=True)
    bad = [r for r in results if not r[3]]
    print("\n[done] %d/%d charts ok" % (len(results) - len(bad), len(results)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
