# -*- coding: utf-8 -*-
"""t13_render_140.py v2：140 原子反应图（尝试严格摆放反应物；修文本重叠）"""
import json
import math
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
import pot_v2
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
IMGOUT = BASE + r"\images\t13_140_atom_reaction.png"
FILL = {"O": (107, 191, 107), "X": (240, 160, 75), "C": (127, 182, 232),
        "P": (240, 130, 185), "W": (201, 162, 39), "L": (255, 224, 102),
        "K": (150, 110, 220), "A": (143, 214, 192), "F": (224, 90, 79)}
FONT = R.FONT
FONT_B = R.FONT_B
font = R.font
text_center = R.text_center
draw_formula = R.draw_formula
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}


def draw_mol(d, atoms, edges, place, box, max_s=None, schematic=False):
    x0, y0, w, h = box
    n = len(atoms)
    if place is None:
        cx, cy = x0 + w / 2, y0 + h / 2
        rad = min(w, h) / 2 - 24
        pts = [(cx + rad * math.cos(2 * math.pi * i / n),
                cy + rad * math.sin(2 * math.pi * i / n)) for i in range(n)]
        for e in edges:
            i, j = e[0], e[1]
            d.line([pts[i], pts[j]], fill="#888", width=1)
        for i, el in enumerate(atoms):
            r = max(2.5, rad / max(12, n) * 1.2)
            d.ellipse([pts[i][0] - r, pts[i][1] - r, pts[i][0] + r, pts[i][1] + r],
                      fill=FILL[el], outline="#333")
        return
    s = max_s or 26.0
    for _ in range(80):
        pts = [R.center_of(place[i], s) for i in range(n)]
        bw = max(p[0] for p in pts) - min(p[0] for p in pts) + 2.2 * s
        bh = max(p[1] for p in pts) - min(p[1] for p in pts) + 2.2 * s
        if bw <= w and bh <= h:
            break
        s *= 0.94
    pts = [R.center_of(place[i], s) for i in range(n)]
    ox = x0 + w / 2 - (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    oy = y0 + h / 2 - (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    pos = [(p[0] + ox, p[1] + oy) for p in pts]
    polys = [R.hex_pts(pos[i][0], pos[i][1], s) for i in range(n)]
    for e in edges:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = R.rel_type(dd)
        col = BONDC.get(t, "#333")
        width = max(1, int(s / 12)) if t in ("S", "C") else max(1, int(s / 15))
        if t == "S":
            sv = R.common_vertices(polys[i], polys[j])
            if len(sv) >= 2:
                R.ray_offset_line(d, sv[0], sv[1], col, width, m)
        elif t == "C":
            p1, p2 = R.nearest_vertices(polys[i], polys[j])
            R.ray_offset_line(d, p1, p2, col, width, m)
        elif t == "L":
            p1 = R.ray_exit(polys[i], pos[i], pos[j])
            p2 = R.ray_exit(polys[j], pos[j], pos[i])
            if p1 and p2:
                ux, uy = p2[0] - p1[0], p2[1] - p1[1]
                L = math.hypot(ux, uy)
                nx, ny = -uy / L, ux / L
                for k in range(m):
                    off = (k - (m - 1) / 2) * max(2.0, s * 0.12)
                    a = (p1[0] + nx * off, p1[1] + ny * off)
                    b = (p2[0] + nx * off, p2[1] + ny * off)
                    R.dashed(d, a, b, col, width)
    for i, el in enumerate(atoms):
        d.polygon(polys[i], fill=FILL[el], outline="#333", width=max(1, int(s / 20)))
        if s >= 9:
            text_center(d, pos[i][0], pos[i][1], el, font(FONT_B, int(s * 0.55)), "#111")


def try_place(rec, budget):
    atoms = rec["atoms"]
    edges = [tuple(e) for e in rec["edges"]]
    p = rec.get("place")
    if p is not None:
        return {int(k): tuple(v) for k, v in p.items()}
    print("embedding", rec["formula"], len(atoms), "...", flush=True)
    pl = pot_v2.embed_mol2(atoms, edges, max_nodes=budget)
    if pl is None:
        return None
    ok, msg = pot_v2.validate_place(pl, atoms, edges)
    print(" placed ok:", ok, msg, flush=True)
    return pl


cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
byf = {r["formula"]: r for r in cat}
r1 = byf["O14X13P24K4A13"]
r2 = byf["O14X14P23WK7A7F6"]
prod = json.load(open(BASE + r"\t12c_big140.json", encoding="utf-8"))[0]
prod = {"formula": prod["formula"], "atoms": prod["atoms"],
        "edges": [tuple(e) for e in prod["edges"]],
        "place": {int(k): tuple(v) for k, v in prod["place"].items()}}

p1 = try_place(r1, 5_000_000)
p2 = try_place(r2, 5_000_000)
json.dump({"r1_place": {str(k): list(v) for k, v in (p1 or {}).items()},
           "r2_place": {str(k): list(v) for k, v in (p2 or {}).items()}},
          open(BASE + r"\t13_reactants_place.json", "w", encoding="utf-8"))

W, H = 2000, 1120
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
d.text((30, 18), "140 原子物质的产生反应（当前最大合法分子纪录）", font=font(FONT_B, 34), fill="#111")
d.text((30, 64), "两个反应物共 68 + 72 = 140 个原子 → 一锅反应后全部原子进入同一个分子（O28X27P47WK11A20F6）",
       font=font(FONT, 19), fill="#555")
d.text((30, 94), "红=短键S，绿=角键C，紫虚线=长键L；格内字母=元素符号（O秩/X晶/C冰/P势/W流/L电/K沌/A气/F焰）",
       font=font(FONT, 15), fill="#888")

d.text((30, 145), "反应物 1：O14X13P24K4A13（68 原子）" + ("" if p1 else "（结构示意）"),
       font=font(FONT_B, 19), fill="#0b6")
draw_mol(d, r1["atoms"], [tuple(e) for e in r1["edges"]], p1, (30, 180, 450, 400), max_s=14)
text_center(d, 250, 610, "+", font(FONT_B, 54), "#111")
d.text((500, 145), "反应物 2：O14X14P23WK7A7F6（72 原子）" + ("" if p2 else "（结构示意）"),
       font=font(FONT_B, 19), fill="#0b6")
draw_mol(d, r2["atoms"], [tuple(e) for e in r2["edges"]], p2, (500, 180, 450, 400), max_s=14)
text_center(d, 990, 610, "→", font(FONT_B, 56), "#111")
d.text((1010, 145), "产物：1 个 140 原子巨型分子", font=font(FONT_B, 19), fill="#c33")
draw_mol(d, prod["atoms"], prod["edges"], prod["place"], (1000, 175, 980, 720), max_s=30)
draw_formula(d, 1490, 930, "O28X27P47WK11A20F6", 30, "#111")
text_center(d, 1490, 970, "（140 原子；pot_v2.validate_place 严格校验通过）", font(FONT, 15), "#555")

d.text((30, 660), "反应式：O14X13P24K4A13 + O14X14P23WK7A7F6 → O28X27P47WK11A20F6（140 原子）",
       font=font(FONT_B, 18), fill="#111")
d.text((30, 700), "说明：产物把两个大分子的全部原子按规则 1~9 重新成键成一块；8M 节点预算下约 65 秒找到合法布局；",
       font=font(FONT, 16), fill="#444")
d.text((30, 728), "此前项目最好纪录 97 原子，此产物把最大合法分子下界推到 140 原子（更大分子搜索见 T13_BIG_SEARCH.md）。",
       font=font(FONT, 16), fill="#b8860b")
img.save(IMGOUT)
print("saved", IMGOUT)
