# -*- coding: utf-8 -*-
"""t33_render.py：温度阈值问题示例图"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
from t28_render import draw_mol, font, FONT, FONT_B, panel

BASE = r"G:\AI work\deepseek\work1\alchemy"
d0 = json.load(open(BASE + r"\t33_fig_data.json", encoding="utf-8"))


def main():
    W, H = 1640, 980
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 12), "温度阈值问题：一方达完全阈值、另一方只达不完全阈值，接触会怎样？",
           font=font(FONT_B, 26), fill="#111")
    d.text((24, 48), "结论：发生「不完全反应」。完全反应需要所有参与者都达到各自的完全阈值；单方面的超额温度不能替代对方缺失的断键能力。",
           font=font(FONT, 15), fill="#555")

    # 温度轴
    axis_y = 160
    x0, x1 = 120, 1520
    d.line([x0, axis_y, x1, axis_y], fill="#333", width=4)
    for t in range(0, 7):
        x = x0 + (x1 - x0) * t / 6
        d.line([x, axis_y - 8, x, axis_y + 8], fill="#333", width=2)
        d.text((x - 6, axis_y + 14), str(t), font=font(FONT_B, 14), fill="#333")
    d.text((x1 - 30, axis_y + 40), "温度 T", font=font(FONT_B, 15), fill="#333")
    # 阈值标记
    marks = [(1, "i(A)=i(B)=1"), (3, "c(A)=3"), (5, "c(B)=5")]
    for t, lab in marks:
        x = x0 + (x1 - x0) * t / 6
        d.line([x, axis_y - 70, x, axis_y - 10], fill="#c0392b", width=2)
        d.text((x - 40, axis_y - 65), lab, font=font(FONT_B, 13), fill="#c0392b")
    # 区域
    def xpos(t):
        return x0 + (x1 - x0) * t / 6
    d.rectangle([xpos(0), axis_y + 60, xpos(1), axis_y + 100], fill="#eeeeee")
    d.text((xpos(0) + 10, axis_y + 70), "0：无反应", font=font(FONT, 14), fill="#333")
    d.rectangle([xpos(1), axis_y + 60, xpos(5), axis_y + 100], fill="#dff0d8")
    d.text((xpos(1) + 10, axis_y + 70), "1 ≤ T < 5：不完全反应", font=font(FONT_B, 14), fill="#1e8449")
    d.rectangle([xpos(5), axis_y + 60, xpos(6), axis_y + 100], fill="#fde0dc")
    d.text((xpos(5) + 10, axis_y + 70), "T ≥ 5：完全反应", font=font(FONT_B, 14), fill="#c0392b")
    # T=3 标记
    d.line([xpos(3), axis_y + 110, xpos(3), axis_y + 150], fill="#b7791f", width=3)
    d.text((xpos(3) - 50, axis_y + 152), "T=3：题述情形", font=font(FONT_B, 14), fill="#b7791f")

    # 左侧：A、B
    panel(d, (24, 330, 520, 330))
    d.text((36, 340), "两个物质", font=font(FONT_B, 20), fill="#111")
    d.text((36, 368), "A = W2A：总键数 c(A)=3，不完全断键 i(A)=1", font=font(FONT, 14), fill="#333")
    d.text((36, 392), "B = WA3F2：总键数 c(B)=5，不完全断键 i(B)=1", font=font(FONT, 14), fill="#333")
    draw_mol(d, d0["A"], (36, 420, 230, 200))
    draw_mol(d, d0["B"], (290, 420, 240, 200))
    d.text((36, 625), "W2A", font=font(FONT_B, 14), fill="#333")
    d.text((290, 625), "WA3F2", font=font(FONT_B, 14), fill="#333")

    # 右上：T=3 不完全
    panel(d, (560, 330, 520, 330))
    d.text((572, 340), "T=3：不完全反应", font=font(FONT_B, 20), fill="#1e8449")
    d.text((572, 368), "A 达完全阈值，B 只达不完全阈值", font=font(FONT, 14), fill="#333")
    prods = d0["incomplete"]
    bw = 480 // max(1, len(prods))
    for i, p in enumerate(prods):
        draw_mol(d, p, (572 + i * bw, 400, bw - 10, 200))
        d.text((572 + i * bw + 4, 604), p["formula"], font=font(FONT_B, 14), fill="#c0392b")
    d.text((572, 628), "结果：只生成不完全产物（A 的完全能力被\"浪费\"）", font=font(FONT, 13), fill="#555")

    # 右下：T=5 完全
    panel(d, (1096, 330, 520, 330))
    d.text((1108, 340), "T=5：完全反应", font=font(FONT_B, 20), fill="#c0392b")
    d.text((1108, 368), "双方都达到完全阈值", font=font(FONT, 14), fill="#333")
    prods = d0["complete"]
    bw = 480 // max(1, len(prods))
    for i, p in enumerate(prods):
        draw_mol(d, p, (1108 + i * bw, 400, bw - 10, 200))
        d.text((1108 + i * bw + 4, 604), p["formula"], font=font(FONT_B, 13), fill="#333")
    d.text((1108, 628), "结果：大锅完全产物", font=font(FONT, 13), fill="#555")

    # 底部解释
    d.rounded_rectangle([24, 680, 1616, 950], radius=10, fill="#fbfbfb", outline="#ccc", width=2)
    d.text((40, 692), "方案与原因：", font=font(FONT_B, 20), fill="#111")
    lines = [
        "① 反应模式 = 所有接触参与者的「共同能力」：若所有人都满足完全阈值 → 完全反应；否则若所有人都满足不完全阈值 → 不完全反应；否则不反应。",
        "② 题述 T=3 时：B 的完全阈值 5 未达到，完整大锅反应无法拆开 B 的全部键，因此不能进行完全反应；但双方不完全阈值 1 都满足，所以进行不完全反应。",
        "③ 不做\"A 完全 + B 不完全\"的混合模式：完全反应要求所有原子全部解锁；只对 A 完全断键、B 部分断键不是任何已定义的反应，会破坏能量/阈值一致性。",
        "④ 不保持\"不反应\"：双方不完全阈值已满足且接触，没有理由被 B 的较高完全阈值阻断；温度是\"能力\"，不是\"触发开关\"。",
        "⑤ 若 A 是不稳定物质且 T≥c(A)，它可以在接触反应之外单独自分解（M→F(v_M)）；若 A 已被不完全反应用掉，则不再单独自分解。",
    ]
    y = 730
    for s in lines:
        d.text((40, y), s, font=font(FONT, 14), fill="#222")
        y += 40
    img.save(BASE + r"\images\t33_temperature_threshold.png")
    print("saved t33_temperature_threshold.png")


if __name__ == "__main__":
    main()
