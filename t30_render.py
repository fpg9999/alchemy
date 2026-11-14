# -*- coding: utf-8 -*-
"""t30_render.py：不稳定物质自分解规则图"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
from t28_render import draw_mol, font, FONT, FONT_B, panel

BASE = r"G:\AI work\deepseek\work1\alchemy"
data = json.load(open(BASE + r"\t30_fig_data.json", encoding="utf-8"))


def main():
    W, H = 1720, 920
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 14), "不稳定物质的自分解规则：M → F(v_M)（完全大锅反应）",
           font=font(FONT_B, 28), fill="#111")
    d.text((24, 52), "不稳定物质定义：F(v_M) ≠ {M}（不是大锅完全产物）。满足条件时，分子按自身元素向量重跑完整大锅反应；产物都是大锅可产物、且为 F 不动点。",
           font=font(FONT, 15), fill="#555")

    # 左：不稳定分子
    panel(d, (24, 100, 470, 460))
    d.text((36, 110), "不稳定物质 M", font=font(FONT_B, 20), fill="#c0392b")
    d.text((36, 138), "XCP2WLK2A（目录外）", font=font(FONT, 15), fill="#333")
    draw_mol(d, data["M"], (34, 170, 450, 350))
    d.text((36, 520), "它是自然环境下产生的新物质，不是大锅可产物。",
           font=font(FONT, 14), fill="#555")

    # 中间：条件箭头
    panel(d, (520, 100, 360, 460))
    d.text((532, 110), "触发条件（任选其一）", font=font(FONT_B, 19), fill="#111")
    conds = [
        "① 完全反应场：接触大锅 / 恒素 E / 高温",
        "② 时间条件：在自然环境中存在足够长时间",
        "③ 概率条件：每个时间步以概率 p 自分解",
        "④ 不稳定度阈值：U(M) ≥ θ",
        "",
        "稳定物质（F 不动点）在任何条件下都不自分解。",
    ]
    y = 150
    for c in conds:
        d.text((532, y), c, font=font(FONT, 14), fill="#333")
        y += 34
    d.line([540, 400, 850, 400], fill="#333", width=4)
    d.polygon([(840, 392), (840, 408), (858, 400)], fill="#333")
    d.text((560, 420), "M → F(v_M)", font=font(FONT_B, 22), fill="#111")

    # 右：产物
    panel(d, (900, 100, 790, 460))
    d.text((912, 110), "自分解产物（全部为大锅可产物质、F 不动点）",
           font=font(FONT_B, 18), fill="#1e8449")
    prods = data["products"]
    n = len(prods)
    cols = 2
    rows = (n + cols - 1) // cols
    bw = 370
    bh = 180
    for k, p in enumerate(prods):
        r, c = divmod(k, cols)
        x = 912 + c * (bw + 10)
        y = 145 + r * (bh + 10)
        panel(d, (x, y, bw, bh))
        draw_mol(d, p, (x + 4, y + 4, bw - 8, bh - 34))
        d.text((x + 8, y + bh - 30), p["formula"], font=font(FONT_B, 15), fill="#333")
        d.text((x + bw - 100, y + bh - 30), "稳定", font=font(FONT_B, 13), fill="#1e8449")

    # 底部统计
    d.text((24, 590), "验证数据（143 种自然反应新物质，全部做完整大锅反应）：",
           font=font(FONT_B, 19), fill="#111")
    stats = [
        "143/143：全部完全转化为别的物质（没有任何一个新物质在 F 中保留自己）",
        "143/143：全部产物的分子式都在大锅目录中（即大锅可产物）",
        "产物个数分布：2 个 47 种、3 个 28 种、4 个 25 种、5 个 15 种、6 个 21 种、7 个 4 种、8 个 3 种",
        "目录物质 F 不动点抽样：80/80；自分解产物再作用 F：30/30 仍为自身（一步收敛）",
    ]
    y = 630
    for s in stats:
        d.text((40, y), s, font=font(FONT, 15), fill="#333")
        y += 34

    d.rounded_rectangle([24, 790, 1690, 890], radius=10, fill="#f7f7f7", outline="#ccc", width=1)
    d.text((40, 800), "规则保证：不稳定物质在满足条件时 → 完全大锅反应 → 产物是大锅可产物（F 不动点）→ 不会继续自分解。",
           font=font(FONT_B, 16), fill="#111")
    d.text((40, 832), "因此所有可能的不稳定物质最终都能被\"清空\"，自然环境中只剩大锅可产出的稳定物质。",
           font=font(FONT_B, 16), fill="#1e8449")
    img.save(BASE + r"\images\t30_self_decomposition.png")
    print("saved t30_self_decomposition.png")


if __name__ == "__main__":
    main()
