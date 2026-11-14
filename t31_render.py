# -*- coding: utf-8 -*-
"""t31_render.py：多分子不完全反应示例图 + 统计规律图"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
from t28_render import draw_mol, font, FONT, FONT_B, panel

BASE = r"G:\AI work\deepseek\work1\alchemy"
ex = json.load(open(BASE + r"\t31_examples_geo.json", encoding="utf-8"))


def draw_card(d, box, title, data, new_color="#c0392b"):
    x, y, w, h = box
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, outline="#999", width=2)
    d.text((x + 12, y + 8), title, font=font(FONT_B, 18), fill="#111")
    d.text((x + 12, y + 32), f"k={data['k']}，断裂类 d={data['class'][0]}, m={-data['class'][1]}, v={data['class'][2]}；"
                             f"总原子 {data['atoms']}", font=font(FONT, 13), fill="#666")
    inputs = data["inputs"]
    n = len(inputs)
    top_y = y + 58
    iw = (w - 20) // n
    ih = 120 if n <= 3 else 100
    for i, rec in enumerate(inputs):
        bx = x + 8 + i * iw
        draw_mol(d, rec, (bx, top_y, iw - 6, ih))
        d.text((bx + 4, top_y + ih + 2), rec["formula"], font=font(FONT_B, 13), fill="#333")
    d.line([x + w / 2, top_y + ih + 26, x + w / 2, top_y + ih + 56], fill="#333", width=3)
    d.polygon([(x + w / 2 - 7, top_y + ih + 52), (x + w / 2 + 7, top_y + ih + 52),
               (x + w / 2, top_y + ih + 64)], fill="#333")
    prods = data["products"]
    m = len(prods)
    pw = (w - 20) // m
    py = top_y + ih + 70
    ph = h - (py - y) - 46
    inh = [rec["formula"] for rec in inputs]
    for k, p in enumerate(prods):
        bx = x + 8 + k * pw
        draw_mol(d, p, (bx, py, pw - 6, ph - 18))
        is_new = p["formula"] in data.get("new", [])
        color = new_color if is_new else "#333"
        d.text((bx + 4, py + ph - 16), p["formula"], font=font(FONT_B, 13), fill=color)
        if is_new:
            d.text((bx + 4, py + ph - 32), "★新物质", font=font(FONT_B, 12), fill=color)
        elif p["formula"] in inh:
            d.text((bx + 4, py + ph - 32), "旁观/未变", font=font(FONT, 12), fill="#777")


def main():
    W, H = 1740, 1180
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 12), "自然环境不完全反应：两分子 vs 多分子（规则 v2，价数分级，不含能量）",
           font=font(FONT_B, 27), fill="#111")
    d.text((24, 48), "★ 标出目录外新物质；灰色\"旁观/未变\"表示该分子不含当前全局最不稳定键类，保持原样。",
           font=font(FONT, 14), fill="#555")
    draw_card(d, (24, 84, 560, 500), "① 两分子：交换型（产生新物质）", ex["pair_new"])
    draw_card(d, (600, 84, 560, 500), "② 三分子：部分参与（1 个旁观者）", ex["triple_partial_new"])
    draw_card(d, (1176, 84, 540, 500), "③ 三分子：全体参与合并成一个", ex["triple_all_to_one"])
    draw_card(d, (24, 600, 850, 545), "④ 四分子：两个旁观者 + 两分子合并", ex["quad_partial_new"])
    draw_card(d, (890, 600, 826, 545), "⑤ 五分子：三个旁观者 + 两分子合并", ex["quint_partial_new"])
    img.save(BASE + r"\images\t31_multi_examples.png")
    print("saved t31_multi_examples.png")

    # ---------------- 统计规律图 ----------------
    W2, H2 = 1600, 980
    img2 = Image.new("RGB", (W2, H2), "white")
    d2 = ImageDraw.Draw(img2)
    d2.text((24, 12), "两分子 vs 多分子：不完全反应的统计规律（每档 500 个体系）",
            font=font(FONT_B, 27), fill="#111")

    # 数据表
    rows = [
        ("分子数 k", "复原", "真正改变", "改变率", "产新物质", "产新率", "部分反应占比"),
        ("2", "459", "41", "8.2%", "27", "5.4%", "0%"),
        ("3", "428", "72", "14.4%", "52", "10.4%", "90.3%"),
        ("4", "410", "90", "18.0%", "62", "12.4%", "98.9%"),
        ("5", "386", "114", "22.8%", "80", "16.0%", "100%"),
    ]
    cols = [24, 160, 270, 400, 520, 650, 790]
    y = 70
    for r in rows:
        for c, txt in zip(cols, r):
            d2.text((c, y), txt, font=font(FONT_B if r is rows[0] else FONT, 16),
                    fill="#111" if r is rows[0] else "#333")
        y += 34

    # 条形图
    d2.text((24, 290), "反应率 / 产新率随分子数上升：", font=font(FONT_B, 19), fill="#111")
    base_y = 620
    max_h = 220
    for i, k in enumerate([2, 3, 4, 5]):
        x = 90 + i * 360
        vals = {2: (8.2, 5.4), 3: (14.4, 10.4), 4: (18.0, 12.4), 5: (22.8, 16.0)}[k]
        for j, (v, col, lab) in enumerate([(vals[0], "#5b8ff9", "改变率"), (vals[1], "#e8684a", "产新率")]):
            bh = v / 25 * max_h
            bx = x + j * 60
            d2.rectangle([bx, base_y - bh, bx + 42, base_y], fill=col)
            d2.text((bx, base_y - bh - 22), f"{v:.1f}%", font=font(FONT_B, 13), fill="#333")
            d2.text((bx, base_y + 6), lab, font=font(FONT, 12), fill="#555")
        d2.text((x + 30, base_y + 30), f"k={k}", font=font(FONT_B, 16), fill="#111")

    # 规律
    d2.text((24, 720), "规律总结：", font=font(FONT_B, 20), fill="#111")
    laws = [
        "① 反应率随分子数上升：k=2 8.2% → k=5 22.8%；产新率 5.4% → 16.0%。",
        "② 多分子反应绝大多数是「部分反应」：k≥3 时 90% 以上的变化只由其中一个子集完成，其余分子是旁观者。",
        "③ 典型的产物数 = k−1（两个分子合并，其余不动）；少数为 k（交换）；裂解（产物数>k）极罕见。",
        "④ 全体参与（所有输入分子都改变）极稀有：k=3 只有 7/500，k=4 1/500，k=5 0/500。",
        "⑤ 多分子体系会产生更大、更复杂的新物质（合并产物包含更多原子），新物质率显著高于两分子。",
        "⑥ 旁观者惰性：分子不含当前全局最不稳定键类时完全不变，因此多分子反应本质上仍是「局部两两反应」的集合。",
    ]
    y = 760
    for law in laws:
        d2.text((40, y), law, font=font(FONT, 15), fill="#222")
        y += 36
    img2.save(BASE + r"\images\t31_multi_stats.png")
    print("saved t31_multi_stats.png")


if __name__ == "__main__":
    main()
