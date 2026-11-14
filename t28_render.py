# -*- coding: utf-8 -*-
"""t28_render.py：规则 v2 示意图
1) 键不稳定分级图
2) 分解反应过程图（CW2F + OX2C → OX2C2W2F）
3) 能量规则图
"""
import json
import math
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
import t8_render_forms as R
from t28_rule_v2 import VAL, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT, FONT_B = R.FONT, R.FONT_B
font = R.font
text_center = R.text_center

COL = {"O": "#7fc97f", "X": "#f5a623", "C": "#8ecae6",
       "P": "#ff8fa3", "W": "#e3c34a", "L": "#fff08a",
       "K": "#b39ddb", "A": "#8fd6c0", "F": "#ef5350"}
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}


def draw_mol(d, rec, box, highlight=None, removed=None, stubs=False, title=None):
    x0, y0, w, h = box
    atoms = rec["atoms"]
    edges = [tuple(e) for e in rec["edges"]]
    place = {int(k): tuple(v) for k, v in rec["place"].items()}
    n = len(atoms)
    s = 26.0
    for _ in range(60):
        pts = [R.center_of(place[i], s) for i in range(n)]
        if max(p[0] for p in pts) - min(p[0] for p in pts) + 3 * s <= w and \
           max(p[1] for p in pts) - min(p[1] for p in pts) + 3 * s <= h:
            break
        s *= 0.93
    pts = [R.center_of(place[i], s) for i in range(n)]
    ox = x0 + w / 2 - (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    oy = y0 + h / 2 - (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    pos = [(p[0] + ox, p[1] + oy) for p in pts]
    polys = [R.hex_pts(pos[i][0], pos[i][1], s) for i in range(n)]
    highlight = highlight or set()
    removed = removed or set()

    def key(i, j):
        return (min(i, j), max(i, j))

    # L 中点空格
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        if R.rel_type(dd) == "L" and key(i, j) not in removed:
            mid = ((place[i][0] + place[j][0]) // 2, (place[i][1] + place[j][1]) // 2)
            if mid not in place.values():
                cp = R.center_of(mid, s)
                poly = R.hex_pts(cp[0] + ox, cp[1] + oy, s)
                d.polygon(poly, fill="#f5f5f5")
                R.dotted_poly(d, poly, "#bbbbbb", 2)
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = R.rel_type(dd)
        if key(i, j) in removed:
            # 断开的键：红色虚线 + 断点标记
            R.dashed(d, pos[i], pos[j], "#d62728", 3)
            mx, my = (pos[i][0] + pos[j][0]) / 2, (pos[i][1] + pos[j][1]) / 2
            d.line([mx - 7, my - 7, mx + 7, my + 7], fill="#d62728", width=3)
            d.line([mx - 7, my + 7, mx + 7, my - 7], fill="#d62728", width=3)
            continue
        if t == "S":
            sv = R.common_vertices(polys[i], polys[j])
            if len(sv) >= 2:
                R.ray_offset_line(d, sv[0], sv[1], BONDC["S"], max(2, int(s / 12)), m)
        elif t == "C":
            p1, p2 = R.nearest_vertices(polys[i], polys[j])
            R.ray_offset_line(d, p1, p2, BONDC["C"], max(2, int(s / 12)), m)
        elif t == "L":
            p1 = R.ray_exit(polys[i], pos[i], pos[j])
            p2 = R.ray_exit(polys[j], pos[j], pos[i])
            if p1 and p2:
                for k in range(m):
                    R.dashed(d, p1, p2, BONDC["L"], 2)
        if key(i, j) in highlight:
            d.line([pos[i], pos[j]], fill="#d62728", width=4)
    for i, e in enumerate(atoms):
        d.polygon(polys[i], fill=COL.get(e, "#ccc"), outline="#333", width=2)
        text_center(d, pos[i][0], pos[i][1] - s * 0.14, e, font(FONT_B, int(s * 0.56)), "#111")
        text_center(d, pos[i][0], pos[i][1] + s * 0.34, CN[e], font(FONT, int(s * 0.34)), "#111")
    if stubs:
        for i, e in enumerate(atoms):
            used = sum(m for (a, b, m) in edges if a == i or b == i)
            used -= sum(m for (a, b, m) in edges if a == i or b == i and key(a, b) in removed)
            # 更准确：保留边
            kept = sum(m for (a, b, m) in edges if (a == i or b == i) and key(a, b) not in removed)
            free = VAL[e] - kept
            for k in range(max(0, free)):
                ang = math.radians(-90 + 30 * k + 15)
                x1 = pos[i][0] + (s * 0.9) * math.cos(ang)
                y1 = pos[i][1] + (s * 0.9) * math.sin(ang)
                x2 = pos[i][0] + (s * 1.35) * math.cos(ang)
                y2 = pos[i][1] + (s * 1.35) * math.sin(ang)
                d.line([x1, y1, x2, y2], fill="#555", width=2)
    if title:
        d.text((x0 + 8, y0 + 6), title, font=font(FONT_B, 16), fill="#111")


def panel(d, box, outline="#ddd"):
    x, y, w, h = box
    d.rectangle([x, y, x + w, y + h], outline=outline, width=1)


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    byf = {r["formula"]: r for r in cat}
    ex = json.load(open(BASE + r"\t28_examples.json", encoding="utf-8"))
    target = None
    for f in ex:
        if f["A"]["formula"] == "CW2F" and f["B"]["formula"] == "OX2C":
            target = f
    assert target is not None

    # ---------------- 图1：键不稳定分级 ----------------
    W, H = 1700, 1150
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 16), "自然环境分解规则 v2：键不稳定分级", font=font(FONT_B, 30), fill="#111")
    d.text((26, 58), "排序：① 元素周期距离越小越先断 → ② 同距离时键级越高越先断 → ③ 同距离同键级时低价的键先断（1价 > 2价 > 3价）",
           font=font(FONT, 16), fill="#555")

    # 第一级：距离
    d.text((26, 100), "① 元素周期距离：同元素（d=0）最不稳定，然后 d=1,2,…,6", font=font(FONT_B, 20), fill="#333")
    boxes = [(26, 130, 380, 250), (430, 130, 380, 250), (834, 130, 380, 250)]
    hl = [{(0, 1)}, {(0, 1)}, {(1, 2)}]
    for (fx, box, h) in zip(["O2", "O2X", "CPK2"], boxes, hl):
        panel(d, box)
        draw_mol(d, byf[fx], box, highlight=h)
    d.text((60, 385), "O≡O：d=0（同元素，最不稳定）", font=font(FONT, 15), fill="#444")
    d.text((440, 385), "O–X：d=1（近距离）", font=font(FONT, 15), fill="#444")
    d.text((850, 385), "P–K：d=6（远距离，较稳定）", font=font(FONT, 15), fill="#444")

    # 第二级：键级
    d.text((26, 430), "② 键级：同距离时，三键 > 二键 > 一键（先断三键）", font=font(FONT_B, 20), fill="#333")
    boxes = [(26, 460, 380, 250), (430, 460, 380, 250), (834, 460, 380, 250)]
    hl2 = [{(0, 1)}, {(0, 2)}, {(0, 2)}]
    for (fx, box, h) in zip(["O2", "O2X", "O2CK"], boxes, hl2):
        panel(d, box)
        draw_mol(d, byf[fx], box, highlight=h)
    d.text((60, 715), "O≡O（三键，先断）", font=font(FONT, 15), fill="#444")
    d.text((440, 715), "O=O（双键，后断）", font=font(FONT, 15), fill="#444")
    d.text((850, 715), "O–O（一键，最后断）", font=font(FONT, 15), fill="#444")

    # 第三级：价数
    d.text((26, 760), "③ 价数分级（建议新增）：同距离同键级时，含 1 价元素的键先断，其次 2 价，最后 3 价",
           font=font(FONT_B, 20), fill="#333")
    boxes = [(26, 790, 380, 280), (430, 790, 380, 280), (834, 790, 380, 280)]
    hl3 = [{(0, 2)}, {(1, 2)}, {(1, 2)}]
    for (fx, box, h) in zip(["OCA", "O2X", "CPK2"], boxes, hl3):
        panel(d, box)
        draw_mol(d, byf[fx], box, highlight=h)
    d.text((60, 1075), "C–O：1 价端键，优先断", font=font(FONT, 15), fill="#444")
    d.text((440, 1075), "X–O：2 价端键，其次断", font=font(FONT, 15), fill="#444")
    d.text((850, 1075), "P–K：3 价骨架键，最后断", font=font(FONT, 15), fill="#444")
    img.save(BASE + r"\images\t28_bond_hierarchy.png")
    print("saved t28_bond_hierarchy.png")

    # ---------------- 图2：分解过程 ----------------
    W2, H2 = 1750, 800
    img2 = Image.new("RGB", (W2, H2), "white")
    d2 = ImageDraw.Draw(img2)
    d2.text((24, 14), "自然环境分解过程：CW2F + OX2C → OX2C2W2F", font=font(FONT_B, 28), fill="#111")
    d2.text((24, 52), "选中类：d=0, 键级=1, 最低端价数=2（同元素单键）→ 每个元素对断 1 根键，共 2 根；断后按大锅规则重结合",
            font=font(FONT, 15), fill="#555")
    # 四个面板
    pw, ph, top = 400, 520, 100
    xs = [24, 452, 880, 1308]
    titles = ["① 反应物（两个分子）", "② 选中最不稳定类并断键", "③ 断键后（自由价）", "④ 重结合产物"]
    for x, t in zip(xs, titles):
        panel(d2, (x, top, pw, ph))
        d2.text((x + 8, top + 6), t, font=font(FONT_B, 17), fill="#111")
    # 面板1：两个分子上下
    draw_mol(d2, byf["CW2F"], (xs[0] + 10, top + 40, pw - 20, 210))
    draw_mol(d2, byf["OX2C"], (xs[0] + 10, top + 270, pw - 20, 210))
    # 面板2：高亮要断的键 (CW2F: W-W 键 1-2；OX2C: X-X 键 2-3)
    draw_mol(d2, byf["CW2F"], (xs[1] + 10, top + 40, pw - 20, 210), highlight={(1, 2)},
             title="CW2F：断 W–W 单键")
    draw_mol(d2, byf["OX2C"], (xs[1] + 10, top + 270, pw - 20, 210), highlight={(2, 3)},
             title="OX2C：断 X–X 单键")
    # 面板3：断键后
    draw_mol(d2, byf["CW2F"], (xs[2] + 10, top + 40, pw - 20, 210), removed={(1, 2)}, stubs=True)
    draw_mol(d2, byf["OX2C"], (xs[2] + 10, top + 270, pw - 20, 210), removed={(2, 3)}, stubs=True)
    # 面板4：产物
    prod = target["products"][0]
    draw_mol(d2, prod, (xs[3] + 10, top + 60, pw - 20, 380))
    d2.text((xs[3] + 20, top + 460), "OX2C2W2F（合并为单分子）", font=font(FONT, 15), fill="#444")
    d2.text((xs[2] + 20, top + 465), "保留键 + 自由价（短线标记）", font=font(FONT, 14), fill="#666")
    d2.text((24, H2 - 36), "能量校验：体系 8 原子 = 8/3 ≈ 2.67 能量单位；断 2 根键耗 2 能量 → 足够，可发生。",
            font=font(FONT_B, 16), fill="#a0522d")
    img2.save(BASE + r"\images\t28_decomposition_process.png")
    print("saved t28_decomposition_process.png")

    # ---------------- 图3：能量规则 ----------------
    W3, H3 = 1600, 1000
    img3 = Image.new("RGB", (W3, H3), "white")
    d3 = ImageDraw.Draw(img3)
    d3.text((24, 14), "能量规则：拆 1 根键耗 1 能量；地图每 1 单位储 1 能量", font=font(FONT_B, 28), fill="#111")
    d3.text((24, 52), "标准骨架形态 = O3P 型四原子核心（4 格）= 1 单位；能量不足时，本次分解不成立（原样保留）。",
            font=font(FONT, 15), fill="#555")
    panel(d3, (24, 100, 380, 310))
    draw_mol(d3, byf["O3P"], (34, 110, 360, 260))
    d3.text((56, 430), "O3P 四原子核心：4 格 = 1 单位", font=font(FONT_B, 17), fill="#111")
    d3.text((56, 458), "1 单位地图储存 1 能量", font=font(FONT, 15), fill="#444")

    def energy_box(x, y, name, atoms, cost, ok, detail):
        d3.rounded_rectangle([x, y, x + 700, y + 150], radius=10, outline="#ccc", width=2)
        d3.text((x + 16, y + 10), name, font=font(FONT_B, 18), fill="#111")
        avail = atoms / 4.0
        d3.text((x + 16, y + 42), f"体系大小：{atoms} 原子 = {atoms}/4 = {avail:.2f} 单位 → 储能 {avail:.2f}",
                font=font(FONT, 15), fill="#333")
        d3.text((x + 16, y + 68), f"拆键消耗：{cost} 根 × 1 = {cost} 能量", font=font(FONT, 15), fill="#333")
        d3.text((x + 16, y + 96), f"结论：{'√ 能量足够，分解可发生' if ok else '× 能量不足，本次分解不成立'}",
                font=font(FONT_B, 17), fill="#1e8449" if ok else "#c0392b")
        if detail:
            d3.text((x + 16, y + 122), detail, font=font(FONT, 13), fill="#666")

    energy_box(24, 480, "CW2F + OX2C（通过）", 8, 2, True, "断 1 根 W–W + 1 根 X–X")
    energy_box(820, 480, "X3 + W3（能量不足）", 6, 6, False, "三个 X–X + 三个 W–W 全被选为同类断裂")
    d3.text((24, 660), "参数选择对反应的影响（400 个随机分子对，无几何校验）：", font=font(FONT_B, 18), fill="#111")
    rows = [
        ("单位大小", "每单位储能", "能量不足比例", "实际变化比例"),
        ("3 原子", "1", "0.75%", "7.25%"),
        ("3 原子", "2", "0%", "8.00%"),
        ("4 原子", "1（推荐）", "4.00%", "5.75%"),
        ("5 原子", "1", "9.00%", "3.50%"),
        ("6 原子", "1", "15.25%", "2.00%"),
        ("8 原子", "1", "34.50%", "1.00%"),
        ("8 原子", "2", "4.00%", "5.75%"),
    ]
    y = 698
    for r in rows:
        cols = [24, 260, 480, 760]
        for c, txt in zip(cols, r):
            d3.text((c, y), txt, font=font(FONT_B if r is rows[0] else FONT, 15),
                    fill="#111" if r is rows[0] else "#333")
        y += 32
    img3.save(BASE + r"\images\t28_energy_rule.png")
    print("saved t28_energy_rule.png")


if __name__ == "__main__":
    main()
