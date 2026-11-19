# -*- coding: utf-8 -*-
"""t78_products.py —— T78 最终产物的「分层图」：每层有哪些物质、多少、什么形态。

输入：t78_main_result.json（t=239 快照 + final_composition）+ t4_catalog_all_validated.json
      （取分子结构 atoms/edges/place，六边形格子坐标用于画形态）
输出：images/t78_products.png（每层一张卡片：组成条 + 三轴构成 + 代表物结构图）
      t78_products.json（图中数字的结构化版本，便于复核）

层：按世界高度 y∈[0,4000) 等分 5 层（顶层 3200-4000、中上层 2400-3200、中层 1600-2400、
    中下层 800-1600、底层 0-800）。

用法：python t78_products.py
"""
import io
import json
import math
import os
from collections import Counter, defaultdict

from PIL import Image, ImageDraw, ImageFont

from alchemy.core.elements import classify_offset

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

RESULT = os.path.join(BASE, "t78_main_result.json")
CATALOG = os.path.join(BASE, "t4_catalog_all_validated.json")
OUT_PNG = os.path.join(BASE, "images", "t78_products.png")
OUT_MATRIX = os.path.join(BASE, "images", "t78_products_matrix.png")
OUT_JSON = os.path.join(BASE, "t78_products.json")

W_IMG, H_IMG = 2400, 1886
N_TOP = 8          # 每层展示的物种条数
N_SKETCH = 4       # 每层结构图数量

LAYERS = [
    ("顶层", 3200, 4000),
    ("中上层", 2400, 3200),
    ("中层", 1600, 2400),
    ("中下层", 800, 1600),
    ("底层", 0, 800),
]
LAYER_ACCENT = {
    "顶层": (44, 127, 184),
    "中上层": (92, 160, 190),
    "中层": (150, 150, 150),
    "中下层": (196, 150, 96),
    "底层": (150, 90, 60),
}
ELEM_COLORS = {
    "O": (214, 39, 40), "K": (255, 127, 14), "P": (188, 189, 34),   # 概念族（三价）
    "X": (31, 119, 180), "W": (23, 190, 207), "A": (44, 160, 44),   # 物质族（二价）
    "F": (227, 119, 194), "L": (148, 103, 189), "C": (140, 86, 75), # 能量族（一价）
}
TIER_COLORS = {
    "mass": {"轻": (44, 160, 44), "中": (31, 119, 180), "重": (214, 39, 40)},
    "state": {"气": (158, 202, 225), "液": (66, 146, 198), "固": (107, 76, 59)},
    "temp": {"冷": (69, 117, 180), "温": (189, 189, 189), "热": (215, 48, 39)},
}
BAR_COL = (76, 120, 168)
BAR_TOP = (228, 87, 86)
GREY = (90, 90, 90)
LIGHT = (120, 120, 120)


def fnt(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def text_width(d, s, font):
    return d.textlength(s, font=font)


def load_json(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def formula_atoms(formula):
    """CF -> ['C','F']（只用于没有目录结构的纯文本场景）。"""
    out = []
    for ch in formula:
        out.append(ch)
    return out


# ---------------------------------------------------------------- 数据准备
def build_data():
    res = load_json(RESULT)
    snap = res["snapshots"][-1]
    pts = [[p[0], min(max(p[1], 0.0), 3999.999), p[2]] for p in snap["points"]]
    final_comp = res["final_composition"]      # formula -> {count, atoms, mass, state, temperature, cell}
    cat = {r["formula"]: r for r in load_json(CATALOG)}

    # 每层：总数 / 物种计数 / 三轴构成 / 原子数分布
    layer_stats = {}
    for name, lo, hi in LAYERS:
        sub = [p for p in pts if lo <= p[1] < hi]
        cc = Counter(p[2] for p in sub)
        tiers = {"mass": Counter(), "state": Counter(), "temp": Counter()}
        for f, n in cc.items():
            cell = final_comp[f]["cell"]
            m, s, t = cell.split("·")
            tiers["mass"][m] += n
            tiers["state"][s] += n
            tiers["temp"][t] += n
        natoms = [final_comp[f]["atoms"] for f in cc.elements() for _ in range(0)]
        atom_sum = sum(final_comp[f]["atoms"] * n for f, n in cc.items())
        layer_stats[name] = {
            "y": [lo, hi],
            "N": len(sub),
            "species": len(cc),
            "mean_atoms": (atom_sum / len(sub)) if sub else 0.0,
            "tiers": {k: dict(v) for k, v in tiers.items()},
            "counts": dict(cc),
        }

    # 物种在哪几层出现
    presence = defaultdict(set)
    for name, lo, hi in LAYERS:
        for f in set(p[2] for p in pts if lo <= p[1] < hi):
            presence[f].add(name)
    overlap = Counter(len(v) for v in presence.values())
    all_layers = [f for f, v in presence.items() if len(v) == len(LAYERS)]

    # 每层的代表物：优先本层优势种（全局归属层 = 该物种出现最多的层），其余取本层独有的高排位物种
    dom_layer = {}
    for f, lay in presence.items():
        # 哪个层里这个物种最多
        best, best_n = None, -1
        for name, lo, hi in LAYERS:
            n = layer_stats[name]["counts"].get(f, 0)
            if n > best_n:
                best, best_n = name, n
        dom_layer[f] = best

    picks = {}
    used = set()
    for name, lo, hi in LAYERS:
        counts = layer_stats[name]["counts"]
        ranked = [f for f, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
        chosen = []
        if ranked:                                      # 1) 本层第一大物种
            chosen.append(ranked[0])
            used.add(ranked[0])
        big = sorted([f for f in ranked[:20] if f not in used and cat.get(f, {}).get("place")],
                     key=lambda f: (-(cat[f].get("natoms") or len(cat[f]["atoms"])), -counts[f]))
        if big:                                         # 2) 至少一张较大分子（形态更有代表性）
            chosen.append(big[0])
            used.add(big[0])
        for f in ranked:                                # 3) 本层优势种
            if len(chosen) >= N_SKETCH:
                break
            if dom_layer.get(f) == name and f not in used:
                chosen.append(f)
                used.add(f)
        for f in ranked:                                # 4) 层内其余高排位
            if len(chosen) >= N_SKETCH:
                break
            if f not in used:
                chosen.append(f)
                used.add(f)
        for f in ranked:                                # 5) 兜底（允许重复）
            if len(chosen) >= N_SKETCH:
                break
            if f not in chosen:
                chosen.append(f)
        picks[name] = [f for f in chosen if cat.get(f, {}).get("place")]

    summary = {
        "N": len(pts),
        "species": len(presence),
        "layers": {k: {kk: vv for kk, vv in v.items() if kk != "counts"} for k, v in layer_stats.items()},
        "overlap": {"only_1": overlap.get(1, 0), "n2": overlap.get(2, 0), "n3": overlap.get(3, 0),
                    "n4": overlap.get(4, 0), "n5": overlap.get(5, 0), "all_layers": all_layers},
        "picks": picks,
    }
    return res, pts, final_comp, cat, layer_stats, picks, summary


# ---------------------------------------------------------------- 绘图工具
def draw_sketch(d, box, formula, rec, atom_r_scale=1.0):
    """在 box=(x0,y0,x1,y1) 内画分子结构：六边形格子 place -> 像素。"""
    x0, y0, x1, y1 = box
    atoms = rec["atoms"]
    edges = rec["edges"]
    place = rec["place"]
    n = len(atoms)
    coords = {}
    for i in range(n):
        q, r = place[str(i)]
        coords[i] = (math.sqrt(3.0) * (q + r / 2.0), 1.5 * r)
    xs = [p[0] for p in coords.values()]
    ys = [p[1] for p in coords.values()]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    pad = 16
    bw = max(1.0, (x1 - x0) - 2 * pad)
    bh = max(1.0, (y1 - y0) - 2 * pad)
    sx = bw / span_x if span_x > 1e-9 else 1e9
    sy = bh / span_y if span_y > 1e-9 else 1e9
    s = min(sx, sy)
    if s > 1e8:
        s = 1.0
    # 单原子/正多边形时 span 可能为 0：给一个合适的 s
    if n <= 2:
        s = min(bw, bh) / 2.2
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    mid_x = (max(xs) + min(xs)) / 2.0
    mid_y = (max(ys) + min(ys)) / 2.0
    pts = {i: (cx + (coords[i][0] - mid_x) * s, cy + (coords[i][1] - mid_y) * s)
           for i in range(n)}
    r_atom = max(5.5, min(11.0, 13.0 - 0.55 * n)) * atom_r_scale

    # 先画键
    for (i, j, mult) in edges:
        (ax, ay), (bx, by) = pts[i], pts[j]
        dq = place[str(j)][0] - place[str(i)][0]
        dr = place[str(j)][1] - place[str(i)][1]
        try:
            btype = classify_offset((dq, dr))
        except Exception:
            btype = "S"
        if btype == "S":
            d.line([ax, ay, bx, by], fill=(70, 70, 70), width=3)
        elif btype == "C":
            # 虚线
            seg = math.hypot(bx - ax, by - ay)
            step = 9.0
            t = 0.0
            while t < seg:
                t2 = min(seg, t + 5.0)
                d.line([ax + (bx - ax) * t / seg, ay + (by - ay) * t / seg,
                        ax + (bx - ax) * t2 / seg, ay + (by - ay) * t2 / seg],
                       fill=(70, 70, 70), width=3)
                t += step
        else:
            # 点线（L 键，中点必为空）
            seg = math.hypot(bx - ax, by - ay)
            step = 8.0
            t = 4.0
            while t < seg - 2:
                x = ax + (bx - ax) * t / seg
                y = ay + (by - ay) * t / seg
                d.ellipse([x - 2.0, y - 2.0, x + 2.0, y + 2.0], fill=(70, 70, 70))
                t += step

    # 再画原子
    for i in range(n):
        x, y = pts[i]
        col = ELEM_COLORS.get(atoms[i], (120, 120, 120))
        d.ellipse([x - r_atom, y - r_atom, x + r_atom, y + r_atom],
                  fill=col, outline=(40, 40, 40), width=2)
        if r_atom >= 8.0:
            d.text((x - 4.2, y - 6.0), atoms[i], font=fnt(11, True), fill=(255, 255, 255))


def draw_stacked_bar(d, x, y, w, h, counts, order, colors, label=False, fs=12):
    total = sum(counts.get(k, 0) for k in order) or 1
    cx = x
    for k in order:
        n = counts.get(k, 0)
        if n <= 0:
            continue
        seg = w * n / total
        d.rectangle([cx, y, cx + seg, y + h], fill=colors[k], outline=(255, 255, 255), width=1)
        if label and seg >= 26 and n / total >= 0.04:
            d.text((cx + seg / 2 - 6, y + (h - 14) / 2), "%d" % round(100 * n / total),
                   font=fnt(fs - 1), fill=(255, 255, 255))
        cx += seg
    return total


# ---------------------------------------------------------------- 主绘图
def render():
    res, pts, final_comp, cat, layer_stats, picks, summary = build_data()

    img = Image.new("RGB", (W_IMG, H_IMG), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # 标题
    d.text((36, 22), "T78 最终产物分层图：每一层里有哪些物质、有多少、什么形态",
           font=fnt(40, True), fill=(20, 20, 20))
    sub = ("main 臂 · t=239 min · 共 %d 分子 / %d 种分子式（607 种中 %d 种只出现在 1 层，%d 种跨 5 层）"
           " · 世界高 4000，按高度等分 5 层" % (summary["N"], summary["species"],
                                     summary["overlap"]["only_1"], summary["overlap"]["n5"]))
    d.text((36, 78), sub, font=fnt(20), fill=(70, 70, 70))

    row_y0 = 128
    row_h = 320
    left_x0, left_x1 = 28, 1180
    right_x0, right_x1 = 1200, 2372

    for idx, (name, lo, hi) in enumerate(LAYERS):
        st = layer_stats[name]
        y0 = row_y0 + idx * row_h
        y1 = y0 + row_h - 12
        # 行底色
        bg = (250, 250, 252) if idx % 2 == 0 else (244, 246, 249)
        d.rectangle([left_x0, y0, right_x1, y1], fill=bg, outline=(205, 208, 212), width=1)
        d.rectangle([left_x0, y0, left_x0 + 8, y1], fill=LAYER_ACCENT[name])

        # 层头
        head = "%s（y=%d–%d）  N=%d 分子 · %d 种 · 平均 %.1f 原子/分子" % (
            name, lo, hi, st["N"], st["species"], st["mean_atoms"])
        d.text((left_x0 + 18, y0 + 8), head, font=fnt(21, True), fill=(30, 30, 30))

        # ---------------- 左：组成条（该层内占比）
        counts = st["counts"]
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top = ranked[:N_TOP]
        rest = ranked[N_TOP:]
        total = st["N"] or 1
        bar_x = left_x0 + 150
        bar_max = 430
        ly = y0 + 44
        for k, (f, n) in enumerate(top):
            share = n / total
            d.text((left_x0 + 18, ly + 1), f, font=fnt(15, True), fill=(30, 30, 30))
            bw = max(2.0, bar_max * share)
            col = BAR_TOP if k == 0 else BAR_COL
            d.rectangle([bar_x, ly + 1, bar_x + bw, ly + 17], fill=col)
            lab = "%d 个 · %.1f%%" % (n, 100 * share)
            d.text((bar_x + bw + 8, ly), lab, font=fnt(14), fill=(60, 60, 60))
            ly += 21
        if rest:
            rn = sum(n for _, n in rest)
            d.text((left_x0 + 18, ly + 1), "其他 %d 种" % len(rest), font=fnt(14), fill=(110, 110, 110))
            bw = max(2.0, bar_max * rn / total)
            d.rectangle([bar_x, ly + 1, bar_x + bw, ly + 17], fill=(185, 190, 195))
            d.text((bar_x + bw + 8, ly), "%d 个 · %.1f%%" % (rn, 100 * rn / total),
                   font=fnt(14), fill=(110, 110, 110))

        # ---------------- 左中：三轴构成（质量/物态/温度）
        tx0 = left_x0 + 790
        tw = left_x1 - 40 - tx0
        ty = y0 + 48
        for axis, order, lab in (("mass", ("轻", "中", "重"), "质量"),
                                 ("state", ("气", "液", "固"), "物态"),
                                 ("temp", ("冷", "温", "热"), "温度")):
            d.text((tx0, ty + 2), lab, font=fnt(14), fill=(70, 70, 70))
            draw_stacked_bar(d, tx0 + 40, ty, tw - 40, 20, st["tiers"][axis], order,
                             TIER_COLORS[axis], label=True)
            ty += 34
        d.text((tx0, ty + 2), "（条内数字 = 该层分子百分比）", font=fnt(12), fill=(130, 130, 130))

        # ---------------- 右：代表物形态
        sx0 = right_x0 + 14
        sky0 = y0 + 40
        box_w = (right_x1 - 18 - sx0) / N_SKETCH
        box_h = 232
        for k, f in enumerate(picks[name]):
            rec = cat[f]
            bx0 = sx0 + k * box_w
            box = (bx0 + 6, sky0, bx0 + box_w - 6, sky0 + box_h - 60)
            d.rectangle([box[0], box[1], box[2], box[3]], fill=(255, 255, 255), outline=(215, 218, 222))
            draw_sketch(d, box, f, rec)
            cnt = counts.get(f, 0)
            cell = final_comp[f]["cell"]
            d.text((bx0 + 10, sky0 + box_h - 54), "%s  ×%d" % (f, cnt), font=fnt(19, True), fill=(30, 30, 30))
            d.text((bx0 + 10, sky0 + box_h - 28),
                   "%d 原子 · %s" % (rec.get("natoms", len(rec["atoms"])), cell.replace("·", " · ")),
                   font=fnt(14), fill=(80, 80, 80))

    # ---------------- 页脚：图例（两行）
    fy = row_y0 + len(LAYERS) * row_h + 6
    d.line([28, fy, W_IMG - 28, fy], fill=(200, 200, 200), width=1)
    fy += 10
    d.text((32, fy), "元素配色：", font=fnt(17, True), fill=(30, 30, 30))
    cx = 150
    for fam, elems in (("概念族(三价)", ("O", "K", "P")),
                       ("物质族(二价)", ("X", "W", "A")),
                       ("能量族(一价)", ("F", "L", "C"))):
        d.text((cx, fy + 1), fam, font=fnt(15), fill=(90, 90, 90))
        cx += 118
        for e in elems:
            d.ellipse([cx, fy, cx + 20, fy + 20], fill=ELEM_COLORS[e], outline=(40, 40, 40))
            d.text((cx + 5, fy + 1), e, font=fnt(13, True), fill=(255, 255, 255))
            cx += 32
        cx += 26
    d.text((cx, fy + 1), "键型：", font=fnt(17, True), fill=(30, 30, 30))
    cx += 62
    d.line([cx, fy + 10, cx + 46, fy + 10], fill=(70, 70, 70), width=3)
    d.text((cx + 52, fy), "S 短键", font=fnt(15), fill=(70, 70, 70))
    cx += 130
    for t0 in range(0, 42, 9):
        d.line([cx + t0, fy + 10, cx + t0 + 5, fy + 10], fill=(70, 70, 70), width=3)
    d.text((cx + 52, fy), "C 角键", font=fnt(15), fill=(70, 70, 70))
    cx += 130
    for t0 in range(4, 42, 8):
        d.ellipse([cx + t0 - 2, fy + 8, cx + t0 + 2, fy + 12], fill=(70, 70, 70))
    d.text((cx + 52, fy), "L 长键", font=fnt(15), fill=(70, 70, 70))

    fy2 = fy + 30
    d.text((32, fy2), "三轴档配色：", font=fnt(15, True), fill=(30, 30, 30))
    cx = 158
    for axis, order, lab in (("mass", ("轻", "中", "重"), "质量"),
                             ("state", ("气", "液", "固"), "物态"),
                             ("temp", ("冷", "温", "热"), "温度")):
        d.text((cx, fy2 + 1), lab, font=fnt(14), fill=(90, 90, 90))
        cx += 42
        for k in order:
            d.rectangle([cx, fy2 + 2, cx + 18, fy2 + 16], fill=TIER_COLORS[axis][k], outline=(120, 120, 120))
            d.text((cx + 23, fy2), k, font=fnt(14), fill=(60, 60, 60))
            cx += 46
        cx += 22
    d.text((cx, fy2 + 1), "条长 = 该层内分子占比；红条 = 该层第一大物种；每层完整前 14 名见 t78_products.json",
           font=fnt(14), fill=(110, 110, 110))

    img.save(OUT_PNG)
    print("saved", OUT_PNG, img.size)
    matrix = render_matrix(layer_stats, final_comp, cat)

    # 结构化结果
    out = {
        "source": "t78_main_result.json snapshot t=239",
        "layers": [],
        "overlap": summary["overlap"],
        "matrix": matrix,
    }
    for name, lo, hi in LAYERS:
        st = layer_stats[name]
        ranked = sorted(st["counts"].items(), key=lambda kv: (-kv[1], kv[0]))
        out["layers"].append({
            "layer": name,
            "y": [lo, hi],
            "N": st["N"],
            "species": st["species"],
            "mean_atoms": round(st["mean_atoms"], 2),
            "tiers": st["tiers"],
            "top": [{"formula": f, "count": n, "share": round(n / st["N"], 4),
                     "cell": final_comp[f]["cell"], "atoms": final_comp[f]["atoms"]}
                    for f, n in ranked[:14]],
            "sketches": [{"formula": f, "count": st["counts"][f],
                          "atoms": cat[f].get("natoms", len(cat[f]["atoms"])),
                          "cell": final_comp[f]["cell"]} for f in picks[name]],
        })
    with io.open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("saved", OUT_JSON)
    return summary


def render_matrix(layer_stats, final_comp, cat):
    """物种 × 层 分布矩阵：行 = 每层前 5 名的并集，列 = 5 层。"""
    names = [l[0] for l in LAYERS]
    rows, seen = [], set()
    for name in names:
        counts = layer_stats[name]["counts"]
        for f, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
            if f not in seen:
                seen.add(f)
                rows.append(f)

    def order_key(f):
        for i, name in enumerate(names):
            n = layer_stats[name]["counts"].get(f, 0)
            if n:
                return (i, -n, f)
        return (9, 0, f)

    rows.sort(key=order_key)

    x0 = 36
    col_label = 330
    col_layer = 150
    col_total = 110
    col_cell = 210
    col_atom = 100
    grid_x0 = x0 + col_label
    W = grid_x0 + len(LAYERS) * col_layer + col_total + col_cell + col_atom + x0
    header_top = 126
    header_h = 64
    row_h = 44
    H = header_top + header_h + len(rows) * row_h + 150

    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((36, 22), "T78 产物物种 × 层 分布矩阵：哪些物质出现在哪一层、各有多少",
           font=fnt(38, True), fill=(20, 20, 20))
    d.text((36, 78), "行 = 每层前 5 名的并集（共 %d 种）；格内数字 = 该层该物种分子数；★ = 五层都有；"
                     "颜色越深 = 数量越多（对数色阶）" % len(rows),
           font=fnt(19), fill=(70, 70, 70))

    max_n = max(1, max(layer_stats[name]["counts"].get(f, 0) for name in names for f in rows))

    def cell_color(n):
        if n <= 0:
            return (250, 250, 250)
        t = math.log1p(n) / math.log1p(max_n)
        return (int(255 - t * 224), int(255 - t * 177), int(255 - t * 115))

    # 表头
    d.rectangle([x0, header_top, W - x0, header_top + header_h], fill=(238, 241, 245))
    d.line([x0, header_top + header_h, W - x0, header_top + header_h], fill=(160, 165, 172), width=2)
    d.text((x0 + 12, header_top + 20), "物种（分子式）", font=fnt(18, True), fill=(30, 30, 30))
    for i, name in enumerate(names):
        cx = grid_x0 + i * col_layer
        d.text((cx + 14, header_top + 8), name, font=fnt(17, True), fill=(30, 30, 30))
        d.text((cx + 14, header_top + 36), "N=%d · %d 种" % (layer_stats[name]["N"], layer_stats[name]["species"]),
               font=fnt(13), fill=(90, 90, 90))
    cx = grid_x0 + len(LAYERS) * col_layer
    d.text((cx + 14, header_top + 20), "合计", font=fnt(17, True), fill=(30, 30, 30))
    d.text((cx + col_total + 12, header_top + 20), "三轴档", font=fnt(17, True), fill=(30, 30, 30))
    d.text((cx + col_total + col_cell + 14, header_top + 20), "原子数", font=fnt(17, True), fill=(30, 30, 30))

    # 数据行
    for r, f in enumerate(rows):
        ry = header_top + header_h + r * row_h
        all5 = all(layer_stats[name]["counts"].get(f, 0) > 0 for name in names)
        bg = (255, 250, 236) if all5 else ((250, 250, 252) if r % 2 == 0 else (255, 255, 255))
        d.rectangle([x0, ry, W - x0, ry + row_h], fill=bg)
        d.line([x0, ry, W - x0, ry], fill=(228, 230, 234), width=1)
        mark = "★ " if all5 else ""
        d.text((x0 + 12, ry + 10), mark + f, font=fnt(18, all5), fill=(30, 30, 30))
        total = 0
        for i, name in enumerate(names):
            n = layer_stats[name]["counts"].get(f, 0)
            total += n
            cx = grid_x0 + i * col_layer
            d.rectangle([cx + 2, ry + 2, cx + col_layer - 2, ry + row_h - 2], fill=cell_color(n))
            if n:
                dark = math.log1p(n) / math.log1p(max_n) > 0.55
                txt = str(n)
                tw = text_width(d, txt, fnt(16, True))
                d.text((cx + (col_layer - tw) / 2, ry + 11), txt, font=fnt(16, True),
                       fill=(255, 255, 255) if dark else (25, 45, 70))
            else:
                d.text((cx + col_layer / 2 - 4, ry + 12), "·", font=fnt(16), fill=(205, 205, 205))
        cx = grid_x0 + len(LAYERS) * col_layer
        d.text((cx + 16, ry + 10), str(total), font=fnt(17, True), fill=(30, 30, 30))
        d.text((cx + col_total + 12, ry + 11), final_comp[f]["cell"].replace("·", " · "), font=fnt(14), fill=(70, 70, 70))
        d.text((cx + col_total + col_cell + 14, ry + 11), str(cat[f].get("natoms", len(cat[f]["atoms"]))),
               font=fnt(14), fill=(70, 70, 70))

    # 合计行
    ry = header_top + header_h + len(rows) * row_h
    d.rectangle([x0, ry, W - x0, ry + row_h], fill=(232, 236, 240))
    d.text((x0 + 12, ry + 11), "合计", font=fnt(17, True), fill=(30, 30, 30))
    for i, name in enumerate(names):
        cx = grid_x0 + i * col_layer
        d.text((cx + 14, ry + 11), str(layer_stats[name]["N"]), font=fnt(16, True), fill=(30, 30, 30))
    d.text((grid_x0 + len(LAYERS) * col_layer + 16, ry + 11), str(sum(layer_stats[n]["N"] for n in names)),
           font=fnt(17, True), fill=(30, 30, 30))

    # 页脚
    fy = ry + row_h + 18
    d.line([x0, fy, W - x0, fy], fill=(200, 200, 200), width=1)
    cf_n = layer_stats["顶层"]["counts"].get("CF", 0)
    ok_n = layer_stats["底层"]["counts"].get("OK", 0)
    d.text((x0, fy + 10),
           "读法示例：顶层有 %d 个 CF 分子（占顶层 %.0f%%）；OK 与 PK 是唯二在五层都出现的物种；"
           "底层以 OK（重·气·冷，%d 个）为主。完整每层前 14 名见 t78_products.json。"
           % (cf_n, 100.0 * cf_n / max(1, layer_stats["顶层"]["N"]), ok_n),
           font=fnt(15), fill=(110, 110, 110))
    img.save(OUT_MATRIX)
    print("saved", OUT_MATRIX, img.size)

    return {
        "layers": names,
        "rows": [{"formula": f,
                  "counts": {name: layer_stats[name]["counts"].get(f, 0) for name in names},
                  "cell": final_comp[f]["cell"],
                  "atoms": cat[f].get("natoms", len(cat[f]["atoms"]))} for f in rows],
    }


if __name__ == "__main__":
    s = render()
    print(json.dumps(s, ensure_ascii=False, indent=1))
