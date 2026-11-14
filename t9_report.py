# -*- coding: utf-8 -*-
"""t9_report.py：只含一种三价元素（或无三价）的物质：分类统计 + 完整清单 + 图片"""
import json
import math
import sys
from collections import Counter, defaultdict
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t8_render_forms as R8
R8.BASE_FILL.update({
    "X": (240, 160, 75), "C": (127, 182, 232), "W": (201, 162, 39),
    "L": (255, 224, 102), "A": (143, 214, 192), "F": (224, 90, 79),
})
R8.CN.update({"X": "晶", "C": "冰", "W": "流", "L": "电", "A": "气", "F": "焰"})

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
CAT_NAME = {"none": "不含三价元素", "O": "只含秩 O", "P": "只含势 P", "K": "只含沌 K"}
FONT = R8.FONT
FONT_B = R8.FONT_B
font = R8.font
text_center = R8.text_center
draw_formula = R8.draw_formula


def rep_forms(cat_list, k=15):
    """每类选 k 个代表：优先覆盖不同"其它元素集合"，再按原子数从小到大"""
    seen_sets = set()
    out = []
    # 先按 (其它元素种类数, 原子数, 公式) 排序
    def others(r):
        return frozenset(set(r["atoms"]) - TRI)
    for r in sorted(cat_list, key=lambda r: (len(others(r)), r["natoms"], r["formula"])):
        s = others(r)
        if s in seen_sets:
            continue
        seen_sets.add(s)
        out.append(r)
        if len(out) >= k:
            break
    return out


def to_form(r):
    n = len(r["atoms"])
    return {"atoms": r["atoms"], "edges": [tuple(e) for e in r["edges"]],
            "rems": [0] * n, "place": {int(k): tuple(v) for k, v in r["place"].items()},
            "formula": r["formula"], "size": n, "active": 0,
            "rem_dist": {0: n}, "types": "".join(sorted(set(r["atoms"])))}


def panel(img, d, box, form, idx):
    x0, y0, w, h = box
    d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dddddd", width=1)
    d.text((x0 + 8, y0 + 6), f"{idx:02d}", font=font(FONT_B, 15), fill="#999999")
    text_center(d, x0 + w - 40, y0 + 14, f"{form['size']}原子", font(FONT, 13), "#999999")
    R8.draw_form(d, form, (x0 + 4, y0 + 22, w - 8, h - 62))
    draw_formula(d, x0 + w / 2, y0 + h - 42, form["formula"], 24, "#111111")


def make_page(path, title, subtitle, forms, ncol=5, pw=300, ph=310):
    nrow = (len(forms) + ncol - 1) // ncol
    left, top = 26, 120
    W = left + ncol * pw + 22
    H = top + nrow * ph + 26
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 14), title, font=font(FONT_B, 27), fill="#111111")
    d.text((26, 52), subtitle, font=font(FONT, 17), fill="#555555")
    d.text((26, 78), "物质（最终分子，所有键已满）：红=短键S、绿=角键C、紫虚线=长键L（虚线格为中间空格）；格内大写字母=元素符号。",
           font=font(FONT, 15), fill="#888888")
    for i, f in enumerate(forms):
        r, c = divmod(i, ncol)
        panel(img, d, (left + c * pw + 3, top + r * ph + 3, pw - 6, ph - 6), f, i + 1)
    img.save(path)
    print("saved", path)


def bar_chart(path):
    cats = ["none", "O", "P", "K"]
    img = Image.new("RGB", (1200, 500), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 14), "只含一种三价元素（或无三价元素）的物质数量", font=font(FONT_B, 26), fill="#111")
    d.text((24, 50), "数据源：t4_catalog_all_validated.json（权威目录；≤16 原子完备，>16 原子为已找到下界）",
           font=font(FONT, 16), fill="#666")
    vals = counts
    mx = max(vals.values())
    x = 80
    base = 430
    for cat in cats:
        v = vals[cat]
        h = int(300 * v / mx)
        col = {"none": "#888888", "O": "#6bbf6b", "P": "#f082b9", "K": "#966ede"}[cat]
        d.rectangle([x, base - h, x + 150, base], fill=col)
        text_center(d, x + 75, base - h - 18, str(v), font(FONT_B, 20), "#111")
        text_center(d, x + 75, base + 22, CAT_NAME[cat], font(FONT, 18), "#333")
        x += 230
    d.line([50, base, 1150, base], fill="#333", width=2)
    img.save(path)
    print("saved", path)


def natoms_chart(path):
    img = Image.new("RGB", (1200, 520), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 14), "各类物质的原子数分布（2~16 为主；>16 为已找到的少量大分子）",
           font=font(FONT_B, 24), fill="#111")
    d.text((24, 48), "灰色=不含三价；绿=只含秩；粉=只含势；紫=只含沌（同原子数处并列）",
           font=font(FONT, 16), fill="#666")
    hist = {c: Counter(r["natoms"] for r in cat_lists[c]) for c in cat_lists}
    xs = list(range(2, 17))
    mx = max(hist[c].get(n, 0) for c in hist for n in xs) or 1
    x0, y0, w, h = 70, 100, 1080, 340
    bw = w / len(xs)
    for i, n in enumerate(xs):
        x = x0 + i * bw
        parts = [("none", "#888888"), ("O", "#6bbf6b"), ("P", "#f082b9"), ("K", "#966ede")]
        acc = 0
        for c, col in parts:
            v = hist[c].get(n, 0)
            bh = h * v / mx
            if bh > 0:
                d.rectangle([x + 4, y0 + h - acc - bh, x + bw - 4, y0 + h - acc], fill=col)
            acc += bh
        text_center(d, x + bw / 2, y0 + h + 18, str(n), font(FONT, 15), "#333")
    d.line([x0, y0 + h, x0 + w, y0 + h], fill="#333", width=2)
    img.save(path)
    print("saved", path)


if __name__ == "__main__":
    data = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
    cat_lists = {c: data[c] for c in ["none", "O", "P", "K"]}
    counts = {c: len(cat_lists[c]) for c in cat_lists}
    print("counts:", counts, "total:", sum(counts.values()))

    # ---------- Markdown 报告 ----------
    L = []
    L.append("# T9 · 只含一种三价元素（或无三价元素）的全部物质\n")
    L.append("> 数据源：`t4_catalog_all_validated.json`（84,225 条权威目录）。")
    L.append("> 口径：按分子式统计；只保留「三价元素种类数 ≤ 1」的物质。")
    L.append("> 完备性：≤16 原子部分完备；>16 原子的物质只包含目录中已找到的合法分子（PROJECT_HANDOFF §9）。\n")
    L.append("## 总览\n")
    L.append("| 类别 | 物质数 | 原子数范围 |")
    L.append("|---|---|---|")
    for c in ["none", "O", "P", "K"]:
        ns = [r["natoms"] for r in cat_lists[c]]
        L.append(f"| {CAT_NAME[c]} | {counts[c]} | {min(ns)}~{max(ns)} |")
    L.append(f"| **合计** | **{sum(counts.values())}** | |\n")
    L.append("## 子分类（按出现的其它元素组合）\n")
    for c in ["none", "O", "P", "K"]:
        sub = Counter()
        for r in cat_lists[c]:
            others = "".join(sorted(set(r["atoms"]) - TRI)) or "(纯三价)"
            sub[others] += 1
        L.append(f"### {CAT_NAME[c]}\n")
        L.append("| 其它元素 | 数量 |")
        L.append("|---|---|")
        for k, v in sorted(sub.items(), key=lambda kv: (len(kv[0]), kv[0])):
            L.append(f"| {k} | {v} |")
        L.append("")
    L.append("## 完整物质清单\n")
    for c in ["none", "O", "P", "K"]:
        L.append(f"### {CAT_NAME[c]}（{counts[c]} 种，按原子数、字母序）\n")
        L.append("```")
        for r in cat_lists[c]:
            L.append(r["formula"])
        L.append("```\n")
    open(BASE + r"\T9_SINGLE_TRIVALENT.md", "w", encoding="utf-8").write("\n".join(L))
    print("saved T9_SINGLE_TRIVALENT.md")

    # ---------- 图片 ----------
    bar_chart(BASE + r"\t9_overview_counts.png")
    natoms_chart(BASE + r"\t9_natoms_hist.png")
    for c in ["none", "O", "P", "K"]:
        reps = [to_form(r) for r in rep_forms(cat_lists[c], 15)]
        make_page(BASE + rf"\t9_reps_{c}.png",
                  f"{CAT_NAME[c]}：代表性物质（{counts[c]} 种中选 {len(reps)} 种，覆盖不同元素组合）",
                  "每类优先挑「不同其它元素组合 + 最小原子数」的代表。",
                  reps)
