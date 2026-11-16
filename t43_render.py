# -*- coding: utf-8 -*-
"""t43_render.py：O3P5K2 演算对比图
  A) 正式规则 1~9 的 6 级中间态骨架（单个 10 原子块，13 根键，rem 4）
  B) 正式规则 1~9 的最终分子 O3P5K2（单分子，15 根键）
  C) 若规则 5 第二比较项方向取反：6 级结束就是 OP2K + O2P3K 两个骨架（最终为两个分子）
"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
import pot_all as P
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
VAL = {"O": 3, "P": 3, "K": 3}


def rems_of(atoms, edges):
    used = [0] * len(atoms)
    for (a, b, m) in edges:
        used[a] += m
        used[b] += m
    return [VAL[e] - u for e, u in zip(atoms, used)]


def main():
    trace = json.load(open(BASE + r"\t43_o3p5k2_trace.json", encoding="utf-8"))
    cat = {r["formula"]: r for r in json.load(open(BASE + r"\t4_catalog_all_validated.json",
                                                   encoding="utf-8"))}
    blk = trace["official"]["level6"][0]
    blk_form = {"atoms": blk["atoms"],
                "edges": [tuple(e) for e in blk["edges"]],
                "rems": rems_of(blk["atoms"], [tuple(e) for e in blk["edges"]])}
    # 摆放：用 pot_v2 计算
    import pot_v2
    place = pot_v2.embed_mol2(blk_form["atoms"], blk_form["edges"])
    blk_form["place"] = {i: p for i, p in place.items()}

    r = cat["O3P5K2"]
    final_form = {"atoms": r["atoms"], "edges": [tuple(e) for e in r["edges"]],
                  "rems": [0] * len(r["atoms"]),
                  "place": {int(k): tuple(v) for k, v in r["place"].items()}}

    var_forms = []
    for f in ["OP2K", "O2P3K"]:
        rr = cat[f]
        var_forms.append({"atoms": rr["atoms"], "edges": [tuple(e) for e in rr["edges"]],
                          "rems": [0] * len(rr["atoms"]),
                          "place": {int(k): tuple(v) for k, v in rr["place"].items()}})

    PW, PH = 500, 560
    W, H = 3 * PW + 40, PH + 210
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((28, 18), "O3P5K2 一锅反应：正式规则 1~9 的中间态骨架与最终骨架",
           font=R.font(R.FONT_B, 28), fill="#111111")
    d.text((28, 58), "A：6 级结束时是【一个】10 原子中间态骨架（13 根键，金框为剩余价 rem=4）；",
           font=R.font(R.FONT, 16), fill="#555555")
    d.text((28, 80), "B：之后只在同一骨架内补 2 根 P-P（0 级）键 → 最终是【一个】O3P5K2 分子（15 根键）。",
           font=R.font(R.FONT, 16), fill="#555555")
    d.text((28, 102), "C：若把规则 5 的第二比较项方向取反，6 级结束就分裂成 OP2K + O2P3K（与你的手算一致）——差异出在第 10 步。",
           font=R.font(R.FONT, 16), fill="#c0392b")

    def panel(idx, title, sub, color):
        x0 = 20 + idx * PW
        y0 = 150
        d.rectangle([x0, y0, x0 + PW - 24, y0 + PH - 20], outline="#dddddd", width=1)
        d.text((x0 + 16, y0 + 10), title, font=R.font(R.FONT_B, 20), fill=color)
        d.text((x0 + 16, y0 + 38), sub, font=R.font(R.FONT, 14), fill="#666666")
        return x0 + 16, y0 + 70, PW - 56, PH - 120

    box = panel(0, "A  6 级中间态骨架（正式规则）", "1 个连通块：O3P5K2（10 原子，13 键）", "#1e8449")
    R.draw_form(d, blk_form, box)
    box = panel(1, "B  最终分子（正式规则）", "仍是 1 个分子：O3P5K2（10 原子，15 键）", "#1e8449")
    R.draw_form(d, final_form, box)
    box = panel(2, "C  规则 5 第二项取反的变体", "6 级结束即为 OP2K + O2P3K 两个骨架", "#c0392b")
    x0, y0, w, h = box
    for k, form in enumerate(var_forms):
        sub_box = (x0 + (k % 2) * (w // 2), y0, w // 2 - 8, h)
        R.draw_form(d, form, sub_box)
        d.text((sub_box[0] + 6, sub_box[1] + h - 18), P.formula_of(form["atoms"]),
               font=R.font(R.FONT_B, 15), fill="#c0392b")

    out = BASE + r"\images\t43_o3p5k2_trace.png"
    img.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
