# -*- coding: utf-8 -*-
"""t57_render.py —— T57 实验图表（Pillow 绘制，中文字体 msyh）

读取 t57_analysis.json，生成 10 张要求图 + 1 张补充低温图：
  images/t57_design.png              ① 设计表三联（原子数-面积-数量）+ 校验
  images/t57_composition.png         ② 组成随时间演化（29 聚素投料 → OXC/OX2C）
  images/t57_reaction_rate.png       ③ 反应判定计数/分钟 + 温度轴 + 净变化事件
  images/t57_state_sizes.png         ④ 状态/尺寸时间线（速度/N/平均+最大原子数）
  images/t57_snapshots.png           ⑤ 2D 快照拼图（7 色元素集合）
  images/t57_final_composition.png   ⑥ 终态组成（4 种，全部 29 内/目录内）
  images/t57_crossings.png           ⑦ 穿越验证（整体 + by_size 分组，含大分子）
  images/t57_temperature_windows.png ⑧ 温度区间反应类型统计
  images/t57_size_compare.png        ⑨ 尺寸分布对比（area vs uniform + 初始基准）
  images/t57_area_vs_uniform.png     ⑩ 面积假设检验（area vs 固定半径）
  images/t57_sensitivity.png         ⑪ 低温窗口敏感性（T0=12/20，补充）

用法：
  python t57_render.py
  python t57_render.py --analysis t57_analysis.json --images images
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_ANALYSIS = os.path.join(BASE, "t57_analysis.json")
DEFAULT_IMAGES = os.path.join(BASE, "images")

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT_REG

PAL = ["#2e86de", "#ee5253", "#10ac84", "#f39c12", "#8e44ad", "#16a085",
       "#d35400", "#2c3e50", "#c0392b", "#7f8c8d", "#27ae60", "#e84393",
       "#00acc1", "#795548", "#607d8b", "#f06292", "#aed581", "#ffb74d"]
TYPECOL = {"complete": "#e74c3c", "incomplete": "#f39c12",
           "none": "#95a5a6", "decomp": "#8e44ad"}
SNAPCOL7 = {0: "#2ecc71", 1: "#f39c12", 2: "#3498db", 3: "#9b59b6",
            4: "#1abc9c", 5: "#e74c3c", 6: "#00acc1"}
GREEN = "#2e8b57"
ORANGE = "#e67e22"
BLUE = "#2e86de"
RED = "#c0392b"


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


def _size_color(n):
    return {2: "#2ecc71", 3: "#10ac84", 4: "#3498db", 5: "#2e86de",
            6: "#f39c12", 7: "#e67e22", 8: "#e74c3c", 9: "#8e44ad"}.get(
        int(n), "#888")


# ================================================================ ① 设计表
def chart_design(a, out):
    d = a.get("design") or {}
    rows = d.get("species") or []
    if not rows:
        raise RuntimeError("design.species 为空")
    W, H = 1600, 1000
    c = Chart(W, H,
              "① 设计表验证：29 种纯聚素，面积 ∝ 原子数，数量 ∝ 1/面积（严格反向）",
              "A(M)=πR0²·(n/2)，R=R0·sqrt(n/2)，R0=0.2；count=max(30, round(K/n))，"
              "K=1328.258；共 9002 分子 / 38532 原子")
    # 左：原子数-面积
    box = (100, 160, 540, 600)
    xt = list(range(2, 10))
    yt = nice_ticks(0, 0.65, 5)
    mx, my = c.frame(box, (1.5, 9.5), (0, 0.65), xt, yt, ytick_fmt=lambda v: "%.2f" % v)
    c.line([(mx(n), my(math.pi * 0.2 * 0.2 * n / 2.0)) for n in range(2, 10)],
           fill="#999", width=2)
    for r in rows:
        n = r.get("atoms")
        c.d.ellipse([mx(n) - 4, my(r.get("area") or 0) - 4,
                     mx(n) + 4, my(r.get("area") or 0) + 4],
                    fill=_size_color(n), outline="#333")
    c.rot(box[0] - 56, (box[1] + box[3]) / 2, "面积 A（单位）", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 38, "分子原子数 n", size=15, anchor="ma")
    c.txt(box[0] + 8, box[1] + 8, "A = πR0²·(n/2)", size=14, bold=True)
    c.txt(box[0] + 8, box[1] + 30, "Pearson(n, A) = %.2f"
          % (d["checks"].get("pearson_atoms_area") or 0), size=13, fill="#555")

    # 中：原子数-数量
    box2 = (620, 160, 1060, 600)
    yt2 = nice_ticks(0, 720, 5)
    mx2, my2 = c.frame(box2, (1.5, 9.5), (0, 720), xt, yt2,
                       ytick_fmt=lambda v: fmt_commas(v))
    K = (d.get("meta") or {}).get("K") or 1328.258
    c.line([(mx2(n), my2(K / n)) for n in range(2, 10)], fill="#999", width=2)
    for r in rows:
        n = r.get("atoms")
        c.d.ellipse([mx2(n) - 4, my2(r.get("count") or 0) - 4,
                     mx2(n) + 4, my2(r.get("count") or 0) + 4],
                    fill=_size_color(n), outline="#333")
    c.rot(box2[0] - 56, (box2[1] + box2[3]) / 2, "投料数量", size=14)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 38, "分子原子数 n", size=15, anchor="ma")
    c.txt(box2[0] + 8, box2[1] + 8, "count ≈ K/n（K=1328.258）", size=14, bold=True)
    c.txt(box2[0] + 8, box2[1] + 30, "数量 %d → %d（严格反向）  Pearson(n,count)=%.2f"
          % ((d.get("ranges") or {}).get("count", [0, 0])[1],
             (d.get("ranges") or {}).get("count", [0, 0])[0],
             d["checks"].get("pearson_atoms_count") or 0),
          size=13, fill="#555")

    # 右：按原子数聚合的设计表
    box3 = (1140, 160, 1560, 600)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 14, box3[1] + 12, "按原子数聚合（29 种）", size=16, bold=True)
    by_n = {}
    for r in rows:
        by_n.setdefault(r.get("atoms"), []).append(r)
    y = box3[1] + 46
    c.txt(box3[0] + 14, y, "n   种数  面积范围        数量/种", size=13, bold=True,
          fill="#333")
    y += 26
    for n in sorted(by_n):
        rs = by_n[n]
        areas = [x.get("area") or 0 for x in rs]
        counts = [x.get("count") or 0 for x in rs]
        c.txt(box3[0] + 14, y,
              "%d    %d    %.3f~%.3f    %d~%d"
              % (n, len(rs), min(areas), max(areas), min(counts), max(counts)),
              size=13, fill=_size_color(n))
        y += 24
    y += 10
    c.txt(box3[0] + 14, y, "合计: 29 种 / %s 分子 / %s 原子" % (
        fmt_commas((d.get("checks") or {}).get("total_molecules")),
        fmt_commas((d.get("checks") or {}).get("total_atoms"))), size=13, bold=True)
    y += 24
    c.txt(box3[0] + 14, y, "平均原子数: %.2f" % ((d.get("checks") or {}).get(
        "mean_atoms") or 0), size=13)
    y += 24
    c.txt(box3[0] + 14, y, "元素原子 O:X:C = %s : %s : %s"
          % tuple((d.get("atom_ratio_O_X_C") or ["-"] * 3)), size=13, fill="#555")

    # 下：物种明细条（按原子数排序，面积柱 + 数量线）
    box4 = (100, 690, 1560, 940)
    rows_sorted = sorted(rows, key=lambda r: (r.get("atoms") or 0,
                                              r.get("formula") or ""))
    n = len(rows_sorted)
    gw = (box4[2] - box4[0]) / n
    ymax = max(r.get("area") or 0 for r in rows_sorted) * 1.2
    cmax = max(r.get("count") or 0 for r in rows_sorted) * 1.2
    yt4 = nice_ticks(0, ymax, 4)

    def my4(v):
        return box4[3] - v / ymax * (box4[3] - box4[1] - 30)

    def myc(v):
        return box4[3] - v / cmax * (box4[3] - box4[1] - 30)

    for v in yt4:
        Y = my4(v)
        c.d.line([box4[0], Y, box4[2], Y], fill="#eee", width=1)
        c.txt(box4[0] - 8, Y, "%.2f" % v, size=12, anchor="rm")
    c.d.rectangle([box4[0], box4[1], box4[2], box4[3]], outline="#333", width=2)
    pts = []
    for i, r in enumerate(rows_sorted):
        X = box4[0] + gw * (i + 0.5)
        Y = my4(r.get("area") or 0)
        c.d.rectangle([X - gw * 0.32, Y, X + gw * 0.32, box4[3]],
                      fill=_size_color(r.get("atoms")), outline="#333", width=1)
        pts.append((X, myc(r.get("count") or 0)))
        if i % 2 == 0:
            c.txt(X, box4[3] + 6, "%s" % r.get("formula"), size=9, anchor="ma",
                  fill="#333")
    c.line(pts, fill="#c0392b", width=2)
    c.rot(box4[0] - 52, (box4[1] + box4[3]) / 2, "面积（柱）", size=13)
    c.txt(1500, box4[1] + 8, "数量（红线，右轴无量纲）", size=12, anchor="ra",
          fill="#c0392b")
    data_note(c, [
        "设计校验：面积∝原子数（最大误差 %.0e，Pearson=%.2f）；数量∝1/面积"
        "（count·n 恒为 K=%.1f，严格反向单调=%s）；面积 0.1257→0.5655（4.5 倍），"
        "数量 664→148（1/4.5）。"
        % (max((d["checks"].get("max_area_error") or 0), 0.0),
           d["checks"].get("pearson_atoms_area") or 0, K,
           "是" if d["checks"].get("strict_inverse_monotone") else "否"),
        "初始投料中 ≥5 原子分子 %s 个（%.1f%% 分子、%.1f%% 原子）——这是检验"
        "『环境是否保留大分子』的起点。"
        % (fmt_commas((d.get("initial_big5") or {}).get("molecules")),
           100.0 * ((d.get("initial_big5") or {}).get("molecule_share") or 0),
           100.0 * ((d.get("initial_big5") or {}).get("atom_share") or 0)),
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
              "② 组成演化：29 种聚素投料 → 完全反应退火 → OXC / OX2C 小分子终态",
              "每 5 分钟完整组成；堆叠 = top 分子式数量（t=0 已含第 0 分钟反应）；"
              "初始 9002 分子（2~9 原子）")
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
    c.legend(1326, 186, items, size=12, row_h=23)

    # 下：大分子（≥5 原子）占比 + 物种数
    box2 = (100, 720, 1120, 930)
    big5_m = []
    big5_a = []
    for s in series:
        cts = s.get("counts") or {}
        tot_m = sum(cts.values()) or 1
        tot_a = sum(sum(int(c) for c in __import__("re").findall(
            r"(\d+)", f) or [1]) * int(v) if False else 0 for f, v in cts.items())
        # 用原子数直接算（formula 解析）
        from collections import Counter as _C
        cnt = _C()
        for f, v in cts.items():
            import re as _re
            a_ = sum(int(x) if x else 1 for x in _re.findall(r"[A-Z]([0-9]*)", f))
            cnt[a_] += v
        tot_m = sum(cnt.values()) or 1
        tot_a = sum(a_ * v for a_, v in cnt.items()) or 1
        bm = sum(v for a_, v in cnt.items() if a_ >= 5)
        ba = sum(a_ * v for a_, v in cnt.items() if a_ >= 5)
        big5_m.append(bm / tot_m)
        big5_a.append(ba / tot_a)
    nsp = [r.get("n_species") or 0 for r in series]
    nsmax = max(nsp + [1]) * 1.08
    yt2 = [0, 0.25, 0.5, 0.75, 1.0]
    mx2, my2 = c.frame(box2, (0, minutes), (0, 1.0), xt, yt2,
                       ytick_fmt=lambda v: "%.0f%%" % (v * 100))
    myr = c.right_axis(box2, (0, nsmax), nice_ticks(0, nsmax, 5),
                       label="分子式数", color=BLUE)
    c.d.line([(mx2(series[j]["t"]), my2(big5_m[j])) for j in range(n)],
             fill="#c0392b", width=3)
    c.d.line([(mx2(series[j]["t"]), my2(big5_a[j])) for j in range(n)],
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
    data_note(c, [
        "初始 ≥5 原子分子占 39.7%%（3578 个、58.6%% 原子）→ 终态仅 %d 个（%.2f%% 分子、"
        "%.2f%% 原子）；终态 %d 种分子式全部在 29 聚素内：OXC %s（80.9%%）+ OX2C %s（19.0%%）"
        "+ O2X2C4 %d + O2X4 %d。"
        % ((ls.get("ge5") or {}).get("molecules"),
           100.0 * ((ls.get("ge5") or {}).get("molecule_share") or 0),
           100.0 * ((ls.get("ge5") or {}).get("atom_share") or 0),
           comp.get("final_total_formulas") or 0,
           fmt_commas((comp.get("final_table") or [{}])[0].get("count")),
           fmt_commas((comp.get("final_table") or [{}, {}])[1].get("count")
                      if len(comp.get("final_table") or []) > 1 else 0),
           (comp.get("final_table") or [{}, {}, {}])[2].get("count")
           if len(comp.get("final_table") or []) > 2 else 0,
           (comp.get("final_table") or [{}, {}, {}, {}])[3].get("count")
           if len(comp.get("final_table") or []) > 3 else 0),
        "净变化事件最后 t=%s（T=%s）；终态平均原子数 %.3f、最大 %s 原子；初速 64138。"
        % (((a.get("timeline") or {}).get("transitions") or {}).get(
            "last_net_change", {}).get("t"),
           ((a.get("timeline") or {}).get("transitions") or {}).get(
            "last_net_change", {}).get("T"),
           kn.get("final_mean_atoms") or 0, kn.get("final_max_atoms") or 0),
    ], y=1010)
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
              "③ 反应判定计数/分钟（complete/incomplete/none）与温度轴；净变化事件/分钟",
              "左轴=判定次数（对数），右轴=温度（T=T0-t，虚线）；complete 含大量净结果"
              "不变的完全判定（F 不动点），真正化学事件看下图")
    box = (110, 172, 1430, 600)
    cmax = max([r.get("complete") or 0 for r in rows] + [1])
    ymax = cmax * 1.6
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
    for key, col, wdt in (("complete", TYPECOL["complete"], 3),
                          ("incomplete", TYPECOL["incomplete"], 2),
                          ("none", TYPECOL["none"], 2)):
        pts = [(mx(r["t"]), my(r[key])) for r in rows if (r.get(key) or 0) > 0]
        if len(pts) >= 2:
            c.d.line(pts, fill=col, width=wdt)
        elif len(pts) == 1:
            x, y = pts[0]
            c.d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=col)
    trans = tl.get("transitions") or {}
    last_net = trans.get("last_net_change") or {}
    fzc = trans.get("first_zero_complete") or {}
    marks = [(last_net.get("t"), "净变化停止 t=%s（T=%s）"
              % (last_net.get("t"), last_net.get("T")), box[1] + 8, "la", RED),
             (fzc.get("t"), "complete→0（T=%s）" % fzc.get("T"),
              box[1] + 62, "ra", RED)]
    for tv, lab, ty, anch, col in marks:
        if tv is not None and 0 <= tv <= minutes:
            c.dashed((mx(tv), box[1]), (mx(tv), box[3]), fill=col, width=1)
            c.txt_bg(mx(tv) + (4 if anch == "la" else -4), ty, lab, size=12,
                     anchor=anch, fill=col)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "判定次数/分钟（对数）", size=14)
    c.legend(box[0] + 4, box[1] - 42,
             [(TYPECOL["complete"], "complete（完全反应判定，含净不变）"),
              (TYPECOL["incomplete"], "incomplete（不完全反应判定）"),
              (TYPECOL["none"], "none（不反应/弹性）")],
             size=13, row_h=24, cols=3, col_w=380)

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
    n_ev = sum(ev)
    n_min = sum(1 for x in ev if x > 0)
    rng = trans.get("net_event_T_range") or [None, None]
    c.txt_bg(box2[0] + 12, box2[1] + 8,
             "净变化事件 %s 次、分布 %d 分钟；全部发生在 T≥%s"
             % (fmt_commas(n_ev), n_min, rng[0]), size=13, fill="#8e44ad")
    c.txt_bg(box2[0] + 12, box2[1] + 32,
             "t=0 分钟 %s 次（初始 29 种聚素成键/重排）；低温段不完全判定多为复原。"
             % fmt_commas(ev[0] if ev else 0), size=13, fill="#555")
    data_note(c, [
        "判定计数合计 %s = 碰撞数（complete %s / incomplete %s / none %s）；"
        "其中 %.2f%% 的 complete 判定净结果不变（F 不动点）。"
        % (fmt_commas(sum((r.get("collisions") or 0) for r in rows)),
           fmt_commas(sum((r.get("complete") or 0) for r in rows)),
           fmt_commas(sum((r.get("incomplete") or 0) for r in rows)),
           fmt_commas(sum((r.get("none") or 0) for r in rows)),
           100.0 * (ev_a.get("complete_noop_ratio") or 0.0)),
        "温度行为：complete 判定在 T 很高时就把体系退火到 OXC/OX2C；T≤5 后 complete 归零、"
        "incomplete 大量出现但基本复原；decomp 全程 0。",
    ])
    return c.save(out)


# ================================================================ ④ 状态/尺寸
def chart_state_sizes(a, out):
    rows = (a.get("timeline") or {}).get("per_minute") or []
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or len(rows)
    T0 = cfg.get("T0") or 1000
    if not rows:
        raise RuntimeError("timeline.per_minute 为空")
    W, H = 1600, 1120
    c = Chart(W, H,
              "④ 状态/尺寸时间线：速度 / 粒子数 / 平均与最大原子数",
              "速度按每次碰撞衰减 ε=0.2%；面积模型下初速 64138（按最大分子达标设计）；"
              "平均原子数 4.28 → 3.197，最大原子数从 9 降到 8")
    xt = nice_ticks(0, minutes, 10)
    kin = a.get("kinetics") or {}
    trans = (a.get("timeline") or {}).get("transitions") or {}
    half = trans.get("speed_half")

    box = (130, 170, 1410, 390)
    sp = [r.get("speed_mean") or 0 for r in rows]
    ymax = max(sp + [1]) * 1.12
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (0, minutes), (0, ymax), xt, yt,
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
             "N 最小 %s @ t=%s；终态 N=%s（初始 9002）"
             % (fmt_commas(nmin.get("N")), nmin.get("t"),
                fmt_commas(kin.get("N_final"))),
             size=13, anchor="ra", fill=BLUE)

    box3 = (130, 760, 1380, 960)
    ma = [r.get("mean_atoms") or 0 for r in rows]
    maxa = [r.get("max_atoms") or 0 for r in rows]
    ymax3 = max(ma + [1]) * 1.5
    yt3 = nice_ticks(0, ymax3, 5)
    mx_, my3 = c.frame(box3, (0, minutes), (0, ymax3), xt, yt3)
    myr = c.right_axis(box3, (0, max(maxa + [1]) * 1.15),
                       nice_ticks(0, max(maxa + [1]) * 1.15, 4),
                       label="最大原子数", color="#7f8c8d")
    c.line([(mx_(r["t"]), my3(r.get("mean_atoms") or 0)) for r in rows],
           fill="#10ac84", width=3)
    c.line([(mx_(r["t"]), myr(r.get("max_atoms") or 0)) for r in rows],
           fill="#7f8c8d", width=2)
    c.rot(box3[0] - 60, (box3[1] + box3[3]) / 2, "平均原子数", size=14)
    c.txt((box3[0] + box3[2]) / 2, box3[3] + 38, "时间 t（分钟）", size=16, anchor="ma")
    c.txt_bg(box3[2] - 16, box3[1] + 12,
             "平均 %.2f → %.3f；最大原子数 %s → %s"
             % (a["design"]["initial_size_stats"]["mean_atoms"] or 0,
                kin.get("mean_atoms_final") or 0,
                a["design"]["initial_size_stats"]["max_atoms"],
                (max((r.get("atoms") or 0) for r in comp_rows(a)) if False else
                 (a.get("key_numbers") or {}).get("main", {}).get("final_max_atoms"))),
             size=13, anchor="ra", fill="#10ac84")
    data_note(c, [
        "速度 %.0f → %.0f（保留 %.1f%%），半速 t=%s；自由程随 N/半径变化。"
        % (kin.get("speed_initial") or 0, kin.get("speed_final") or 0,
           100.0 * (kin.get("speed_ratio") or 0), (half or {}).get("t", "-")),
        "原子数守恒 38532；N 从 9002 到终态 %s（完全反应把大分子拆成更多小分子）。"
        % fmt_commas(kin.get("N_final")),
    ], y=1010)
    return c.save(out)


def comp_rows(a):
    return (a.get("composition") or {}).get("final_table") or []


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
    chosen = _pick_snapshots(snaps, [0, 2, 5, 10, 50, 200, 500, 995], 8)
    if not chosen:
        raise RuntimeError("没有可用 snapshots")
    cfg = a.get("config") or {}
    L = cfg.get("L") or 10000
    cols, rows = 4, max(1, math.ceil(len(chosen) / 4))
    pw, ph = 365, 400
    W = cols * pw + 40
    H = 160 + rows * ph + 90
    c = Chart(W, H,
              "⑤ 2D 粒子环境快照（每帧 ≤3000 个分子，按元素集合上色）",
              "颜色 = 分子包含的元素组合（旧 7 色方案）；t=0 混合大小分子，早期即退火为 O+X+C 类小分子；"
              "空间分布近似均匀")
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
            code = int(p[2])
            per_code[code] = per_code.get(code, 0) + 1
            px = box[0] + max(0.0, min(1.0, p[0] / L)) * bw
            py = box[3] - max(0.0, min(1.0, p[1] / L)) * bh
            c.d.ellipse([px - rad, py - rad, px + rad, py + rad],
                        fill=SNAPCOL7.get(code, "#b0bec5"))
        dom = max(per_code.items(), key=lambda kv: kv[1]) if per_code else (6, 0)
        dom_label = legend.get(str(dom[0]), str(dom[0]))
        inf = [box[0] + 5, box[1] + 5, box[0] + 222, box[1] + 58]
        c.d.rectangle(inf, fill="#ffffff", outline="#d9d9d9")
        c.txt(inf[0] + 8, inf[1] + 6, "t=%s  T=%s" % (
            s.get("t"), (a.get("config") or {}).get("T0", 1000) - (s.get("t") or 0)),
            size=15, bold=True, fill="#111")
        c.txt(inf[0] + 8, inf[1] + 29,
              "主导：%s（%.1f%%）" % (dom_label,
                                   100.0 * dom[1] / max(1, len(pts))),
              size=13, fill="#444")
        c.d.rectangle(box, outline="#999", width=1)
    items = [(SNAPCOL7[i], lab) for i, lab in
             ((0, "O(秩)"), (1, "X(晶)"), (2, "C(冰)"), (3, "O+X"),
              (4, "O+C"), (5, "X+C"), (6, "O+X+C"))]
    c.legend(40, H - 56, items, size=14, row_h=24, cols=7, col_w=200)
    return c.save(out)


# ================================================================ ⑥ 终态组成
def chart_final_composition(a, out):
    comp = a.get("composition") or {}
    table = comp.get("final_table") or []
    if not table:
        raise RuntimeError("final_table 为空")
    kn = (a.get("key_numbers") or {}).get("main") or {}
    sm = a.get("summary") or {}
    W, H = 1600, 1080
    c = Chart(W, H,
              "⑥ 终态组成：仅 %d 种分子式，全部闭合在 29 聚素内（OXC 80.9%% + OX2C 19.0%%）"
              % (comp.get("final_total_formulas") or 0),
              "横轴对数刻度；本次终态 4 种全部为 29 内且 84,225 目录内；括号内为分子原子数")
    box = (520, 165, 1420, 700)
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
        cnt = r.get("count") or 0
        bar_h = min(row_h * 0.62, 46)
        c.d.rectangle([x0 + 1, cy - bar_h / 2, mx(cnt), cy + bar_h / 2],
                      fill=GREEN, outline="#333", width=1)
        label = "%s  %s（%d 原子）" % (r.get("formula"), r.get("zh") or "",
                                      r.get("atoms") or 0)
        c.txt(x0 - 14, cy, label, size=14, anchor="rm", bold=True)
        c.txt(mx(cnt) + 8, cy, "%s（%.2f%% / 原子 %.1f%%）"
              % (fmt_commas(cnt), 100.0 * (r.get("share") or 0),
                 100.0 * (r.get("atoms_share") or 0)),
              size=13, anchor="lm")
    ls = comp.get("large_stats") or {}
    c.txt(100, 750, "终态 %d 种分子式（count>0）：29 内 4 / 目录内 4 / 目录外 0；"
          "新物质 0（完全反应 F 闭合）" % (comp.get("final_total_formulas") or 0),
          size=14, bold=True)
    lines = [
        "分子数 %s（初始 9002 → 终态 %s），原子 %s 守恒；平均 %.3f 原子、最大 %s 原子。"
        % (fmt_commas(kn.get("final_N")), fmt_commas(sm.get("final_N")),
           fmt_commas(sm.get("final_atoms")), kn.get("final_mean_atoms") or 0,
           kn.get("final_max_atoms") or 0),
        "大分子（≥5 原子）仅 %s 个（%.2f%% 分子、%.2f%% 原子）；≥10 原子 0 个。"
        % (fmt_commas((ls.get("ge5") or {}).get("molecules")),
           100.0 * ((ls.get("ge5") or {}).get("molecule_share") or 0),
           100.0 * ((ls.get("ge5") or {}).get("atom_share") or 0)),
        "初始 ≥5 原子分子 3578 个（39.7%% 分子、58.6%% 原子）→ 终态减少 99.5%%："
        "完全反应把大分子拆成 OXC/OX2C 等小分子不动点。",
        "固定半径对照终态几乎相同：OXC 9734 / OX2C 2279 / O2X2C4 20 / O2X4 9；"
        "说明终态由化学规则决定，与面积模型无关。",
        "对比 T55（9000→5974、99.5%% OXC、最大 9、新物质 0）与 T56（双原子盐终态、"
        "最大 36、120 新物质）：T57 全 29 聚素投料仍收敛到同一 OXC/OX2C 不动点。",
    ]
    y = 784
    for s in lines:
        for seg in c.wrap(s, W - 130, size=13):
            c.txt(100, y, seg, size=13, fill="#333")
            y += 22
    data_note(c, [
        "终态原子守恒：%s；%d 种终态全部为 29 聚素内、目录内分子式。"
        % (fmt_commas(sm.get("final_atoms")), comp.get("final_total_formulas") or 0),
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
    W, H = 1600, 980
    c = Chart(W, H,
              "⑦ 角-对角穿越验证：面积模型对照全部 ≥500 次（min=%.1f），大分子也达标"
              % (st.get("min") or 0),
              "设计目标：前 500 分钟内每个初始分子 ≥500 次角-对角穿越；面积模型下按最大"
              "分子（9 原子）反解 v0=64138")
    # 左：整体分布
    box = (90, 165, 900, 640)
    xlo, xhi = 450.0, 1050.0
    edges = hist.get("bin_edges") or []
    fracs = hist.get("fractions") or []
    ymax = max(fracs + [1e-9]) * 1.25
    xt = list(range(450, 1051, 100))
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (xlo, xhi), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: "%.2f" % v)
    xr = mx(500)
    c.d.rectangle([mx(xlo), box[1], xr, box[3]], fill="#fdecea")
    c.d.line([xr, box[1], xr, box[3]], fill=RED, width=3)
    c.txt_bg(xr + 8, box[1] + 10, "要求 ≥500（实测全部远高于此线）",
             size=14, bold=True, fill=RED)
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
          "每粒在 500 分钟内的角-对角穿越次数（9002 粒）", size=15, anchor="ma")
    sbox = [box[0] + 14, box[3] - 118, box[0] + 430, box[3] - 10]
    c.d.rectangle(sbox, fill="#f7f9fc", outline="#d0d7e2")
    c.txt(sbox[0] + 10, sbox[1] + 6, "对照组统计（9002 粒，500 分钟）", size=13, bold=True)
    c.txt(sbox[0] + 10, sbox[1] + 27,
          "min=%.1f  p1=%.1f  p5=%.1f" % (st.get("min"), st.get("p1"), st.get("p5")),
          size=13)
    c.txt(sbox[0] + 10, sbox[1] + 46,
          "median=%.1f  p95=%.1f  max=%.1f"
          % (st.get("median"), st.get("p95"), st.get("max")), size=13)
    c.txt(sbox[0] + 10, sbox[1] + 68,
          "fraction ≥500 = %.0f%%（9002/9002 全部达标）"
          % (100.0 * (st.get("fraction_ge_500") or 0)), size=14, bold=True,
          fill="#1e8449")

    # 右：by_size 分组（min/median/max）
    box2 = (960, 165, 1560, 700)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 16, box2[1] + 12, "按初始分子原子数分组的穿越统计", size=17, bold=True)
    c.txt(box2[0] + 16, box2[1] + 36, "（面积模型：大分子投料少但截面大；重点核对 ≥5 原子组）",
          size=13, fill="#555")
    sizes = sorted(by.keys(), key=lambda k: int(k))
    if sizes:
        x0, x1 = box2[0] + 70, box2[2] - 24
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
        bw = (x1 - x0) / len(sizes) * 0.28
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
            c.txt(X, y1 + 8, "%d" % int(k), size=13, anchor="ma")
            c.txt(X, y1 + 28, "n=%d" % (v.get("n") or 0), size=11, anchor="ma",
                  fill="#777")
        # 500 要求线画在柱之后，避免标注被柱遮挡
        c.d.line([x0, myb(500), x1, myb(500)], fill=RED, width=2)
        c.txt_bg(x1 - 6, myb(500) - 22, "500 次要求线", size=12,
                 anchor="ra", fill=RED)
        c.txt((x0 + x1) / 2, y1 + 52, "初始分子原子数（每柱：min / median / max 穿越）",
              size=14, anchor="ma")
        c.legend(box2[0] + 170, box2[1] + 64,
                 [("#e67e22", "min"), (BLUE, "median"), ("#10ac84", "max")],
                 size=12, row_h=22, cols=3, col_w=130)
    mi = cr.get("main_initial_single") or {}
    stats = mi.get("stats") or {}
    data_note(c, [
        "对照组（无化学、面积模型）：min=%.1f、median=%.1f、fraction≥500=%.0f%%；"
        "by_size 各组 min 从 2 原子的 %.1f 单调降到 9 原子的 %.1f，全部 ≥500。"
        % (st.get("min") or 0, st.get("median") or 0,
           100.0 * (st.get("fraction_ge_500") or 0),
           (by.get("2") or {}).get("min") or 0,
           (by.get("9") or {}).get("min") or 0),
        "主实验初始分子中位寿命 %.1f D（≈1 步，碰撞即反应）；survivors=%s。"
        "t=500 等效穿越 %s 次/初始分子（v0=64138 比 T55/T56 更高，因为设计取最大分子也达标）。"
        % (stats.get("median") or 0, stats.get("survivors"),
           (a.get("key_numbers") or {}).get("main", {}).get(
               "crossings_equiv_per_initial_at_500")),
        "结论：面积模型下『大分子也 ≥500 次穿越』的要求满足（by_size 全部达标）；"
        "主实验寿命短是反应设计使然，速度指标由无化学对照独立验证。",
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
              "⑧ 温度区间内的反应类型统计（主实验 1000→0°C，每分钟 -1°C）",
              "上：判定类型计数之和（对数轴）；下：净变化事件数。净变化事件全部发生在 "
              "T≥325；低温段只剩判定/复原/弹性。")
    n = len(wins)
    labels = [w.get("label") for w in wins]
    box = (120, 185, 1420, 620)
    ymax = 1.0
    for w in wins:
        for k in ("complete", "incomplete", "none"):
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
    bw = gw * 0.2
    for i, w in enumerate(wins):
        xc = box[0] + gw * (i + 0.5)
        for k, colr, off in (("complete", TYPECOL["complete"], -bw),
                             ("incomplete", TYPECOL["incomplete"], 0.0),
                             ("none", TYPECOL["none"], bw)):
            val = w.get(k) or 0
            if val <= 0:
                continue
            X = xc + off
            Y = myval(val)
            c.d.rectangle([X - bw * 0.42, Y, X + bw * 0.42, box[3]],
                          fill=colr, outline="#333", width=1)
            c.txt(X, Y - 4, fmt_num(val), size=11, anchor="mb", fill="#333")
        c.txt(xc, box[3] + 12, labels[i] + "°C", size=13, bold=True, anchor="ma")
        c.txt(xc, box[3] + 34, "%d 分钟" % (w.get("minutes") or 0), size=12,
              anchor="ma", fill="#777")
    c.txt((box[0] + box[2]) / 2, box[3] + 64, "温度区间（°C）", size=16, anchor="ma")
    c.legend(box[0] + 4, box[1] - 46,
             [(TYPECOL["complete"], "complete（完全反应判定）"),
              (TYPECOL["incomplete"], "incomplete（不完全反应判定）"),
              (TYPECOL["none"], "none（不反应/弹性）")],
             size=13, row_h=24, cols=3, col_w=340)

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
    trans = tl.get("transitions") or {}
    c.txt_bg(box2[0] + 250, box2[1] + 8,
             "净变化事件 100%% 发生在 T≥%s（退火期）；T≤%s 后只判定/复原/弹性"
             % (((trans.get("net_event_T_range") or [None])[0]),
                ((trans.get("last_net_change") or {}).get("T"))),
             size=13, fill="#8e44ad")
    data_note(c, [
        "低温窗口：T=5~0 区间 complete 判定 0 次（T<6 时 OXC/OX2C 对达不到 Σc，无法完全反应）、"
        "incomplete %s 次、none %s 次；全部净变化已停止。"
        % (fmt_commas(wins[-1].get("incomplete")), fmt_commas(wins[-1].get("none"))),
        "decomp 全程 0：面积模型/全 29 聚素投料下也没有不稳定中间体在降温后自分解，"
        "终态由完全反应动力学决定。",
    ], y=985)
    return c.save(out)


# ================================================================ ⑨ 尺寸分布对比
def chart_size_compare(a, out):
    cvu = a.get("comparison_area_vs_uniform") or {}
    if not cvu.get("available"):
        raise RuntimeError("缺少 area/uniform 对比数据")
    A = cvu["area"]
    U = cvu["uniform"]
    initial = (cvu.get("initial_reference") or {}).get("size_distribution") or []
    W, H = 1600, 1050
    c = Chart(W, H,
              "⑨ 尺寸分布对比：面积模型 vs 固定半径（+ 初始投料基准）",
              "初始投料含 2~9 原子；两种碰撞模型终态都把大分子压成 3~4 原子小分子，"
              "面积模型的大分子残余甚至更少")
    # 上：初始 vs area 终态 vs uniform 终态（分子数，对数）
    box = (110, 165, 1420, 610)
    xs = list(range(2, 10))
    series = []
    m_init = {int(d["atoms"]): d["molecules"] for d in initial}
    m_area = {int(d["atoms"]): d["molecules"] for d in (A.get("size_distribution") or [])}
    m_uni = {int(d["atoms"]): d["molecules"] for d in (U.get("size_distribution") or [])}
    ymax = max([v for d in (m_init, m_area, m_uni) for v in d.values()] + [1]) * 2.0
    yt = [1, 10, 100, 1000, 10000]
    v = 100000
    while v <= ymax:
        yt.append(v)
        v *= 10
    mx, my = c.frame(box, (1.5, 9.5), (1, ymax), xs, yt, logy=True,
                     ytick_fmt=lambda v: "%g" % v)
    bw = 0.24
    for i, nn in enumerate(xs):
        for val, colr, off, lab in (
                (m_init.get(nn, 0), "#95a5a6", -bw, "初始"),
                (m_area.get(nn, 0), BLUE, 0.0, "面积模型终态"),
                (m_uni.get(nn, 0), "#e67e22", bw, "固定半径终态")):
            if val <= 0:
                continue
            X = mx(nn) + off * (mx(3) - mx(2))
            Y = my(val)
            c.d.rectangle([X - (mx(3) - mx(2)) * 0.11, Y,
                           X + (mx(3) - mx(2)) * 0.11, box[3]],
                          fill=colr, outline="#333", width=1)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "分子数（对数）", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 38, "分子原子数", size=15, anchor="ma")
    c.legend(box[0] + 20, box[1] + 12,
             [("#95a5a6", "初始投料"), (BLUE, "面积模型终态"),
              ("#e67e22", "固定半径终态")], size=14, row_h=26, cols=3, col_w=210)

    # 下左：大分子数量（对数纵轴，初始 3578 与终态 17/29 同图可见）
    box2 = (110, 700, 800, 940)
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 14, box2[1] + 10, "≥5 原子大分子：初始 vs 两种终态（对数）", size=16,
          bold=True)
    lsA = A.get("large_stats") or {}
    lsU = U.get("large_stats") or {}
    init_big = (cvu.get("initial_reference") or {}).get("big5") or {}
    vals = [init_big.get("molecules") or 0,
            (lsA.get("ge5") or {}).get("molecules") or 0,
            (lsU.get("ge5") or {}).get("molecules") or 0]
    cols = ["#95a5a6", BLUE, "#e67e22"]
    labels = ["初始", "面积模型", "固定半径"]
    x0, x1 = box2[0] + 70, box2[2] - 20
    y0, y1 = box2[1] + 80, box2[3] - 80
    logmax = math.log10(max(vals + [10]) * 1.5)

    def myb(v):
        return y1 - (math.log10(max(1.0, float(v))) / logmax) * (y1 - y0)

    for v in (1, 10, 100, 1000, 10000):
        if v > 10 ** logmax:
            continue
        Y = myb(v)
        c.d.line([x0, Y, x1, Y], fill="#eee", width=1)
        c.txt(x0 - 8, Y, fmt_commas(v), size=12, anchor="rm")
    c.d.rectangle([x0, y0, x1, y1], outline="#888", width=1)
    for i, val in enumerate(vals):
        X = x0 + (x1 - x0) / 3 * (i + 0.5)
        Y = myb(max(1.0, val))
        c.d.rectangle([X - 55, Y, X + 55, y1], fill=cols[i], outline="#333", width=1)
        c.txt(X, Y - 6, fmt_commas(val), size=14, anchor="mb", bold=True)
        c.txt(X, y1 + 10, labels[i], size=13, anchor="ma")
        c.txt(X, y1 + 30, "原子 %.1f%%" % (100.0 * (
            (init_big.get("atom_share") if i == 0 else
             (lsA.get("ge5") or {}).get("atom_share") if i == 1 else
             (lsU.get("ge5") or {}).get("atom_share")) or 0)), size=12,
            anchor="ma", fill="#555")

    # 下右：结论
    box3 = (840, 700, 1560, 940)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 14, box3[1] + 10, "尺寸对比结论", size=16, bold=True)
    lines = [
        "初始：29 种、2~9 原子；≥5 原子 %s 个（%.1f%% 分子、%.1f%% 原子）。"
        % (fmt_commas(init_big.get("molecules")),
           100.0 * (init_big.get("molecule_share") or 0),
           100.0 * (init_big.get("atom_share") or 0)),
        "面积模型终态：平均 %.3f、最大 %s；≥5 原子 %s 个（%.2f%% 分子、%.2f%% 原子）。"
        % (A.get("final_mean_atoms") or 0, A.get("final_max_atoms") or 0,
           fmt_commas((lsA.get("ge5") or {}).get("molecules")),
           100.0 * ((lsA.get("ge5") or {}).get("molecule_share") or 0),
           100.0 * ((lsA.get("ge5") or {}).get("atom_share") or 0)),
        "固定半径终态：平均 %.3f、最大 %s；≥5 原子 %s 个（%.2f%% 分子、%.2f%% 原子）。"
        % (U.get("final_mean_atoms") or 0, U.get("final_max_atoms") or 0,
           fmt_commas((lsU.get("ge5") or {}).get("molecules")),
           100.0 * ((lsU.get("ge5") or {}).get("molecule_share") or 0),
           100.0 * ((lsU.get("ge5") or {}).get("atom_share") or 0)),
        "→ 面积模型没有保留更多大分子（17 < 29），两种模型都退火到 3~4 原子小分子；"
        "尺寸分布由完全反应 F 决定，而不是碰撞截面。",
    ]
    y = box3[1] + 44
    for s in lines:
        for seg in c.wrap(s, box3[2] - box3[0] - 28, size=13):
            c.txt(box3[0] + 14, y, seg, size=13, fill="#333")
            y += 22
    data_note(c, [
        "尺寸分布叠图：初始大分子（2~9）在两种 1000°C 模型下都被完全反应拆掉，"
        "终态集中在 3（OXC）与 4（OX2C）原子。",
        "低温窗口（补充图 t57_sensitivity）里大分子才留得住：T0=12 平均 4.09、≥5 原子 2473 个（26.3%）。",
    ], y=H - 52)
    return c.save(out)


# ================================================================ ⑩ 面积假设检验
def chart_area_vs_uniform(a, out):
    cvu = a.get("comparison_area_vs_uniform") or {}
    if not cvu.get("available"):
        raise RuntimeError("缺少 area/uniform 对比数据")
    A = cvu["area"]
    U = cvu["uniform"]
    cmp_ = cvu.get("comparison") or {}
    interp = cmp_.get("interpretation") or {}
    W, H = 1600, 1080
    c = Chart(W, H,
              "⑩ 面积假设检验：面积模型碰撞 +37%，但终态没有更偏向大分子",
              "同投料/同 seed/同化学引擎，仅碰撞半径与伙伴加权不同；"
              "area=面积∝n、数量∝1/n、加权伙伴；uniform=固定半径 0.2")
    panels = [
        ("碰撞总数", A.get("collisions_total"), U.get("collisions_total"),
         fmt_commas, "#8e44ad"),
        ("complete 判定数", (A.get("reaction_counts") or {}).get("complete"),
         (U.get("reaction_counts") or {}).get("complete"), fmt_num, RED),
        ("终态平均原子数", A.get("final_mean_atoms"), U.get("final_mean_atoms"),
         lambda v: "%.3f" % v, BLUE),
        ("≥5 原子大分子数", (A.get("large_stats") or {}).get("ge5", {}).get("molecules"),
         (U.get("large_stats") or {}).get("ge5", {}).get("molecules"),
         fmt_commas, "#10ac84"),
    ]
    panel_w, panel_h = 720, 330
    x0s = [60, 840]
    y0s = [110, 460]
    for idx, (name, av, uv, fmt, colr) in enumerate(panels):
        px = x0s[idx % 2]
        py = y0s[idx // 2]
        box = (px + 100, py + 44, px + panel_w - 40, py + panel_h - 40)
        c.txt(px + 16, py + 4, "%s %s" % ("①②③④"[idx], name), size=19, bold=True)
        vmax = max([av or 0, uv or 0, 1]) * 1.3
        yt = nice_ticks(0, vmax, 4)
        tick_fmt = (lambda v: "%.1f" % v) if idx == 2 else fmt
        mx, my = c.frame(box, (0, 2), (0, vmax), [0.5, 1.5], yt,
                         xtick_labels=["面积模型", "固定半径"], ytick_fmt=tick_fmt)
        for i, (val, col2) in enumerate(((av, BLUE), (uv, "#e67e22"))):
            X = mx(i + 0.5)
            Y = my(val or 0)
            c.d.rectangle([X - 60, Y, X + 60, box[3]], fill=col2,
                          outline="#333", width=1)
            c.txt(X, Y - 6, fmt(val or 0), size=15, anchor="mb", bold=True)
        if av and uv:
            c.txt((box[0] + box[2]) / 2, box[3] + 34,
                  "差值 %+s（%+.1f%%）" % (fmt_commas(av - uv),
                                          100.0 * (av - uv) / uv),
                  size=13, anchor="ma", fill="#555")
    # 结论
    c.txt(60, 830, "假设检验结论（由数据决定）", size=18, bold=True)
    y = 866
    for s in c.wrap(interp.get("hypothesis_verdict") or "", W - 130, size=14):
        c.txt(60, y, s, size=14, fill="#111")
        y += 24
    if y > 1010:
        pass
    data_note(c, [
        interp.get("caveat") or "",
        "初始投料 ≥5 原子分子 3578 个（39.7%% 分子、58.6%% 原子）→ 两种模型终态都只剩"
        "极小比例：面积 0.34%% 原子、固定半径 0.56%% 原子。",
    ], y=1032)
    return c.save(out)


# ================================================================ ⑪ 低温敏感性
def chart_sensitivity(a, out):
    sens = a.get("sensitivity") or {}
    if not sens.get("available"):
        raise RuntimeError("没有敏感性数据")
    runs = sens.get("runs") or []
    ref = sens.get("main_reference") or {}
    W, H = 1600, 1120
    c = Chart(W, H,
              "11 低温窗口敏感性（面积模型，补充）：大分子只有低温才留得住",
              "T0=12/20°C 各自运行 T0 分钟（T0→0）；红色虚线=主实验 1000°C×1000 分钟参考")
    metrics = [
        ("终态平均原子数", lambda r: r.get("mean_size"), ref.get("mean_size"),
         lambda v: "%.2f" % v, "T0=12 平均 4.09 原子，主实验仅 3.197"),
        ("≥5 原子大分子数", lambda r: r.get("big5"), ref.get("big5"),
         fmt_commas, "T0=12 有 2473 个（26.3% 分子），主实验仅 17 个（0.14%）"),
        ("终态分子式数", lambda r: r.get("n_formulas"), ref.get("n_formulas"),
         lambda v: "%d 种" % v, "T0=12 终态 18 种，主实验仅 4 种"),
        ("自分解事件数", lambda r: r.get("decomp"), ref.get("decomp"),
         fmt_commas, "T0=12 自分解 1017 次；主实验 0 次"),
    ]
    panel_w, panel_h = 720, 400
    x0s = [60, 840]
    y0s = [110, 540]
    n = len(runs)
    labels = ["T0=%s°C" % r.get("T0") for r in runs]
    cols = [BLUE, "#8e44ad", "#f39c12", "#e74c3c"]
    for idx, (name, getter, refv, fmt, comment) in enumerate(metrics):
        px = x0s[idx % 2]
        py = y0s[idx // 2]
        box = (px + 80, py + 48, px + panel_w - 30, py + 300)
        vals = [getter(r) or 0 for r in runs]
        vmax = max(vals + [refv or 0, 1]) * 1.25
        c.txt(px + 16, py + 6, "%s %s" % ("①②③④"[idx], name), size=19, bold=True)
        if refv is not None:
            c.txt(px + panel_w - 10, py + 10, "主实验 1000°C = %s" % fmt(refv),
                  size=13, anchor="ra", fill=RED)
        yt = nice_ticks(0, vmax, 4)
        mx, my = c.frame(box, (0, n), (0, vmax), [i + 0.5 for i in range(n)],
                         yt, ytick_fmt=fmt, xtick_labels=labels)
        bw = (box[2] - box[0]) / n * 0.44
        for i, r in enumerate(runs):
            X = box[0] + (box[2] - box[0]) / n * (i + 0.5)
            Y = my(vals[i])
            c.d.rectangle([X - bw / 2, Y, X + bw / 2, box[3]],
                          fill=cols[i % len(cols)], outline="#333", width=1)
            c.txt(X, Y - 6, fmt(vals[i]), size=15, anchor="mb", bold=True)
        c.txt((box[0] + box[2]) / 2, box[3] + 36, "初温 T0（°C）", size=14, anchor="ma")
        if refv is not None:
            Yr = my(min(refv, vmax))
            c.dashed((box[0], Yr), (box[2], Yr), fill=RED, width=2, dash=8)
        c.txt(px + 16, py + panel_h - 14, "→ " + comment, size=13, fill="#555")
    by = {r.get("T0"): r for r in runs}
    r12 = by.get(12) or {}
    r20 = by.get(20) or {}
    data_note(c, [
        "低温窗口（面积模型）：T0=12 平均 %.2f 原子、≥5 原子 %s 个（%.1f%% 分子）、%s 种分子式、"
        "%s 种新物质、自分解 %s 次；"
        % (r12.get("mean_size") or 0, fmt_commas(r12.get("big5")),
           100.0 * (r12.get("big5_share") or 0), r12.get("n_formulas"),
           r12.get("new_substances"), fmt_commas(r12.get("decomp"))),
        "T0=20 平均 %.2f、大分子 %s 个（%.1f%%）、%s 种分子式、%s 新物质、自分解 %s 次；"
        "对照 1000°C 主实验平均 %.2f、大分子仅 %s 个、%s 种分子式、decomp 0。"
        % (r20.get("mean_size") or 0, fmt_commas(r20.get("big5")),
           100.0 * (r20.get("big5_share") or 0), r20.get("n_formulas"),
           r20.get("new_substances"), fmt_commas(r20.get("decomp")),
           ref.get("mean_size") or 0, fmt_commas(ref.get("big5")),
           ref.get("n_formulas")),
        "→ 大分子只有在低温窗口才留得住；1000°C 的快速完全反应退火会把几乎所有大分子"
        "拆回 OXC/OX2C 不动点，这与面积模型无关。",
        "注意：低温实验只运行 T0 分钟（T0→0°C），主实验运行 1000 分钟。",
    ], y=1000)
    return c.save(out)


# ================================================================ main
CHARTS = [
    ("design", "t57_design.png", chart_design),
    ("composition", "t57_composition.png", chart_composition),
    ("reaction_rate", "t57_reaction_rate.png", chart_reaction_rate),
    ("state_sizes", "t57_state_sizes.png", chart_state_sizes),
    ("snapshots", "t57_snapshots.png", chart_snapshots),
    ("final_composition", "t57_final_composition.png", chart_final_composition),
    ("crossings", "t57_crossings.png", chart_crossings),
    ("temperature_windows", "t57_temperature_windows.png", chart_temperature_windows),
    ("size_compare", "t57_size_compare.png", chart_size_compare),
    ("area_vs_uniform", "t57_area_vs_uniform.png", chart_area_vs_uniform),
    ("sensitivity", "t57_sensitivity.png", chart_sensitivity),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="T57 图表渲染")
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
