# -*- coding: utf-8 -*-
"""t55_render.py —— T55 实验图表（Pillow 绘制，中文 msyh）

读取 t55_analysis.json，生成：
  images/t55_composition.png        ① 组成随时间堆叠图（top 分子式 + OXC 占比/物种数）
  images/t55_reaction_rate.png      ② 反应计数/分钟 + 温度轴（双轴）+ 净变化事件/分钟
  images/t55_state_timeseries.png   ③ 速度 / 粒子数 / 平均原子数 三联图
  images/t55_snapshots.png          ④ 2D 快照拼图（8 帧，按元素组合上色）
  images/t55_final_composition.png  ⑤ 终态 top20 条形图（29 内绿色 / 新物质橙色）
  images/t55_crossings.png          ⑥ 对照组穿越次数直方图 + 500 要求线；主实验初始单质寿命
  images/t55_temperature_windows.png⑦ 温度区间反应类型统计
  images/t55_sensitivity.png        ⑧ 温度标度敏感性（T0=6/8/12/20 + 主实验 1000°C 参考）

用法：
  python t55_render.py
  python t55_render.py --analysis t55_analysis.json --images images
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_ANALYSIS = os.path.join(BASE, "t55_analysis.json")
DEFAULT_IMAGES = os.path.join(BASE, "images")

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT_REG

# 配色（尽量与项目既有图一致）
PAL = ["#2e86de", "#ee5253", "#10ac84", "#f39c12", "#8e44ad", "#16a085",
       "#d35400", "#2c3e50", "#c0392b", "#7f8c8d", "#27ae60", "#e84393"]
TYPECOL = {"complete": "#e74c3c", "incomplete": "#f39c12",
           "none": "#95a5a6", "decomp": "#8e44ad"}
SNAPCOL = {0: "#2ecc71", 1: "#f39c12", 2: "#3498db", 3: "#9b59b6",
           4: "#1abc9c", 5: "#e74c3c", 6: "#00acc1"}
GREEN = "#2e8b57"
ORANGE = "#e67e22"
GRAY = "#7f8c8d"


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
    out = []
    v = first
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
        self._map = (lambda v: v, lambda v: v)
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
        """带白底文字（避免压在曲线/散点上）。"""
        f = self.f(size, bold)
        w = f.getlength(s)
        h = size + 6
        if anchor.startswith("l"):
            left = x
        elif anchor.startswith("r"):
            left = x - w
        else:  # m*
            left = x - w / 2
        if anchor.endswith("a"):
            top = y
        elif anchor.endswith("m"):
            top = y - h / 2
        else:  # b
            top = y - h
        box = [left - pad, top - pad + 1, left + w + pad, top + h - pad]
        self.d.rectangle(box, fill=bg, outline=outline or bg)
        self.txt(x, y, s, size=size, bold=bold, fill=fill, anchor=anchor)

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

    def rot(self, x, y, s, size=14, bold=False, fill="#222"):
        f = self.f(size, bold)
        tw = int(f.getlength(s)) + 8
        th = int(size) + 10
        tmp = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
        ImageDraw.Draw(tmp).text((4, 3), s, font=f, fill=fill)
        tmp = tmp.rotate(90, expand=True)
        self.img.paste(tmp, (int(x - tmp.width / 2), int(y - tmp.height / 2)), tmp)

    # ---- 坐标框 ----
    def frame(self, box, xlim, ylim, xticks, yticks, grid=True, logy=False,
              logx=False, xtick_fmt=None, ytick_fmt=None, tick_size=13,
              grid_color="#e9e9e9", border_color="#333", xtick_labels=None):
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

        self._map = (mx, my)
        if grid:
            for xv in xticks:
                if not (xlo <= float(xv) <= xhi):
                    continue
                self.d.line([mx(xv), y0, mx(xv), y1], fill=grid_color, width=1)
            for yv in yticks:
                if not (ylo <= float(yv) <= yhi):
                    continue
                self.d.line([x0, my(yv), x1, my(yv)], fill=grid_color, width=1)
        # 边框
        self.d.rectangle([x0, y0, x1, y1], outline=border_color, width=2)
        # x 轴刻度
        fmt_x = xtick_fmt or (lambda v: ("%g" % v))
        for i, xv in enumerate(xticks):
            if not (xlo <= float(xv) <= xhi):
                continue
            X = mx(xv)
            self.d.line([X, y1, X, y1 + 6], fill="#333", width=1)
            lab = (xtick_labels[i] if xtick_labels is not None and i < len(xtick_labels)
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


def series_values(rows, key, default=None):
    return [r.get(key, default) for r in rows]


def data_note(c, lines, y=None, size=13, color="#555", x=36):
    wrapped = []
    for s in lines:
        wrapped.extend(c.wrap(s, c.W - x - 24, size=size))
    y = c.H - 18 - 22 * len(wrapped) if y is None else y
    for i, s in enumerate(wrapped):
        c.txt(x, y + i * 22, s, size=size, fill=color)


# ================================================================ ① 组成堆叠
def chart_composition(a, out):
    comp = a.get("composition") or {}
    cfg = a.get("config") or {}
    series = comp.get("series") or []
    minutes = cfg.get("minutes") or (series[-1]["t"] if series else 100)
    T0 = cfg.get("T0") or 1000
    if not series:
        raise RuntimeError("composition.series 为空")
    W, H = 1600, 1120
    c = Chart(W, H,
              "① 组成随时间的演化：9000 个初始单质 → 完全反应退火 → OXC 基态",
              "每 5 分钟完整组成；堆叠 = top 分子式数量（t=0 已含第 0 分钟反应）；"
              "初始 C2/X2/O2 各 3000 个（未绘于 t=0 之前）")
    box = (100, 152, 1320, 640)
    totals = [r.get("total") or 0 for r in series]
    ymax = max(totals + [1]) * 1.12
    xticks = nice_ticks(0, minutes, 10)
    yticks = nice_ticks(0, ymax, 6)
    mx, my = c.frame(box, (0, minutes), (0, ymax), xticks, yticks,
                     ytick_fmt=lambda v: fmt_commas(v))
    c.top_temp_axis(box, (0, minutes), mx, T0, minutes)
    # 堆叠填充
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
    # 图例
    items = []
    for i, f in enumerate(comp.get("stack_order") or []):
        zh = (comp.get("top_formulas") or [{}])[i].get("zh", "") if i < len(
            comp.get("top_formulas") or []) else ""
        items.append((PAL[i % len(PAL)], "%s %s" % (f, zh)))
    items.append((PAL[len(comp.get("stack_order") or []) % len(PAL)], "其它分子式"))
    c.txt(1336, 150, "分子式（颜色）", size=16, bold=True)
    c.legend(1336, 186, items, size=13, row_h=27)

    # 下方：OXC 占比 + 终态物种数
    box2 = (100, 700, 1320, 890)
    oxc = [r.get("oxc_share") or 0.0 for r in series]
    dist = [r.get("n_distinct") or 0 for r in series]
    y2max = max(dist + [1]) * 1.15
    xt2 = nice_ticks(0, minutes, 10)
    yt2 = [0, 0.25, 0.5, 0.75, 1.0]
    mx2, my2 = c.frame(box2, (0, minutes), (0, 1.0), xt2, yt2,
                       ytick_fmt=lambda v: "%.0f%%" % (v * 100))
    # 右轴：物种数
    myr = c.right_axis(box2, (0, y2max), nice_ticks(0, y2max, 5),
                       label="物种数", color="#2e86de")
    c.d.line([(mx2(series[j]["t"]), my2(oxc[j])) for j in range(n)],
             fill="#c0392b", width=3)
    c.d.line([(mx2(series[j]["t"]), myr(dist[j])) for j in range(n)],
             fill="#2e86de", width=2)
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 42, "时间 t（分钟）", size=16, anchor="ma")
    c.rot(box2[0] - 58, (box2[1] + box2[3]) / 2, "OXC 占比", size=14, fill="#c0392b")
    # 里程碑竖线
    for tv, lab, col in [(866, "净变化停止 t=866 (T=134)", "#7f8c8d")]:
        if 0 <= tv <= minutes:
            c.dashed((mx2(tv), box2[1]), (mx2(tv), box2[3]), fill=col, width=2)
            c.txt_bg(mx2(tv) - 6, box2[1] + 6, lab, size=12, anchor="ra", fill=col)
    # 图例放右侧留白（不压线）
    c.legend(1410, 760,
             [("#c0392b", "OXC 占比"), ("#2e86de", "物种数")],
             size=13, row_h=24)
    trans = (a.get("timeline") or {}).get("transitions") or {}
    ann = trans.get("annealing") or {}
    ms = ann.get("oxc_share_milestones") or {}
    m50 = ms.get("50%") or {}
    m635 = ms.get("63.5%") or {}
    m90 = ms.get("90%") or {}
    m99 = ms.get("99%") or {}
    if m50.get("bracket"):
        s50 = "50%% @ t≈%.1f（t=%s: %.1f%% → t=%s: %.1f%%）" % (
            m50.get("t"), m50["bracket"][0], 100 * m50["shares"][0],
            m50["bracket"][1], 100 * m50["shares"][1])
    else:
        s50 = "50%% @ t≈%s" % _t(m50)
    s90 = ("90%% @ t=%s（T=%s，样本 %.1f%%；插值 t≈%.1f）"
           % (m90.get("sample_t", _t(m90)), _T(m90),
              100 * (m90.get("sample_share") or 0), m90.get("t") or 0)
           if m90.get("sample_t") is not None else "90%% @ t≈%s" % _t(m90))
    s99 = ("99%% @ t=%s（样本 %.2f%%；插值 t≈%.1f）"
           % (m99.get("sample_t", _t(m99)),
              100 * (m99.get("sample_share") or 0), m99.get("t") or 0)
           if m99.get("sample_t") is not None else "99%% @ t≈%s" % _t(m99))
    data_note(c, [
        "退火里程碑：OXC 占比 " + s50 + "、63.5%% @ t=%s；" % _t(m635),
        "%s、%s、99.5%% @ 终态（t=%s）。" % (s90, s99, _t(ms.get("99.5%（终态）"))),
        "净变化事件最后出现在 t=866（T=134）；终态：N=%s 个分子、%s 个原子，"
        "OXC %s 个 = %.1f%%，仅 %d 种分子式（全部在 29 聚素内）。"
        % (fmt_commas((a.get("summary") or {}).get("final_N")),
           fmt_commas((a.get("summary") or {}).get("final_atoms")),
           fmt_commas(_oxc_count(comp)), _oxc_share(comp) * 100,
           comp.get("final_total_formulas") or 0),
    ], y=1000)
    return c.save(out)


def _t(ms):
    return ms.get("t") if ms else "-"


def _T(ms):
    return ms.get("T") if ms else "-"


def _oxc_count(comp):
    for r in comp.get("final_table") or []:
        if r.get("formula") == "OXC":
            return r.get("count")
    return None


def _oxc_share(comp):
    for r in comp.get("final_table") or []:
        if r.get("formula") == "OXC":
            return r.get("share") or 0.0
    return 0.0


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
              "左轴=判定次数（对数），右轴=温度（T=T0-t，虚线）；"
              "complete 含大量净结果不变的完全判定（F 不动点），真正化学事件看下图")
    # --- 上图：判定计数（对数）+ 温度右轴
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
                     ytick_fmt=lambda v: ("0" if v < 1 else "%g" % v))
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
    # 关键竖线 + 标签（错开高度，避免右侧拥挤）
    marks = [(866, "净变化停止 t=866 (T=134)", box[1] + 8, "la", "#c0392b"),
             (995, "complete→0（T=5）", box[1] + 62, "ra", "#c0392b"),
             (998, "none 出现（T=2）", box[1] + 92, "ra", "#c0392b")]
    for tv, lab, ty, anch, col in marks:
        if 0 <= tv <= minutes:
            c.dashed((mx(tv), box[1]), (mx(tv), box[3]), fill=col, width=1)
            c.txt_bg(mx(tv) + (4 if anch == "la" else -4), ty, lab, size=12,
                     anchor=anch, fill=col)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "判定次数/分钟（对数）", size=14)
    # 图例放在图框上方（不压曲线）
    c.legend(box[0] + 4, box[1] - 42,
             [(TYPECOL["complete"], "complete（完全反应判定，含净不变）"),
              (TYPECOL["incomplete"], "incomplete（不完全反应判定）"),
              (TYPECOL["none"], "none（不反应/弹性）")],
             size=13, row_h=24, cols=3, col_w=380)

    # --- 下图：净变化事件/分钟
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
    c.txt_bg(box2[0] + 12, box2[1] + 8, "t=0 分钟：3,283 次净变化事件（初始单质合并）",
             size=13, fill="#8e44ad")
    met = sum(ev)
    c.txt_bg(box2[0] + 12, box2[1] + 32,
             "全程净变化事件 %s 次，仅 %d 分钟发生；t=866（T=134）后为 0。"
             % (fmt_commas(met), sum(1 for x in ev if x > 0)), size=13, fill="#555")
    data_note(c, [
        "判定计数合计 %s = 碰撞数（complete %s / incomplete %s / none %s）；"
        "其中 %.1f%% 的 complete 判定净结果不变（F 不动点，如 OXC+OXC→OXC+OXC）。"
        % (fmt_commas(sum((r.get("collisions") or 0) for r in rows)),
           fmt_commas(sum((r.get("complete") or 0) for r in rows)),
           fmt_commas(sum((r.get("incomplete") or 0) for r in rows)),
           fmt_commas(sum((r.get("none") or 0) for r in rows)),
           100.0 * ((a.get("events") or {}).get("complete_noop_ratio") or 0.0)),
        "温度阈值行为：T≥6 时 complete 仍触发（无净变化）；T≤5 时 complete 归零、"
        "incomplete 出现；T≤2 时出现 none（纯弹性）。decomp 全程为 0。",
    ])
    return c.save(out)


# ================================================================ ③ 状态时间序列
def chart_state_timeseries(a, out):
    rows = (a.get("timeline") or {}).get("per_minute") or []
    cfg = a.get("config") or {}
    minutes = cfg.get("minutes") or len(rows)
    T0 = cfg.get("T0") or 1000
    if not rows:
        raise RuntimeError("timeline.per_minute 为空")
    W, H = 1600, 1080
    c = Chart(W, H,
              "③ 速度 / 粒子数 / 平均原子数 随时间变化",
              "速度按每次碰撞衰减 ε=0.2%；粒子数先降（合并）后回升（完全反应重排）；"
              "平均原子数在大分子峰后回落到 OXC 值 3")
    xt = nice_ticks(0, minutes, 10)
    kin = a.get("kinetics") or {}
    half = ((a.get("timeline") or {}).get("transitions") or {}).get("speed_half")

    # --- 速度
    box = (130, 170, 1430, 380)
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

    # --- 粒子数
    box2 = (130, 455, 1430, 655)
    N = [r.get("N") or 0 for r in rows]
    ymax2 = max(N + [1]) * 1.12
    yt2 = nice_ticks(0, ymax2, 5)
    mx2, my2 = c.frame(box2, (0, minutes), (0, ymax2), xt, yt2,
                       ytick_fmt=lambda v: fmt_commas(v))
    c.line([(mx2(r["t"]), my2(r.get("N") or 0)) for r in rows],
           fill="#2e86de", width=3)
    c.rot(box2[0] - 60, (box2[1] + box2[3]) / 2, "粒子数 N", size=14)
    nmin = kin.get("N_min") or {}
    c.txt_bg(box2[2] - 16, box2[3] - 30,
             "N 最小 %s @ t=%s（合并峰）；终态 N=%s（初始 9000）"
             % (fmt_commas(nmin.get("N")), nmin.get("t"),
                fmt_commas(kin.get("N_final"))),
             size=13, anchor="ra", fill="#2e86de")

    # --- 平均原子数（+ max_atoms 右轴）
    box3 = (130, 730, 1400, 920)
    ma = [r.get("mean_atoms") or 0 for r in rows]
    maxa = [r.get("max_atoms") or 0 for r in rows]
    ymax3 = max(ma + [1]) * 1.25
    yt3 = nice_ticks(0, ymax3, 5)
    mx_, my3 = c.frame(box3, (0, minutes), (0, ymax3), xt, yt3)
    myr = c.right_axis(box3, (0, max(maxa + [1]) * 1.2),
                       nice_ticks(0, max(maxa + [1]) * 1.2, 4),
                       label="最大原子数", color="#7f8c8d")
    c.line([(mx_(r["t"]), my3(r.get("mean_atoms") or 0)) for r in rows],
           fill="#10ac84", width=3)
    c.line([(mx_(r["t"]), myr(r.get("max_atoms") or 0)) for r in rows],
           fill="#7f8c8d", width=2)
    c.rot(box3[0] - 60, (box3[1] + box3[3]) / 2, "平均原子数", size=14)
    c.txt((box3[0] + box3[2]) / 2, box3[3] + 40, "时间 t（分钟）", size=16, anchor="ma")
    peak = kin.get("mean_atoms_peak") or {}
    c.txt_bg(box3[2] - 16, box3[1] + 12,
             "峰值 %.2f @ t=%s；终态 %.3f（OXC=3 原子）"
             % (peak.get("mean_atoms") or 0, peak.get("t"),
                (kin.get("samples") or [{}])[-1].get("mean_atoms") or 0),
             size=13, anchor="ra", fill="#10ac84")
    data_note(c, [
        "速度从 %.0f 衰减到 %.0f（保留 %.1f%%），半速时间 t=%s；"
        "自由程随粒子数变化（约 6,000~30,000）。"
        % (kin.get("speed_initial") or 0, kin.get("speed_final") or 0,
           100.0 * (kin.get("speed_ratio") or 0), (half or {}).get("t", "-")),
        "原子数守恒：始终 18,000；N 从 9000 降到终态 %s，平均原子数 2→4.15→3.01。"
        % fmt_commas(kin.get("N_final")),
    ], y=990)
    return c.save(out)


# ================================================================ ④ 快照拼图
def _pick_snapshots(snaps, targets, max_n=8):
    snaps = [s for s in snaps if s.get("points")]
    if not snaps:
        return []
    used = set()
    out = []
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
    chosen = _pick_snapshots(snaps, [0, 25, 50, 100, 200, 400, 700, 995], 8)
    if not chosen:
        raise RuntimeError("没有可用 snapshots")
    cfg = a.get("config") or {}
    L = cfg.get("L") or 10000
    cols = 4
    rows = max(1, math.ceil(len(chosen) / cols))
    pw, ph = 365, 400
    W = cols * pw + 40
    H = 150 + rows * ph + 80
    c = Chart(W, H,
              "④ 2D 粒子环境快照（每帧 ≤3000 个分子，按元素组合上色）",
              "颜色 = 分子包含的元素组合；t=25 后 O+X+C 类（OXC）占绝对多数，空间分布保持均匀"
              "（O+X+C 用青蓝色表示）")
    for i, s in enumerate(chosen):
        r, col = divmod(i, cols)
        x0 = 30 + col * pw
        y0 = 120 + r * ph
        box = (x0, y0, x0 + pw - 18, y0 + ph - 62)
        c.d.rectangle(box, fill="#fbfbfb", outline="#ccc", width=1)
        pts = s.get("points") or []
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        rad = 2.4 if len(pts) > 1500 else 3.0
        for p in pts:
            if len(p) < 3:
                continue
            px = box[0] + max(0.0, min(1.0, p[0] / L)) * bw
            py = box[3] - max(0.0, min(1.0, p[1] / L)) * bh
            colr = SNAPCOL.get(int(p[2]), "#888")
            c.d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=colr)
        counts = {}
        for p in pts:
            if len(p) >= 3:
                counts[int(p[2])] = counts.get(int(p[2]), 0) + 1
        dom = max(counts.items(), key=lambda kv: kv[1]) if counts else (6, 0)
        # 白色信息框（避免压点）
        inf = [box[0] + 6, box[1] + 6, box[0] + 214, box[1] + 58]
        c.d.rectangle(inf, fill="#ffffff", outline="#d9d9d9")
        c.txt(inf[0] + 8, inf[1] + 6, "t=%s  T=%s" % (
            s.get("t"), (a.get("config") or {}).get("T0", 1000) - (s.get("t") or 0)),
            size=15, bold=True, fill="#111")
        c.txt(inf[0] + 8, inf[1] + 29,
              "主导：%s（%.1f%%）" % (_snap_label(dom[0]),
                                   100.0 * dom[1] / max(1, len(pts))),
              size=13, fill="#444")
        c.d.rectangle(box, outline="#999", width=1)
    # 图例
    legend = [(SNAPCOL[0], "0=O(秩)"), (SNAPCOL[1], "1=X(晶)"), (SNAPCOL[2], "2=C(冰)"),
              (SNAPCOL[3], "3=O+X"), (SNAPCOL[4], "4=O+C"), (SNAPCOL[5], "5=X+C"),
              (SNAPCOL[6], "6=O+X+C")]
    c.legend(60, H - 56, legend, size=14, row_h=24, cols=7, col_w=200)
    return c.save(out)


def _snap_label(code):
    return {0: "O(秩)", 1: "X(晶)", 2: "C(冰)", 3: "O+X", 4: "O+C",
            5: "X+C", 6: "O+X+C"}.get(code, "?")


# ================================================================ ⑤ 终态组成
def chart_final_composition(a, out):
    comp = a.get("composition") or {}
    table = (comp.get("final_table") or [])[:20]
    if not table:
        raise RuntimeError("final_table 为空")
    sm = a.get("summary") or {}
    W, H = 1600, 1040
    c = Chart(W, H,
              "⑤ 终态组成：N=%s、原子 %s，OXC（秩晶冰）占 %.1f%%"
              % (fmt_commas(sm.get("final_N")), fmt_commas(sm.get("final_atoms")),
                 _oxc_share(comp) * 100),
              "横轴为对数刻度（数量 2~5945 跨度大）；绿色=29 聚素内，橙色=29 聚素外新物质（本次为 0）")
    box = (470, 150, 1450, 800)
    vmax = max([r.get("count") or 1 for r in table] + [1]) * 2.2
    vmin = 1.0
    yt = [1, 10, 100, 1000, 10000]
    yt = [v for v in yt if v <= vmax] or [1, 10]
    xt = nice_ticks(0, 1, 1)
    # 逻辑：y=条目，x=数量（对数）→ 手动画框
    x0, y0, x1, y1 = box
    logmin, logmax = math.log10(vmin), math.log10(max(vmax, 10))

    def mx(v):
        v = max(vmin, float(v))
        return x0 + (math.log10(v) - logmin) / (logmax - logmin) * (x1 - x0)

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
        known = bool(r.get("known29"))
        col = GREEN if known else ORANGE
        cnt = r.get("count") or 0
        bar_h = min(row_h * 0.62, 42)
        c.d.rectangle([x0 + 1, cy - bar_h / 2, mx(cnt), cy + bar_h / 2],
                      fill=col, outline="#333", width=1)
        label = "%s  %s" % (r.get("formula"), r.get("zh") or "")
        c.txt(x0 - 14, cy, label, size=14, anchor="rm", bold=True)
        c.txt(mx(cnt) + 8, cy, "%s（%.2f%%）"
              % (fmt_commas(cnt), 100.0 * (r.get("share") or 0)),
              size=13, anchor="lm", fill="#333")
    # 右侧摘要
    c.txt(470, 864, "终态共 %d 种分子式（count>0）：29 聚素内 %d 种、新物质 %d 种；全部在大锅目录内。"
          % (comp.get("final_total_formulas") or 0,
             sum(1 for r in table if r.get("known29")),
             sum(1 for r in table if not r.get("known29"))),
          size=14, fill="#333")
    data_note(c, [
        "绿色=29 聚素内；橙色=新物质（本次 T0=1000°C 主实验未产生任何 29 聚素外分子式）。",
        "OXC（秩晶冰，3 原子）是 F 不动点：5945 个 = 99.5%%，其余 8 种为少量残留大分子。",
        "终态平均原子数 3.013；初始 9000 个双原子单质经完全反应退火为 OXC 基态。",
    ], y=900)
    return c.save(out)


# ================================================================ ⑥ 穿越验证
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
              "设计目标：前 500 分钟内每个初始单质 ≥500 次转角-对角穿越（角-对角距离 D=14142.1，v0=38197）")
    # ---- 左：对照组分布（分位数重构直方图）
    box = (90, 165, 980, 700)
    xlo, xhi = 450.0, 880.0
    edges = hist.get("bin_edges") or []
    fracs = hist.get("fractions") or []
    ymax = max(fracs + [1e-9]) * 1.25
    xt = list(range(450, 901, 50))
    yt = nice_ticks(0, ymax, 5)
    mx, my = c.frame(box, (xlo, xhi), (0, ymax), xt, yt,
                     ytick_fmt=lambda v: "%.2f" % v)
    # 500 需求线 + 不达标区
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
          "每粒在 500 分钟内的角-对角穿越次数（9000 粒）", size=15, anchor="ma")
    # 统计信息放左下方空白浅色框（避开直方图与红线）
    sbox = [box[0] + 14, box[3] - 122, box[0] + 438, box[3] - 10]
    c.d.rectangle(sbox, fill="#f7f9fc", outline="#d0d7e2")
    c.txt(sbox[0] + 10, sbox[1] + 6, "对照组统计（9000 粒，500 分钟）",
          size=13, bold=True, fill="#333")
    c.txt(sbox[0] + 10, sbox[1] + 28,
          "min=%.1f  p1=%.1f  p5=%.1f" % (st.get("min"), st.get("p1"), st.get("p5")),
          size=13, fill="#333")
    c.txt(sbox[0] + 10, sbox[1] + 48,
          "median=%.1f  p95=%.1f  max=%.1f"
          % (st.get("median"), st.get("p95"), st.get("max")), size=13, fill="#333")
    c.txt(sbox[0] + 10, sbox[1] + 70,
          "fraction ≥500 = %.0f%%（9000/9000 全部达标）"
          % (100.0 * (st.get("fraction_ge_500") or 0)), size=14, bold=True,
          fill="#1e8449")
    c.txt(box[0] + 14, box[3] - 44,
          "", size=12, fill="#777")

    # ---- 右：主实验初始单质寿命路径
    box2 = (1040, 165, 1550, 700)
    mi = cr.get("main_initial_single") or {}
    stats = mi.get("stats") or {}
    c.d.rectangle(box2, outline="#333", width=2)
    c.txt(box2[0] + 16, box2[1] + 12, "主实验：初始单质寿命路径", size=17, bold=True)
    vals = [("min", stats.get("min")), ("p1", stats.get("p1")),
            ("median", stats.get("median")), ("max", stats.get("max"))]
    x0, x1 = box2[0] + 120, box2[2] - 60
    xlo2, xhi2 = 0.0, max(50.0, (stats.get("max") or 40) * 1.25)

    def mx2(v):
        return x0 + (v - xlo2) / (xhi2 - xlo2) * (x1 - x0)

    for v in [0, 10, 20, 30, 40, 50]:
        X = mx2(v)
        c.d.line([X, box2[1] + 70, X, box2[3] - 150], fill="#eee", width=1)
        c.txt(X, box2[3] - 144, "%g" % v, size=12, anchor="ma")
    c.txt((x0 + x1) / 2, box2[3] - 122, "路径长度 path / D", size=14, anchor="ma")
    for i, (lab, v) in enumerate(vals):
        Y = box2[1] + 90 + i * 52
        c.txt(box2[0] + 16, Y, lab, size=14, anchor="lm", fill="#333")
        if v is not None:
            c.d.rectangle([x0, Y - 11, mx2(v), Y + 11], fill="#f39c12",
                          outline="#b7791f", width=1)
            c.txt(mx2(v) + 8, Y, "%.1f D" % v, size=13, anchor="lm", bold=True)
    c.txt(box2[0] + 16, box2[3] - 96,
          "中位寿命 %.1f D = %.1f 个时间步（v0/D=%.2f D/分钟）"
          % (stats.get("median") or 0, mi.get("median_in_steps") or 0,
             mi.get("path_per_minute_D") or 0),
          size=13, fill="#c0392b")
    c.txt(box2[0] + 16, box2[3] - 70,
          "survivors=%s：初始单质全部被反应消耗" % stats.get("survivors"),
          size=13, fill="#555")
    c.txt(box2[0] + 16, box2[3] - 44,
          "→ 寿命指标不能由主实验验证，必须用无化学对照组",
          size=13, bold=True, fill="#1e8449")

    # ---- 底部结论
    kin = a.get("kinetics") or {}
    data_note(c, [
        "对照组（无化学、仅弹性碰撞+衰减）：min %.1f、median %.1f、fraction≥500 = %.0f%% → 运动速度设计达标。"
        % (st.get("min") or 0, st.get("median") or 0,
           100.0 * (st.get("fraction_ge_500") or 0)),
        "主实验等效穿越：t=500 时累计 path_D=%s /9000 = %.1f 次/初始单质 > 500；"
        "但单个初始单质因“碰撞即反应”中位寿命只有 %.1f D（≈1 步）。"
        % (fmt_commas(kin.get("path_D_at_500")),
           kin.get("crossings_equiv_per_initial_at_500") or 0,
           stats.get("median") or 0),
        "结论：500 次穿越要求由对照组独立验证通过；主实验的短寿命是设计使然（反应占主导），不是速度不足。",
        "左图直方图由 min/p1/p5/median/p95/max 分位数线性插值重构（对照组仅输出统计量，无逐粒原始数据）。",
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
              "上：每分钟判定类型计数之和（对数轴）；下：净变化事件数。"
              "所有净变化事件集中在 T>100°C 的退火期；低温段只剩判定/弹性。")
    n = len(wins)
    labels = [w.get("label") for w in wins]

    # ---------- 上：判定类型分组柱 ----------
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
    group_w = (box[2] - box[0]) / n
    logmin, logmax = math.log10(1), math.log10(ymax)

    def mx_center(i):
        return box[0] + group_w * (i + 0.5)

    def myval(v):
        v = max(1.0, float(v))
        t = (math.log10(v) - logmin) / (logmax - logmin)
        return box[3] - t * (box[3] - box[1])

    for v in yticks:
        Y = myval(v)
        c.d.line([box[0], Y, box[2], Y], fill="#e9e9e9", width=1)
        c.d.line([box[0] - 6, Y, box[0], Y], fill="#333", width=1)
        c.txt(box[0] - 10, Y, "%g" % v, size=13, anchor="rm")
    c.d.rectangle(box, outline="#333", width=2)
    c.rot(box[0] - 58, (box[1] + box[3]) / 2, "判定次数（对数）", size=14)
    bw = group_w * 0.2
    for i, w in enumerate(wins):
        xc = mx_center(i)
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
    # 图例放在图框上方（不压柱子）
    c.legend(box[0] + 4, box[1] - 46,
             [(TYPECOL["complete"], "complete（完全反应判定）"),
              (TYPECOL["incomplete"], "incomplete（不完全反应判定）"),
              (TYPECOL["none"], "none（不反应/弹性）")],
             size=13, row_h=24, cols=3, col_w=340)

    # ---------- 下：净变化事件（同样的温度窗口类别） ----------
    box2 = (120, 735, 1420, 900)
    evmax = max([w.get("net_events") or 0 for w in wins] + [1]) * 3.0
    eyt = [1, 10, 100, 1000, 10000]
    v = 100000
    while v <= evmax:
        eyt.append(v)
        v *= 10
    logmax2 = math.log10(evmax)

    def my2(v):
        v = max(1.0, float(v))
        return box2[3] - (math.log10(v) / logmax2) * (box2[3] - box2[1])

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
        c.txt(xc, Y - 4, fmt_commas(val), size=12, anchor="mb", fill="#333")
    c.txt((box2[0] + box2[2]) / 2, box2[3] + 42, "温度区间（°C）", size=15, anchor="ma")
    c.txt_bg(box2[0] + 250, box2[1] + 8,
             "净变化事件 100% 发生在 T>100°C（退火期）：系统已在 t=866（T=134）前锁定 OXC 基态",
             size=13, fill="#8e44ad")
    data_note(c, [
        "温度阈值证据：complete 判定从 T=5 起为 0（OXC 对 Σc=6，T<6 不能完全反应）；"
        "incomplete 判定在 T≤5 出现（Σi≤5）；T≤2 时仅剩 none（弹性）。",
        "decomp 全程 0：主实验高温段没有不稳定中间体存活到 T 降到其 c(U) 以下，"
        "降温时系统已是稳定 OXC 基态。",
    ], y=985)
    return c.save(out)


# ================================================================ ⑧ 敏感性
def chart_sensitivity(a, out):
    sens = a.get("sensitivity") or {}
    if not sens.get("available"):
        raise RuntimeError("没有敏感性数据")
    runs = [r for r in (sens.get("runs") or []) if r.get("T0") is not None]
    if not runs:
        raise RuntimeError("敏感性 runs 为空")
    main_ref = sens.get("main_reference") or {}
    W, H = 1600, 1080
    c = Chart(W, H,
              "⑧ 温度标度敏感性：把初温放到 T35 阈值量级（6/8/12/20°C）才出现新物质与自分解",
              "每次实验 T0→0°C，分钟数=T0；主实验 1000°C（1000 分钟）作参考（红色虚线 + 右上角标注）。"
              "reaction_counts 为判定计数（含净结果不变），自分解/新物质为净事件。")
    metrics = [
        ("终态不同分子式数", lambda r: r.get("n_distinct_final"),
         main_ref.get("n_distinct_final"), lambda v: "%d 种" % v,
         _sens_comment(0, runs)),
        ("新物质数（29 聚素外）", lambda r: r.get("n_new_final"),
         main_ref.get("n_new_final"), lambda v: "%d 种" % v,
         _sens_comment(1, runs)),
        ("不完全反应判定数", lambda r: (r.get("reaction_counts") or {}).get("incomplete"),
         (main_ref.get("reaction_counts") or {}).get("incomplete"), fmt_commas,
         _sens_comment(2, runs)),
        ("自分解事件数", lambda r: r.get("decomp_events"),
         main_ref.get("decomp_events"), fmt_commas, _sens_comment(3, runs)),
    ]
    panel_w, panel_h = 720, 400
    x0s = [60, 840]
    y0s = [110, 540]
    n = len(runs)
    labels = ["T0=%s" % r.get("T0") for r in runs]
    cols = ["#2e86de", "#10ac84", "#f39c12", "#8e44ad"]
    for idx, (name, getter, ref, fmt, comment) in enumerate(metrics):
        px = x0s[idx % 2]
        py = y0s[idx // 2]
        box = (px + 80, py + 48, px + panel_w - 30, py + 300)
        vals = [getter(r) or 0 for r in runs]
        vmax = max(vals + [ref or 0, 1]) * 1.25
        c.txt(px + 16, py + 6, "%s %s" % ("①②③④"[idx], name), size=19, bold=True)
        if ref is not None:
            c.txt(px + panel_w - 10, py + 10, "主实验 1000°C = %s" % fmt(ref),
                  size=13, anchor="ra", fill="#c0392b")
        yt = nice_ticks(0, vmax, 4)
        mx, my = c.frame(box, (0, n), (0, vmax),
                         [i + 0.5 for i in range(n)], yt, ytick_fmt=fmt,
                         xtick_labels=labels)
        bw = (box[2] - box[0]) / n * 0.5
        for i, r in enumerate(runs):
            X = box[0] + (box[2] - box[0]) / n * (i + 0.5)
            Y = my(vals[i])
            c.d.rectangle([X - bw / 2, Y, X + bw / 2, box[3]],
                          fill=cols[i % len(cols)], outline="#333", width=1)
            c.txt(X, Y - 6, fmt(vals[i]), size=14, anchor="mb", bold=True)
        c.txt((box[0] + box[2]) / 2, box[3] + 36, "初温 T0（°C）", size=14, anchor="ma")
        if ref is not None:
            Yr = my(min(ref, vmax))
            c.dashed((box[0], Yr), (box[2], Yr), fill="#c0392b", width=2, dash=8)
        c.txt(px + 16, py + panel_h - 14, "→ " + comment, size=13, fill="#555")
    data_note(c, [
        sens.get("conclusion", ""),
        "注意：敏感性每次只运行 T0 分钟（T0→0），主实验运行 1000 分钟，横比时注意时长不同。",
    ], y=960)
    return c.save(out)


def _sens_comment(idx, runs):
    by = {r.get("T0"): r for r in runs}
    if idx == 0:
        return "T0=12 终态最丰富（34 种）；T0=20 完全反应更强，物种回落"
    if idx == 1:
        return "T0=8/12/20 各产 4/5/2 种新物质；T0=6（近阈值）未产新物质"
    if idx == 2:
        return "阈值量级温度下不完全反应大量发生（主实验仅 4407 且无净变化）"
    return "自分解：T0=8/12/20 为 82/133/49；主实验与 T0=6 为 0"


# ================================================================ main
CHARTS = [
    ("composition", "t55_composition.png", chart_composition),
    ("reaction_rate", "t55_reaction_rate.png", chart_reaction_rate),
    ("state_timeseries", "t55_state_timeseries.png", chart_state_timeseries),
    ("snapshots", "t55_snapshots.png", chart_snapshots),
    ("final_composition", "t55_final_composition.png", chart_final_composition),
    ("crossings", "t55_crossings.png", chart_crossings),
    ("temperature_windows", "t55_temperature_windows.png", chart_temperature_windows),
    ("sensitivity", "t55_sensitivity.png", chart_sensitivity),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="T55 图表渲染")
    ap.add_argument("--analysis", default=DEFAULT_ANALYSIS)
    ap.add_argument("--images", default=DEFAULT_IMAGES)
    ap.add_argument("--only", default=None,
                    help="只渲染指定图（逗号分隔名字，如 composition,crossings）")
    args = ap.parse_args(argv)
    if not os.path.exists(args.analysis):
        print("[error] 分析文件不存在：%s" % args.analysis)
        return 2
    a = json.load(open(args.analysis, encoding="utf-8"))
    # 快照原数据不在分析 JSON 里（体积原因），按 meta.main_path 读取主实验
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
