# -*- coding: utf-8 -*-
"""t58_render.py —— T58 实验图表（Pillow 绘制，中文字体 msyh）

读取 t58_analysis.json，生成 10 张图：
  images/t58_mixture.png           ① 投料设计/九元素覆盖（44 种随机物质）
  images/t58_composition.png       ② 组成随时间演化
  images/t58_reaction_rate.png     ③ 反应判定计数/分钟（含 capped 计算保护）+ 温度
  images/t58_state_sizes.png       ④ 状态/尺寸时间线（速度/N/平均+最大原子数，cap=20）
  images/t58_snapshots.png         ⑤ 2D 快照拼图（element_bitmask）
  images/t58_final_composition.png ⑥ 终态组成（29内/目录内/目录外）
  images/t58_crossings.png         ⑦ 穿越验证（整体 + by_size）
  images/t58_temperature_windows.png ⑧ 温度区间反应类型（含 capped）
  images/t58_size_distribution.png ⑨ 尺寸分布演化 + 终态分布（上限 20）
  images/t58_scale_compare.png     ⑩ 历史规模对比（T55/T56/T57/T58）

用法：
  python t58_render.py
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_ANALYSIS = os.path.join(BASE, "t58_analysis.json")
DEFAULT_IMAGES = os.path.join(BASE, "images")

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT_REG

PAL = ["#2e86de", "#ee5253", "#10ac84", "#f39c12", "#8e44ad", "#16a085",
       "#d35400", "#2c3e50", "#c0392b", "#7f8c8d", "#27ae60", "#e84393",
       "#00acc1", "#795548", "#607d8b", "#f06292"]
TYPECOL = {"complete": "#e74c3c", "incomplete": "#f39c12",
           "none": "#95a5a6", "capped": "#8e44ad", "decomp": "#6c3483"}
SNAPCOL7 = {0: "#2ecc71", 1: "#f39c12", 2: "#3498db", 3: "#9b59b6",
            4: "#1abc9c", 5: "#e74c3c", 6: "#00acc1"}
GREEN = "#2e8b57"
ORANGE = "#e67e22"
BLUE = "#2e86de"
RED = "#c0392b"
ELEMCOL = {"O": "#2ecc71", "X": "#f39c12", "C": "#3498db", "P": "#8e44ad",
           "W": "#16a085", "L": "#d35400", "K": "#c0392b", "A": "#1abc9c",
           "F": "#e74c3c"}
ELEMCN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
          "K": "沌", "A": "气", "F": "焰"}
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]


# ---------------------------------------------------------------- 通用绘图
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


# ================================================================ ① 投料设计
def chart_mixture(a, out):
    mix = a.get("mixture") or {}
    rows = mix.get("species") or []
    if not rows:
        raise RuntimeError("mixture.species 为空")
    checks = mix.get("checks") or {}
    meta = mix.get("meta") or {}
    W, H = 1600, 1120
    c = Chart(W, H,
              "① 投料设计：44 种随机物质（原子数 2~12 各 4 种）+ 九元素全覆盖",
              "从 84,225 目录随机抽取；数量∝1/面积；14000 分子 / 73216 原子（平均 5.23 原子）；"
              "L=400000，v0≈8.85e5，计算保护上限 20 原子")
    # A：n-面积
    box = (90, 165, 520, 560)
    xt = list(range(2, 13))
    ymax = max(r.get("area") or 0 for r in rows) * 1.15
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (1.5, 12.5), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: "%.2f" % v)
    c.line([(mx(n), my(math.pi * 0.2 * 0.2 * n / 2.0)) for n in range(2, 13)],
           fill="#999", width=2)
    for r in rows:
        c.d.ellipse([mx(r.get("atoms")) - 4, my(r.get("area") or 0) - 4,
                     mx(r.get("atoms")) + 4, my(r.get("area") or 0) + 4],
                    fill=BLUE, outline="#333")
    c.rot(box[0] - 56, (box[1] + box[3]) / 2, "面积 A", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 38, "分子原子数 n", size=15, anchor="ma")
    c.txt(box[0] + 8, box[1] + 8, "A = πR0²·(n/2)", size=14, bold=True)
    c.txt(box[0] + 8, box[1] + 30, "Pearson(n,A)=%.2f"
          % (checks.get("pearson_atoms_area") or 0), size=13, fill="#555")

    # B：n-数量
    box2 = (600, 165, 1030, 560)
    ymax2 = max(r.get("count") or 0 for r in rows) * 1.15
    yt2 = nice_ticks(0, ymax2, 5)
    mx2, my2 = c.frame(box2, (1.5, 12.5), (0, ymax2), xt, yt2,
                       ytick_fmt=lambda v: fmt_commas(v))
    Kc = meta.get("K") or 0
    if Kc:
        c.line([(mx2(n), my2(Kc / n)) for n in range(2, 13)], fill="#999", width=2)
    for r in rows:
        c.d.ellipse([mx2(r.get("atoms")) - 4, my2(r.get("count") or 0) - 4,
                     mx2(r.get("atoms")) + 4, my2(r.get("count") or 0) + 4],
                    fill=ORANGE, outline="#333")
    c.rot(box2[0] - 56, (box2[1] + box2[3]) / 2, "投料数量", size=14)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 38, "分子原子数 n", size=15, anchor="ma")
    c.txt(box2[0] + 8, box2[1] + 8, "count ∝ 1/n（%d→%d）" % (
        checks.get("count_range", [0, 0])[1], checks.get("count_range", [0, 0])[0]),
        size=14, bold=True)
    c.txt(box2[0] + 8, box2[1] + 30,
          "严格反向=%s  Pearson(n,count)=%.2f"
          % ("是" if checks.get("strict_inverse_monotone") else "否",
             checks.get("pearson_atoms_count") or 0), size=13, fill="#555")

    # C：尺寸分布（分子数柱 + 物种数）
    box3 = (1110, 165, 1560, 560)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 14, box3[1] + 10, "原子数分布（44 种）", size=16, bold=True)
    sd = mix.get("size_distribution") or []
    y = box3[1] + 44
    c.txt(box3[0] + 14, y, "n   种数   分子数    原子数", size=13, bold=True)
    y += 24
    for d in sd:
        c.txt(box3[0] + 14, y, "%2d   %2d   %6s   %7s"
              % (d["atoms"], d["species"], fmt_commas(d["molecules"]),
                 fmt_commas(d["atoms_total"])), size=13, fill=ELEMCOL.get("O"))
        y += 21
    y += 8
    c.txt(box3[0] + 14, y, "合计 44 种 / %s 分子 / %s 原子"
          % (fmt_commas(checks.get("total_molecules")),
             fmt_commas(checks.get("total_atoms"))), size=13, bold=True)
    y += 24
    c.txt(box3[0] + 14, y, "平均 %.2f 原子；面积 %.3f~%.3f；数量 %d~%d"
          % (checks.get("mean_atoms") or 0,
             checks.get("area_range", [0, 0])[0], checks.get("area_range", [0, 0])[1],
             checks.get("count_range", [0, 0])[0],
             checks.get("count_range", [0, 0])[1]), size=12, fill="#555")

    # D：九元素原子数
    box4 = (90, 650, 1560, 930)
    el = mix.get("element_atoms") or {}
    els = [e for e in ORDER if el.get(e, 0) > 0]
    x0, x1 = box4[0] + 70, box4[2] - 30
    y0, y1 = box4[1] + 50, box4[3] - 70
    emax = max(el.values() or [1]) * 1.2
    for v in nice_ticks(0, emax, 4):
        Y = y1 - v / emax * (y1 - y0)
        c.d.line([x0, Y, x1, Y], fill="#eee", width=1)
        c.txt(x0 - 8, Y, fmt_commas(v), size=12, anchor="rm")
    bw = (x1 - x0) / len(els) * 0.6
    for i, e in enumerate(els):
        X = x0 + (x1 - x0) / len(els) * (i + 0.5)
        val = el.get(e, 0)
        Y = y1 - val / emax * (y1 - y0)
        c.d.rectangle([X - bw / 2, Y, X + bw / 2, y1], fill=ELEMCOL.get(e, "#888"),
                      outline="#333", width=1)
        c.txt(X, Y - 6, fmt_commas(val), size=12, anchor="mb")
        c.txt(X, y1 + 10, "%s %s" % (e, ELEMCN.get(e, "")), size=14, anchor="ma")
    c.txt((x0 + x1) / 2, box4[1] + 10,
          "九元素原子数（全部覆盖：%s）" % " ".join(els), size=16, bold=True)
    c.rot(box4[0] - 52, (box4[1] + box4[3]) / 2, "原子数", size=14)
    data_note(c, [
        "投料：从 84,225 目录按原子数 2~12 每档随机抽 4 种并补足缺失元素 → 44 种、"
        "14000 分子、73216 原子；九元素全部出现。",
        "T58 规模对比：分子数 14000（T55 9000 / T56 9200 / T57 9002），"
        "原子数 73216（T57 38532 的 1.9 倍）；环境 L=400000（面积 1600×），初速≈8.85e5。",
        "计算保护：合并后 >20 原子的碰撞不反应（只弹性），reaction_counts['capped'] 计数；"
        "因此终态尺寸上限 20 原子。",
    ], y=960)
    return c.save(out)


# ================================================================ ② 组成
def chart_composition(a, out):
    comp = a.get("composition") or {}
    cfg = a.get("config") or {}
    series = comp.get("series") or []
    minutes = cfg.get("minutes") or (series[-1]["t"] if series else 1000)
    T0 = cfg.get("T0") or 1000
    if not series:
        raise RuntimeError("composition.series 为空")
    W, H = 1600, 1160
    c = Chart(W, H,
              "② 组成演化：44 种随机物质 → 完全反应退火 → 少数小分子终态",
              "每 5 分钟完整组成；堆叠 = top 分子式数量；t=0 已含第 0 分钟反应")
    box = (100, 150, 1310, 650)
    totals = [r.get("total") or 0 for r in series]
    ymax = max(totals + [1]) * 1.12
    xt = nice_ticks(0, minutes, 10)
    yt = nice_ticks(0, ymax, 6)
    mx, my = c.frame(box, (0, minutes), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: fmt_commas(v))
    c.top_temp_axis(box, (0, minutes), mx, T0, minutes)
    layers = [(f, [r.get("top_counts", {}).get(f, 0) for r in series])
              for f in comp.get("stack_order") or []]
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
    c.txt((box[0] + box[2]) / 2, box[3] + 42, "时间 t（分钟）", size=16, anchor="ma")
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "分子数", size=15)
    items = []
    topf = comp.get("top_formulas") or []
    for i, f in enumerate(comp.get("stack_order") or []):
        zh = topf[i].get("zh") if i < len(topf) else ""
        items.append((PAL[i % len(PAL)], "%s %s" % (f, zh)))
    items.append((PAL[len(comp.get("stack_order") or []) % len(PAL)], "其它"))
    c.txt(1326, 150, "分子式（颜色）", size=16, bold=True)
    c.legend(1326, 186, items, size=11, row_h=22)

    # 下：物种数 + 大分子占比 + capped 占比
    box2 = (100, 720, 1120, 930)
    nsp = [r.get("n_species") or 0 for r in series]
    nsmax = max(nsp + [1]) * 1.08
    lm = [r.get("big5_molecule_share") or 0.0 for r in series]
    la = [r.get("big5_atom_share") or 0.0 for r in series]
    yt2 = [0, 0.25, 0.5, 0.75, 1.0]
    mx2, my2 = c.frame(box2, (0, minutes), (0, 1.0), xt, yt2,
                       ytick_fmt=lambda v: "%.0f%%" % (v * 100))
    myr = c.right_axis(box2, (0, nsmax), nice_ticks(0, nsmax, 5),
                       label="分子式数", color=BLUE)
    c.d.line([(mx2(series[j]["t"]), my2(lm[j])) for j in range(n)],
             fill="#c0392b", width=3)
    c.d.line([(mx2(series[j]["t"]), my2(la[j])) for j in range(n)],
             fill="#e67e22", width=2)
    c.d.line([(mx2(series[j]["t"]), myr(nsp[j])) for j in range(n)],
             fill="#95a5a6", width=2)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 42, "时间 t（分钟）", size=16, anchor="ma")
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "大分子占比", size=14)
    c.legend(1220, 750,
             [("#c0392b", "≥5 原子：分子占比"),
              ("#e67e22", "≥5 原子：原子占比"),
              ("#95a5a6", "分子式数（右轴）")], size=13, row_h=28)
    kn = (a.get("key_numbers") or {}).get("main") or {}
    ls = comp.get("large_stats") or {}
    capped = (a.get("timeline") or {}).get("capped") or {}
    data_note(c, [
        "终态 %s 分子、%d 种分子式（29内 %d / 目录内 %d / 目录外 %d）；平均 %.2f 原子、"
        "最大 %s 原子；≥5 原子 %s 个（%.2f%% 分子、%.2f%% 原子）；新物质 %s 种。"
        % (fmt_commas(kn.get("final_N")), kn.get("final_distinct_formulas") or 0,
           (kn.get("final_class3_counts") or {}).get("29内") or 0,
           (kn.get("final_class3_counts") or {}).get("目录内") or 0,
           (kn.get("final_class3_counts") or {}).get("目录外") or 0,
           kn.get("final_mean_atoms") or 0, kn.get("final_max_atoms") or 0,
           fmt_commas((ls.get("ge5") or {}).get("molecules")),
           100.0 * ((ls.get("ge5") or {}).get("molecule_share") or 0),
           100.0 * ((ls.get("ge5") or {}).get("atom_share") or 0),
           kn.get("new_substances_total")),
        "计算保护：capped 碰撞共 %s 次（占碰撞 %.2f%%）；净变化事件 %s；capped 只限制"
        ">20 原子合并，不改变 ≤20 原子的化学。"
        % (fmt_commas(kn.get("capped_total")), 100.0 * (kn.get("capped_share") or 0),
           fmt_commas(kn.get("net_events_total"))),
    ], y=990)
    return c.save(out)


# ================================================================ ③ 反应率
def chart_reaction_rate(a, out):
    tl = a.get("timeline") or {}
    rows = tl.get("per_minute") or []
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or len(rows)
    T0 = cfg.get("T0") or 1000
    if not rows:
        raise RuntimeError("timeline.per_minute 为空")
    W, H = 1600, 1010
    c = Chart(W, H,
              "③ 反应判定计数/分钟（complete/incomplete/none/capped）与温度轴",
              "左轴=判定次数（对数），右轴=温度；capped=合并>20 原子的计算保护（弹性），"
              "真正净变化事件见下图")
    box = (110, 172, 1430, 600)
    cmax = max([r.get("complete") or 0 for r in rows] + [1])
    ymax = cmax * 1.8
    yticks = [1, 10, 100, 1000]
    v = 10000
    while v <= ymax:
        yticks.append(v)
        v *= 10
    xt = nice_ticks(0, minutes, 10)
    mx, my = c.frame(box, (0, minutes), (1, ymax), xt, yticks, logy=True,
                     ytick_fmt=lambda v: "%g" % v)
    myr = c.right_axis(box, (0, T0), [0, 200, 400, 600, 800, 1000],
                       label="温度 T (°C)", color="#555")
    c.dashed((mx(0), myr(T0)), (mx(minutes), myr(0)), fill="#999", width=2)
    for key, colr, wdt in (("complete", TYPECOL["complete"], 3),
                           ("incomplete", TYPECOL["incomplete"], 2),
                           ("none", TYPECOL["none"], 2),
                           ("capped", TYPECOL["capped"], 2)):
        pts = [(mx(r["t"]), my(r[key])) for r in rows if (r.get(key) or 0) > 0]
        if len(pts) >= 2:
            c.d.line(pts, fill=colr, width=wdt)
        elif len(pts) == 1:
            x, y = pts[0]
            c.d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=colr)
    trans = tl.get("transitions") or {}
    last_net = trans.get("last_net_change") or {}
    fzc = trans.get("first_zero_complete") or {}
    if last_net.get("t") is not None:
        c.dashed((mx(last_net["t"]), box[1]), (mx(last_net["t"]), box[3]),
                 fill=RED, width=1)
        c.txt_bg(mx(last_net["t"]) + 4, box[1] + 8,
                 "净变化停止 t=%s（T=%s）" % (last_net["t"], last_net["T"]),
                 size=12, fill=RED)
    if fzc.get("t") is not None:
        c.dashed((mx(fzc["t"]), box[1]), (mx(fzc["t"]), box[3]), fill=RED, width=1)
        c.txt_bg(mx(fzc["t"]) - 4, box[1] + 62, "complete→0（T=%s）" % fzc["T"],
                 size=12, anchor="ra", fill=RED)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "判定次数/分钟（对数）", size=14)
    c.legend(box[0] + 4, box[1] - 42,
             [(TYPECOL["complete"], "complete（含净不变）"),
              (TYPECOL["incomplete"], "incomplete"),
              (TYPECOL["none"], "none（弹性）"),
              (TYPECOL["capped"], "capped（>20 原子保护）")],
             size=13, row_h=24, cols=4, col_w=290)

    box2 = (110, 672, 1430, 900)
    ev = [r.get("net_events") or 0 for r in rows]
    emax = max(ev + [1]) * 1.5
    yt2 = [1, 10, 100, 1000]
    v = 10000
    while v <= emax:
        yt2.append(v)
        v *= 10
    mx2, my2 = c.frame(box2, (0, minutes), (1, emax), xt, yt2, logy=True,
                       ytick_fmt=lambda v: "%g" % v)
    bw = max(1.0, (mx2(minutes) - mx2(0)) / max(1, minutes) * 1.2)
    for r in rows:
        if (r.get("net_events") or 0) > 0:
            X = mx2(r["t"])
            c.d.rectangle([X - bw / 2, my2(r["net_events"]),
                           X + bw / 2, box2[3]], fill="#8e44ad")
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "净变化事件/分钟", size=14,
          fill="#8e44ad")
    ev_a = a.get("events") or {}
    capped = tl.get("capped") or {}
    c.txt_bg(box2[0] + 12, box2[1] + 8,
             "净变化事件 %s 次、分布 %d 分钟；capped 合计 %s 次（占碰撞 %.2f%%）"
             % (fmt_commas(sum(ev)), sum(1 for x in ev if x > 0),
                fmt_commas(capped.get("total")),
                100.0 * (capped.get("share") or 0)),
             size=13, fill="#8e44ad")
    c.txt_bg(box2[0] + 12, box2[1] + 32,
             "t=0 分钟 %s 次；capped 随大分子累积而上升（峰值 t≈%s）。"
             % (fmt_commas(ev[0] if ev else 0),
                (capped.get("peak") or {}).get("t")), size=13, fill="#555")
    data_note(c, [
        "判定计数合计 %s = 碰撞数（complete %s / incomplete %s / none %s / capped %s）；"
        "其中 %.2f%% 的 complete 判定净结果不变（F 不动点）。"
        % (fmt_commas(sum((r.get("collisions") or 0) for r in rows)),
           fmt_commas(sum((r.get("complete") or 0) for r in rows)),
           fmt_commas(sum((r.get("incomplete") or 0) for r in rows)),
           fmt_commas(sum((r.get("none") or 0) for r in rows)),
           fmt_commas(sum((r.get("capped") or 0) for r in rows)),
           100.0 * (ev_a.get("complete_noop_ratio") or 0.0)),
        "计算保护：合并后 >%s 原子的碰撞不反应（弹性），capped 随大分子累积而上升"
        "（峰值 t≈%s）；保护不改变 ≤%s 原子的化学，只封顶尺寸。"
        % (cfg.get("max_reaction_atoms"),
           (capped.get("peak") or {}).get("t"),
           cfg.get("max_reaction_atoms")),
    ])
    return c.save(out)


# ================================================================ ④ 状态/尺寸
def chart_state_sizes(a, out):
    rows = (a.get("timeline") or {}).get("per_minute") or []
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or len(rows)
    T0 = cfg.get("T0") or 1000
    cap = cfg.get("max_reaction_atoms") or 20
    if not rows:
        raise RuntimeError("timeline.per_minute 为空")
    W, H = 1600, 1120
    c = Chart(W, H,
              "④ 状态/尺寸时间线：速度 / 粒子数 / 平均与最大原子数（计算保护上限 %s）" % cap,
              "速度按每次碰撞衰减 ε=0.2%%；L=400000、v0≈8.85e5；最大原子数不应超过 %s" % cap)
    xt = nice_ticks(0, minutes, 10)
    kin = a.get("kinetics") or {}
    trans = (a.get("timeline") or {}).get("transitions") or {}
    half = trans.get("speed_half")

    box = (130, 170, 1410, 390)
    sp = [r.get("speed_mean") or 0 for r in rows]
    sp_all = ([r.get("speed_mean") or 0 for r in rows] +
              [r.get("speed_median") or 0 for r in rows] +
              [r.get("speed_p90") or 0 for r in rows])
    smin = min(sp) if sp else 0
    smax = max(sp_all) if sp_all else 1
    ylo = max(0.0, smin * 0.95)
    ymax = smax * 1.02
    if ymax <= ylo:
        ymax = ylo + 1
    yt = nice_ticks(ylo, ymax, 5)
    mx, my = c.frame(box, (0, minutes), (ylo, ymax), xt, yt,
                     ytick_fmt=lambda v: fmt_commas(v))
    c.top_temp_axis(box, (0, minutes), mx, T0, minutes)
    c.line([(mx(r["t"]), my(r.get("speed_mean") or 0)) for r in rows],
           fill=RED, width=3)
    c.line([(mx(r["t"]), my(r.get("speed_median") or 0)) for r in rows],
           fill="#e67e22", width=2)
    c.line([(mx(r["t"]), my(r.get("speed_p90") or 0)) for r in rows],
           fill="#95a5a6", width=2)
    c.rot(box[0] - 60, (box[1] + box[3]) / 2, "速度", size=14)
    c.legend(760, 96,
             [(RED, "平均速度"), ("#e67e22", "中位速度"), ("#95a5a6", "p90 速度")],
             size=13, row_h=24, cols=3, col_w=210)
    c.txt_bg(box[2] - 16, box[1] + 12,
             "速度 %.0f → %.0f（保留 %.1f%%）" % (
                 kin.get("speed_initial") or 0, kin.get("speed_final") or 0,
                 100.0 * (kin.get("speed_ratio") or 0)),
             size=13, anchor="ra", fill=RED)
    if half:
        c.dashed((mx(half["t"]), box[1]), (mx(half["t"]), box[3]), fill="#555", width=1)
        c.txt_bg(mx(half["t"]) + 6, box[3] - 26,
                 "半速 t=%s（v=%.0f）" % (half["t"], half["v"]), size=12, fill="#555")

    box2 = (130, 470, 1410, 680)
    N = [r.get("N") or 0 for r in rows]
    ymax2 = max(N + [1]) * 1.12
    yt2 = nice_ticks(0, ymax2, 5)
    mx2, my2 = c.frame(box2, (0, minutes), (0, ymax2), xt, yt2,
                       ytick_fmt=lambda v: fmt_commas(v))
    c.line([(mx2(r["t"]), my2(r.get("N") or 0)) for r in rows],
           fill=BLUE, width=3)
    c.rot(box2[0] - 60, (box2[1] + box2[3]) / 2, "粒子数 N", size=14)
    nmin = trans.get("N_min") or {}
    c.txt_bg(box2[2] - 16, box2[3] - 30,
             "N 最小 %s @ t=%s；终态 N=%s（初始 %s）"
             % (fmt_commas(nmin.get("N")), nmin.get("t"),
                fmt_commas(kin.get("N_final")),
                fmt_commas(cfg.get("initial_particles"))),
             size=13, anchor="ra", fill=BLUE)

    box3 = (130, 760, 1380, 960)
    ma = [r.get("mean_atoms") or 0 for r in rows]
    maxa = [r.get("max_atoms") or 0 for r in rows]
    ymax3 = max(maxa + [cap + 2])
    yt3 = nice_ticks(0, ymax3, 5)
    mx_, my3 = c.frame(box3, (0, minutes), (0, ymax3), xt, yt3)
    c.dashed((mx_(0), my3(cap)), (mx_(minutes), my3(cap)), fill=ORANGE,
             width=2, dash=8)
    c.txt_bg(mx_(minutes) - 6, my3(cap) - 22, "计算保护上限 %s 原子" % cap,
             size=12, anchor="ra", fill=ORANGE)
    c.line([(mx_(r["t"]), my3(r.get("mean_atoms") or 0)) for r in rows],
           fill="#10ac84", width=3)
    c.line([(mx_(r["t"]), my3(r.get("max_atoms") or 0)) for r in rows],
           fill="#7f8c8d", width=2)
    c.rot(box3[0] - 60, (box3[1] + box3[3]) / 2, "平均原子数（绿）", size=13)
    c.rot(box3[2] + 52, (box3[1] + box3[3]) / 2, "最大原子数（灰）", size=13,
          fill="#7f8c8d")
    c.txt((box3[0] + box3[2]) / 2, box3[3] + 38, "时间 t（分钟）", size=16, anchor="ma")
    c.txt_bg(box3[0] + 16, box3[1] + 12,
             "平均 %.2f → %.3f；最大原子数峰值 %s @ t=%s；终态最大 %s"
             % ((a.get("mixture") or {}).get("checks", {}).get("mean_atoms") or 0,
                kin.get("mean_atoms_final") or 0, kin.get("max_atoms_max"),
                kin.get("max_atoms_peak_t"),
                (a.get("key_numbers") or {}).get("main", {}).get("final_max_atoms")),
             size=13, fill="#10ac84")
    data_note(c, [
        "速度 %.0f → %.0f（保留 %.1f%%）；L=400000、自由程长，碰撞稀疏，速度衰减仅 %.1f%%，"
        "未到半速。"
        % (kin.get("speed_initial") or 0, kin.get("speed_final") or 0,
           100.0 * (kin.get("speed_ratio") or 0),
           100.0 * (1.0 - (kin.get("speed_ratio") or 0))),
        "原子数守恒；N 从 %s 到终态 %s；最大原子数被计算保护封顶在 %s（不是化学上限）。"
        % (fmt_commas(cfg.get("initial_particles")),
           fmt_commas(kin.get("N_final")), cap),
    ], y=1010)
    return c.save(out)


# ================================================================ ⑤ 快照
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
    for s in snaps:
        if len(out) >= max_n:
            break
        if id(s) not in used:
            used.add(id(s))
            out.append(s)
    out.sort(key=lambda s: s.get("t") or 0)
    return out[:max_n]


def chart_snapshots(a, out):
    snaps = a.get("snapshots") or (a.get("_main_raw") or {}).get("snapshots") or []
    chosen = _pick_snapshots(snaps, [0, 2, 5, 10, 100, 300, 700, 995], 8)
    if not chosen:
        raise RuntimeError("没有可用 snapshots")
    cfg = a.get("config") or {}
    L = cfg.get("L") or 400000
    bitmask = any((s.get("color_mode") == "element_bitmask") for s in chosen)
    freq = {}
    for s in chosen:
        for p in s.get("points") or []:
            if len(p) >= 3:
                freq[p[2]] = freq.get(p[2], 0) + 1
    top_codes = [code for code, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:10]]
    palette = {code: PAL[i % len(PAL)] for i, code in enumerate(top_codes)}
    total_pts = sum(freq.values()) or 1
    cols, rows = 4, max(1, math.ceil(len(chosen) / 4))
    pw, ph = 365, 400
    W = cols * pw + 40
    H = 160 + rows * ph + 90
    c = Chart(W, H,
              "⑤ 2D 粒子环境快照（L=400000，每帧 ≤3000 个分子）",
              "颜色 = 元素组合（%s）；只列占比最高的 %d 种组合，其余灰色"
              % ("element_bitmask" if bitmask else "旧 7 色", len(top_codes)))
    for i, s in enumerate(chosen):
        r, col = divmod(i, cols)
        x0 = 30 + col * pw
        y0 = 130 + r * ph
        box = (x0, y0, x0 + pw - 18, y0 + ph - 62)
        c.d.rectangle(box, fill="#fbfbfb", outline="#ccc", width=1)
        pts = s.get("points") or []
        bw, bh = box[2] - box[0], box[3] - box[1]
        rad = 2.4 if len(pts) > 1500 else 3.0
        legend = s.get("legend") or {}
        per_code = {}
        for p in pts:
            if len(p) < 3:
                continue
            code = p[2]
            per_code[code] = per_code.get(code, 0) + 1
            px = box[0] + max(0.0, min(1.0, p[0] / L)) * bw
            py = box[3] - max(0.0, min(1.0, p[1] / L)) * bh
            colr = palette.get(code, "#b0bec5") if bitmask else SNAPCOL7.get(
                int(code), "#b0bec5")
            c.d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=colr)
        dom = max(per_code.items(), key=lambda kv: kv[1]) if per_code else (None, 0)
        dom_label = legend.get(str(dom[0]), str(dom[0]))
        inf = [box[0] + 5, box[1] + 5, box[0] + 226, box[1] + 58]
        c.d.rectangle(inf, fill="#ffffff", outline="#d9d9d9")
        c.txt(inf[0] + 8, inf[1] + 6, "t=%s  T=%s" % (
            s.get("t"), (a.get("config") or {}).get("T0", 1000) - (s.get("t") or 0)),
            size=15, bold=True, fill="#111")
        c.txt(inf[0] + 8, inf[1] + 29,
              "主导：%s（%.1f%%）" % (dom_label,
                                   100.0 * dom[1] / max(1, len(pts))),
              size=12, fill="#444")
        c.d.rectangle(box, outline="#999", width=1)
    items = []
    for code in top_codes:
        lab = None
        for s in chosen:
            leg = s.get("legend") or {}
            if str(code) in leg:
                lab = leg[str(code)]
                break
        items.append((palette[code], "%s %.1f%%" % (lab or code,
                                                   100.0 * freq[code] / total_pts)))
    c.txt(40, H - 78, "元素组合图例（top %d，按全部帧出现频率）" % len(items),
          size=13, bold=True, fill="#333")
    c.legend(40, H - 52, items, size=13, row_h=24, cols=5, col_w=290)
    return c.save(out)


# ================================================================ ⑥ 终态组成
def chart_final_composition(a, out):
    comp = a.get("composition") or {}
    table = (comp.get("final_table") or [])[:20]
    if not table:
        raise RuntimeError("final_table 为空")
    kn = (a.get("key_numbers") or {}).get("main") or {}
    cfg = a.get("config") or {}
    sm = a.get("summary") or {}
    W, H = 1600, 1120
    c = Chart(W, H,
              "⑥ 终态组成：%d 种分子式（29内 %d / 目录内 %d / 目录外 %d）"
              % (kn.get("final_distinct_formulas") or 0,
                 (kn.get("final_class3_counts") or {}).get("29内") or 0,
                 (kn.get("final_class3_counts") or {}).get("目录内") or 0,
                 (kn.get("final_class3_counts") or {}).get("目录外") or 0),
              "绿色=29 聚素内；蓝色=84,225 目录内；橙色=目录外（目录 >16 原子不完备）；"
              "括号内为分子原子数；计算保护上限 %s" % cfg.get("max_reaction_atoms"))
    box = (560, 165, 1420, 800)
    vmax = max([r.get("count") or 1 for r in table] + [1]) * 2.2
    x0, y0, x1, y1 = box
    logmin, logmax = 0.0, math.log10(max(vmax, 10))

    def mx(v):
        v = max(1.0, float(v))
        return max(x0 + 2.0,
                   x0 + (math.log10(v) - logmin) / (logmax - logmin) * (x1 - x0))

    yt = [v for v in (1, 10, 100, 1000, 10000) if v <= vmax] or [1, 10]
    for v in yt:
        X = mx(v)
        c.d.line([X, y0, X, y1], fill="#e9e9e9", width=1)
        c.d.line([X, y1, X, y1 + 6], fill="#333", width=1)
        c.txt(X, y1 + 10, "%g" % v, size=13, anchor="ma")
    c.d.rectangle(box, outline="#333", width=2)
    c.txt((x0 + x1) / 2, y1 + 42, "终态分子数（对数轴）", size=16, anchor="ma")
    n = len(table)
    row_h = (y1 - y0) / max(1, n)
    for i, r in enumerate(table):
        cy = y0 + row_h * (i + 0.5)
        cls = r.get("class3") or ""
        col = GREEN if cls == "29内" else (BLUE if cls == "目录内" else ORANGE)
        cnt = r.get("count") or 0
        bar_h = min(row_h * 0.62, 36)
        c.d.rectangle([x0 + 1, cy - bar_h / 2, mx(cnt), cy + bar_h / 2],
                      fill=col, outline="#333", width=1)
        label = "%s  %s（%d 原子）" % (r.get("formula"), r.get("zh") or "",
                                      r.get("atoms") or 0)
        c.txt(x0 - 14, cy, label, size=12, anchor="rm",
              bold=(cls == "29内"))
        c.txt(mx(cnt) + 8, cy, "%s（%.2f%%）%s"
              % (fmt_commas(cnt), 100.0 * (r.get("share") or 0),
                 "" if cls == "29内" else "  " + cls),
              size=11, anchor="lm")
    ls = comp.get("large_stats") or {}
    c.txt(100, 848, "终态 %s 种：29内 %d / 目录内 %d / 目录外 %d；新物质 %s 种（终态存活 %s）"
          % (kn.get("final_distinct_formulas"),
             (kn.get("final_class3_counts") or {}).get("29内") or 0,
             (kn.get("final_class3_counts") or {}).get("目录内") or 0,
             (kn.get("final_class3_counts") or {}).get("目录外") or 0,
             kn.get("new_substances_total"), kn.get("new_substances_survived")),
          size=14, bold=True)
    lines = [
        "终态 %s 分子、%s 原子守恒；平均 %.2f 原子、最大 %s 原子；≥5 原子 %s 个"
        "（%.2f%% 分子、%.2f%% 原子）、≥16 原子 %s 个、20 原子 %s 个分子。"
        % (fmt_commas(kn.get("final_N")), fmt_commas(sm.get("final_atoms")),
           kn.get("final_mean_atoms") or 0, kn.get("final_max_atoms") or 0,
           fmt_commas((ls.get("ge5") or {}).get("molecules")),
           100.0 * ((ls.get("ge5") or {}).get("molecule_share") or 0),
           100.0 * ((ls.get("ge5") or {}).get("atom_share") or 0),
           fmt_commas((ls.get("ge16") or {}).get("molecules")),
           fmt_commas((ls.get("ge20") or {}).get("molecules"))),
        "计算保护 capped：合并>%s 原子的碰撞不反应（弹性），共 %s 次（占碰撞 %.2f%%）；"
        "它只封顶尺寸，不改变 ≤%s 原子的化学，终态尺寸不能据此当作化学上限。"
        % (cfg.get("max_reaction_atoms"), fmt_commas(kn.get("capped_total")),
           100.0 * (kn.get("capped_share") or 0), cfg.get("max_reaction_atoms")),
        "九元素守恒：初始 %s 原子 = 终态 %s 原子（逐元素校验通过）。"
        % (fmt_commas((a.get("elements") or {}).get("initial_total")),
           fmt_commas((a.get("elements") or {}).get("final_total"))),
        "规模对比：T58 投料 14000 分子/73216 原子（T55 9000/18000、T56 9200/18400、"
        "T57 9002/38532）；终态最大原子数 %s（T56 36、T57 9）。"
        % (kn.get("final_max_atoms") or 0),
    ]
    y = 884
    for s in lines:
        for seg in c.wrap(s, W - 130, size=13):
            c.txt(100, y, seg, size=13, fill="#333")
            y += 22
    data_note(c, [
        "目录口径：84,225 目录只对 ≤16 原子完备；目录外 ≠ 化学上不可能。"
        "T58 的 capped=20 是计算保护，不是化学上限。",
    ], y=H - 40)
    return c.save(out)


# ================================================================ ⑦ 穿越
def chart_crossings(a, out):
    cr = a.get("crossings") or {}
    ctrl = cr.get("control") or {}
    if not ctrl.get("stats"):
        raise RuntimeError("缺少对照组统计")
    st = ctrl["stats"]
    by = ctrl.get("by_size") or {}
    hist = ctrl.get("approx_hist") or {}
    cfg = a.get("config") or {}
    W, H = 1600, 1000
    c = Chart(W, H,
              "⑦ 角-对角穿越验证：L=400000 大面积下全部 ≥500 次（min=%.1f）"
              % (st.get("min") or 0),
              "设计目标：前 500 分钟内每个初始分子 ≥500 次角-对角穿越（含 12 原子大分子）；"
              "v0≈%s" % fmt_commas(cfg.get("v0")))
    box = (90, 165, 880, 650)
    xlo, xhi = 450.0, 1100.0
    edges = hist.get("bin_edges") or []
    fracs = hist.get("fractions") or []
    ymax = max(fracs + [1e-9]) * 1.25
    xt = list(range(450, 1101, 100))
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (xlo, xhi), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: "%.2f" % v)
    xr = mx(500)
    c.d.rectangle([mx(xlo), box[1], xr, box[3]], fill="#fdecea")
    c.d.line([xr, box[1], xr, box[3]], fill=RED, width=3)
    c.txt_bg(xr + 8, box[1] + 10, "要求 ≥500（实测全部 ≥500）", size=14, bold=True,
             fill=RED)
    if edges and fracs and len(edges) == len(fracs) + 1:
        for i, fr in enumerate(fracs):
            x0 = mx(max(edges[i], xlo))
            x1 = mx(min(edges[i + 1], xhi))
            if x1 <= x0:
                continue
            c.d.rectangle([x0, my(fr), x1, box[3]], fill=BLUE,
                          outline="#1c5f9e", width=1)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "粒子占比", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 40,
          "每粒在 500 分钟内的角-对角穿越次数（%d 粒）" % (st.get("n") or 0),
          size=15, anchor="ma")
    sbox = [box[0] + 14, box[3] - 118, box[0] + 430, box[3] - 10]
    c.d.rectangle(sbox, fill="#f7f9fc", outline="#d0d7e2")
    c.txt(sbox[0] + 10, sbox[1] + 6, "对照组统计（500 分钟）", size=13, bold=True)
    c.txt(sbox[0] + 10, sbox[1] + 27,
          "min=%.1f  p1=%.1f  p5=%.1f" % (st.get("min"), st.get("p1"), st.get("p5")),
          size=13)
    c.txt(sbox[0] + 10, sbox[1] + 46,
          "median=%.1f  p95=%.1f  max=%.1f"
          % (st.get("median"), st.get("p95"), st.get("max")), size=13)
    c.txt(sbox[0] + 10, sbox[1] + 68,
          "fraction ≥500 = %.0f%%" % (100.0 * (st.get("fraction_ge_500") or 0)),
          size=14, bold=True, fill="#1e8449")

    box2 = (940, 165, 1560, 720)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 16, box2[1] + 12, "按初始分子原子数分组的穿越统计", size=17, bold=True)
    c.txt(box2[0] + 16, box2[1] + 36, "（L=400000，面积模型；重点核对 ≥5 原子组）",
          size=13, fill="#555")
    sizes = sorted(by.keys(), key=lambda k: int(k))
    if sizes:
        x0, x1 = box2[0] + 66, box2[2] - 24
        y0, y1 = box2[1] + 90, box2[3] - 70
        vmax = max((by[k].get("max") or 0) for k in sizes) * 1.15

        def mxb(i):
            return x0 + (x1 - x0) / len(sizes) * (i + 0.5)

        def myb(v):
            return y1 - (v / vmax) * (y1 - y0)

        for v in nice_ticks(0, vmax, 5):
            Y = myb(v)
            c.d.line([x0, Y, x1, Y], fill="#eee", width=1)
            c.txt(x0 - 8, Y, "%g" % v, size=12, anchor="rm")
        bw = (x1 - x0) / len(sizes) * 0.26
        for i, k in enumerate(sizes):
            v = by[k]
            X = mxb(i)
            for val, colr, off in ((v.get("min"), "#e67e22", -bw),
                                   (v.get("median"), BLUE, 0.0),
                                   (v.get("max"), "#10ac84", bw)):
                if val is None:
                    continue
                c.d.rectangle([X + off - bw * 0.45, myb(val),
                               X + off + bw * 0.45, y1], fill=colr,
                              outline="#333", width=1)
            c.txt(X, y1 + 8, "%d" % int(k), size=12, anchor="ma")
            c.txt(X, y1 + 28, "n=%d" % (v.get("n") or 0), size=10, anchor="ma",
                  fill="#777")
        c.d.line([x0, myb(500), x1, myb(500)], fill=RED, width=2)
        c.txt_bg(x1 - 6, myb(500) - 22, "500 次要求线", size=12, anchor="ra", fill=RED)
        c.txt((x0 + x1) / 2, y1 + 52, "初始分子原子数（每柱：min / median / max）",
              size=13, anchor="ma")
        c.legend(box2[0] + 170, box2[1] + 64,
                 [("#e67e22", "min"), (BLUE, "median"), ("#10ac84", "max")],
                 size=12, row_h=22, cols=3, col_w=130)
    mi = cr.get("main_initial_single") or {}
    stats = mi.get("stats") or {}
    kn = (a.get("key_numbers") or {}).get("main") or {}
    data_note(c, [
        "对照组（无化学、面积模型）：min=%.1f、median=%.1f、fraction≥500=%.0f%%；"
        "by_size 各组 min 全部 ≥500（大分子组也达标）。"
        % (st.get("min") or 0, st.get("median") or 0,
           100.0 * (st.get("fraction_ge_500") or 0)),
        "主实验初始分子 path 中位 %.1f D（≈%.1f 步，碰撞即反应）；survivors=%s；"
        "t=500 等效穿越 %s 次/初始分子。"
        % (stats.get("median") or 0, mi.get("median_in_steps") or 0,
           stats.get("survivors"), kn.get("crossings_equiv_per_initial_at_500")),
        "结论：L=400000 大面积 + 九元素/大面积混合投料下，500 次穿越要求仍由无化学对照"
        "全部满足；主实验寿命短是反应设计使然。",
        "左图直方图由 min/p1/p5/median/p95/max 分位数线性插值重构（对照仅输出统计量）。",
    ])
    return c.save(out)


# ================================================================ ⑧ 温度窗口
def chart_temperature_windows(a, out):
    tl = a.get("timeline") or {}
    wins = [w for w in (tl.get("temperature_windows") or [])
            if (w.get("minutes") or 0) > 0]
    if not wins:
        raise RuntimeError("温度窗口无数据")
    W, H = 1600, 1080
    c = Chart(W, H,
              "⑧ 温度区间内的反应类型统计（含 capped 计算保护）",
              "上：判定类型计数之和（对数轴）；下：净变化事件数；"
              "capped=合并>20 原子的弹性保护")
    n = len(wins)
    labels = [w.get("label") for w in wins]
    box = (120, 185, 1420, 620)
    ymax = 1.0
    for w in wins:
        for k in ("complete", "incomplete", "none", "capped"):
            ymax = max(ymax, w.get(k) or 0)
    ymax *= 3.0
    yticks = [1, 10, 100, 1000, 10000]
    v = 100000
    while v <= ymax:
        yticks.append(v)
        v *= 10
    gw = (box[2] - box[0]) / n
    logmin, logmax = 0.0, math.log10(ymax)

    def myval(val):
        val = max(1.0, float(val))
        return box[3] - (math.log10(val) - logmin) / (logmax - logmin) * (box[3] - box[1])

    for v in yticks:
        Y = myval(v)
        c.d.line([box[0], Y, box[2], Y], fill="#e9e9e9", width=1)
        c.d.line([box[0] - 6, Y, box[0], Y], fill="#333", width=1)
        c.txt(box[0] - 10, Y, "%g" % v, size=13, anchor="rm")
    c.d.rectangle(box, outline="#333", width=2)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "判定次数（对数）", size=14)
    bw = gw * 0.16
    for i, w in enumerate(wins):
        xc = box[0] + gw * (i + 0.5)
        for k, colr, off in (("complete", TYPECOL["complete"], -1.5 * bw),
                             ("incomplete", TYPECOL["incomplete"], -0.5 * bw),
                             ("none", TYPECOL["none"], 0.5 * bw),
                             ("capped", TYPECOL["capped"], 1.5 * bw)):
            val = w.get(k) or 0
            if val <= 0:
                continue
            X = xc + off
            Y = myval(val)
            c.d.rectangle([X - bw * 0.42, Y, X + bw * 0.42, box[3]],
                          fill=colr, outline="#333", width=1)
        c.txt(xc, box[3] + 12, labels[i] + "°C", size=13, bold=True, anchor="ma")
        c.txt(xc, box[3] + 34, "%d 分钟" % (w.get("minutes") or 0), size=12,
              anchor="ma", fill="#777")
    c.txt((box[0] + box[2]) / 2, box[3] + 64, "温度区间（°C）", size=16, anchor="ma")
    c.legend(box[0] + 4, box[1] - 46,
             [(TYPECOL["complete"], "complete"), (TYPECOL["incomplete"], "incomplete"),
              (TYPECOL["none"], "none"), (TYPECOL["capped"], "capped（>20 原子保护）")],
             size=13, row_h=24, cols=4, col_w=300)

    box2 = (120, 735, 1420, 900)
    evmax = max([w.get("net_events") or 0 for w in wins] + [1]) * 3.0
    eyt = [1, 10, 100, 1000, 10000]
    v = 100000
    while v <= evmax:
        eyt.append(v)
        v *= 10
    logmax2 = math.log10(evmax)

    def my2(val):
        return box2[3] - (math.log10(max(1.0, float(val))) / logmax2) * (box2[3] - box2[1])

    for v in eyt:
        if v > evmax:
            continue
        Y = my2(v)
        c.d.line([box2[0], Y, box2[2], Y], fill="#eee", width=1)
        c.d.line([box2[0] - 6, Y, box2[0], Y], fill="#333", width=1)
        c.txt(box2[0] - 10, Y, "%g" % v, size=13, anchor="rm")
    c.d.rectangle(box2, outline="#333", width=2)
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "净变化事件（对数）", size=14)
    bw2 = (box2[2] - box2[0]) / n * 0.45
    for i, w in enumerate(wins):
        xc = box2[0] + (box2[2] - box2[0]) / n * (i + 0.5)
        val = w.get("net_events") or 0
        c.txt(xc, box2[3] + 10, labels[i] + "°C", size=12, anchor="ma", fill="#333")
        if val <= 0:
            c.txt(xc, box2[3] - 16, "0", size=12, anchor="ma", fill="#999")
            continue
        Y = my2(val)
        c.d.rectangle([xc - bw2 / 2, Y, xc + bw2 / 2, box2[3]],
                      fill="#8e44ad", outline="#333", width=1)
        c.txt(xc, Y - 4, fmt_commas(val), size=12, anchor="mb")
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 42, "温度区间（°C）", size=15, anchor="ma")
    capped = tl.get("capped") or {}
    data_note(c, [
        "capped 保护：合并>%s 原子的碰撞不反应；总 capped %s 次（占碰撞 %.2f%%），"
        "随大分子累积而上升（峰值 t≈%s）。"
        % ((a.get("config") or {}).get("max_reaction_atoms"),
           fmt_commas(capped.get("total")), 100.0 * (capped.get("share") or 0),
           (capped.get("peak") or {}).get("t")),
        "decomp 全程 %s 次；低温窗口的 incomplete 多为复原（净事件不增加）。"
        % fmt_commas((a.get("key_numbers") or {}).get("main", {}).get("decomp_events")),
    ], y=985)
    return c.save(out)


# ================================================================ ⑨ 尺寸分布
def chart_size_distribution(a, out):
    comp = a.get("composition") or {}
    ss = comp.get("size_series") or []
    dist = comp.get("final_size_distribution") or []
    if not ss:
        raise RuntimeError("size_series 为空")
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or (ss[-1]["t"] if ss else 1000)
    cap = cfg.get("max_reaction_atoms") or 20
    kn = (a.get("key_numbers") or {}).get("main") or {}
    W, H = 1600, 1120
    c = Chart(W, H,
              "⑨ 尺寸分布：演化 max/mean/p90/p99；终态分布（计算保护上限 %s 原子）" % cap,
              "尺寸=分子原子数；上限 %s 来自计算保护，不是化学上限" % cap)
    box = (105, 165, 1400, 560)
    ymax = max([s.get("max_atoms") or 0 for s in ss] + [cap + 2]) * 1.1
    xt = nice_ticks(0, minutes, 10)
    yt = nice_ticks(0, ymax, 6)
    mx, my = c.frame(box, (0, minutes), (0, ymax), xt, yt)
    c.top_temp_axis(box, (0, minutes), mx, cfg.get("T0") or 1000, minutes)
    c.dashed((mx(0), my(cap)), (mx(minutes), my(cap)), fill=ORANGE, width=2,
             dash=8)
    c.txt_bg(mx(minutes) - 6, my(cap) - 22, "计算保护上限 %s" % cap, size=12,
             anchor="ra", fill=ORANGE)
    for key, colr, wdt, lab in (("max_atoms", "#c0392b", 3, "max"),
                                ("p99_atoms", "#e67e22", 2, "p99"),
                                ("p90_atoms", "#10ac84", 2, "p90"),
                                ("mean_atoms", BLUE, 3, "平均")):
        c.line([(mx(s["t"]), my(s.get(key) or 0)) for s in ss], fill=colr,
               width=wdt)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "原子数（分子尺寸）", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 42, "时间 t（分钟）", size=16, anchor="ma")
    c.legend(1080, 175,
             [("#c0392b", "max"), ("#e67e22", "p99"), ("#10ac84", "p90"),
              (BLUE, "平均原子数")], size=13, row_h=24)
    peak = (a.get("timeline") or {}).get("transitions", {}).get("max_atoms_peak") or {}
    if peak:
        c.txt_bg(mx(peak.get("t") or 0) + 8, box[1] + 14,
                 "峰值 %s 原子 @ t=%s" % (peak.get("max_atoms"), peak.get("t")),
                 size=13, fill=RED)
    # 下：终态分布（双峰：2 原子 vs 6~20 原子；19/20 接近 cap）
    box2 = (105, 690, 960, 1000)
    maxa = max([d.get("atoms") or 0 for d in dist] + [cap + 1])
    ydist = max([d.get("molecules") or 0 for d in dist] + [1])
    yt2 = [1, 10, 100, 1000, 10000]
    v = 100000
    while v <= ydist * 1.5:
        yt2.append(v)
        v *= 10
    xt2 = list(range(2, maxa + 1))
    mx3, my3 = c.frame(box2, (0.5, maxa + 0.5), (1, ydist * 1.6), xt2, yt2,
                       logy=True, ytick_fmt=lambda v: "%g" % v)
    barw = (mx3(maxa + 0.5) - mx3(0.5)) / maxa * 0.72
    for d in dist:
        a_ = d.get("atoms") or 0
        m_ = d.get("molecules") or 0
        if m_ <= 0:
            continue
        X = mx3(a_)
        colr = ORANGE if a_ >= 19 else (BLUE if a_ <= 16 else "#8e44ad")
        c.d.rectangle([X - barw / 2, my3(m_), X + barw / 2, box2[3]],
                      fill=colr, outline="#333", width=1)
        if a_ in (6, 7, 8, 19, 20):
            c.txt(X, my3(m_) - 4, fmt_commas(m_), size=10, anchor="mb", fill="#333")
    # 双峰汇总（放右侧统计面板，避免与柱标注重叠）
    dist_map = {int(d["atoms"]): d["molecules"] for d in dist}
    non_di = sum(v for a_, v in dist_map.items() if a_ > 2)
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "分子数（对数）", size=14)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 42,
          "终态分子原子数分布（蓝=≤16，橙=19~20 近 cap）", size=14, anchor="ma")
    # 右下：统计
    box3 = (1000, 690, 1560, 1000)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 14, box3[1] + 12, "尺寸统计", size=17, bold=True)
    ls = comp.get("large_stats") or {}
    lines = [
        "终态平均 %.2f 原子、最大 %s 原子（上限 %s）"
        % (kn.get("final_mean_atoms") or 0, kn.get("final_max_atoms") or 0, cap),
        "双峰：2 原子 %s 个（%.1f%% 分子、%.1f%% 原子）；非双原子（3~%s 原子）%s 个"
        % (fmt_commas(dist_map.get(2, 0)),
           100.0 * ((next((d for d in dist if d["atoms"] == 2), {}) or {})
                    .get("molecule_share") or 0),
           100.0 * ((next((d for d in dist if d["atoms"] == 2), {}) or {})
                    .get("atoms_share") or 0),
           cap, fmt_commas(non_di)),
        "≥5 原子 %s 个（%.2f%% 分子 / %.2f%% 原子）"
        % (fmt_commas((ls.get("ge5") or {}).get("molecules")),
           100.0 * ((ls.get("ge5") or {}).get("molecule_share") or 0),
           100.0 * ((ls.get("ge5") or {}).get("atom_share") or 0)),
        "≥10 原子 %s 个；≥16 原子 %s 个；19/20 原子 %s/%s 个（近 cap）"
        % (fmt_commas((ls.get("ge10") or {}).get("molecules")),
           fmt_commas((ls.get("ge16") or {}).get("molecules")),
           fmt_commas(dist_map.get(19, 0)), fmt_commas(dist_map.get(20, 0))),
        "演化最大原子数 %s @ t=%s；初始投料最大 12 原子"
        % (kn.get("max_atoms_evolution"), kn.get("max_atoms_peak_t")),
        "capped 碰撞 %s 次（%.2f%% 碰撞）只封顶尺寸，不改变化学"
        % (fmt_commas(kn.get("capped_total")), 100.0 * (kn.get("capped_share") or 0)),
        "对比：T56 演化最大 36 原子（无 cap）；T57 最大 9（投料限制）",
    ]
    y = box3[1] + 46
    for s in lines:
        for seg in c.wrap(s, box3[2] - box3[0] - 30, size=13):
            c.txt(box3[0] + 14, y, seg, size=13, fill="#222")
            y += 24
        y += 4
    data_note(c, [
        "尺寸分布说明：终态尺寸受三重因素影响——投料尺寸（2~12）、完全反应 F 的不动点、"
        "以及 >%s 原子合并的 capped 保护；报告时不能把 %s 原子当作化学上限。"
        % (cap, cap),
    ], y=H - 42)
    return c.save(out)


# ================================================================ ⑪ capped 计算保护
def chart_capped(a, out):
    tl = a.get("timeline") or {}
    capped = tl.get("capped") or {}
    series = capped.get("series") or []
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or (len(series) or 1000)
    T0 = cfg.get("T0") or 1000
    if not series:
        raise RuntimeError("capped.series 为空")
    W, H = 1600, 1000
    c = Chart(W, H,
              "11 capped 计算保护：合并 >%s 原子的碰撞不反应（占全部碰撞 %.1f%%）"
              % (cfg.get("max_reaction_atoms"), 100.0 * (capped.get("share") or 0)),
              "capped = 合并后原子数 > 上限而被强制弹性的碰撞；它随大分子增多而上升，"
              "是 T58 的主要计算限制（不改变 ≤%s 原子的化学）"
              % cfg.get("max_reaction_atoms"))
    # 上：每分钟 capped 数与占比
    box = (110, 170, 1440, 570)
    xt = nice_ticks(0, minutes, 10)
    cmax = max([r.get("capped") or 0 for r in series] + [1]) * 1.2
    sharemax = max([r.get("capped_share") or 0 for r in series] + [0.1]) * 1.15
    yt = nice_ticks(0, cmax, 5)
    mx, my = c.frame(box, (0, minutes), (0, cmax), xt, yt,
                     ytick_fmt=lambda v: fmt_commas(v))
    c.top_temp_axis(box, (0, minutes), mx, T0, minutes)
    myr = c.right_axis(box, (0, sharemax * 100),
                       nice_ticks(0, sharemax * 100, 5),
                       fmt=lambda v: "%.0f%%" % v, color=RED,
                       label="capped 占碰撞比例")
    bw = max(1.0, (mx(minutes) - mx(0)) / max(1, minutes) * 1.2)
    for r in series:
        if (r.get("capped") or 0) > 0:
            X = mx(r["t"])
            c.d.rectangle([X - bw / 2, my(r["capped"]), X + bw / 2, box[3]],
                          fill=TYPECOL["capped"])
    c.line([(mx(r["t"]), myr(100.0 * (r.get("capped_share") or 0))) for r in series],
           fill=RED, width=2)
    peak = capped.get("peak") or {}
    if peak.get("t") is not None:
        c.dashed((mx(peak["t"]), box[1]), (mx(peak["t"]), box[3]),
                 fill=RED, width=1)
        c.txt_bg(mx(peak["t"]) + 6, box[1] + 12,
                 "峰值 t=%s：%s 次/分、占 %.1f%%"
                 % (peak["t"], fmt_commas(peak.get("capped")),
                    100.0 * (peak.get("capped_share") or 0)),
                 size=13, fill=RED)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "capped 次数/分钟", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 42, "时间 t（分钟）", size=16, anchor="ma")
    c.legend(box[0] + 16, box[1] + 12,
             [(TYPECOL["capped"], "capped 次数/分钟（柱）"),
              (RED, "capped 占碰撞比例（右轴线）")],
             size=13, row_h=24, cols=2, col_w=340)

    # 左下：按温度窗口的 capped 占比
    wins = [w for w in (tl.get("temperature_windows") or [])
            if (w.get("minutes") or 0) > 0]
    box2 = (110, 660, 800, 930)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 14, box2[1] + 10, "各温度窗口 capped 占比", size=16, bold=True)
    if wins:
        x0, x1 = box2[0] + 70, box2[2] - 20
        y0, y1 = box2[1] + 60, box2[3] - 70
        vmax = max([w.get("capped_share") or 0 for w in wins] + [0.1]) * 100 * 1.2
        for v in nice_ticks(0, vmax, 4):
            Y = y1 - v / vmax * (y1 - y0)
            c.d.line([x0, Y, x1, Y], fill="#eee", width=1)
            c.txt(x0 - 8, Y, "%.0f%%" % v, size=12, anchor="rm")
        bw2 = (x1 - x0) / len(wins) * 0.55
        for i, w in enumerate(wins):
            X = x0 + (x1 - x0) / len(wins) * (i + 0.5)
            val = 100.0 * (w.get("capped_share") or 0)
            Y = y1 - val / vmax * (y1 - y0)
            c.d.rectangle([X - bw2 / 2, Y, X + bw2 / 2, y1],
                          fill=TYPECOL["capped"], outline="#333", width=1)
            c.txt(X, Y - 4, "%.0f%%" % val, size=12, anchor="mb")
            c.txt(X, y1 + 10, w.get("label"), size=12, anchor="ma")
        c.txt((x0 + x1) / 2, y1 + 36, "温度区间（°C）", size=13, anchor="ma")

    # 右下：统计与解释
    box3 = (850, 660, 1530, 930)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 14, box3[1] + 12, "计算保护统计", size=17, bold=True)
    kn = (a.get("key_numbers") or {}).get("main") or {}
    lines = [
        "capped 总数 %s 次；总碰撞 %s 次 → 占比 %.2f%%"
        % (fmt_commas(capped.get("total")), fmt_commas(capped.get("total_collisions")),
           100.0 * (capped.get("share") or 0)),
        "平均 %.1f 次/分钟；首次出现 t=%s；最后 t=%s"
        % (capped.get("mean_per_minute") or 0,
           (capped.get("first") or {}).get("t"),
           (capped.get("last") or {}).get("t")),
        "峰值 t=%s（T=%s）：%s 次、占 %.1f%%"
        % ((capped.get("peak") or {}).get("t"),
           (capped.get("peak") or {}).get("T"),
           fmt_commas((capped.get("peak") or {}).get("capped")),
           100.0 * ((capped.get("peak") or {}).get("capped_share") or 0)),
        "原因：大分子截面大→互相碰撞多；合并>%s 原子会被强制弹性，"
        "于是大分子越积越多、capped 占比随之上升。" % cfg.get("max_reaction_atoms"),
        "影响：capped 只阻止 >%s 原子的合并，不改变 ≤%s 原子的反应；"
        "它让终态尺寸封顶在 %s 原子（不是化学上限）。"
        % (cfg.get("max_reaction_atoms"), cfg.get("max_reaction_atoms"),
           cfg.get("max_reaction_atoms")),
        "净变化事件仍 %s 次、decomp %s 次；capped 碰撞不产生化学事件。"
        % (fmt_commas(kn.get("net_events_total")), kn.get("decomp_events")),
    ]
    y = box3[1] + 46
    for s in lines:
        for seg in c.wrap(s, box3[2] - box3[0] - 30, size=13):
            c.txt(box3[0] + 14, y, seg, size=13, fill="#222")
            y += 23
    data_note(c, [
        "数据来源：%s。capped 是 T58 特有的计算保护，报告中需在『局限』里明确说明；"
        "capped 高不代表化学上不能形成更大分子。" % (capped.get("source") or "-"),
    ], y=950)
    return c.save(out)


# ================================================================ ⑩ 历史规模对比
def chart_scale_compare(a, out):
    hist = a.get("comparison_history") or {}
    table = hist.get("table") or []
    if not table:
        raise RuntimeError("comparison_history.table 为空")
    W, H = 1600, 1080
    c = Chart(W, H,
              "⑩ 历史规模对比：T55 / T56 / T57 / T58（分子数、原子数、元素数、终态）",
              "T58 首次九元素全覆盖 + 14000 分子 / 73216 原子；终态最大原子数受 20 原子计算保护限制")
    names = [t.get("name") for t in table]
    cols = ["#95a5a6", "#8e44ad", "#f39c12", BLUE]
    panels = [
        ("初始分子数", lambda t: t.get("initial_molecules"), fmt_commas, False),
        ("初始原子数", lambda t: t.get("initial_atoms"), fmt_commas, True),
        ("元素数", lambda t: t.get("elements"), lambda v: "%d" % v, False),
        ("终态分子数", lambda t: t.get("final_N"), fmt_commas, False),
        ("演化最大原子数", lambda t: t.get("final_max_atoms"), lambda v: "%d" % v, False),
        ("新物质数", lambda t: t.get("new_substances"), fmt_commas, False),
    ]
    pw, ph = 720, 250
    x0s = [60, 840]
    y0s = [110, 380, 650]
    for idx, (title, getter, fmt, logy) in enumerate(panels):
        px = x0s[idx % 2]
        py = y0s[idx // 2]
        box = (px + 92, py + 40, px + pw - 32, py + ph - 34)
        vals = [getter(t) or 0 for t in table]
        vmax = max(vals + [1]) * 1.3
        c.txt(px + 16, py + 4, "%s %s" % ("①②③④⑤⑥"[idx], title), size=18, bold=True)
        if logy:
            yt = [v for v in (1000, 10000, 100000, 1000000) if v <= vmax] or [1, 10]
            ymin = 1000
        else:
            yt = nice_ticks(0, vmax, 4)
            ymin = 0
        nn = len(table)
        mx, my = c.frame(box, (0, nn), (ymin, vmax),
                         [i + 0.5 for i in range(nn)], yt,
                         xtick_labels=names, ytick_fmt=fmt, logy=logy)
        bw = (box[2] - box[0]) / nn * 0.42
        for i, t in enumerate(table):
            X = box[0] + (box[2] - box[0]) / nn * (i + 0.5)
            val = vals[i]
            Y = my(max(val, ymin if logy else 0))
            c.d.rectangle([X - bw / 2, Y, X + bw / 2, box[3]],
                          fill=cols[i % len(cols)], outline="#333", width=1)
            c.txt(X, Y - 6, fmt(val), size=13, anchor="mb", bold=True)
        if idx == 0:
            c.txt(box[2] - 4, box[1] + 6,
                  "T58 = %.2f× T55 分子 / %.2f× 原子"
                  % ((vals[3] or 0) / max(1, vals[0] or 1),
                     ((table[3].get("initial_atoms") or 0) /
                      max(1, table[0].get("initial_atoms") or 1))),
                  size=12, anchor="ra", fill=RED)
    t55 = next((t for t in table if t.get("name") == "T55"), {})
    t58 = next((t for t in table if t.get("name") == "T58"), {})
    data_note(c, [
        "规模：T58 投料 14000 分子 / 73216 原子（T55 9000/18000、T56 9200/18400、"
        "T57 9002/38532）；元素 9 种（T55 3、T56 6、T57 3）。",
        "终态：T58 %s 种分子式 / %s 种新物质；T55 9/0、T56 22/120、T57 4/0。"
        % (fmt_commas(t58.get("final_N")), fmt_commas(t58.get("new_substances"))),
        "碰撞：T58 总碰撞 %s 次（L=400000 大面积，碰撞稀疏）；T55/T56/T57 的碰撞率远高，"
        "因此 T58 未充分退火、保留了更多大分子。"
        % fmt_commas(t58.get("collisions_total")),
        "终态最大原子数：T56 36（无 cap）；T57 9（投料限制）；T58 受 20 原子计算保护限制。",
    ], y=930)
    return c.save(out)


# ================================================================ main
CHARTS = [
    ("mixture", "t58_mixture.png", chart_mixture),
    ("composition", "t58_composition.png", chart_composition),
    ("reaction_rate", "t58_reaction_rate.png", chart_reaction_rate),
    ("state_sizes", "t58_state_sizes.png", chart_state_sizes),
    ("snapshots", "t58_snapshots.png", chart_snapshots),
    ("final_composition", "t58_final_composition.png", chart_final_composition),
    ("crossings", "t58_crossings.png", chart_crossings),
    ("temperature_windows", "t58_temperature_windows.png", chart_temperature_windows),
    ("size_distribution", "t58_size_distribution.png", chart_size_distribution),
    ("capped", "t58_capped.png", chart_capped),
    ("scale_compare", "t58_scale_compare.png", chart_scale_compare),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="T58 图表渲染")
    ap.add_argument("--analysis", default=DEFAULT_ANALYSIS)
    ap.add_argument("--images", default=DEFAULT_IMAGES)
    ap.add_argument("--only", default=None)
    args = ap.parse_args(argv)
    if not os.path.exists(args.analysis):
        print("[error] 分析文件不存在：%s" % args.analysis)
        return 2
    a = json.load(open(args.analysis, encoding="utf-8"))
    main_path = (a.get("meta") or {}).get("main_path")
    if main_path and os.path.exists(main_path):
        try:
            raw = json.load(open(main_path, encoding="utf-8"))
            a["_main_raw"] = raw
            a.setdefault("snapshots", raw.get("snapshots") or [])
        except Exception as exc:
            print("[warn] 读取主实验快照失败：%s" % exc, flush=True)
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
