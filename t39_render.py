# -*- coding: utf-8 -*-
"""t39_render.py：把 T39 的「库外骨架」实例画成对比图
  A) 38 库内 O3P5K2 的 6 级块（默认并列分支）
  B) 38 库外 O3P5K2 的 6 级块（另一并列分支；同 10 原子、同分子式）
  C) 45 库外终态骨架：O3P（4 原子、6 根单键的 K4）
  D) 45 库外终态三价组件：O2CK 中的 O-K-O 三角（含 O-O 同类键）

运行：python t39_render.py
输出：images/t39_library_outside.png
"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = {"O": 3, "P": 3, "K": 3}


def rems_of(atoms, edges):
    used = [0] * len(atoms)
    for (a, b, m) in edges:
        used[a] += m
        used[b] += m
    return [VAL[e] - u for e, u in zip(atoms, used)]


def main():
    ver = json.load(open(BASE + r"\t39_library_verify.json", encoding="utf-8"))
    t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
    cat = {r["formula"]: r for r in json.load(open(BASE + r"\t4_catalog_all_validated.json",
                                                   encoding="utf-8"))}
    g = ver["genuine_example"]

    # A) 库内 O3P5K2（t8 形态）
    lib_form = next(f for f in t8 if f["formula"] == "O3P5K2")
    lib_panel = {"atoms": lib_form["atoms"],
                 "edges": [tuple(e) for e in lib_form["edges"]],
                 "rems": lib_form["rems"],
                 "place": {int(k): tuple(v) for k, v in lib_form["place"].items()}}

    # B) 库外 O3P5K2 6 级块（另一并列分支）
    blk = next(b for b in g["alt_block_structures"] if b["kind"] == "BAD")
    alt_panel = {"atoms": blk["atoms"],
                 "edges": [tuple(e) for e in blk["edges"]],
                 "rems": blk["rems"],
                 "place": {int(k): tuple(v) for k, v in blk["place"].items()}}

    # C) O3P 终态（K4）
    r = cat["O3P"]
    o3p = {"atoms": r["atoms"],
           "edges": [tuple(e) for e in r["edges"]],
           "rems": [0] * len(r["atoms"]),
           "place": {int(k): tuple(v) for k, v in r["place"].items()}}

    # D) O2CK 的终态三价组件 O-K-O
    r = cat["O2CK"]
    atoms = r["atoms"]
    edges = [tuple(e) for e in r["edges"]]
    tri_idx = [i for i, a in enumerate(atoms) if a in TRI]
    idx = {v: k for k, v in enumerate(tri_idx)}
    sub_atoms = [atoms[i] for i in tri_idx]
    sub_edges = []
    for (a, b, m) in edges:
        if a in tri_idx and b in tri_idx:
            sub_edges.append((idx[a], idx[b], m))
    place_all = {int(k): tuple(v) for k, v in r["place"].items()}
    o2ck = {"atoms": sub_atoms, "edges": sub_edges,
            "rems": rems_of(sub_atoms, sub_edges),
            "place": {k: place_all[v] for k, v in idx.items()}}

    # 画布：2×2
    PW, PH = 480, 470
    W, H = 2 * PW + 30, 2 * PH + 150
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((28, 18), "T39 · 骨架库外的骨架实例（用正确规范形 mol_label 复核）",
           font=R.font(R.FONT_B, 27), fill="#111111")
    d.text((28, 56),
           "A/B：同一物质 O3P5K2、同一分子式，不同并列分支 → 6 级块（10 原子）一个在 38 库内、一个在库外。",
           font=R.font(R.FONT, 16), fill="#555555")
    d.text((28, 80),
           "C/D：终态三价骨架 = 库内 6 级块 + 0 级同类键加固/融合（不算库外）；671 个融合形态的宿主 670/670 验证：6 级块全部在库内。",
           font=R.font(R.FONT, 16), fill="#555555")
    d.text((28, 104),
           "金框+右上角数字=剩余价（rem）；实心=价满。",
           font=R.font(R.FONT, 15), fill="#888888")

    panels = [
        (lib_panel, "A  38 库内 · O3P5K2 6 级块", "默认并列分支（与目录结构一致）", "#1e8449"),
        (alt_panel, "B  38 库外 · O3P5K2 6 级块", "另一并列分支（同分子式、骨架不同；唯一真·库外族）", "#c0392b"),
        (o3p, "C  终态融合 · O3P", "库内 6 级块 + 0 级融合（不算库外）", "#1e8449"),
        (o2ck, "D  终态融合 · O2CK 的终态三价组件", "库内块 + O-O 同类键加固（不算库外）", "#1e8449"),
    ]
    for n, (form, title, sub, color) in enumerate(panels):
        r_, c_ = divmod(n, 2)
        x0 = 16 + c_ * (PW + 0)
        y0 = 132 + r_ * PH
        d.rectangle([x0, y0, x0 + PW - 12, y0 + PH - 12], outline="#dddddd", width=1)
        d.text((x0 + 14, y0 + 10), title, font=R.font(R.FONT_B, 20), fill=color)
        d.text((x0 + 14, y0 + 38), sub, font=R.font(R.FONT, 14), fill="#666666")
        R.draw_form(d, form, (x0 + 14, y0 + 64, PW - 40, PH - 130))
        act = sum(1 for x in form["rems"] if x > 0)
        d.text((x0 + 14, y0 + PH - 52),
               f"原子={len(form['atoms'])}  活跃(rem>0)={act}  键数={sum(e[2] for e in form['edges'])}",
               font=R.font(R.FONT, 14), fill="#666666")

    out = BASE + r"\images\t39_library_outside.png"
    img.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
