# -*- coding: utf-8 -*-
"""t12b_figs.py —— T12B 图（PIL，无 matplotlib）。输出 t12b_*.png。"""
import json

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
W, H = 1200, 620
BG = "#ffffff"
FG = "#222222"
BAR = "#2e86c1"
BAR2 = "#c0392b"
GRID = "#dddddd"


def F(sz):
    return ImageFont.truetype(FONT_PATH, sz)


def hbar(draw, x0, y0, w, h, frac, color):
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill="#f0f0f0")
    draw.rectangle([x0, y0, x0 + int(w * frac), y0 + h], fill=color)


def fig_classification(S, path):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    f1, f2, f3 = F(30), F(20), F(18)
    d.text((40, 24), "T12B 全物质两两反应：结果分类（7,728,346 对）", font=f1, fill=FG)
    cls = S["classification"]
    tp = cls["total"]
    items = [("失败（不相容）", cls["fail"], BAR2),
             ("惰性（原样返回）", cls["inert"], "#f39c12"),
             ("单产物（化合）", cls["single"], "#27ae60"),
             ("多产物（复分解）", cls["multi"], BAR)]
    if cls.get("unresolved"):
        items.append(("未判定（超时）", cls["unresolved"], "#7f8c8d"))
    y = 110
    maxw = 660
    for name, v, color in items:
        d.text((40, y), name, font=f2, fill=FG)
        frac = v / tp if tp else 0
        hbar(d, 300, y + 2, maxw, 34, frac, color)
        d.text((300 + maxw + 14, y + 8), f"{v:,}  ({frac*100:.2f}%)", font=f3, fill=FG)
        y += 78
    d.text((40, y + 20), "结论：成功占绝大多数；多产物是常态，单产物仅少数；失败极少。",
           font=f2, fill="#555555")
    im.save(path)
    print("saved", path)


def fig_product_size(S, path):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    f1, f2, f3 = F(30), F(20), F(17)
    d.text((40, 24), "T12B 产物分子大小分布（出现次数，对数加权）", font=f1, fill=FG)
    h = S["product_size"]["size_hist"]
    keys = sorted(int(k) for k in h)
    vals = [h[str(k)] for k in keys]
    total = sum(vals) or 1
    x0, y0, pw, ph = 90, 110, 1080, 400
    # 坐标轴
    d.line([x0, y0 + ph, x0 + pw, y0 + ph], fill="#888888", width=2)
    d.line([x0, y0, x0, y0 + ph], fill="#888888", width=2)
    nb = len(keys)
    bw = pw // max(nb, 1)
    mx = max(vals)
    for t, k in enumerate(keys):
        v = vals[t]
        bh = int(ph * v / mx) if mx else 0
        bx = x0 + t * bw + bw * 0.12
        d.rectangle([bx, y0 + ph - bh, bx + bw * 0.76, y0 + ph], fill=BAR)
        d.text((bx - 2, y0 + ph + 8), str(k), font=f3, fill=FG)
        if v / total > 0.02 or k in (2, 16):
            d.text((bx - 6, y0 + ph - bh - 24), f"{v*100/total:.1f}%", font=F(14), fill="#444444")
    d.text((x0 + pw - 180, y0 + ph + 34), "产物原子数 →", font=f2, fill=FG)
    d.text((40, 560), f"共 {S['product_size']['n_products_total']:,} 个产物分子（按反应对数加权；"
                      f"总原子数守恒违例 {S['product_size']['conservation_bad_pairs']} 对）。",
           font=f2, fill="#555555")
    im.save(path)
    print("saved", path)


def fig_sets2(S, path):
    """三价元素组合（O/P/K 出现与否）的失败率 / 惰性率。"""
    im = Image.new("RGB", (W, 700), BG)
    d = ImageDraw.Draw(im)
    f1, f2, f3 = F(28), F(19), F(18)
    d.text((40, 20), "T12B 三价元素组合：失败率 / 惰性率 / 多产物率", font=f1, fill=FG)
    items = S.get("triv_combo", [])
    x0, y0, pw, ph = 90, 110, 1050, 440
    d.line([x0, y0 + ph, x0 + pw, y0 + ph], fill="#888888", width=2)
    d.line([x0, y0, x0, y0 + ph], fill="#888888", width=2)
    n = len(items)
    bw = pw / max(n, 1)
    mx = max([x["fail_rate"] for x in items] + [0.01])
    for t, it in enumerate(items):
        fr, ir, mr = it["fail_rate"], it["inert_rate"], it["multi_rate"]
        bx = x0 + t * bw + bw * 0.12
        h_f = int(ph * 0.85 * fr / mx)
        d.rectangle([bx, y0 + ph - h_f, bx + bw * 0.2, y0 + ph], fill=BAR2)
        d.rectangle([bx + bw * 0.24, y0 + ph - int(ph * 0.85 * ir), bx + bw * 0.44, y0 + ph],
                    fill="#f39c12")
        d.rectangle([bx + bw * 0.48, y0 + ph - int(ph * 0.85 * mr), bx + bw * 0.68, y0 + ph],
                    fill=BAR)
        d.text((bx - 6, y0 + ph - h_f - 22), f"{fr*100:.1f}%", font=F(15), fill="#7b241c")
        label = it["key"] if it["key"] != "无" else "无三价"
        d.text((bx + 2, y0 + ph + 8), label, font=f3, fill=FG)
        d.text((bx - 2, y0 + ph + 32), f"{it['pairs']:,}", font=F(12), fill="#777777")
    d.text((x0 + pw - 260, y0 + ph + 60), "红=失败率  橙=惰性率  蓝=多产物率（柱高按各自比例）",
           font=f2, fill="#555555")
    im.save(path)
    print("saved", path)


def main():
    S = json.load(open(BASE + r"\t12b_summary.json", encoding="utf-8"))
    fig_classification(S, BASE + r"\t12b_classification.png")
    fig_product_size(S, BASE + r"\t12b_product_size.png")
    fig_sets2(S, BASE + r"\t12b_sets2.png")


if __name__ == "__main__":
    main()
