# -*- coding: utf-8 -*-
"""T67 生态群系总目录：汇总 T64/T65/T66 全部 32 个群系，按终态组织形态分类并出图。

输出：
  t67_catalog.json            —— 32 行总表（含分类、指标、代表产物）
  images/t67_catalog_map.png  —— 生态位全景（专一性×聚合度 + 类别分布）
  images/t67_catalog_bars.png —— 32 群系按类别排列的条带目录
"""
import json, math, os
from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
IMG = os.path.join(BASE, "images")
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

ROUNDS = [
    ("T64", "t64_analysis.json", "T64（12 群系，首批）", (110, 116, 128)),
    ("T65", "t65_analysis.json", "T65（10 群系，≥4 元素）", (230, 128, 40)),
    ("T66", "t66_analysis.json", "T66（10 群系，化合物播种）", (128, 84, 190)),
]

CATS = [
    ("A", "单主型", "≥90%：一种产物吃掉几乎所有原子", (60, 120, 200)),
    ("B", "主辅型", "50~90%：主产物 + 次级产物/游离残留", (240, 150, 60)),
    ("C", "双主型", "40~50%：两种产物并列", (90, 170, 120)),
    ("D", "多主型", "<40%：三种以上并列（多组分生态）", (200, 90, 110)),
]

# 注释分组（同坐标/近邻的群系合并成一条注记，避免重叠）：(ids, 文本, 偏移dx, 偏移dy)
ANNOTS = [
    (["B01", "B02", "B03"], "B01/B02/B03 纯族一元盐 99%", -250, -46),
    (["C03", "E03"], "C03/E03 四元盐 98%", -60, 62),
    (["B08", "C06", "E06"], "B08/C06/E06 十原子簇 94%", -200, -74),
    (["C07", "E07"], "C07/E07 六元盐 94%", 46, 34),
    (["B11", "C10"], "B11=C10 九元生态 LF+OXCPWKA", 40, 46),
    (["E09"], "E09 八元 27 种", 56, -26),
    (["E10"], "E10 九元盐穹顶 29 种", -190, -34),
    (["C05", "E05"], "C05/E05 capped 7,313/1,009", -330, -40),
    (["B09", "B10"], "B09=B10 三对双原子各 1/3", -180, -66),
    (["C01", "E01"], "C01/E01 双主 50/50", 20, -84),
    (["C02", "E02"], "C02/E02 双盐 50/50", 44, 52),
    (["C04", "E04"], "C04/E04 XKF+A2", 60, -40),
    (["C08"], "C08 七元 53%", 40, 30),
]


def load_rows():
    rows = []
    for tag, fn, label, color in ROUNDS:
        d = json.load(open(os.path.join(BASE, fn), encoding="utf-8"))
        for b in d["biomes"]:
            if not b.get("present"):
                continue
            t1 = b.get("top1", "")
            if isinstance(t1, dict):
                top1, top1_n = t1.get("formula", ""), t1.get("count")
            else:
                top1, top1_n = t1, None
            share = float(b.get("top1_share") or 0.0)
            groups = b.get("groups") or {}
            rows.append({
                "round": tag,
                "id": b["id"],
                "name": b["name"],
                "tag": b.get("tag", ""),
                "n_elements": b["n_elements"],
                "elements": list((b.get("elements") or {}).keys()),
                "trivalent": b.get("trivalent", []),
                "L": b.get("L"),
                "total_atoms": b.get("total_atoms_design"),
                "final_N": b.get("final_N"),
                "species": len(b.get("composition") or {}),
                "mean_atoms": b.get("mean_atoms"),
                "max_atoms": b.get("max_atoms"),
                "capped": b.get("capped", 0),
                "capped_share": b.get("capped_share", 0.0),
                "new_substances": b.get("new_substances", 0),
                "effective_species": b.get("effective_species"),
                "top1": top1,
                "top1_count": top1_n,
                "top1_share": share,
                "groups": groups,
                "hold_activity": b.get("hold_activity"),
                "trivalent_util": b.get("trivalent_util"),
                "conversion": b.get("conversion"),
                "runtime_s": b.get("runtime_s"),
            })
    return rows


def classify(rows):
    for r in rows:
        s = r["top1_share"]
        r["cat"] = "A" if s >= 0.90 else ("B" if s >= 0.50 else ("C" if s >= 0.40 else "D"))
        r["cluster"] = (r["mean_atoms"] or 0) >= 7.0
        r["capped_heavy"] = (r["capped"] or 0) >= 1000
        mix = (r.get("groups") or {}).get("mixed", {})
        r["mixed_share"] = (mix.get("share") if isinstance(mix, dict) else None)
    return rows


def fonts():
    return (lambda s: ImageFont.truetype(FONT_REG, s)), (lambda s: ImageFont.truetype(FONT_BOLD, s))


def jitter(rid):
    """确定性抖动，避免同坐标点完全重叠。"""
    h = sum(ord(c) * (i + 1) for i, c in enumerate(rid))
    dx = ((h % 17) - 8) * 0.0085
    dy = (((h // 17) % 17) - 8) * 0.085
    return dx, dy


def scatter_map(rows):
    W, H = 1680, 1180
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    reg, bold = fonts()
    d.text((36, 22), "T67 生态群系总目录：32 个群系的生态位全景（专一性 × 聚合度）", font=bold(30), fill=(20, 20, 20))
    d.text((36, 64), "点=群系（同坐标点做了微小抖动）；颜色=实验轮次；大小=终态种数；竖虚线=四类分界（专一性 0.90 / 0.50 / 0.40）",
           font=reg(16), fill=(70, 70, 70))
    x0, y0, x1, y1 = 120, 150, 1060, 940
    d.rectangle([x0, y0, x1, y1], outline=(110, 110, 110), width=2)
    for t in [0.40, 0.50, 0.90]:
        x = x0 + t * (x1 - x0)
        d.line([x, y0, x, y1], fill=(200, 200, 200), width=1)
    for t in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        x = x0 + t * (x1 - x0)
        d.line([x, y1, x, y1 + 6], fill=(120, 120, 120), width=1)
        d.text((x - 12, y1 + 12), f"{t:.1f}", font=reg(13), fill=(90, 90, 90))
    ymin, ymax = 1.5, 10.5
    for v in [2, 4, 6, 8, 10]:
        y = y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)
        d.line([x0 - 6, y, x0, y], fill=(120, 120, 120), width=1)
        d.text((x0 - 40, y - 8), f"{v}", font=reg(13), fill=(90, 90, 90))
        d.line([x0, y, x1, y], fill=(240, 240, 240), width=1)
    d.text((x0, y1 + 34), "头号产物占比（专一性）→ 越大越集中", font=reg(16), fill=(40, 40, 40))
    d.text((20, y0 - 28), "平均原子数（聚合度）", font=reg(15), fill=(40, 40, 40))
    cmap = {tag: color for tag, _, _, color in ROUNDS}
    # 类别区名
    for t, name, col in [(0.16, "D 多主型", (200, 90, 110)), (0.45, "C 双主型", (90, 170, 120)),
                         (0.70, "B 主辅型", (230, 140, 40)), (0.95, "A 单主型", (60, 120, 200))]:
        d.text((x0 + t * (x1 - x0) - 30, y0 + 8), name, font=bold(16), fill=col)
    pts = []
    for r in rows:
        dx, dy = jitter(r["id"])
        px = x0 + (r["top1_share"] + dx) * (x1 - x0)
        py = y1 - (r["mean_atoms"] + dy - ymin) / (ymax - ymin) * (y1 - y0)
        rad = 5 + min(5.0, math.sqrt(max(1, r["species"])) * 1.2)
        pts.append((px, py, rad, r))
    for px, py, rad, r in pts:
        col = cmap[r["round"]]
        d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=col, outline=(35, 35, 35))
        d.text((px - 9, py - 7), r["id"], font=reg(10), fill="white")
    # 注释（按分组绘制，合并近邻点，避免文字重叠）
    lookup = {r["id"]: (px, py) for px, py, rad, r in pts}
    for ids, text, ox, oy in ANNOTS:
        use = [lookup[i] for i in ids if i in lookup]
        if not use:
            continue
        gx = sum(u[0] for u in use) / len(use)
        gy = sum(u[1] for u in use) / len(use)
        tx, ty = gx + ox, gy + oy
        d.line([gx, gy, tx + 4, ty + 10], fill=(150, 150, 150), width=1)
        bb = d.textbbox((tx, ty), text, font=reg(12))
        d.rectangle([bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2], fill="white", outline=(215, 215, 215))
        d.text((tx, ty), text, font=reg(12), fill=(45, 45, 45))
    # 图例（右栏）
    lx = 1110
    d.text((lx, 150), "实验轮次", font=bold(18), fill=(20, 20, 20))
    for i, (tag, _, label, color) in enumerate(ROUNDS):
        yy = 184 + i * 30
        d.ellipse([lx, yy, lx + 16, yy + 16], fill=color, outline=(40, 40, 40))
        d.text((lx + 26, yy - 1), label, font=reg(14), fill=(40, 40, 40))
    d.text((lx, 300), "终态形态类别（按专一性划分）", font=bold(17), fill=(20, 20, 20))
    for i, (code, name, desc, color) in enumerate(CATS):
        yy = 336 + i * 74
        d.rectangle([lx, yy + 2, lx + 16, yy + 18], fill=color)
        d.text((lx + 24, yy - 2), f"{code} {name}", font=bold(16), fill=color)
        d.text((lx + 24, yy + 18), desc, font=reg(12), fill=(85, 85, 85))
    # 类别×轮次计数（右栏底部）
    bx, by = lx, 660
    d.text((bx, by), "类别分布（按轮次）", font=bold(17), fill=(20, 20, 20))
    counts = {c[0]: {tag: 0 for tag, _, _, _ in ROUNDS} for c in CATS}
    for r in rows:
        counts[r["cat"]][r["round"]] += 1
    for i, (code, name, desc, color) in enumerate(CATS):
        yy = by + 34 + i * 58
        d.text((bx, yy + 2), f"{code} {name}", font=reg(14), fill=(40, 40, 40))
        xx = bx + 96
        for tag, _, _, col2 in ROUNDS:
            for k in range(counts[code][tag]):
                d.rectangle([xx, yy + 2, xx + 16, yy + 18], fill=col2, outline=(40, 40, 40))
                xx += 20
            xx += 6
        d.text((xx + 2, yy + 2), f"共 {sum(counts[code].values())}", font=reg(13), fill=(70, 70, 70))
    d.text((bx, by + 268), "合计 32 个群系：A 10、B 11、C 7、D 4", font=reg(13), fill=(70, 70, 70))
    d.text((36, H - 40), "口径：专一性=头号产物分子数/终态总分子数；聚合度=终态原子数/终态分子数；"
                         "类别阈值 A≥0.90、B 0.50~0.90、C 0.40~0.50、D<0.40（本轮由 t67_catalog.py 自动划分）。",
           font=reg(14), fill=(90, 90, 90))
    out = os.path.join(IMG, "t67_catalog_map.png")
    img.save(out)
    return out


def catalog_bars(rows):
    order = []
    for code, name, desc, color in CATS:
        group = [r for r in rows if r["cat"] == code]
        group.sort(key=lambda r: (r["top1_share"], -(r["mean_atoms"] or 0)), reverse=True)
        order.extend(group)
    W, H = 1780, 1560
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    reg, bold = fonts()
    d.text((36, 20), "T67 生态群系总目录：32 个群系按类别排列（专一性 / 聚合度 / capped / 元素数）", font=bold(27), fill=(20, 20, 20))
    d.text((36, 58), "左=头号产物占比条；右列=平均原子、最大原子、capped、终态种数；颜色=实验轮次",
           font=reg(16), fill=(70, 70, 70))
    y0, rowh = 150, 38
    x_cat, x_id, x_name, x_el, x0, xmax = 36, 190, 246, 452, 530, 1010
    x_agg, x_max, x_cap, x_sp, x_clu = 1120, 1230, 1320, 1450, 1550
    cmap = {tag: color for tag, _, _, color in ROUNDS}
    prev = None
    for i, r in enumerate(order):
        y = y0 + i * rowh
        col = cmap[r["round"]]
        if r["cat"] != prev:
            c = [c for c in CATS if c[0] == r["cat"]][0]
            d.rectangle([x_cat, y - 4, 168, y + rowh - 6], fill=c[3])
            d.text((x_cat + 6, y + 2), f"{c[0]} {c[1]}", font=bold(14), fill="white")
            prev = r["cat"]
        else:
            d.text((x_cat + 6, y + 2), r["cat"], font=reg(12), fill=(130, 130, 130))
        d.text((x_id, y + 2), r["id"], font=reg(14), fill=(30, 30, 30))
        d.text((x_name, y + 2), r["name"], font=reg(14), fill=(30, 30, 30))
        d.text((x_el, y + 2), f"{r['n_elements']}元", font=reg(12), fill=(90, 90, 90))
        bw = r["top1_share"] * (xmax - x0)
        d.rectangle([x0, y + 4, x0 + bw, y + rowh - 8], fill=col)
        lab = f"{r['top1']} {r['top1_share']*100:.1f}%"
        tw = d.textlength(lab, font=reg(13))
        if bw > tw + 26:
            d.text((x0 + bw - tw - 8, y + 2), lab, font=reg(13), fill="white")
        else:
            d.text((x0 + bw + 8, y + 2), lab, font=reg(13), fill=(40, 40, 40))
        d.text((x_agg, y + 2), f"{r['mean_atoms']:.2f}", font=reg(13), fill=(60, 60, 60))
        d.text((x_max, y + 2), f"{r['max_atoms']}", font=reg(13), fill=(60, 60, 60))
        d.text((x_cap, y + 2), f"{r['capped']}", font=reg(13), fill=(60, 60, 60))
        d.text((x_sp, y + 2), f"{r['species']}", font=reg(13), fill=(60, 60, 60))
        if r.get("cluster"):
            d.text((x_clu, y + 2), "簇合", font=bold(13), fill=(200, 60, 60))
    # 表头
    hy = 112
    d.text((x_cat, hy), "类别", font=bold(13), fill=(60, 60, 60))
    d.text((x_id, hy), "编号", font=bold(13), fill=(60, 60, 60))
    d.text((x_name, hy), "群系名称", font=bold(13), fill=(60, 60, 60))
    d.text((x_el, hy), "元素", font=bold(13), fill=(60, 60, 60))
    d.text((x0, hy), "头号产物占比（专一性）", font=bold(13), fill=(60, 60, 60))
    d.text((x_agg, hy), "聚合", font=bold(13), fill=(60, 60, 60))
    d.text((x_max, hy), "最大值", font=bold(13), fill=(60, 60, 60))
    d.text((x_cap, hy), "capped", font=bold(13), fill=(60, 60, 60))
    d.text((x_sp, hy), "种数", font=bold(13), fill=(60, 60, 60))
    d.text((x_clu, hy), "标记", font=bold(13), fill=(60, 60, 60))
    y = y0 + len(order) * rowh + 18
    d.text((36, y), "轮次：", font=bold(15), fill=(20, 20, 20))
    xx = 100
    for tag, _, label, color in ROUNDS:
        d.rectangle([xx, y + 2, xx + 16, y + 18], fill=color)
        d.text((xx + 22, y), tag, font=reg(14), fill=(40, 40, 40))
        xx += 70
    d.text((36, y + 34), "说明：capped=合并后 >40 原子的弹性截断次数（不计入判定）；"
                         "「簇合」=平均原子数≥7 的骨架簇合型生态；专一性=头号产物分子数/终态分子数。",
           font=reg(14), fill=(90, 90, 90))
    out = os.path.join(IMG, "t67_catalog_bars.png")
    img.save(out)
    return out


def main():
    rows = classify(load_rows())
    order = {tag: i for i, (tag, _, _, _) in enumerate(ROUNDS)}
    rows.sort(key=lambda r: (order[r["round"]], r["id"]))
    counts = {c[0]: sum(1 for r in rows if r["cat"] == c[0]) for c in CATS}
    out = {
        "meta": {
            "experiment": "T67",
            "title": "生态群系总目录（T64 12 + T65 10 + T66 10 = 32 群系）",
            "date": "2026-11-17",
            "category_rule": "top1_share>=0.90 A单主；0.50~0.90 B主辅；0.40~0.50 C双主；<0.40 D多主",
            "note": "聚合度=终态原子/分子；专一性=top1分子数/终态分子数；capped 为合并>40原子弹性截断",
        },
        "category_counts": counts,
        "round_counts": {tag: sum(1 for r in rows if r["round"] == tag) for tag, _, _, _ in ROUNDS},
        "biomes": rows,
    }
    json.dump(out, open(os.path.join(BASE, "t67_catalog.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    a = scatter_map(rows)
    b = catalog_bars(rows)
    print("saved", os.path.basename(a), os.path.basename(b), "t67_catalog.json")
    print("category counts:", counts)


if __name__ == "__main__":
    main()
