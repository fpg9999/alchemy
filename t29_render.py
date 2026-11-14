# -*- coding: utf-8 -*-
"""t29_render.py：新物质反应示例图 + 分类规律图"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
from t28_render import draw_mol, font, FONT, FONT_B, text_center, COL

BASE = r"G:\AI work\deepseek\work1\alchemy"
ex = json.load(open(BASE + r"\t29_examples_geo.json", encoding="utf-8"))

ORDER = [("merge_new", "① 合并型（2→1，产生新物质）"),
         ("exchange_new", "② 交换型（2→2，产生新物质）"),
         ("split_new", "③ 裂解型（2→≥3，产生新物质）"),
         ("merge_old", "④ 合并型（2→1，无新物质）"),
         ("exchange_old", "⑤ 交换型（2→2，无新物质）"),
         ("split_old", "⑥ 裂解型（2→≥3，无新物质）")]


def card(d, box, key, title):
    x, y, w, h = box
    e = ex.get(key)
    if not e:
        return
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, outline="#999", width=2)
    d.text((x + 12, y + 8), title, font=font(FONT_B, 17), fill="#111")
    d.text((x + 12, y + 32), f"断裂类 d={e['class'][0]}, m={-e['class'][1]}, v={e['class'][2]}",
           font=font(FONT, 13), fill="#666")
    # 反应物
    top_y = y + 55
    half = (w - 30) // 2
    draw_mol(d, {"formula": e["A"]["formula"], "atoms": e["A"]["atoms"],
                 "edges": e["A"]["edges"], "place": e["A"]["place"]},
             (x + 10, top_y, half, 130))
    draw_mol(d, {"formula": e["B"]["formula"], "atoms": e["B"]["atoms"],
                 "edges": e["B"]["edges"], "place": e["B"]["place"]},
             (x + 20 + half, top_y, half, 130))
    d.text((x + 14, top_y + 132), e["A"]["formula"], font=font(FONT_B, 14), fill="#333")
    d.text((x + 20 + half, top_y + 132), e["B"]["formula"], font=font(FONT_B, 14), fill="#333")
    d.text((x + w / 2 - 10, top_y + 108), "+", font=font(FONT_B, 22), fill="#111")
    d.line([x + w / 2, top_y + 160, x + w / 2, top_y + 195], fill="#333", width=3)
    d.polygon([(x + w / 2 - 7, top_y + 192), (x + w / 2 + 7, top_y + 192),
               (x + w / 2, top_y + 205)], fill="#333")
    # 产物
    n = len(e["products"])
    bw = (w - 20) // n
    for k, p in enumerate(e["products"]):
        px = x + 10 + k * bw
        draw_mol(d, p, (px, top_y + 215, bw - 6, 150))
        color = "#c0392b" if p["formula"] in e.get("new", []) else "#333"
        d.text((px + 6, top_y + 366), p["formula"], font=font(FONT_B, 14), fill=color)
        if p["formula"] in e.get("new", []):
            d.text((px + 6, top_y + 386), "★ 新物质", font=font(FONT_B, 13), fill="#c0392b")
    if not e.get("new"):
        d.text((x + 12, y + h - 26), "（产物都在大锅目录内）", font=font(FONT, 13), fill="#777")


def main():
    W, H = 1720, 1120
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 14), "自然环境分解规则 v2：产生新物质的反应类型（含价数分级，不含能量）",
           font=font(FONT_B, 27), fill="#111")
    d.text((24, 50), "★ 标出目录外新分子式；四类：合并（2→1）/ 交换（2→2）/ 裂解（2→≥3）；每类给出\"新\"与\"旧\"对照。",
           font=font(FONT, 15), fill="#555")
    cw, ch = 560, 470
    for i, (key, title) in enumerate(ORDER):
        r, c = divmod(i, 3)
        card(d, (24 + c * (cw + 18), 90 + r * (ch + 16), cw, ch), key, title)
    img.save(BASE + r"\images\t29_new_reactions.png")
    print("saved t29_new_reactions.png")

    # ---------------- 分类规律图 ----------------
    W2, H2 = 1600, 980
    img2 = Image.new("RGB", (W2, H2), "white")
    d2 = ImageDraw.Draw(img2)
    d2.text((24, 14), "产生新物质的分类规律（1500 个随机分子对的统计）", font=font(FONT_B, 27), fill="#111")

    d2.rounded_rectangle([24, 70, 1560, 130], radius=10, fill="#eef5ff", outline="#7aa7d9", width=2)
    d2.text((40, 86), "必要条件：至少 2 个分子含有同一个「全局最不稳定键类」；否则单分子只会复原，不产生任何反应。",
            font=font(FONT_B, 17), fill="#123")

    # 三个分支
    branches = [
        ("合并型 2→1", "70 例", "新 66", "旧 4",
         "碎片跨分子重连 → 合并成一个新的大分子", "#1e8449"),
        ("交换型 2→2", "104 例", "新 70", "旧 34",
         "两分子碎片互换 → 得到两个新组合（或一个旧+一个新）", "#b7791f"),
        ("裂解型 2→≥3", "8 例", "新 1", "旧 7",
         "断裂后形成更多小分子；小分子多为目录内物质", "#6c3483"),
    ]
    for k, (name, total, new, old, desc, col) in enumerate(branches):
        x = 24 + k * 520
        d2.rounded_rectangle([x, 170, x + 490, 340], radius=10, outline=col, width=3)
        d2.text((x + 18, 186), name, font=font(FONT_B, 24), fill=col)
        d2.text((x + 18, 226), f"变化反应数：{total}", font=font(FONT_B, 18), fill="#111")
        d2.text((x + 18, 258), f"产生新物质：{new}    仅旧物质：{old}", font=font(FONT, 16), fill="#333")
        d2.text((x + 18, 292), desc, font=font(FONT, 13), fill="#555")
    # 箭头
    for k in range(3):
        x = 24 + k * 520 + 245
        d2.line([x, 130, x, 168], fill="#333", width=3)
        d2.polygon([(x - 7, 162), (x + 7, 162), (x, 172)], fill="#333")

    # 断裂类分布
    d2.text((24, 380), "按「断裂类」统计（182 个变化反应）：", font=font(FONT_B, 20), fill="#111")
    rows = [
        ("(d=0, m=1, v=3)：三价骨架的同元素单键", "84"),
        ("(d=0, m=1, v=2)：二价的同元素单键", "68"),
        ("(d=3, m=1, v=1)：1 价端键（远距离）", "9"),
        ("(d=1/2/4, m=1, v=1)：1 价端键", "15"),
        ("(d=1, m=1, v=2)：二价端键", "4"),
        ("(d=0, m=2, v=3)：三价同元素双键", "2"),
    ]
    y = 420
    for r in rows:
        d2.text((40, y), r[0], font=font(FONT, 16), fill="#333")
        d2.text((900, y), r[1], font=font(FONT_B, 16), fill="#111")
        y += 34

    # 规律总结
    d2.text((24, 640), "分类规律总结：", font=font(FONT_B, 20), fill="#111")
    laws = [
        "① 新物质只能来自「分子间碎片重连」：单分子断裂后会被大锅规则原样补回（复原），不产生新物质。",
        "② 断裂类决定哪些原子被释放：d=0 同元素键（尤其 v=3 骨架键、v=2 二价键）是主要来源；d 越大的 1 价端键参与越少。",
        "③ 产物分子数变化是最干净的分类轴：合并（2→1）与交换（2→2）是产生新物质的主要方式；裂解（2→≥3）几乎只得到目录内小分子。",
        "④ 是否成为「新物质」取决于重结合的大锅贪心：碎片优先形成高距离跨类键；若最终分子式与原分子不同 → 新物质，相同 → 复原/旧物质。",
        "⑤ 经验分布（1500 对）：复原 1318（87.9%）；变化 182（12.1%），其中产生新分子式 137（占变化 75.3%）；合并/交换是主力（136/137）。",
    ]
    y = 680
    for law in laws:
        d2.text((40, y), law, font=font(FONT, 15), fill="#222")
        y += 40
    img2.save(BASE + r"\images\t29_new_classification.png")
    print("saved t29_new_classification.png")


if __name__ == "__main__":
    main()
