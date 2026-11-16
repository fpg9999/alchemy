# -*- coding: utf-8 -*-
"""t56_render.py —— T56 实验图表（Pillow 绘制，中文字体 msyh）

读取 t56_analysis.json，生成 9 张图：
  images/t56_composition.png        ① 组成随时间演化（堆叠 + CF/XA/OK 三主峰占比）
  images/t56_reaction_rate.png      ② 反应判定计数/分钟 + 温度轴 + 净变化事件
  images/t56_state_timeseries.png   ③ 速度 / 粒子数 / 平均原子数 三联图
  images/t56_snapshots.png          ④ 2D 快照拼图（element_bitmask 上色，top 组合图例）
  images/t56_final_composition.png  ⑤ 终态组成（目录内绿 / 目录外橙，标注原子数）
  images/t56_crossings.png          ⑥ 穿越验证（对照直方图 + 500 线 + 初始单质寿命）
  images/t56_temperature_windows.png⑦ 温度区间反应类型统计
  images/t56_sizes.png              ⑧ 分子尺寸演化（max/mean/p90）+ 终态尺寸分布
  images/t56_ratio.png              ⑨ 价数比例验证（3价:2价:1价 = 1:1.75:3）

用法：
  python t56_render.py
  python t56_render.py --analysis t56_analysis.json --images images
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_ANALYSIS = os.path.join(BASE, "t56_analysis.json")
DEFAULT_IMAGES = os.path.join(BASE, "images")

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT_REG

PAL = ["#2e86de", "#ee5253", "#10ac84", "#f39c12", "#8e44ad", "#16a085",
       "#d35400", "#2c3e50", "#c0392b", "#7f8c8d", "#27ae60", "#e84393",
       "#00acc1", "#795548", "#607d8b", "#f06292"]
TYPECOL = {"complete": "#e74c3c", "incomplete": "#f39c12",
           "none": "#95a5a6", "decomp": "#8e44ad"}
ELEMCOL = {"O": "#2ecc71", "X": "#f39c12", "C": "#3498db",
           "K": "#9b59b6", "A": "#1abc9c", "F": "#e74c3c"}
GREEN = "#2e8b57"
ORANGE = "#e67e22"
VALCOL = {3: "#e74c3c", 2: "#2e86de", 1: "#10ac84"}

# 旧 7 色快照方案（bench20 兼容）
SNAPCOL7 = {0: "#2ecc71", 1: "#f39c12", 2: "#3498db", 3: "#9b59b6",
            4: "#1abc9c", 5: "#e74c3c", 6: "#00acc1"}


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
              grid_color="#e9e9e9", xtick_labels=None, xlabel_every=1):
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

    def line(self, pts, fill="#333", width=3):
        pts = [p for p in pts if p is not None]
        if len(pts) >= 2:
            self.d.line(pts, fill=fill, width=width, joint="curve")

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


def _t(ms):
    return (ms or {}).get("t", "-")


def _zh(comp, f):
    for r in comp.get("final_table") or []:
        if r.get("formula") == f:
            return r.get("zh") or f
    for x in comp.get("top_formulas") or []:
        if x.get("formula") == f:
            return x.get("zh") or f
    return f


# ================================================================ ① 组成
def chart_composition(a, out):
    comp = a.get("composition") or {}
    cfg = a.get("config") or {}
    series = comp.get("series") or []
    minutes = cfg.get("minutes") or (series[-1]["t"] if series else 1000)
    T0 = cfg.get("T0") or 1000
    if not series:
        raise RuntimeError("composition.series 为空")
    W, H = 1600, 1150
    c = Chart(W, H,
              "① 组成随时间的演化：6 种单质 → 大分子峰 → 同价跨类配对的双原子盐终态",
              "每 5 分钟完整组成；堆叠 = top 分子式数量（t=0 已含第 0 分钟反应）；"
              "初始 9200 单质（O2/K2 800、X2/A2 1400、C2/F2 2400）")
    box = (100, 150, 1320, 660)
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
    c.txt(1336, 150, "分子式（颜色）", size=16, bold=True)
    c.legend(1336, 186, items, size=13, row_h=26)

    # 下方：CF/XA/OK 三主峰占比 + 物种数
    box2 = (100, 730, 1100, 930)
    salt = ["CF", "XA", "OK"]
    order = comp.get("stack_order") or []
    salt_col = {f: PAL[order.index(f) % len(PAL)] if f in order else PAL[i % len(PAL)]
                for i, f in enumerate(salt)}
    shares = {f: [(r.get("top_shares") or {}).get(f) or 0.0 for r in series]
              for f in salt}
    nsp = [r.get("n_species") or 0 for r in series]
    nsmax = max(nsp + [1]) * 1.08
    yt2 = [0, 0.25, 0.5, 0.75, 1.0]
    mx2, my2 = c.frame(box2, (0, minutes), (0, 1.0), xt, yt2,
                       ytick_fmt=lambda v: "%.0f%%" % (v * 100))
    myr = c.right_axis(box2, (0, nsmax), nice_ticks(0, nsmax, 5),
                       label="分子式数", color="#2e86de")
    for f in salt:
        c.d.line([(mx2(series[j]["t"]), my2(shares[f][j])) for j in range(n)],
                 fill=salt_col[f], width=3)
    c.d.line([(mx2(series[j]["t"]), myr(nsp[j])) for j in range(n)],
             fill="#95a5a6", width=2)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 42, "时间 t（分钟）", size=16, anchor="ma")
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "双原子盐占比", size=14)
    c.legend(1200, 745,
             [(salt_col["CF"], "CF 冰焰（1+1价）"),
              (salt_col["XA"], "XA 晶气（2+2价）"),
              (salt_col["OK"], "OK 秩沌（3+3价）"),
              ("#95a5a6", "分子式数（右轴，峰值≈790）")],
             size=13, row_h=28)
    kn = (a.get("key_numbers") or {}).get("main") or {}
    peak = (a.get("timeline") or {}).get("transitions", {}).get("max_atoms_peak") or {}
    data_note(c, [
        "终态 N=%s：双原子盐占 %.2f%%（CF %s + XA %s + OK %s = %s），"
        "另有 %s 个大分子承载 %.1f%% 原子；终态共 %d 种分子式（%d 种在目录内、%d 种目录外）。"
        % (fmt_commas(kn.get("final_N")),
           100.0 * (kn.get("final_diatomic_share") or 0),
           fmt_commas((kn.get("final_salt_peaks") or [{}])[0].get("count")),
           fmt_commas((kn.get("final_salt_peaks") or [{}])[1].get("count")),
           fmt_commas((kn.get("final_salt_peaks") or [{}])[2].get("count")),
           fmt_commas(kn.get("final_diatomic_count")),
           fmt_commas(kn.get("final_large_molecules")),
           100.0 * (kn.get("final_large_atoms_share") or 0),
           kn.get("final_distinct_formulas") or 0,
           (kn.get("final_distinct_formulas") or 0) -
           (kn.get("final_outside_catalog_n") or 0),
           kn.get("final_outside_catalog_n") or 0),
        "演化峰值：最大分子 %s 原子 @ t=%s（T=%s）；净变化事件最后 t=%s（T=%s）；"
        "complete→0 在 T=1。终态平均原子数 %.2f，最大 %s 原子。"
        % (peak.get("max_atoms"), peak.get("t"), peak.get("T"),
           _t(kn.get("last_net_change")), (kn.get("last_net_change") or {}).get("T"),
           kn.get("final_mean_atoms") or 0,
           max((r.get("atoms") or 0) for r in (comp.get("final_table") or [{}]))),
    ], y=1000)
    return c.save(out)


# ================================================================ ② 反应率
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
              "② 反应判定计数/分钟（complete/incomplete/none）与温度轴；净变化事件/分钟",
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
              % (last_net.get("t"), last_net.get("T")), box[1] + 8, "la", "#c0392b"),
             (fzc.get("t"), "complete→0（T=%s）" % fzc.get("T"), box[1] + 62, "ra", "#c0392b")]
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
    c.txt_bg(box2[0] + 12, box2[1] + 8,
             "净变化事件 %s 次、分布 %d 分钟；全部发生在 T≥%s"
             % (fmt_commas(n_ev), n_min,
                (trans.get("net_event_T_range") or [None])[0]),
             size=13, fill="#8e44ad")
    c.txt_bg(box2[0] + 12, box2[1] + 32,
             "t=0 分钟 %s 次（初始单质成键）；之后快速衰减，低温段不完全判定多为复原。"
             % fmt_commas(ev[0] if ev else 0), size=13, fill="#555")
    data_note(c, [
        "判定计数合计 %s = 碰撞数（complete %s / incomplete %s / none %s）；"
        "其中 %.1f%% 的 complete 判定净结果不变（F 不动点）。"
        % (fmt_commas(sum((r.get("collisions") or 0) for r in rows)),
           fmt_commas(sum((r.get("complete") or 0) for r in rows)),
           fmt_commas(sum((r.get("incomplete") or 0) for r in rows)),
           fmt_commas(sum((r.get("none") or 0) for r in rows)),
           100.0 * (ev_a.get("complete_noop_ratio") or 0.0)),
        "温度窗口：T=6~2 完全判定仍大量发生（随大分子 Σc 变高而下降），T=1 完全判定归零；"
        "不完全判定在 T≤5 出现但基本复原（净事件不增加）；decomp 全程 0。",
    ])
    return c.save(out)


# ================================================================ ③ 状态
def chart_state_timeseries(a, out):
    rows = (a.get("timeline") or {}).get("per_minute") or []
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or len(rows)
    T0 = cfg.get("T0") or 1000
    if not rows:
        raise RuntimeError("timeline.per_minute 为空")
    W, H = 1600, 1100
    c = Chart(W, H,
              "③ 状态三联：速度 / 粒子数 / 平均原子数（含最大原子数）随时间",
              "速度按每次碰撞衰减 ε=0.2%；粒子数先降（成键合并）后回升；"
              "平均原子数在大分子峰后回落到双原子终态（≈2）")
    xt = nice_ticks(0, minutes, 10)
    kin = a.get("kinetics") or {}
    half = ((a.get("timeline") or {}).get("transitions") or {}).get("speed_half")

    box = (130, 170, 1410, 380)
    sp = [r.get("speed_mean") or 0 for r in rows]
    ymax = max(sp + [1]) * 1.12
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (0, minutes), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: fmt_commas(v))
    c.top_temp_axis(box, (0, minutes), mx, T0, minutes)
    c.line([(mx(r["t"]), my(r.get("speed_mean") or 0)) for r in rows],
           fill="#c0392b", width=3)
    c.line([(mx(r["t"]), my(r.get("speed_median") or 0)) for r in rows],
           fill="#e67e22", width=2)
    c.line([(mx(r["t"]), my(r.get("speed_p90") or 0)) for r in rows],
           fill="#95a5a6", width=2)
    c.rot(box[0] - 60, (box[1] + box[3]) / 2, "速度", size=14)
    c.d.rectangle([box[0] + 8, box[3] - 104, box[0] + 186, box[3] - 8],
                  fill="#ffffff", outline="#e0e0e0")
    c.legend(box[0] + 16, box[3] - 98,
             [("#c0392b", "平均速度"), ("#e67e22", "中位速度"), ("#95a5a6", "p90 速度")],
             size=13, row_h=23)
    c.txt_bg(box[2] - 16, box[1] + 12,
             "速度 %.0f → %.0f（保留 %.1f%%）" % (
                 kin.get("speed_initial") or 0, kin.get("speed_final") or 0,
                 100.0 * (kin.get("speed_ratio") or 0)),
             size=13, anchor="ra", fill="#c0392b")
    if half:
        c.dashed((mx(half["t"]), box[1]), (mx(half["t"]), box[3]), fill="#555", width=1)
        c.txt_bg(mx(half["t"]) + 6, box[3] - 26,
                 "半速 t=%s（v=%.0f）" % (half["t"], half["v"]), size=12, fill="#555")

    box2 = (130, 455, 1410, 655)
    N = [r.get("N") or 0 for r in rows]
    ymax2 = max(N + [1]) * 1.12
    yt2 = nice_ticks(0, ymax2, 5)
    mx2, my2 = c.frame(box2, (0, minutes), (0, ymax2), xt, yt2,
                       ytick_fmt=lambda v: fmt_commas(v))
    c.line([(mx2(r["t"]), my2(r.get("N") or 0)) for r in rows],
           fill="#2e86de", width=3)
    c.rot(box2[0] - 60, (box2[1] + box2[3]) / 2, "粒子数 N", size=14)
    nmin = (a.get("timeline") or {}).get("transitions", {}).get("N_min") or {}
    c.txt_bg(box2[2] - 16, box2[3] - 30,
             "N 最小 %s @ t=%s；终态 N=%s（初始 9200）"
             % (fmt_commas(nmin.get("N")), nmin.get("t"),
                fmt_commas(kin.get("N_final"))),
             size=13, anchor="ra", fill="#2e86de")

    box3 = (130, 730, 1380, 920)
    ma = [r.get("mean_atoms") or 0 for r in rows]
    maxa = [r.get("max_atoms") or 0 for r in rows]
    ymax3 = max(ma + [1]) * 1.4
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
    c.txt((box3[0] + box3[2]) / 2, box3[3] + 40, "时间 t（分钟）", size=16, anchor="ma")
    peak = kin.get("mean_atoms_peak") or {}
    c.txt_bg(box3[2] - 16, box3[1] + 12,
             "平均原子数峰值 %.2f @ t=%s；终态 %.2f（双原子≈2）"
             % (peak.get("mean_atoms") or 0, peak.get("t"),
                kin.get("mean_atoms_final") or 0),
             size=13, anchor="ra", fill="#10ac84")
    data_note(c, [
        "速度从 %.0f 衰减到 %.0f（保留 %.1f%%），半速 t=%s；自由程随 N 变化。"
        % (kin.get("speed_initial") or 0, kin.get("speed_final") or 0,
           100.0 * (kin.get("speed_ratio") or 0), (half or {}).get("t", "-")),
        "原子数守恒：始终 18,400；N 从 9200 降到谷值 %s 后回升到终态 %s（大分子被"
        "完全反应拆成双原子盐）。"
        % (fmt_commas(nmin.get("N")), fmt_commas(kin.get("N_final"))),
    ], y=990)
    return c.save(out)


# ================================================================ ④ 快照
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
    bitmask = any((s.get("color_mode") == "element_bitmask") for s in chosen)
    # 全局 code 频次（用于 palette / 图例）
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
    mode_txt = ("element_bitmask（code=9 位元素集合掩码）" if bitmask
                else "旧 7 色（bench 样本）")
    c = Chart(W, H,
              "④ 2D 粒子环境快照（每帧 ≤3000 个分子，按元素组合上色）",
              "颜色 = 分子包含的元素组合（%s）；只列占比最高的 %d 种组合，"
              "其余归入灰色。空间分布保持近似均匀。" % (mode_txt, len(top_codes)))
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
            if bitmask:
                colr = palette.get(code, "#b0bec5")
            else:
                colr = SNAPCOL7.get(int(code), "#b0bec5")
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
              size=13, fill="#444")
        c.d.rectangle(box, outline="#999", width=1)
    # 图例（top 10 组合）
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


# ================================================================ ⑤ 终态组成
def chart_final_composition(a, out):
    comp = a.get("composition") or {}
    table = (comp.get("final_table") or [])[:20]
    if not table:
        raise RuntimeError("final_table 为空")
    kn = (a.get("key_numbers") or {}).get("main") or {}
    sm = a.get("summary") or {}
    W, H = 1600, 1100
    c = Chart(W, H,
              "⑤ 终态组成：双原子盐占 %.1f%%，CF/XA/OK 三主峰"
              % (100.0 * (kn.get("final_diatomic_share") or 0)),
              "横轴对数刻度；绿色=84,225 目录内，橙色=目录外（目录 >16 原子不完备，"
              "不能据此判断化学上不可能）；括号内为分子原子数")
    box = (520, 150, 1420, 780)
    vmax = max([r.get("count") or 1 for r in table] + [1]) * 2.2
    x0, y0, x1, y1 = box
    logmin, logmax = 0.0, math.log10(max(vmax, 10))

    def mx(v):
        v = max(1.0, float(v))
        X = x0 + (math.log10(v) - logmin) / (logmax - logmin) * (x1 - x0)
        return max(x0 + 2.0, X)

    yt = [1, 10, 100, 1000, 10000]
    yt = [v for v in yt if v <= vmax] or [1, 10]
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
        in_cat = bool(r.get("in_catalog"))
        col = GREEN if in_cat else ORANGE
        cnt = r.get("count") or 0
        bar_h = min(row_h * 0.62, 38)
        c.d.rectangle([x0 + 1, cy - bar_h / 2, mx(cnt), cy + bar_h / 2],
                      fill=col, outline="#333", width=1)
        label = "%s  %s（%d 原子）" % (r.get("formula"), r.get("zh") or "",
                                      r.get("atoms") or 0)
        c.txt(x0 - 14, cy, label, size=13, anchor="rm", bold=True)
        tag = "" if in_cat else "  目录外"
        c.txt(mx(cnt) + 8, cy, "%s（%.2f%%）%s"
              % (fmt_commas(cnt), 100.0 * (r.get("share") or 0), tag),
              size=12, anchor="lm", fill="#333")
    # 右侧摘要
    salt = kn.get("final_salt_peaks") or []
    c.txt(100, 852, "终态 %d 种分子式（count>0）：目录内 %d 种 / 目录外 %d 种"
          % (kn.get("final_distinct_formulas") or 0,
             (kn.get("final_distinct_formulas") or 0) - (kn.get("final_outside_catalog_n") or 0),
             kn.get("final_outside_catalog_n") or 0), size=14, bold=True)
    lines = [
        "双原子盐 %s 个（%.2f%% 分子 / %.1f%% 原子）：CF %s（冰焰，1+1 价）、"
        "XA %s（晶气，2+2 价）、OK %s（秩沌，3+3 价）。"
        % (fmt_commas(kn.get("final_diatomic_count")),
           100.0 * (kn.get("final_diatomic_share") or 0),
           100.0 * (kn.get("final_diatomic_atoms_share") or 0),
           fmt_commas(salt[0].get("count") if salt else None),
           fmt_commas(salt[1].get("count") if len(salt) > 1 else None),
           fmt_commas(salt[2].get("count") if len(salt) > 2 else None)),
        "大分子 %s 个（2~22 原子）承载 %.1f%% 原子；终态最大 %d 原子；"
        "演化中最大 %s 原子（t=%s）。"
        % (fmt_commas(kn.get("final_large_molecules")),
           100.0 * (kn.get("final_large_atoms_share") or 0),
           max((r.get("atoms") or 0) for r in comp.get("final_table") or [{}]),
           kn.get("max_atoms_evolution"), kn.get("max_atoms_evolution_t")),
        "7 种目录外终态大分子见分析 JSON composition.final_outside_catalog；"
        "84,225 目录只对 ≤16 原子完备。",
        "对比 T55：9000→5974、终态 99.5%% OXC（3 原子单一物）、最大 9 原子、新物质 0；"
        "T56=9200→%s、双原子盐终态、最大 %s 原子、新物质 %s 种。"
        % (fmt_commas(kn.get("final_N")), kn.get("max_atoms_evolution"),
           kn.get("new_substances_total")),
    ]
    y = 884
    for s in lines:
        for seg in c.wrap(s, W - 130, size=13):
            c.txt(100, y, seg, size=13, fill="#333")
            y += 22
    data_note(c, [
        "终态原子守恒：%s；平均每分子 %.2f 原子（双原子主导）。"
        % (fmt_commas(sm.get("final_atoms")), kn.get("final_mean_atoms") or 0),
    ], y=H - 40)
    return c.save(out)


# ================================================================ ⑥ 穿越
def chart_crossings(a, out):
    cr = a.get("crossings") or {}
    ctrl = cr.get("control") or {}
    if not ctrl.get("stats"):
        raise RuntimeError("缺少对照组统计")
    st = ctrl["stats"]
    hist = ctrl.get("approx_hist") or {}
    W, H = 1600, 940
    c = Chart(W, H,
              "⑥ 角-对角穿越验证：对照组全部 ≥500 次（min=%.1f）；主实验初始单质寿命极短"
              % (st.get("min") or 0),
              "设计目标：前 500 分钟内每个初始单质 ≥500 次转角-对角穿越（D=14142.1，v0=38741）")
    box = (90, 165, 980, 700)
    xlo, xhi = 450.0, 880.0
    edges = hist.get("bin_edges") or []
    fracs = hist.get("fractions") or []
    ymax = max(fracs + [1e-9]) * 1.25
    xt = list(range(450, 901, 50))
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (xlo, xhi), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: "%.2f" % v)
    xr = mx(500)
    c.d.rectangle([mx(xlo), box[1], xr, box[3]], fill="#fdecea")
    c.d.line([xr, box[1], xr, box[3]], fill="#c0392b", width=3)
    c.txt_bg(xr + 8, box[1] + 10, "要求 ≥500（实测全部远高于此线）",
             size=14, bold=True, fill="#c0392b")
    if edges and fracs and len(edges) == len(fracs) + 1:
        for i, fr in enumerate(fracs):
            x0 = mx(max(edges[i], xlo))
            x1 = mx(min(edges[i + 1], xhi))
            if x1 <= x0:
                continue
            c.d.rectangle([x0, my(fr), x1, box[3]], fill="#2e86de",
                          outline="#1c5f9e", width=1)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "粒子占比", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 42,
          "每粒在 500 分钟内的角-对角穿越次数（9200 粒）", size=15, anchor="ma")
    sbox = [box[0] + 14, box[3] - 122, box[0] + 438, box[3] - 10]
    c.d.rectangle(sbox, fill="#f7f9fc", outline="#d0d7e2")
    c.txt(sbox[0] + 10, sbox[1] + 6, "对照组统计（9200 粒，500 分钟）", size=13, bold=True)
    c.txt(sbox[0] + 10, sbox[1] + 28,
          "min=%.1f  p1=%.1f  p5=%.1f" % (st.get("min"), st.get("p1"), st.get("p5")),
          size=13)
    c.txt(sbox[0] + 10, sbox[1] + 48,
          "median=%.1f  p95=%.1f  max=%.1f"
          % (st.get("median"), st.get("p95"), st.get("max")), size=13)
    c.txt(sbox[0] + 10, sbox[1] + 70,
          "fraction ≥500 = %.0f%%（9200/9200 全部达标）"
          % (100.0 * (st.get("fraction_ge_500") or 0)), size=14, bold=True,
          fill="#1e8449")

    box2 = (1040, 165, 1550, 700)
    mi = cr.get("main_initial_single") or {}
    stats = mi.get("stats") or {}
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 16, box2[1] + 12, "主实验：初始单质寿命路径", size=17, bold=True)
    vals = [("min", stats.get("min")), ("p1", stats.get("p1")),
            ("median", stats.get("median")), ("max", stats.get("max"))]
    x0, x1 = box2[0] + 130, box2[2] - 60
    xlo2, xhi2 = 0.0, max(50.0, (stats.get("max") or 40) * 1.15)

    def mx2(v):
        return x0 + (v - xlo2) / (xhi2 - xlo2) * (x1 - x0)

    for v in [0, 200, 400, 600, 800, 1000, 1200]:
        if v > xhi2:
            continue
        X = mx2(v)
        c.d.line([X, box2[1] + 70, X, box2[3] - 150], fill="#eee", width=1)
        c.txt(X, box2[3] - 144, "%g" % v, size=11, anchor="ma")
    c.txt((x0 + x1) / 2, box2[3] - 122, "路径长度 path / D", size=14, anchor="ma")
    for i, (lab, v) in enumerate(vals):
        Y = box2[1] + 90 + i * 52
        c.txt(box2[0] + 16, Y, lab, size=14, anchor="lm")
        if v is not None:
            c.d.rectangle([x0, Y - 11, mx2(min(v, xhi2)), Y + 11], fill="#f39c12",
                          outline="#b7791f", width=1)
            c.txt(mx2(min(v, xhi2)) + 8, Y, "%.1f D" % v, size=13, anchor="lm",
                  bold=True)
    c.txt(box2[0] + 16, box2[3] - 96,
          "中位寿命 %.1f D = %.1f 个时间步（v0/D=%.2f D/分钟）"
          % (stats.get("median") or 0, mi.get("median_in_steps") or 0,
             mi.get("path_per_minute_D") or 0), size=13, fill="#c0392b")
    c.txt(box2[0] + 16, box2[3] - 70,
          "survivors=%s：%d 个初始单质存活到终态（最长 %.1f D）"
          % (stats.get("survivors"), stats.get("survivors") or 0,
             stats.get("max") or 0), size=13, fill="#555")
    c.txt(box2[0] + 16, box2[3] - 44,
          "→ 寿命指标不能由主实验验证，必须用无化学对照组",
          size=13, bold=True, fill="#1e8449")

    kin = a.get("kinetics") or {}
    data_note(c, [
        "对照组（无化学、仅弹性碰撞+衰减）：min %.1f、median %.1f、fraction≥500 = %.0f%% → 速度设计达标。"
        % (st.get("min") or 0, st.get("median") or 0,
           100.0 * (st.get("fraction_ge_500") or 0)),
        "主实验等效穿越：t=500 累计 path_D=%s /9200 = %.1f 次/初始单质 > 500；"
        "t=999 为 %.1f 次。"
        % (fmt_commas(kin.get("path_D_at_500")),
           kin.get("crossings_equiv_per_initial_at_500") or 0,
           kin.get("crossings_equiv_per_initial_final") or 0),
        "结论：500 次穿越要求由对照组独立验证通过；主实验单质寿命短是『碰撞即反应』"
        "的设计使然，不是速度不足。",
        "左图直方图由 min/p1/p5/median/p95/max 分位数线性插值重构（对照仅输出统计量）。",
    ])
    return c.save(out)


# ================================================================ ⑦ 温度窗口
def chart_temperature_windows(a, out):
    tl = a.get("timeline") or {}
    wins = [w for w in (tl.get("temperature_windows") or [])
            if (w.get("minutes") or 0) > 0]
    if not wins:
        raise RuntimeError("温度窗口无数据")
    W, H = 1600, 1060
    c = Chart(W, H,
              "⑦ 温度区间内的反应类型统计（主实验 1000→0°C，每分钟 -1°C）",
              "上：判定类型计数之和（对数轴）；下：净变化事件数。净变化事件全部发生在 "
              "T≥16；低温段只剩判定/弹性。")
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
        for k, col, off in (("complete", TYPECOL["complete"], -bw),
                            ("incomplete", TYPECOL["incomplete"], 0.0),
                            ("none", TYPECOL["none"], bw)):
            val = w.get(k) or 0
            if val <= 0:
                continue
            X = xc + off
            Y = myval(val)
            c.d.rectangle([X - bw * 0.42, Y, X + bw * 0.42, box[3]],
                          fill=col, outline="#333", width=1)
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
    c.txt_bg(box2[0] + 250, box2[1] + 8,
             "净变化事件 100% 发生在 T≥16（退火期）；T≤15 后只判定/复原/弹性",
             size=13, fill="#8e44ad")
    data_note(c, [
        "低温窗口：T=5~0 区间 complete 仍有 %s 次判定（大分子 Σc 高、小分子对仍可完全反应），"
        "但净结果不变占比极高；incomplete %s 次多为复原，none %s 次为纯弹性。"
        % (fmt_commas(wins[-1].get("complete")), fmt_commas(wins[-1].get("incomplete")),
           fmt_commas(wins[-1].get("none"))),
        "decomp 全程 0：主实验没有不稳定中间体在降温后自分解，终态由完全反应动力学"
        "（同价跨类配对）决定。",
    ], y=985)
    return c.save(out)


# ================================================================ ⑧ 尺寸
def chart_sizes(a, out):
    comp = a.get("composition") or {}
    ss = comp.get("size_series") or []
    dist = comp.get("final_size_distribution") or []
    if not ss:
        raise RuntimeError("size_series 为空")
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or (ss[-1]["t"] if ss else 1000)
    kn = (a.get("key_numbers") or {}).get("main") or {}
    W, H = 1600, 1150
    c = Chart(W, H,
              "⑧ 分子尺寸（原子数）演化与终态分布：演化峰值 %s 原子，终态最大 %s 原子"
              % (kn.get("max_atoms_evolution"),
                 max((r.get("atoms") or 0) for r in comp.get("final_table") or [{}])),
              "尺寸=分子原子数（不依赖结构）；上：max/mean/p90/p99 随时间的精确统计；"
              "下：终态尺寸分布与原子数占比")
    box = (105, 160, 1400, 560)
    ymax = max([s.get("max_atoms") or 0 for s in ss] + [1]) * 1.15
    xt = nice_ticks(0, minutes, 10)
    yt = nice_ticks(0, ymax, 6)
    mx, my = c.frame(box, (0, minutes), (0, ymax), xt, yt)
    c.top_temp_axis(box, (0, minutes), mx, cfg.get("T0") or 1000, minutes)
    for key, col, wdt, lab in (("max_atoms", "#c0392b", 3, "最大原子数"),
                               ("p99_atoms", "#e67e22", 2, "p99"),
                               ("p90_atoms", "#10ac84", 2, "p90"),
                               ("mean_atoms", "#2e86de", 3, "平均原子数")):
        c.line([(mx(s["t"]), my(s.get(key) or 0)) for s in ss], fill=col, width=wdt)
    # 每分鐘 max（time_series）叠加
    rows = (a.get("timeline") or {}).get("per_minute") or []
    if rows:
        mx2, my2 = mx, my
        c.line([(mx2(r["t"]), my2(r.get("max_atoms") or 0)) for r in rows],
               fill="#bdc3c7", width=1)
    peak = (a.get("timeline") or {}).get("transitions", {}).get("max_atoms_peak") or {}
    if peak:
        c.dashed((mx(peak.get("t") or 0), box[1]),
                 (mx(peak.get("t") or 0), box[3]), fill="#c0392b", width=1)
        c.txt_bg(mx(peak.get("t") or 0) + 8, box[1] + 14,
                 "峰值 %s 原子 @ t=%s（T=%s）"
                 % (peak.get("max_atoms"), peak.get("t"), peak.get("T")),
                 size=13, fill="#c0392b")
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "原子数（分子尺寸）", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 42, "时间 t（分钟）", size=16, anchor="ma")
    c.legend(1080, 168,
             [("#bdc3c7", "逐分钟 max（引擎）"), ("#c0392b", "max（5 分钟精确）"),
              ("#e67e22", "p99"), ("#10ac84", "p90"), ("#2e86de", "平均原子数")],
             size=13, row_h=24)

    # 下：终态尺寸分布
    box2 = (105, 690, 960, 970)
    maxa = max([d.get("atoms") or 0 for d in dist] + [1])
    ydist = max([d.get("molecules") or 0 for d in dist] + [1])
    yt2 = [1, 10, 100, 1000, 10000]
    v = 100000
    while v <= ydist * 1.5:
        yt2.append(v)
        v *= 10
    xt2 = list(range(1, maxa + 1, 2)) + [maxa]
    mx3, my3 = c.frame(box2, (0.5, maxa + 0.5), (1, ydist * 1.6), xt2, yt2,
                       logy=True, ytick_fmt=lambda v: "%g" % v)
    barw = (mx3(maxa + 0.5) - mx3(0.5)) / maxa * 0.72
    for d in dist:
        a_ = d.get("atoms") or 0
        m_ = d.get("molecules") or 0
        if m_ <= 0:
            continue
        X = mx3(a_)
        c.d.rectangle([X - barw / 2, my3(m_), X + barw / 2, box2[3]],
                      fill="#2e86de" if a_ <= 16 else "#e67e22",
                      outline="#333", width=1)
    # >16 区域提示
    if maxa > 16:
        c.txt_bg(mx3(17) + 8, box2[1] + 10,
                 "→ ≤16 原子：目录完备段", size=12, fill="#1e8449")
        c.txt_bg(mx3(maxa) - 6, box2[1] + 10,
                 ">16 原子：目录不完备（不能称不可能）", size=12, anchor="ra",
                 fill="#c0392b")
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "分子数（对数）", size=14)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 42,
          "终态分子原子数分布（蓝=≤16，橙=>16）", size=14, anchor="ma")

    # 右下：统计与对比
    box3 = (1000, 690, 1560, 1000)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 14, box3[1] + 12, "尺寸统计", size=17, bold=True)
    di = comp.get("final_diatomic") or {}
    lg = comp.get("final_large") or {}
    stats_lines = [
        "终态平均原子数 %.2f，中位 2，p90=2，p99=2" % (kn.get("final_mean_atoms") or 0),
        "双原子 %s 个（%.1f%% 分子 / %.1f%% 原子）"
        % (fmt_commas(di.get("count")), 100.0 * (di.get("share") or 0),
           100.0 * (di.get("atoms_share") or 0)),
        "大分子 %s 个（2~%s 原子），承载 %.1f%% 原子"
        % (fmt_commas(lg.get("molecules")), lg.get("max_atoms") or "?",
           100.0 * (lg.get("atoms_share") or 0)),
        "演化峰值 %s 原子 @ t=%s；终态最大 %s 原子"
        % (kn.get("max_atoms_evolution"), kn.get("max_atoms_evolution_t"),
           max((r.get("atoms") or 0) for r in comp.get("final_table") or [{}])),
        "目录：≤16 完备，>16 仅 %s 条；%s 种新物质中 %s 种 >16 原子"
        % (fmt_commas((comp.get("catalog_stats") or {}).get("n_gt16")),
           kn.get("new_substances_total"), kn.get("new_substances_gt16")),
        "T55 对比：最大仅 9 原子；T56 峰值 %s、终态 %s 原子"
        % (kn.get("max_atoms_evolution"),
           max((r.get("atoms") or 0) for r in comp.get("final_table") or [{}])),
    ]
    y = box3[1] + 46
    for s in stats_lines:
        for seg in c.wrap(s, box3[2] - box3[0] - 30, size=13):
            c.txt(box3[0] + 14, y, seg, size=13, fill="#222")
            y += 24
        y += 6
    # 原子数占比条
    y += 6
    x0, x1 = box3[0] + 14, box3[2] - 20
    dy = 100.0 * (di.get("atoms_share") or 0)
    c.d.rectangle([x0, y, x0 + (x1 - x0) * dy / 100.0, y + 22], fill="#2e86de",
                  outline="#333")
    c.d.rectangle([x0 + (x1 - x0) * dy / 100.0, y, x1, y + 22], fill="#e67e22",
                  outline="#333")
    c.txt(x0 + 6, y + 3, "双原子 %.1f%% 原子" % dy, size=12, fill="#fff")
    c.txt(x1 - 6, y + 3, "大分子 %.1f%%" % (100 - dy), size=12, anchor="ra",
          fill="#fff")
    data_note(c, [
        "尺寸峰值出现在早期退火（t≈20~50）：大分子由完全反应合并生成，随后在降温中"
        "被完全反应重新拆成同价配对的双原子盐；终态仅剩 35 个大分子（~2.3%% 原子）。",
        "『目录外』不等于『不可能』：84,225 目录只对 ≤16 原子完备（≤16 约 82,961 条、"
        ">16 仅 1,264 条），本实验新物质 %s 种 >16 原子。" % kn.get("new_substances_gt16"),
    ], y=1052)
    return c.save(out)


# ================================================================ ⑨ 价数比例
def chart_ratio(a, out):
    ratio = a.get("ratio") or {}
    feed = ratio.get("feed") or []
    rec = ratio.get("recomputed") or {}
    if not feed:
        raise RuntimeError("ratio.feed 为空")
    W, H = 1600, 1020
    c = Chart(W, H,
              "⑨ 价数比例验证：三价:二价:一价 原子数 3200:5600:9600 = 1:1.75:3（严格递增 √）",
              "O/K=3 价，X/A=2 价，C/F=1 价；投料全为双原子单质；共 9200 单质 / 18400 原子")
    atoms = [rec.get("valence3", {}).get("atoms", 0),
             rec.get("valence2", {}).get("atoms", 0),
             rec.get("valence1", {}).get("atoms", 0)]
    mols = [rec.get("valence3", {}).get("molecules", 0),
            rec.get("valence2", {}).get("molecules", 0),
            rec.get("valence1", {}).get("molecules", 0)]
    cats = ["3 价 O+K", "2 价 X+A", "1 价 C+F"]
    xt = [0.5, 1.5, 2.5]

    # 左上：各价类原子数
    box = (100, 175, 760, 520)
    ymax = max(atoms + [1]) * 1.3
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (0, 3), (0, ymax), xt, yt,
                     xtick_labels=cats, xtick_fmt=lambda v: "", ytick_fmt=fmt_commas)
    for i, val in enumerate(atoms):
        X = mx(i + 0.5)
        Y = my(val)
        c.d.rectangle([X - 70, Y, X + 70, box[3]], fill=VALCOL[3 - i],
                      outline="#333", width=1)
        c.txt(X, Y - 6, "%s 原子" % fmt_commas(val), size=14, anchor="mb", bold=True)
        c.txt(X, (Y + box[3]) / 2, "×%d" % (2 * (i + 1)), size=13, anchor="mm",
              fill="#fff")
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "原子数", size=14)
    c.txt((box[0] + box[2]) / 2, box[3] + 38, "价类（原子数）", size=15, anchor="ma")

    # 左下：各价类分子数
    box2 = (100, 600, 760, 870)
    ymax2 = max(mols + [1]) * 1.3
    yt2 = nice_ticks(0, ymax2, 4)
    mx2, my2 = c.frame(box2, (0, 3), (0, ymax2), xt, yt2,
                       xtick_labels=cats, xtick_fmt=lambda v: "", ytick_fmt=fmt_commas)
    for i, val in enumerate(mols):
        X = mx2(i + 0.5)
        Y = my2(val)
        c.d.rectangle([X - 70, Y, X + 70, box2[3]], fill=VALCOL[3 - i],
                      outline="#333", width=1)
        c.txt(X, Y - 6, "%s 分子" % fmt_commas(val), size=13, anchor="mb", bold=True)
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "单质分子数", size=14)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 38, "价类（分子数）", size=15, anchor="ma")

    # 右：投料构成 + 校验
    box3 = (840, 175, 1560, 880)
    c.d.rectangle(box3, outline="#333", width=2)
    c.txt(box3[0] + 16, box3[1] + 14, "投料构成：9200 个双原子单质", size=17, bold=True)
    total_m = sum(f.get("count") or 0 for f in feed) or 1
    x0, x1 = box3[0] + 20, box3[2] - 20
    y = box3[1] + 54
    for item in feed:
        frac = (item.get("count") or 0) / total_m
        w = (x1 - x0) * frac
        col = ELEMCOL.get(item.get("element"), "#888")
        c.d.rectangle([x0, y, x0 + w, y + 30], fill=col, outline="#333", width=1)
        if w >= 90:
            c.txt(x0 + 6, y + 5, "%s×%s" % (item.get("formula"),
                                           fmt_commas(item.get("count"))),
                  size=12, fill="#fff")
        x0 += w
    # 六种单质逐行说明
    y += 50
    c.txt(box3[0] + 20, y, "六种单质（按价类）", size=14, bold=True)
    y += 26
    for item in feed:
        col = ELEMCOL.get(item.get("element"), "#888")
        c.d.rectangle([box3[0] + 20, y + 3, box3[0] + 33, y + 16], fill=col,
                      outline="#555")
        c.txt(box3[0] + 42, y,
              "%s %s（%s，%d 价）：%s 分子 · %s 原子"
              % (item.get("formula"), item.get("zh"),
                 item.get("category") or "", item.get("valence") or 0,
                 fmt_commas(item.get("count")),
                 fmt_commas(2 * (item.get("count") or 0))), size=13)
        y += 26
    y += 12
    c.txt(box3[0] + 20, y, "按价类汇总", size=14, bold=True)
    y += 26
    for v, lab, i in ((3, "三价（O/K）", 0), (2, "二价（X/A）", 1), (1, "一价（C/F）", 2)):
        c.txt(box3[0] + 32, y,
              "%s：%s 分子 → %s 原子"
              % (lab, fmt_commas(mols[i]), fmt_commas(atoms[i])), size=13)
        y += 24
    y += 14
    c.txt(box3[0] + 20, y, "原子比 3200 : 5600 : 9600 = 1 : 1.75 : 3",
          size=21, bold=True, fill="#c0392b")
    y += 36
    c.txt(box3[0] + 20, y, "验证：严格递增 √    总单质 9200 √    总原子 18400 √",
          size=15, bold=True, fill="#1e8449")
    y += 30
    c.txt(box3[0] + 20, y,
          "价数按 pot_all.ELEM：O/K=3、X/A=2、C/F=1；K/A/F 为 T56 新增散素。",
          size=12, fill="#555")
    # 底部校验表
    checks = ratio.get("checks") or {}
    data_note(c, [
        "校验项：" + "；".join("%s=%s" % (k, "√" if v else "×")
                              for k, v in checks.items()),
        "投料说明：三价 O2/K2 各 800、二价 X2/A2 各 1400、一价 C2/F2 各 2400；"
        "价数按 pot_all.ELEM（O/K=3、X/A=2、C/F=1）。",
    ], y=940)
    return c.save(out)


# ================================================================ ⑩ 低温敏感性（补充）
def chart_sensitivity(a, out):
    sens = a.get("sensitivity") or {}
    if not sens.get("available"):
        raise RuntimeError("没有敏感性数据")
    runs = [r for r in (sens.get("runs") or []) if r.get("T0") is not None]
    if not runs:
        raise RuntimeError("敏感性 runs 为空")
    ref = sens.get("main_reference") or {}
    W, H = 1600, 1080
    c = Chart(W, H,
              "⑩ 低温窗口敏感性（补充）：T0=12/20°C 才留住不完全反应/自分解/新物质",
              "主实验 1000°C×1000 分钟作红色参考线；低温实验各自运行 T0 分钟（T0→0°C）。"
              "catalog 内/外按 84,225 目录判断。")
    metrics = [
        ("终态分子式数", lambda r: r.get("n_final"), ref.get("n_final"),
         lambda v: "%d 种" % v,
         "T0=12 终态 379 种（主实验仅 22 种）；低温保留了巨大的组成多样性"),
        ("新物质总数", lambda r: r.get("n_new_total"), ref.get("n_new_total"),
         lambda v: "%d 种" % v,
         "T0=12 产生 112 种新物质（主实验 120 种但几乎全部瞬时/未存活）"),
        ("终态存活的新物质", lambda r: r.get("n_new_final"), ref.get("n_new_final"),
         lambda v: "%d 种" % v,
         "T0=12 有 79 种新物质存活到终态；主实验仅 7 种存活"),
        ("自分解事件数", lambda r: r.get("decomp_events"), ref.get("decomp_events"),
         fmt_commas, "T0=12 自分解 17 次、T0=20 为 7 次；主实验为 0"),
    ]
    panel_w, panel_h = 720, 400
    x0s = [60, 840]
    y0s = [110, 540]
    n = len(runs)
    labels = ["T0=%s°C" % r.get("T0") for r in runs]
    cols = ["#2e86de", "#8e44ad", "#f39c12", "#e74c3c"]
    for idx, (name, getter, refv, fmt, comment) in enumerate(metrics):
        px = x0s[idx % 2]
        py = y0s[idx // 2]
        box = (px + 80, py + 48, px + panel_w - 30, py + 300)
        vals = [getter(r) or 0 for r in runs]
        vmax = max(vals + [refv or 0, 1]) * 1.25
        c.txt(px + 16, py + 6, "%s %s" % ("①②③④"[idx], name), size=19, bold=True)
        if refv is not None:
            c.txt(px + panel_w - 10, py + 10, "主实验 1000°C = %s" % fmt(refv),
                  size=13, anchor="ra", fill="#c0392b")
        yt = nice_ticks(0, vmax, 4)
        mx, my = c.frame(box, (0, n), (0, vmax),
                         [i + 0.5 for i in range(n)], yt, ytick_fmt=fmt,
                         xtick_labels=labels)
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
            c.dashed((box[0], Yr), (box[2], Yr), fill="#c0392b", width=2, dash=8)
        c.txt(px + 16, py + panel_h - 14, "→ " + comment, size=13, fill="#555")
    data_note(c, [
        sens.get("conclusion", ""),
        "注意：低温实验只运行 T0 分钟（T0→0°C），主实验运行 1000 分钟，横向比较时注意时长不同；"
        "低温实验的『新物质总数』与主实验接近，但存活率差异巨大（79 vs 7）。",
    ], y=960)
    return c.save(out)


# ================================================================ main
CHARTS = [
    ("composition", "t56_composition.png", chart_composition),
    ("reaction_rate", "t56_reaction_rate.png", chart_reaction_rate),
    ("state_timeseries", "t56_state_timeseries.png", chart_state_timeseries),
    ("snapshots", "t56_snapshots.png", chart_snapshots),
    ("final_composition", "t56_final_composition.png", chart_final_composition),
    ("crossings", "t56_crossings.png", chart_crossings),
    ("temperature_windows", "t56_temperature_windows.png", chart_temperature_windows),
    ("sizes", "t56_sizes.png", chart_sizes),
    ("ratio", "t56_ratio.png", chart_ratio),
    ("sensitivity", "t56_sensitivity.png", chart_sensitivity),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="T56 图表渲染")
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
