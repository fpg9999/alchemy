# -*- coding: utf-8 -*-
"""t9_none_report.py：不含三价元素的 175 种物质：分类、规律、全部图示"""
import json
import sys
from collections import Counter, defaultdict
from PIL import Image, ImageDraw

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t9_report as R9

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
ELEMS = "XCWLAF"
font = R9.font
FONT = R9.FONT
FONT_B = R9.FONT_B
text_center = R9.text_center
draw_formula = R9.draw_formula


def to_form(r):
    n = len(r["atoms"])
    return {"atoms": r["atoms"], "edges": [tuple(e) for e in r["edges"]],
            "rems": [0] * n, "place": {int(k): tuple(v) for k, v in r["place"].items()},
            "formula": r["formula"], "size": n, "active": 0,
            "rem_dist": {0: n}, "types": "".join(sorted(set(r["atoms"])))}


def cycle_rank(r):
    n = len(r["atoms"])
    m = len(r["edges"])
    # 连通分量数
    par = list(range(n))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for e in r["edges"]:
        i, j = e[0], e[1]
        par[find(i)] = find(j)
    comps = len({find(i) for i in range(n)})
    return m - n + comps


def degs(r):
    d = Counter()
    for e in r["edges"]:
        mult = e[2] if len(e) > 2 else 1
        d[e[0]] += mult
        d[e[1]] += mult
    return d


def main():
    data = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
    lst = data["none"]
    print("总数:", len(lst))

    # 结构分类
    fam = Counter()
    for r in lst:
        atoms = r["atoms"]
        cr = cycle_rank(r)
        dg = degs(r)
        n1 = sum(1 for s in atoms if s in "CLF")
        n2 = sum(1 for s in atoms if s in "XWA")
        if len(atoms) == 2:
            k = "双键二聚体"
        elif cr == 0:
            if max(dg.values()) == 2:
                k = "链/支链（树）"
            else:
                k = "树"
        else:
            k = "环"
        fam[(k, n1, n2)] += 1
    print("结构分类:", dict(fam))
    print("原子数分布:", dict(sorted(Counter(r["natoms"] for r in lst).items())))
    print("元素种类数分布:", dict(sorted(Counter(len(set(r["atoms"])) for r in lst).items())))

    # 按元素集合分组
    groups = defaultdict(list)
    for r in lst:
        groups["".join(sorted(set(r["atoms"])))].append(r)

    print("\n子类（元素集合）数量:", len(groups))
    for k in sorted(groups, key=lambda s: (len(s), s)):
        g = groups[k]
        sizes = sorted(r["natoms"] for r in g)
        print(f"  {k}: {len(g)} 种, 大小 {sizes[0]}~{sizes[-1]}, 最大={max(g, key=lambda r: r['natoms'])['formula']}")

    # MD 报告
    L = ["# T9-none · 不含三价元素的全部物质（175 种）\n",
         "> 三价元素（O/P/K）一个都不出现；只由 X,C,W,L,A,F 组成。",
         "> 结论：全部 ≤7 原子；大规模探测（二元池计数 0..24、三元池步长 3、六元随机大计数、等比例放大到 48/类）",
         "> 均未发现更大的分子 → **不存在 >16 原子的无三价物质**。\n",
         "## 总览\n",
         f"- 物质总数：**{len(lst)}**；原子数范围：{min(r['natoms'] for r in lst)}~{max(r['natoms'] for r in lst)}",
         f"- 元素集合（子类）数：**{len(groups)}**",
         "- 结构类型：" + "；".join(f"{k}={v}" for k, v in fam.most_common()),
         ""]
    L.append("## 按元素集合分类（全部物质）\n")
    for k in sorted(groups, key=lambda s: (len(s), s)):
        g = sorted(groups[k], key=lambda r: (r["natoms"], r["formula"]))
        L.append(f"### {k}（{len(g)} 种）")
        L.append("公式：" + "、".join(r["formula"] for r in g))
        L.append("")
    L.append("## 结构分类明细\n")
    for (k, n1, n2), v in sorted(fam.items()):
        L.append(f"- {k}（1价{n1}·2价{n2}）：{v} 种")
    open(BASE + r"\T9_NONE_ALL.md", "w", encoding="utf-8").write("\n".join(L))
    print("\nsaved T9_NONE_ALL.md")

    # 全部 175 种图示：7 列 × 7 行/页，共 4 页
    forms = [to_form(r) for r in sorted(lst, key=lambda r: (len(set(r["atoms"])), r["natoms"], r["formula"]))]
    per = 49
    for p in range((len(forms) + per - 1) // per):
        chunk = forms[p * per:(p + 1) * per]
        page = p + 1
        ncol, pw, ph = 7, 226, 232
        nrow = (len(chunk) + ncol - 1) // ncol
        left, top = 24, 96
        W = left + ncol * pw + 16
        H = top + nrow * ph + 20
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)
        d.text((24, 12), f"不含三价元素的全部物质（第 {page} 页 / 共 {(len(forms)+per-1)//per} 页）",
               font=font(FONT_B, 22), fill="#111")
        d.text((24, 44), "共 175 种；按元素种类数、原子数、公式排序。图例：红=短键S，绿=角键C，紫虚线=长键L。",
               font=font(FONT, 13), fill="#666")
        for i, f in enumerate(chunk):
            rr, cc = divmod(i, ncol)
            x0 = left + cc * pw + 2
            y0 = top + rr * ph + 2
            d.rectangle([x0, y0, x0 + pw - 4, y0 + ph - 4], outline="#e5e5e5")
            d.text((x0 + 5, y0 + 4), f"{p*per+i+1:03d}", font=font(FONT_B, 11), fill="#aaa")
            text_center(d, x0 + pw - 42, y0 + 10, f"{f['size']}原子", font(FONT, 10), "#999")
            R9.R8.draw_form(d, f, (x0 + 3, y0 + 16, pw - 8, ph - 58))
            draw_formula(d, x0 + pw / 2, y0 + ph - 26, f["formula"], 17, "#111")
        img.save(BASE + rf"\t9_none_all_{page}.png")
        print("saved", rf"t9_none_all_{page}.png")


if __name__ == "__main__":
    main()
