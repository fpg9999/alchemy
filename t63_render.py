# -*- coding: utf-8 -*-
"""t63_render.py —— T63「聚素退火 + F2→A2→K2 三次单质投放（价数滴定）」四阶段实验图表

读取 t63_analysis.json，生成 12 张图（前缀 t63_，输出到 images/）：
  images/t63_loads.png              ① 投料设计：29 种纯聚素 + 三次 8000 单质投放
  images/t63_stage_profiles.png     ② 四阶段 timeline（N / 平均·最大原子数，拼接时间轴）
  images/t63_element_balance.png    ③ 九元素守恒（逐阶段绝对原子数 + 占比）
  images/t63_valence.png            ④ 价数结构演化（v3:v2:v1 占比 + 原子数/增量）
  images/t63_top_species.png        ⑤ 每阶段终态 top10 物种
  images/t63_persistence.png        ⑥ 跨阶段物种存续矩阵（top20 并集）+ new/retained/lost
  images/t63_size_distribution.png  ⑦ 分子尺寸分布（逐阶段，对数）
  images/t63_snapshots.png          ⑧ 2D 快照（4 阶段 × t=0/500/995，element_bitmask）
  images/t63_reaction_stats.png     ⑨ 反应判定 + capped + 净事件/耗时
  images/t63_diversity.png          ⑩ 多样性/新物质/最大尺寸随阶段变化
  images/t63_top_structures.png     ⑪ 每阶段 top 物种分子结构图
  images/t63_stage_compare.png      ⑫ 四阶段总览 + 守恒核对

缺阶段（结果未就绪）时：对应面板画 未就绪 占位，其余图照常输出；
快照图需要原始 result JSON（meta.files.phases），缺失则该阶段行画占位。

用法：
  python t63_render.py
  python t63_render.py --analysis t63_analysis.json --images images
  python t63_render.py --only loads,valence     # 自测部分图
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_ANALYSIS = os.path.join(BASE, "t63_analysis.json")
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
# 阶段配色：s1 灰（纯聚素）/ s2 红（F）/ s3 橙（A）/ s4 紫（K）
STAGE_COL = {1: "#7f8c8d", 2: "#e74c3c", 3: "#f39c12", 4: "#8e44ad"}
STAGE_NAME = {1: "阶段1 纯聚素", 2: "阶段2 +F2", 3: "阶段3 +A2",
              4: "阶段4 +K2"}
STAGE_ADD = {1: None, 2: ("F", "F2", 8000, 16000), 3: ("A", "A2", 8000, 16000),
             4: ("K", "K2", 8000, 16000)}
FAM_COL = {"poly": "#2e86de", "F": "#e74c3c", "A": "#f39c12", "K": "#8e44ad"}
FAM_CN = {"poly": "聚素", "F": "含焰", "A": "含气", "K": "含沌"}
VALCOL = {"v3": "#c0392b", "v2": "#2e86de", "v1": "#27ae60"}
VALCN = {"v3": "3 价（O/P/K）", "v2": "2 价（X/W/A）", "v1": "1 价（C/L/F）"}
SNAP_PAL = ["#2ecc71", "#f39c12", "#3498db", "#9b59b6", "#1abc9c", "#e74c3c",
            "#00acc1", "#e84393", "#7f8c8d", "#2c3e50"]


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


def vals3(sh):
    """把价数占比统一为 (v3,v2,v1) 三位百分比字符串。"""
    if not sh:
        return "-"
    seq = [sh.get("v3"), sh.get("v2"), sh.get("v1")]
    return " : ".join(pct(x) for x in seq)


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


def layout_mol(atoms, edges, iters=260):
    """返回归一化坐标 [-1,1]^2；弹簧布局（含同斥力）。"""
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


def draw_mol_panel(c, rec, box, header_size=13, node_letter=True, rank=None):
    x0, y0, x1, y1 = box
    st = rec.get("structure") or {}
    atoms = st.get("atoms") or []
    edges = st.get("edges") or []
    n = len(atoms)
    formula = rec.get("formula") or ""
    c.txt((x0 + x1) / 2, y0 + 4, formula, size=header_size, bold=True,
          anchor="ma", fill="#111")
    pad = 8
    bx0, by0, bx1, by1 = x0 + pad, y0 + 26, x1 - pad, y1 - 44
    bw, bh = bx1 - bx0, by1 - by0
    c.d.rectangle([bx0, by0, bx1, by1], fill="#fbfbfb", outline="#e0e0e0")
    if n and edges is not None:
        pos = layout_mol(atoms, edges)
        rad = max(2.6, min(9.0, 0.5 * min(bw, bh) / (math.sqrt(max(1, n)) * 1.9)))
        if n > 24:
            rad = max(2.2, min(4.5, rad))
        pts = [(bx0 + bw / 2 + px * (bw / 2 - rad - 3),
                by0 + bh / 2 + py * (bh / 2 - rad - 3)) for px, py in pos]
        for e in edges:
            i, j, m = int(e[0]), int(e[1]), int(e[2])
            col = BONDCOL.get(m, "#888")
            wdt = 1 if m == 1 else 2
            c.d.line([pts[i], pts[j]], fill=col, width=wdt)
        for i, e in enumerate(atoms):
            X, Y = pts[i]
            c.d.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                        fill=ELEMCOL.get(e, "#ccc"), outline="#333", width=1)
            if node_letter and rad >= 5.5:
                c.txt(X, Y - 1, e, size=max(7, int(rad * 1.5)), bold=True,
                      anchor="mm", fill="#111")
    else:
        c.txt((bx0 + bx1) / 2, (by0 + by1) / 2, "（无结构数据）", size=12,
              anchor="mm", fill="#888")
    line1 = "×%s · %d 原子" % (fmt_commas(rec.get("count")),
                              rec.get("atoms") or n)
    c.txt((x0 + x1) / 2, y1 - 34, line1, size=11, anchor="ma", fill="#333")
    extra = []
    if rank is not None:
        extra.append("#%d" % rank)
    if rec.get("f_stable"):
        extra.append("F稳定")
    if rec.get("family"):
        extra.append(FAM_CN.get(rec["family"], rec["family"]))
    if extra:
        c.txt((x0 + x1) / 2, y1 - 18, " · ".join(extra), size=10, anchor="ma",
              fill="#666")


# ---------------------------------------------------------------- 阶段/原始数据
def stage(a, k):
    return (a.get("stages") or {}).get("phase%d" % k) or {}


def stage_ok(a, k):
    return stage(a, k).get("status") == "ok"


def present(a):
    return [k for k in (1, 2, 3, 4) if stage_ok(a, k)]


def pending_boxes(c, ks, note="未就绪：该阶段结果尚未就绪"):
    """在缺失阶段位置画占位框。"""
    for k in ks:
        pass


def pending_panel(c, box, msg="未就绪", sub="结果未就绪"):
    x0, y0, x1, y1 = box
    c.d.rectangle(box, outline="#c0392b", width=2, fill="#fff8f8")
    c.txt((x0 + x1) / 2, (y0 + y1) / 2 - 14, msg, size=20, bold=True,
          anchor="mm", fill="#c0392b")
    c.txt((x0 + x1) / 2, (y0 + y1) / 2 + 18, sub, size=13, anchor="mm",
          fill="#a05252")


_RAW = {}


def load_raw(a, k):
    if k in _RAW:
        return _RAW[k]
    path = ((a.get("meta") or {}).get("files") or {}).get("phases", {}).get(
        "phase%d" % k)
    data = None
    if path:
        cands = [path, os.path.join(BASE, path),
                 os.path.join(os.path.dirname(os.path.abspath(
                     sys.argv[0])), path)]
        for p in cands:
            if p and os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as fh:
                        data = json.load(fh)
                    break
                except Exception:
                    data = None
    _RAW[k] = data
    return data


def pick_snaps(snaps, targets):
    out = []
    for tg in targets:
        if not snaps:
            out.append(None)
            continue
        best = min(snaps, key=lambda s: abs(int(s.get("t", 0)) - tg))
        out.append(best)
    return out


# ---------------------------------------------------------------- ① 投料设计
def chart_loads(a, out):
    loads = a.get("loads") or {}
    s1 = loads.get("stage1") or {}
    sp = s1.get("species") or []
    meta = s1.get("meta") or {}
    adds = loads.get("additions") or []
    W, H = 1600, 1120
    c = Chart(
        W, H,
        "① T63 投料设计：29 种纯聚素退火 → 三次 8000 单质投放（F2/A2/K2 价数滴定）",
        "阶段1：%d 种聚素 / %s 分子 / %s 原子（平均 %.2f，T57 同款）；"
        "阶段2/3/4 各 +8000 双原子单质 = +16,000 原子；L=30000、cap=40、每阶段 1000 分钟"
        % (meta.get("n_species") or len(sp), fmt_commas(meta.get("total_molecules")),
           fmt_commas(meta.get("total_atoms")), meta.get("mean_atoms") or 0))
    # 左：29 种聚素（按原子数、分子式排序，横向条形）
    box = (90, 190, 700, 860)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 10, "阶段1 投料：29 种纯聚素（分子数）",
           size=16, bold=True)
    species = sorted(sp, key=lambda r: (r.get("atoms") or 0, r.get("formula") or ""))
    if species:
        mx = max((r.get("molecules") or r.get("count") or 0) for r in species) or 1
        row_h = min(21.0, (box[3] - box[1] - 48) / float(len(species)))
        x0, x1 = box[0] + 178, box[2] - 16
        y = box[1] + 42
        for r in species:
            f = r.get("formula") or "?"
            n = r.get("molecules") or r.get("count") or 0
            at = r.get("atoms") or 0
            col = ELEMCOL.get("O") if at == 2 else PAL[at % len(PAL)]
            w = (x1 - x0) * n / float(mx)
            c.d.rectangle([x0, y + 2, x0 + max(2, w), y + row_h - 5], fill=col,
                          outline="#666")
            c.txt(x0 - 8, y + (row_h - 5) / 2, "%s (%d原子)" % (f, at), size=11,
                  anchor="rm", fill="#333")
            c.txt(x0 + max(2, w) + 6, y + (row_h - 5) / 2, fmt_commas(n), size=11,
                  anchor="lm", fill="#333")
            y += row_h
    # 右上：三次投放卡片
    box2 = (740, 190, 1560, 560)
    c.border(box2)
    c.txt(box2[0] + 14, box2[1] + 10, "三次单质投放（每次 8000 分子 = 16,000 原子）",
           size=16, bold=True)
    cards = [(1, "阶段1", "29 种纯聚素", "—", STAGE_COL[1], 9002, 38532)]
    for ad in adds:
        k = ad.get("stage") or 0
        cards.append((k, "阶段%d" % k,
                      "%s + %s" % ("底物", ad.get("formula")),
                      "%s（%s）" % (ad.get("formula"), ad.get("name")),
                      STAGE_COL.get(k, "#333"), ad.get("molecules") or 8000,
                      ad.get("atoms") or 16000))
    cw = (box2[2] - box2[0] - 40) / 4.0
    for i, (k, name, title, addline, col, mol, at) in enumerate(cards[:4]):
        x = box2[0] + 16 + i * cw
        cy0, cy1 = box2[1] + 48, box2[1] + 320
        c.d.rectangle([x + 4, cy0, x + cw - 12, cy1], fill="#fafafa",
                      outline=col, width=3)
        c.txt(x + 14, cy0 + 10, name, size=15, bold=True, fill=col)
        c.txt(x + cw / 2 - 4, cy0 + 48, title, size=15, bold=True, anchor="ma")
        if k > 1:
            c.txt(x + cw / 2 - 4, cy0 + 82, "投放 %s" % addline, size=13,
                  anchor="ma", fill=RED)
        c.txt(x + cw / 2 - 4, cy0 + 128, "投放分子", size=12, anchor="ma",
              fill="#666")
        c.txt(x + cw / 2 - 4, cy0 + 148, fmt_commas(mol) if k > 1 else "—",
              size=17, bold=True, anchor="ma")
        c.txt(x + cw / 2 - 4, cy0 + 186, "投放原子", size=12, anchor="ma",
              fill="#666")
        c.txt(x + cw / 2 - 4, cy0 + 206, fmt_commas(at) if k > 1 else "—",
              size=17, bold=True, anchor="ma")
        if i < 3:
            c.d.line([x + cw - 8, (cy0 + cy1) / 2, x + cw + 2, (cy0 + cy1) / 2],
                     fill="#333", width=2)
    c.txt(box2[0] + 14, box2[3] - 40,
          "价数滴定逻辑：F2（一价端帽）→ A2（二价桥）→ K2（三价骨架）；F=1 价、A=2 价、K=3 价",
          size=13, fill="#555")
    # 右下：累计投料（设计口径）
    box3 = (740, 590, 1560, 860)
    c.border(box3)
    c.txt(box3[0] + 14, box3[1] + 8, "累计投料（按设计叠加：初始 9002 分子 / 38,532 原子）",
           size=15, bold=True)
    cum = [(1, 9002, 38532)] + [(ad["stage"], 9002 + 8000 * (ad["stage"] - 1),
                                 38532 + 16000 * (ad["stage"] - 1))
                                for ad in adds]
    bx = (box3[0] + 90, box3[1] + 46, box3[2] - 24, box3[3] - 56)
    maxat = max(r[2] for r in cum) * 1.12
    mx, my = c.frame(bx, (0, 4), (0, maxat),
                     [i + 0.5 for i in range(4)],
                     nice_ticks(0, maxat, 5),
                     xtick_fmt=lambda v: "",
                     ytick_fmt=lambda v: fmt_num(v))
    gw = (bx[2] - bx[0]) / 4.0
    for i, (k, mol, at) in enumerate(cum):
        x = bx[0] + gw * (i + 0.25)
        bw = gw * 0.5
        h = (bx[3] - bx[1]) * at / float(maxat)
        c.d.rectangle([x, bx[3] - h, x + bw, bx[3]], fill=STAGE_COL[k],
                      outline="#333")
        c.txt(x + bw / 2, bx[3] - h - 8, fmt_commas(at), size=11,
              anchor="mb", bold=True)
        c.txt(x + bw / 2, bx[3] + 8, "s%d" % k, size=12, anchor="ma", fill="#333")
    c.txt(bx[0], bx[3] + 30, "累计原子数（设计口径，实际阶段初始=上一阶段终态+投放）",
          size=12, fill="#666")
    data_note(c, [
        "阶段1 投料为 29 种纯聚素（O/X/C 三种元素，9002 分子 / 38,532 原子，与 T57 相同）；"
        "阶段2/3/4 各加入 8000 个双原子单质（F2/A2/K2），每次 +16,000 原子。",
        "元素投放：F 8,000×2=16,000 → A 16,000 → K 16,000；初始 29 种聚素不含 P/W/L/K/A/F，"
        "九元素在四阶段末全部覆盖。",
        "面积模型 A∝原子数（同 T57）；L=30000、max_reaction_atoms=40、每阶段 1000 分钟 1000→0°C；"
        "种子按阶段递增。",
    ])
    return c.save(out)


# ---------------------------------------------------------------- ② 四阶段 profile
def chart_stage_profiles(a, out):
    W, H = 1600, 1120
    c = Chart(W, H,
              "② T63 四阶段 timeline：分子数 N 与平均/最大原子数（拼接时间轴，每阶段 1000 分钟）",
              "x=阶段偏移后的时间（阶段 k 占 (k-1)×1000 → k×1000）；竖线=阶段边界 + 单质投放；"
              "虚线=最大原子数，实线=平均原子数")
    ks = present(a)
    minutes = int(((a.get("loads") or {}).get("minutes")) or 1000)
    box1 = (90, 190, 1490, 560)
    c.border(box1)
    c.txt(box1[0] + 12, box1[1] + 8, "分子数 N（每阶段 1000 分钟，1000→0°C）", size=16,
          bold=True)
    # 拼接 timeline
    segs = {}
    for k in ks:
        st = stage(a, k)
        rows = st.get("timeline") or []
        segs[k] = [((k - 1) * 1000 + int(r.get("t") or 0), r) for r in rows]
    ns = [(x, r.get("N") or 0) for k in ks for x, r in segs[k]]
    if not ns:
        pending_panel(c, box1, "无阶段数据")
    else:
        nmax = max(v for _, v in ns)
        bx = (box1[0] + 80, box1[1] + 46, box1[2] - 20, box1[3] - 46)
        mx, my = c.frame(bx, (0, len(ks) * 1000), (0, nmax * 1.12),
                         [i * 250 for i in range(len(ks) * 4 + 1)],
                         nice_ticks(0, nmax * 1.12, 6),
                         ytick_fmt=lambda v: fmt_num(v))
        for k in ks:
            pts = [(mx(x), my(r.get("N") or 0)) for x, r in segs[k]]
            c.line(pts, fill=STAGE_COL[k], width=3)
        for k in ks[1:]:
            X = mx((k - 1) * 1000)
            c.dashed((X, bx[1]), (X, bx[3]), fill="#c0392b", width=2, dash=7,
                     gap=5)
            ad = STAGE_ADD.get(k)
            label = ("+%s %s" % (fmt_commas(ad[2]), ad[1])) if ad else ""
            c.txt_bg(X + 6, bx[1] + 6, label, size=12, fill="#c0392b")
        c.legend(bx[0] + 10, bx[1] + 8,
                 [(STAGE_COL[k], STAGE_NAME[k]) for k in ks], size=13,
                 row_h=24, cols=2, col_w=210)
        c.txt(bx[0], bx[3] + 26, "时间 t（分钟，四阶段拼接）", size=13, anchor="la")
        c.rot(bx[0] - 52, (bx[1] + bx[3]) / 2, "分子数 N", size=14)
    # 下：平均/最大原子数
    box2 = (90, 640, 1490, 960)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "平均原子数（实线）与最大原子数（虚线）", size=16,
          bold=True)
    amax = 0
    for k in ks:
        for _, r in segs.get(k, []):
            amax = max(amax, r.get("max_atoms") or 0, r.get("mean_atoms") or 0)
    if ks and amax > 0:
        bx = (box2[0] + 80, box2[1] + 46, box2[2] - 20, box2[3] - 46)
        mx, my = c.frame(bx, (0, len(ks) * 1000), (0, amax * 1.15),
                         [i * 250 for i in range(len(ks) * 4 + 1)],
                         nice_ticks(0, amax * 1.15, 5))
        for k in ks:
            meanpts = [(mx(x), my(r.get("mean_atoms") or 0)) for x, r in segs[k]]
            maxpts = [(mx(x), my(r.get("max_atoms") or 0)) for x, r in segs[k]]
            c.line(meanpts, fill=STAGE_COL[k], width=3)
            c.dashed(maxpts[0], maxpts[0], fill=STAGE_COL[k], width=2)
            for i in range(1, len(maxpts)):
                c.dashed(maxpts[i - 1], maxpts[i], fill=STAGE_COL[k], width=2,
                         dash=7, gap=5)
        for k in ks[1:]:
            X = mx((k - 1) * 1000)
            c.dashed((X, bx[1]), (X, bx[3]), fill="#c0392b", width=2, dash=7,
                     gap=5)
        c.txt(bx[0], bx[3] + 26, "时间 t（分钟，四阶段拼接）", size=13, anchor="la")
        c.rot(bx[0] - 52, (bx[1] + bx[3]) / 2, "原子数", size=14)
        c.legend(bx[2] - 660, bx[1] + 8,
                 [(STAGE_COL[k], STAGE_NAME[k]) for k in ks], size=12,
                 row_h=22, cols=4, col_w=165)
    else:
        pending_panel(c, box2, "无阶段数据")
    lines = ["每阶段 1000 分钟、温度 1000→0°C；阶段边界竖线处为“整理归档 + 温度重置 + 下一单质投放”。"]
    for k in ks:
        st = stage(a, k)
        lines.append(
            "阶段%d：初始 %s 分子 / %s 原子 → 终态 %s / %s；平均 %.2f、最大 %d 原子；净事件 %s；耗时 %.1fs"
            % (k, fmt_commas(st.get("config", {}).get("initial_particles")),
               fmt_commas(st.get("config", {}).get("initial_atoms")),
               fmt_commas(st.get("final_N")), fmt_commas(st.get("final_atoms")),
               st.get("final_mean_atoms") or 0, st.get("final_max_atoms") or 0,
               fmt_commas(st.get("net_events")), st.get("runtime_s") or 0))
    missing = [k for k in (1, 2, 3, 4) if k not in ks]
    if missing:
        lines.append("未就绪：阶段 %s 结果未就绪，图中暂缺。"
                     % "、".join("phase%d" % k for k in missing))
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- ③ 元素守恒
def chart_element_balance(a, out):
    cross = a.get("cross_stage") or {}
    mat = cross.get("element_stage_matrix") or []
    cons = cross.get("conservation") or []
    ks = present(a)
    W, H = 1600, 1120
    c = Chart(W, H,
              "③ T63 九元素守恒：A 阶段初始聚素元素不变，F/A/K 逐阶段 +16,000 原子",
              "逐阶段终态元素原子数（左）与元素占比（右）；阶段 k 期望 = 阶段 k-1 终态 + 本阶段投放")
    # 左：绝对原子数
    box = (90, 190, 850, 860)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "元素原子数（逐阶段终态）", size=16, bold=True)
    elems = [r for r in mat if r.get("element") in ORDER]
    elems.sort(key=lambda r: ORDER.index(r["element"]))
    tot_by_stage = {k: sum((r.get("stages", {}).get("stage%d" % k) or 0)
                           for r in elems) or 1 for k in ks}
    if elems and ks:
        ymax = max((r.get("stages", {}).get("stage%d" % k) or 0)
                   for r in elems for k in ks) or 1
        bx = (box[0] + 78, box[1] + 68, box[2] - 20, box[3] - 60)
        mx, my = c.frame(bx, (0, len(elems)), (0, ymax * 1.15),
                         [i + 0.5 for i in range(len(elems))],
                         nice_ticks(0, ymax * 1.15, 6),
                         xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: fmt_num(v))
        gw = (bx[2] - bx[0]) / len(elems)
        bw = gw * 0.8 / max(1, len(ks))
        for i, r in enumerate(elems):
            e = r["element"]
            for j, k in enumerate(ks):
                v = r.get("stages", {}).get("stage%d" % k) or 0
                x = bx[0] + gw * (i + 0.1) + j * bw
                h = (bx[3] - bx[1]) * v / float(ymax * 1.15)
                c.d.rectangle([x, bx[3] - h, x + bw * 0.86, bx[3]],
                              fill=STAGE_COL[k], outline="#555")
            c.txt(bx[0] + gw * (i + 0.5), bx[3] + 8, "%s %s" % (e, CN[e]), size=13,
                  anchor="ma")
        c.legend(bx[0], box[1] + 34, [(STAGE_COL[k], STAGE_NAME[k]) for k in ks],
                 size=11, row_h=20, cols=4, col_w=180)
        c.txt(bx[0], bx[3] + 30, "元素", size=12, fill="#666")
        c.rot(bx[0] - 50, (bx[1] + bx[3]) / 2, "原子数", size=14)
    else:
        pending_panel(c, box, "无阶段数据")
    # 右：元素占比
    box2 = (890, 190, 1560, 640)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "元素占比（%）", size=16, bold=True)
    if elems and ks:
        bx = (box2[0] + 70, box2[1] + 46, box2[2] - 20, box2[3] - 46)
        mx, my = c.frame(bx, (0, len(elems)), (0, 100),
                         [i + 0.5 for i in range(len(elems))],
                         [0, 20, 40, 60, 80, 100],
                         xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: "%d%%" % v)
        gw = (bx[2] - bx[0]) / len(elems)
        bw = gw * 0.8 / max(1, len(ks))
        for i, r in enumerate(elems):
            e = r["element"]
            for j, k in enumerate(ks):
                tot = tot_by_stage.get(k) or 1
                v = r.get("stages", {}).get("stage%d" % k) or 0
                share = 100.0 * v / tot
                x = bx[0] + gw * (i + 0.1) + j * bw
                h = (bx[3] - bx[1]) * share / 100.0
                c.d.rectangle([x, bx[3] - h, x + bw * 0.86, bx[3]],
                              fill=STAGE_COL[k], outline="#555")
            c.txt(bx[0] + gw * (i + 0.5), bx[3] + 8, "%s" % e, size=12,
                  anchor="ma")
        c.rot(bx[0] - 50, (bx[1] + bx[3]) / 2, "占比 (%)", size=14)
    else:
        pending_panel(c, box2, "无阶段数据")
    # 右下：守恒核对
    box3 = (890, 670, 1560, 860)
    c.border(box3)
    c.txt(box3[0] + 12, box3[1] + 8, "守恒核对（元素 / 分子 / 原子）", size=16,
          bold=True)
    y = box3[1] + 44
    for c0 in cons:
        if c0.get("status") != "ok":
            continue
        ok = (c0.get("elements_conserved") and c0.get("molecule_balance")
              and c0.get("atom_balance"))
        c.txt(box3[0] + 16, y,
              "阶段%d：期望 %s 分子 / %s 原子，终态 %s / %s；元素核对 %s，状态链 %s"
              % (c0.get("stage"), fmt_commas(c0.get("expected_molecules")),
                 fmt_commas(c0.get("expected_atoms")),
                 fmt_commas(c0.get("final_N")), fmt_commas(c0.get("final_atoms")),
                 "√" if c0.get("elements_conserved") else "×",
                 ("√" if c0.get("states_chain_ok") else "—")
                 if c0.get("states_chain_ok") is not None else "—"),
              size=12, fill=GREEN if ok else RED)
        y += 24
    bs = cross.get("balance_summary") or {}
    c.txt(box3[0] + 16, box3[3] - 28,
          "总判定：元素守恒 %s / 分子守恒 %s / 原子守恒 %s / 状态链 %s"
          % ("√" if bs.get("all_elements_conserved") else "×",
             "√" if bs.get("all_molecule_balance") else "×",
             "√" if bs.get("all_atom_balance") else "×",
             "√" if bs.get("all_states_chain_ok") else "×"), size=13,
          bold=True, fill=GREEN)
    lines = ["阶段 k 期望分子/原子 = 阶段 k-1 终态 + 本阶段投放（阶段1 期望 = 初始投料 9002 / 38,532）。"]
    for r in cons:
        if r.get("status") != "ok":
            continue
        deltas = [d for d in (r.get("element_delta_rows") or []) if d.get("delta")]
        lines.append(
            "阶段%d：投放 %s 分子 / %s 原子%s；元素最大偏差 %s"
            % (r.get("stage"), fmt_commas(r.get("addition_molecules")),
               fmt_commas(r.get("addition_atoms")),
               ("（%s）" % r.get("addition_element")) if r.get("addition_element") else "",
               ("0（全部元素 delta=0）" if not deltas else
                "、".join("%s %+d" % (d["element"], d["delta"]) for d in deltas))))
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- ④ 价数演化
def chart_valence(a, out):
    vp = (a.get("cross_stage") or {}).get("valence_progression") or []
    ks = present(a)
    rows = [r for r in vp if r.get("stage") in ks]
    W, H = 1600, 1060
    c = Chart(W, H,
              "④ T63 价数结构演化：v3:v2:v1 逐阶段被单质投放改变（F2→v1、A2→v2、K2→v3）",
              "价数口径：O/P/K=3 价、X/W/A=2 价、C/L/F=1 价；阶段2 起每次投放 +16,000 原子，"
              "占比随滴定逐级偏移")
    # 上：100% 堆叠
    box = (90, 190, 1000, 520)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "价数原子占比（100% 堆叠）", size=16, bold=True)
    if rows:
        bx = (box[0] + 74, box[1] + 50, box[2] - 24, box[3] - 80)
        gw = (bx[2] - bx[0]) / max(1, len(rows))
        for i, r in enumerate(rows):
            k = r["stage"]
            p = r.get("percent") or {}
            x = bx[0] + gw * (i + 0.18)
            bw = gw * 0.64
            y0 = bx[3]
            for key in ("v3", "v2", "v1"):
                h = (bx[3] - bx[1]) * (p.get(key) or 0) / 100.0
                y0 -= h
                c.d.rectangle([x, y0, x + bw, y0 + h], fill=VALCOL[key],
                              outline="#333")
                if h > 26:
                    c.txt(x + bw / 2, y0 + h / 2, "%s%%" % pct(p.get(key) / 100.0),
                          size=12, anchor="mm", bold=True, fill="white")
            c.txt(x + bw / 2, bx[3] + 8, "阶段%d" % k, size=13, anchor="ma")
        c.legend(bx[0], bx[3] + 30,
                 [(VALCOL[k], VALCN[k]) for k in ("v3", "v2", "v1")], size=12,
                 row_h=22, cols=3, col_w=210)
        c.rot(bx[0] - 50, (bx[1] + bx[3]) / 2, "占比 (%)", size=14)
    else:
        pending_panel(c, box, "无阶段数据")
    # 右上：绝对原子数 + 增量
    box2 = (1040, 190, 1560, 620)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "价数原子数与阶段增量", size=16, bold=True)
    if rows:
        ymax = max((r.get("atoms") or {}).get(key) or 0
                   for r in rows for key in ("v3", "v2", "v1")) or 1
        bx = (box2[0] + 66, box2[1] + 46, box2[2] - 16, box2[3] - 40)
        mx, my = c.frame(bx, (0, len(rows)), (0, ymax * 1.2),
                         [i + 0.5 for i in range(len(rows))],
                         nice_ticks(0, ymax * 1.2, 5),
                         xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: fmt_num(v))
        gw = (bx[2] - bx[0]) / len(rows)
        bw = gw * 0.66 / 3.0
        for i, r in enumerate(rows):
            for j, key in enumerate(("v3", "v2", "v1")):
                v = (r.get("atoms") or {}).get(key) or 0
                h = (bx[3] - bx[1]) * v / float(ymax * 1.2)
                x = bx[0] + gw * (i + 0.17) + j * bw
                c.d.rectangle([x, bx[3] - h, x + bw * 0.9, bx[3]],
                              fill=VALCOL[key], outline="#555")
            d = r.get("delta")
            c.txt(bx[0] + gw * (i + 0.5), bx[3] + 8, "阶段%d" % r["stage"], size=12,
                  anchor="ma")
            if d:
                add = [k2 for k2 in ("v3", "v2", "v1") if d.get(k2)]
                c.txt(bx[0] + gw * (i + 0.5), bx[3] + 26,
                      "+" + fmt_commas(sum(d.values())) + (" " + "+".join(add) if add else ""),
                      size=11, anchor="ma", fill=GREEN)
        c.rot(bx[0] - 46, (bx[1] + bx[3]) / 2, "原子数", size=13)
    else:
        pending_panel(c, box2, "无阶段数据")
    # 右下：文字摘要
    box3 = (1040, 650, 1560, 880)
    c.border(box3)
    c.txt(box3[0] + 12, box3[1] + 8, "各阶段价数结构", size=16, bold=True)
    y = box3[1] + 44
    for r in rows:
        p = r.get("percent") or {}
        c.txt(box3[0] + 14, y, "阶段%d：%s%% : %s%% : %s%%" % (
            r["stage"], pct((p.get("v3") or 0) / 100.0),
            pct((p.get("v2") or 0) / 100.0), pct((p.get("v1") or 0) / 100.0)),
            size=12)
        y += 22
    if rows:
        r = rows[-1]
        a3 = (r.get("atoms") or {}).get("v3") or 0
        a2 = (r.get("atoms") or {}).get("v2") or 0
        a1 = (r.get("atoms") or {}).get("v1") or 0
        c.txt(box3[0] + 14, y + 6, "末阶段原子数：v3=%s / v2=%s / v1=%s（合计 %s）"
              % (fmt_commas(a3), fmt_commas(a2), fmt_commas(a1),
                 fmt_commas(a3 + a2 + a1)), size=12, fill="#333")
    lines = [
        "阶段1 投料只含 O/X/C（v3:v2:v1 ≈ 31:37:31），后续每次单质投放把某价数原子数抬高 16,000：",
    ]
    for r in rows:
        d = r.get("delta")
        if d:
            lines.append("阶段%d：+%s 原子 → 占比 %s : %s : %s（v3:v2:v1）"
                         % (r["stage"], fmt_commas(sum(d.values())),
                            pct((r.get("percent", {}).get("v3") or 0) / 100.0),
                            pct((r.get("percent", {}).get("v2") or 0) / 100.0),
                            pct((r.get("percent", {}).get("v1") or 0) / 100.0)))
    lines.append("价数滴定预期：F2 拉高 v1、A2 拉高 v2、K2 拉高 v3，每次投放对应价数原子数 +16,000；"
                 "末阶段 v3:v2:v1 ≈ 32:35:32，三价数原子量重新趋于接近。")
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- ⑤ top 物种
def chart_top_species(a, out):
    ks = [1, 2, 3, 4]
    W, H = 1600, 1140
    c = Chart(W, H,
              "⑤ T63 各阶段终态 top10 物种：聚素 → F 端帽 → A 桥 → K 骨架",
              "每面板内按数量排序（对数轴）；颜色=家族（聚素/含焰/含气/含沌）；未就绪阶段显示为占位")
    pw, ph = 720, 380
    for idx, k in enumerate(ks):
        col, row = idx % 2, idx // 2
        x0 = 60 + col * (pw + 60)
        y0 = 150 + row * (ph + 60)
        box = (x0, y0, x0 + pw, y0 + ph)
        c.border(box)
        st = stage(a, k)
        c.txt(x0 + 10, y0 + 8, "%s（终态 %s 种）" % (
            STAGE_NAME[k], st.get("distinct_formulas") or "—"), size=15,
            bold=True, fill=STAGE_COL[k])
        if not stage_ok(a, k):
            pending_panel(c, (x0 + 10, y0 + 40, x0 + pw - 10, y0 + ph - 10),
                          "未就绪", "phase%d 结果未就绪" % k)
            continue
        top = st.get("top20") or []
        top = top[:10]
        if not top:
            c.txt(x0 + pw / 2, y0 + ph / 2, "（无数据）", size=14, anchor="mm",
                  fill="#888")
            continue
        bx = (x0 + 150, y0 + 40, x0 + pw - 120, y0 + ph - 16)
        vmax = max(r.get("count") or 0 for r in top) or 1
        vmin = 1.0
        row_h = (bx[3] - bx[1]) / float(len(top))
        for i, r in enumerate(top):
            v = r.get("count") or 0
            y = bx[1] + i * row_h
            t = (math.log(max(v, 1)) - math.log(vmin)) / max(1e-9, (math.log(vmax) - math.log(vmin)))
            w = (bx[2] - bx[0]) * max(0.02, t)
            fam = r.get("family") or "poly"
            c.d.rectangle([bx[0], y + 2, bx[0] + w, y + row_h - 3],
                          fill=FAM_COL.get(fam, "#888"), outline="#555")
            c.txt(bx[0] - 8, y + row_h / 2, r.get("formula") or "?", size=11,
                  anchor="rm")
            c.txt(bx[0] + w + 6, y + row_h / 2, fmt_commas(v), size=11,
                  anchor="lm")
    c.legend(70, 100, [(FAM_COL[f], FAM_CN[f]) for f in ("poly", "F", "A", "K")],
             size=12, row_h=22, cols=4, col_w=140)
    lines = ["每阶段终态 top10（按分子数）；阶段 1 只有聚素（poly），阶段 2 起出现含 F 端帽产物，"
             "阶段 3/4 依次出现含 A / 含 K 产物。"]
    for k in (1, 2, 3, 4):
        st = stage(a, k)
        if not stage_ok(a, k):
            lines.append("阶段%d：未就绪（phase%d 结果缺失）" % (k, k))
            continue
        top = (st.get("top20") or [])[:3]
        lines.append("阶段%d top3：%s" % (k, "、".join(
            "%s×%s" % (r.get("formula"), fmt_commas(r.get("count"))) for r in top)))
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- ⑥ 存续矩阵
def chart_persistence(a, out):
    cross = a.get("cross_stage") or {}
    tm = cross.get("top_matrix") or []
    trans = cross.get("transitions") or []
    ks = [1, 2, 3, 4]
    W, H = 1600, 1180
    c = Chart(W, H,
              "⑥ T63 跨阶段物种存续：top20 并集 × 四阶段数量矩阵 + 阶段间 new/retained/lost",
              "行为四阶段 top20 并集（按最大数量排序，最多 30 行）；格内数字=该阶段终态分子数；"
              "左侧色块=首次出现阶段")
    rows = sorted(tm, key=lambda r: -(r.get("max_count") or 0))[:30]
    box = (90, 190, 1080, 900)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "物种 × 阶段数量矩阵（log 色阶）", size=16, bold=True)
    if rows:
        lab_w = 250
        gx0, gx1 = box[0] + lab_w, box[2] - 16
        gy0, gy1 = box[1] + 66, box[3] - 48
        cw = (gx1 - gx0) / 4.0
        rw = (gy1 - gy0) / float(len(rows))
        vmax = max((r.get("max_count") or 0) for r in rows) or 1
        for j, k in enumerate(ks):
            c.txt(gx0 + cw * (j + 0.5), gy0 - 26, "阶段%d" % k, size=13,
                  anchor="ma", bold=True, fill=STAGE_COL[k])
        for i, r in enumerate(rows):
            y = gy0 + i * rw
            fs = r.get("first_stage") or 1
            c.d.rectangle([box[0] + 8, y + 3, box[0] + 24, y + 3 + max(8, rw - 6)],
                          fill=STAGE_COL.get(fs, "#888"), outline="#555")
            fam = r.get("family") or "poly"
            c.txt(box[0] + 30, y + rw / 2, r.get("formula") or "?", size=11,
                  anchor="lm")
            for j, k in enumerate(ks):
                v = (r.get("counts") or {}).get("stage%d" % k) or 0
                if v > 0:
                    t = math.log1p(v) / math.log1p(vmax)
                else:
                    t = 0.0
                rr = int(247 * (1 - t) + 41 * t)
                gg = int(249 * (1 - t) + 128 * t)
                bb = int(252 * (1 - t) + 200 * t)
                col = "#%02x%02x%02x" % (rr, gg, bb)
                x = gx0 + j * cw
                c.d.rectangle([x + 2, y + 2, x + cw - 2, y + rw - 2], fill=col,
                              outline="#ddd")
                if v > 0:
                    c.txt(x + cw / 2, y + rw / 2, fmt_num(v), size=10,
                          anchor="mm", fill="white" if t > 0.55 else "#111")
        c.txt(box[0] + 8, box[3] - 26,
              "色块=首次出现阶段（灰 s1 / 红 s2 / 橙 s3 / 紫 s4）", size=11, fill="#666")
        c.rot(gx0 - 8, (gy0 + gy1) / 2, "", size=11)
    else:
        pending_panel(c, box, "无阶段数据")
    # 右：transitions
    box2 = (1120, 190, 1560, 640)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "top20 阶段间变化（个）", size=16, bold=True)
    trs = [t for t in trans if t.get("prev")]
    if trs:
        bxx = (box2[0] + 64, box2[1] + 50, box2[2] - 20, box2[3] - 46)
        ymax = max(max(t.get("new_count") or 0, t.get("retained_count") or 0,
                       t.get("lost_count") or 0) for t in trs) or 1
        mx, my = c.frame(bxx, (0, len(trs)), (0, ymax * 1.2),
                         [i + 0.5 for i in range(len(trs))],
                         nice_ticks(0, ymax * 1.2, 5),
                         xtick_fmt=lambda v: "")
        gw = (bxx[2] - bxx[0]) / len(trs)
        bw = gw * 0.66 / 3.0
        cols = {"new": GREEN, "retained": BLUE, "lost": "#95a5a6"}
        for i, t in enumerate(trs):
            for j, key in enumerate(("new", "retained", "lost")):
                v = t.get("%s_count" % key) or 0
                h = (bxx[3] - bxx[1]) * v / float(ymax * 1.2)
                x = bxx[0] + gw * (i + 0.17) + j * bw
                c.d.rectangle([x, bxx[3] - h, x + bw * 0.9, bxx[3]],
                              fill=cols[key], outline="#555")
                if v:
                    c.txt(x + bw * 0.45, bxx[3] - h - 6, str(v), size=10,
                          anchor="mb")
            c.txt(bxx[0] + gw * (i + 0.5), bxx[3] + 8,
                  "s%d→s%d" % (t.get("prev"), t.get("stage")), size=12,
                  anchor="ma")
        c.legend(bxx[0], bxx[3] + 28,
                 [(cols["new"], "new"), (cols["retained"], "retained"),
                  (cols["lost"], "lost")], size=11, row_h=20, cols=3, col_w=110)
    else:
        pending_panel(c, box2, "无阶段数据")
    # 右下文字
    box3 = (1120, 670, 1560, 900)
    c.border(box3)
    c.txt(box3[0] + 12, box3[1] + 8, "关键存续结论", size=15, bold=True)
    y = box3[1] + 42
    for t in trans:
        c.txt(box3[0] + 14, y, "阶段%d→%d：new %d / retained %d / lost %d"
              % (t.get("prev") or 1, t.get("stage"), t.get("new_count") or 0,
                 t.get("retained_count") or 0, t.get("lost_count") or 0),
              size=12)
        y += 22
    if tm:
        firsts = {}
        for r in tm:
            firsts.setdefault(r.get("first_stage"), []).append(r.get("formula"))
        for k in (1, 2, 3, 4):
            if firsts.get(k):
                c.txt(box3[0] + 14, y, "首现于阶段%d：%s" % (k, "、".join(
                    firsts[k][:5]) + ("…" if len(firsts[k]) > 5 else "")), size=11,
                    fill="#555")
                y += 20
    lines = ["存续矩阵取四阶段 top20 并集；阶段间 retained 表示 top20 中同一分子式在相邻两阶段都出现。"]
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- ⑦ 尺寸分布
def chart_size_distribution(a, out):
    ks = present(a)
    W, H = 1600, 1020
    c = Chart(W, H,
              "⑦ T63 分子尺寸分布：四阶段终态（原子数 × 分子数，对数）",
              "柱=分子数（对数轴）；每阶段独立终态组成；尺寸=分子原子数")
    box = (90, 190, 1500, 860)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "终态尺寸分布（逐阶段）", size=16, bold=True)
    dist = {}
    for k in ks:
        d = {}
        for r in (stage(a, k).get("size_distribution") or []):
            d[int(r.get("atoms") or 0)] = r.get("molecules") or 0
        dist[k] = d
    sizes = sorted({s for d in dist.values() for s in d if s})
    if sizes and ks:
        bx = (box[0] + 80, box[1] + 78, box[2] - 20, box[3] - 50)
        vmax = max(max(d.values()) for d in dist.values() if d) or 1
        ymin = 1.0
        mx, my = c.frame(bx, (0, len(sizes) + 0.6), (ymin, vmax * 1.4),
                         [i + 0.5 for i in range(len(sizes))],
                         log_ticks(ymin, vmax * 1.4), logy=True,
                         xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: fmt_num(v, 0))
        gw = (bx[2] - bx[0]) / (len(sizes) + 0.6)
        bw = gw * 0.82 / max(1, len(ks))
        for i, s in enumerate(sizes):
            for j, k in enumerate(ks):
                v = dist[k].get(s) or 0
                if v <= 0:
                    continue
                h = (bx[3] - my(v))
                x = bx[0] + gw * (i + 0.09) + j * bw
                c.d.rectangle([x, my(v), x + bw * 0.88, bx[3]],
                              fill=STAGE_COL[k], outline="#555")
            c.txt(bx[0] + gw * (i + 0.5), bx[3] + 8, "%d" % s, size=12,
                  anchor="ma")
        c.txt(bx[0] + (bx[2] - bx[0]) / 2, bx[3] + 30, "分子原子数", size=13,
              anchor="ma")
        c.rot(bx[0] - 56, (bx[1] + bx[3]) / 2, "分子数（对数）", size=14)
        c.legend(bx[0], box[1] + 40, [(STAGE_COL[k], STAGE_NAME[k]) for k in ks],
                 size=12, row_h=22, cols=4, col_w=180)
    else:
        pending_panel(c, box, "无阶段数据")
    lines = []
    for k in ks:
        st = stage(a, k)
        dist_k = sorted(
            [(int(r.get("atoms") or 0), r.get("molecules") or 0)
             for r in (st.get("size_distribution") or [])],
            key=lambda x: -x[1])[:4]
        lines.append("阶段%d：终态 %s 分子 / %s 原子；前 4 尺寸：%s" % (
            k, fmt_commas(st.get("final_N")), fmt_commas(st.get("final_atoms")),
            "、".join("%d 原子→%s" % (s, fmt_commas(n)) for s, n in dist_k)))
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- ⑧ 快照
def chart_snapshots(a, out):
    ks = [1, 2, 3, 4]
    targets = [0, 500, 995]
    W, H = 1540, 1720
    c = Chart(W, H,
              "⑧ T63 2D 快照：四阶段 × 三个时刻的粒子分布（element_bitmask）",
              "颜色=元素组合（bitmask）；每面板 3000 点抽样；t=0 为阶段初始、t=995 为阶段终态；"
              "缺失原始 result JSON 的阶段显示为占位")
    L = float((a.get("loads") or {}).get("L") or 30000)
    panels = []
    codes_all = {}
    for k in ks:
        raw = load_raw(a, k) if stage_ok(a, k) else None
        snaps = (raw or {}).get("snapshots") or []
        picked = pick_snaps(snaps, targets) if snaps else [None, None, None]
        for tgt, sn in zip(targets, picked):
            panels.append((k, tgt, sn, raw))
            if sn:
                for pt in sn.get("points") or []:
                    codes_all[pt[2]] = codes_all.get(pt[2], 0) + 1
    top_codes = [code for code, _ in sorted(codes_all.items(),
                                            key=lambda kv: -kv[1])[:8]]
    code_col = {}
    for i, code in enumerate(top_codes):
        code_col[code] = SNAP_PAL[i % len(SNAP_PAL)]
    pw = (W - 60 - 2 * 24) / 3.0
    ph = 320
    legend_labels = {}
    for k in ks:
        raw = load_raw(a, k) if stage_ok(a, k) else None
        if raw:
            legend_labels.update((raw.get("snapshots") or [{}])[0].get("legend") or {})
    y = 150
    for row, k in enumerate(ks):
        for col, tgt in enumerate(targets):
            x = 30 + col * (pw + 24)
            box = (x, y, x + pw, y + ph)
            c.border(box)
            c.txt(x + 10, y + 6, "阶段%d · t=%d" % (k, tgt), size=14, bold=True,
                  fill=STAGE_COL[k])
            sn = panels[row * 3 + col][2]
            if not sn:
                c.txt(x + pw / 2, y + ph / 2, "未就绪",
                      size=16, bold=True, anchor="mm", fill="#c0392b")
                continue
            pts = sn.get("points") or []
            mx = x + 8
            my = y + 30
            mw, mh = pw - 16, ph - 56
            c.d.rectangle([mx, my, mx + mw, my + mh], fill="#fbfbfb",
                          outline="#e0e0e0")
            for pt in pts:
                px = mx + (float(pt[0]) / L) * mw
                py = my + mh - (float(pt[1]) / L) * mh
                colr = code_col.get(pt[2], "#bbbbbb")
                c.d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=colr)
            c.txt(x + 10, y + ph - 16, "点数 %d（抽样）" % len(pts), size=10,
                  fill="#666")
        y += ph + 20
    # 图例
    leg_y = 1520
    items = []
    for code in top_codes:
        lab = legend_labels.get(str(code)) or legend_labels.get(code) or ("组合%d" % code)
        items.append((code_col[code], lab))
    if items:
        c.legend(30, leg_y, items, size=12, row_h=22, cols=4, col_w=360)
        c.txt(30, leg_y + 52, "图例：元素组合（bitmask）；未列入的颜色为低频组合。",
              size=11, fill="#666")
    lines = []
    for k in ks:
        raw = load_raw(a, k) if stage_ok(a, k) else None
        st = stage(a, k)
        if not raw:
            lines.append("阶段%d：未就绪（原始 result JSON 缺失，快照面板占位）" % k)
            continue
        lines.append("阶段%d：L=%s，共 %d 个快照；粒子坐标按 L 归一化到面板。" % (
            k, fmt_commas(raw.get("config", {}).get("L")), len(raw.get("snapshots") or [])))
    data_note(c, lines, y=1620)
    return c.save(out)


# ---------------------------------------------------------------- ⑨ 反应统计
def chart_reaction_stats(a, out):
    ks = present(a)
    W, H = 1600, 1080
    c = Chart(W, H,
              "⑨ T63 反应判定 / capped / 净事件：四阶段对比（对数轴）",
              "complete/incomplete/none/capped 计数（对数）；右图=净事件与 capped 占比；每阶段 1000 分钟")
    box = (90, 190, 900, 640)
    c.border(box)
    c.txt(box[0] + 12, box[1] + 8, "反应判定计数（对数）", size=16, bold=True)
    types = ["complete", "incomplete", "none", "capped"]
    if ks:
        bx = (box[0] + 84, box[1] + 76, box[2] - 20, box[3] - 50)
        vmax = 1
        for k in ks:
            for t in types:
                vmax = max(vmax, (stage(a, k).get("reaction_counts") or {}).get(t) or 0)
        mx, my = c.frame(bx, (0, len(types)), (1, vmax * 3.0),
                         [i + 0.5 for i in range(len(types))],
                         log_ticks(1, vmax * 3.0), logy=True,
                         xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: fmt_num(v))
        gw = (bx[2] - bx[0]) / len(types)
        bw = gw * 0.82 / max(1, len(ks))
        for i, t in enumerate(types):
            for j, k in enumerate(ks):
                v = (stage(a, k).get("reaction_counts") or {}).get(t) or 0
                x = bx[0] + gw * (i + 0.09) + j * bw
                if v > 0:
                    c.d.rectangle([x, my(v), x + bw * 0.88, bx[3]],
                                  fill=TYPECOL[t], outline="#555")
                else:
                    c.txt(x + bw * 0.44, bx[3] - 12, "0", size=10, anchor="mb",
                          fill="#888")
            c.txt(bx[0] + gw * (i + 0.5), bx[3] + 8, t, size=13, anchor="ma")
        c.legend(bx[0], box[1] + 38,
                 [(TYPECOL[t], t) for t in types], size=12, row_h=22, cols=4,
                 col_w=150)
        c.rot(bx[0] - 54, (bx[1] + bx[3]) / 2, "计数（对数）", size=14)
    else:
        pending_panel(c, box, "无阶段数据")
    # 右：净事件 / capped 占比
    box2 = (940, 190, 1560, 640)
    c.border(box2)
    c.txt(box2[0] + 12, box2[1] + 8, "净事件与 capped 占比", size=16, bold=True)
    if ks:
        bxx = (box2[0] + 64, box2[1] + 50, box2[2] - 20, box2[3] - 46)
        ymax = max((stage(a, k).get("net_events") or 0) for k in ks) or 1
        mx, my = c.frame(bxx, (0, len(ks)), (0, ymax * 1.2),
                         [i + 0.5 for i in range(len(ks))],
                         nice_ticks(0, ymax * 1.2, 5),
                         xtick_fmt=lambda v: "")
        gw = (bxx[2] - bxx[0]) / len(ks)
        bw = gw * 0.5
        for i, k in enumerate(ks):
            st = stage(a, k)
            v = st.get("net_events") or 0
            h = (bxx[3] - bxx[1]) * v / float(ymax * 1.2)
            x = bxx[0] + gw * (i + 0.25)
            c.d.rectangle([x, bxx[3] - h, x + bw, bxx[3]], fill=STAGE_COL[k],
                          outline="#555")
            c.txt(x + bw / 2, bxx[3] - h - 6, fmt_num(v), size=11, anchor="mb")
            c.txt(x + bw / 2, bxx[3] + 8, "阶段%d" % k, size=12, anchor="ma")
            c.txt(x + bw / 2, bxx[3] + 28,
                  "capped %s%%" % pct(st.get("capped_share") or 0, 3), size=10,
                  anchor="ma", fill="#8e44ad")
        c.rot(bxx[0] - 48, (bxx[1] + bxx[3]) / 2, "净事件", size=13)
    else:
        pending_panel(c, box2, "无阶段数据")
    # 下：耗时 + 判定占比
    box3 = (90, 690, 1560, 900)
    c.border(box3)
    c.txt(box3[0] + 12, box3[1] + 8, "阶段耗时与判定占比", size=16, bold=True)
    y = box3[1] + 44
    for k in ks:
        st = stage(a, k)
        rs = st.get("reaction_shares") or {}
        c.txt(box3[0] + 14, y,
              "阶段%d：complete %s%% / incomplete %s%% / none %s%% / capped %s%%；"
              "净事件 %s；耗时 %.1fs"
              % (k, pct(rs.get("complete") or 0, 2), pct(rs.get("incomplete") or 0, 2),
                 pct(rs.get("none") or 0, 2), pct(rs.get("capped") or 0, 3),
                 fmt_commas(st.get("net_events")), st.get("runtime_s") or 0),
              size=12)
        y += 24
    for k in (1, 2, 3, 4):
        if k not in ks:
            c.txt(box3[0] + 14, y, "阶段%d：未就绪（phase%d 结果缺失）" % (k, k),
                  size=12, fill="#c0392b")
            y += 22
    lines = ["capped = 合并后 >40 原子的碰撞被弹性截断（max_reaction_atoms=40）；capped 占比越低越接近无保护极限。",
             "complete/incomplete/none 为反应判定三类；净事件 = 反应事件总数（不含 capped 弹性碰撞）。"]
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- ⑩ 多样性
def chart_diversity(a, out):
    ks = [1, 2, 3, 4]
    W, H = 1600, 1000
    c = Chart(W, H,
              "⑩ T63 多样性/新物质/最大尺寸随阶段变化",
              "四阶段终态：分子式种数、目录外新物质、最大原子数、终态分子数；未就绪阶段显示为占位")
    panels = [("终态分子式种数", "distinct_formulas"),
              ("目录外新物质数", "new_substances"),
              ("终态最大原子数", "final_max_atoms"),
              ("终态分子数", "final_N")]
    for i, (title, key) in enumerate(panels):
        col, row = i % 2, i // 2
        x0 = 80 + col * 740
        y0 = 160 + row * 380
        box = (x0, y0, x0 + 680, y0 + 330)
        c.border(box)
        c.txt(x0 + 12, y0 + 8, title, size=15, bold=True)
        vals = []
        for k in ks:
            st = stage(a, k)
            vals.append((k, st.get(key) or 0 if stage_ok(a, k) else None))
        real = [(k, v) for k, v in vals if v is not None]
        if real:
            bx = (x0 + 70, y0 + 46, x0 + 660, y0 + 330 - 36)
            vmax = max(v for _, v in real) or 1
            mx, my = c.frame(bx, (0, 4), (0, vmax * 1.2),
                             [i + 0.5 for i in range(4)],
                             nice_ticks(0, vmax * 1.2, 5),
                             xtick_fmt=lambda v: "",
                             ytick_fmt=lambda v: fmt_num(v))
            for k, v in vals:
                if v is None:
                    continue
                gw = (bx[2] - bx[0]) / 4
                bw = gw * 0.5
                x = bx[0] + gw * ((k - 1) + 0.25)
                h = (bx[3] - bx[1]) * v / float(vmax * 1.2)
                c.d.rectangle([x, bx[3] - h, x + bw, bx[3]], fill=STAGE_COL[k],
                              outline="#555")
                c.txt(x + bw / 2, bx[3] - h - 6, fmt_num(v), size=11,
                      anchor="mb", bold=True)
                c.txt(x + bw / 2, bx[3] + 8, "s%d" % k, size=12, anchor="ma")
            for k in ks:
                if k not in [k2 for k2, v in vals if v is not None]:
                    c.txt(bx[0] + (bx[2] - bx[0]) / 4 * (k - 0.5), bx[3] - 20,
                          "未就绪", size=9, anchor="mm", fill="#c0392b")
        else:
            pending_panel(c, (x0 + 10, y0 + 40, x0 + 670, y0 + 320), "未就绪")
    lines = []
    for k in ks:
        st = stage(a, k)
        if not stage_ok(a, k):
            lines.append("阶段%d：未就绪（phase%d 结果缺失）" % (k, k))
            continue
        lines.append("阶段%d：%s 种分子式 / %s 新物质 / 最大 %d 原子 / %s 分子"
                     % (k, st.get("distinct_formulas"), fmt_commas(st.get("new_substances")),
                        st.get("final_max_atoms") or 0, fmt_commas(st.get("final_N"))))
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- 11 top 结构
def chart_top_structures(a, out):
    ks = [1, 2, 3, 4]
    structs = (a.get("structures") or {}).get("per_stage") or {}
    ncols = 6
    pw, ph = 250, 300
    W = 40 + ncols * (pw + 10)
    H = 170 + 4 * (ph + 30) + 90
    c = Chart(W, H,
              "11 T63 四阶段 top 物种分子结构（每阶段前 6，共 24 面板）",
              "节点=原子（9 元素配色）；键按多重键着色（1 灰 / 2 深蓝 / 3 红）；"
              "F稳定=该分子式在 fast 引擎下为唯一稳定产物；缺失阶段显示为占位")
    items = [(ELEMCOL[e], "%s %s" % (e, CN[e])) for e in ORDER]
    c.legend(40, 104, items, size=12, row_h=22, cols=9, col_w=105)
    c.legend(1120, 104, [(BONDCOL[1], "单键"), (BONDCOL[2], "双键"),
                         (BONDCOL[3], "三键")], size=12, row_h=22, cols=3,
             col_w=120)
    # 行 = 阶段
    for row, k in enumerate(ks):
        y0 = 150 + row * (ph + 30)
        lst = structs.get("phase%d" % k) or []
        if not stage_ok(a, k):
            for col in range(ncols):
                box = (40 + col * (pw + 10), y0, 40 + col * (pw + 10) + pw,
                       y0 + ph)
                c.border(box)
                if col == 0:
                    pending_panel(c, box, "未就绪", "phase%d 未就绪" % k)
                else:
                    c.d.rectangle(box, outline="#e0e0e0", width=1)
            continue
        for col in range(ncols):
            x0 = 40 + col * (pw + 10)
            box = (x0, y0, x0 + pw, y0 + ph)
            c.border(box)
            if col < len(lst):
                draw_mol_panel(c, lst[col], box, rank=lst[col].get("rank"))
            else:
                label = ("（本阶段仅 %d 种）" % len(lst)) if lst else "—"
                c.txt(x0 + pw / 2, y0 + ph / 2, label, size=11,
                      anchor="mm", fill="#999")
    lines = []
    for k in ks:
        lst = structs.get("phase%d" % k) or []
        if not stage_ok(a, k):
            lines.append("阶段%d：未就绪（phase%d 结果缺失）" % (k, k))
            continue
        lines.append("阶段%d top6：%s" % (k, "、".join(
            "%s(%d)" % (r.get("formula"), r.get("atoms") or 0) for r in lst[:6])))
    data_note(c, lines)
    return c.save(out)


# ---------------------------------------------------------------- 12 总览
def chart_stage_compare(a, out):
    ks = [1, 2, 3, 4]
    W, H = 1600, 1080
    c = Chart(W, H,
              "12 T63 四阶段总览：聚素熔体 → F 端帽 → A 桥 → K 骨架（价数滴定）",
              "每阶段终态关键数字 + 分子数/原子数/种数条形；底部为守恒核对结论")
    # 顶部卡片
    cw = (1560 - 90 - 3 * 12) / 4.0
    for i, k in enumerate(ks):
        x = 90 + i * (cw + 12)
        st = stage(a, k)
        ok = stage_ok(a, k)
        box = (x, 140, x + cw, 420)
        c.d.rectangle(box, fill="#fafafa", outline=STAGE_COL[k], width=3)
        c.txt(x + 10, 148, "阶段%d" % k, size=18, bold=True, fill=STAGE_COL[k])
        c.txt(x + 10, 174, STAGE_NAME[k], size=12, fill="#555")
        if not ok:
            c.txt(x + cw / 2, 300, "未就绪", size=22, bold=True, anchor="mm",
                  fill="#c0392b")
            continue
        rows = [
            ("初始", "%s 分子 / %s 原子" % (fmt_commas(st.get("config", {}).get("initial_particles")),
                                         fmt_commas(st.get("config", {}).get("initial_atoms")))),
            ("终态", "%s 分子 / %s 原子" % (fmt_commas(st.get("final_N")),
                                         fmt_commas(st.get("final_atoms")))),
            ("结构种数", "%s" % st.get("distinct_formulas")),
            ("平均原子", "%.2f" % (st.get("final_mean_atoms") or 0)),
            ("最大原子", "%d" % (st.get("final_max_atoms") or 0)),
            ("新物质", fmt_commas(st.get("new_substances"))),
            ("净事件", fmt_commas(st.get("net_events"))),
            ("capped", "%s（%s%%）" % (fmt_commas(st.get("capped_total")),
                                      pct(st.get("capped_share") or 0, 3))),
            ("耗时", "%.1fs" % (st.get("runtime_s") or 0)),
        ]
        y = 200
        for lab, val in rows:
            c.txt(x + 12, y, lab, size=11, fill="#666")
            c.txt(x + 96, y, val, size=11, fill="#222")
            y += 24
    # 底部三个条形图
    metrics = [("终态分子数", "final_N"), ("终态原子数", "final_atoms"),
               ("分子式种数", "distinct_formulas")]
    for i, (title, key) in enumerate(metrics):
        x0 = 90 + i * 490
        box = (x0, 470, x0 + 470, 780)
        c.border(box)
        c.txt(x0 + 12, box[1] + 8, title, size=14, bold=True)
        vals = [(k, (stage(a, k).get(key) or 0)) for k in ks if stage_ok(a, k)]
        if not vals:
            continue
        bx = (x0 + 60, box[1] + 44, x0 + 456, box[3] - 40)
        vmax = max(v for _, v in vals) or 1
        mx, my = c.frame(bx, (0, 4), (0, vmax * 1.2),
                         [j + 0.5 for j in range(4)],
                         nice_ticks(0, vmax * 1.2, 4),
                         xtick_fmt=lambda v: "",
                         ytick_fmt=lambda v: fmt_num(v))
        gw = (bx[2] - bx[0]) / 4
        bw = gw * 0.5
        for k, v in vals:
            x = bx[0] + gw * ((k - 1) + 0.25)
            h = (bx[3] - bx[1]) * v / float(vmax * 1.2)
            c.d.rectangle([x, bx[3] - h, x + bw, bx[3]], fill=STAGE_COL[k],
                          outline="#555")
            c.txt(x + bw / 2, bx[3] - h - 6, fmt_num(v), size=10, anchor="mb")
            c.txt(x + bw / 2, bx[3] + 8, "s%d" % k, size=11, anchor="ma")
        for k in ks:
            if not stage_ok(a, k):
                c.txt(bx[0] + gw * ((k - 1) + 0.5), bx[3] - 24, "未就绪", size=9,
                      anchor="mm", fill="#c0392b")
    # 守恒结论
    cs = a.get("cross_stage") or {}
    bs = cs.get("balance_summary") or {}
    pres = cs.get("present") or []
    miss = cs.get("missing") or []
    if not miss and len(pres) >= 4:
        stage_txt = "四阶段全部通过"
    elif miss:
        stage_txt = "已完成 %d/4 阶段（未就绪：%s）" % (
            len(pres), "、".join("阶段%d" % k for k in miss))
    else:
        stage_txt = "已完成 %d/4 阶段" % len(pres)
    box = (90, 810, 1560, 900)
    c.border(box)
    c.txt(box[0] + 14, box[1] + 10,
          "守恒核对：元素 %s / 分子 %s / 原子 %s / 状态链 %s；%s"
          % ("√" if bs.get("all_elements_conserved") else "×",
             "√" if bs.get("all_molecule_balance") else "×",
             "√" if bs.get("all_atom_balance") else "×",
             "√" if bs.get("all_states_chain_ok") else "×",
             stage_txt),
          size=14, bold=True)
    lines = ["每阶段：1000 分钟降温（1000→0°C）→ 整理归档 → 温度重置 + 投入下一单质 → 继续退火。",
             "价数滴定：F2 端帽（+v1）→ A2 桥（+v2）→ K2 骨架（+v3）；每个阶段元素守恒（期望=上一阶段终态+投放）。"]
    data_note(c, lines)
    return c.save(out)


CHARTS = [
    ("loads", "t63_loads.png", chart_loads),
    ("stage_profiles", "t63_stage_profiles.png", chart_stage_profiles),
    ("element_balance", "t63_element_balance.png", chart_element_balance),
    ("valence", "t63_valence.png", chart_valence),
    ("top_species", "t63_top_species.png", chart_top_species),
    ("persistence", "t63_persistence.png", chart_persistence),
    ("size_distribution", "t63_size_distribution.png", chart_size_distribution),
    ("snapshots", "t63_snapshots.png", chart_snapshots),
    ("reaction_stats", "t63_reaction_stats.png", chart_reaction_stats),
    ("diversity", "t63_diversity.png", chart_diversity),
    ("top_structures", "t63_top_structures.png", chart_top_structures),
    ("stage_compare", "t63_stage_compare.png", chart_stage_compare),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="T63 图表渲染")
    ap.add_argument("--analysis", default=DEFAULT_ANALYSIS)
    ap.add_argument("--images", default=DEFAULT_IMAGES)
    ap.add_argument("--only", default=None,
                    help="只渲染指定图（逗号分隔 name），用于自测")
    args = ap.parse_args(argv)
    if not os.path.exists(args.analysis):
        print("[error] analysis 文件不存在：%s" % args.analysis)
        return 2
    with open(args.analysis, encoding="utf-8") as fh:
        a = json.load(fh)
    os.makedirs(args.images, exist_ok=True)
    want = None
    if args.only:
        want = [s.strip() for s in args.only.split(",") if s.strip()]
    ok, fail = 0, 0
    for name, fname, func in CHARTS:
        if want and name not in want:
            continue
        out = os.path.join(args.images, fname)
        try:
            size = func(a, out)
            ok += 1
            print("[ok] %-18s %8d bytes  %s" % (name, size, out))
        except Exception as exc:
            fail += 1
            import traceback
            traceback.print_exc()
            print("[FAIL] %-16s %s: %s" % (name, fname, exc))
    print("\n[done] %d ok, %d failed" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
