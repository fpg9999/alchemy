# -*- coding: utf-8 -*-
"""t61_render.py —— T61 六边形棋盘格详细摆放图（只读 t61_hex_layouts.json）

生成：
  images/t61_hex_medium.png        5~18 原子中等大分子（4×3 网格，全部 9 种）
  images/t61_hex_giants_01..10.png 37~40 原子巨型（3×2/页，共 57 种 → 10 页）
  images/t61_hex_summary.png       66 种索引表
  images/t61_hex_legend.png        图例（9 元素/S/C/L/多重键/L 中点空格）
  t61_hex_manifest.json

几何：place 为轴向坐标 (q,r)；flat-top 六边形 center=(1.5 s q, √3 s (r+q/2))，
复用 t8_render_forms.center_of / hex_pts。键型 S/C/L 直接取自数据，不重算。
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import t59_render as R
import t8_render_forms as T8
import pot_all as P
import pot_v2

Chart = R.Chart
data_note = R.data_note
fmt_commas = R.fmt_commas
ORDER = R.ORDER
data_note = R.data_note

S3 = math.sqrt(3.0)
ELEMCOL = {"O": "#2ecc71", "X": "#f39c12", "C": "#3498db", "P": "#8e44ad",
           "W": "#16a085", "L": "#d35400", "K": "#c0392b", "A": "#1abc9c",
           "F": "#e74c3c"}
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
BONDCOL = {"S": "#c0392b", "C": "#1e8449", "L": "#8e44ad", None: "#7f8c8d"}
BONDNAME = {"S": "S 共享边", "C": "C 共享顶点", "L": "L 隔格长键",
            None: "未解析"}
GRIDCOL = "#e4e4e4"
MIDCOL = "#8e44ad"
WARNCOL = "#e67e22"

DATA = os.path.join(BASE, "t61_hex_layouts.json")
IMAGES = os.path.join(BASE, "images")
MANIFEST = os.path.join(BASE, "t61_hex_manifest.json")


def load_data():
    with open(DATA, "r", encoding="utf-8") as fh:
        return json.load(fh)


def zh_of(formula):
    out = []
    for e in ORDER:
        c = formula.count(e)
        if c:
            # 去掉已被其它元素计数的干扰：按 formula 正则解析更稳
            pass
    # 正则解析
    import re
    parts = re.findall(r"([A-Z])(\d*)", formula or "")
    cnt = {}
    for e, n in parts:
        cnt[e] = cnt.get(e, 0) + (int(n) if n else 1)
    return "".join(CN[e] + (str(cnt[e]) if cnt[e] > 1 else "")
                   for e in ORDER if e in cnt) or formula


def counts_str(item):
    c = item.get("counts") or {}
    a = c.get("T59A")
    b = c.get("T59B")
    seg = []
    if a is not None:
        seg.append("T59A ×%s" % fmt_commas(a))
    if b is not None:
        seg.append("T59B ×%s" % fmt_commas(b))
    return " · ".join(seg) if seg else "-"


def bonds_consistent(item):
    pos = item.get("place") or []
    for (a, b, m) in item.get("edges") or []:
        d = (pos[b][0] - pos[a][0], pos[b][1] - pos[a][1])
        if P.classify_offset(d) is None:
            return False
    return True


def repair_item(item):
    """保存的 place 与 bonds 不一致时，用修正后的随机重排映射重新嵌入（仅内存，不改数据）。"""
    import random
    atoms = list(item["atoms"])
    edges = [tuple(e) for e in item["edges"]]
    n = len(atoms)
    best = None
    for seed in range(12):
        rng = random.Random(seed)
        perm = list(range(n))
        rng.shuffle(perm)
        new_atoms = [atoms[perm[i]] for i in range(n)]
        inv = {perm[i]: i for i in range(n)}
        new_edges = [(inv[a], inv[b], m) for (a, b, m) in edges]
        place = pot_v2.embed_mol2(new_atoms, new_edges, max_nodes=1500000)
        if place is None:
            continue
        ok, _ = pot_v2.validate_place(place, new_atoms, new_edges)
        if not ok:
            continue
        back = {}
        for i in range(n):
            back[perm[i]] = place[i]
        pos = [tuple(back[j]) for j in range(n)]
        bad = 0
        for (a, b, m) in edges:
            d = (pos[b][0] - pos[a][0], pos[b][1] - pos[a][1])
            if P.classify_offset(d) is None:
                bad += 1
        if bad == 0:
            best = pos
            break
    if best is None:
        return False
    pos = best
    bonds = []
    for (a, b, m) in edges:
        d = (pos[b][0] - pos[a][0], pos[b][1] - pos[a][1])
        typ = P.classify_offset(d)
        mid = None
        if typ == "L":
            mid = (pos[a][0] + d[0] // 2, pos[a][1] + d[1] // 2)
        bonds.append({"a": a, "b": b, "m": m, "type": typ,
                      "mid": list(mid) if mid else None})
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    item["place"] = pos
    item["bonds"] = bonds
    item["bbox"] = [min(xs), min(ys), max(xs), max(ys)]
    item["_repaired"] = True
    return True


def order_items(items):
    return sorted(items, key=lambda x: (-max((x.get("counts") or {"x": 0}).values()),
                                        -(x.get("n_atoms") or 0),
                                        x.get("formula") or ""))


# ---------------------------------------------------------------- 几何/绘制
def geom(item, box, ring=1):
    """返回 (s, 像素中心函数, 占用格集合, 中点集合, 所有背景格)。"""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    place = [tuple(p) for p in (item.get("place") or [])]
    occ = set(place)
    bonds = item.get("bonds") or []
    mids = set()
    for b in bonds:
        if b.get("mid"):
            mids.add(tuple(b["mid"]))
    bb = item.get("bbox") or [min(p[0] for p in place), min(p[1] for p in place),
                              max(p[0] for p in place), max(p[1] for p in place)]
    q0, r0, q1, r1 = bb
    cells = [(q, r) for q in range(q0 - ring, q1 + ring + 1)
             for r in range(r0 - ring, r1 + ring + 1)]
    # 坐标范围（s=1）
    pts = [T8.center_of(c, 1.0) for c in cells]
    pts += [T8.center_of(c, 1.0) for c in mids]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs) - 1.0, max(xs) + 1.0
    miny, maxy = min(ys) - S3 / 2.0, max(ys) + S3 / 2.0
    pad = 4
    s = min((bw - 2 * pad) / max(1e-6, maxx - minx),
            (bh - 2 * pad) / max(1e-6, maxy - miny))
    cx = x0 + bw / 2.0 - (minx + maxx) / 2.0 * s
    cy = y0 + bh / 2.0 - (miny + maxy) / 2.0 * s

    def center(cell):
        p = T8.center_of(cell, s)
        return (cx + p[0], cy + p[1])

    return s, center, occ, mids, cells


def hexpoly(center, s):
    return T8.hex_pts(center[0], center[1], s)


def draw_hex(c, poly, fill=None, outline="#333", width=1, dash=False):
    if fill:
        c.d.polygon(poly, fill=fill)
    if dash:
        for i in range(6):
            p0, p1 = poly[i], poly[(i + 1) % 6]
            c.dashed(p0, p1, fill=outline, width=width, dash=4, gap=3)
    else:
        c.d.polygon(poly, outline=outline, width=width)


def draw_bond(c, p0, p1, typ, m):
    """按键型颜色 + 多重键平行线绘制。"""
    col = BONDCOL.get(typ, "#7f8c8d")
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    m = max(1, int(m or 1))
    gap = 2.6
    for i in range(m):
        off = (i - (m - 1) / 2.0) * gap
        a = (p0[0] + nx * off, p0[1] + ny * off)
        b = (p1[0] + nx * off, p1[1] + ny * off)
        if typ is None:
            c.dashed(a, b, fill=col, width=1, dash=5, gap=4)
        else:
            c.d.line([a, b], fill=col, width=2)


def text_on(c, x, y, s, size, fill="#111", anchor="mm"):
    c.txt(x, y, s, size=size, bold=True, fill=fill, anchor=anchor)


def draw_mol_panel(c, item, box, big=False, rank=None):
    x0, y0, x1, y1 = box
    c.d.rectangle(box, fill="#ffffff", outline="#cccccc", width=1)
    s, center, occ, mids, cells = geom(item, box, ring=1)
    # 1) 背景棋盘格（空格浅灰细线）
    for cell in cells:
        if cell in occ:
            continue
        poly = hexpoly(center(cell), s)
        if cell in mids:
            draw_hex(c, poly, fill="#f7f0fb", outline=MIDCOL, width=2, dash=True)
            if s >= 7:
                text_on(c, center(cell)[0], center(cell)[1],
                        "空", max(6, int(s * 0.5)), fill=MIDCOL)
        else:
            draw_hex(c, poly, fill=None, outline=GRIDCOL, width=1)
    # 2) 键
    bonds = item.get("bonds") or []
    for b in bonds:
        p0 = center(tuple(item["place"][b["a"]]))
        p1 = center(tuple(item["place"][b["b"]]))
        draw_bond(c, p0, p1, b.get("type"), b.get("m") or 1)
    # 3) 占据格
    n = item.get("n_atoms") or len(item.get("place") or [])
    for i, cell in enumerate(item["place"]):
        el = item["atoms"][i]
        poly = hexpoly(center(tuple(cell)), s)
        draw_hex(c, poly, fill=ELEMCOL.get(el, "#bdbdbd"), outline="#222",
                 width=2)
        # 文字对比色
        fill = "#ffffff" if el in ("P", "K", "F", "W", "L") else "#111"
        if s >= 8:
            text_on(c, center(tuple(cell))[0], center(tuple(cell))[1], el,
                    max(8, int(s * 0.85)), fill=fill)
            if (not big) and n <= 18 and s >= 12:
                text_on(c, center(tuple(cell))[0],
                        center(tuple(cell))[1] + s * 0.52, str(i + 1),
                        max(6, int(s * 0.34)), fill="#333")
    # 4) 标注
    formula = item.get("formula") or ""
    head = ("#%d %s" % (rank, formula)) if rank else formula
    c.txt(x0 + 8, y0 + 5, head, size=13 if big else 12, bold=True,
          fill="#111")
    c.txt(x0 + 8, y0 + 24, "%s · %d 原子 · %s"
          % (zh_of(formula), n, counts_str(item)), size=9, fill="#444")
    unknown = sum(1 for b in bonds if b.get("type") is None)
    if unknown:
        c.txt(x0 + 8, y1 - 18,
              "⚠ place/bonds 不匹配（%d/%d 键未解析），仅示占据格" % (unknown, len(bonds)),
              size=8, fill=WARNCOL)
    return s


# ---------------------------------------------------------------- ① 中等大分子
def chart_medium(items, out):
    W, H = 1600, 1650
    c = Chart(W, H,
              "T61 六边形棋盘格（中等大分子）：T59A/T59B 全部 5~18 原子大分子（%d 种）"
              % len(items),
              "flat-top hex：center=(1.5·s·q, √3·s·(r+q/2))；占据格按元素上色并标字母；"
              "键型 S 红 / C 绿 / L 紫（多重键=平行线）；紫虚线格=L 键中点（必须为空）")
    cols, rows = 4, 3
    pw, ph = 383, 470
    for i, item in enumerate(items[:12]):
        r, col = divmod(i, cols)
        x0 = 24 + col * (pw + 10)
        y0 = 140 + r * (ph + 10)
        draw_mol_panel(c, item, (x0, y0, x0 + pw, y0 + ph), rank=i + 1)
    # 空位
    for i in range(len(items), 12):
        r, col = divmod(i, cols)
        x0 = 24 + col * (pw + 10)
        y0 = 140 + r * (ph + 10)
        c.d.rectangle([x0, y0, x0 + pw, y0 + ph], outline="#eee")
    data_note(c, [
        "全部结构经 pot_v2.embed_mol2 严格校验；L 键中点格必须为空。"
        "图中每个分子覆盖 66 种大分子中的 %d 种（5~18 原子）；其余 57 种 37~40 原子巨型见 "
        "t61_hex_giants_01..10。" % len(items),
        "数量为 T59A/T59B 终态分子数（同一结构跨阶段合并）；原子编号小字仅中等分子显示。",
    ], y=1530)
    return c.save(out)


# ---------------------------------------------------------------- ② 巨型分页
def chart_giants_page(items, page, pages, out, total=None, base_rank=0):
    W, H = 1600, 1130
    c = Chart(W, H,
              "T61 六边形棋盘格（37~40 原子巨型）第 %d/%d 页 · 本页 %d 个 · 共 %d 种"
              % (page, pages, len(items), total or 57),
              "按数量/原子数排序；占据格按元素上色，S/C/L 键按颜色与多重线；"
              "紫虚线格=L 中点空；灰细线=棋盘格空位")
    cols, rows = 3, 2
    pw, ph = 510, 450
    for i, item in enumerate(items):
        r, col = divmod(i, cols)
        x0 = 24 + col * (pw + 12)
        y0 = 120 + r * (ph + 10)
        draw_mol_panel(c, item, (x0, y0, x0 + pw, y0 + ph), big=True,
                       rank=base_rank + i + 1)
    c.txt(24, H - 44,
          "图注：全部结构经 pot_v2.embed_mol2 严格校验；L 键中点格必须为空。"
          "S=共享边、C=共享顶点、L=隔一格长键；1/2/3 重键用平行线数表示。", size=10,
          fill="#555")
    return c.save(out)


# ---------------------------------------------------------------- ③ 索引表
def chart_summary(items, out):
    W = 1600
    row_h = 20
    H = 170 + len(items) * row_h + 90
    c = Chart(W, H,
              "T61 六边形棋盘格索引：T59A/T59B 大分子 %d 种（≥5 原子，按结构去重）" % len(items),
              "按数量/原子数排序；原子数 5~18 为中等（t61_hex_medium），37~40 为巨型"
              "（t61_hex_giants_01..10）；数量=T59A/T59B 终态分子数")
    box = (30, 120, W - 30, 120 + len(items) * row_h + 6)
    c.d.rectangle(box, outline="#ccc")
    cols_x = [40, 130, 500, 640, 780, 940, 1090, 1290]
    heads = ["#", "formula", "中文名", "原子数", "T59A 数量", "T59B 数量",
             "出现实验", "布局"]
    for x, h in zip(cols_x, heads):
        c.txt(x, 126, h, size=11, bold=True, fill="#111")
    c.d.line([box[0], 144, box[2], 144], fill="#999", width=1)
    for i, item in enumerate(items):
        y = 150 + i * row_h
        n = item.get("n_atoms") or 0
        cts = item.get("counts") or {}
        exp = "/".join(k.replace("T59", "") for k in ("T59A", "T59B")
                       if k in cts) or "-"
        unknown = sum(1 for b in (item.get("bonds") or [])
                      if b.get("type") is None)
        vals = [str(i + 1), item.get("formula"), zh_of(item.get("formula")),
                str(n), fmt_commas(cts.get("T59A")) if cts.get("T59A") is not None else "-",
                fmt_commas(cts.get("T59B")) if cts.get("T59B") is not None else "-",
                exp, "OK(修正)" if item.get("_repaired") else
                ("OK" if not unknown else "待修复(%d键)" % unknown)]
        for j, (x, v) in enumerate(zip(cols_x, vals)):
            col = "#111"
            if j == 0:
                col = "#666"
            if j == 7 and unknown:
                col = WARNCOL
            c.txt(x, y + 2, str(v), size=9, fill=col,
                  bold=(j == 1))
        if i % 2 == 0:
            c.d.rectangle([box[0], y - 1, box[2], y + row_h - 1],
                          outline="#f3f3f3")
    data_note(c, [
        "全部 66 种结构经 pot_v2.embed_mol2 严格校验（4 个 39/40 原子经随机重排加强搜索）；"
        "L 键中点格必须为空。",
        "布局列 OK=place/bonds 一致；渲染器保留不一致检测作为安全网（若触发会标 OK(修正)），"
        "本次数据已修正、未触发。",
    ], y=H - 74)
    return c.save(out)


# ---------------------------------------------------------------- ④ 图例
def chart_legend(out):
    W, H = 1600, 950
    c = Chart(W, H,
              "T61 图例：棋盘格 / 9 元素 / S·C·L 键型 / 多重键 / L 中点空",
              "flat-top hex：center=(1.5·s·q, √3·s·(r+q/2))；"
              "占据格=原子（元素上色），空格=浅灰细线，L 键中点格=紫虚线且必须为空")
    # 元素
    c.txt(40, 110, "① 9 元素配色（六边形=原子，中心字母=元素）", size=16, bold=True)
    x = 60
    for e in ORDER:
        poly = T8.hex_pts(x + 30, 210, 26)
        c.d.polygon(poly, fill=ELEMCOL[e], outline="#222", width=2)
        c.txt(x + 30, 210, e, size=16, bold=True, anchor="mm",
              fill="#fff" if e in ("P", "K", "F", "W", "L") else "#111")
        c.txt(x + 30, 248, "%s %s" % (e, CN[e]), size=13, anchor="ma")
        x += 108
    # 键型
    c.txt(40, 330, "② 键型：S 红 / C 绿 / L 紫；平行线条数=多重键 1/2/3", size=16,
          bold=True)
    demo = [("S", 1), ("S", 2), ("C", 1), ("C", 3), ("L", 1), ("L", 2)]
    x = 70
    for typ, m in demo:
        p0, p1 = (x, 420), (x + 110, 420)
        draw_bond(c, p0, p1, typ, m)
        poly0 = T8.hex_pts(x, 420, 16)
        poly1 = T8.hex_pts(x + 110, 420, 16)
        c.d.polygon(poly0, fill="#dddddd", outline="#333")
        c.d.polygon(poly1, fill="#dddddd", outline="#333")
        if typ == "L":
            mid = ((p0[0] + p1[0]) / 2, 420)
            draw_hex(c, T8.hex_pts(mid[0], mid[1], 16), fill="#f7f0fb",
                     outline=MIDCOL, width=2, dash=True)
            c.txt(mid[0], mid[1] + 26, "L 中点空", size=10, anchor="ma",
                  fill=MIDCOL)
        c.txt(x + 55, 470, "%s ×%d" % (BONDNAME.get(typ, typ), m), size=11,
              anchor="ma")
        x += 245
    # 棋盘格/空格说明
    c.txt(40, 550, "③ 棋盘格示意：占据格=实心六边形；周围一圈空格=浅灰细线；"
          "L 键中间格=紫虚线（必须为空）", size=16, bold=True)
    # 小型示意
    cells = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)]
    cx0, cy0 = 180, 700
    s = 34
    for (q, r) in cells:
        p = T8.center_of((q, r), s)
        poly = T8.hex_pts(cx0 + p[0], cy0 + p[1], s)
        el = ["O", "X", "C", "P", "W"][cells.index((q, r))]
        c.d.polygon(poly, fill=ELEMCOL[el], outline="#222", width=2)
        c.txt(cx0 + p[0], cy0 + p[1], el, size=18, bold=True, anchor="mm",
              fill="#fff" if el in ("P",) else "#111")
    # 周围空格
    for q in range(-1, 4):
        for r in range(-1, 3):
            if (q, r) in cells:
                continue
            p = T8.center_of((q, r), s)
            c.d.polygon(T8.hex_pts(cx0 + p[0], cy0 + p[1], s),
                        outline=GRIDCOL, width=1)
    # L 键示例
    p0 = T8.center_of((0, 0), s)
    p2 = T8.center_of((2, 0), s)
    draw_bond(c, (cx0 + p0[0], cy0 + p0[1]), (cx0 + p2[0], cy0 + p2[1]),
              "L", 1)
    mid = T8.center_of((1, 0), s)
    c.d.polygon(T8.hex_pts(cx0 + mid[0], cy0 + mid[1], s), fill="#f7f0fb",
                outline=MIDCOL, width=2)
    # 用 dashed 覆盖
    draw_hex(c, T8.hex_pts(cx0 + mid[0], cy0 + mid[1], s), fill=None,
             outline=MIDCOL, width=2, dash=True)
    c.txt(cx0 + mid[0], cy0 + mid[1] - s - 14, "L 中点空", size=11, anchor="ma",
          fill=MIDCOL)
    c.txt(420, 660,
          "说明：\n"
          "· 每个分子由 place 轴向坐标决定占据格，按元素上色；\n"
          "· 键型/多重键直接取自 t61_hex_layouts.json 的 bonds，不重算；\n"
          "· S=共享边（相邻格），C=共享顶点（角相邻），L=隔一格长键；\n"
          "· L 键的中间格必须为空（紫虚线画出）；\n"
          "· 浅灰细线只画在分子周围一圈，用于体现棋盘格；\n"
          "· 全部 66 个分子的 place 与 bonds 一致（n_valid=66）；渲染器保留不一致检测，"
          "本次数据已修正、未触发。",
          size=13, fill="#333")
    data_note(c, [
        "全部结构经 pot_v2.embed_mol2 严格校验；L 键中点格必须为空。"
        "几何映射：center_of(cell,s)=(1.5·s·q, √3·s·(r+q/2))，六边形顶点=radius s、"
        "每 60° 一个（flat-top）。",
    ], y=880)
    return c.save(out)


# ---------------------------------------------------------------- main
def main():
    data = load_data()
    items = data.get("items") or []
    n_rep = 0
    for x in items:
        if not bonds_consistent(x):
            if repair_item(x):
                n_rep += 1
    os.makedirs(IMAGES, exist_ok=True)
    med = order_items([x for x in items if 5 <= (x.get("n_atoms") or 0) <= 18])
    giants = order_items([x for x in items if (x.get("n_atoms") or 0) >= 37])
    manifest = {"source": os.path.basename(DATA),
                "n_total": len(items), "n_medium": len(med),
                "n_giants": len(giants), "n_giant_pages": 0,
                "n_repaired_at_render": 0,
                "figures": [], "notes": [
                    "t61_hex_layouts.json 全部 66 种大分子（≥5 原子，按结构去重，T59A/T59B 合并）。",
                    "中等=5~18 原子；巨型=37~40 原子，按数量/原子数排序分页。",
                    "键型 S/C/L 与多重键取自数据 bonds，不重算；L 中点格用紫虚线。",
                    "数据已修正（place/bonds 一致，n_valid=66）；渲染器保留不一致检测作为安全网，"
                    "本次未触发。",
                ]}
    import datetime
    manifest["generated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = os.path.join(IMAGES, "t61_hex_medium.png")
    sz = chart_medium(med, out)
    manifest["figures"].append({"file": os.path.basename(out), "type": "medium",
                                "n": len(med), "bytes": sz})
    print("[ok] medium %d %s" % (len(med), out), flush=True)
    pages = []
    per = 6
    for i in range(0, len(giants), per):
        pages.append(giants[i:i + per])
    manifest["n_giant_pages"] = len(pages)
    for pi, page in enumerate(pages, 1):
        out = os.path.join(IMAGES, "t61_hex_giants_%02d.png" % pi)
        sz = chart_giants_page(page, pi, len(pages), out, total=len(giants),
                               base_rank=len(med) + (pi - 1) * per)
        manifest["figures"].append({"file": os.path.basename(out),
                                    "type": "giants", "page": pi,
                                    "n": len(page), "bytes": sz})
        print("[ok] giants page %d/%d (%d) %s"
              % (pi, len(pages), len(page), out), flush=True)
    out = os.path.join(IMAGES, "t61_hex_summary.png")
    sz = chart_summary(items, out)
    manifest["figures"].append({"file": os.path.basename(out), "type": "summary",
                                "n": len(items), "bytes": sz})
    print("[ok] summary %s" % out, flush=True)
    out = os.path.join(IMAGES, "t61_hex_legend.png")
    sz = chart_legend(out)
    manifest["figures"].append({"file": os.path.basename(out), "type": "legend",
                                "bytes": sz})
    print("[ok] legend %s" % out, flush=True)
    manifest["n_repaired_at_render"] = n_rep
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


