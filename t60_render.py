# -*- coding: utf-8 -*-
"""t60_render.py —— T60 全系列汇报图摆盘（只读 t60_top20_data.json）

生成：
  images/t60_top20_T55.png / _T56 / _T57 / _T58 / _T59A / _T59B
  images/t60_top20_T59A_hf.png / _T59B_hf.png      # 8 张 top20 摆盘
  images/t60_important_1.png / _t60_important_2.png # 67 个重要物质图鉴（36+31）
  images/t60_series_overview.png                    # 全系列总览
  images/t60_top20_counts.png                       # 各实验 top20 数量条形（可选）
  t60_figures_manifest.json

风格与 t59 一致（msyh、1600px 宽、无重叠）。结构布局复用 t59_render.layout_mol
（弹簧/环形自动布局）；节点按 9 元素配色，键按多重键着色。
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import t59_render as R  # 复用 Chart / layout_mol / 配色

Chart = R.Chart
layout_mol = R.layout_mol
ELEMCOL = R.ELEMCOL
BONDCOL = R.BONDCOL
ORDER = R.ORDER
CN = R.CN
data_note = R.data_note

DATA = os.path.join(BASE, "t60_top20_data.json")
IMAGES = os.path.join(BASE, "images")
MANIFEST = os.path.join(BASE, "t60_figures_manifest.json")

TAG_COL = {"29内": "#2e8b57", "目录内": "#2e86de", "新物质": "#e67e22"}
EXP_ORDER = ["T55", "T56", "T57", "T58", "T59A", "T59B", "T59A_hf", "T59B_hf"]
EXP_SHORT = {"T55": "T55", "T56": "T56", "T57": "T57", "T58": "T58",
             "T59A": "T59A", "T59B": "T59B", "T59A_hf": "T59A_hf",
             "T59B_hf": "T59B_hf"}
ELEMENTS_N = {"T55": 3, "T56": 6, "T57": 3, "T58": 9, "T59A": 9, "T59B": 9,
              "T59A_hf": 9, "T59B_hf": 9}
LAYOUT_CACHE = {}


def load_data():
    with open(DATA, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- 结构绘制
def _layout(st):
    key = (st.get("label") or "", len(st.get("atoms") or []),
           tuple(tuple(e) for e in (st.get("edges") or [])))
    if key not in LAYOUT_CACHE:
        LAYOUT_CACHE[key] = layout_mol(st.get("atoms") or [],
                                       st.get("edges") or [])
    return LAYOUT_CACHE[key]


def draw_structure(c, st, box, letters=True):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    atoms = (st or {}).get("atoms") or []
    edges = (st or {}).get("edges") or []
    n = len(atoms)
    c.d.rectangle([x0, y0, x1, y1], fill="#fbfbfb", outline="#e3e3e3")
    if not n:
        c.txt((x0 + x1) / 2, (y0 + y1) / 2, "（无结构）", size=10,
              anchor="mm", fill="#999")
        return
    pos = _layout(st)
    rad = max(2.2, min(11.0, 0.42 * min(bw, bh) / math.sqrt(n)))
    if n > 24:
        rad = min(rad, 4.2)
    elif n > 18:
        rad = min(rad, 6.0)
    if n == 2:
        pos = [(-0.36, 0.0), (0.36, 0.0)]
    pts = [(x0 + bw / 2 + px * (bw / 2 - rad - 2),
            y0 + bh / 2 + py * (bh / 2 - rad - 2)) for px, py in pos]
    for e in edges:
        i, j, m = int(e[0]), int(e[1]), int(e[2])
        c.d.line([pts[i], pts[j]], fill=BONDCOL.get(m, "#888"),
                 width=1 if m == 1 else 2)
    for i, el in enumerate(atoms):
        X, Y = pts[i]
        c.d.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                    fill=ELEMCOL.get(el, "#ccc"), outline="#333", width=1)
        if letters and rad >= 5.2:
            c.txt(X, Y - 1, el, size=max(7, int(rad * 1.45)), bold=True,
                  anchor="mm", fill="#111")


def elem_str(ec):
    if not ec:
        return "-"
    return "".join("%s%d" % (e, ec[e]) for e in ORDER if ec.get(e))


def tag_of(rec):
    if rec.get("in_29"):
        return "29内"
    if rec.get("in_catalog"):
        return "目录内"
    return "新物质"


def _tag(c, x, y, s, size=10, anchor="la"):
    c.txt(x, y, s, size=size, bold=True, fill=TAG_COL.get(s, "#444"),
          anchor=anchor)


# ---------------------------------------------------------------- ① top20 摆盘
def exp_title(e):
    name = e["name"]
    desc = e.get("desc", "") or ""
    for pref in (name + "：", name + ":", "T59 "):
        if desc.startswith(pref):
            desc = desc[len(pref):]
            break
    return "%s · %s" % (name, desc)


def exp_subtitle(e):
    cap = e.get("max_reaction_atoms")
    cap_s = "cap=%s" % cap if cap else "无 cap"
    n = len(e.get("top20") or [])
    distinct = e.get("distinct_formulas") or n
    note = ""
    if n < 20:
        note = "（终态仅 %d 种，已全部展示）" % n
    return ("投料 %s 分子 / %s 原子 · L=%s · %s · 终态 %s 分子 / %s 原子 / "
            "%s 种结构 / 最大 %s 原子  %s"
            % (R.fmt_commas(e.get("initial_particles")),
               R.fmt_commas(e.get("initial_atoms")),
               R.fmt_commas(e.get("environment_L")), cap_s,
               R.fmt_commas(e.get("final_N")),
               R.fmt_commas(e.get("final_atoms")),
               R.fmt_commas(distinct), e.get("max_atoms"), note))


def chart_top20(e, out):
    top = e.get("top20") or []
    n = len(top)
    cols = 4
    rows = max(1, math.ceil(n / cols))
    pw, ph = 383, 365
    W = 1600
    header = 150
    H = header + rows * (ph + 10) + 86
    c = Chart(W, H, "T60 摆盘 · %s" % exp_title(e), exp_subtitle(e))
    # 色卡（只列本实验 top20 中出现的元素）
    present = set()
    for rec in top:
        present |= set((rec.get("element_counts") or {}).keys())
    ela = [x for x in ORDER if x in present]
    items = [(ELEMCOL[x], "%s %s" % (x, CN[x])) for x in ela]
    c.legend(36, 100, items, size=11, row_h=20, cols=len(ela), col_w=150)
    c.legend(1390, 100, [(BONDCOL[1], "单键"), (BONDCOL[2], "双键"),
                         (BONDCOL[3], "三键")], size=11, row_h=20, cols=3,
             col_w=70)
    for i, rec in enumerate(top):
        r, col = divmod(i, cols)
        x0 = 24 + col * (pw + 10)
        y0 = header + r * (ph + 10)
        box = (x0, y0, x0 + pw, y0 + ph)
        c.d.rectangle(box, fill="#ffffff", outline="#d8d8d8", width=1)
        # 头部
        c.txt(x0 + 10, y0 + 6, "#%d  %s" % (rec.get("rank"), rec.get("formula")),
              size=15, bold=True, fill="#111")
        c.txt(x0 + 10, y0 + 29, rec.get("zh") or "", size=11, fill="#555")
        _tag(c, x0 + pw - 10, y0 + 8, tag_of(rec), size=11, anchor="ra")
        # 结构
        draw_structure(c, rec.get("structure") or {},
                       (x0 + 8, y0 + 48, x0 + pw - 8, y0 + ph - 78))
        # 底部信息
        yb = y0 + ph - 72
        c.txt(x0 + 10, yb, "×%s · %d 原子"
              % (R.fmt_commas(rec.get("count")), rec.get("atoms") or 0),
              size=12, bold=True, fill="#111")
        va = rec.get("valence_atoms") or {}
        c.txt(x0 + 10, yb + 20, "元素 %s · 价数 %d/%d/%d"
              % (elem_str(rec.get("element_counts")), va.get("v3", 0),
                 va.get("v2", 0), va.get("v1", 0)), size=10, fill="#333")
        c.txt(x0 + 10, yb + 38, "目录：%s · %s"
              % (tag_of(rec), "在 84,225 目录" if rec.get("in_catalog")
                 else "目录外"), size=9, fill="#777")
    # 空位标注
    if n < cols * rows:
        r, col = divmod(n, cols)
        x0 = 24 + col * (pw + 10)
        y0 = header + r * (ph + 10)
        c.txt(x0 + 18, y0 + 40,
              "该实验终态仅 %d 种，其余格位留空" % n, size=12, fill="#999")
    c.txt(36, H - 46,
          "图注：rank=终态数量排名；每个面板为结构（9 元素配色、键按 1/2/3 重着色）+ "
          "公式/中文名/数量/原子数/元素组成/价数/目录归属；"
          "标签 29内=29 聚素库、目录内=84,225 目录、新物质=目录外。", size=11,
          fill="#555")
    return c.save(out)


# ---------------------------------------------------------------- ② 重要物质图鉴
def chart_important(items, page, total_pages, out):
    cols = 6
    rows = 6
    pw, ph = 256, 282
    W = 1600
    header = 132
    H = header + rows * (ph + 8) + 76
    c = Chart(W, H,
              "T60 重要物质图鉴（%d/%d）：跨实验出现的重要分子（共 %d 个）"
              % (page, total_pages, len(items)),
              "排序：出现实验数（多→少）→ 最佳排名（小→大）→ 最大数量（多→少）→ 原子数；"
              "标签为出现过的实验（T59A_hf/T59B_hf 为 cap60 高保真）")
    for i, rec in enumerate(items):
        r, col = divmod(i, cols)
        x0 = 20 + col * (pw + 8)
        y0 = header + r * (ph + 8)
        box = (x0, y0, x0 + pw, y0 + ph)
        c.d.rectangle(box, fill="#ffffff", outline="#d8d8d8")
        num = (page - 1) * 36 + i + 1
        c.txt(x0 + 8, y0 + 4, "#%d %s" % (num, rec.get("formula")), size=12,
              bold=True if rec.get("n_experiments", 0) >= 3 else False,
              fill="#111")
        c.txt(x0 + 8, y0 + 21, "%s · %d 原子"
              % (rec.get("zh") or "", rec.get("atoms") or 0), size=9,
              fill="#555")
        draw_structure(c, rec.get("structure") or {},
                       (x0 + 6, y0 + 38, x0 + pw - 6, y0 + 168))
        occ = rec.get("occurrences") or []
        labels = [EXP_SHORT.get(o["experiment"], o["experiment"]) for o in occ]
        c.txt(x0 + 8, y0 + 174, "出现 %d 次" % rec.get("n_experiments", 0),
              size=9, bold=True, fill="#333")
        # 标签分两行
        line1 = " ".join(labels[:3])
        line2 = " ".join(labels[3:])
        c.txt(x0 + 8, y0 + 190, line1, size=9, fill="#2e86de")
        c.txt(x0 + 8, y0 + 204, line2, size=9, fill="#2e86de")
        c.txt(x0 + 8, y0 + 222,
              "最大 %s · 最佳 #%s"
              % (R.fmt_commas(rec.get("max_count")), rec.get("best_rank")),
              size=9, fill="#333")
        # 该物质最常出现的实验最高名次
        best = min(occ, key=lambda o: o.get("rank") or 99) if occ else None
        if best:
            c.txt(x0 + 8, y0 + 238,
                  "最佳出现：%s #%d（%s）"
                  % (EXP_SHORT.get(best["experiment"], best["experiment"]),
                     best.get("rank") or 0,
                     R.fmt_commas(best.get("count"))), size=8, fill="#777")
    c.txt(20, H - 40,
          "图注：跨实验重要物质并集按重要度排序；结构为 F 稳定产物（含 39/40/59/60 原子巨型，"
          "自动弹簧/环形布局）；出现标签中 T59A_hf/T59B_hf 为 cap60 高保真实验。", size=10,
          fill="#555")
    return c.save(out)


# ---------------------------------------------------------------- ③ 总览
def chart_series_overview(data, out):
    exps = data["experiments"]
    names = [e["name"] for e in exps]
    W, H = 1600, 1210
    c = Chart(W, H,
              "T60 全系列总览：T55 → T59B（含 cap60 高保真）",
              "规模 / 环境 / 终态 / 结构数 / 最大原子数；T55-T59B 为主系列，"
              "T59A_hf/T59B_hf 为 cap60 对照")
    cols_main = ["#95a5a6", "#8e44ad", "#f39c12", "#2e86de",
                 "#16a085", "#c0392b", "#7f8c8d", "#e67e22"]
    panels = [
        ("初始分子数", lambda e: e.get("initial_particles"), R.fmt_commas, False),
        ("初始原子数（对数）", lambda e: e.get("initial_atoms"), R.fmt_commas, True),
        ("环境 L（对数）", lambda e: e.get("environment_L"), R.fmt_commas, True),
        ("终态分子数", lambda e: e.get("final_N"), R.fmt_commas, False),
        ("终态结构种数", lambda e: e.get("distinct_formulas"), R.fmt_commas, False),
        ("终态最大原子数", lambda e: e.get("max_atoms"), lambda v: "%d" % v, False),
    ]
    pw, ph = 740, 300
    x0s = [36, 820]
    y0s = [120, 440, 760]
    for idx, (title, getter, fmt, logy) in enumerate(panels):
        px = x0s[idx % 2]
        py = y0s[idx // 2]
        box = (px + 100, py + 44, px + pw - 30, py + ph - 40)
        vals = [getter(e) or 0 for e in exps]
        vmax = max(vals + [1]) * 1.45
        c.txt(px + 14, py + 4, "%s %s" % ("①②③④⑤⑥"[idx], title), size=18,
              bold=True)
        if logy:
            yt = [v for v in (1000, 10000, 100000, 1000000, 10000000)
                  if v <= vmax] or [1, 10]
            ylo = 1000
        else:
            yt = R.nice_ticks(0, vmax, 4)
            ylo = 0
        nn = len(exps)
        mx, my = c.frame(box, (0, nn), (ylo, vmax),
                         [i + 0.5 for i in range(nn)], yt,
                         xtick_labels=names, ytick_fmt=fmt, logy=logy)
        bw = (box[2] - box[0]) / nn * 0.46
        for i, e in enumerate(exps):
            X = box[0] + (box[2] - box[0]) / nn * (i + 0.5)
            val = vals[i]
            Y = my(max(val, ylo if logy else 0))
            c.d.rectangle([X - bw / 2, Y, X + bw / 2, box[3]],
                          fill=cols_main[i % len(cols_main)], outline="#333",
                          width=1)
            c.txt(X, Y - 5, fmt(val), size=11, anchor="mb",
                  bold=(i >= 6))
    data_note(c, [
        "主系列：T55（O/X/C，9000 分子/18000 原子）→ T56（6 元素）→ T57（29 聚素+面积）"
        "→ T58（九元素、84,225 库随机 44 种、L=400000、cap20）→ T59A（120 种、L=60000、cap40、"
        "三价最多）→ T59B（整理底物+batchB 复热、230,133 原子）。",
        "终态结构种数：9 / 22 / 4 / 937 / 43 / 67；T59 cap60 对照把 T59A 收敛到 9 种、"
        "T59B 收敛到 13 种（见 t60_top20_T59A_hf/T59B_hf）。",
        "元素数：T55 3、T56 6、T57 3、T58/T59 9；环境 L：T55/T56/T57 10000、T58 400000、"
        "T59 60000；最大原子数：T56 22、T58 20、T59A/B 40、cap60 对照 B 60。",
    ], y=1090)
    return c.save(out)


# ---------------------------------------------------------------- ④ top20 数量
def chart_top20_counts(data, out):
    exps = data["experiments"]
    W, H = 1600, 1380
    c = Chart(W, H,
              "T60 各实验 top20 数量（对数）：主导分子数量级对比",
              "每格一个实验；横向条形为终态数量（对数），标注前 3 名数量；"
              "灰色=常规，橙色=39/40/59/60 原子巨型")
    cols, rows = 2, 4
    pw, ph = 770, 300
    for i, e in enumerate(exps):
        r, col = divmod(i, cols)
        x0 = 24 + col * (pw + 12)
        y0 = 96 + r * 300
        c.d.rectangle([x0, y0, x0 + pw, y0 + ph], outline="#ddd")
        c.txt(x0 + 10, y0 + 4, e["name"], size=13, bold=True)
        c.txt(x0 + 120, y0 + 6, e.get("desc", ""), size=10, fill="#555")
        top = (e.get("top20") or [])[:20]
        n = len(top)
        vmax = max([t.get("count") or 1 for t in top] + [1]) * 2.2
        bx0, by0, bx1, by1 = x0 + 150, y0 + 26, x0 + pw - 110, y0 + ph - 10
        logmin, logmax = 0.0, math.log10(max(vmax, 10))

        def mx(v):
            v = max(1.0, float(v))
            return bx0 + (math.log10(v) - logmin) / (logmax - logmin) * (bx1 - bx0)

        row_h = (by1 - by0) / max(1, n)
        for j, t in enumerate(top):
            cy = by0 + row_h * (j + 0.5)
            giant = (t.get("atoms") or 0) >= 39
            c.d.rectangle([bx0, cy - row_h * 0.32, mx(t.get("count") or 0),
                           cy + row_h * 0.32],
                          fill=("#e67e22" if giant else "#95a5a6"),
                          outline="#333")
            c.txt(bx0 - 6, cy, t.get("formula"), size=8, anchor="rm")
            if j < 3:
                c.txt(mx(t.get("count") or 0) + 5, cy,
                      R.fmt_commas(t.get("count")), size=8, anchor="lm")
    data_note(c, [
        "数量跨度：T55 OXC 5,945（第 2 名仅 5）；T56 CF 4,749；T57 OXC 9,746；"
        "T58 WA 3,151；T59A CF 9,349；T59B CF 12,131；cap60 对照 CF 9,403/11,867。",
        "橙色条目为 39/40 原子（或 59/60）巨型分子，数量通常 1~2，是 cap 边界允许的 F 产物。",
    ], y=1320)
    return c.save(out)


# ---------------------------------------------------------------- main
def main():
    data = load_data()
    exps = data["experiments"]
    os.makedirs(IMAGES, exist_ok=True)
    manifest = {"generated": "", "source": os.path.basename(DATA),
                "figures": [], "notes": [
                    "所有图仅由 t60_top20_data.json 生成；结构布局复用 t59_render.layout_mol。",
                    "top20 摆盘：4 列动态行；T55（9 种）/T57（4 种）/T59A_hf（9 种）"
                    "展示全部并注明。",
                    "重要物质 67 个分 2 页（36+31），按出现实验数/最佳排名/最大数量排序。",
                    "tag 29内=29 聚素库、目录内=84,225 目录、新物质=目录外。",
                ]}
    import datetime
    manifest["generated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for e in exps:
        name = e["name"]
        out = os.path.join(IMAGES, "t60_top20_%s.png" % name)
        size = chart_top20(e, out)
        manifest["figures"].append({
            "file": os.path.basename(out), "type": "top20",
            "experiment": name, "title": exp_title(e),
            "subtitle": exp_subtitle(e),
            "n_panels": len(e.get("top20") or []),
            "bytes": size})
        print("[ok] top20 %-9s %d panels %s" % (name, len(e.get("top20") or []),
                                                out), flush=True)
    imp = data["important"]
    pages = [imp[:36], imp[36:]]
    for i, items in enumerate(pages, 1):
        out = os.path.join(IMAGES, "t60_important_%d.png" % i)
        size = chart_important(items, i, 2, out)
        manifest["figures"].append({
            "file": os.path.basename(out), "type": "important",
            "page": i, "n_items": len(items), "bytes": size,
            "title": "T60 重要物质图鉴 %d/2（%d 个）" % (i, len(items)),
            "description": "跨实验重要物质并集（67 个）第 %d 页；按出现实验数/最佳排名/最大数量排序。" % i})
        print("[ok] important %d (%d items) %s" % (i, len(items), out), flush=True)
    out = os.path.join(IMAGES, "t60_series_overview.png")
    size = chart_series_overview(data, out)
    manifest["figures"].append({"file": os.path.basename(out),
                                "type": "overview", "bytes": size,
                                "title": "T60 全系列总览：T55 → T59B（含 cap60 高保真）",
                                "description": "8 个实验的初始分子/原子、环境 L、终态分子/结构数/最大原子数对比。"})
    print("[ok] overview %s" % out, flush=True)
    out = os.path.join(IMAGES, "t60_top20_counts.png")
    size = chart_top20_counts(data, out)
    manifest["figures"].append({"file": os.path.basename(out),
                                "type": "counts", "bytes": size,
                                "title": "T60 各实验 top20 数量（对数）",
                                "description": "8 个实验 top20 数量条形拼图；橙色为 39/40/59/60 原子巨型。"})
    print("[ok] counts %s" % out, flush=True)
    # 尺寸
    for f in manifest["figures"]:
        p = os.path.join(IMAGES, f["file"])
        im = Image.open(p)
        f["width"], f["height"] = im.width, im.height
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print("[saved] %s (%d figures)" % (MANIFEST, len(manifest["figures"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())



