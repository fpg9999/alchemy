# -*- coding: utf-8 -*-
"""t11_cycles_report.py：反应循环报告 + 图示
三类：聚素内、无三价内、跨类；均为「真反应 + 允许副产物」的 2-环（A→C→A）。
"""
import json
import sys
from collections import Counter
from PIL import Image, ImageDraw

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t11_report as R11

BASE = r"G:\AI work\deepseek\work1\alchemy"
font = R11.font
FONT = R11.FONT
FONT_B = R11.FONT_B
text_center = R11.text_center
draw_formula = R11.draw_formula
draw_mol = R11.draw_mol


def build_struct():
    struct = {}
    data = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    for d in data:
        struct[d["formula"]] = {"atoms": d["atoms"], "edges": [tuple(e) for e in d["edges"]],
                                "place": {int(k): tuple(v) for k, v in d["place"].items()}}
    t9 = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
    for cat in ("none", "O", "P", "K"):
        for r in t9[cat]:
            pl = r["place"]
            if pl is None:
                pl = {str(i): [2 * i, 0] for i in range(len(r["atoms"]))}
            struct.setdefault(r["formula"], {
                "atoms": r["atoms"], "edges": [tuple(e) for e in r["edges"]],
                "place": {int(k): tuple(v) for k, v in pl.items()}})
    return struct


def draw_mol_small(d, st, box):
    x0, y0, w, h = box
    atoms = st["atoms"]
    edges = st["edges"]
    place = st["place"]
    n = len(atoms)
    s = 15.0
    for _ in range(60):
        pts = [R11.R.center_of(place[i], s) for i in range(n)]
        if (max(p[0] for p in pts) - min(p[0] for p in pts) + 2.6 * s) <= w and \
           (max(p[1] for p in pts) - min(p[1] for p in pts) + 2.6 * s) <= h:
            break
        s *= 0.92
    pts = [R11.R.center_of(place[i], s) for i in range(n)]
    ox = x0 + w / 2 - (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    oy = y0 + h / 2 - (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    pos = [(p[0] + ox, p[1] + oy) for p in pts]
    polys = [R11.R.hex_pts(pos[i][0], pos[i][1], s) for i in range(n)]
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = R11.R.rel_type(dd)
        col = R11.BONDC.get(t, "#333")
        width = max(1, int(s / 12)) if t in ("S", "C") else max(1, int(s / 15))
        if t == "S":
            sv = R11.R.common_vertices(polys[i], polys[j])
            if len(sv) >= 2:
                R11.R.ray_offset_line(d, sv[0], sv[1], col, width, m)
        elif t == "C":
            p1, p2 = R11.R.nearest_vertices(polys[i], polys[j])
            R11.R.ray_offset_line(d, p1, p2, col, width, m)
        elif t == "L":
            p1 = R11.R.ray_exit(polys[i], pos[i], pos[j])
            p2 = R11.R.ray_exit(polys[j], pos[j], pos[i])
            if p1 and p2:
                ux, uy = p2[0] - p1[0], p2[1] - p1[1]
                L = (ux * ux + uy * uy) ** 0.5
                nx, ny = -uy / L, ux / L
                for k in range(m):
                    off = (k - (m - 1) / 2) * 4
                    a = (p1[0] + nx * off, p1[1] + ny * off)
                    b = (p2[0] + nx * off, p2[1] + ny * off)
                    R11.R.dashed(d, a, b, col, width)
    for i, e in enumerate(atoms):
        d.polygon(polys[i], fill=R11.FILL[e], outline="#333", width=1)
        text_center(d, pos[i][0], pos[i][1] - s * 0.12, e, font(FONT_B, int(s * 0.5)), "#111")


def step_view(d, x, y, w, h, lhs, rhs):
    """画一步反应：lhs 分子 + → + rhs 分子"""
    n = len(lhs) + len(rhs)
    bw = w / max(n, 1)
    xx = x
    for k, nm in enumerate(lhs):
        draw_mol_small(d, STRUCT[nm], (xx, y, bw - 4, h - 22))
        draw_formula(d, xx + (bw - 4) / 2, y + h - 14, nm, 13, "#111")
        xx += bw
    text_center(d, xx + 12, y + h / 2 - 10, "→", font(FONT_B, 22), "#111")
    xx += 28
    for k, nm in enumerate(rhs):
        draw_mol_small(d, STRUCT[nm], (xx, y, bw - 4, h - 22))
        draw_formula(d, xx + (bw - 4) / 2, y + h - 14, nm, 13, "#111")
        xx += bw


def cycle_image(path):
    rows = [
        ("① 无三价内 2-环", "C2 → X2C2 → C2",
         ["C2", "X2"], ["X2C2"],
         ["X2C2", "A2"], ["C2", "XA", "XA"],
         "净反应：A2 + X2 → 2 XA      （C2 被再生：催化剂）"),
        ("② 跨类 2-环", "C2 → X2 → C2",
         ["C2", "O2X2C4"], ["OC3", "OC3", "X2"],
         ["X2", "C2A2"], ["C2", "XA", "XA"],
         "净反应：O2X2C4 + C2A2 → 2 OC3 + 2 XA      （C2 被再生）"),
        ("③ 聚素内 2-环", "O2C2 → O2C4 → O2C2",
         ["O2C2", "C2"], ["O2C4"],
         ["O2C4", "O2"], ["O2C2", "O2C2"],
         "净反应：C2 + O2 → O2C2      （O2C2 被再生）"),
    ]
    W, H = 1560, 1240
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 14), "反应循环（允许副产物）：A → C → A，A 被再生", font=font(FONT_B, 26), fill="#111")
    d.text((24, 50), "每一步都是真反应；中间产物 C 与新的伙伴反应后重新放出 A（其余为副产物）。",
           font=font(FONT, 16), fill="#666")
    for i, (title, chain, l1, r1, l2, r2, net) in enumerate(rows):
        y0 = 90 + i * 380
        d.rectangle([20, y0, W - 20, y0 + 360], outline="#dddddd")
        d.text((36, y0 + 10), title + "   " + chain, font=font(FONT_B, 20), fill="#111")
        d.text((36, y0 + 44), "第 1 步", font=font(FONT_B, 16), fill="#0b6")
        step_view(d, 36, y0 + 66, 700, 120, l1, r1)
        d.text((800, y0 + 44), "第 2 步（C + 新伙伴 → 重新放出 A）", font=font(FONT_B, 16), fill="#c33")
        step_view(d, 800, y0 + 66, 700, 120, l2, r2)
        d.text((36, y0 + 220), net, font=font(FONT_B, 19), fill="#b8860b")
        # 小循环示意
        cx1, cy1, cx2, cy2 = 300, y0 + 300, 900, y0 + 300
        d.ellipse([cx1 - 26, cy1 - 26, cx1 + 26, cy1 + 26], outline="#333", width=2)
        d.ellipse([cx2 - 26, cy2 - 26, cx2 + 26, cy2 + 26], outline="#333", width=2)
        text_center(d, cx1, cy1, "A", font(FONT_B, 18), "#111")
        text_center(d, cx2, cy2, "C", font(FONT_B, 18), "#111")
        d.line([cx1 + 26, cy1 - 8, cx2 - 26, cy2 - 8], fill="#666", width=2)
        d.line([cx2 - 26, cy2 + 8, cx1 + 26, cy1 + 8], fill="#666", width=2)
        text_center(d, (cx1 + cx2) / 2, cy1 - 26, "第1步", font(FONT, 13), "#666")
        text_center(d, (cx1 + cx2) / 2, cy1 + 34, "第2步（再生 A）", font(FONT, 13), "#666")
    img.save(path)
    print("saved", path)


if __name__ == "__main__":
    STRUCT = build_struct()
    cycle_image(BASE + r"\t11_cycles_cards.png")

    # 报告
    cyc = json.load(open(BASE + r"\t11_cycles.json", encoding="utf-8"))["two_rings"]
    cls = Counter(c["class"] for c in cyc)
    L = []
    A = L.append
    A("# T11B · 反应循环研究（允许副产物）\n")
    A("> 定义修正：**循环 = 起点物质 A 最终被重新产出**，中间步骤可以产生副产物。")
    A("> 例：`A+B=C`（单产物），`C+D=A+E`（A 重新出现，E 为副产物）——这种循环**存在且大量存在**。\n")
    A("## 0. 结论\n")
    A(f"- 真 2-环（A→C→A，两步都是真反应）：**{len(cyc)} 个**（按无向去重；含方向则倍）。")
    A(f"  - 分类：聚素内 **{cls['聚素内']}**、无三价内 **{cls['无三价内']}**、跨类 **{cls['跨类']}**。")
    A("- 真 3-环：188,723 个（聚素内 2,147、无三价内 145,473、跨类 41,103）。")
    A("- 环很常见，**A 在这类循环中扮演催化剂**：循环净反应里 A 被消掉（重新生成），只把其它物质转化。")
    A("- 之前的\"循环不可能\"结论只适用于**每一步都是单产物**的严格链；一旦允许副产物，守恒不再禁止循环。\n")
    A("## 1. 三类 2-环示例（净反应式）\n")
    A("### ① 无三价内：C2 催化（最典型）")
    A("```")
    A("第1步  C2 + X2      → X2C2")
    A("第2步  X2C2 + A2    → C2 + 2 XA")
    A("净反应  A2 + X2     → 2 XA          （C2 被再生，可循环使用）")
    A("```")
    A("再如：`C2+X2→X2C2; X2C2+A2→C2+2XA`、`C2+A3→C2A3; C2A3+W3→C2+3WA` 等。\n")
    A("### ② 跨类：C2 催化，把 聚素 与 散素/动素 连接")
    A("```")
    A("第1步  C2 + O2X2C4  → 2 OC3 + X2")
    A("第2步  X2 + C2A2    → C2 + 2 XA")
    A("净反应  O2X2C4 + C2A2 → 2 OC3 + 2 XA     （C2 被再生）")
    A("```")
    A("更简单的跨类：`C2+O2→O2C2; O2C2+A3→C2+O2A3`，净反应 `O2+A3→O2A3`。\n")
    A("### ③ 聚素内：O2C2 催化")
    A("```")
    A("第1步  O2C2 + C2  → O2C4")
    A("第2步  O2C4 + O2  → 2 O2C2")
    A("净反应  C2 + O2 → O2C2      （O2C2 被再生）")
    A("```\n")
    A("## 2. 催化剂排行（真 2-环中出现次数）")
    A("CF 89、CL 86、WA 83、XA 77、XW 77、LF 76、X2 72、C2 67、X3 65、F2 60、L2 59 …")
    A("→ **低阶小分子（二聚体/一价二聚体/2价-2价双键）最容易当\"催化剂载体\"**。\n")
    A("## 3. 规律总结\n")
    A("1. 循环的存在条件（向量层面）：设循环 A→C→A，")
    A("   第一步 vA+vB = vC+ΣE1；第二步 vC+vD = vA+ΣE2 ⇒ 副产物总量 = vB+vD。")
    A("   只要系统里存在能承载 vB+vD 的副产物组合，就有循环。")
    A("2. 因为反应结果只由总向量决定，循环与具体分子式无关，只与总组成有关——同一总组成的不同物质对共享同一循环。")
    A("3. 典型模式：**小分子 A 先与伙伴 B 合并成 C，C 再与 D 反应把 A 挤出**（吸收-释放），A 净再生。")
    A("4. 这类循环是真正的\"催化\"：A 不被消耗，可反复使用；净反应只发生在 B 与 D 之间。")
    A("5. 越小的物质（1~4 原子）越容易当催化剂（因为它们的向量小、容易在第二步被重新挤出）。\n")
    A("## 4. 文件\n")
    A("- `t11_cycles4.py`（循环搜索）、`t11_cycles_report.py`（本报告与图）")
    A("- `t11_cycles.json`（全部 2-环、净反应式、分类）")
    A("- 图：`t11_cycles_cards.png`（三类循环示意图）")
    open(BASE + r"\T11B_REACTION_CYCLES.md", "w", encoding="utf-8").write("\n".join(L))
    print("saved T11B_REACTION_CYCLES.md")
