# -*- coding: utf-8 -*-
"""t36c_render.py：同时含 38 库多三价骨架 + 7×3 库单三价骨架的物质示例图"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
import t8_render_forms as R
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
by = {r["formula"]: r for r in cat}
FONT, FONT_B = R.FONT, R.FONT_B
font = R.font
text_center = R.text_center
COL = {"O": "#7fc97f", "X": "#f5a623", "C": "#8ecae6",
       "P": "#ff8fa3", "W": "#e3c34a", "L": "#fff08a",
       "K": "#b39ddb", "A": "#8fd6c0", "F": "#ef5350"}
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}


def components(rec):
    atoms = rec["atoms"]
    n = len(atoms)
    adj = [[] for _ in range(n)]
    em = {}
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        em[(i, j)] = m
        em[(j, i)] = m
        if atoms[i] in TRI and atoms[j] in TRI:
            adj[i].append(j)
            adj[j].append(i)
    seen = set()
    out = []
    for s in range(n):
        if s in seen or atoms[s] not in TRI:
            continue
        st = [s]
        seen.add(s)
        mem = [s]
        while st:
            u = st.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
                    mem.append(v)
        out.append(sorted(mem))
    return out


def draw_molecule(d, rec, box, multi_atoms, single_atoms):
    x0, y0, w, h = box
    atoms = rec["atoms"]
    edges = [tuple(e) for e in rec["edges"]]
    place = {int(k): tuple(v) for k, v in rec["place"].items()}
    n = len(atoms)
    s = 28.0
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
    # L 中点
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        if R.rel_type(dd) == "L":
            mid = ((place[i][0] + place[j][0]) // 2, (place[i][1] + place[j][1]) // 2)
            if mid not in place.values():
                cp = R.center_of(mid, s)
                poly = R.hex_pts(cp[0] + ox, cp[1] + oy, s)
                d.polygon(poly, fill="#f5f5f5")
                R.dotted_poly(d, poly, "#bbbbbb", 2)
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = R.rel_type(dd)
        col = BONDC.get(t, "#333")
        width = max(2, int(s / 12.5)) if t in ("S", "C") else max(2, int(s / 16))
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
                for k in range(m):
                    R.dashed(d, p1, p2, col, 2)
    for i, e in enumerate(atoms):
        if i in multi_atoms:
            fill = "#e8684a"
        elif i in single_atoms:
            fill = "#5b8ff9"
        else:
            fill = COL.get(e, "#ccc")
        d.polygon(polys[i], fill=fill, outline="#333", width=2)
        text_center(d, pos[i][0], pos[i][1] - s * 0.14, e, font(FONT_B, int(s * 0.55)), "#111")
        text_center(d, pos[i][0], pos[i][1] + s * 0.34, CN[e], font(FONT, int(s * 0.33)), "#111")


def main():
    examples = [
        ("O5X3KA", ["O3K", "O–O 单键二聚"]),
        ("OCP7W2KA2", ["OP4K", "PPP 三元链"]),
    ]
    W, H = 1740, 980
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 12), "同时包含「38 库多三价骨架」和「7×3 库单三价骨架」的物质",
           font=font(FONT_B, 27), fill="#111")
    d.text((24, 48), "红 = 38 库多三价骨架（≥2 种三价元素）；蓝 = 7×3 库单三价骨架；其它颜色 = 二价/一价装饰层。",
           font=font(FONT, 14), fill="#555")
    for k, (f, labels) in enumerate(examples):
        rec = by[f]
        cs = components(rec)
        multi = None
        single = None
        for comp in cs:
            types = set(rec["atoms"][i] for i in comp) & TRI
            if len(types) >= 2 and multi is None:
                multi = comp
            elif len(types) == 1 and single is None:
                single = comp
        x = 24 + k * 870
        d.rounded_rectangle([x, 90, x + 840, 640], radius=10, outline="#999", width=2)
        d.text((x + 16, 100), f"示例：{f}（{len(rec['atoms'])} 原子）", font=font(FONT_B, 20), fill="#111")
        draw_molecule(d, rec, (x + 10, 140, 820, 430), set(multi or []), set(single or []))
        # 图例说明
        d.text((x + 16, 590), "◆ 多三价骨架：" + labels[0], font=font(FONT_B, 15), fill="#e8684a")
        d.text((x + 16, 615), "◆ 单三价骨架：" + labels[1], font=font(FONT_B, 15), fill="#5b8ff9")
        d.text((x + 430, 590), "分子式：" + f, font=font(FONT, 14), fill="#333")
    # 统计
    d.rounded_rectangle([24, 660, 1716, 950], radius=10, fill="#fafafa", outline="#ccc", width=2)
    d.text((40, 672), "搜索结果（全部 84,225 种物质）：", font=font(FONT_B, 20), fill="#111")
    lines = [
        "• 同时包含两类骨架：12,268 种（14.6%）；其中“单三价骨架”为非单原子的有 2,192 种。",
        "• 若要求多三价骨架是独立完整组件：9,869 种；其中单三价骨架非单原子的有 153 种。",
        "• 单三价骨架的形态：单原子 13,975 个（平凡）、单键二聚 1,543、双键二聚 589、三元链 65；未发现三元环。",
        "• 与单三价骨架共同出现的多三价骨架只有 7 种：OK3、O3K、O3P、PK3、P3K、OP3、OP4K（38 库中的其余 28 种未出现）。",
        "• 最小案例是 10 原子：O5X3KA、O5X3PA、OP5W3A、OWK5A3、OXK5A3、OXP5W3、P5W3KA、PWK5A3 等。",
        "• 结论：确实存在；但它们不是 38 库 × 21 库的任意组合，而是集中在少数小骨架 + 二价/一价装饰连接的结构。",
    ]
    y = 712
    for s in lines:
        d.text((40, y), s, font=font(FONT, 14), fill="#222")
        y += 34
    img.save(BASE + r"\images\t36_both_skeletons.png")
    print("saved t36_both_skeletons.png")


if __name__ == "__main__":
    main()
